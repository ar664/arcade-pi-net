# ARCADE PI NETWORK MANAGER 
A simple streamlit python script that runs on a raspberry pi to control pis running arcadepi server. This assumes the other pis have mounted the RetroPie and .emulationstation folders from this one.

Setup environment:
```
cd arcade-pi-net
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```
Run Streamlit:
```
cd arcade-pi-net
source venv/Scripts/activate
streamlit run main.py
```

## Misc 

For setting up multiple pis sharing this hosts rom directory. Modify the `/opt/retropie/configs/all/retroarch.cfg ` with the following options:
```
savefile_directory = /home/pi/RetroPie/saves
savestate_directory = /home/pi/RetroPie/savestates
```