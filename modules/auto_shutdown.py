import pycraft_utils as pu

import os
import time

from pycraft_module import PCMod
from mcstatus import MinecraftServer
from threading import Thread
from threading import Event
from threading import Timer

description = "Tool to automatically shutdown the server."
patterns = ['as', 'auto-shutdown']

def get_module():
    return module

exit_event = Event()
server_status_thread = None

class MyTimer(Timer):
    start_time = None
    last_time = None
    started = False
    
    def __init__(self, t, target, args, actual_t):
        super().__init__(t, target, args)
        self.last_time = actual_t

    def start(self):
        self.start_time = time.time()
        self.started = True
        Timer.start(self)

    def elapsed(self):
        return time.time() - self.start_time

    def remaining(self):
        return self.last_time - self.elapsed()

timer = None
hard = False

def close():
    global timer
    stop_watchdog()
    if not (timer is None):
        timer.cancel()
        timer = None

def usage(subcmd=[]):
    return """Usage:   as|auto-shutdown <SUBCOMMANDS>

Subcommands include:
 - query: Shows the current scheduled shutdown.
 - idle <TIME[s][m][h]> [HARD]: Shuts down the server if the server has had 0 players online for the given TIME.
 - schedule <TIME[s|m|h]> [HARD]: Schedules a shutdown in TIME, set HARD to also schedule computer shutdown.
 - cancel: Cancels any scheduled shutdowns."""

def pyprint(string, loglevel=1):
    get_module().pyprint(string, loglevel)

def server_status(port, t, run_cmd):
    global timer
    poll_delay = max(10, min(t // 10, 120))

    def reset_timer():
        global timer

        if t > 59: timer = MyTimer(max(0, t - 60), start_countdown, [60, run_cmd], t)
        else: timer = MyTimer(max(0, t - 10), start_countdown, [min(10, int(t)), run_cmd], t)

    server = MinecraftServer.lookup('127.0.0.1:%s' % port)
    reset_timer()
    while not exit_event.is_set():
        try:
            status = server.status().players.online
            if status < 1 and not timer.started:
                run_cmd("say [Auto Shutdown] No players online, will shutdown in %s from now!" % pretty_time(t))
                timer.start()
            elif status > 0 and timer.started:
                pyprint('Shutdown canceled, because of player login.')
                timer.cancel()
                reset_timer()
        except ConnectionRefusedError:
            pyprint("Could not connect to the server!", 3)
        except IOError:
            pyprint("Server is not ready yet!", 3)

        exit_event.wait(poll_delay)
    if not (timer is None):
        timer.cancel()
        timer = None

def pretty_time(t):
    if (t == 1): st = '1 second'
    elif (t < 121): st = '%d seconds' % t
    elif (t < 3601): st = '%.2f minutes' % (t / 60.0)
    else: st = '%.2f hours' % (t / 3600.0)
    return st

def stop_watchdog():
    global server_status_thread
    if server_status_thread is not None:
        exit_event.set()
        server_status_thread.join()
        exit_event.clear()
        server_status_thread = None
        pyprint('Player watchdog has been turned off.')

def command_parser(cmd, server_config, run_cmd, event_triggers):
    global hard, timer, server_status_thread

    key, sub = pu.next_cmd(cmd)
    if key == "query":
        if pu.max_cmd_len(sub, 0, pyprint): return
        if timer is None:
            pyprint("No shutdown is currently scheduled.")
        else:
            if timer.started:
                pyprint("%s before shutdown!" % pretty_time(timer.remaining()))
            else:
                pyprint("Idle timer set to %s! (players online might prevent countdown)" % pretty_time(timer.last_time))
    elif key == "cancel":
        if pu.max_cmd_len(sub, 0, pyprint): return
        v = False
        if not (timer is None):
            timer.cancel()
            timer = None
            run_cmd("say [Auto Shutdown] Automatic shutdown was canceled!")
            v = True
        if server_status_thread is not None:
            stop_watchdog()
            v = True
        if not v:
            pyprint('Could not cancel, as no shutdown was scheduled.', 2)
    elif key == "schedule":
        key2, sub2 = pu.next_cmd(sub)
        if key2 is None:
            pyprint("You must specify a time for scheduling a shutdown!", 3)
            return
        if pu.max_cmd_len(sub2, 1, pyprint): return
        try:
            t = pu.parse_time(key2)
            if (t < 0): t = 0
            
            hard = True if len(sub2) > 0 and sub2[0] == 'HARD' else False
            if (hard):
                pyprint('HARD parameter has been set. The system will shutdown in 30 seconds after the server is closed.', 2)
            stop_watchdog()
            if not (timer is None):
                timer.cancel()
                pyprint('Previous scheduled shutdown was replaced.', 1)
            
            if t > 59: timer = MyTimer(max(0, t - 60), start_countdown, [60, run_cmd], t)
            else: timer = MyTimer(max(0, t - 10), start_countdown, [min(10, int(t)), run_cmd], t)
            timer.start()

            run_cmd("say [Auto Shutdown] Server scheduled to close in %s!" % pretty_time(t))
        except Exception:
            pyprint('Error in command: %s' % sub, 3)
    elif key == 'idle':
        key2, sub2 = pu.next_cmd(sub)
        if key2 is None:
            pyprint("You must specify an idle time for scheduling a shutdown!", 3)
            return
        if pu.max_cmd_len(sub2, 1, pyprint): return
        try:
            t = pu.parse_time(key2)
            if (t < 0): t = 0
            
            hard = True if len(sub2) > 0 and sub2[0] == 'HARD' else False
            if (hard):
                pyprint('HARD parameter has been set. The system will shutdown in 30 seconds after the server is closed.', 2)
            if not (timer is None):
                timer.cancel()
                pyprint('Previous scheduled shutdown was replaced.', 1)
            stop_watchdog()
            
            server_status_thread = Thread(target=server_status, args=(server_config['port'], t, run_cmd))
            server_status_thread.daemon = True
            server_status_thread.start()

            run_cmd("say [Auto Shutdown] Server will automatically close if no players have been online for at least %s!" % pretty_time(t))
        except Exception:
            print('Error in command: %s' % sub, 3)
    else:
        pyprint(usage())

def shutdown_server(run_cmd):
    stop_watchdog()
    run_cmd("say [Auto Shutdown] Server shutting down!")
    run_cmd("stop")
    if hard: shutdown_pc()

def start_countdown(t, run_cmd, poll_players_server=None):
    global timer, running, server_status_thread

    if not (poll_players_server is None) and t % 2 == 0:
        try:
            status = poll_players_server.status().players.online
            if status > 0:
                run_cmd("say [Auto Shutdown] Automatic shutdown was canceled, because a player logged in!")
                return
        except (ConnectionRefusedError, IOError):
            pyprint("No server response!", 3)
    if (t == 0):
        shutdown_server(run_cmd)
    elif (t == 60):
        run_cmd("say [Auto Shutdown] Server will automatically close in %s!" % pretty_time(t))
        timer = MyTimer(50, start_countdown, [10, run_cmd, poll_players_server], t)
        timer.start()
    else:
        run_cmd("say [Auto Shutdown] Server closes in %s..." % pretty_time(t))
        timer = MyTimer(1, start_countdown, [t - 1, run_cmd, poll_players_server], t)
        timer.start()

def shutdown_pc():
    pyprint(' --- INITIATING FULL SYSTEM SHUTDOWN IN 30 SECONDS AS REQUESTED! --- ', 3)
    os.system("shutdown /s /t 30");

module = PCMod(__name__, description, patterns, command_parser, close, usage)