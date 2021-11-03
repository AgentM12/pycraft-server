import pycraft_utils as pu

import re

from pycraft_module import PCMod
from mcstatus import MinecraftServer

description = "Get server status from current server."
patterns = ['status']

def get_module():
    return module

def usage(subcmd=[]):
    return """Usage:   status [ping|query [PORT]]

Without subcommands: Get some generic server info.
With subcommand:
 - ping: Get the server ping.
 - query [PORT]: Get some detailed server info. Query run from PORT. (will return a failure if enable.query=false)"""

def pyprint(string, loglevel=1):
    get_module().pyprint(string, loglevel)

def callback(cmd, server_config, run_cmd, event_triggers):
    h, t = pu.next_cmd(cmd)
    port = int(server_config['port'])
    if len(t) > 0:
        if pu.max_cmd_len(t, 1, pyprint): return
        port = int(t[0])
        if port > 65535 or port < 1:
            pyprint("Invalid port: %s" % str(port))
            return
    server_status(port, h)

def format_strip(string):
    return re.sub(re.compile('§.'), '', string)

def server_status(port, variant):
    if variant is None:
        variant = 'status'
    try:
        if variant == 'ping' or variant == 'status' or variant == 'query' or variant == 'test':
            server = MinecraftServer('127.0.0.1', port)
            if variant == 'ping':
                pyprint("Ping: %sms" % server.ping())
            elif variant == 'status':
                s = server.status()
                f = 'x' if s.favicon is None else '^_^'
                description = format_strip(s.description) if isinstance(s.description, str) else format_strip(s.description['text'])
                sample = s.players.sample
                if sample is None:
                    if s.players.online > 0:
                        sample = "<Hidden>"
                    else:
                        sample = "<None>"
                pyprint("Status returned:\n"
                        " - ping: %s ms [%s]\n"
                        " - version: %s (protocol %s)\n"
                        " - description: %s\n"
                        " - players (%s/%s): %s" % (s.latency, f, s.version.name, s.version.protocol, description, s.players.online, s.players.max, sample))
            elif variant == 'query':
                s = server.query()
                pyprint("Query returned:\n"
                        " - game: %s (%s)\n"
                        " - ip: %s:%s\n"
                        " - version: %s (%s)\n"
                        " - description: %s\n"
                        " - map: %s\n"
                        " - plugins: %s\n"
                        " - players (%s/%s): %s" % (s.raw['game_id'], s.raw['gametype'], s.raw['hostip'], s.raw['hostport'], s.software.version, s.software.brand, format_strip(s.motd), s.map, s.software.plugins, s.players.online, s.players.max, s.players.names))
    except ConnectionRefusedError:
        pyprint("Could not connect to the server!", 3)
    except ConnectionResetError:
        pyprint("Query is not enabled on the server!", 3)
    except IOError:
        pyprint("Server is not ready yet!", 3)


module = PCMod(__name__, description, patterns, callback, None, usage)