'''
A PyCraft module is basically a custom console command that allows to interact with the server.
Some basic modules have been added already to serve as an example and also because they're very generic and useful.

You can create your own by very easily and modules can be hotfixed dynamically, removed, added, etc.

To create a PyCraft Server Module, you need:
 - get_module(): Should return a PCMod object.
'''

severities = ['DEBUG', 'INFO', 'WARN', 'ERROR']

# From most to least ERROR, WARN, INFO, DEBUG. setting the least significant to 0, disables debug warning.
log_flag = 0b1110

class PCMod:

    def __init__(self, name, description, patterns, callback, close_callback, help_callback=lambda _: 'No help specified.'):
        '''
        name: Should be __name__
        description: Human readable description.
        patterns: The patterns on which to match this command.
        callback: The function to call when matched on pattern. Takes all subcommands, server_config and stdin as arguments.
        help_callback: The function to call when help <name> is ran. Takes all subcommands as argument.
        close_callback: Function run when the server is closed. Use this to join threads, close resources and cleanup.
        '''
        self.name = name
        self.description = description
        self.patterns = [p for p in patterns]
        self.callback = callback
        self.help_callback = help_callback
        self.close = close_callback if not (close_callback is None) else lambda: None

    def matches(self, cmd):
        '''
        Returns True if matched on any pattern else False.
        '''
        for p in self.patterns:
            if p == cmd:
                return True
        return False

    def execute(self, subcmd, server_config, stdin, event_triggers):
        '''
        subcmd: The remaining subcommands after the matched pattern.
        server_config: The server config specific to this server, including port, name, etc.
        stdin: The inputstream of the server, which allows writing commands to it such as say, stop, etc.
        event_triggers: Dict of events that can be triggered (see pycraft_server for a list of them).
        '''
        self.callback(subcmd, server_config, lambda x: stdin.write(x + "\n"), event_triggers)

    def pyprint(self, string, loglevel=1):
        '''
        Prints with a convenient loglevel and format.
        '''
        if ((2 ** loglevel) & log_flag) != 0:
            print("[PyCraft.%s/%s] %s" % (self.name, severities[loglevel], string))

    def help(self, subcmd):
        '''
        subcmd: The remaining subcommands.
        '''
        self.pyprint(self.help_callback(subcmd))

