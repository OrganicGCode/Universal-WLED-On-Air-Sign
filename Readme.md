# 🎙️ Universal WLED On-Air Sign Sync (v3.1.0)

This Python script acts as a "Universal On-Air Light" for remote workers. It monitors your Windows PC for active meeting software and automatically triggers a physical WLED smart light over your local network. 

**The Magic:** To bypass strict corporate firewalls, VPNs, and hidden headset audio routing, this script reads the native Windows Microphone Privacy Registry to detect when your mic is *truly* "hot."

---

## 🚀 Supported Apps

### 1. Hardware-Level Detection (Mic active via specific `.exe`)
* **Notion AI** (`notion.exe`)

### 2. Browser & Web Apps (Requires specific Window Title + Active Mic)
* **Google Meet** (`"Meet -"`)
* **Microsoft Teams**
* **Zoom** (`"Zoom Meeting"`)
* **GoToMeeting Web**

### 3. Standalone Apps (Requires Window Title only)
* **8x8 Work** (`"8x8 Work (On a Call)"`)
* **Slack Huddles** (`"Huddle:"`)
* **GoToMeeting Desktop App**

---

## 🛠️ Requirements
* A physical **WLED controller** connected to your local Wi-Fi.
* **Python 3.x** installed on your Windows PC.
* The following Python libraries. Run this in your command prompt:
> `pip install requests pygetwindow pillow pystray`

---

## ⚙️ Configuration & Setup
Open the script in any text editor and edit the **MASTER CONFIGURATION SECTION**. You will need to define your `WLED_IP` and set up your WLED Presets.

**⚠️ CRITICAL: The Two-Preset Rule**
For this script to function properly out of the box, you must create at least *two* specific presets inside your WLED app:

1. **Preset 1 (The "OFF" State):** Turn your WLED sign completely OFF. Create a new preset, check the box for *"Apply at boot"*, and save it as **ID 1**. This guarantees your sign boots up dark and gives the script a baseline "Off" state.
2. **Preset 2 (The Default "ON" State):** Turn your WLED sign ON and set it to your preferred default layout (e.g., Solid Red). Save this as **ID 2**. By default, the script points all meeting apps to trigger Preset 2.

*(Optional)*: You can create additional presets (e.g., Preset 3 = Blue for Teams) and map those specific ID numbers to the corresponding apps in the script's configuration block!

---

## ▶️ How to Run
* **For Testing:** Run the script normally from a command prompt. A system tray icon will appear.
* **For Daily Use:** Change the file extension from `.py` to `.pyw`. This tells Windows to run it completely invisibly in the background without keeping a command prompt window open. You can place a shortcut to this file in your Windows Startup folder to run it automatically.

---

## ✨ Features
* 🔄 **Two-Way Sync:** Accurately reflects WLED hardware state in the Windows System Tray.
* 🎨 **Custom Presets:** Assign different colors to different meeting apps.
* 🛡️ **"Dead Tab" Protection:** Automatically turns off if you leave a Google Meet tab open but the microphone disconnects.
* 🤝 **App-to-App Handoff:** Seamlessly switches WLED colors if you jump directly from one meeting platform to another without turning off in between.