import pycraft_utils as pu

import re

from pycraft_module import PCMod
from threading import Thread
from threading import Event
from threading import Lock
# from winsound import Beep

description = "Tool to notify on certain events (by ringing the bell)"
patterns = ['notify']

join_notification = False
leave_notification = False

chat_patterns = []
pattern_lock = Lock()

def get_module():
    return module

join_kill_event = Event()
leave_kill_event = Event()
chat_kill_event = Event()

join_thread = None
leave_thread = None
chat_thread = None

def usage(subcmd=[]):
    return """Usage:   notify <SUBCOMMANDS>

Subcommands include:
 - query: Shows which notifications are on and off.
 - join [on|off]: Toggle notifications on join.
 - leave [on|off]: Toggle notifications on leave.
 - chat add <Search Pattern>: Notifies when this chat pattern is found.
 - chat remove (all|<index>): Removes this index from the patterns, or all."""

def pyprint(string, loglevel=1):
    get_module().pyprint(string, loglevel)

def choice(v, t, f):
    return t if v else f

def ed(v):
    return choice(v, 'enabled', 'disabled')

def event_callback(et, k):
    while not k.is_set():
        if et.event.wait(1):
            print('\u0007', end='', flush=True)
            # Beep(750, 100)
            # Beep(1000, 100)

def chat_event_callback(et, k):
    while not k.is_set():
        if et.event.wait(1):
            c = et.match.group(2)
            pattern_lock.acquire()
            for p in chat_patterns:
                if p.match(c):
                    print('\u0007', end='', flush=True)
                    # Beep(750, 100)
                    # Beep(1000, 100)
            pattern_lock.release()

def update_event(value, ov, t, e, k):
    if value is None: rt = not ov
    elif value == 'on': rt = True
    elif value == 'off': rt = False
    else:
        pyprint("Did not recognize %s as 'on' or 'off'." % value)
        return None

    if t is None and rt:
        t = Thread(target=event_callback, args=(e, k))
        t.start()
    elif not rt:
        k.set()
        t.join()
        t = None
        k.clear()
    return rt, t

def command_parser(cmd, server_config, run_cmd, event_triggers):
    global join_thread, leave_thread, chat_thread
    global join_notification, leave_notification, chat_patterns

    key, sub = pu.next_cmd(cmd)
    if key == "query":
        if pu.max_cmd_len(sub, 0, pyprint): return
        pyprint("Join: %s\nLeave: %s\nChat: %s" % (ed(join_notification), ed(leave_notification), '\n'.join([p.pattern for p in chat_patterns])))
    elif key == "join":
        key2, sub2 = pu.next_cmd(sub)
        if pu.max_cmd_len(sub2, 0, pyprint): return

        rt, t = update_event(key2, join_notification, join_thread, event_triggers['join'], join_kill_event)
        if rt is None: return
        join_notification = rt
        join_thread = t
        pyprint("Join: %s" % ed(rt))
    elif key == "leave":
        key2, sub2 = pu.next_cmd(sub)
        if pu.max_cmd_len(sub2, 0, pyprint): return
        
        rt, t = update_event(key2, leave_notification, leave_thread, event_triggers['leave'], leave_kill_event)
        if rt is None: return
        leave_notification = rt
        leave_thread = t
        pyprint("Leave: %s" % ed(rt))
    elif key == 'chat':
        key2, sub2 = pu.next_cmd(sub)
        if key2 is None:
            pyprint('Too little arguments, specify "add" or "remove"!', 2)
            return
        key3 = ' '.join(sub2)

        if key3 is None or key3 == '':
            pyprint('Too little arguments, specify the regex!', 2)
            return
        
        pattern_lock.acquire()
        if key2 == 'add':
            try:
                regex = re.compile(key3)
                chat_patterns.append(regex)
                pyprint("Added chat pattern: '%s'" % chat_patterns[-1].pattern)
            except:
                pyprint("Regex '%s' provided is incorrect!" % key3, 2)
                pattern_lock.release()
                return
        elif key2 == 'remove':
            if key3 == 'all':
                chat_patterns = []
                pyprint("Removed all chat patterns!")
            else:
                try:
                    i = int(key3)
                    if i >= 0 and i < len(chat_patterns):
                        pyprint("Removed chat pattern: '%s'" % chat_patterns[i].pattern)
                        del chat_patterns[i]
                    else:
                        pyprint("Chat pattern with index %s doesn't exist!" % key3, 2)
                        pattern_lock.release()
                        return
                except:
                    pyprint("'%s' is not a valid index!" % key3, 2)
                    pattern_lock.release()
                    return

        if chat_thread is None and len(chat_patterns) > 0:
            chat_thread = Thread(target=chat_event_callback, args=(event_triggers['any'], chat_kill_event))
            chat_thread.start()
        elif len(chat_patterns) == 0:
            chat_kill_event.set()
            chat_thread.join()
            chat_thread = None
            chat_kill_event.clear()
        pattern_lock.release()
    else:
        pyprint(usage())

def close():
    ''' End all threads '''
    join_kill_event.set()
    leave_kill_event.set()
    chat_kill_event.set()
    if join_thread is not None: join_thread.join()
    if leave_thread is not None: leave_thread.join()
    if chat_thread is not None: chat_thread.join()


module = PCMod(__name__, description, patterns, command_parser, close, usage)