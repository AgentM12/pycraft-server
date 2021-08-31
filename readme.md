# PyCraft Server #
Pycraft Server is a collection of tools that can be used while running a server. Basic usage allows running a minecraft server with arguments more easily, run backups and automatically shut down the server when no players are online for some time.

PyCraft Server is a bundle of python scripts written by [AgentM](https://www.youtube.com/c/AgentMOfficial)  
Special thanks to Dinnerbone for [mcstatus](https://github.com/Dinnerbone/mcstatus)

**Documentation version: 1.0**  
**Script version: `<can be seen when running server.py>`**  
*Make sure these match before contacting me.*

## Table of Contents ##
 1. [Installation](#install)
 2. [Basic Usage](#basic)
   - Setting up a PyCraft server
     - PyCraft file structure
     - PyCraft server config file
   - Running a PyCraft server
     - PyCraft command line
   - Using built-in commands
     - help
     - stop | quit | exit
     - modules
 3. [Built-in Modules](#modules)
   - auto-shutdown | as
   - backup
   - status
   - notify
 4. [Advanced Usage](#advanced)
   - Creating your own modules
     - Bare bones
     - Running server commands
     - Server Config
     - Events

<a name="install">

## 1. Installation ##
</a>

You need Python 3.X to run the scripts.  
Also, install mcstatus from: [https://github.com/Dinnerbone/mcstatus](https://github.com/Dinnerbone/mcstatus)

Then, installation is as simple as:
1. Extracting the contents of the zip to some safe folder (I like to put it under C:/MCServers or something).
2. Putting a server.jar in a ServerName folder in servers.
3. (Running the server to generate a server.properties and eula, if you haven't already)
4. Creating a configuration for this server by running `python pycraft_config.py`
5. Running `python pycraft.py ServerName`.
6. (Optionally) Run `python pycraft_updater.py` in conjunction with `auto-update` set to `true` in `config.json` to update all your servers.

If you have any trouble, check my YouTube channel for the tutorial: [https://www.youtube.com/c/AgentMOfficial](https://www.youtube.com/c/AgentMOfficial)  
You can contact me in the comments for any further questions.

<a name="basic">

## 2. Basic Usage ##
</a>

### Setting up a PyCraft server ###

#### PyCraft file structure
The PyCraft server will need a couple files and folders to work.

```
- (root)
  - [modules]
    - auto_shutdown.py
    - backup.py
    - status.py
    - ...
  - [servers]
    - [SomeServer]
      - [backups]
        - [auto]
          - world1_2020-12-01_23-55-00.zip
        - world1_2020-12-01-23-54-00.zip
      - [logs]
      - [worlds]
        - [world1]
          - level.dat
          - ...
      - eula.txt
      - server.jar
      - server.properties
      - server-icon.png
      - ...
  - config.json
  - pycraft.py
  - pycraft_config.py
  - pycraft_module.py
  - pycraft_updater.py
  - pycraft_utils.py
  - readme.md
```

The `...` represent other files and folders, for example, those created by the server.jar or custom modules.

For every server folder ("SomeServer" in the example above), there must be an entry in the config.json file specifying how to run it. The structure of such a config.json file is given below.

#### PyCraft server config file ####

A config.json file contains the configuration information for the PyCraft and its modules on how to run the servers and with which parameters.

You can run `python pycraft_config.py` from the command line to create and edit such config file.

The basic barebones config file looks like this:

``` json
{
    "jvm-args": [],
    "hide-gui": true,
    "upgrade-all-chunks-on-version-mismatch": false,
    "module-data": {
      "module_<module_name>": {
        "module_config_setting": "Any"
      }
    },
    "server-list": [
        {
            "name": "ServerName",
            "universe": "worlds",
            "world": "test_world",
            "version": "custom",
            "port": 25565,
            "description": "Test server for the development of PyCraft.",
            "auto-update": false,
            "auto-restart": false,
            "read-only": false,
            "initialize": [
                "modules list",
                "/say This message will appear when the server is ready."
            ]
        }
    ]
}
```

These config settings apply to every server configuration that is run. For any specific server configuration settings, apply them in "server-list" under the server for which you want to apply that config.

- `jvm-args` (list\<str\>): A list of str arguments to pass to the java virtual machine (to increase RAM for example)
- `hide-gui` (bool): Hide the server console window from popping up.
- `upgrade-all-chunks-on-version-mismatch` (bool): If the server should upgrade/optimize chunks when it has recently been updated to a different version.
- `module-data` (dict): Any custom configuration settings used by modules. The convention is to use `module_<module_name>` for the key to properly namespace settings. `shared` could be used for any config settings shared between modules.
<!--"upgrade-all-chunks-on-version-mismatch" will probably be moved to server specific config-->


- `server-list` (list\<dict\>): A list of all server configurations. Each server must have the following keys:
  - `name` (str): The exact same name as the server folder (server.jar is in this folder)
  - `universe` (str): The name of the universe (location of all server worlds).
  - `world` (str): The name of the world.
  - `version` (str): The type of version the server runs on (for auto updates), can be "release" or "snapshot", "custom" if you don't want to use auto-updates, or if using modded versions.
  - `port` (int\<0-65536\>): The server port to use. Note that the server will run on port 25565 if this isn't specified. It will NOT use the port specified in server.properties, this is completely ignored.
  - `description` (str): Human readable description for what the server is for.
  - `auto-update` (bool): For 'release' or 'snapshot' versions, will automatically check for updates and apply them to the server when the server is booted up. **`Note`**: This setting is not checked by `pycraft.py` but only by the `pycraft_updater.py`. You may run the updater directly before the server each time to make use of this feature effectively.
  - `auto-restart` (bool): *`Not yet implemented`*; If the server should automatically restart when it crashes (not when it gracefully closes)
  - `read-only` (bool): *`Not yet implemented`*; If the map loaded should be saved to. If this is turned on, the server will make a temporary copy of the world that is selected. `<WORLDNAME_pycraft_copy>` (overriding the previous one). This is useful when you want to run minigames or custom maps that need to be in pristine condition when you first start it. The server will not reset the map when it closed due to a crash, this to preserve the state. You can also just save the copy under a different name to keep progress, but then why are you using read-only anyways?
  - `initialize` (list\<str\>): A list of commands ran at server startup. Commands that start with a `/` are server commands such as `/say`, `/give`, etc. Other commands are module commands such as `modules list` (to list all active modules) (for example setting automatic shutdown and backups, or to send a nice log message, or other stuff)
  - `__comment_<anything>`: Comments, useful for reading configurations as a human, but it doesn't really do anything for us computers.

### Running a PyCraft server ###

#### PyCraft command line ####
You can start the PyCraft server from the command line using:
```bat
python pycraft.py [YourServerName]
```
If you want you can simply put the line above in a windows batch file (server.bat) and run it by right clicking. (For linux/mac you can use a .sh file)

### Using built-in commands ###
The difference between this section and the next (modules), is that these commands are hardcoded, because they tie in with the core functionality and should not be accidentally removed from the 'modules' folder for example.

#### help ####
Use this command to view help of all available commands and modules.

- `help`: To get an overview of all commands
- `help <MODULE> [subcommands]`: Show the help of MODULE, with optional 'subcommands' for more detailed info.

#### stop | quit | exit ####
You can use any of those 3 commands to gracefully stop the server.

*This command takes no arguments.*

#### modules ####
Use this command to manage modules.

- `modules list`: List all active modules.
- `modules reload`: Reload all modules (any found in 'modules' folder will be available for usage)

<a name="modules">

## 3. Built-in Modules ##
</a>

The built-in modules are not strictly required, but are vital that they are included with every shipment of PyCraft.

### auto-shutdown | as ###
This command can be used to manage automatic shutdown of the server.
**It will also shut down the computer if HARD is specified.**

- `as`: Shows the usage of this command.
- `as idle <TIME> [HARD]`: Schedules a shutdown when no players are online.
- `as schedule <TIME> [HARD`: Schedules a shutdown right now. (reminds players 1m and 10s before shutdown)
- `as cancel`: Cancels any schedule or idle timers.

Example: `as idle 10m HARD` Will shutdown the server AND computer after nobody has been online for 10 minutes. The 10m timer is reset when a player joins. This can also be canceled completely using `as cancel`.

The shutdown thread will query the server for the amount of players online, for short schedules, there's at least 10 seconds between each request to the server, for longer schedules, there's up to 120 seconds between each request, to reduce overloading the server. This means that after a player has left, it may take up to 120 seconds longer for the script to detect the player count on the server. A 30 minute idle schedule can therefore take up to 32 minutes. However a 60 seconds idle timer may take up to 70 seconds, depending on the polling time. For your interest:

``` python
poll_delay = max(10, min(t // 10, 120))
```

### backup ###
This command handles backups. There are 2 types of backups, manual backups and automatic backups. They are stored separately.

Manual backups are stored under `<SERVER FOLDER>/backups`.  
Automatic backups are stored under `<SERVER FOLDER>/backups/auto`.

- `backup now [END]`: Creates a manual backup right now. (Specify `END` to close the server after the backup finishes)
- `backup schedule <TIME> [AMOUNT]`: Schedules a backup in TIME up to AMOUNT auto backups in total, after which the oldest is deleted.
- `backup off`: Turns off automatic backups.

The name of the resulting zipfile backup will be: `<universe>_<world>_<date>_<time>.zip`  
Automatic backups will have the name: `<universe>_<world>_<date>_<time>_apcbkp.zip`

**Note that making a backup could take a while and during a backup, auto-saving is turned off. The absolute bare minimum backup-time is therefore 2 minutes, 30 minutes or more is advised. However, using 7z combined with fast-backups, backing up may be faster.** <!--Currently, the zipping is not smart and will include all files, not just the new/changed/deleted files. However using 7z quick times like 15s for 2 to 3 GB can be achieved easily-->

**Also note that a backup takes quite some space, especially for large worlds. Therefore it is recommended to keep the total amount of automatic backups around 4 max. You can make as many manual backups as you'd like of course.**

*The server will NOT automatically back up any worlds when the version is updated.* <!--Make sure to make a backup before updating to a newer version automatically.-->

#### 7z assisted backups ####
Some configuration options exist to increase the efficiency of backups using a third party tool: 7-Zip. (Not affiliated)

* `7z-path`
  * The path to your 7z command line executable. (or simply leave it out if 7z is on your path)

* `prefer-7z`
  * Tries to use 7z over the standard backup method (if it can succesfully locate the executable).

* `fast-backup`
  * Requires 7z utilization. If a previous backup file can be found in the backups directory, it will be used as a basis for the new backup. This can speed up backups significantly for large worlds with only few modifications. (Basically skips: any regions that you haven't loaded/unmodified files)

An example setup in the config.json:

```json
"module-data": {
  "module_backup": {
    "prefer-7z": true,
    "fast-backup": true,
    "7z-path": "C:\\Program Files\\7-Zip\\bin\\7z.exe"
  }
}
```

### status ###
A simple wrapper for mcstatus. Displays some useful server information such as: ping, version, description, players and query. (if query is enabled)

### notify ###
A simple tool to make the console window go *BEEP* whenever certain criteria are met, such as: someone entering the server, someone leaving the server, specific chat messages, etc.

<a name="advanced">

## 4. Advanced Usage ##
</a>

### Creating your own modules ###
To start creating your own module, create a new file `<nameHere>.py` under `modules`. Then edit it with the editor of your likings. You will need to know a little bit of python and at least the bare bones (boilerplate) code given below to start.

#### Bare bones ####

For starters I recommend checking the other modules and figure out how they work first. This will give you an insight for writing your own.

The boilerplate (required structure of a module) is as follows:

``` python
from pycraft_module import PCMod

description = "Place a human friendly description here."
patterns = ['custom-command']

def get_module():
    return module

def usage(subcmd=[]):
    return "Replace this with your help message."

# Not strictly necessary, but generally a stylish way to print commands.
# Don't use raw print statements!
def pyprint(string, loglevel=1):
    get_module().pyprint(string, loglevel)

def callback(cmd, server_config, run_cmd, event_triggers):
    '''
    cmd: The remaining subcommands after the matched pattern.
    server_config: The server config specific to this server, including port, name, etc.
    run_cmd: Allows writing commands to the server such as say, stop, etc. (Without preceding '/'!)
    event_triggers: Dict of events that can be triggered (see pycraft_server for a list of them).
    '''

    ### Write your module code here.
    pass

module = PCMod(__name__, description, patterns, callback, usage)

```


The boiler plate code can be even more concise when you remove all the comments, of course.

Most of the time you may also want to use

``` python
import pycraft_utils as pu
```
This includes easy argument parsing and various neat utilities.

#### Running server commands ####

You can run commands on the server by simply calling `run_cmd(<YOUR COMMAND HERE>)`
You can run any server command, but be careful with them, things like `fill`, `kill` can do major damage to the server when used wrongly.

If you want to log something, don't use say. This will print to all players. You can just use pyprint(msg), this will only log to the pycraft server, but that's the best we can do. Or you'd need to do some fancy trickery.

#### Server Config ####

The server specific config file is passed as a dictionary. You can edit it, but it's recommended you don't, as other modules might depend on it. You can read/write custom key-value pairs to it, but the changes will only be local, as a server restart will reset them. <!--This might change in the future-->

#### Events ####

Some things can't be queried using namemc/mcstatus. I provided as best as I could, an interface between server chat and events for the major things.

`event_triggers` is passed as a dict, with keys as event names.
e.g. `{'done': event_trigger}`

The keys for events include:

- `done`: Triggers when the server is done loading and is ready to receive commands.
- `save`: Triggers when the server is saved using save-all.
- `stop`: Triggers when the server is stopped. (for shutdown hooks only, spawn a thread waiting for this event.)
- `join`: Triggers when a player joins the server.
- `leave`: Triggers when a player leaves the server.
- `chat`: Triggers on any chat message (starting with \<NAME\>)
- `server-chat`: Triggers on any chat message sent by the SERVER ONLY. (or a player named Server, be careful, don't give them '/say' access)
- `emote`: Triggers on all emotes (lines starting with *).
- `any`: Triggers on anything, useful for partially regexxing.

`event_trigger.data` will contain the raw chat message that triggered this event.
You can only use event_trigger.data somewhat reliably just after the `event_trigger.event.wait()` call.

#### Module Data ####
You may include special config keys to be used in config.json. By default, the `server_config` will pass these config values to all active modules.

It should be used as stated before:

> `module-data`: Dict of any custom configuration settings used by modules. The convention is to use `module_<module_name>` for the key to properly namespace settings. `shared` could be used for any config settings shared between modules.

An example of some module data can be seen below:

```json
"module-data": {
  "module_foo": {
    "key": "value",
    "bar": true,
    "baz": 123
  }
}
```

You can then access these values through `server_config["module_foo"]["key"]`, `server_config["module_foo"]["bar"]`, etc.

Make sure to validate this data and types yourself.