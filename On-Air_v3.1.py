"""
====================================================================================
Title:        Universal WLED On-Air Sign Sync
Description:  Monitors Windows for active meeting software (Teams, Zoom, Google Meet, 
              Slack, 8x8, GoToMeeting, Notion AI) and automatically triggers a physical 
              WLED sign. Bypasses corporate audio routing by reading native Windows logs.
Author:       Josh
Date:         March 2026

CHANGELOG:
- v1.0.0: Initial build using `pycaw` for audio and `pygetwindow` for window titles.
- v1.1.0: Added Two-Way Sync to fix "blind" toggling desyncs. Added Preset injection.
- v2.0.0: Architectural overhaul. Dropped `pycaw` and switched to native `winreg` 
          Microphone tracking to bypass Work Chrome profiles and headset routing.
- v2.1.0: Added GoToMeeting support and fixed the browser "dead tab" bug.
- v3.0.0: Implemented Master Configuration block. Added app-specific Custom Preset 
          mapping, Universal Mic Check, and Zoom support.
- v3.1.0: Added Notion AI transcript detection using direct process (`.exe`) 
          tracking to prevent window-title interference.
====================================================================================
"""

import time
import os
import requests
import pygetwindow as gw
import winreg  
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

# ==========================================
# --- ⚙️ MASTER CONFIGURATION SECTION ⚙️ ---
# ==========================================
WLED_IP = "http://192.168.1.x"
CHECK_INTERVAL = 2

# --- APP WINDOW TITLES ---
TARGET_8x8 = "8x8 Work (On a Call)"
TARGET_SLACK = "Huddle:"
TARGET_GOTO_APP = "GoToMeeting"  

# --- WLED PRESETS ---
# Set to the WLED Preset ID you want to load for each app.
PRESET_8X8 = 2
PRESET_SLACK = 2
PRESET_MEET = 2
PRESET_TEAMS = 2
PRESET_GOTO_WEB = 2
PRESET_GOTO_APP = 2
PRESET_ZOOM = 2    
PRESET_NOTION = 2  
PRESET_MANUAL = 2  

# ==========================================

# --- STATE TRACKING ---
is_auto_active = False       
script_wants_on = False  
wled_is_actually_on = False 

def get_wled_actual_state():
    """Asks the WLED controller directly if it is physically turned on."""
    try:
        response = requests.get(f"{WLED_IP}/json/state", timeout=1).json()
        return response.get("on", False)
    except:
        return False

def get_active_mic_apps():
    """Returns a list of specific application executables currently using the microphone."""
    active_apps = []
    try:
        key_path = r"Software\Microsoft\Windows\CurrentVersion\CapabilityAccessManager\ConsentStore\microphone\NonPackaged"
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, key_path) as key:
            i = 0
            while True:
                try:
                    subkey_name = winreg.EnumKey(key, i)
                    with winreg.OpenKey(key, subkey_name) as subkey:
                        stop_time, _ = winreg.QueryValueEx(subkey, "LastUsedTimeStop")
                        # If LastUsedTimeStop is 0, this specific app is hot!
                        if stop_time == 0:
                            active_apps.append(subkey_name.lower())
                except EnvironmentError:
                    break
                i += 1
    except Exception:
        pass
    return active_apps

def check_auto_condition():
    """Checks for meetings/recordings and returns TWO things: (Is_Active, Preset_ID)"""
    try:
        all_titles = gw.getAllTitles()
        active_mic_apps = get_active_mic_apps()
        mic_is_hot = len(active_mic_apps) > 0 
        
        # 1. Hardware-Level App Check (Bypasses Window Titles entirely!)
        for app in active_mic_apps:
            if "notion.exe" in app:
                return True, PRESET_NOTION

        # 2. Standalone Apps (No mic check needed, just being open means you're busy)
        for title in all_titles:
            if TARGET_8x8 in title:
                return True, PRESET_8X8
            if title.startswith(TARGET_SLACK):
                return True, PRESET_SLACK
            if TARGET_GOTO_APP in title:
                return True, PRESET_GOTO_APP
            
        # 3. Browser/Universal Apps (Requires the window AND an active microphone)
        for title in all_titles:
            if "Meet -" in title and mic_is_hot:
                return True, PRESET_MEET
            if "Microsoft Teams" in title and mic_is_hot:
                return True, PRESET_TEAMS
            if "GoTo Meeting" in title and mic_is_hot:
                return True, PRESET_GOTO_WEB
            if "Zoom Meeting" in title and mic_is_hot:   
                return True, PRESET_ZOOM
                
    except: pass
    return False, None

def set_wled_power(power_on, preset_id=2):
    """Sends the command to turn WLED on/off and passes the correct Preset ID."""
    if power_on and preset_id is not None:
        cmd = f"{WLED_IP}/win&T=1&PL={preset_id}" 
    else:
        cmd = f"{WLED_IP}/win&T=0"
    try:
        requests.get(cmd, timeout=0.5)
    except: pass

def get_square_image(color):
    img = Image.new('RGB', (64, 64), color)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 64, 64], fill=color)
    return img

def update_tray_visuals(icon):
    global is_auto_active, wled_is_actually_on
    icon.icon = get_square_image('red' if wled_is_actually_on else 'gray')
    
    if is_auto_active and wled_is_actually_on:
        icon.title = f"ON AIR: Auto-Detected (v3.1)"
    elif is_auto_active and not wled_is_actually_on:
        icon.title = "ON AIR: Mic Active (Sign overridden off)"
    elif not is_auto_active and wled_is_actually_on:
        icon.title = "ON AIR: Manual Override ON"
    else:
        icon.title = "ON AIR: Idle"

def action_toggle_manual(icon, item):
    global script_wants_on, wled_is_actually_on
    script_wants_on = not wled_is_actually_on 
    set_wled_power(script_wants_on, PRESET_MANUAL)
    time.sleep(0.2)
    wled_is_actually_on = get_wled_actual_state()
    update_tray_visuals(icon)

def on_exit(icon, item):
    icon.stop()
    os._exit(0)

# --- SYSTEM TRAY SETUP ---
tray_menu = Menu(
    MenuItem('Toggle Sign', action_toggle_manual, default=True),
    MenuItem('Exit', on_exit)
)

tray_icon = Icon("OnAirSign", get_square_image('gray'), "ON AIR: v3.1.0 Running", menu=tray_menu)
tray_icon.run_detached()
time.sleep(1)

# --- MAIN LOOP ---
last_auto_state = False
last_active_preset = None

while True:
    wled_is_actually_on = get_wled_actual_state()
    new_auto_state, triggered_preset = check_auto_condition()
    
    state_changed = (new_auto_state != last_auto_state)
    preset_changed = (new_auto_state and triggered_preset != last_active_preset)
    
    if state_changed or preset_changed:
        is_auto_active = new_auto_state
        script_wants_on = new_auto_state  
        
        set_wled_power(script_wants_on, triggered_preset)
        
        last_auto_state = new_auto_state
        last_active_preset = triggered_preset
        
        time.sleep(0.2)
        wled_is_actually_on = get_wled_actual_state()

    update_tray_visuals(tray_icon) 
    time.sleep(CHECK_INTERVAL)
