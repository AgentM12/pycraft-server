import pycraft_utils as pu
import zipfile
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

timer = None
min_b_time = 300 # 5 minutes
running = True
save_event = None

backup_lock = Lock()

def get_module():
    return module

def usage(subcmd=[]):
    return """Usage:   backup <now|schedule|off>: Create/schedule backups.

Subcommands:
 - now: Create a manual backup right now.
 - schedule <TIME<m|h>> [AMOUNT]: Schedule backup every TIME, up to AMOUNT automatic backups to keep (default 1).
 - off: Turn automatic backups off.

Backups are saved per server configuration under the folder 'backups'. Automatic backups will be under 'backups/auto'"""

def pyprint(string, loglevel=1):
    get_module().pyprint(string, loglevel)

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
    global backup_folder, auto_backup_folder, world_folder, universe_name, world_name
    backup_folder = path.join(server_config['server-root'], 'backups')
    auto_backup_folder = path.join(backup_folder, 'auto')
    world_folder = server_config['world-root']
    universe_name = server_config['universe']
    world_name = server_config['world']

    os.makedirs(path.join(backup_folder, 'auto'), exist_ok=True)

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

def schedule_backup(t, a, run_cmd, save_event):
    global timer
    while True:
        files = os.listdir(auto_backup_folder)
        backups = []
        for file in files:
            if file.startswith(f"{universe_name}_{world_name}_") and file.endswith('_apcbkp.zip'):
                backups.append(file)
        if len(backups) >= a:
            of = min([path.join(auto_backup_folder, f) for f in backups], key=path.getctime)
            pyprint(f"Deleted oldest backup: {of}", 0)
            os.remove(of)
        else:
            break

    make_backup(run_cmd, save_event, True)
    if (not (timer is None) and running):
        pyprint('Next backup is scheduled to run in %s!' % pretty_time(t))
        timer = Timer(t, schedule_backup, [t, a, run_cmd, save_event])
        timer.start()

def root_from(world, root):
    return root[len(world):].lstrip(path.sep)

def zip_world(world, backup_zip):
    # Speedup for automatic backups.
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
    
    zip_world(world_folder, store_location)

    if running:
        run_cmd('save-on')
    pyprint('Server backup created!')
    backup_lock.release()    

module = PCMod(__name__, description, patterns, callback, close, usage)