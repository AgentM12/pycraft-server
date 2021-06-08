
import requests
import json
import sys
import os
import shutil
import zipfile

version_url = "https://launchermeta.mojang.com/mc/game/version_manifest.json"
config_file = 'config.json'
temp_download_folder = "__TEMP_UPDATE_JARS_b590aOih9"
servers_folder = "servers"

def get_latest():
	with requests.get(version_url) as f:
		data = json.loads(f.text)
	latest_release = data['latest']['release']
	latest_snapshot = data['latest']['snapshot']
	
	snapshot_url = None
	release_url = None
	for version in data['versions']:
		if version['id'] == latest_snapshot:
			snapshot_url = version['url']
		if version['id'] == latest_release:
			release_url = version['url']
			if not snapshot_url:
				snapshot_url = version['url']
			break # If we find the latest release before the snapshot, then it's also the latest 'snapshot'
	return latest_release, latest_snapshot, release_url, snapshot_url

def server_version_info(server_jar):
	try:
		with zipfile.ZipFile(server_jar) as z:
			with z.open("version.json") as f:
				return json.load(f)['id']
	except:
		return "OLD" # version.json doesn't exist

def read_config():
	try:
		with open(config_file, 'r') as f:
			return json.load(f)
	except json.decoder.JSONDecodeError as e:
		print(f"[PyCraftUpdater/INFO] Error in Config file: {str(e)}")
		sys.exit(1)

def download_url(url, save_path, chunk_size=1024):
    r = requests.get(url, stream=True)
    with open(save_path, 'wb') as fd:
        for chunk in r.iter_content(chunk_size=chunk_size):
            fd.write(chunk)

def get_jar_url_from_json(json_file):
	with open(json_file, 'r') as f:
		data = json.load(f)
	return data['downloads']['server']['url']

def check_for_updates(config, latest_release, latest_snapshot):
	release_servers = []
	snapshot_servers = []
	for server in config['server-list']:
		if server['auto-update']:
			if server['version'] == "release":
				existing_jar = os.path.join(os.path.join(servers_folder, server['name']), "server.jar")
				if os.path.isfile(existing_jar):
					if server_version_info(existing_jar) == latest_release:
						continue
				release_servers.append(server['name'])
			elif server['version'] == "snapshot":
				existing_jar = os.path.join(os.path.join(servers_folder, server['name']), "server.jar")
				if os.path.isfile(existing_jar):
					if server_version_info(existing_jar) == latest_snapshot:
						continue
				snapshot_servers.append(server['name'])
	return release_servers, snapshot_servers

def update(latest_release, latest_snapshot, release_servers, snapshot_servers, release_url, snapshot_url):
	if snapshot_servers or release_servers:
		if snapshot_servers:
			print(f"[PyCraftUpdater/INFO] Downloading latest snapshot {latest_snapshot}...")
			temp_snapshot_dir = os.path.join(temp_download_folder, "snapshot")
			temp_snapshot_jar = os.path.join(temp_snapshot_dir, "server.jar")
			temp_snapshot_json = os.path.join(temp_snapshot_dir, "server.json")
			os.makedirs(temp_snapshot_dir, exist_ok=True)
			download_url(snapshot_url, temp_snapshot_json)
			snapshot_jar_url = get_jar_url_from_json(temp_snapshot_json)
			download_url(snapshot_jar_url, temp_snapshot_jar)
			for server in snapshot_servers:
				print(f"[PyCraftUpdater/INFO] Updating {server}...")
				path = os.path.join(os.path.join(servers_folder, server), "server.jar")
				shutil.copy(temp_snapshot_jar, path)

		if release_servers:
			print(f"[PyCraftUpdater/INFO] Downloading latest release {latest_release}...")
			temp_release_dir = os.path.join(temp_download_folder, "release")
			temp_release_jar = os.path.join(temp_release_dir, "server.jar")
			temp_release_json = os.path.join(temp_release_dir, "server.json")
			os.makedirs(temp_release_dir, exist_ok=True)
			download_url(release_url, temp_release_json)
			release_jar_url = get_jar_url_from_json(temp_release_json)
			download_url(release_jar_url, temp_release_jar)
			for server in release_servers:
				print(f"[PyCraftUpdater/INFO] Updating {server}...")
				path = os.path.join(os.path.join(servers_folder, server), "server.jar")
				shutil.copy(temp_release_jar, path)

		shutil.rmtree(temp_download_folder)

		print("[PyCraftUpdater/INFO] All auto-update servers have been updated succesfully!")
	else:
		print("[PyCraftUpdater/INFO] All auto-update servers are already up to date!")

def main():
	print("[PyCraftUpdater/INFO] Reading config...")
	config = read_config()
	
	print("[PyCraftUpdater/INFO] Obtaining latest versions...")
	latest_release, latest_snapshot, release_url, snapshot_url = get_latest()

	print("[PyCraftUpdater/INFO] Checking for updates...")
	release_servers, snapshot_servers = check_for_updates(config, latest_release, latest_snapshot)
	
	update(latest_release, latest_snapshot, release_servers, snapshot_servers, release_url, snapshot_url)


if __name__ == '__main__':
	main()