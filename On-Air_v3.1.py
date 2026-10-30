"""
====================================================================================
Title:        Universal WLED On-Air Sign Sync
Version:      v3.2.0
Description:  Monitors Windows for active meeting software (Teams, Zoom, Google Meet, 
              Slack, 8x8, GoToMeeting, Notion AI) and automatically triggers a physical 
              WLED sign. Bypasses corporate audio routing by reading native Windows logs.
Author:       Josh
Date:         October 2026

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
- v3.2.0: Replaced deprecated winreg ConsentStore checks with native Windows Core Audio
          (WASAPI) session inspection. Survives audio route changes and 
          headless/background Chrome tab switches.
====================================================================================
"""



import time
import os
import requests
import pygetwindow as gw
import ctypes
from ctypes import wintypes
from PIL import Image, ImageDraw
from pystray import Icon, Menu, MenuItem

# ==========================================
# --- ⚙️ MASTER CONFIGURATION SECTION ⚙️ ---
# ==========================================
WLED_IP = "http://192.168.1.181"
CHECK_INTERVAL = 2

# --- APP WINDOW TITLES ---
TARGET_8X8 = "8x8 Work (On a Call)"
TARGET_SLACK = "Huddle:"
TARGET_GOTO_APP = "GoToMeeting"

# --- WLED PRESETS ---
PRESET_8X8 = 2
PRESET_SLACK = 2
PRESET_MEET = 2
PRESET_TEAMS = 2
PRESET_GOTO = 2
PRESET_ZOOM = 2
PRESET_NOTION = 2
PRESET_MANUAL = 2

# ==========================================
# --- 🎙️ NATIVE WASAPI AUDIO CAPTURE CHECK ---
# ==========================================
class GUID(ctypes.Structure):
    _fields_ = [
        ('Data1', wintypes.DWORD),
        ('Data2', wintypes.WORD),
        ('Data3', wintypes.WORD),
        ('Data4', ctypes.c_ubyte * 8)
    ]
    def __init__(self, l, w1, w2, b):
        super().__init__(l, w1, w2, (ctypes.c_ubyte * 8)(*b))

CLSID_MMDeviceEnumerator = GUID(0xBCDE0395, 0xE52F, 0x467C, [0x8E, 0x3D, 0xC4, 0x57, 0x92, 0x91, 0x69, 0x2E])
IID_IMMDeviceEnumerator = GUID(0xA95664D2, 0x9614, 0x4F35, [0xA7, 0x46, 0xDE, 0x8D, 0xB6, 0x36, 0x17, 0xE6])
IID_IAudioSessionManager2 = GUID(0x77AA99A0, 0x1BD6, 0x484F, [0x8B, 0xC7, 0x2C, 0x65, 0x4C, 0x9A, 0x9B, 0x6F])

ole32 = ctypes.oledll.ole32

def is_microphone_streaming():
    """Queries all active Windows capture endpoints to check if any session is actively capturing."""
    ole32.CoInitialize(None)
    try:
        pEnum = ctypes.c_void_p()
        if ole32.CoCreateInstance(ctypes.byref(CLSID_MMDeviceEnumerator), None, 1, ctypes.byref(IID_IMMDeviceEnumerator), ctypes.byref(pEnum)) != 0 or not pEnum.value:
            return False

        vt_enum = ctypes.cast(pEnum, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        EnumEndpoints = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int, wintypes.DWORD, ctypes.POINTER(ctypes.c_void_p))(vt_enum[3])

        pColl = ctypes.c_void_p()
        # eCapture = 1, DEVICE_STATE_ACTIVE = 1
        if EnumEndpoints(pEnum, 1, 1, ctypes.byref(pColl)) != 0:
            return False

        vt_coll = ctypes.cast(pColl, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
        GetCountColl = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_uint))(vt_coll[3])
        ItemColl = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_uint, ctypes.POINTER(ctypes.c_void_p))(vt_coll[4])

        count = ctypes.c_uint(0)
        GetCountColl(pColl, ctypes.byref(count))
        active_found = False

        for i in range(count.value):
            pDev = ctypes.c_void_p()
            if ItemColl(pColl, i, ctypes.byref(pDev)) == 0 and pDev.value:
                vt_dev = ctypes.cast(pDev, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                Activate = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(GUID), wintypes.DWORD, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(vt_dev[3])

                pMgr = ctypes.c_void_p()
                if Activate(pDev, ctypes.byref(IID_IAudioSessionManager2), 1, None, ctypes.byref(pMgr)) == 0 and pMgr.value:
                    vt_mgr = ctypes.cast(pMgr, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                    GetSessionEnum = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_void_p))(vt_mgr[5])

                    pSessEnum = ctypes.c_void_p()
                    if GetSessionEnum(pMgr, ctypes.byref(pSessEnum)) == 0 and pSessEnum.value:
                        vt_se = ctypes.cast(pSessEnum, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                        GetCountSE = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))(vt_se[3])
                        GetSession = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.c_int, ctypes.POINTER(ctypes.c_void_p))(vt_se[4])

                        sCount = ctypes.c_int(0)
                        GetCountSE(pSessEnum, ctypes.byref(sCount))

                        for s in range(sCount.value):
                            pCtrl = ctypes.c_void_p()
                            if GetSession(pSessEnum, s, ctypes.byref(pCtrl)) == 0 and pCtrl.value:
                                vt_ctrl = ctypes.cast(pCtrl, ctypes.POINTER(ctypes.POINTER(ctypes.c_void_p))).contents
                                GetState = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_void_p, ctypes.POINTER(ctypes.c_int))(vt_ctrl[3])
                                state = ctypes.c_int(0)
                                GetState(pCtrl, ctypes.byref(state))

                                ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt_ctrl[2])(pCtrl)

                                # 1 = AudioSessionStateActive
                                if state.value == 1:
                                    active_found = True
                                    break

                        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt_se[2])(pSessEnum)
                    ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt_mgr[2])(pMgr)
                ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt_dev[2])(pDev)
            if active_found:
                break

        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt_coll[2])(pColl)
        ctypes.WINFUNCTYPE(ctypes.c_ulong, ctypes.c_void_p)(vt_enum[2])(pEnum)
        return active_found
    except:
        return False

# ==========================================

is_auto_active = False
script_wants_on = False
wled_is_actually_on = False

def get_wled_actual_state():
    try:
        response = requests.get(f"{WLED_IP}/json/state", timeout=1).json()
        return response.get("on", False)
    except:
        return False

def check_auto_condition():
    try:
        all_titles = gw.getAllTitles()
        mic_is_hot = is_microphone_streaming()

        # 1. Standalone Apps (Window title alone is authoritative)
        for title in all_titles:
            if TARGET_8X8 in title:
                return True, PRESET_8X8
            if title.startswith(TARGET_SLACK):
                return True, PRESET_SLACK
            if TARGET_GOTO_APP in title:
                return True, PRESET_GOTO

        # 2. Browser / Audio-Gated Apps (Requires meeting presence AND an open mic stream)
        for title in all_titles:
            if "Meet -" in title and mic_is_hot:
                return True, PRESET_MEET
            if ("Microsoft Teams" in title or "Meeting |" in title) and mic_is_hot:
                return True, PRESET_TEAMS
            if "GoTo Meeting" in title and mic_is_hot:
                return True, PRESET_GOTO
            if "Zoom Meeting" in title and mic_is_hot:
                return True, PRESET_ZOOM

        # 3. Notion AI Background Transcription (Active mic check while Notion window exists)
        if mic_is_hot:
            for title in all_titles:
                if "Notion" in title:
                    return True, PRESET_NOTION

    except:
        pass
    return False, None

def set_wled_power(power_on, preset_id=2):
    if power_on and preset_id is not None:
        cmd = f"{WLED_IP}/win&T=1&PL={preset_id}"
    else:
        cmd = f"{WLED_IP}/win&T=0"
    try:
        requests.get(cmd, timeout=0.5)
    except:
        pass

def get_square_image(color):
    img = Image.new('RGB', (64, 64), color)
    d = ImageDraw.Draw(img)
    d.rectangle([0, 0, 64, 64], fill=color)
    return img

def update_tray_visuals(icon):
    global is_auto_active, wled_is_actually_on
    icon.icon = get_square_image('red' if wled_is_actually_on else 'gray')

    if is_auto_active and wled_is_actually_on:
        icon.title = "ON AIR: Auto-Detected (Active)"
    elif is_auto_active and not wled_is_actually_on:
        icon.title = "ON AIR: Auto Active (Overridden Off)"
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

tray_icon = Icon("OnAirSign", get_square_image('gray'), "ON AIR: v3.2.0 Running", menu=tray_menu)
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
