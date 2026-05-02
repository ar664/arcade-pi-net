import streamlit as st
import subprocess, re, shlex, pathlib
import os, socket, urllib.request
import json, xml.etree.ElementTree as ET



comment1 = """
MAC Address Range for RPI's
B8:27:EB:**:**:**
DC:A6:32:**:**:**
E4:5F:01:**:**:**
"""

rom_directory = pathlib.Path.home().joinpath('RetroPie/roms/')

st.title("Arcade Pi Network Management")

def get_arp_devices():
    # Runs 'arp -a' command
    result = subprocess.check_output(['arp', '-a']).decode('utf-8')
    # Regex to find IP and MAC addresses in the output
    devices = re.findall(r'(\d+\.\d+\.\d+\.\d+)\s+([0-9a-fA-F:-]+)', result)
    return devices

def get_pis():
    pi_macs = [
        'b8-27-eb',
        'dc-a6-32',
        'e4-5f-01'
    ]
    pattern = re.compile('(' + '|'.join(pi_macs) + ')')
    devices = get_arp_devices()
    pis = list(filter(lambda x: pattern.search(x[1]), devices))
    pi_hosts = []
    for x in pis:
        try:
            hostname, alias, address = socket.gethostbyaddr(x[0])
            pi_hosts.append((hostname, alias, address))
        except:
            pi_hosts.append(x[0])
            continue
    return pi_hosts

def run_skyscraper(console):
    #ssCommand = '/opt/retropie/supplementary/skyscraper/Skyscraper'
    ssCommand = pathlib.Path.home().joinpath('Skyscraper/Skyscraper.exe')
    if not os.path.exists(ssCommand):
            print('skyScraper not found in: ' + ssCommand)
            return

    # Example command:
    # /opt/retropie/supplementary/skyscraper/Skyscraper -p psx 
    # -g /opt/retropie/configs/all/emulationstation/gamelists/psx 
    # -o /opt/retropie/configs/all/emulationstation/downloaded_media/psx 

    gamelists_path = pathlib.Path.home().joinpath('.emulationstation/gamelists/')
    dlmedia_path = pathlib.Path.home().joinpath('.emulationstation/downloaded_media/')
    options = ' --flags onlymissing,unattend,skipped'

    command:str = '' + str(ssCommand) + ' -s screenscraper -p ' + console + ' -g ' + str(gamelists_path.joinpath(console)) + ' -o ' + str(dlmedia_path.joinpath(console)) + options
    command = command.replace('\\', "\\\\")
    print(command)

    return subprocess.run(shlex.split(command),shell=True)

#Scrape all consoles, while updating the gamelist.xml
def all_skyscraper(consoles):
    ret_list = []
    for console in consoles:
        ret_list.append(run_skyscraper(console))

@st.cache_data
def get_roms():
    roms = []
    romDirs = []
    consoles = []
    extensions = []

    consoles = os.listdir(pathlib.Path.home().joinpath('.emulationstation/gamelists/'))
    extensions = ['.null']*len(consoles)
    consoles.remove('retropie')
    #print(consoles)
#/etc/emulationstation/es_systems.cfg
    extensionTree = ET.parse('./es_systems.cfg')
    if(extensionTree is not None):
        root = extensionTree.getroot()
        for system in root.iter('system'):
            name = system.find('name').text
            if(name in consoles):
                index = consoles.index(name)
                extensions[index] = system.find('extension').text.split(' ')

    for i, console in enumerate(consoles):
        #romDirs.append(rom_directory.joinpath(console).as_uri)

        romTree = ET.parse(pathlib.Path.home().joinpath('.emulationstation/gamelists/' + consoles[i] + '/gamelist.xml'))
        if(romTree is not None):
            #print('romTree found:', pathlib.Path.home().joinpath('.emulationstation/gamelists/' + consoles[i] + '/gamelist.xml'))
            root = romTree.getroot()
            for game in root.iter('game'):
                roms.append({'console': console,
                                'name': game.find('name').text, 
                                'genre': game.find('genre').text, 
                                'players': game.find('players').text})
    return consoles, roms


consoles, roms = get_roms()
pis = get_pis()

if len(consoles) > 0:
    expander = st.expander("Console|Rom List")
    with expander:
        tabs = st.tabs(consoles)
        for i, console in enumerate(consoles):
            with tabs[i]:
                rom_table = [rom for rom in roms if rom['console'] == console]
                st.dataframe(rom_table, height=400)


pi_col, rom_col = st.tabs(["Communicate", "File Management"])

with pi_col:
    st.header("Game Setter")

    pi_selection = st.pills("Select Pis", pis, selection_mode="multi")

    console_selection =  st.selectbox("Select Console", consoles)
    if console_selection:
        rom_selection = st.selectbox("Select Rom", [rom['name'] for rom in roms if rom['console'] == console_selection])
        if rom_selection and len(pi_selection) > 0:
            if st.button("Press to play on Pi(s)"):
                print(console_selection + ' ' + rom_selection)
                
                headers = {"Content-Type": "application/json"}
                data = {'rom': rom_selection, "console": console_selection}
                responses = []
                for i, pi in enumerate(pi_selection):
                    url = 'http://' + pi + ':5001/games'
                    #print(url)
                    encoded_data = json.dumps(data).encode("utf-8")
                    req = urllib.request.Request(url, data=encoded_data, headers=headers, method='POST')
                    try:
                        resp = urllib.request.urlopen(req).read()
                        body = json.loads(resp.decode("utf-8"))
                        print(body)
                        if(body['result']):
                            responses.append({'ip':pi, 'result': body['result']})
                        else:
                            responses.append({'ip':pi, 'result': 'unknown'})
                    except Exception as error:
                        responses.append({'ip':pi, 'result': error})
                        print(error)
                        continue
                st.table(responses)
with rom_col:
    st.header("Rom Uploader")

    up_console =  st.selectbox("Select Console:", consoles, accept_new_options=True)
    up_roms = st.file_uploader("Upload Rom(s)", accept_multiple_files=True)
    if up_roms is not None and len(up_console) > 0 and st.button("Process Rom"):
        if not rom_directory.joinpath(up_console).exists():
            st.error(f"Rom directory {up_console} not found")
        else:
            for up_rom in up_roms:
                file_name = up_rom.name
                
                # Define the full path to save the file
                rom_path = rom_directory.joinpath(up_console + '/' + file_name)
                
                # Write the file to disk
                with open(rom_path, "wb") as f:
                    f.write(up_rom.getbuffer())
                
                st.success(f"Saved file: {file_name} to {rom_path}")
    if len(up_console) > 0 and st.button("Generate Metadata (Current Console, Recommended)"):
        proc = run_skyscraper(up_console)
        if proc.returncode == 0:
            st.success(f"Skyscraper ran successfully for {up_console}")
        else:
            st.error(str(proc))
    if st.button("Generate Metadata (All Consoles)"):
        st.table(all_skyscraper(consoles))
