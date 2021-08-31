import pycraft_utils as pu
import subprocess
import tempfile
import zipfile
import shutil
import time
import os

from multiprocessing import Process
from pycraft_module import PCMod
from datetime import datetime
from threading import Timer
from threading import Lock
from os import path

description = "Manage backups automatically."
patterns = ['backup']

seven_zip_exe = "7z" # Set to absolute path if not in %PATH% variable.

backup_method_initialized = False
use_7z = True
fast_backup = True

timer = None
min_b_time = 120 # 5 minutes
running = True
save_event = None

DEFAULT_MODULE_DATA = {
    'use-7z': use_7z,
    'quick-backup': fast_backup,
    '7z-path': seven_zip_exe
}

backup_lock = Lock()

def get_module():
    return module

def usage(subcmd=[]):
    return """Usage:   backup <now|schedule|off>: Create/schedule backups.

Subcommands:
 - now [END]: Create a manual backup right now. Specify `END` to also stop the server.
 - schedule <TIME<m|h>> [AMOUNT]: Schedule backup every TIME, up to AMOUNT automatic backups to keep (default 1).
 - off: Turn automatic backups off.

Backups are saved per server configuration under the folder 'backups'. Automatic backups will be under 'backups/auto'"""

def pyprint(string, loglevel=1):
    get_module().pyprint(string, loglevel)

def world_7z(world, new_backup_zip, auto=False):
    '''
    Requires 7z to be installed (and on path)
    Uses 7z to create a new zip archive (faster) or update using an existing (newest) archive
    '''
    pyprint("Using 7z to create backup archive", 0)
    backups_root_folder = auto_backup_folder if auto else backup_folder
    
    files = os.listdir(backups_root_folder)
    backups = []
    for file in files:
        if file.startswith(f"{universe_name}_{world_name}_") and file.endswith('.zip'):
            backups.append(file)

    with tempfile.TemporaryDirectory() as temp_folder:
        # Update existing backup file and add disk_exist_ar_not, remove ar_exist_disk_not, replace disk_new, keep ar_new, keep ar_same, replace disk_diff
        if fast_backup and len(backups) > 0:
            existing_newest_backup_zip = max([path.join(backups_root_folder, backup) for backup in backups], key=path.getmtime)
            if os.path.exists(existing_newest_backup_zip):
                pyprint(f"Updating from newest backup: {existing_newest_backup_zip}", 0)
                shutil.move(existing_newest_backup_zip, f"{temp_folder}/old.zip")
            
                cmd = [seven_zip_exe, "u", f"{temp_folder}/old.zip", "-u-", f"-up0q0r2x1y2z1w2!{temp_folder}/new.zip", "-ssw", "*", "-x!session.lock"]
        # Create new backup file and add all
        else:
            pyprint("7z will create a new backup file!", 0)
            cmd = [seven_zip_exe, "a", f"{temp_folder}/new.zip", "-ssw", "*", "-x!session.lock"]

        rc = subprocess.call(cmd, cwd=world, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) # Suppress dirty output, but may be useful for debugging.
        
        # Move the existing backup back!
        if fast_backup and len(backups) > 0:
            shutil.move(f"{temp_folder}/old.zip", existing_newest_backup_zip)
        
        if (rc != 0):
            pyprint("An unexpected error happened while backing up the files!", 3)
            return False

        shutil.move(f"{temp_folder}/new.zip", new_backup_zip)

        return True

def zip_method(world, zip_folder, auto):
    return (world_7z(world, zip_folder, auto) if use_7z else zip_world(world, zip_folder))

def close():
    global running, timer
    running = False
    if backup_lock.locked():
        pyprint('Waiting for backup to finish...')
        if not (save_event is None):
            save_event.set()
    backup_lock.acquire()
    if not (timer is None):
        timer.cancel()
        timer = None
    backup_lock.release()

def set_environment(server_config):
    global backup_folder, auto_backup_folder, world_folder, universe_name, world_name, use_7z, fast_backup, backup_method_initialized

    if not backup_method_initialized:
        world_folder = server_config['world-root']
        universe_name = server_config['universe']
        world_name = server_config['world']
        backup_folder = path.join(server_config['server-root'], 'backups')
        auto_backup_folder = path.join(backup_folder, 'auto')
        
        backup_module_data = server_config.get('module-data', {}).get('module_backup', DEFAULT_MODULE_DATA)
        seven_zip_exe = str(backup_module_data.get('7z-path', '7z'))
        use_7z = bool(backup_module_data.get('prefer-7z', True)) and (subprocess.call([seven_zip_exe], stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT) == 0)
        fast_backup = bool(backup_module_data.get('fast-backup', True))

        backup_method_initialized = True

    os.makedirs(auto_backup_folder, exist_ok=True)

def pretty_time(t):
    if (t == 1): st = '1 second'
    elif (t < 121): st = '%d seconds' % t
    elif (t < 3601): st = '%.2f minutes' % (t / 60.0)
    else: st = '%.2f hours' % (t / 3600.0)
    return st

def callback(cmd, server_config, run_cmd, event_triggers):
    global timer, save_event
    set_environment(server_config)

    save_event = event_triggers['save'].event
    h, t = pu.next_cmd(cmd)
    if h == 'now':
        make_backup(run_cmd, save_event)
        h2, t2 = pu.next_cmd(t)
        if (h2 == 'END'):
            run_cmd("stop")
    elif h == 'off':
        if not (timer is None):
            timer.cancel()
            timer = None
            pyprint('Auto-backups is turned off.')
        else:
            pyprint('Could not turn off backups as none were scheduled.', 2)
    elif h == 'schedule':
        h2, t2 = pu.next_cmd(t)
        h3, t3 = pu.next_cmd(t2)
        if h2 is None:
            pyprint('Time required to schedule a backup.', 3)
            return
        if pu.max_cmd_len(t3, 0, pyprint): return
        tm = pu.parse_time(h2, 'm')
        if tm < min_b_time:
            pyprint('Time given is below minimum time of 5 minutes.', 3)
            return
        amount = 1
        if not (h3 is None) and int(h3) > 0:
            amount = int(h3)
        if not (timer is None):
            timer.cancel()
            timer = None
            pyprint('Replaced previous backup schedule.')
        timer = Timer(tm, schedule_backup, [tm, amount, run_cmd, save_event])
        timer.start()
        pyprint('Backup has been scheduled to run every %s (max: %s backup%s)!' % (pretty_time(tm), amount, 's' if amount > 1 else ''))

def truncate(max_auto_backups):
    while True:
        files = os.listdir(auto_backup_folder)
        backups = []
        for file in files:
            if file.startswith(f"{universe_name}_{world_name}_") and file.endswith('_apcbkp.zip'):
                backups.append(file)
        if len(backups) > max_auto_backups:
            of = min([path.join(auto_backup_folder, f) for f in backups], key=path.getctime)
            pyprint(f"Deleted oldest backup: {of}", 0)
            os.remove(of)
        else:
            break

def schedule_backup(t, a, run_cmd, save_event):
    global timer

    make_backup(run_cmd, save_event, True)
    
    # Truncate afterwards so 7z can fully utilize other backup for quick backups
    truncate(a)
    
    if (not (timer is None) and running):
        pyprint('Next backup is scheduled to run in %s!' % pretty_time(t))
        timer = Timer(t, schedule_backup, [t, a, run_cmd, save_event])
        timer.start()

def root_from(world, root):
    return root[len(world):].lstrip(path.sep)

def zip_world(world, backup_zip):
    # Speedup for automatic backups.
    pyprint("Using py.stdlib: zipfile to create backup archive", 0)
    p = Process(target=multi_zip, args=[world, backup_zip, world_name])
    p.start()
    p.join()

def multi_zip(world, backup_zip, world_name):
    zipf = zipfile.ZipFile(backup_zip, 'w', zipfile.ZIP_DEFLATED)
    pyprint(f'Creating backup at "{backup_zip}"')

    for root, dirs, files in os.walk(world):
        for file in files:
            if file == "session.lock":
                continue
            loc = path.join(path.join(world_name, root_from(world, root)), file)
            pyprint('Backing up: %s' % loc, 0)
            zipf.write(path.join(root, file), loc)
    zipf.close()

def make_backup(run_cmd, save_event, auto=False):
    if not running:
        pyprint("Can't backup while server is shutting down.", 2)
        return
    if backup_lock.locked():
        pyprint('A backup is already in progress.', 2)
        return
    backup_lock.acquire()
    perf_start = time.time()
    if running:
        run_cmd('save-off')
        run_cmd('save-all flush')
        pyprint('Waiting for server to finish saving...')
        save_event.wait()
    pyprint('Performing server backup!')

    today = datetime.now()
    df = today.strftime("%Y-%m-%d_%H-%M-%S")

    if auto:
        zip_name = f"{universe_name}_{world_name}_{df}_apcbkp.zip"
        store_location = path.join(auto_backup_folder, zip_name)
    else:
        zip_name = f"{universe_name}_{world_name}_{df}.zip"
        store_location = path.join(backup_folder, zip_name)
    
    success = zip_method(world_folder, store_location, auto)

    if running:
        run_cmd('save-on')

    perf_end = time.time()
    perf_elapsed = (perf_end - perf_start)
    pyprint(f'Backup took {int(int(perf_elapsed) / 60)}m{int(perf_elapsed) % 60}s!', 1)   
    if success:
        pyprint('Server backup created!')
    else:
        pyprint('An error happened during backup creation!', 3)
    backup_lock.release() 

module = PCMod(__name__, description, patterns, callback, close, usage)