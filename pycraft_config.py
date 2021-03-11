import json

from os import path

#GLOBALS
config_file = 'config.json'
servers_location = 'servers'

def read_config():
    if not path.exists(config_file):
        return None
    with open(config_file, 'r') as f:
        c = ''.join(f.readlines()).strip()
        if len(c) == 0:
            return None # Check for an empty file.
    with open(config_file, 'r') as f:
        return json.load(f)

def write_config(data):
    with open(config_file, 'w+') as f:
        return json.dump(data, f, indent=4)

def default_config():
    config = {
        'jvm-args': [],
        'hide-gui': True,
        'upgrade-when-update': False,
        'server-list': []
    }

    return config

def main():
    config = read_config()
    if config == None:
        print("Config file does not exist yet and will be created!")
        config = default_config()
    running = True

    def stop():
        nonlocal running
        running = False

    def modify_jvm_args():
        nonlocal config, running

        while(running):
            print('')
            print(' === Current jvm-args ===\n%s' % config['jvm-args'])
            print('')
            print('Edit jvm-args:')
            print('- Add <VALUE>: Adds VALUE as a new argument.')
            print('- Remove <N>: Removes the n-th value from the list. (1-indexed)')
            print('- Back: Go back')

            c = input('> ')
            cl = c.lower()
            
            if cl == 'exit' or cl == 'quit':
                running = False
                return
            if cl.startswith('back') or len(c.strip()) == 0:
                return
            if cl.startswith('remove '):
                s = c.split(" ", 1)[1]
                try:
                    i = int(s) - 1
                    try:
                        if (i < 0):
                            raise IndexError("Can't directly access negative index.")
                        del config['jvm-args'][i]
                    except IndexError:
                        print('Failed to remove at index %d' % (i+1))
                except ValueError:
                    print('Invalid index: %s should be integer.' % s)
            elif cl.startswith('add '):
                s = c.split(" ", 1)[1]
                config['jvm-args'].append(s)
            else:
                print('Invalid input: %s' % c)

    def toggle(k):
        nonlocal config
        config[k] = not config[k]

    def toggle_hide_gui():
        toggle('hide-gui')

    def toggle_upgrade_when_update():
        toggle('upgrade-when-update')

    def pretty_print_list(list_name, ls):
        i = 1
        print(list_name)
        for s in ls:
            print("%d: %s" % (i, s))
            i += 1

    def is_int(c):
        try:
            int(c)
            return True
        except:
            False

    def edit_init(index):
        nonlocal config, running

        while(running):
            print('')
            pretty_print_list(" === Commands to run on startup ===", config['server-list'][index]['initialize'])
            print('')
            print('Modify list: ')
            print('- Add <COMMAND>: Add the command COMMAND to the end of the list.')
            print('- Remove <N>: Remove n-th init command. (1-indexed)')
            print('- Back: Go back')

            c = input('> ')
            cl = c.lower()
            
            if cl == 'exit' or cl == 'quit':
                running = False
                return
            if cl.startswith('back') or len(c.strip()) == 0:
                return
            if cl.startswith('add '):
                cmd = c.split(" ", 1)[1]
                config['server-list'][index]['initialize'].append(cmd)
            elif cl.startswith('remove '):
                num = int(c.split(" ", 1)[1]) - 1
                del config['server-list'][index]['initialize'][num]


    def server_list_editor():
        nonlocal config, running

        while(running):
            print('')
            ls = [d['name'] if len(d['description']) == 0 else "%s -- %s" % (d['name'], d['description']) for d in config['server-list']]
            pretty_print_list(" === Server configurations ===", ls)
            print('')
            print('Modify list: ')
            print('- Add: Step by step tool to add a server config.')
            print('- View <N>: View settings of a certain server config by index N. (1-indexed)')
            print('- Init <N>: Tool to add commands to run when server starts up. (1-indexed)')
            print('- Remove <N>: Remove n-th server config. (1-indexed)')
            print('- Back: Go back')

            c = input('> ')
            cl = c.lower()
            
            if cl == 'exit' or cl == 'quit':
                running = False
                return
            if cl.startswith('back') or len(c.strip()) == 0:
                return
            if cl.startswith('init '):
                s = c.split(" ", 1)[1]
                try:
                    i = int(s) - 1
                    try:
                        if (i < 0):
                            raise IndexError("Can't directly access negative index.")
                        sc = config['server-list'][i]
                        edit_init(i)
                    except IndexError:
                        print('Failed to remove at index %d' % (i+1))
                except ValueError:
                    print('Invalid index: %s should be integer.' % s)
            elif cl.startswith('remove '):
                s = c.split(" ", 1)[1]
                try:
                    i = int(s) - 1
                    try:
                        if (i < 0):
                            raise IndexError("Can't directly access negative index.")
                        del config['server-list'][i]
                    except IndexError:
                        print('Failed to remove at index %d' % (i+1))
                except ValueError:
                    print('Invalid index: %s should be integer.' % s)
            elif cl.startswith('add'):
                new_name = input('Server/Config name: ').strip()
                loc = input('Server Worlds save location (Blank for default "worlds"): ').strip()
                new_universe = loc if len(loc) > 0 else 'worlds'
                world = input('World name (Blank for default "world"): ').strip()
                new_world = world if len(world) > 0 else 'world'
                new_desc = input('Human friendly description (optional): ').strip()
                new_vers = input('Version type ("release", "snapshot", etc.): ').strip().lower()
                c = input('Port number (1-65535): ').strip()
                new_port = int(c) if is_int(c) and int(c) > 0 and int(c) < 65536 else 0
                c = input('Auto update (Y/N): ').strip().lower()
                new_updt = True if c.startswith('y') or c.startswith('t') else False
                c = input('Auto restart (Y/N): ').strip().lower()
                new_rest = False if c.startswith('n') or c.startswith('f') else True
                c = input('Read only (Y/N): ').strip().lower()
                new_read = True if c.startswith('y') or c.startswith('t') else False

                new_config = {
                    'name': new_name,
                    'universe': new_universe,
                    'world': new_world,
                    'description': new_desc,
                    'port': new_port,
                    'version': new_vers,
                    'auto-update': new_updt,
                    'auto-restart': new_rest,
                    'read-only': new_read,
                    'initialize': []
                }
                config['server-list'].append(new_config)
                print('Success!')
            # elif cl.startswith('modify '):
            #     s = c.split(" ", 1)[1].strip()
            #     try:
            #         i = int(s) - 1
            #         try:
            #             if (i < 0):
            #                 raise IndexError("Can't directly access negative index.")
            #             key = input('Key to update: ')
            #             value = input('Value to update: ')
            #             old_value = config['server-list'][i][key]
            #             if type(value) != type(old_value):
            #                 print("Type of old and new value don't match!")
            #             else:
            #                 config['server-list'][i][key] = value # Allows illegal values
            #         except IndexError:
            #             print('Failed to view at index %d' % (i+1))
            #     except ValueError:
            #         print('Invalid index: %s should be integer.' % s)
            elif cl.startswith('view '):
                s = c.split(" ", 1)[1].strip()
                try:
                    i = int(s) - 1
                    try:
                        if (i < 0):
                            raise IndexError("Can't directly access negative index.")
                        print('')
                        [print("%s: %s" % (k, v)) for k, v in config['server-list'][i].items()]
                    except IndexError:
                        print('Failed to view at index %d' % (i+1))
                except ValueError:
                    print('Invalid index: %s should be integer.' % s)
            else:
                print('Invalid input: %s' % c)

    functions = [
        stop,
        modify_jvm_args,
        toggle_hide_gui,
        toggle_upgrade_when_update,
        server_list_editor
    ]

    print('This is the server configuration editor tool.')
    print('The format is - Command|Alias: Description')

    while(running):
        print('')
        print('Server config options: ')
        print('- 1: Modify "jvm-args" (%s)' % config['jvm-args']) 
        print('- 2: Toggle "hide-gui" (%s)' % config['hide-gui'])
        print('- 3: Toggle "optimize-on-startup" (%s)' % config['upgrade-when-update'])
        print('- 4: View/Modify "server-list"')
        print('- quit|exit: Exit this tool at any time.')
        
        try:
            s = input('> ')
            if s.lower() == 'exit' or s.lower() == 'quit':
                running = False
            else:
                c = int(s)
                if c < 0:
                    raise IndexError("Can't directly access negative index.")
                functions[c]()
        except (ValueError, IndexError):
            print("Invalid input!")
            continue

    write_config(config)

main()