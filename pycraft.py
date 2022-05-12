### pycraft_server.py
## Script provided as-is by AgentM
## Handles a minecraft server.
import pycraft_utils as pu

import pycraft_module
import subprocess
import importlib
import argparse
import glob
import json
import time
import sys
import zipfile
import os
import re

from mcstatus import MinecraftServer
from jprops import Properties
from threading import Thread
from threading import Event
from threading import Lock
from threading import Condition
from queue import Queue
from os import path

# Make sure our working directory is the location of the pycraft_server.py file.
cur_dir = path.dirname(__file__)
if len(cur_dir.strip()) > 0:
	os.chdir(cur_dir)

DEBUG = False
if DEBUG:
	pycraft_module.log_flag |= 0b1111

#GLOBALS
# Version history: 1.0 is unsafe due to log4j error. Use 1.1+
pycraft_server_version = '1.1'

config_file = 'config.json'
servers_location = 'servers'
backups_location = 'backups'
modules_location = 'modules'
resources_location = 'resources'
sys.path.insert(1, modules_location) # Tell python to look in the modules folder when relaoding imports.

server_config = None
server_properties = None
queue_lock = Lock()
read_flag = False
running = False
command_providers = []
raw_imports = []
read_condition = Condition()

base_pattern = '(^\\[\\d{1,2}:\\d{1,2}:\\d{1,2}\\] \\[[a-zA-Z\\s]*?(?:|#\\d+)\\/[A-Z].*?\\]:) (%s)'
name_pattern = '[a-zA-Z0-9_]+?' # Use this when you don't use pre-/suffixes (safer)
ps_name_pattern = '[^<*].*' # Can be anything because of pre-/suffixes BUT disallows < and > usage. (more lenient, less safe)

signature_done = re.compile(base_pattern % 'Done \\([0-9.]+s\\)! For help, type "help"')
signature_save = re.compile(base_pattern % 'Saved the game')
signature_stop = re.compile(base_pattern % 'Stopping server')
signature_join = re.compile(base_pattern % ('UUID of player %s is [0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$' % name_pattern))
signature_leave = re.compile(base_pattern % ('%s lost connection: .*$' % name_pattern))
signature_chat = re.compile(base_pattern % '<.*?> .*')
signature_server_chat = re.compile(base_pattern % '[Server] .*') # Not safe. May also trigger on entities or commandblocks named 'Server' performing the /say command.
signature_emote = re.compile(base_pattern % '\\* .*')
signature_any = re.compile(base_pattern % '.*')

class EventTrigger:
	def __init__(self, signature):
		self.event = Event()
		self.signature = signature
		self.data = None
		self.match = None

event_triggers = {
	'done': EventTrigger(signature_done), # Triggers when the server is done loading and is ready to receive commands.
	'save': EventTrigger(signature_save), # Triggers when the server is saved using save-all.
	'stop': EventTrigger(signature_stop), # Triggers when the server is stopped. (for shutdown hooks only, spawn a thread waiting for this event.)
	'join': EventTrigger(signature_join), # Triggers when a player joins the server.
	'leave': EventTrigger(signature_leave), # Triggers when a player leaves the server.
	'chat': EventTrigger(signature_chat), # Triggers on any chat message (starting with <NAME>)
	'server-chat': EventTrigger(signature_server_chat), # Triggers on any chat message sent by the SERVER ONLY. (or a player named Server, be careful, don't give them '/say' access)
	'emote': EventTrigger(signature_emote), # Triggers on all emotes (lines starting with *).
	'any': EventTrigger(signature_any), # Triggers on anything, useful for partially regexxing.
}

safety = ""
severities = ['DEBUG', 'INFO', 'WARN', 'ERROR']
def pyprint(string, loglevel=1):
	print(f"[{safety}PyCraft/%s] %s" % (severities[loglevel], string))

def arguments():
	parser = argparse.ArgumentParser(description="Run a minecraft server with backups, shut-down hooks and possibly scripts.", epilog="Priority Order: Arguments, config.json, server.properties, DEFAULT")

	# Required
	parser.add_argument(dest="server_name", help="Starts the server with the specified name, matching case. If not specified, an interactive console allows you to select one.", nargs='?', default=None)
	
	# Optional
	parser.add_argument("-j", "--jvm-args", default=[], nargs="+", dest="jvm_arguments", help="Run the server with more RAM or other jvm arguments (don't include the leading dashes).")
	parser.add_argument("-u", "--universe", default=None, dest="universe", help='Select a folder as the save location of world folders for the server. (see Priority Order)')
	parser.add_argument("-w", "--world", default=None, dest="world", help="Select a folder as the world folder to load for the server. (see Priority Order)")
	return parser.parse_args()

def read_config():
	try:
		with open(config_file, 'r') as f:
			return json.load(f)
	except json.decoder.JSONDecodeError as e:
		pyprint("Error in Config file: %s" % str(e), 3)
		sys.exit(1)

def find_server_config(server_name, dict_list):
	for d in dict_list:
		if d['name'] == server_name:
			return d
	raise Exception('[Config] Configuration for %s was not found!' % server_name)

def get_server_properties(server_jar_location):
	p = Properties()
	with open(path.join(server_jar_location, 'server.properties'), 'r') as f:
		p.load(f)
	return p

def server_args(universe, world, nogui, forceupgrade, port):
	args = []
	if nogui: args.append('--nogui')
	if forceupgrade: args.append('--forceUpgrade')
	if universe != '.': args.extend(['--universe', universe])
	args.extend(['--world', world])
	args.extend(['--port', str(port)])
	return args

def try_get(priority_order, none_values=[None], default=None):
	'''
	Tries to return the value from first element to last element if it isn't a none_value, if the last case fails returns default.
	'''
	for p in priority_order:
		if not p in none_values:
			return p
	return default

def expect_type(name, key, ty):
	if not isinstance(key, ty):
		raise Exception(f"[Config] Type of {name} must be {ty}, but was: {key} ({type(key)})")

def configure(key, value):
	'''
	Ensures key-value is in the server config, then returns the value.
	'''
	global server_config
	server_config[key] = value
	return value

# WARNING. THIS PATCH ONLY WORKS ON VANILLA JARS
def log4j_patch(server_version, server_jar_location, jvm_arguments):
	global safety

	if (safety == "INSECURE-"):
		print("PROCEEDING LAUNCH (INSECURE)!")
		return
	for arg in jvm_arguments:
		if (arg.startswith("-Dlog4j2.formatMsgNoLookups") or arg.startswith("-Dlog4j.configurationFile")):
			import random
			pyprint("JVM arguments for Log4J should not be included within config.json:", 2)
			print("  A patch for the log4J [CVE-2021-44228] vulnerability will automatically be applied for any VANILLA version.")
			print("  For any version before 18w47b, the default mitigation chosen is to strip any malicious messages from logs.")
			print("  If you decide to override these choices (for example for versions prior to 1.7 or modded),")
			print("  you may still continue at the risk of your system being compromised by an outside attacker.")
			print('')
			print("  Are you sure you know what you're doing?")
			security_question = f"YES I ACKNOWLEDGE {random.randint(1000, 9999)}"
			print(f"  (To proceed, write this exact string without the quotes: '{security_question}')")
			print('')
			ans = input("  Proceed? > ")
			if (ans != security_question):
				raise Exception("Server launch has been aborted due to security violation.")
			print("PROCEEDING LAUNCH (INSECURE)!")
			safety = "INSECURE-"
			return

	# Snapshots will run according to this unless they are 22w+
	log4j_jvm_patch_flags = "-Dlog4j.configurationFile=log4j2_17-111.xml"
	patch_method = 2
	vulnerable = True
	safety = ""

	full_release_pattern = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[_-].*)?$")
	m = full_release_pattern.match(server_version['id'])
	l = 0 if not m else len(m.groups())
	if (m and l > 2):
		major = int(m.group(1))
		minor = int(m.group(2))
		patch = int(m.group(2)) if (l > 3) else 0
		if (major != 1):
			pass
		elif ((minor == 18 and patch > 0) or (minor > 18)):
			vulnerable = False
		elif (minor == 17 or (minor == 18 and patch < 1)):
			log4j_jvm_patch_flags = "-Dlog4j2.formatMsgNoLookups=true"
			patch_method = 0
		elif (minor >= 12 and minor <= 16):
			log4j_jvm_patch_flags = "-Dlog4j.configurationFile=log4j2_112-116.xml"
			patch_method = 1
		elif (minor >= 7 and minor <= 11):
			log4j_jvm_patch_flags = "-Dlog4j.configurationFile=log4j2_17-111.xml"
			patch_method = 2
		else:
			pass
	else:
		snapshot_pattern = re.compile(r"^(\d+)(?:\.(\d+))?(?:\.(\d+))?(?:[_-].*)?$")
		m = snapshot_pattern.match(server_version['id'])
		if (m):
			year = int(m.group(1))
			week = int(m.group(2))
			patch = m.group(3)
			if (year >= 22):
				vulnerable = False
			elif (year == 21 and week >= 37):
				log4j_jvm_patch_flags = "-Dlog4j2.formatMsgNoLookups=true"
				patch_method = 0
			elif (year >= 17 and week >= 31):
				log4j_jvm_patch_flags = "-Dlog4j.configurationFile=log4j2_112-116.xml"
				patch_method = 1
			elif (year >= 13 and week >= 47):
				log4j_jvm_patch_flags = "-Dlog4j.configurationFile=log4j2_17-111.xml"
				patch_method = 2
			else:
				pass

	if (vulnerable):
		jvm_arguments.append(log4j_jvm_patch_flags)
		
		if (patch_method > 0):
			if (patch_method == 2):
				url = "https://launcher.mojang.com/v1/objects/dd2b723346a8dcd48e7f4d245f6bf09e98db9696/log4j2_17-111.xml"
				xml_path = "log4j2_17-111.xml"
			else:
				url = "https://launcher.mojang.com/v1/objects/02937d122c86ce73319ef9975b58896fc1b491d1/log4j2_112-116.xml"
				xml_path = "log4j2_112-116.xml"
			xml_destination = os.path.join(server_jar_location, xml_path)
			cache_path = os.path.join(resources_location, xml_path)
			if not path.isfile(xml_destination):
				import shutil
				if not path.isfile(cache_path):
					import requests
					pyprint("Downloading log4j patch from mojang servers...")
					chunk_size=1024
					r = requests.get(url, stream=True)
					os.makedirs(resources_location, exist_ok=True)
					with open(cache_path, 'wb') as fd:
						for chunk in r.iter_content(chunk_size=chunk_size):
							fd.write(chunk)
				pyprint("Patching log4j...")
				shutil.copy(cache_path, xml_destination)


def obtain_launch_code(config, args):
	global server_config, server_properties, server_jar, server_version

	server_name = args.server_name
	server_config = find_server_config(server_name, config['server-list'])
	server_jar_location = path.join(servers_location, server_name)
	server_jar = path.join(server_jar_location, 'server.jar')
	if not path.exists(server_jar):
		raise Exception(f"[Config] Could not find the server located at: {server_jar}")

	with zipfile.ZipFile(server_jar) as z:
		try:
			with z.open("version.json") as f:
				server_version = json.load(f)
		except:
			server_version = {
				"id": "Unknown",
				"name": "Unknown",
				"java_component": "jre-legacy"
			}
	if not 'java_component' in server_version:
		server_version['java_component'] = "jre-legacy"

	java_component = server_version['java_component']
	default_java_path = f"C:\\Program Files (x86)\\Minecraft Launcher\\runtime\\{java_component}\\windows-x64\\{java_component}\\bin\\java.exe"
	if not (os.path.exists(default_java_path)):
		default_java_path = f"C:\\Program Files (x86)\\Minecraft\\runtime\\{java_component}\\windows-x64\\{java_component}\\bin\\java.exe"
	if not (os.path.exists(default_java_path)):
		raise Exception(f"The default java path could not be found.\nPlease specify a path to a valid java binary.")

	java_executable = try_get([config.get('java-executable')], none_values=[None, ""], default=default_java_path)
	expect_type('java-executable', java_executable, str)

	jvm_arguments = try_get([["-" + a for a in args.jvm_arguments], config.get('jvm-args')], none_values=[None, []], default=[])
	expect_type('jvm-args', jvm_arguments, list)

	# Log4j security patch
	log4j_patch(server_version, server_jar_location, jvm_arguments)
	#raise Exception("MANUAL END")

	server_properties = get_server_properties(server_jar_location)

	# Configure
	universe = configure('universe', try_get([args.universe, server_config.get('universe')], default='worlds'))
	expect_type('universe', universe, str)
	world = configure('world', try_get([args.world, server_config.get('world'), server_properties.get('level-name')], default='world'))
	expect_type('world', world, str)
	nogui = config.get('hide-gui', True)
	expect_type('hide-gui', nogui, bool)
	forceupgrade = config.get('upgrade-all-chunks-on-version-mismatch', False)
	expect_type('upgrade-all-chunks-on-version-mismatch', forceupgrade, bool)
	port = configure('port', try_get([server_config.get('port'), int(server_properties.get('server-port'))], default=25565))
	expect_type('port', port, int)
	qport = configure('query-port', try_get([int(server_properties.get('query.port'))], default=25565))
	expect_type('query-port', qport, int)
	module_data = config.get('module-data', {})
	expect_type('module-data', module_data, dict)

	# Give modules access to their module data.
	server_config['module-data'] = module_data

	# Convenience locations (stored in RAM only)
	configure('server-root', server_jar_location)
	configure('world-root', path.join(path.join(server_jar_location, universe), world))

	server_argument_list = server_args(universe, world, nogui, forceupgrade, port)
	return [java_executable] + jvm_arguments + ['-jar', 'server.jar'] + server_argument_list

def launch_server(name, launch_code):
	wd = os.getcwd()
	os.chdir('%s/%s' % (servers_location, name))
	p = subprocess.Popen(launch_code, stdout=subprocess.PIPE, stdin=subprocess.PIPE, encoding='utf-8', bufsize=1, universal_newlines=True)
	os.chdir(wd)
	return p

def add_input(input_queue):
	global read_flag
	buff = []
	while running:
		c = sys.stdin.read(1)
		buff.append(c)
		if c == '\n':
			queue_lock.acquire()
			for i in buff:
				input_queue.put(i)
			buff = []
			read_flag = True
			queue_lock.release()
			with read_condition:
				read_condition.notify()

def list_modules():
	return ', '.join([cp.name for cp in command_providers])

def import_tool():
	global command_providers, raw_imports

	for cp in command_providers:
		cp.close() # Kill any threads first.

	importlib.invalidate_caches()
	modules = glob.glob(path.join(modules_location, "*.py"))
	imports = [path.basename(f)[:-3] for f in modules if path.isfile(f) and not f.endswith('__init__.py')]

	def import_or_reload(mod):
		for ri in raw_imports:
			if ri.__name__ == mod:
				return importlib.reload(ri)
		return importlib.import_module(mod)

	raw_imports = [import_or_reload(i) for i in imports]
	command_providers = [i.get_module() for i in raw_imports]
	pyprint('Succesfully (re)loaded modules: %s' % list_modules())

def show_help():
	print('')
	pyprint('Minecraft Commands should start with a "/" (e.g. /say, /help)')
	print('\n----- Built-in Commands -----')
	print(' - help [MODULE]: Show this help, or the help page of a MODULE.')
	print(' - modules <list|reload>: List pycraft modules or reload them.')
	print(' - stop|quit|exit: Stops the server and PyCraft (identical to /stop)')
	print('\n--- PyCraft Module Commands ---')
	if len(command_providers) == 0:
		print(f' No PyCraft Server Modules were found in {modules_location}')
	for cp in command_providers:
		print(' - %s: %s' % (', '.join(cp.patterns), cp.description))

def handle_events(message):
	for k in event_triggers:
		et = event_triggers[k]
		m = et.signature.match(message)
		if m:
			et.data = message
			et.match = m
			et.event.set()
			et.event.clear()

def perform_command(cmd, stdin):
	global running
	cmd_parts = cmd.split()
	key, sub = pu.next_cmd(cmd_parts)

	# Built-in
	if (key == 'exit' or key == 'quit' or key == 'stop'):
		if len(sub) > 0:
			key2, sub2 = pu.next_cmd(sub)
			if pu.max_cmd_len(sub2, 0, pyprint): return
			if (key2 == 'FORCE'):
				try:
					stdin.write('/stop\n')
				except:
					pass
				running = False
		else:
			try:
				stdin.write('/stop\n')
			except:
				pass
		return
	if (key == 'help'):
		if len(sub) > 0:
			key2, sub2 = pu.next_cmd(sub)
			for cp in command_providers:
				if cp.matches(key2):
					cp.help(sub2)
					return
			pyprint('Unknown module/command: %s' % key2, 3)
		else:
			show_help()
		return
	if (key == 'modules'):
		key2, sub2 = pu.next_cmd(sub)
		if pu.max_cmd_len(sub2, 0, pyprint): return
		if (key2 == 'reload'): import_tool()
		elif (key2 == 'list'): pyprint('Active modules: %s' % list_modules())
		return
	# Modules
	for cp in command_providers:
		if cp.matches(key):
			try:
				cp.execute(sub, server_config, stdin, event_triggers)
			except Exception as e:
				pyprint('%s: Performing command: %s' % (e, cmd), 3)
			return
	pyprint('Unknown command: %s' % cmd, 3)

def initial_commands(stdin):
	for cmd in server_config['initialize']:
		s = cmd.strip()
		if s.startswith('/'): stdin.write('%s\n' % s[1:])
		elif len(s) > 0: perform_command(s, stdin)

def ask_server_type(config):
	while True:
		choices = []
		print(" ====== Servers loaded from config.json ====== ")
		for i in range(len(config["server-list"])):
			sn = config["server-list"][i]['name']
			choices.append(sn)
			x = f"*{i}".rjust(3, ' ')
			print(f"{x}: {sn}")
		c = input("Select the server Name or *Index to start (*q/*quit/*exit to quit): ").strip()
		if c.startswith('*'):
			rest = c[1:]
			if rest == 'q' or rest == 'quit' or rest == 'exit':
				return None
			try:
				return choices[int(rest)]
			except ValueError:
				print(f"{rest} is not a valid index selection!")
		elif c in choices:
			return c
		else:
			try:
				int(c)
				print(f"{c} is not a valid option! (Did you mean to select the index: *{c})")
			except ValueError:
				print(f"{c} is not a valid option! (case-sensitive)")

def main():
	global running

	pyprint('Version: %s' % pycraft_server_version)
	if DEBUG: pyprint('DEBUG is enabled!')

	import_tool()
	config = read_config()
	args = arguments()

	if args.server_name is None:
		x = ask_server_type(config)
		if x is None:
			return
		args.server_name = x
	
	launch_code = obtain_launch_code(config, args)
	print(f"Version: {server_version['name']}")

	launch_str = ' '.join(launch_code)
	server_name = args.server_name
	pyprint(f'Launching "{server_name}"...')
	pyprint(f'With command "{launch_str}"', 0)
	process = launch_server(args.server_name, launch_code)
	
	running = True
	def print_callback(input_queue):
		nonlocal process
		global running, read_flag

		initial_commands(process.stdin)

		while running:
			with read_condition:
				read_condition.wait()
			if read_flag:
				queue_lock.acquire()
				s = ''
				while not input_queue.empty():
					s += input_queue.get()
				if s.startswith('/'): process.stdin.write(s[1:])
				elif len(s.strip()) > 0: perform_command(s.strip(), process.stdin)
				read_flag = False
				queue_lock.release()

	input_queue = Queue()
	input_thread = Thread(target=add_input, args=(input_queue,))
	input_thread.daemon = True
	input_thread.start()
	print_thread = Thread(target=print_callback, args=(input_queue,))
	print_thread.start()

	while (process.poll() == None):
		try:
			message = process.stdout.readline().rstrip('\r\n')
		except UnicodeDecodeError:
			message = "The message contains unknown unicode characters that can't be decoded with utf-8"
			#TODO fix this properly.

		if len(message.strip()) != 0:
			print(message)
			handle_events(message)
	
	running = False

	for cp in command_providers:
		cp.close() # Kill any threads first.
	
	with read_condition:
		read_condition.notify() # Remove the condition
	print_thread.join()
	pyprint('Server has terminated succesfully!')

if __name__ == '__main__': main()