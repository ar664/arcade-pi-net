import streamlit as st
import subprocess, re, shlex, pathlib
import os, platform, socket, urllib.request
import json, xml.etree.ElementTree as ET
import struct, ipaddress
if platform.system() == "Windows":
    import winfcntl
else:
    import fcntl

comment1 = """
MAC Address Range for RPI's
B8:27:EB:**:**:**
DC:A6:32:**:**:**
E4:5F:01:**:**:**
"""
endpoint_port = '5001'
rom_directory = pathlib.Path.home().joinpath('RetroPie/roms/')
paths_bool = False
options_bool = True

st.title("Arcade Pi Network Management")

def get_gateway_and_netmask():
    iface = gw = netmask = None
    with open("/proc/net/route") as f:
        for line in f.readlines()[1:]:
            fields = line.strip().split()
            iface, dest, gateway = fields[0], fields[1], fields[2]

            if dest == '00000000':  # default route
                gw = socket.inet_ntoa(struct.pack("<L", int(gateway, 16)))
    
    if iface:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        ifreq = struct.pack('256s', iface[:15].encode('utf-8'))
        res = fcntl.ioctl(s.fileno(), 0x891b, ifreq)  # SIOCGIFNETMASK
        netmask = socket.inet_ntoa(res[20:24])

    return gw, netmask

def nmap_discover():
    gw, nm  = get_gateway_and_netmask()
    network = ipaddress.IPv4Network(f"{gw}/{nm}", strict=False)
    subprocess.run(['nmap', '-sn', str(network)])

def get_arp_devices():
    # Runs 'arp -a' command
    result = subprocess.check_output(['arp', '-a']).decode('utf-8')
    # Regex to find IP and MAC addresses in the output
    devices = re.findall(r'(\d+\.\d+\.\d+\.\d+).+([0-9a-fA-F:-]{17,})', result)
    return devices

@st.cache_data
def get_pis():
    pi_macs = []
    if platform.system() == "Windows":
        pi_macs = [
            'b8-27-eb',
            'dc-a6-32',
            'e4-5f-01'
        ]
    else:
        pi_macs = [
            'b8:27:eb',
            'dc:a6:32',
            'e4:5f:01'
        ]
    pattern = re.compile('(' + '|'.join(pi_macs) + ')')
    devices = get_arp_devices()
    pis = list(filter(lambda x: pattern.search(x[1]), devices))
    pi_hosts = []
    for x in pis:
        try:
            hostname, alias, address = socket.gethostbyaddr(x[0])
            resp = request_pi(x[0], endpoint_port, 'game')
            pi_hosts.append({"hostname": hostname, "address": ''.join(address), "rom": resp.get('rom', ''), "status": resp.get('result', '')})
        except:
            resp = request_pi(x[0], endpoint_port, 'game')
            pi_hosts.append({"address": x[0], "rom": resp.get('rom', ''), "status": resp.get('result', '')})
            continue
    return pi_hosts

def request_pi(ip, port, endpoint, data=None, method='GET'):
    url = 'http://' + ip + ':' + port + '/' + endpoint
    headers = {"Content-Type": "application/json"}

    req = urllib.request.Request(url, headers=headers, method='GET')
    if method == 'POST':
        encoded_data = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(url, data=encoded_data, headers=headers, method='POST')
    try:
        resp = urllib.request.urlopen(req).read()
        body = json.loads(resp.decode("utf-8"))
        print(body)
        response = {'ip': ip}
        if('result' in body):
            response['result'] = body['result']
        elif 'process' in body:    
            response['result'] = body['process']
        else:
            response['result'] = 'unknown'
        response['rom'] = body['rom'] if 'rom' in body else ''
    except Exception as error:
        response = {'ip':ip, 'result': str(error)}
    return response

#Run the skyscraper command twice to update gamelist.xml
def run_skyscraper(console):
    ssCommand = ''
    shell_bool = False
    if platform.system() == 'Windows':
        ssCommand = pathlib.Path.home().joinpath('Skyscraper/Skyscraper.exe')
        shell_bool = True
    else:
        ssCommand = '/opt/retropie/supplementary/skyscraper/Skyscraper'
    
    if not os.path.exists(ssCommand):
            print('skyScraper not found in: ' + ssCommand)
            return

    #Set paths/options in config.ini
    input_path = pathlib.Path.home().joinpath('RetroPie/roms/')
    #gamelists_path = pathlib.Path.home().joinpath('.emulationstation/gamelists/')
    #dlmedia_path = pathlib.Path.home().joinpath('.emulationstation/downloaded_media/')
    paths = ' -i "' + str(input_path.joinpath(console)) 
    options = ' -s screenscraper --flags onlymissing,unattend,skipped'

    command = str(ssCommand) + ' -p ' + console
    
    if platform.system() == "Windows":      
        command = command.replace('\\', "\\\\")
    command2 = command

    if paths_bool:
        command = command + paths
    if options_bool: 
        command = command + options        
    
    print(command)

    subprocess.run(shlex.split(command), shell=shell_bool)
    return subprocess.run(shlex.split(command2), shell=shell_bool)

#Scrape all consoles, while updating the gamelist.xml
def all_skyscraper(consoles):
    ret_list = []
    for console in consoles:
        ret_list.append(run_skyscraper(console))

#Find the current consoles with a gamelist.xml in the rom directory 
def find_consoles():
    consoles = []
    consoles_all = os.listdir(rom_directory)
    for console in consoles_all:
        if os.path.isfile(rom_directory.joinpath(console + '/gamelist.xml')):
            consoles.append(console)
    return consoles

@st.cache_data
def get_roms():
    roms = []
    consoles = []
    genres = {}
    extensions = []

    consoles = find_consoles()
    extensions = ['.null']*len(consoles)

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

        romTree = ET.parse(rom_directory.joinpath(console + '/gamelist.xml'))
        if(romTree is not None):
            #print('romTree found:', pathlib.Path.home().joinpath('.emulationstation/gamelists/' + consoles[i] + '/gamelist.xml'))
            root = romTree.getroot()
            for game in root.iter('game'):
                roms.append({'console': console,
                                'name': game.find('name').text, 
                                'genre': game.find('genre').text, 
                                'players': game.find('players').text})
                for genre in game.find('genre').text.split(','):
                    genres[genre.strip()] = 1
    genres = list(genres)
    genres.sort()
    return consoles, roms, genres


consoles, roms, genres = get_roms()
pis = get_pis()

if len(consoles) > 0:
    expander = st.expander("Console|Rom List")
    with expander:
        if st.button("Refresh Rom List"):
            consoles, roms, genres = get_roms()
        tabs = st.tabs(consoles)
        for i, console in enumerate(consoles):
            with tabs[i]:
                rom_table = [{'name': rom['name'], 'genre': rom['genre'], 'players': rom['players']} for rom in roms if rom['console'] == console]
                st.dataframe(rom_table, height=400)
    expander2 = st.expander("Genre List")
    with expander2:
        st.dataframe(genres, height=400)


pi_col, rom_col = st.tabs(["Communicate", "File Management"])

with pi_col:
    if st.button("Refresh network / pis"):
        if platform.system() == "Linux":
            nmap_discover()
        pis = get_pis()

    pi_selection = st.dataframe(pis, selection_mode="multi-row", on_select="rerun")

    st.subheader("Global Options")
    attract_mode = st.checkbox("Attract Mode (Game changes without user interaction)")
    attract_timeout = st.text_input("Attract Mode Timeout (seconds)", value=300)

    game_tab, filter_tab, maint_tab = st.tabs(["Game Setter", "Filter Setter", "Maintenance"])
    with game_tab:
        console_selection =  st.selectbox("Select Console", consoles)
        if console_selection:
            rom_sublist = [rom['name'] for rom in roms if rom['console'] == console_selection]
            rom_sublist.sort()
            rom_selection = st.selectbox("Select Rom", rom_sublist)
            if rom_selection:
                if st.button("Press to play on Pi(s)", key="RomPlay"):
                    print(console_selection + ' ' + rom_selection)
                    data = {
                        'rom': rom_selection, 
                        'console': console_selection,
                        'attractMode': attract_mode,
                        'attractModeTimeout': attract_timeout
                    }
                    
                    responses = []
                    for pi in pi_selection['selection']['rows']:
                        responses.append(request_pi(pis[pi]['address'], endpoint_port, 'games', data, 'POST'))

                    st.table(responses)

    with filter_tab:
        genre_selection = st.selectbox("Select Genre", genres)
        players_selection = st.selectbox("Select Player Amount (Optional)", [1, 2, 4], index=None)
        if genre_selection:
            if st.button("Press to play on Pi(s)", key="FilterPlay"):
                print('Genre selection: ' + genre_selection)
                data = {
                        'attractMode': attract_mode,
                        'attractModeTimeout': attract_timeout,
                        'filter': 
                            {
                                'genres': genre_selection
                            }
                        }
                if(players_selection):
                    data['filter']['players'] = players_selection

                responses = []
                for pi in pi_selection['selection']['rows']:
                    responses.append(request_pi(pis[pi]['address'], endpoint_port, 'random', data, 'POST'))

                st.table(responses)

    with maint_tab:
        if st.button("Reboot Pi(s)"):
            data = {'dummy': 'data'}
            responses = []
            for pi in pi_selection['selection']['rows']:
                responses.append(request_pi(pis[pi]['address'], endpoint_port, 'reboot', data, 'POST'))

            st.table(responses)
        
        if st.button("Play EmulationStation on Pi(s)"):
            data = {'dummy': 'data'}
            responses = []
            for pi in pi_selection['selection']['rows']:
                responses.append(request_pi(pis[pi]['address'], endpoint_port, 'startES', data, 'POST'))

            st.table(responses)


with rom_col:
    st.header("Rom Uploader")

    up_console =  st.selectbox("Select Console:", consoles, accept_new_options=True)
    up_roms = st.file_uploader("Upload Rom(s)", accept_multiple_files=True)
    if up_roms is not None and len(up_console) > 0 and st.button("Process Rom(s)"):
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
