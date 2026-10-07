import os
import sys
import json
import time
import threading
import subprocess
import shutil
import copy
from pathlib import Path
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import tkinter.font as tkfont

import ctypes
import pyautogui
import psutil
from pynput import keyboard
import webbrowser

# ──────────────────────────────────────────────────────────────────────────────
# DPI-Awareness  (muss VOR allem anderen gesetzt werden)
# ──────────────────────────────────────────────────────────────────────────────
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass

pyautogui.FAILSAFE = True

# Bilderkennungs-Imports
try:
    import cv2
    import numpy as np
    import mss as _mss_check   # Verfügbarkeit prüfen
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

# ──────────────────────────────────────────────────────────────────────────────
# Pfade
# ──────────────────────────────────────────────────────────────────────────────
if getattr(sys, "frozen", False):
    _BASE_DIR = Path(sys.executable).parent
else:
    _BASE_DIR = Path(__file__).parent

APP_NAME       = "SkadiTerminal"
_PREFIX        = "skadi"
_LEGACY_PREFIX = "gterminal"      # alter Name (Gterminal) — wird migriert

# Projektordner im Google Drive (unter "Meine Ablage")
GDRIVE_PROJECT_DIR = Path("_060_Projekte") / "_010_Aktiv"


def _find_gdrive_root() -> Path | None:
    """Google Drive für Desktop: 'Meine Ablage' bzw. 'My Drive' auf irgendeinem Laufwerk."""
    if os.name != "nt":
        return None
    for letter in "GHIJKLMNOPQRSTUVWXYZDEF":
        for name in ("Meine Ablage", "My Drive"):
            p = Path(f"{letter}:/") / name
            try:
                if p.is_dir():
                    return p
            except OSError:
                pass
    return None

_GDRIVE = _find_gdrive_root()


def _resolve_data_dir() -> Path:
    """
    Datenordner für Templates, Config und Debug-Bilder — auf jedem PC derselbe,
    egal wo die EXE liegt:
      1. Umgebungsvariable SKADI_DATA_DIR
      2. Datei skadi_datenordner.txt neben der EXE (enthält einen Ordnerpfad)
      3. Google Drive: <Laufwerk>:\\Meine Ablage\\_060_Projekte\\_010_Aktiv\\SkadiTerminal
      4. Ordner der EXE
    Ist der Ordner nicht beschreibbar, wird %LOCALAPPDATA%\\SkadiTerminal benutzt.
    """
    candidates = []
    if os.environ.get("SKADI_DATA_DIR"):
        candidates.append(Path(os.environ["SKADI_DATA_DIR"]))
    try:
        txt = (_BASE_DIR / f"{_PREFIX}_datenordner.txt").read_text(encoding="utf-8").strip()
        if txt:
            candidates.append(Path(txt))
    except OSError:
        pass
    if _GDRIVE:
        candidates.append(_GDRIVE / GDRIVE_PROJECT_DIR / APP_NAME)
    candidates.append(_BASE_DIR)
    candidates.append(Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / APP_NAME)

    for d in candidates:
        try:
            d.mkdir(parents=True, exist_ok=True)
            test = d / f".{_PREFIX}_write_test"
            test.write_text("ok", encoding="utf-8")
            test.unlink(missing_ok=True)
            return d
        except OSError:
            continue
    return _BASE_DIR

DATA_DIR = _resolve_data_dir()


def _migrate_legacy_files():
    """
    Holt beim Start fehlende Templates/Config in den Datenordner:
    alte gterminal_*-Dateien (→ skadi_*) und skadi_*-Dateien, die noch neben der
    EXE liegen. Es wird nur kopiert, nie verschoben oder überschrieben.
    """
    sources = [DATA_DIR, _BASE_DIR]
    if _GDRIVE:
        sources += [_GDRIVE / GDRIVE_PROJECT_DIR / "Dota2_Draft_Helfer_Maerz",
                    _GDRIVE / GDRIVE_PROJECT_DIR / "gterminal26"]
    if os.environ.get("LOCALAPPDATA"):
        sources.append(Path(os.environ["LOCALAPPDATA"]) / "Gterminal")
    for d in sources:
        try:
            files = [f for f in d.iterdir() if f.is_file()
                     and f.name.startswith((_LEGACY_PREFIX + "_", _PREFIX + "_"))
                     and "_debug" not in f.name]
        except OSError:
            continue
        for f in files:
            name = (_PREFIX + f.name[len(_LEGACY_PREFIX):]
                    if f.name.startswith(_LEGACY_PREFIX + "_") else f.name)
            target = DATA_DIR / name
            if target.exists() or target == f:
                continue
            try:
                shutil.copy2(f, target)
            except OSError:
                pass

_migrate_legacy_files()

FIELD_TEMPLATE_PATH  = DATA_DIR / f"{_PREFIX}_field.png"
AUSWAHL_TEMPLATE_PATH= DATA_DIR / f"{_PREFIX}_auswahl.png"
PLANUNG_TEMPLATE_PATH= DATA_DIR / f"{_PREFIX}_planung.png"
NEUTRAL_POS_PATH     = DATA_DIR / f"{_PREFIX}_neutral.png"
DOPPELT_TEMPLATE_PATH= DATA_DIR / f"{_PREFIX}_doppelt.png"
_BUNDLE_DIR          = Path(getattr(sys, "_MEIPASS", _BASE_DIR))   # in die EXE gepackte Dateien
ICON_PATH            = next((p for p in (_BASE_DIR / "skaditerminal.ico",
                                         _BUNDLE_DIR / "skaditerminal.ico",
                                         _BASE_DIR / "germinallogo.ico") if p.exists()),
                            _BASE_DIR / "skaditerminal.ico")

def _item_file(set_idx: int, item_idx: int) -> str:
    """Dateiname des Item-Templates (beide Indizes 0-basiert)."""
    return f"{_PREFIX}_{set_idx+1}_{item_idx+1}.png"

def _get_config_path() -> Path:
    return DATA_DIR / f"{_PREFIX}_config.json"

CONFIG_PATH = _get_config_path()

# ──────────────────────────────────────────────────────────────────────────────
# Prozesse
# ──────────────────────────────────────────────────────────────────────────────
STEAM_PROCS   = {"steam.exe", "steamwebhelper.exe"}
GAME_PROCS    = {"dota2.exe", "cs2.exe", "pioneergame.exe"}
DISCORD_PROCS = {"discord.exe", "discordcanary.exe", "discordptb.exe"}
D2_SETTINGS_PATH = r"G:\Meine Ablage\D2 Setting"

# ──────────────────────────────────────────────────────────────────────────────
# KOMPLETTE HELDEN-LISTE  (Dota 2 Stand 2025)
# ──────────────────────────────────────────────────────────────────────────────
# Stärke → Strength | Beweglichkeit → Agility | Intelligenz → Intelligence
ALL_HEROES_MASTER: dict[str, list[tuple[str, str]]] = {
    "Strength": [
        ("aba",     "Abaddon"),
        ("alch",    "Alchemist"),
        ("axe",     "Axe"),
        ("bb",      "Bristleback"),
        ("cent",    "Centaur Warrunner"),
        ("ck",      "Chaos Knight"),
        ("db",      "Dawnbreaker"),
        ("doom",    "Doom"),
        ("dk",      "Dragon Knight"),
        ("esp",     "Earth Spirit"),
        ("esh",     "Earthshaker"),
        ("et",      "Elder Titan"),
        ("huskar",  "Huskar"),
        ("kunkka",  "Kunkka"),
        ("largo",   "Largo"),
        ("lc",      "Legion Commander"),
        ("ls",      "Lifestealer"),
        ("mars",    "Mars"),
        ("ns",      "Night Stalker"),
        ("ogre",    "Ogre Magi"),
        ("omni",    "Omniknight"),
        ("pb",      "Primal Beast"),
        ("pudge",   "Pudge"),
        ("snap",    "Snapfire"),
        ("sb",      "Spirit Breaker"),
        ("sven",    "Sven"),
        ("tide",    "Tidehunter"),
        ("timber",  "Timbersaw"),
        ("tiny",    "Tiny"),
        ("treant",  "Treant Protector"),
        ("tusk",    "Tusk"),
        ("ul",      "Underlord"),
        ("undying", "Undying"),
        ("wk",      "Wraith King"),
    ],
    "Agility": [
        ("am",      "Anti-Mage"),
        ("bs",      "Bloodseeker"),
        ("bh",      "Bounty Hunter"),
        ("brood",   "Broodmother"),
        ("clinkz",  "Clinkz"),
        ("drow",    "Drow Ranger"),
        ("ember",   "Ember Spirit"),
        ("fv",      "Faceless Void"),
        ("gyro",    "Gyrocopter"),
        ("hw",      "Hoodwink"),
        ("jugg",    "Juggernaut"),
        ("kez",     "Kez"),
        ("luna",    "Luna"),
        ("dusa",    "Medusa"),
        ("meepo",   "Meepo"),
        ("mk",      "Monkey King"),
        ("morph",   "Morphling"),
        ("naga",    "Naga Siren"),
        ("pa",      "Phantom Assassin"),
        ("pl",      "Phantom Lancer"),
        ("razor",   "Razor"),
        ("riki",    "Riki"),
        ("rm",      "Ringmaster"),
        ("sf",      "Shadow Fiend"),
        ("slark",   "Slark"),
        ("sniper",  "Sniper"),
        ("spec",    "Spectre"),
        ("ta",      "Templar Assassin"),
        ("tb",      "Terrorblade"),
        ("troll",   "Troll Warlord"),
        ("ursa",    "Ursa"),
        ("weaver",  "Weaver"),
    ],
    "Intelligence": [
        ("aa",       "Ancient Apparition"),
        ("cm",       "Crystal Maiden"),
        ("dp",       "Death Prophet"),
        ("disruptor","Disruptor"),
        ("ench",     "Enchantress"),
        ("grim",     "Grimstroke"),
        ("jakiro",   "Jakiro"),
        ("kotl",     "Keeper of the Light"),
        ("lesh",     "Leshrac"),
        ("lich",     "Lich"),
        ("lina",     "Lina"),
        ("lion",     "Lion"),
        ("muerta",   "Muerta"),
        ("np",       "Nature's Prophet"),
        ("oracle",   "Oracle"),
        ("od",       "Outworld Destroyer"),
        ("puck",     "Puck"),
        ("pugna",    "Pugna"),
        ("qop",      "Queen of Pain"),
        ("rubick",   "Rubick"),
        ("sd",       "Shadow Demon"),
        ("ss",       "Shadow Shaman"),
        ("silencer", "Silencer"),
        ("sky",      "Skywrath Mage"),
        ("storm",    "Storm Spirit"),
        ("tinker",   "Tinker"),
        ("warlock",  "Warlock"),
        ("wd",       "Witch Doctor"),
        ("zeus",     "Zeus"),
    ],
    "Universal": [
        ("arc",     "Arc Warden"),
        ("bane",    "Bane"),
        ("bat",     "Batrider"),
        ("bm",      "Beastmaster"),
        ("brew",    "Brewmaster"),
        ("chen",    "Chen"),
        ("clock",   "Clockwerk"),
        ("ds",      "Dark Seer"),
        ("dw",      "Dark Willow"),
        ("dazzle",  "Dazzle"),
        ("enigma",  "Enigma"),
        ("invo",    "Invoker"),
        ("io",      "Io"),
        ("ld",      "Lone Druid"),
        ("lycan",   "Lycan"),
        ("mag",     "Magnus"),
        ("marci",   "Marci"),
        ("mirana",  "Mirana"),
        ("necro",   "Necrophos"),
        ("nyx",     "Nyx Assassin"),
        ("pango",   "Pangolier"),
        ("phoenix", "Phoenix"),
        ("sk",      "Sand King"),
        ("techies", "Techies"),
        ("venge",   "Vengeful Spirit"),
        ("veno",    "Venomancer"),
        ("viper",   "Viper"),
        ("visage",  "Visage"),
        ("vs",      "Void Spirit"),
        ("wr",      "Windranger"),
        ("ww",      "Winter Wyvern"),
        ("slardar", "Slardar"),
    ],
}

# Standard-Pool (beim ersten Start)
_DEFAULT_POOL = [
    "wk","pudge","kunkka","mars","tusk","tide","ogre","slardar","snap",
    "sniper","drow","weaver","gyro","pa","mk","luna","jugg","fv","sf",
    "lion","lina","muerta","jakiro","silencer","wd","aa","lich",
    "invo","necro",
]

def _build_heroes(pool: list[str], custom: list[dict]) -> dict[str, list[tuple[str, str]]]:
    """Baut die Anzeige-Heroes aus dem Pool + eigenen Helden."""
    pool_set = set(p.lower() for p in pool)
    heroes: dict[str, list[tuple[str, str]]] = {k: [] for k in ALL_HEROES_MASTER}

    for attr, hero_list in ALL_HEROES_MASTER.items():
        for code, name in hero_list:
            if code in pool_set:
                heroes[attr].append((code, name))

    for entry in custom:
        attr = entry.get("attr", "Universal")
        code = entry.get("code", "").strip().lower()
        name = entry.get("name", "").strip()
        if attr in heroes and code and code not in pool_set:
            heroes[attr].append((code, name or code))

    return heroes

# ──────────────────────────────────────────────────────────────────────────────
# Config
# ──────────────────────────────────────────────────────────────────────────────
DEFAULT_CONFIG = {
    "field_point":  [960, 540],
    "pick_points":  [[1000, 800], [1040, 800], [1020, 820]],
    "custom_heroes": [],
    "hero_pool":    list(_DEFAULT_POOL),
    "presets":      {},
    "pinned_presets": [],    # Liste von Preset-Namen die fest angezeigt werden (max 3)
    "startup_preset": "",    # Preset das beim Programmstart automatisch geladen wird
    "timings": {
        "field_click_delay":   0.15,
        "type_duration":       4.0,
        "enter_pause":         1.0,
        "pick_duration":       2.0,
        "pick_click_interval": 0.05,
        "loop_pause":          0.0,
        "suchfeld_wait":       2.0,    # max. Wartezeit auf PLANUNG nach dem Pick
        "doppel_watch":        60.0,   # Phase D: so lange nach dem Pick auf Doppel-Pick achten
    },
    "pick_hotkey":  ["end"],
    "dark_mode":    False,
    "font_large":   False,
    "game_res":     [1920, 1200],
    "pick_mode":    "both",         # "image" | "coords" | "both"
    # Item-Sets für Phase C (6 Sets, je bis zu 6 Items)
    "item_sets": [
        {"name": f"Set {i+1}", "items": [
            {"label": lbl, "file": _item_file(i, j)}
            for j, lbl in enumerate(["Boots","Iron Branch","Stick","Item 4","Item 5","Item 6"])
        ]} for i in range(6)
    ],
    "active_item_set": 0,
    "item_phase_enabled": True,
    "doppel_check_enabled": True,   # Phase D an/aus
}

def load_config() -> dict:
    if CONFIG_PATH.exists():
        try:
            cfg = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            cfg = None
        if isinstance(cfg, dict):
            # Fehlende Keys mit (kopierten!) Defaults auffüllen — sonst teilen
            # sich Config und DEFAULT_CONFIG dieselben Listen/Dicts.
            for k, v in DEFAULT_CONFIG.items():
                if k not in cfg:
                    cfg[k] = copy.deepcopy(v)
            for k, v in DEFAULT_CONFIG["timings"].items():
                cfg["timings"].setdefault(k, v)
            # Item-Templates von gterminal_* auf skadi_* umbenennen
            for s in cfg.get("item_sets", []):
                for it in s.get("items", []):
                    f = it.get("file", "")
                    if f.startswith(_LEGACY_PREFIX + "_"):
                        it["file"] = _PREFIX + f[len(_LEGACY_PREFIX):]
            return cfg
    return copy.deepcopy(DEFAULT_CONFIG)

def save_config(cfg: dict):
    CONFIG_PATH.write_text(json.dumps(cfg, indent=2), encoding="utf-8")

# ──────────────────────────────────────────────────────────────────────────────
# Prozess-Helpers
# ──────────────────────────────────────────────────────────────────────────────
def kill_processes_by_name(names_lower: set[str]) -> list[str]:
    killed = []
    for p in psutil.process_iter(["pid", "name"]):
        try:
            name = (p.info["name"] or "").lower()
            if name in names_lower:
                p.kill()
                killed.append(name)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return killed

def _windows_try_start(paths: list[Path], args: list[str] | None = None) -> bool:
    for p in paths:
        if p.exists():
            try:
                if args:
                    subprocess.Popen([str(p), *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    os.startfile(str(p))
                return True
            except Exception:
                pass
    return False

def _which_try_start(exe_names: list[str], args: list[str] | None = None) -> bool:
    for name in exe_names:
        found = shutil.which(name)
        if found:
            try:
                if args:
                    subprocess.Popen([found, *args], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                else:
                    subprocess.Popen([found], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except Exception:
                pass
    return False

def start_steam() -> bool:
    if os.name == "nt":
        pf    = os.environ.get("ProgramFiles",      r"C:\Program Files")
        pfx86 = os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")
        if _windows_try_start([Path(pfx86)/"Steam"/"steam.exe", Path(pf)/"Steam"/"steam.exe"]):
            return True
        return _which_try_start(["steam.exe", "steam"])
    return _which_try_start(["steam"])

def start_discord() -> bool:
    if os.name == "nt":
        localapp = os.environ.get("LOCALAPPDATA", "")
        appdata  = os.environ.get("APPDATA", "")
        cands = []
        if localapp: cands.append(Path(localapp)/"Discord"/"Update.exe")
        if appdata:  cands.append(Path(appdata) /"Discord"/"Update.exe")
        if _windows_try_start(cands, args=["--processStart","Discord.exe"]): return True
        disc_cands = []
        if localapp:
            base = Path(localapp)/"Discord"
            if base.exists():
                for child in base.glob("app-*"):
                    disc_cands.append(child/"Discord.exe")
        if _windows_try_start(disc_cands): return True
        return _which_try_start(["Discord.exe","discord"])
    return _which_try_start(["discord"])

def open_discord_voice_video():
    url = "discord://-/settings/voice"
    try:
        webbrowser.open(url)
    except Exception:
        if os.name == "nt":
            try: os.startfile(url)
            except Exception: pass

def open_folder(path_str: str) -> bool:
    try:
        if os.name == "nt":           os.startfile(path_str)
        elif sys.platform == "darwin": subprocess.Popen(["open",     path_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        else:                          subprocess.Popen(["xdg-open", path_str], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        return True
    except Exception:
        return False

# ──────────────────────────────────────────────────────────────────────────────
# Farb-Paletten
# ──────────────────────────────────────────────────────────────────────────────
PAL_DARK = {
    "bg":"#15172a","surface":"#1d2038","surface2":"#262a4a",
    "accent":"#f0506e","on_accent":"#ffffff","text":"#e6e7f2","text_dim":"#9a9cc0",
    "str_col":"#f06a6a","agi_col":"#5cd68a","int_col":"#6aa8f0","uni_col":"#c98af0",
    "btn_bg":"#2b2f52","hover":"#383d68","separator":"#33375c",
    "success":"#2fa866","danger":"#f0506e","input_bg":"#23264a",
}
PAL_LIGHT = {
    "bg":"#eceef5","surface":"#ffffff","surface2":"#dde1ee",
    "accent":"#c0143c","on_accent":"#ffffff","text":"#1a1c2e","text_dim":"#5b5e80",
    "str_col":"#b02020","agi_col":"#17733c","int_col":"#1050b0","uni_col":"#7030a0",
    "btn_bg":"#e4e7f2","hover":"#cfd4ea","separator":"#c9cee2",
    "success":"#1e8048","danger":"#c0143c","input_bg":"#f4f6ff",
}
PAL: dict[str, str] = dict(PAL_LIGHT)

ATTR_ORDER  = ["Strength","Agility","Intelligence","Universal"]
ATTR_COLORS = {"Strength": PAL["str_col"],"Agility": PAL["agi_col"],"Intelligence": PAL["int_col"],"Universal": PAL["uni_col"]}
ATTR_ICONS  = {"Strength":"STR","Agility":"AGI","Intelligence":"INT","Universal":"UNI"}
ATTR_DE     = {"Strength":"Stärke","Agility":"Beweglichkeit","Intelligence":"Intelligenz","Universal":"Universal"}
HERO_COLS   = 5
WIN_W       = 480
RES_PRESETS = [(2560, 1600, 165), (1920, 1200, 165)]   # Auflösungs-Buttons auf der Startseite
MODE_LABELS = {"image": "Bild", "coords": "Koord.", "both": "Beides"}

# Schriften: (Familie, Basisgröße in pt, Gewicht). "Groß" skaliert alles um 20 %.
FONT_SPECS = {
    "ui":         ("Segoe UI", 9, "normal"),
    "ui_bold":    ("Segoe UI", 9, "bold"),
    "mono":       ("Consolas", 9, "normal"),
    "title":      ("Segoe UI", 11, "bold"),
    "section":    ("Segoe UI", 8, "bold"),
    "small":      ("Segoe UI", 8, "normal"),
    "small_bold": ("Segoe UI", 8, "bold"),
    "hero":       ("Consolas", 9, "normal"),
    "hero_bold":  ("Consolas", 9, "bold"),
    "status":     ("Segoe UI", 8, "normal"),
    "big_bold":   ("Segoe UI", 9, "bold"),
}

# ──────────────────────────────────────────────────────────────────────────────
# Hotkey-Helpers
# ──────────────────────────────────────────────────────────────────────────────
_TK_TO_PYNPUT: dict[str, str] = {
    "Control_L":"ctrl","Control_R":"ctrl","Shift_L":"shift","Shift_R":"shift",
    "Alt_L":"alt","Alt_R":"alt","End":"end","Home":"home",
    "Prior":"page_up","Next":"page_down","Return":"enter","BackSpace":"backspace",
    "Insert":"insert","Delete":"delete",
    "Up":"up","Down":"down","Left":"left","Right":"right",
    "Tab":"tab","Escape":"esc",
    **{f"F{i}":f"f{i}" for i in range(1,13)},
}
_KEY_DISPLAY: dict[str, str] = {
    "ctrl":"Strg","shift":"Shift","alt":"Alt","end":"Ende","home":"Pos1",
    "page_up":"Bild+","page_down":"Bild-","enter":"Enter","backspace":"Backspace",
    "delete":"Entf","insert":"Einfg","up":"↑","down":"↓","left":"←","right":"→",
    "tab":"Tab","esc":"Esc",
    **{f"f{i}":f"F{i}" for i in range(1,13)},
}

def _hotkey_display(keys: list[str]) -> str:
    return " + ".join(_KEY_DISPLAY.get(k, k.upper()) for k in keys)

def _pynput_matches(key, key_str: str) -> bool:
    if key_str=="ctrl"  and key in (keyboard.Key.ctrl_l,  keyboard.Key.ctrl_r):  return True
    if key_str=="shift" and key in (keyboard.Key.shift_l, keyboard.Key.shift_r): return True
    if key_str=="alt"   and key in (keyboard.Key.alt_l,   keyboard.Key.alt_r, keyboard.Key.alt_gr): return True
    if hasattr(key,"name") and key.name==key_str: return True
    if hasattr(key,"char") and key.char and key.char.lower()==key_str: return True
    return False

def _apply_icon(window):
    try:
        if ICON_PATH.exists():
            window.iconbitmap(str(ICON_PATH))
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────────────────────
# Auflösungs-API (Windows)
# ──────────────────────────────────────────────────────────────────────────────
class _DEVMODE(ctypes.Structure):
    _fields_ = [
        ("dmDeviceName",        ctypes.c_wchar * 32),
        ("dmSpecVersion",       ctypes.c_ushort),
        ("dmDriverVersion",     ctypes.c_ushort),
        ("dmSize",              ctypes.c_ushort),
        ("dmDriverExtra",       ctypes.c_ushort),
        ("dmFields",            ctypes.c_ulong),
        ("dmPositionX",         ctypes.c_long),
        ("dmPositionY",         ctypes.c_long),
        ("dmDisplayOrientation",ctypes.c_ulong),
        ("dmDisplayFixedOutput",ctypes.c_ulong),
        ("dmColor",             ctypes.c_short),
        ("dmDuplex",            ctypes.c_short),
        ("dmYResolution",       ctypes.c_short),
        ("dmTTOption",          ctypes.c_short),
        ("dmCollate",           ctypes.c_short),
        ("dmFormName",          ctypes.c_wchar * 32),
        ("dmLogPixels",         ctypes.c_ushort),
        ("dmBitsPerPel",        ctypes.c_ulong),
        ("dmPelsWidth",         ctypes.c_ulong),
        ("dmPelsHeight",        ctypes.c_ulong),
        ("dmDisplayFlags",      ctypes.c_ulong),
        ("dmDisplayFrequency",  ctypes.c_ulong),
        ("dmICMMethod",         ctypes.c_ulong),
        ("dmICMIntent",         ctypes.c_ulong),
        ("dmMediaType",         ctypes.c_ulong),
        ("dmDitherType",        ctypes.c_ulong),
        ("dmReserved1",         ctypes.c_ulong),
        ("dmReserved2",         ctypes.c_ulong),
        ("dmPanningWidth",      ctypes.c_ulong),
        ("dmPanningHeight",     ctypes.c_ulong),
    ]

def _get_current_resolution() -> tuple[int, int, int]:
    dm = _DEVMODE()
    dm.dmSize = ctypes.sizeof(_DEVMODE)
    ctypes.windll.user32.EnumDisplaySettingsW(None, -1, ctypes.byref(dm))
    return int(dm.dmPelsWidth), int(dm.dmPelsHeight), int(dm.dmDisplayFrequency)

def _apply_resolution(width: int, height: int, hz: int) -> bool:
    dm = _DEVMODE()
    dm.dmSize             = ctypes.sizeof(_DEVMODE)
    dm.dmPelsWidth        = width
    dm.dmPelsHeight       = height
    dm.dmDisplayFrequency = hz
    dm.dmBitsPerPel       = 32
    dm.dmFields           = 0x00080000 | 0x00100000 | 0x00400000 | 0x00040000
    result = ctypes.windll.user32.ChangeDisplaySettingsW(ctypes.byref(dm), 0x01)
    return result == 0


# ──────────────────────────────────────────────────────────────────────────────
# Bilderkennung: Template-Cache + Screenshot pro Thread
# ──────────────────────────────────────────────────────────────────────────────
class _TemplateCache:
    """Lädt Templates einmal (Graustufen) und lädt neu, wenn die Datei sich ändert."""
    def __init__(self):
        self._cache: dict[Path, tuple[float, object]] = {}
        self._lock = threading.Lock()

    def get(self, path: Path):
        try:
            mtime = path.stat().st_mtime
        except OSError:
            return None
        with self._lock:
            hit = self._cache.get(path)
        if hit and hit[0] == mtime:
            return hit[1]
        img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        with self._lock:
            self._cache[path] = (mtime, img)
        return img

_TEMPLATES = _TemplateCache()
_screen_tls = threading.local()   # mss-Instanzen sind nicht thread-sicher

def _grab_screen_gray():
    sct = getattr(_screen_tls, "sct", None)
    if sct is None:
        import mss
        sct = _screen_tls.sct = mss.mss()
    raw = sct.grab(sct.monitors[1])
    return cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2GRAY)

def _release_screen():
    sct = getattr(_screen_tls, "sct", None)
    if sct is not None:
        try: sct.close()
        except Exception: pass
        _screen_tls.sct = None


# ──────────────────────────────────────────────────────────────────────────────
# GUI
# ──────────────────────────────────────────────────────────────────────────────
class SkadiTerminalApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title(APP_NAME)
        self.cfg  = load_config()

        # Theme & Schriftgröße
        self._dark_mode:  bool = self.cfg.get("dark_mode",  False)
        self._font_large: bool = self.cfg.get("font_large", False)
        PAL.update(PAL_DARK if self._dark_mode else PAL_LIGHT)
        self._sync_attr_colors()
        self.root.configure(bg=PAL["bg"])

        # Schrift-Objekte (tkfont — änderbar ohne UI-Neuaufbau)
        self._fonts = {name: tkfont.Font(root, family=fam, size=self._fsize(base), weight=w)
                       for name, (fam, base, w) in FONT_SPECS.items()}

        # State
        self.stop_enter = threading.Event()
        self.stop_four  = threading.Event()
        self.stop_pick  = threading.Event()
        self.enter_thread = None
        self.four_thread  = None
        self.pick_thread  = None
        self.selected_heroes: list[str] = []
        self.hero_buttons:    dict[str, tk.Button] = {}
        self.pressed_keys     = set()
        self.kill_combo_armed = False
        self.close_apps_armed = False
        self.pick_hotkey_armed= False
        self.calibrating  = False
        self.calib_points: list[tuple[int,int]] = []
        self.calib_lock   = threading.Lock()
        self.status_var   = tk.StringVar(value=f"Bereit.  Config: {CONFIG_PATH.name}")
        self.theme_btn = None
        self.font_btn  = None

        self._install_hover()
        self._setup_ttk_style()

        root.columnconfigure(0, weight=1)
        root.rowconfigure(0, weight=1)

        main = tk.Frame(root, bg=PAL["bg"], padx=8, pady=6)
        main.grid(row=0, column=0, sticky="nsew")
        main.columnconfigure(0, weight=1)
        main.rowconfigure(2, weight=1)

        # ── AUTOMATIK ─────────────────────────────────────────────────
        auto = self._section(main, "AUTOMATIK", row=0,
                             hint="Pos1 · Strg+Einfg · ⌫ = Stop")
        auto.columnconfigure((0, 1, 2), weight=1, uniform="auto")
        self._btn(auto, "Enter alle 5 s",   self.start_enter).grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self._btn(auto, "Taste 4 alle 5 s", self.start_four ).grid(row=0, column=1, sticky="ew", padx=3)
        self._btn(auto, "■  STOP", self.stop_all_macros, accent=True
                  ).grid(row=0, column=2, sticky="ew", padx=(3, 0))

        # ── APPS ──────────────────────────────────────────────────────
        apps = self._section(main, "APPS", row=1,
                             hint="Einfg+Entf = Steam+Discord ✕ · Bild↑+Bild↓ = Spiele ✕")
        apps.columnconfigure((0, 1, 2, 3), weight=1, uniform="apps")
        for col, (txt, cmd) in enumerate([
            ("▶ Steam",       self.ui_start_steam),
            ("▶ Discord",     self.ui_start_discord),
            ("Voice & Video", self.ui_open_discord_voice_video),
            ("D2 Settings",   self.ui_open_d2_settings_folder),
        ]):
            self._btn(apps, txt, cmd).grid(row=0, column=col, sticky="ew",
                                           padx=(0 if col == 0 else 2, 0 if col == 3 else 2))
        for col, (txt, cmd, acc) in enumerate([
            ("✕ Steam",           self.kill_steam,         False),
            ("✕ Discord",         self.kill_discord,       False),
            ("✕ Steam+Disc.",    self.kill_steam_discord, False),
            ("✕ Spiele",          self.kill_games,         True),
        ]):
            self._btn(apps, txt, cmd, accent=acc).grid(row=1, column=col, sticky="ew", pady=(4, 0),
                                                      padx=(0 if col == 0 else 2, 0 if col == 3 else 2))

        # ── HELDEN-PICK (Notebook) ────────────────────────────────────
        pick_outer = self._section(main, "HELDEN-PICK", row=2, expand=True,
                                   hint="Ende = Pick starten")
        self._pick_hint_lbl = self._last_section_hint
        pick_outer.configure(padx=0, pady=0)
        pick_outer.rowconfigure(0, weight=1)

        nb = ttk.Notebook(pick_outer, style="GT.TNotebook")
        nb.grid(row=0, column=0, sticky="nsew")

        # ── TAB 1 : Pick ──────────────────────────────────────────────
        tab_pick = tk.Frame(nb, bg=PAL["surface"], padx=6, pady=6)
        tab_pick.columnconfigure(0, weight=1)
        tab_pick.rowconfigure(4, weight=1)
        nb.add(tab_pick, text="  Pick  ")

        # Zeile 0: Auswahl + Leeren
        top_row = tk.Frame(tab_pick, bg=PAL["surface"])
        top_row.grid(row=0, column=0, sticky="ew", pady=(0, 6))
        top_row.columnconfigure(0, weight=1)

        self.selected_label = tk.Label(top_row, text="", bg=PAL["surface"], fg=PAL["text"],
                                       font=self._fonts["ui_bold"], anchor="w",
                                       justify="left", wraplength=360)
        self.selected_label.grid(row=0, column=0, sticky="ew")
        self._small_btn(top_row, "✕ leeren", self.clear_selection
                        ).grid(row=0, column=1, sticky="ne", padx=(4, 0))

        # Zeile 1: Phasen-Schalter + Item-Sets
        item_row = tk.Frame(tab_pick, bg=PAL["surface"])
        item_row.grid(row=1, column=0, sticky="ew", pady=(0, 6))
        item_row.columnconfigure((0, 1, 2), weight=1, uniform="itemset")

        self._item_phase_var = tk.BooleanVar(value=self.cfg.get("item_phase_enabled", True))

        def _toggle_cfg(key):
            self.cfg[key] = not self.cfg.get(key, True)
            save_config(self.cfg)
            _update_toggles()

        self._onoff_btn  = self._toggle_btn(item_row, lambda: _toggle_cfg("item_phase_enabled"))
        self._onoff_btn.grid(row=0, column=0, sticky="ew", padx=(0, 2))
        self._doppel_btn = self._toggle_btn(item_row, lambda: _toggle_cfg("doppel_check_enabled"))
        self._doppel_btn.grid(row=0, column=1, sticky="ew", padx=2)
        self._small_btn(item_row, "⚙ Item-Sets", self.open_item_set_editor
                        ).grid(row=0, column=2, sticky="ew", padx=(2, 0))

        def _update_toggles():
            for btn, key, label in ((self._onoff_btn,  "item_phase_enabled",   "Items kaufen"),
                                    (self._doppel_btn, "doppel_check_enabled", "Doppel-Check")):
                on = self.cfg.get(key, True)
                btn.config(text=f"{'✔' if on else '✕'}  {label}",
                           bg=PAL["success"] if on else PAL["btn_bg"],
                           fg=PAL["on_accent"] if on else PAL["text_dim"],
                           activebackground=PAL["success"], activeforeground=PAL["on_accent"])
            self._item_phase_var.set(self.cfg.get("item_phase_enabled", True))
        _update_toggles()
        self._update_onoff_btn = _update_toggles

        self._item_set_var  = tk.IntVar(value=self.cfg.get("active_item_set", 0))
        self._item_set_btns: list[tk.Button] = []

        def _set_active_item_set(idx: int):
            self.cfg["active_item_set"] = idx
            save_config(self.cfg)
            self._item_set_var.set(idx)
            _refresh_item_set_btns()

        def _refresh_item_set_btns():
            active = self.cfg.get("active_item_set", 0)
            sets   = self.cfg.get("item_sets", DEFAULT_CONFIG["item_sets"])
            for i, btn in enumerate(self._item_set_btns):
                on = i == active
                btn.config(text=sets[i]["name"] if i < len(sets) else f"Set {i+1}",
                           bg=PAL["accent"] if on else PAL["btn_bg"],
                           fg=PAL["on_accent"] if on else PAL["text"],
                           font=self._fonts["small_bold" if on else "small"])
        self._refresh_item_set_btns = _refresh_item_set_btns

        for idx in range(6):
            btn = tk.Button(item_row, command=lambda i=idx: _set_active_item_set(i),
                            relief="flat", bd=0, cursor="hand2", padx=2, pady=3,
                            activebackground=PAL["accent"], activeforeground=PAL["on_accent"],
                            highlightthickness=0)
            btn.grid(row=1 + idx // 3, column=idx % 3, sticky="ew",
                     padx=(0 if idx % 3 == 0 else 2, 0 if idx % 3 == 2 else 2), pady=(4, 0))
            self._item_set_btns.append(btn)
        _refresh_item_set_btns()

        # Zeile 2: Presets
        preset_outer = tk.Frame(tab_pick, bg=PAL["surface"])
        preset_outer.grid(row=2, column=0, sticky="ew", pady=(0, 6))
        preset_outer.columnconfigure(0, weight=1)

        preset_header = tk.Frame(preset_outer, bg=PAL["surface"])
        preset_header.grid(row=0, column=0, sticky="ew", pady=(0, 3))
        preset_header.columnconfigure(0, weight=1)
        tk.Label(preset_header, text="PRESETS", bg=PAL["surface"], fg=PAL["text_dim"],
                 font=self._fonts["section"], anchor="w").grid(row=0, column=0, sticky="w")

        self._preset_open = tk.BooleanVar(value=False)

        def _toggle_preset():
            if self._preset_open.get():
                preset_extra.grid_remove()
                self._preset_open.set(False)
            else:
                preset_extra.grid()
                self._preset_open.set(True)
            toggle_btn.config(text="▾ weniger" if self._preset_open.get() else "▸ alle")
            self._fit_window()

        toggle_btn = self._small_btn(preset_header, "▸ alle", _toggle_preset)
        toggle_btn.grid(row=0, column=1, sticky="e", padx=(0, 2))
        self._small_btn(preset_header, "＋ speichern", self.save_preset_dialog
                        ).grid(row=0, column=2, sticky="e", padx=2)

        self._preset_edit_mode = False

        def _toggle_edit_mode():
            self._preset_edit_mode = not self._preset_edit_mode
            edit_btn.config(bg=PAL["accent"] if self._preset_edit_mode else PAL["btn_bg"],
                            fg=PAL["on_accent"] if self._preset_edit_mode else PAL["text"])
            self.status_var.set("Bearbeiten: ☆ = Preset beim Start laden" if self._preset_edit_mode
                                else "Bearbeiten beendet.")
            self._rebuild_preset_buttons()
            self._fit_window()

        edit_btn = self._small_btn(preset_header, "✏", _toggle_edit_mode)
        edit_btn.grid(row=0, column=3, sticky="e", padx=(2, 0))
        self._preset_edit_btn = edit_btn

        self.preset_btn_frame = tk.Frame(preset_outer, bg=PAL["surface"])
        self.preset_btn_frame.grid(row=1, column=0, sticky="ew")

        preset_extra = tk.Frame(preset_outer, bg=PAL["surface"])
        preset_extra.grid(row=2, column=0, sticky="ew")
        preset_extra.grid_remove()
        self._preset_extra_frame = preset_extra

        self._rebuild_preset_buttons()

        # Zeile 3: Trennlinie, Zeile 4: Hero-Grid
        tk.Frame(tab_pick, bg=PAL["separator"], height=1).grid(row=3, column=0, sticky="ew", pady=(0, 4))
        self.hero_frame = tk.Frame(tab_pick, bg=PAL["surface"])
        self.hero_frame.grid(row=4, column=0, sticky="nsew")
        for c in range(HERO_COLS):
            self.hero_frame.columnconfigure(c, weight=1, uniform="hero")
        self._rebuild_hero_grid()

        # ── TAB 2 : Konfiguration ─────────────────────────────────────
        tab_cfg = tk.Frame(nb, bg=PAL["surface"], padx=6, pady=6)
        tab_cfg.columnconfigure((0, 1), weight=1, uniform="cfg")
        nb.add(tab_cfg, text="  Konfiguration  ")

        cfg_row = 0

        def cfg_header(text):
            nonlocal cfg_row
            tk.Label(tab_cfg, text=text, bg=PAL["surface"], fg=PAL["text_dim"],
                     font=self._fonts["section"], anchor="w"
                     ).grid(row=cfg_row, column=0, columnspan=2, sticky="w",
                            pady=(0 if cfg_row == 0 else 10, 3))
            cfg_row += 1

        def cfg_buttons(items):
            nonlocal cfg_row
            for i, (label, cmd) in enumerate(items):
                self._btn(tab_cfg, label, cmd).grid(
                    row=cfg_row + i // 2, column=i % 2, sticky="ew",
                    padx=(0 if i % 2 == 0 else 2, 2 if i % 2 == 0 else 0), pady=2)
            cfg_row += (len(items) + 1) // 2

        cfg_header("ERKENNUNG")
        self._mode_var = tk.StringVar(value=self.cfg.get("pick_mode", "both"))
        mode_row = tk.Frame(tab_cfg, bg=PAL["surface"])
        mode_row.grid(row=cfg_row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        cfg_row += 1
        tk.Label(mode_row, text="Pick-Modus:", bg=PAL["surface"], fg=PAL["text"],
                 font=self._fonts["ui"]).pack(side="left", padx=(0, 6))
        mode_inner = tk.Frame(mode_row, bg=PAL["separator"], padx=1, pady=1)
        mode_inner.pack(side="left")
        tk.Label(mode_row, text="Bild = Templates · Koord. = F8-Punkte", bg=PAL["surface"],
                 fg=PAL["text_dim"], font=self._fonts["small"]).pack(side="left", padx=(8, 0))

        def _set_mode(val):
            self._mode_var.set(val)
            self.cfg["pick_mode"] = val
            save_config(self.cfg)
            _refresh_mode_buttons()
            self.status_var.set(f"Erkennung: {MODE_LABELS[val]}")

        self._mode_btns = {}
        for val in ("image", "coords", "both"):
            b = tk.Button(mode_inner, text=MODE_LABELS[val], command=lambda v=val: _set_mode(v),
                          relief="flat", bd=0, cursor="hand2",
                          font=self._fonts["small"], padx=7, pady=2, highlightthickness=0)
            b.pack(side="left", padx=(0 if val == "image" else 1, 0))
            self._mode_btns[val] = b

        def _refresh_mode_buttons():
            cur = self._mode_var.get()
            for key, btn in self._mode_btns.items():
                on = key == cur
                btn.config(bg=PAL["accent"] if on else PAL["btn_bg"],
                           fg=PAL["on_accent"] if on else PAL["text"],
                           activebackground=PAL["accent"], activeforeground=PAL["on_accent"])
        _refresh_mode_buttons()
        self._refresh_mode_buttons = _refresh_mode_buttons

        cfg_buttons([
            ("Bild-Templates erfassen",      self.open_image_calib_dialog),
            ("Erkennung testen",             self.test_image_recognition),
            ("Doppel-Pick-Test",             self.test_doppel_check),
            ("Koordinaten kalibrieren (F8)", self.start_calibration),
        ])

        cfg_header("PICK & ITEMS")
        cfg_buttons([
            ("Zeiten & Hotkey",          self.open_timing_config),
            ("Item-Sets verwalten",      self.open_item_set_editor),
            ("Held-Pool verwalten",      self.open_hero_pool_manager),
            ("Eigenen Held hinzufügen",  self.open_hero_manager),
        ])

        cfg_header("ANZEIGE")
        self.theme_btn = self._btn(tab_cfg, "", self.toggle_theme)
        self.theme_btn.grid(row=cfg_row, column=0, sticky="ew", padx=(0, 2), pady=2)
        self.font_btn = self._btn(tab_cfg, "", self.toggle_font_scale)
        self.font_btn.grid(row=cfg_row, column=1, sticky="ew", padx=(2, 0), pady=2)
        self._update_display_btns()
        cfg_row += 1

        cfg_header("STRATZ")
        cfg_buttons([(name, lambda u=url: webbrowser.open(u)) for name, url in [
            ("Robert", "https://stratz.com/players/44216623"),
            ("Jan",    "https://stratz.com/players/20846181"),
            ("Ben",    "https://stratz.com/players/314442285"),
        ]])

        cfg_header("STATUS")
        self._cfg_mode_label = tk.Label(tab_cfg, text="", bg=PAL["surface"], fg=PAL["text"],
                                        font=self._fonts["mono"], anchor="w", justify="left")
        self._cfg_mode_label.grid(row=cfg_row, column=0, columnspan=2, sticky="ew")
        cfg_row += 1

        def _update_cfg_mode_label(*_):
            ok = lambda b, miss="✕ fehlt": "✔" if b else miss
            lines = [
                f"Suchfeld        {ok(FIELD_TEMPLATE_PATH.exists())}",
                f"Auswählen       {ok(AUSWAHL_TEMPLATE_PATH.exists())}",
                f"Planung         {ok(PLANUNG_TEMPLATE_PATH.exists())}",
                f"Doppel-Pick     {ok(DOPPELT_TEMPLATE_PATH.exists(), '– optional')}",
                f"Koordinaten     {ok(self._has_coords(), '✕ nicht kalibriert')}",
            ]
            self._cfg_mode_label.config(text="\n".join(lines))

        _update_cfg_mode_label()
        self._update_cfg_mode_label = _update_cfg_mode_label
        nb.bind("<<NotebookTabChanged>>", lambda e: (_update_cfg_mode_label(), self._fit_window()))

        tk.Label(tab_cfg, text=f"Datenordner (Templates, Config): {DATA_DIR}", bg=PAL["surface"], fg=PAL["text_dim"],
                 font=self._fonts["small"], anchor="w", justify="left", wraplength=420
                 ).grid(row=cfg_row, column=0, columnspan=2, sticky="ew", pady=(6, 2))
        cfg_row += 1
        cfg_buttons([
            ("Alte Templates importieren …", self.import_templates),
            ("Datenordner öffnen",           lambda: open_folder(str(DATA_DIR))),
        ])

        # ── AUFLÖSUNG (immer sichtbar) ────────────────────────────────
        res = self._section(main, "AUFLÖSUNG", row=3)
        self._res_status = self._last_section_hint      # aktuelle Auflösung rechts im Titel
        res.columnconfigure((0, 1), weight=1, uniform="res")
        self._res_btns: dict[tuple[int, int, int], tk.Button] = {}
        for col, mode in enumerate(RES_PRESETS):
            w, h, hz = mode
            b = self._btn(res, f"{w} × {h} · {hz} Hz", lambda m=mode: self._set_res(*m))
            b.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 2, 2 if col == 0 else 0))
            self._res_btns[mode] = b
        self._refresh_res_display()

        # ── Statusleiste ──────────────────────────────────────────────
        status_bar = tk.Frame(root, bg=PAL["surface2"])
        status_bar.grid(row=1, column=0, sticky="ew")
        status_bar.columnconfigure(0, weight=1)
        tk.Label(status_bar, textvariable=self.status_var,
                 bg=PAL["surface2"], fg=PAL["text"],
                 font=self._fonts["status"], anchor="w", padx=8, pady=4
                 ).grid(row=0, column=0, sticky="ew")
        tk.Button(status_bar, text="💾 Speichern", command=self.save_all_settings,
                  bg=PAL["surface2"], fg=PAL["text"],
                  activebackground=PAL["success"], activeforeground=PAL["on_accent"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["small"], padx=8, pady=3, highlightthickness=0
                  ).grid(row=0, column=1, sticky="e", padx=(0, 4))
        # Lange Statusmeldungen umbrechen statt das Fenster zu verbreitern
        status_bar.bind("<Configure>", lambda e: status_bar.winfo_children()[0].config(
            wraplength=max(200, e.width - 110)))

        # Hotkey-Listener
        self.kb_listener = keyboard.Listener(
            on_press=self._on_global_key_press,
            on_release=self._on_global_key_release)
        self.kb_listener.daemon = True
        self.kb_listener.start()
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self._update_hotkey_hint()

        # Startup-Preset beim Start automatisch laden
        sp = self.cfg.get("startup_preset", "")
        if sp and sp in self.cfg.get("presets", {}):
            self.root.after(200, lambda: self.load_preset(sp))

        # Auto-Close Timer
        self._last_game_seen = time.time()
        self._auto_close_check()

    # ──────────────────────────────────────────────────────────────────
    # Font-Helpers
    # ──────────────────────────────────────────────────────────────────
    def _fsize(self, base: int) -> int:
        return round(base * (1.2 if self._font_large else 1.0))

    def _update_fonts(self):
        for name, (_fam, base, _w) in FONT_SPECS.items():
            self._fonts[name].configure(size=self._fsize(base))

    def _fit_window(self):
        """Breite fix, Höhe an den Inhalt anpassen (aber nie höher als der Bildschirm)."""
        self.root.update_idletasks()
        h = min(self.root.winfo_reqheight(), self.root.winfo_screenheight() - 80)
        self.root.geometry(f"{WIN_W}x{h}")

    # ──────────────────────────────────────────────────────────────────
    # Stil: ttk-Tabs, Hover-Effekt
    # ──────────────────────────────────────────────────────────────────
    def _setup_ttk_style(self):
        style = ttk.Style()
        style.theme_use("clam")
        style.configure("GT.TNotebook", background=PAL["surface"], borderwidth=0,
                        bordercolor=PAL["separator"], lightcolor=PAL["surface"],
                        darkcolor=PAL["surface"], tabmargins=[0, 0, 0, 0])
        style.configure("GT.TNotebook.Tab", background=PAL["btn_bg"], foreground=PAL["text_dim"],
                        padding=[12, 5], font=self._fonts["ui_bold"], borderwidth=0,
                        bordercolor=PAL["separator"], lightcolor=PAL["btn_bg"])
        style.map("GT.TNotebook.Tab",
                  background=[("selected", PAL["surface"]), ("active", PAL["hover"])],
                  foreground=[("selected", PAL["accent"])],
                  lightcolor=[("selected", PAL["surface"])])

    def _install_hover(self):
        """Neutrale Buttons beim Überfahren leicht hervorheben."""
        def _enter(e):
            w = e.widget
            try:
                if w.cget("bg") == PAL["btn_bg"]:
                    w.config(bg=PAL["hover"])
            except Exception:
                pass

        def _leave(e):
            w = e.widget
            try:
                if w.cget("bg") == PAL["hover"]:
                    w.config(bg=PAL["btn_bg"])
            except Exception:
                pass

        self.root.bind_class("Button", "<Enter>", _enter, add="+")
        self.root.bind_class("Button", "<Leave>", _leave, add="+")

    def _update_display_btns(self):
        if self.theme_btn:
            self.theme_btn.config(text=f"Design: {'Dunkel' if self._dark_mode else 'Hell'}")
        if self.font_btn:
            self.font_btn.config(text=f"Schrift: {'Groß' if self._font_large else 'Normal'}")

    def _update_hotkey_hint(self):
        combo = self.cfg.get("pick_hotkey", ["end"])
        try:
            self._pick_hint_lbl.config(text=f"{_hotkey_display(combo)} = Pick starten")
        except Exception:
            pass

    # ──────────────────────────────────────────────────────────────────
    # Theme & Font Toggle
    # ──────────────────────────────────────────────────────────────────
    def _sync_attr_colors(self):
        ATTR_COLORS["Strength"]     = PAL["str_col"]
        ATTR_COLORS["Agility"]      = PAL["agi_col"]
        ATTR_COLORS["Intelligence"] = PAL["int_col"]
        ATTR_COLORS["Universal"]    = PAL["uni_col"]

    def toggle_theme(self):
        old_pal = dict(PAL)
        self._dark_mode = not self._dark_mode
        PAL.update(PAL_DARK if self._dark_mode else PAL_LIGHT)
        self._sync_attr_colors()
        color_map = {old_pal[k]: PAL[k] for k in PAL}
        self._retheme_widgets(self.root, color_map)
        self._setup_ttk_style()
        self._update_display_btns()
        self._rebuild_hero_grid()
        self._rebuild_preset_buttons()
        self._refresh_mode_buttons()
        self._refresh_item_set_btns()
        self._update_onoff_btn()
        self._refresh_res_display()
        self.cfg["dark_mode"] = self._dark_mode
        save_config(self.cfg)

    def _retheme_widgets(self, widget, color_map: dict[str,str]):
        for attr in ("bg","fg","highlightbackground","highlightcolor",
                     "activebackground","activeforeground","selectcolor","insertbackground"):
            try:
                cur = widget.cget(attr)
                if cur and cur.startswith("#") and cur.lower() in color_map:
                    widget.config(**{attr: color_map[cur.lower()]})
            except Exception:
                pass
        for child in widget.winfo_children():
            self._retheme_widgets(child, color_map)

    def toggle_font_scale(self):
        self._font_large = not self._font_large
        self._update_fonts()
        self._update_display_btns()
        self._rebuild_hero_grid()
        self._rebuild_preset_buttons()
        self.cfg["font_large"] = self._font_large
        save_config(self.cfg)
        self._fit_window()
        self.status_var.set(f"Schrift: {'Groß' if self._font_large else 'Normal'}")

    # ──────────────────────────────────────────────────────────────────
    # Style helpers
    # ──────────────────────────────────────────────────────────────────
    def _section(self, parent, title: str, row: int, hint: str = "",
                 expand: bool = False) -> tk.Frame:
        """Abschnitt: kleine Überschrift (links Titel, rechts Hotkey-Hinweis) + Karte."""
        wrapper = tk.Frame(parent, bg=PAL["bg"])
        wrapper.grid(row=row, column=0, sticky="nsew" if expand else "ew", pady=(0, 6))
        wrapper.columnconfigure(0, weight=1)
        if expand:
            wrapper.rowconfigure(1, weight=1)

        header = tk.Frame(wrapper, bg=PAL["bg"])
        header.grid(row=0, column=0, sticky="ew", pady=(0, 2))
        header.columnconfigure(1, weight=1)
        tk.Label(header, text=title, bg=PAL["bg"], fg=PAL["accent"],
                 font=self._fonts["section"], anchor="w").grid(row=0, column=0, sticky="w")
        self._last_section_hint = tk.Label(header, text=hint, bg=PAL["bg"], fg=PAL["text_dim"],
                                           font=self._fonts["small"], anchor="e")
        self._last_section_hint.grid(row=0, column=1, sticky="e")

        content = tk.Frame(wrapper, bg=PAL["surface"], padx=6, pady=6,
                           highlightthickness=1, highlightbackground=PAL["separator"])
        content.grid(row=1, column=0, sticky="nsew")
        content.columnconfigure(0, weight=1)
        return content

    def _btn(self, parent, text: str, command, accent: bool = False) -> tk.Button:
        return tk.Button(parent, text=text, command=command,
                         bg=PAL["accent"] if accent else PAL["btn_bg"],
                         fg=PAL["on_accent"] if accent else PAL["text"],
                         activebackground=PAL["accent"], activeforeground=PAL["on_accent"],
                         relief="flat", bd=0, cursor="hand2",
                         font=self._fonts["ui_bold" if accent else "ui"],
                         padx=6, pady=5, highlightthickness=0)

    def _small_btn(self, parent, text: str, command) -> tk.Button:
        return tk.Button(parent, text=text, command=command,
                         bg=PAL["btn_bg"], fg=PAL["text"],
                         activebackground=PAL["accent"], activeforeground=PAL["on_accent"],
                         relief="flat", bd=0, cursor="hand2",
                         font=self._fonts["small"], padx=6, pady=2, highlightthickness=0)

    def _toggle_btn(self, parent, command) -> tk.Button:
        return tk.Button(parent, text="", command=command,
                         relief="flat", bd=0, cursor="hand2",
                         font=self._fonts["small_bold"], padx=6, pady=3, highlightthickness=0)

    # ──────────────────────────────────────────────────────────────────
    # Hero Grid
    # ──────────────────────────────────────────────────────────────────
    def _rebuild_hero_grid(self):
        for w in self.hero_frame.winfo_children():
            w.destroy()
        self.hero_buttons.clear()

        heroes      = _build_heroes(self.cfg.get("hero_pool",[]), self.cfg.get("custom_heroes",[]))
        current_row = 0

        for attr in ATTR_ORDER:
            attr_heroes = heroes.get(attr, [])
            if not attr_heroes:
                continue
            color = ATTR_COLORS[attr]
            tk.Label(self.hero_frame, text=f"■ {ATTR_DE[attr].upper()}",
                     bg=PAL["surface"], fg=color, font=self._fonts["section"], anchor="w"
                     ).grid(row=current_row, column=0, columnspan=HERO_COLS, sticky="ew",
                            pady=(0 if current_row == 0 else 6, 2))
            current_row += 1

            for i, (code, name) in enumerate(attr_heroes):
                btn = tk.Button(self.hero_frame, text=code,
                                command=lambda k=code: self.toggle_hero(k),
                                activebackground=color, activeforeground=PAL["on_accent"],
                                relief="flat", bd=0, cursor="hand2",
                                padx=2, pady=3, highlightthickness=0)
                btn.grid(row=current_row + i // HERO_COLS, column=i % HERO_COLS,
                         sticky="ew", padx=1, pady=1)
                self.hero_buttons[code] = btn

            current_row += (len(attr_heroes) + HERO_COLS - 1) // HERO_COLS

        for code in list(self.selected_heroes):
            if code not in self.hero_buttons:
                self.selected_heroes.remove(code)
        self._update_selected_label()

    def _refresh_hero_buttons(self):
        """Ausgewählte Helden hervorheben und mit ihrer Pick-Reihenfolge beschriften."""
        order = {code: i + 1 for i, code in enumerate(self.selected_heroes)}
        for code, btn in self.hero_buttons.items():
            n = order.get(code)
            btn.configure(text=f"{n}·{code}" if n else code,
                          bg=PAL["accent"] if n else PAL["btn_bg"],
                          fg=PAL["on_accent"] if n else PAL["text"],
                          font=self._fonts["hero_bold" if n else "hero"])

    def toggle_hero(self, hero_code: str):
        if hero_code in self.selected_heroes:
            self.selected_heroes.remove(hero_code)
        else:
            if len(self.selected_heroes) >= 8:
                self.status_var.set("Maximal 8 Helden — erst einen abwählen.")
                return
            self.selected_heroes.append(hero_code)
        self._update_selected_label()

    def clear_selection(self):
        self.selected_heroes = []
        self._update_selected_label()
        self.status_var.set("Auswahl geleert.")

    def _set_button_selected(self, hero_code: str, selected: bool):
        self._refresh_hero_buttons()

    def _update_selected_label(self):
        n = len(self.selected_heroes)
        if not n:
            self.selected_label.config(text="Auswahl 0/8 — Helden in Pick-Reihenfolge anklicken",
                                       fg=PAL["text_dim"], font=self._fonts["small"])
        else:
            self.selected_label.config(text=f"Auswahl {n}/8:  " + " → ".join(self.selected_heroes),
                                       fg=PAL["text"], font=self._fonts["ui_bold"])
        self._refresh_hero_buttons()

    # ──────────────────────────────────────────────────────────────────
    # 🎯 Hero-Pool-Manager  (komplette Held-Übersicht)
    # ──────────────────────────────────────────────────────────────────
    def open_hero_pool_manager(self):
        win = tk.Toplevel(self.root)
        win.title("Held-Pool verwalten")
        win.configure(bg=PAL["bg"])
        win.grab_set()
        win.focus_force()
        win.columnconfigure(0, weight=1)
        win.rowconfigure(0, weight=1)
        _apply_icon(win)

        current_pool = set(self.cfg.get("hero_pool", []))
        selected_set = set(self.selected_heroes)

        # ── Scrollbereich
        outer = tk.Frame(win, bg=PAL["bg"])
        outer.grid(row=0, column=0, sticky="nsew", padx=8, pady=8)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=PAL["bg"], highlightthickness=0)
        scrollbar = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=scrollbar.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        scrollbar.grid(row=0, column=1, sticky="ns")

        inner = tk.Frame(canvas, bg=PAL["bg"])
        canvas_window = canvas.create_window((0,0), window=inner, anchor="nw")
        inner.columnconfigure(0, weight=1)

        def _on_resize(evt):
            canvas.itemconfig(canvas_window, width=evt.width)
        canvas.bind("<Configure>", _on_resize)
        inner.bind("<Configure>", lambda e: canvas.configure(scrollregion=canvas.bbox("all")))

        # Mausrad-Scroll
        def _on_mousewheel(evt):
            canvas.yview_scroll(int(-1*(evt.delta/120)), "units")
        canvas.bind_all("<MouseWheel>", _on_mousewheel)

        # checkboxes: code → BooleanVar
        check_vars: dict[str, tk.BooleanVar] = {}

        for attr_idx, attr in enumerate(ATTR_ORDER):
            all_in_attr = ALL_HEROES_MASTER.get(attr, [])
            custom_in_attr = [(e["code"], e.get("name","")) for e in self.cfg.get("custom_heroes",[]) if e.get("attr")==attr]
            all_heroes_here = all_in_attr + custom_in_attr
            if not all_heroes_here:
                continue

            color   = ATTR_COLORS[attr]
            top_pad = 8 if attr_idx > 0 else 0

            # Attribut-Header mit Alle/Keine-Buttons
            hdr = tk.Frame(inner, bg=PAL["surface2"])
            hdr.grid(row=attr_idx*2, column=0, sticky="ew", pady=(top_pad,2))
            hdr.columnconfigure(0, weight=1)
            tk.Label(hdr, text=f"  {ATTR_ICONS[attr]}  {attr.upper()}  ({ATTR_DE[attr]})",
                     bg=PAL["surface2"], fg=color, font=self._fonts["section"], anchor="w", padx=4, pady=3
                     ).grid(row=0, column=0, sticky="w")

            def make_select_all(code_list, val):
                def _cmd():
                    for c in code_list:
                        if c in check_vars:
                            check_vars[c].set(val)
                return _cmd

            codes_in_attr = [c for c, _ in all_heroes_here]
            btn_all  = tk.Button(hdr, text="Alle",  command=make_select_all(codes_in_attr, True),
                                 bg=PAL["surface2"], fg=PAL["success"], relief="flat", bd=0,
                                 font=self._fonts["small"], padx=6, pady=2, cursor="hand2")
            btn_all.grid(row=0, column=1, padx=4)
            btn_none = tk.Button(hdr, text="Keine", command=make_select_all(codes_in_attr, False),
                                 bg=PAL["surface2"], fg=PAL["danger"], relief="flat", bd=0,
                                 font=self._fonts["small"], padx=6, pady=2, cursor="hand2")
            btn_none.grid(row=0, column=2, padx=(0,4))

            # Hero-Checkboxes in Raster
            grid_frame = tk.Frame(inner, bg=PAL["surface"])
            grid_frame.grid(row=attr_idx*2+1, column=0, sticky="ew", padx=0, pady=0)
            COLS = 6
            for c in range(COLS):
                grid_frame.columnconfigure(c, weight=1)

            for i, (code, name) in enumerate(all_heroes_here):
                r = i // COLS
                c = i % COLS
                var = tk.BooleanVar(value=code in current_pool)
                check_vars[code] = var

                # Farbe basierend auf Status
                in_sel   = code in selected_set
                in_pool  = code in current_pool

                cell_bg = PAL["surface"]
                lbl_color = PAL["accent"] if in_sel else color if in_pool else PAL["text_dim"]

                cell = tk.Frame(grid_frame, bg=cell_bg)
                cell.grid(row=r, column=c, sticky="ew", padx=1, pady=1)
                cell.columnconfigure(0, weight=1)

                cb = tk.Checkbutton(cell, text=code, variable=var,
                                    bg=cell_bg, fg=lbl_color,
                                    selectcolor=PAL["input_bg"],
                                    activebackground=cell_bg, activeforeground=color,
                                    font=self._fonts["mono"], anchor="w",
                                    relief="flat", bd=0, cursor="hand2",
                                    highlightthickness=0)
                cb.grid(row=0, column=0, sticky="ew", padx=2)

                # Tooltip: voller Name
                if name:
                    tip_lbl = tk.Label(cell, text=name, bg=cell_bg, fg=PAL["text_dim"],
                                       font=self._fonts["small"], anchor="w")
                    tip_lbl.grid(row=1, column=0, sticky="ew", padx=2, pady=(0,1))

                # Markierung: in Auswahl = Akzentfarbe border
                if in_sel:
                    cell.config(highlightbackground=PAL["accent"], highlightthickness=1)

        # ── Legende
        legend = tk.Frame(win, bg=PAL["surface"], padx=8, pady=4)
        legend.grid(row=1, column=0, sticky="ew", padx=8, pady=(0,4))
        tk.Label(legend, text="☑ = im Pool (sichtbar im Picker)  |  ",
                 bg=PAL["surface"], fg=PAL["text_dim"], font=self._fonts["small"]).pack(side="left")
        tk.Label(legend, text="Akzentfarbe = aktuell in Auswahl",
                 bg=PAL["surface"], fg=PAL["accent"], font=self._fonts["small"]).pack(side="left")

        # ── Buttons
        btn_row = tk.Frame(win, bg=PAL["bg"])
        btn_row.grid(row=2, column=0, sticky="ew", padx=8, pady=(0,8))
        btn_row.columnconfigure((0,1,2), weight=1)

        def do_apply():
            new_pool = [code for code, var in check_vars.items() if var.get()]
            self.cfg["hero_pool"] = new_pool
            save_config(self.cfg)
            self._rebuild_hero_grid()
            self.status_var.set(f"Pool gespeichert: {len(new_pool)} Helden aktiv.")
            win.destroy()

        def do_reset():
            for code, var in check_vars.items():
                var.set(code in _DEFAULT_POOL)

        tk.Button(btn_row, text="✔  Speichern & Schliessen",
                  command=do_apply,
                  bg=PAL["accent"], fg=PAL["on_accent"],
                  activebackground=PAL["success"], activeforeground=PAL["on_accent"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["big_bold"], padx=6, pady=6, highlightthickness=0
                  ).grid(row=0, column=0, sticky="ew", padx=(0,4))
        tk.Button(btn_row, text="Standard",
                  command=do_reset,
                  bg=PAL["btn_bg"], fg=PAL["text"],
                  activebackground=PAL["separator"], activeforeground=PAL["text"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["ui"], padx=6, pady=6, highlightthickness=0
                  ).grid(row=0, column=1, sticky="ew", padx=4)
        tk.Button(btn_row, text="Abbrechen",
                  command=win.destroy,
                  bg=PAL["btn_bg"], fg=PAL["text"],
                  activebackground=PAL["separator"], activeforeground=PAL["text"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["ui"], padx=6, pady=6, highlightthickness=0
                  ).grid(row=0, column=2, sticky="ew", padx=(4,0))

        win.update_idletasks()
        win.geometry("560x680")
        rx = self.root.winfo_x() + self.root.winfo_width()//2  - 280
        ry = self.root.winfo_y() + self.root.winfo_height()//2 - 340
        win.geometry(f"+{max(0,rx)}+{max(0,ry)}")

    # ──────────────────────────────────────────────────────────────────
    # Presets
    # ──────────────────────────────────────────────────────────────────
    def _rebuild_preset_buttons(self):
        for w in self.preset_btn_frame.winfo_children():
            w.destroy()
        if hasattr(self, "_preset_extra_frame"):
            for w in self._preset_extra_frame.winfo_children():
                w.destroy()

        presets    = self.cfg.get("presets", {})
        startup    = self.cfg.get("startup_preset", "")
        edit_mode  = getattr(self, "_preset_edit_mode", False)

        if not presets:
            tk.Label(self.preset_btn_frame, text="Noch keine Presets — Helden wählen, dann „＋ speichern“.",
                     bg=PAL["surface"], fg=PAL["text_dim"],
                     font=self._fonts["small"], anchor="w"
                     ).grid(row=0, column=0, sticky="w", padx=4)
            return

        all_names = list(presets.keys())
        pinned    = [n for n in self.cfg.get("pinned_presets", []) if n in presets]
        unpinned  = [n for n in all_names if n not in pinned]

        def _toggle_startup(name: str):
            if self.cfg.get("startup_preset") == name:
                self.cfg["startup_preset"] = ""
                self.status_var.set("Startup-Preset entfernt.")
            else:
                self.cfg["startup_preset"] = name
                self.status_var.set(f"⭐ Startup: '{name}' — wird beim nächsten Start geladen.")
            save_config(self.cfg)
            self._rebuild_preset_buttons()

        def _delete(name: str):
            if not messagebox.askyesno("Preset löschen", f"Preset '{name}' wirklich löschen?",
                                       parent=self.root):
                return
            self.cfg["presets"].pop(name, None)
            if self.cfg.get("startup_preset") == name:
                self.cfg["startup_preset"] = ""
            self.cfg["pinned_presets"] = [n for n in self.cfg.get("pinned_presets", []) if n != name]
            save_config(self.cfg)
            self._rebuild_preset_buttons()
            self.status_var.set(f"Preset '{name}' gelöscht.")

        def _make_btn(parent, name, idx):
            is_startup = (name == startup)
            cell = tk.Frame(parent, bg=PAL["surface"])
            cell.grid(row=idx // 3, column=idx % 3, sticky="ew",
                      padx=(0 if idx % 3 == 0 else 2, 0 if idx % 3 == 2 else 2), pady=(0, 3))
            cell.columnconfigure(0, weight=1)
            tk.Button(cell, text=("★ " if is_startup else "") + name,
                      command=lambda n=name: self.load_preset(n),
                      bg=PAL["btn_bg"], fg=PAL["int_col"],
                      activebackground=PAL["int_col"], activeforeground=PAL["on_accent"],
                      relief="flat", bd=0, cursor="hand2",
                      font=self._fonts["small_bold"], padx=4, pady=3, highlightthickness=0,
                      ).grid(row=0, column=0, sticky="ew")
            if edit_mode:
                for col, (txt, fg, cmd) in enumerate((
                    ("★" if is_startup else "☆", "#d9a400" if is_startup else PAL["text_dim"],
                     lambda n=name: _toggle_startup(n)),
                    ("✕", PAL["danger"], lambda n=name: _delete(n)),
                ), start=1):
                    tk.Button(cell, text=txt, command=cmd, bg=PAL["btn_bg"], fg=fg,
                              activebackground=PAL["hover"], activeforeground=fg,
                              relief="flat", bd=0, cursor="hand2",
                              font=self._fonts["small_bold"], padx=4, pady=3, highlightthickness=0,
                              ).grid(row=0, column=col, sticky="ns", padx=(1, 0))

        for parent in (self.preset_btn_frame, self._preset_extra_frame):
            parent.columnconfigure((0, 1, 2), weight=1, uniform="preset")

        # Gepinnte → immer sichtbar (bis zu 3), Rest → aufklappbar
        visible = pinned[:3] if pinned else all_names[:3]
        rest    = unpinned if pinned else all_names[3:]
        for i, name in enumerate(visible):
            _make_btn(self.preset_btn_frame, name, i)
        for i, name in enumerate(rest):
            _make_btn(self._preset_extra_frame, name, i)

    def open_preset_pin_manager(self):
        """Dialog zum Auswählen welche 3 Presets fest angezeigt werden."""
        presets = self.cfg.get("presets", {})
        if not presets:
            self.status_var.set("Noch keine Presets vorhanden.")
            return

        win = tk.Toplevel(self.root)
        win.title("Feste Presets auswählen")
        win.configure(bg=PAL["bg"])
        win.resizable(False, False)
        win.grab_set()
        win.focus_force()
        win.columnconfigure(0, weight=1)
        _apply_icon(win)

        frm = tk.Frame(win, bg=PAL["surface"], padx=12, pady=10)
        frm.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 4))
        frm.columnconfigure(0, weight=1)

        tk.Label(frm, text="Wähle bis zu 3 Presets die immer sichtbar sind:",
                 bg=PAL["surface"], fg=PAL["text_dim"],
                 font=self._fonts["ui"], anchor="w", wraplength=280
                 ).grid(row=0, column=0, sticky="w", pady=(0, 8))

        pinned = list(self.cfg.get("pinned_presets", []))
        check_vars: dict[str, tk.BooleanVar] = {}
        fb_var = tk.StringVar()

        for i, name in enumerate(presets.keys()):
            var = tk.BooleanVar(value=name in pinned)
            check_vars[name] = var

            row_bg = PAL["surface"] if i % 2 == 0 else PAL["btn_bg"]
            cell   = tk.Frame(frm, bg=row_bg)
            cell.grid(row=i+1, column=0, sticky="ew", pady=1)
            cell.columnconfigure(1, weight=1)

            cb = tk.Checkbutton(cell, variable=var,
                                bg=row_bg, selectcolor=PAL["input_bg"],
                                activebackground=row_bg,
                                relief="flat", bd=0, cursor="hand2",
                                highlightthickness=0)
            cb.grid(row=0, column=0, padx=(4, 2))

            tk.Label(cell, text=name,
                     bg=row_bg, fg=PAL["accent"],
                     font=self._fonts["mono"], anchor="w"
                     ).grid(row=0, column=1, sticky="w", pady=3)

            heroes = "  /  ".join(self.cfg["presets"].get(name, [])[:4])
            tk.Label(cell, text=heroes,
                     bg=row_bg, fg=PAL["text_dim"],
                     font=self._fonts["small"], anchor="w"
                     ).grid(row=0, column=2, sticky="w", padx=(6, 4))

        # Feedback
        tk.Label(frm, textvariable=fb_var,
                 bg=PAL["surface"], fg=PAL["danger"],
                 font=self._fonts["small"], anchor="w"
                 ).grid(row=len(presets)+1, column=0, sticky="w", pady=(6, 0))

        btn_row = tk.Frame(win, bg=PAL["bg"])
        btn_row.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        btn_row.columnconfigure((0, 1), weight=1)

        def do_save():
            selected = [n for n, v in check_vars.items() if v.get()]
            if len(selected) > 3:
                fb_var.set(f"Maximal 3 Presets auswählen (aktuell: {len(selected)})")
                return
            self.cfg["pinned_presets"] = selected
            save_config(self.cfg)
            self._rebuild_preset_buttons()
            self.status_var.set(f"Feste Presets: {', '.join(selected) if selected else '–'}")
            win.destroy()

        tk.Button(btn_row, text="✔  Speichern", command=do_save,
                  bg=PAL["accent"], fg=PAL["on_accent"],
                  activebackground=PAL["success"], activeforeground=PAL["on_accent"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["big_bold"], padx=6, pady=5, highlightthickness=0
                  ).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        tk.Button(btn_row, text="Abbrechen", command=win.destroy,
                  bg=PAL["btn_bg"], fg=PAL["text"],
                  activebackground=PAL["separator"], activeforeground=PAL["text"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["ui"], padx=6, pady=5, highlightthickness=0
                  ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        win.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()//2  - win.winfo_width()//2
        ry = self.root.winfo_y() + self.root.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{max(0,rx)}+{max(0,ry)}")

    def load_preset(self, name: str):
        heroes = self.cfg.get("presets",{}).get(name,[])
        if not heroes:
            self.status_var.set(f"Preset '{name}' leer.")
            return
        for code in list(self.selected_heroes):
            self._set_button_selected(code, False)
        self.selected_heroes = []
        for code in heroes:
            if code in self.hero_buttons:
                self.selected_heroes.append(code)
                self._set_button_selected(code, True)
        self._update_selected_label()
        self.status_var.set(f"Preset '{name}' geladen: {', '.join(self.selected_heroes)}")

    def save_preset_dialog(self):
        if not self.selected_heroes:
            self.status_var.set("Keine Helden ausgewaehlt.")
            return
        win = tk.Toplevel(self.root)
        win.title("Preset speichern")
        win.configure(bg=PAL["bg"])
        win.resizable(False, False)
        win.grab_set()
        win.focus_force()
        win.columnconfigure(0, weight=1)
        _apply_icon(win)

        frm = tk.Frame(win, bg=PAL["surface"], padx=12, pady=10)
        frm.grid(row=0, column=0, sticky="ew", padx=10, pady=10)
        frm.columnconfigure(1, weight=1)

        tk.Label(frm, text="Auswahl:", bg=PAL["surface"], fg=PAL["text_dim"], font=self._fonts["small"]
                 ).grid(row=0, column=0, columnspan=2, sticky="w")
        tk.Label(frm, text="  /  ".join(self.selected_heroes),
                 bg=PAL["surface"], fg=PAL["accent"], font=self._fonts["mono"]
                 ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(0,8))

        tk.Label(frm, text="Preset-Name:", bg=PAL["surface"], fg=PAL["text"], font=self._fonts["ui"]
                 ).grid(row=2, column=0, sticky="w", padx=(0,8))
        name_var = tk.StringVar()
        entry = tk.Entry(frm, textvariable=name_var, bg=PAL["input_bg"], fg=PAL["text"],
                         insertbackground=PAL["accent"], relief="flat", bd=0, font=self._fonts["mono"],
                         highlightthickness=1, highlightbackground=PAL["separator"],
                         highlightcolor=PAL["accent"])
        entry.grid(row=2, column=1, sticky="ew", pady=2)
        entry.focus_set()

        fb_var = tk.StringVar()
        tk.Label(frm, textvariable=fb_var, bg=PAL["surface"], fg=PAL["success"], font=self._fonts["ui"]
                 ).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(6,0))

        def do_save(evt=None):
            pname = name_var.get().strip()
            if not pname:
                fb_var.set("Name darf nicht leer sein.")
                return
            self.cfg.setdefault("presets",{})[pname] = list(self.selected_heroes)
            save_config(self.cfg)
            self._rebuild_preset_buttons()
            self.status_var.set(f"Preset '{pname}' gespeichert.")
            win.destroy()

        entry.bind("<Return>", do_save)

        presets = self.cfg.get("presets",{})
        if presets:
            tk.Frame(frm, bg=PAL["separator"], height=1
                     ).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(10,4))
            tk.Label(frm, text="Vorhandene Presets:",
                     bg=PAL["surface"], fg=PAL["text_dim"], font=self._fonts["ui_bold"], anchor="w"
                     ).grid(row=5, column=0, columnspan=2, sticky="w", pady=(0,3))
            for pi, (pname, phlist) in enumerate(list(presets.items())):
                prow = 6+pi
                tk.Label(frm, text=pname, bg=PAL["surface"], fg=PAL["accent"],
                         font=self._fonts["mono"], anchor="w").grid(row=prow, column=0, sticky="w")
                del_row = tk.Frame(frm, bg=PAL["surface"])
                del_row.grid(row=prow, column=1, sticky="ew")
                def make_del(n=pname):
                    def _d():
                        self.cfg["presets"].pop(n, None)
                        save_config(self.cfg)
                        self._rebuild_preset_buttons()
                        win.destroy()
                    return _d
                tk.Button(del_row, text="X", command=make_del(),
                          bg=PAL["surface"], fg=PAL["danger"],
                          activebackground=PAL["danger"], activeforeground=PAL["on_accent"],
                          relief="flat", bd=0, cursor="hand2", font=self._fonts["ui_bold"],
                          padx=6, pady=2).pack(side="right")
                tk.Label(del_row, text="  /  ".join(phlist), bg=PAL["surface"],
                         fg=PAL["text_dim"], font=self._fonts["small"]).pack(side="left")

        btn_row = tk.Frame(frm, bg=PAL["surface"])
        btn_row.grid(row=100, column=0, columnspan=2, sticky="ew", pady=(10,0))
        btn_row.columnconfigure((0,1), weight=1)
        tk.Button(btn_row, text="Speichern", command=do_save,
                  bg=PAL["accent"], fg=PAL["on_accent"], activebackground=PAL["success"],
                  relief="flat", bd=0, cursor="hand2", font=self._fonts["big_bold"],
                  padx=6, pady=5, highlightthickness=0).grid(row=0,column=0,sticky="ew",padx=(0,4))
        tk.Button(btn_row, text="Abbrechen", command=win.destroy,
                  bg=PAL["btn_bg"], fg=PAL["text"], activebackground=PAL["separator"],
                  relief="flat", bd=0, cursor="hand2", font=self._fonts["ui"],
                  padx=6, pady=5, highlightthickness=0).grid(row=0,column=1,sticky="ew",padx=(4,0))

        win.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()//2  - win.winfo_width()//2
        ry = self.root.winfo_y() + self.root.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{max(0,rx)}+{max(0,ry)}")

    # ──────────────────────────────────────────────────────────────────
    # Timing & Hotkey Dialog
    # ──────────────────────────────────────────────────────────────────
    def open_timing_config(self):
        win = tk.Toplevel(self.root)
        win.title("Zeiten & Hotkey")
        win.configure(bg=PAL["bg"])
        win.resizable(False, False)
        win.grab_set()
        win.focus_force()
        win.columnconfigure(0, weight=1)
        _apply_icon(win)

        t = self.cfg.get("timings", {})

        def section_lbl(parent, text, row):
            f = tk.Frame(parent, bg=PAL["surface2"])
            f.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(6,2))
            tk.Label(f, text=f"  {text}", bg=PAL["surface2"], fg=PAL["accent"],
                     font=self._fonts["section"], anchor="w", padx=4, pady=2).pack(fill="x")

        frm = tk.Frame(win, bg=PAL["surface"], padx=10, pady=6)
        frm.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,4))
        frm.columnconfigure(1, weight=1)

        timing_fields: dict[str, tk.StringVar] = {}
        TIMING_ROWS = [
            ("SPIELAUFLÖSUNG", None, None),
            ("Spiel Breite",        "game_res_w",          "px  z.B. 1920"),
            ("Spiel Höhe",          "game_res_h",          "px  z.B. 1200"),
            ("PICK-ABLAUF", None, None),
            ("Feld-Klick Pause",    "field_click_delay",   "s  Pause zwischen 2x Klick aufs Suchfeld"),
            ("Tippdauer (gesamt)",  "type_duration",        "s  Budget fuer Namenseingabe"),
            ("Enter-Pause",         "enter_pause",          "s  Warten nach Enter"),
            ("Pick-Button Dauer",   "pick_duration",        "s  Klickzeit auf Pick-Button"),
            ("Pick-Klick-Intervall","pick_click_interval",  "s  Pause zwischen Pick-Klicks"),
            ("LOOP", None, None),
            ("Schleifenpause",      "loop_pause",           "s  Extra Pause nach jedem Helden"),
            ("PLANUNG Wartezeit",   "suchfeld_wait",        "s  Max. warten auf PLANUNG nach dem Pick"),
            ("DOPPEL-PICK (PHASE D)", None, None),
            ("Prüfdauer",           "doppel_watch",         "s  So lange nach dem Pick auf Doppel-Pick achten"),
        ]

        field_row = 0
        game_res = self.cfg.get("game_res", [1920, 1200])
        # Virtuelle timing-keys für Spielauflösung vorbelegen
        t = dict(self.cfg.get("timings", {}))
        t["game_res_w"] = str(game_res[0])
        t["game_res_h"] = str(game_res[1])
        for label, cfg_key, hint in TIMING_ROWS:
            if cfg_key is None:
                section_lbl(frm, label, field_row)
                field_row += 1
                continue
            tk.Label(frm, text=label, bg=PAL["surface"], fg=PAL["text"],
                     font=self._fonts["ui"], anchor="w"
                     ).grid(row=field_row, column=0, sticky="w", padx=(0,8), pady=2)
            var = tk.StringVar(value=str(t.get(cfg_key, DEFAULT_CONFIG["timings"].get(cfg_key,0))))
            timing_fields[cfg_key] = var
            entry_row = tk.Frame(frm, bg=PAL["surface"])
            entry_row.grid(row=field_row, column=1, sticky="ew", pady=2)
            tk.Entry(entry_row, textvariable=var, width=6,
                     bg=PAL["input_bg"], fg=PAL["accent"], insertbackground=PAL["accent"],
                     relief="flat", bd=0, font=self._fonts["mono"],
                     highlightthickness=1, highlightbackground=PAL["separator"],
                     highlightcolor=PAL["accent"], justify="right"
                     ).pack(side="left")
            tk.Label(entry_row, text=f"  {hint}", bg=PAL["surface"], fg=PAL["text_dim"],
                     font=self._fonts["small"], anchor="w").pack(side="left", padx=(4,0))
            field_row += 1

        # Hotkey-Bereich
        section_lbl(frm, "PICK-HOTKEY  (bis zu 3 Tasten)", field_row)
        field_row += 1

        current_combo = list(self.cfg.get("pick_hotkey",["end"]))
        recorded_keys: list[str] = []
        recording_active = [False]
        combo_var = tk.StringVar(value=_hotkey_display(current_combo))

        tk.Label(frm, text="Aktuell:", bg=PAL["surface"], fg=PAL["text_dim"],
                 font=self._fonts["ui"], anchor="w"
                 ).grid(row=field_row, column=0, sticky="w", pady=2)
        tk.Label(frm, textvariable=combo_var, bg=PAL["surface"], fg=PAL["accent"],
                 font=self._fonts["mono"], anchor="w"
                 ).grid(row=field_row, column=1, sticky="w", pady=2)
        field_row += 1

        rec_frame = tk.Frame(frm, bg=PAL["surface"])
        rec_frame.grid(row=field_row, column=0, columnspan=2, sticky="ew", pady=(4,2))
        field_row += 1

        rec_hint  = tk.StringVar(value="Klick 'Aufnehmen', dann bis zu 3 Tasten druecken.")
        tk.Label(rec_frame, textvariable=rec_hint, bg=PAL["surface"], fg=PAL["text_dim"],
                 font=self._fonts["small"], anchor="w", wraplength=240
                 ).pack(side="bottom", fill="x", pady=(2,0))

        rec_entry = tk.Entry(rec_frame, width=1, bg=PAL["surface"], fg=PAL["surface"],
                             insertbackground=PAL["surface"], relief="flat", bd=0, highlightthickness=0)
        rec_entry.pack(side="left")
        rec_btn_var = tk.StringVar(value="Aufnehmen")

        def start_recording():
            recorded_keys.clear()
            recording_active[0] = True
            rec_btn_var.set("Laeuft... (Esc=Abbruch)")
            rec_hint.set("Tasten druecken (bis zu 3). Esc = abbrechen.")
            combo_var.set("...")
            rec_entry.focus_set()

        def on_rec_key(evt):
            if not recording_active[0]: return
            if evt.keysym == "Escape":
                recording_active[0] = False
                rec_btn_var.set("Aufnehmen")
                combo_var.set(_hotkey_display(current_combo))
                rec_hint.set("Aufnahme abgebrochen.")
                return "break"
            ps = _TK_TO_PYNPUT.get(evt.keysym, evt.keysym.lower())
            if ps not in recorded_keys:
                recorded_keys.append(ps)
            combo_var.set(_hotkey_display(recorded_keys))
            if len(recorded_keys) >= 3:
                recording_active[0] = False
                rec_btn_var.set("Aufnehmen")
                rec_hint.set("Aufnahme fertig. 'Speichern' zum Uebernehmen.")
            return "break"

        rec_entry.bind("<KeyPress>", on_rec_key)
        tk.Button(rec_frame, textvariable=rec_btn_var, command=start_recording,
                  bg=PAL["btn_bg"], fg=PAL["text"],
                  activebackground=PAL["accent"], activeforeground=PAL["on_accent"],
                  relief="flat", bd=0, cursor="hand2", font=self._fonts["ui"],
                  padx=8, pady=4, highlightthickness=1, highlightbackground=PAL["separator"]
                  ).pack(side="left", padx=(0,8))

        tk.Frame(frm, bg=PAL["separator"], height=1
                 ).grid(row=field_row, column=0, columnspan=2, sticky="ew", pady=(10,4))
        field_row += 1

        fb_var = tk.StringVar()
        tk.Label(frm, textvariable=fb_var, bg=PAL["surface"], fg=PAL["success"],
                 font=self._fonts["ui"], anchor="w"
                 ).grid(row=field_row, column=0, columnspan=2, sticky="ew")
        field_row += 1

        btn_row = tk.Frame(frm, bg=PAL["surface"])
        btn_row.grid(row=field_row, column=0, columnspan=2, sticky="ew", pady=(4,0))
        btn_row.columnconfigure((0,1), weight=1)

        def do_save():
            new_timings = {}
            new_game_res = list(self.cfg.get("game_res", [1920, 1200]))
            for k, var in timing_fields.items():
                # Spielauflösung separat behandeln
                if k == "game_res_w":
                    try: new_game_res[0] = int(float(var.get()))
                    except: fb_var.set("Ungültige Spielbreite."); return
                    continue
                if k == "game_res_h":
                    try: new_game_res[1] = int(float(var.get()))
                    except: fb_var.set("Ungültige Spielhöhe."); return
                    continue
                try:
                    val = float(var.get().replace(",","."))
                    if val < 0: raise ValueError
                    new_timings[k] = val
                except ValueError:
                    fb_var.set(f"Ungueltig: '{k}' muss positive Zahl sein.")
                    return
            new_hotkey = list(recorded_keys) if recorded_keys else list(current_combo)
            if not new_hotkey:
                fb_var.set("Hotkey darf nicht leer sein.")
                return
            self.cfg["timings"]     = new_timings
            self.cfg["pick_hotkey"] = new_hotkey
            self.cfg["game_res"]    = new_game_res
            save_config(self.cfg)
            self._update_hotkey_hint()
            self.status_var.set(f"Gespeichert.  Pick = {_hotkey_display(new_hotkey)}")
            fb_var.set("Gespeichert!")
            win.after(800, win.destroy)

        tk.Button(btn_row, text="Speichern", command=do_save,
                  bg=PAL["accent"], fg=PAL["on_accent"], activebackground=PAL["success"],
                  relief="flat", bd=0, cursor="hand2", font=self._fonts["big_bold"],
                  padx=6, pady=5, highlightthickness=0
                  ).grid(row=0, column=0, sticky="ew", padx=(0,4))
        tk.Button(btn_row, text="Abbrechen", command=win.destroy,
                  bg=PAL["btn_bg"], fg=PAL["text"], activebackground=PAL["separator"],
                  relief="flat", bd=0, cursor="hand2", font=self._fonts["ui"],
                  padx=6, pady=5, highlightthickness=0
                  ).grid(row=0, column=1, sticky="ew", padx=(4,0))

        win.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()//2  - win.winfo_width()//2
        ry = self.root.winfo_y() + self.root.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{max(0,rx)}+{max(0,ry)}")

    # ──────────────────────────────────────────────────────────────────
    # Hero Manager (eigene Helden hinzufügen/entfernen)
    # ──────────────────────────────────────────────────────────────────
    def open_hero_manager(self):
        win = tk.Toplevel(self.root)
        win.title("Eigene Helden")
        win.configure(bg=PAL["bg"])
        win.resizable(False, False)
        win.grab_set()
        win.focus_force()
        win.columnconfigure(0, weight=1)
        _apply_icon(win)

        frm = tk.Frame(win, bg=PAL["surface"], padx=10, pady=8)
        frm.grid(row=0, column=0, sticky="ew", padx=10, pady=(10,4))
        frm.columnconfigure(1, weight=1)

        def lbl(row, text):
            tk.Label(frm, text=text, bg=PAL["surface"], fg=PAL["text_dim"],
                     font=self._fonts["ui"], anchor="w"
                     ).grid(row=row, column=0, sticky="w", pady=2, padx=(0,8))

        def inp(row):
            e = tk.Entry(frm, bg=PAL["input_bg"], fg=PAL["text"],
                         insertbackground=PAL["accent"], relief="flat", bd=0,
                         font=self._fonts["mono"], highlightthickness=1,
                         highlightbackground=PAL["separator"], highlightcolor=PAL["accent"])
            e.grid(row=row, column=1, sticky="ew", pady=2)
            return e

        lbl(0, "Kuerzel (Tipp-Text)*")
        e_code = inp(0)
        tk.Label(frm, text="Dieser Text wird im Spiel eingetippt (z.B. cm)",
                 bg=PAL["surface"], fg=PAL["text_dim"], font=self._fonts["small"], anchor="w"
                 ).grid(row=1, column=1, sticky="w", pady=(0,5))

        lbl(2, "Anzeigename")
        e_name = inp(2)
        tk.Label(frm, text="Lesbarer Name (z.B. Crystal Maiden) — optional",
                 bg=PAL["surface"], fg=PAL["text_dim"], font=self._fonts["small"], anchor="w"
                 ).grid(row=3, column=1, sticky="w", pady=(0,5))

        lbl(4, "Kategorie")
        attr_var = tk.StringVar(value="Intelligence")
        rb_row = tk.Frame(frm, bg=PAL["surface"])
        rb_row.grid(row=4, column=1, sticky="w", pady=2)
        for attr in ATTR_ORDER:
            tk.Radiobutton(rb_row, text=attr, variable=attr_var, value=attr,
                           bg=PAL["surface"], fg=ATTR_COLORS[attr],
                           selectcolor=PAL["input_bg"],
                           activebackground=PAL["surface"], activeforeground=ATTR_COLORS[attr],
                           font=self._fonts["ui"], bd=0, cursor="hand2"
                           ).pack(side="left", padx=(0,10))

        fb_var = tk.StringVar()
        tk.Label(frm, textvariable=fb_var, bg=PAL["surface"], fg=PAL["success"],
                 font=self._fonts["ui"], anchor="w"
                 ).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6,0))

        def do_add():
            code = e_code.get().strip().lower()
            name = e_name.get().strip()
            attr = attr_var.get()
            if not code:
                fb_var.set("Kuerzel darf nicht leer sein.")
                return
            heroes = _build_heroes(self.cfg.get("hero_pool",[]), self.cfg.get("custom_heroes",[]))
            all_codes = [c for lst in heroes.values() for c, _ in lst]
            # Also check master list
            master_codes = [c for lst in ALL_HEROES_MASTER.values() for c, _ in lst]
            if code in all_codes or code in master_codes:
                fb_var.set(f"'{code}' ist bereits vorhanden.")
                return
            self.cfg.setdefault("custom_heroes",[]).append({"code":code,"name":name or code,"attr":attr})
            # Auch zum Pool hinzufuegen
            self.cfg.setdefault("hero_pool",[]).append(code)
            save_config(self.cfg)
            self._rebuild_hero_grid()
            _refresh_list()
            e_code.delete(0,"end")
            e_name.delete(0,"end")
            fb_var.set(f"'{code}' ({attr}) hinzugefuegt.")
            self.status_var.set(f"Held '{code}' hinzugefuegt.")

        tk.Button(frm, text="  Held hinzufuegen  ", command=do_add,
                  bg=PAL["accent"], fg=PAL["on_accent"],
                  activebackground=PAL["success"], activeforeground=PAL["on_accent"],
                  relief="flat", bd=0, cursor="hand2", font=self._fonts["big_bold"],
                  padx=6, pady=5, highlightthickness=0
                  ).grid(row=6, column=0, columnspan=2, sticky="ew", pady=(10,0))

        # Trennlinie
        tk.Frame(win, bg=PAL["separator"], height=1).grid(row=1, column=0, sticky="ew", padx=10, pady=6)

        tk.Label(win, text="  Eigene Helden  (X = loeschen)",
                 bg=PAL["bg"], fg=PAL["text_dim"],
                 font=self._fonts["ui_bold"], anchor="w"
                 ).grid(row=2, column=0, sticky="ew", padx=10)

        list_wrap = tk.Frame(win, bg=PAL["bg"])
        list_wrap.grid(row=3, column=0, sticky="nsew", padx=10, pady=(2,10))
        list_wrap.columnconfigure(0, weight=1)

        list_frame = tk.Frame(list_wrap, bg=PAL["surface"])
        list_frame.grid(row=0, column=0, sticky="ew")
        list_frame.columnconfigure(1, weight=1)

        def _refresh_list():
            for w in list_frame.winfo_children():
                w.destroy()
            custom = self.cfg.get("custom_heroes",[])
            if not custom:
                tk.Label(list_frame, text="  - noch keine eigenen Helden -",
                         bg=PAL["surface"], fg=PAL["text_dim"],
                         font=self._fonts["ui"], anchor="w", pady=5
                         ).grid(row=0, column=0, sticky="ew")
                return
            for ci, hdr_txt in enumerate(["Kuerzel","Name","Kategorie",""]):
                tk.Label(list_frame, text=hdr_txt, bg=PAL["surface2"], fg=PAL["text_dim"],
                         font=self._fonts["small"], anchor="w", padx=4, pady=2
                         ).grid(row=0, column=ci, sticky="ew")
            for i, entry in enumerate(custom):
                row = i+1
                bg    = PAL["surface"] if i%2==0 else PAL["btn_bg"]
                color = ATTR_COLORS.get(entry.get("attr","Universal"), PAL["text"])
                tk.Label(list_frame, text=entry.get("code",""), bg=bg, fg=PAL["accent"],
                         font=self._fonts["mono"], anchor="w", padx=4, pady=3
                         ).grid(row=row, column=0, sticky="ew")
                tk.Label(list_frame, text=entry.get("name",""), bg=bg, fg=PAL["text"],
                         font=self._fonts["ui"], anchor="w", padx=4
                         ).grid(row=row, column=1, sticky="ew")
                tk.Label(list_frame, text=entry.get("attr",""), bg=bg, fg=color,
                         font=self._fonts["small"], anchor="w", padx=4
                         ).grid(row=row, column=2, sticky="ew")
                def make_del(idx=i):
                    def _d():
                        removed_code = self.cfg["custom_heroes"][idx].get("code","")
                        self.cfg["custom_heroes"].pop(idx)
                        # Auch aus Pool entfernen
                        if removed_code in self.cfg.get("hero_pool",[]):
                            self.cfg["hero_pool"].remove(removed_code)
                        save_config(self.cfg)
                        self._rebuild_hero_grid()
                        _refresh_list()
                        self.status_var.set("Held geloescht.")
                    return _d
                tk.Button(list_frame, text="X", command=make_del(),
                          bg=bg, fg=PAL["danger"],
                          activebackground=PAL["danger"], activeforeground=PAL["on_accent"],
                          relief="flat", bd=0, cursor="hand2",
                          font=self._fonts["ui_bold"], padx=6, pady=2
                          ).grid(row=row, column=3, sticky="ew")

        _refresh_list()
        win.update_idletasks()
        rx = self.root.winfo_x() + self.root.winfo_width()//2  - win.winfo_width()//2
        ry = self.root.winfo_y() + self.root.winfo_height()//2 - win.winfo_height()//2
        win.geometry(f"+{max(0,rx)}+{max(0,ry)}")

    # ──────────────────────────────────────────────────────────────────
    # Bilderkennung
    # ──────────────────────────────────────────────────────────────────
    # ──────────────────────────────────────────────────────────────────
    # Item-Set Editor
    # ──────────────────────────────────────────────────────────────────
    def open_item_set_editor(self):
        """Öffnet den Editor für Item-Sets (3 Sets × 6 Items)."""
        win = tk.Toplevel(self.root)
        win.title("Item-Sets verwalten")
        win.configure(bg=PAL["bg"])
        win.grab_set()
        win.focus_force()
        win.columnconfigure(0, weight=1)
        win.rowconfigure(1, weight=1)
        _apply_icon(win)

        # Header
        hdr = tk.Frame(win, bg=PAL["surface2"])
        hdr.grid(row=0, column=0, sticky="ew")
        tk.Label(hdr, text="  🛒  Item-Sets  (bis zu 6 Items pro Set)",
                 bg=PAL["surface2"], fg=PAL["accent"],
                 font=self._fonts["section"], anchor="w", padx=6, pady=4
                 ).pack(fill="x")

        # Item-Phase aktivieren Toggle
        ip_frame = tk.Frame(win, bg=PAL["surface"], padx=8, pady=4)
        ip_frame.grid(row=0, column=0, sticky="ew", padx=10, pady=(8, 0))
        ip_var = tk.BooleanVar(value=self.cfg.get("item_phase_enabled", True))

        def _toggle_item_phase():
            self.cfg["item_phase_enabled"] = ip_var.get()
            save_config(self.cfg)
            self._update_onoff_btn()

        tk.Checkbutton(ip_frame, text="Phase C (Item-Kauf) aktiviert",
                       variable=ip_var, command=_toggle_item_phase,
                       bg=PAL["surface"], fg=PAL["text"],
                       selectcolor=PAL["input_bg"],
                       activebackground=PAL["surface"], activeforeground=PAL["accent"],
                       font=self._fonts["ui"], bd=0, cursor="hand2"
                       ).pack(side="left")

        # Notebook für 3 Sets
        style = ttk.Style()
        style.configure("Item.TNotebook", background=PAL["bg"], borderwidth=0)
        style.configure("Item.TNotebook.Tab",
                        background=PAL["btn_bg"], foreground=PAL["text_dim"],
                        padding=[8, 3], font=("Segoe UI", 7, "bold"))
        style.map("Item.TNotebook.Tab",
                  background=[("selected", PAL["surface2"])],
                  foreground=[("selected", PAL["accent"])])

        nb = ttk.Notebook(win, style="Item.TNotebook")
        nb.grid(row=1, column=0, sticky="nsew", padx=10, pady=8)

        item_sets   = self.cfg.get("item_sets", DEFAULT_CONFIG["item_sets"])
        name_vars:  list[tk.StringVar] = []
        label_vars: list[list[tk.StringVar]] = []

        for set_idx in range(6):
            s = item_sets[set_idx] if set_idx < len(item_sets) else {"name": f"Set {set_idx+1}", "items": []}
            tab = tk.Frame(nb, bg=PAL["surface"])
            tab.columnconfigure(1, weight=1)

            # Set-Name
            nm_var = tk.StringVar(value=s.get("name", f"Set {set_idx+1}"))
            name_vars.append(nm_var)
            tk.Label(tab, text="Set-Name:", bg=PAL["surface"], fg=PAL["text_dim"],
                     font=self._fonts["small"], anchor="w"
                     ).grid(row=0, column=0, sticky="w", padx=(6,4), pady=(6,4))
            tk.Entry(tab, textvariable=nm_var, bg=PAL["input_bg"], fg=PAL["text"],
                     insertbackground=PAL["accent"], relief="flat", bd=0,
                     font=self._fonts["mono"], highlightthickness=1,
                     highlightbackground=PAL["separator"], highlightcolor=PAL["accent"]
                     ).grid(row=0, column=1, sticky="ew", padx=(0,6), pady=(6,4))

            # Trennlinie
            tk.Frame(tab, bg=PAL["separator"], height=1
                     ).grid(row=1, column=0, columnspan=3, sticky="ew", padx=6, pady=(0,4))

            set_label_vars: list[tk.StringVar] = []
            items = s.get("items", [])

            default_labels = ["Boots", "Iron Branch", "Stick",
                              "Item 4", "Item 5", "Item 6"]

            for item_idx in range(6):
                item = items[item_idx] if item_idx < len(items) else {}
                lbl_var = tk.StringVar(value=item.get("label", default_labels[item_idx]))
                set_label_vars.append(lbl_var)

                item_path = DATA_DIR / item.get("file", _item_file(set_idx, item_idx))
                has_tmpl  = item_path.exists()
                row_bg    = PAL["surface"] if item_idx % 2 == 0 else PAL["btn_bg"]

                cell = tk.Frame(tab, bg=row_bg)
                cell.grid(row=2+item_idx, column=0, columnspan=3, sticky="ew", padx=4, pady=1)
                cell.columnconfigure(1, weight=1)

                tk.Label(cell, text=f"{item_idx+1}.",
                         bg=row_bg, fg=PAL["text_dim"],
                         font=self._fonts["small"], width=2, anchor="e"
                         ).grid(row=0, column=0, padx=(4,4))

                tk.Entry(cell, textvariable=lbl_var,
                         bg=row_bg, fg=PAL["text"],
                         insertbackground=PAL["accent"], relief="flat", bd=0,
                         font=self._fonts["mono"], highlightthickness=1,
                         highlightbackground=PAL["separator"],
                         highlightcolor=PAL["accent"]
                         ).grid(row=0, column=1, sticky="ew", padx=(0,4), pady=2)

                # Template-Status + Aufnahme-Button
                status_txt = "✔" if has_tmpl else "✗"
                status_fg  = PAL["success"] if has_tmpl else PAL["danger"]
                status_lbl = tk.Label(cell, text=status_txt,
                                      bg=row_bg, fg=status_fg,
                                      font=self._fonts["mono"], width=2)
                status_lbl.grid(row=0, column=2, padx=(0,2))

                def make_capture(si=set_idx, ii=item_idx, slbl=status_lbl):
                    def _capture():
                        tpath = DATA_DIR / _item_file(si, ii)
                        slbl.config(text="3s...", fg=PAL["accent"])
                        win.update_idletasks()
                        def _do():
                            time.sleep(3)
                            try:
                                self._capture_template(tpath, region_w=60, region_h=60)
                                self.root.after(0, lambda: slbl.config(text="✔", fg=PAL["success"]))
                            except Exception as e:
                                self.root.after(0, lambda err=e: slbl.config(
                                    text="✗", fg=PAL["danger"]))
                        threading.Thread(target=_do, daemon=True).start()
                    return _capture

                def make_delete(si=set_idx, ii=item_idx, slbl=status_lbl):
                    def _delete():
                        tpath = DATA_DIR / _item_file(si, ii)
                        try:
                            if tpath.exists():
                                tpath.unlink()
                            slbl.config(text="✗", fg=PAL["danger"])
                        except Exception:
                            pass
                    return _delete

                tk.Button(cell, text="📷",
                          command=make_capture(),
                          bg=row_bg, fg=PAL["int_col"],
                          relief="flat", bd=0, cursor="hand2",
                          font=self._fonts["small"], padx=4, pady=1,
                          highlightthickness=0
                          ).grid(row=0, column=3, padx=(0,2))

                tk.Button(cell, text="🗑",
                          command=make_delete(),
                          bg=row_bg, fg=PAL["danger"],
                          activebackground=PAL["danger"], activeforeground=PAL["on_accent"],
                          relief="flat", bd=0, cursor="hand2",
                          font=self._fonts["small"], padx=4, pady=1,
                          highlightthickness=0
                          ).grid(row=0, column=4, padx=(0,4))

            label_vars.append(set_label_vars)
            nb.add(tab, text=s.get("name", f"Set {set_idx+1}"))

        # Speichern
        fb_var = tk.StringVar()
        tk.Label(win, textvariable=fb_var, bg=PAL["bg"], fg=PAL["success"],
                 font=self._fonts["small"], anchor="w", padx=10
                 ).grid(row=2, column=0, sticky="ew", pady=(0,2))

        btn_row = tk.Frame(win, bg=PAL["bg"])
        btn_row.grid(row=3, column=0, sticky="ew", padx=10, pady=(0,10))
        btn_row.columnconfigure((0,1), weight=1)

        def do_save():
            sets = self.cfg.get("item_sets", [])
            while len(sets) < 6:
                sets.append({"name": f"Set {len(sets)+1}", "items": []})
            for si in range(6):
                sets[si]["name"] = name_vars[si].get().strip() or f"Set {si+1}"
                while len(sets[si]["items"]) < 6:
                    n = len(sets[si]["items"]) + 1
                    sets[si]["items"].append({"label": f"Item {n}",
                                              "file":  _item_file(si, n-1)})
                for ii in range(6):
                    sets[si]["items"][ii]["label"] = label_vars[si][ii].get().strip()
                # Tab-Text aktualisieren
                nb.tab(si, text=sets[si]["name"])
            self.cfg["item_sets"] = sets
            save_config(self.cfg)
            self._refresh_item_set_btns()
            fb_var.set("✔ Gespeichert!")

        tk.Button(btn_row, text="✔  Speichern", command=do_save,
                  bg=PAL["accent"], fg=PAL["on_accent"],
                  activebackground=PAL["success"], activeforeground=PAL["on_accent"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["big_bold"], padx=6, pady=5, highlightthickness=0
                  ).grid(row=0, column=0, sticky="ew", padx=(0,4))
        tk.Button(btn_row, text="Abbrechen", command=win.destroy,
                  bg=PAL["btn_bg"], fg=PAL["text"],
                  activebackground=PAL["separator"], activeforeground=PAL["text"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["ui"], padx=6, pady=5, highlightthickness=0
                  ).grid(row=0, column=1, sticky="ew", padx=(4,0))

        win.update_idletasks()
        win.geometry("460x600")
        rx = self.root.winfo_x() + self.root.winfo_width()//2  - 210
        ry = self.root.winfo_y() + self.root.winfo_height()//2 - 260
        win.geometry(f"+{max(0,rx)}+{max(0,ry)}")

    def import_templates(self):
        """
        Holt Templates (gterminal_*/skadi_*.png) und optional die alte Config aus
        einem anderen Ordner — z. B. dem früheren Gterminal-Ordner im Google Drive.
        """
        src = filedialog.askdirectory(parent=self.root,
                                      title="Ordner mit den alten Templates wählen (z. B. Dota2_Draft_Helfer_Maerz)")
        if not src:
            return
        src = Path(src)
        if src.resolve() == DATA_DIR.resolve():
            self.status_var.set("Das ist bereits der Datenordner.")
            return

        def _new_name(name: str) -> str:
            return _PREFIX + name[len(_LEGACY_PREFIX):] if name.startswith(_LEGACY_PREFIX + "_") else name

        files = [f for f in src.iterdir() if f.is_file()
                 and f.name.startswith((_LEGACY_PREFIX + "_", _PREFIX + "_"))
                 and "_debug" not in f.name]
        pngs  = [f for f in files if f.suffix.lower() == ".png"]
        cfgs  = sorted((f for f in files if f.name.endswith("_config.json")),
                       key=lambda f: not f.name.startswith(_PREFIX))   # skadi_ vor gterminal_
        if not pngs and not cfgs:
            self.status_var.set(f"Keine gterminal_*/skadi_*-Dateien in {src.name} gefunden.")
            return

        overwrite = True
        if any((DATA_DIR / _new_name(f.name)).exists() for f in pngs):
            overwrite = messagebox.askyesno("Templates ersetzen?",
                                            "Einige Templates gibt es hier schon.\nMit den importierten ersetzen?",
                                            parent=self.root)
        copied = 0
        for f in pngs:
            target = DATA_DIR / _new_name(f.name)
            if target.exists() and not overwrite:
                continue
            try:
                shutil.copy2(f, target)
                copied += 1
            except OSError:
                pass

        cfg_msg = ""
        if cfgs and messagebox.askyesno(
                "Einstellungen übernehmen?",
                f"In {src.name} liegt auch eine Config ({cfgs[0].name}).\n\n"
                "Presets, Item-Sets, Held-Pool und Zeiten übernehmen?\n"
                "(Die aktuellen Einstellungen werden ersetzt.)", parent=self.root):
            try:
                shutil.copy2(cfgs[0], CONFIG_PATH)
                self.cfg = load_config()
                self.cfg["dark_mode"]  = self._dark_mode       # Anzeige so lassen wie gerade
                self.cfg["font_large"] = self._font_large
                save_config(self.cfg)
                self._mode_var.set(self.cfg.get("pick_mode", "both"))
                self._refresh_mode_buttons()
                self._rebuild_hero_grid()
                self._rebuild_preset_buttons()
                self._refresh_item_set_btns()
                self._update_onoff_btn()
                self._update_hotkey_hint()
                cfg_msg = " + Einstellungen"
            except Exception as e:
                cfg_msg = f" (Config-Fehler: {e})"

        self._update_cfg_mode_label()
        self._fit_window()
        self.status_var.set(f"✔ {copied} Templates{cfg_msg} aus '{src.name}' importiert.")

    def test_doppel_check(self):
        """
        Startet nur Phase D (ohne Klicken/Tippen), damit man die
        Doppel-Pick-Erkennung gefahrlos ausprobieren kann:
        PLANUNG-Bildschirm zeigen → dann zurück zur Heldenauswahl wechseln.
        Abbruch mit BACKSPACE.
        """
        if not CV2_AVAILABLE:
            self.status_var.set("opencv nicht installiert — pip install opencv-python mss")
            return
        if self.pick_thread and self.pick_thread.is_alive():
            self.status_var.set("Pick-Macro läuft gerade — erst stoppen (BACKSPACE).")
            return
        if not (DOPPELT_TEMPLATE_PATH.exists() or
                (FIELD_TEMPLATE_PATH.exists() and PLANUNG_TEMPLATE_PATH.exists())):
            self.status_var.set("Für den Test fehlen Templates: Suchfeld + PLANUNG (oder Doppel-Pick).")
            return

        def _run():
            try:
                found = self._phase_d_duplicate_watch("TEST", use_img=True, force=True)
                if found:
                    self._ui_status("🧪 TEST: ✔ Doppel-Pick ERKANNT — im echten Ablauf würde jetzt neu gepickt.")
                elif self.stop_pick.is_set():
                    self._ui_status("🧪 TEST: abgebrochen.")
                else:
                    self._ui_status("🧪 TEST: kein Doppel-Pick erkannt (Zeit abgelaufen).")
            finally:
                _release_screen()

        self.stop_pick.clear()
        self.pick_thread = threading.Thread(target=_run, daemon=True)
        self.pick_thread.start()

    def test_image_recognition(self):
        """
        Testet beide Templates auf dem aktuellen Bildschirm,
        zeigt Match-Score und speichert ein Debug-Bild mit markiertem Treffer.
        """
        if not CV2_AVAILABLE:
            self.status_var.set("opencv nicht installiert — pip install opencv-python mss")
            return

        def _run():
            try:
                import mss
                with mss.mss() as sct:
                    mon = sct.monitors[1]
                    raw = sct.grab(mon)
                    screen_np = np.array(raw)

                screen_bgr = cv2.cvtColor(screen_np, cv2.COLOR_BGRA2BGR)
                screen_g   = cv2.cvtColor(screen_bgr, cv2.COLOR_BGR2GRAY)
                debug_img  = screen_bgr.copy()
                results    = []

                for tpath, label in (
                    (FIELD_TEMPLATE_PATH,   "Suchfeld"),
                    (AUSWAHL_TEMPLATE_PATH, "Auswählen"),
                    (PLANUNG_TEMPLATE_PATH, "Planung"),
                    (DOPPELT_TEMPLATE_PATH, "Doppel-Pick"),
                ):
                    if not tpath.exists():
                        results.append(f"{label}: ✗ Template fehlt")
                        continue

                    tmpl = cv2.imread(str(tpath), cv2.IMREAD_GRAYSCALE)
                    if tmpl is None:
                        results.append(f"{label}: ✗ Template nicht lesbar")
                        continue

                    sh, sw = screen_g.shape
                    th, tw = tmpl.shape
                    if th > sh or tw > sw:
                        results.append(f"{label}: ✗ Template ({tw}×{th}) > Screen ({sw}×{sh})")
                        continue

                    res = cv2.matchTemplate(screen_g, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, mv, _, ml = cv2.minMaxLoc(res)

                    if mv >= 0.65:
                        # Treffer einzeichnen
                        cx = ml[0] + tw // 2
                        cy = ml[1] + th // 2
                        cv2.rectangle(debug_img,
                                      (ml[0], ml[1]),
                                      (ml[0] + tw, ml[1] + th),
                                      (0, 255, 0), 3)
                        cv2.putText(debug_img, f"{label} {mv:.2f}",
                                    (ml[0], ml[1] - 8),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8,
                                    (0, 255, 0), 2)
                        results.append(f"{label}: ✔ {mv:.2f}  @  ({cx},{cy})")
                    else:
                        results.append(f"{label}: ✗ {mv:.2f}  (zu niedrig, min 0.65)")

                # Screen-Info hinzufügen
                sh, sw = screen_g.shape
                cv2.putText(debug_img, f"Screen: {sw}x{sh}",
                            (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7,
                            (255, 255, 0), 2)

                # Debug-Bild speichern (verkleinert damit es handhabbar ist)
                scale     = min(1.0, 1920 / sw)
                debug_small = cv2.resize(debug_img,
                                          (int(sw * scale), int(sh * scale)))
                debug_path = DATA_DIR / f"{_PREFIX}_debug_match.png"
                cv2.imwrite(str(debug_path), debug_small)

                msg = "  |  ".join(results) + f"  →  Debug: {debug_path.name}"
                self.root.after(0, lambda m=msg: self.status_var.set(m))

                # Ordner öffnen
                self.root.after(200, lambda: open_folder(str(DATA_DIR)))

            except Exception as e:
                self.root.after(0, lambda err=e: self.status_var.set(
                    f"Test Fehler: {err}"))

        self.status_var.set("Teste Bilderkennung...")
        threading.Thread(target=_run, daemon=True).start()

    def _find_on_screen(self, template_path: Path, confidence: float = 0.70,
                        screen=None, report: bool = True):
        """
        Template-Match auf dem Bildschirm (native Auflösung, keine Skalierung).
        Template und Screenshot müssen in derselben Auflösung aufgenommen worden sein.

        screen: optional ein bereits aufgenommener Graustufen-Screenshot, damit
                mehrere Templates gegen denselben Frame geprüft werden können.
        report: Match-Score in der Statuszeile anzeigen.
        """
        if not CV2_AVAILABLE:
            return None
        template = _TEMPLATES.get(template_path)
        if template is None:
            return None
        try:
            screen_g = screen if screen is not None else _grab_screen_gray()
            sh, sw = screen_g.shape
            th, tw = template.shape

            # Template darf nicht größer als Screenshot sein
            if th > sh or tw > sw:
                self._ui_status(
                    f"⚠ Template {template_path.name} ({tw}×{th}) größer als Screen ({sw}×{sh}) — neu aufnehmen!")
                return None

            result = cv2.matchTemplate(screen_g, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, max_loc = cv2.minMaxLoc(result)

            if report:
                self._ui_status(
                    f"Match {template_path.name}: {max_val:.2f}  "
                    f"{'✔' if max_val >= confidence else f'✗ zu niedrig (min {confidence})'}")

            if max_val >= confidence:
                return (max_loc[0] + tw // 2, max_loc[1] + th // 2)
        except Exception as e:
            self._ui_status(f"Bilderkennung Fehler: {e}")
        return None

    def _wait_for(self, template_path: Path, confidence: float, timeout: float,
                  poll: float = 0.12):
        """Sucht ein Template bis zu `timeout` Sekunden lang. Abbrechbar per Stop."""
        if not template_path.exists():
            return None
        deadline = time.monotonic() + timeout
        while not self.stop_pick.is_set():
            pos = self._find_on_screen(template_path, confidence)
            if pos or time.monotonic() >= deadline:
                return pos
            time.sleep(poll)
        return None

    def _save_debug_screenshot(self, name: str):
        """Speichert den aktuellen Screen — nur bei endgültigem Fehlschlag, nicht pro Versuch."""
        try:
            import mss
            with mss.mss() as sct:
                raw = sct.grab(sct.monitors[1])
            cv2.imwrite(str(DATA_DIR / f"debug_{name}.png"),
                        cv2.cvtColor(np.array(raw), cv2.COLOR_BGRA2BGR))
        except Exception:
            pass

    def _capture_template(self, template_path: Path, region_w: int = 200, region_h: int = 80):
        """
        Screenshot der Maus-Region via mss — KEINE Skalierung.
        Die Region wird in der aktuellen nativen Bildschirmauflösung gespeichert.
        Template und spätere Suche müssen in derselben Auflösung sein.
        """
        import mss
        pos = pyautogui.position()
        x   = max(0, pos.x - region_w // 2)
        y   = max(0, pos.y - region_h // 2)
        with mss.mss() as sct:
            region  = {"left": x, "top": y, "width": region_w, "height": region_h}
            raw     = sct.grab(region)
            img     = np.array(raw)
            img_bgr = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
            cv2.imwrite(str(template_path), img_bgr)
        return pos

    def open_image_calib_dialog(self):
        if not CV2_AVAILABLE:
            messagebox.showerror("Fehlende Pakete",
                                 "Bilderkennung nicht verfuegbar.\n\n"
                                 "Bitte installieren:\n  pip install opencv-python mss")
            return

        win = tk.Toplevel(self.root)
        win.title("Bild-Kalibrierung")
        win.configure(bg=PAL["bg"])
        win.resizable(True, True)
        win.grab_set()
        win.focus_force()
        win.columnconfigure(0, weight=1)
        win.rowconfigure(1, weight=1)
        _apply_icon(win)

        # ── Status-Zeile oben (fix) ───────────────────────────────────
        info_var = tk.StringVar(value="")
        info_lbl = tk.Label(win, textvariable=info_var, bg=PAL["bg"], fg=PAL["accent"],
                            font=self._fonts["mono"], anchor="w", wraplength=440, padx=10, pady=4)
        info_lbl.grid(row=0, column=0, sticky="ew")

        # ── Scrollbarer Inhaltsbereich ────────────────────────────────
        outer = tk.Frame(win, bg=PAL["bg"])
        outer.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)
        outer.columnconfigure(0, weight=1)
        outer.rowconfigure(0, weight=1)

        canvas = tk.Canvas(outer, bg=PAL["bg"], highlightthickness=0)
        sb     = tk.Scrollbar(outer, orient="vertical", command=canvas.yview)
        canvas.configure(yscrollcommand=sb.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        sb.grid(row=0, column=1, sticky="ns")

        inner = tk.Frame(canvas, bg=PAL["bg"])
        cwin  = canvas.create_window((0, 0), window=inner, anchor="nw")
        inner.columnconfigure(0, weight=1)

        def _on_canvas_resize(evt):
            canvas.itemconfig(cwin, width=evt.width)
        canvas.bind("<Configure>", _on_canvas_resize)
        inner.bind("<Configure>", lambda e: canvas.configure(
            scrollregion=canvas.bbox("all")))
        canvas.bind_all("<MouseWheel>",
            lambda e: canvas.yview_scroll(int(-1*(e.delta/120)), "units"))

        frm = tk.Frame(inner, bg=PAL["surface"], padx=12, pady=10)
        frm.pack(fill="x", padx=10, pady=10)

        # Speicherort-Info
        tk.Label(frm,
                 text=f"Templates werden gespeichert in:\n  {DATA_DIR}",
                 bg=PAL["surface"], fg=PAL["text_dim"],
                 font=self._fonts["small"], anchor="w", justify="left"
                 ).pack(fill="x", pady=(0, 6))

        def _status(text, color=None):
            info_var.set(text)
            if color: info_lbl.config(fg=color)
            win.update_idletasks()

        def _countdown_and_capture(template_path, label):
            for i in range(3, 0, -1):
                if not win.winfo_exists(): return
                self.root.after(0, lambda n=i, lbl=label: _status(
                    f"{lbl}  —  Noch {n} Sekunde(n)...", PAL["accent"]))
                time.sleep(1)
            if not win.winfo_exists(): return
            try:
                pos = self._capture_template(template_path)
                self.root.after(0, lambda p=pos, lbl=label: _status(
                    f"✔  {lbl}  —  gespeichert ({p.x},{p.y})  →  {template_path.name}",
                    PAL["success"]))
            except Exception as e:
                self.root.after(0, lambda err=e: _status(f"Fehler: {err}", PAL["danger"]))

        def start_capture(template_path, label, status_lbl):
            status_lbl.config(text="Warte...", fg=PAL["text_dim"])
            _status(f"{label}  —  Maus auf das Element hovern...", PAL["text_dim"])
            threading.Thread(target=_countdown_and_capture,
                             args=(template_path, label), daemon=True).start()

        def make_card(parent, title, desc, tpath, color, lbl_ref):
            card = tk.Frame(parent, bg=PAL["surface2"], padx=8, pady=6)
            card.pack(fill="x", pady=(0, 6))
            card.columnconfigure(0, weight=1)
            tk.Label(card, text=title, bg=PAL["surface2"], fg=color,
                     font=self._fonts["ui_bold"], anchor="w"
                     ).grid(row=0, column=0, sticky="w")
            tk.Label(card, text=desc, bg=PAL["surface2"], fg=PAL["text_dim"],
                     font=self._fonts["small"], anchor="w", justify="left"
                     ).grid(row=1, column=0, sticky="w", pady=(2, 6))
            exists = tpath.exists()
            sl = tk.Label(card,
                          text="✔ Template vorhanden" if exists else "✗ Noch kein Template",
                          bg=PAL["surface2"],
                          fg=PAL["success"] if exists else PAL["danger"],
                          font=self._fonts["small"])
            sl.grid(row=2, column=0, sticky="w", pady=(0, 4))
            lbl_ref.append(sl)
            tk.Button(card,
                      text=f"📷  {title.split('.')[0].strip()} erfassen  (3s Countdown)",
                      command=lambda: start_capture(tpath, title.split(".")[0].strip(), sl),
                      bg=PAL["btn_bg"], fg=PAL["text"],
                      activebackground=color, activeforeground=PAL["on_accent"],
                      relief="flat", bd=0, cursor="hand2",
                      font=self._fonts["ui"], padx=6, pady=5, highlightthickness=0
                      ).grid(row=3, column=0, sticky="ew")

        make_card(frm, "1. HELDEN-SUCHFELD",
                  "Maus auf das Suchfeld (AAAAA Texteingabe) im Spiel hovern.",
                  FIELD_TEMPLATE_PATH, PAL["int_col"], [])
        make_card(frm, "2. PICK-BUTTON  ('Auswählen')",
                  "Maus auf den 'AUSWÄHLEN' Button im Spiel hovern.",
                  AUSWAHL_TEMPLATE_PATH, PAL["str_col"], [])
        make_card(frm, "3. PLANUNG  (Item-Phase Erkennung)",
                  "Maus auf den 'PLANUNG'-Schriftzug im Spiel hovern.",
                  PLANUNG_TEMPLATE_PATH, PAL["uni_col"], [])
        make_card(frm, "4. NEUTRALE POSITION  (nach Item-Kauf)",
                  "Leere Stelle im Shop hovern.\n"
                  "Maus springt dorthin nach jedem Rechtsklick,\n"
                  "damit Tooltips die nächsten Items nicht verdecken.",
                  NEUTRAL_POS_PATH, PAL["agi_col"], [])
        make_card(frm, "5. DOPPEL-PICK  (Phase D)",
                  "Hinweis/Meldung hovern, die erscheint, wenn du und das\n"
                  "Gegnerteam denselben Helden genommen habt.\n"
                  "Optional: Ohne Template erkennt Phase D den Doppel-Pick daran,\n"
                  "dass das Suchfeld zurückkommt und PLANUNG verschwindet.",
                  DOPPELT_TEMPLATE_PATH, PAL["danger"], [])

        # Ordner öffnen Button
        tk.Button(frm, text="📂  Speicherordner öffnen",
                  command=lambda: open_folder(str(DATA_DIR)),
                  bg=PAL["btn_bg"], fg=PAL["text"],
                  activebackground=PAL["surface2"], activeforeground=PAL["accent"],
                  relief="flat", bd=0, cursor="hand2",
                  font=self._fonts["ui"], padx=6, pady=4, highlightthickness=0
                  ).pack(fill="x", pady=(8, 0))

        win.update_idletasks()
        win.geometry("480x700")
        rx = self.root.winfo_x() + self.root.winfo_width()//2 - 240
        ry = max(0, self.root.winfo_y() + self.root.winfo_height()//2 - 350)
        win.geometry(f"+{max(0,rx)}+{ry}")
    # ──────────────────────────────────────────────────────────────────
    def _on_global_key_press(self, key):
        self.pressed_keys.add(key)
        if key == keyboard.Key.home:
            self.root.after(0, lambda: self.start_enter()); return
        if key == keyboard.Key.backspace:
            self.root.after(0, lambda: self.stop_all_macros()); return
        if key == keyboard.Key.f8:
            self.root.after(0, lambda: self.capture_calibration_point()); return

        if (key == keyboard.Key.insert and
                any(_pynput_matches(pk,"ctrl") for pk in self.pressed_keys)):
            self.root.after(0, lambda: self.start_four()); return

        combo = self.cfg.get("pick_hotkey",["end"])
        if combo:
            all_pressed = all(
                any(_pynput_matches(pk,ks) for pk in self.pressed_keys)
                for ks in combo)
            if all_pressed and not self.pick_hotkey_armed:
                self.pick_hotkey_armed = True
                self.root.after(0, lambda: self.start_pick_macro())

        if (keyboard.Key.page_up in self.pressed_keys) and (keyboard.Key.page_down in self.pressed_keys):
            if not self.kill_combo_armed:
                self.kill_combo_armed = True
                self.root.after(0, lambda: self.kill_games())

        # Einfg + Entf → Steam und Discord schließen
        if (keyboard.Key.insert in self.pressed_keys) and (keyboard.Key.delete in self.pressed_keys):
            if not self.close_apps_armed:
                self.close_apps_armed = True
                self.root.after(0, lambda: self.kill_steam_discord())

    def _on_global_key_release(self, key):
        if key in self.pressed_keys:
            self.pressed_keys.remove(key)
        combo = self.cfg.get("pick_hotkey",["end"])
        if self.pick_hotkey_armed:
            still_all = all(
                any(_pynput_matches(pk,ks) for pk in self.pressed_keys)
                for ks in combo)
            if not still_all:
                self.pick_hotkey_armed = False
        if key in (keyboard.Key.page_up, keyboard.Key.page_down):
            if (keyboard.Key.page_up not in self.pressed_keys) or (keyboard.Key.page_down not in self.pressed_keys):
                self.kill_combo_armed = False
        if key in (keyboard.Key.insert, keyboard.Key.delete):
            if (keyboard.Key.insert not in self.pressed_keys) or (keyboard.Key.delete not in self.pressed_keys):
                self.close_apps_armed = False

    # ──────────────────────────────────────────────────────────────────
    # Auto Keys
    # ──────────────────────────────────────────────────────────────────
    def start_enter(self):
        if self.enter_thread and self.enter_thread.is_alive():
            self.status_var.set("ENTER laeuft bereits."); return
        self.stop_enter.clear()
        self.enter_thread = threading.Thread(target=self._enter_loop, daemon=True)
        self.enter_thread.start()
        self.status_var.set("ENTER Auto gestartet (alle 5s).")

    def start_four(self):
        if self.four_thread and self.four_thread.is_alive():
            self.status_var.set("Taste 4 laeuft bereits."); return
        self.stop_four.clear()
        self.four_thread = threading.Thread(target=self._four_loop, daemon=True)
        self.four_thread.start()
        self.status_var.set("Taste 4 Auto gestartet (alle 5s).")

    def stop_all_macros(self):
        self.stop_enter.set()
        self.stop_four.set()
        self.stop_pick.set()
        self.status_var.set("BACKSPACE: Alle Macros gestoppt.")

    def _enter_loop(self):
        try:
            while not self.stop_enter.is_set():
                pyautogui.press("enter")
                self._sleep_interruptible(self.stop_enter, 5.0)
        except pyautogui.FailSafeException:
            self.stop_enter.set()
            self.root.after(0, lambda: self.status_var.set("Failsafe: ENTER Loop gestoppt."))

    def _four_loop(self):
        try:
            while not self.stop_four.is_set():
                pyautogui.press("4")
                self._sleep_interruptible(self.stop_four, 5.0)
        except pyautogui.FailSafeException:
            self.stop_four.set()
            self.root.after(0, lambda: self.status_var.set("Failsafe: 4-Loop gestoppt."))

    def _sleep_interruptible(self, evt: threading.Event, seconds: float):
        end = time.monotonic() + seconds
        while time.monotonic() < end and not evt.is_set():
            time.sleep(0.05)

    # ──────────────────────────────────────────────────────────────────
    # Pick Macro
    # ──────────────────────────────────────────────────────────────────
    def _has_coords(self) -> bool:
        pp = self.cfg.get("pick_points")
        fp = self.cfg.get("field_point")
        return (isinstance(pp, list) and len(pp) == 3 and
                isinstance(fp, list) and len(fp) == 2)

    def start_pick_macro(self):
        if not self.selected_heroes:
            self.status_var.set("Keine Helden ausgewaehlt."); return
        if self.pick_thread and self.pick_thread.is_alive():
            self.status_var.set("Pick-Macro laeuft bereits."); return

        mode      = self.cfg.get("pick_mode", "both")
        has_images= FIELD_TEMPLATE_PATH.exists() and AUSWAHL_TEMPLATE_PATH.exists() and CV2_AVAILABLE
        has_coords= self._has_coords()

        if mode == "image"  and not has_images:
            self.status_var.set("Modus '📷 Bild': Templates fehlen → Konfiguration > Bild-Templates."); return
        if mode == "coords" and not has_coords:
            self.status_var.set("Modus '📍 Koordinaten': nicht kalibriert → Konfiguration > Koordinaten."); return
        if mode == "both"   and not has_images and not has_coords:
            self.status_var.set("Bitte zuerst kalibrieren → Tab Konfiguration."); return

        mode_labels = {"image":"📷 Bild", "coords":"📍 Koordinaten", "both":"🔀 Beides"}
        # ENTER-Loop stoppen — Pick-Macro übernimmt ab jetzt
        self.stop_enter.set()
        self.stop_pick.clear()
        self.pick_thread = threading.Thread(target=self._pick_macro_loop, daemon=True)
        self.pick_thread.start()
        self.status_var.set(f"Pick-Macro gestartet  [{mode_labels.get(mode, mode)}].")

    def stop_pick_macro(self):
        self.stop_pick.set()
        self.status_var.set("Pick-Macro gestoppt.")

    def _ui_status(self, msg: str):
        """Statuszeile thread-sicher setzen."""
        self.root.after(0, lambda m=msg: self.status_var.set(m))

    def _t(self, key: str, default: float) -> float:
        try:    return float(self.cfg.get("timings", {}).get(key, default))
        except (TypeError, ValueError): return float(default)

    def _pick_macro_loop(self):
        """
        Phase A — Suchfeld finden → 2x klicken → 2s warten
        Phase B — Helden der Reihe nach: tippen → ENTER → Auswählen klicken
                  → auf PLANUNG warten (gefunden = Held ist gepickt)
        Phase C — Items aus dem aktiven Set per Rechtsklick kaufen (einmalig)
        Phase D — Doppel-Pick-Prüfung: Haben wir und das Gegnerteam denselben
                  Helden genommen, wird der Pick zurückgesetzt. Dann geht es
                  mit Phase A + B ab dem NÄCHSTEN Helden der Liste weiter.
        """
        try:
            heroes     = list(dict.fromkeys(self.selected_heroes))   # ohne Duplikate
            pick_mode  = self.cfg.get("pick_mode", "both")
            use_img    = pick_mode in ("image", "both") and CV2_AVAILABLE
            use_coords = pick_mode in ("coords", "both") and self._has_coords()

            start        = 0
            items_bought = False
            while start < len(heroes) and not self.stop_pick.is_set():
                if not self._phase_a_activate_field(use_img, use_coords):
                    break
                picked_idx, planung = self._phase_b_pick(heroes, start, use_img, use_coords)
                if self.stop_pick.is_set():
                    break
                if picked_idx is None:
                    self._ui_status("✗ Kein Held aus der Liste konnte gepickt werden.")
                    return
                hero = heroes[picked_idx]

                if not items_bought:
                    items_bought = self._phase_c_items(planung, use_img)
                if self.stop_pick.is_set():
                    break

                if not self._phase_d_duplicate_watch(hero, use_img):
                    if not self.stop_pick.is_set():
                        self._ui_status(f"✔ '{hero}' gepickt — kein Doppel-Pick. Ins Spiel!")
                    return

                start = picked_idx + 1
                if start >= len(heroes):
                    self._ui_status(f"⚠ Doppel-Pick bei '{hero}' — keine weiteren Helden in der Liste!")
                    return
                self._ui_status(f"⚠ Doppel-Pick bei '{hero}' erkannt — picke jetzt '{heroes[start]}' ...")
                self._sleep_interruptible(self.stop_pick, 0.5)

            if self.stop_pick.is_set():
                self._ui_status("Pick-Macro gestoppt.")

        except pyautogui.FailSafeException:
            self.stop_pick.set()
            self._ui_status("Failsafe: Pick-Macro gestoppt (Maus links-oben).")
        finally:
            _release_screen()

    # ── Phase A ───────────────────────────────────────────────────────
    def _phase_a_activate_field(self, use_img: bool, use_coords: bool) -> bool:
        pos = None
        if use_img and FIELD_TEMPLATE_PATH.exists():
            self._ui_status("Pick: Warte auf Suchfeld...  |  BACKSPACE = Stop")
            while not self.stop_pick.is_set():
                pos = self._find_on_screen(FIELD_TEMPLATE_PATH, confidence=0.65, report=False)
                if pos:
                    break
                time.sleep(0.3)
        elif use_coords:
            pos = tuple(self.cfg["field_point"])
        else:
            self._ui_status("⚠ Kein Suchfeld-Template — bitte 📷 Bilder kalibrieren.")
            return False

        if self.stop_pick.is_set() or not pos:
            return False

        fx, fy = pos
        self._ui_status("Pick: Suchfeld gefunden — klicke 2x")
        pyautogui.moveTo(fx, fy, duration=0.10)
        pyautogui.click(); time.sleep(self._t("field_click_delay", 0.15)); pyautogui.click()

        self._ui_status("Pick: Suchfeld aktiviert — warte 2s...")
        self._sleep_interruptible(self.stop_pick, 2.0)
        return not self.stop_pick.is_set()

    # ── Phase B ───────────────────────────────────────────────────────
    def _locate_pick_button(self, use_img: bool, use_coords: bool, timeout: float):
        """Liefert die Klickpunkte für 'Auswählen' (Bild zuerst, sonst Koordinaten)."""
        if use_img and AUSWAHL_TEMPLATE_PATH.exists():
            pos = self._wait_for(AUSWAHL_TEMPLATE_PATH, 0.65, timeout)
            if pos:
                ax, ay = pos
                return [(ax - 8, ay), (ax, ay), (ax + 8, ay)]
        if use_coords:
            return [tuple(p) for p in self.cfg["pick_points"]]
        return None

    def _phase_b_pick(self, heroes: list[str], start: int,
                      use_img: bool, use_coords: bool) -> tuple[int | None, bool]:
        """
        Geht die Helden ab Index `start` durch.
        Rückgabe: (Index des gepickten Helden | None, PLANUNG erkannt?)
        """
        type_duration = self._t("type_duration",       4.0)
        enter_pause   = self._t("enter_pause",         1.0)
        pick_duration = self._t("pick_duration",       2.0)
        pick_interval = self._t("pick_click_interval", 0.05)
        planung_wait  = self._t("suchfeld_wait",       2.5)
        loop_pause    = self._t("loop_pause",          0.0)
        has_planung   = use_img and PLANUNG_TEMPLATE_PATH.exists()

        for idx in range(start, len(heroes)):
            if self.stop_pick.is_set():
                return None, False
            hero = heroes[idx]
            self._ui_status(f"Pick {idx+1}/{len(heroes)}: tippe '{hero}'  |  BACKSPACE = Stop")

            # Tippen
            ti = (type_duration / max(len(hero), 1)) * 0.55
            ti = max(0.05, min(ti, 0.4))
            pyautogui.write(hero, interval=ti)
            rem = type_duration - ti * len(hero)
            if rem > 0: self._sleep_interruptible(self.stop_pick, rem)
            if self.stop_pick.is_set(): return None, False

            # ENTER
            pyautogui.press("enter")
            self._sleep_interruptible(self.stop_pick, enter_pause)
            if self.stop_pick.is_set(): return None, False

            # Auswählen suchen & für pick_duration Sekunden klicken
            self._ui_status("Pick: suche 'Auswählen'...")
            points = self._locate_pick_button(use_img, use_coords, pick_duration)
            if not points:
                self._ui_status(f"⚠ Auswählen nicht gefunden — überspringe '{hero}'")
                self._save_debug_screenshot("auswahl")
                continue
            self._ui_status(f"Pick: ✔ Auswählen — klicke für '{hero}'")
            phase_end = time.monotonic() + pick_duration
            ci = 0
            while time.monotonic() < phase_end and not self.stop_pick.is_set():
                px, py = points[ci % len(points)]
                pyautogui.moveTo(px, py, duration=0.04)
                pyautogui.click()
                ci += 1
                time.sleep(pick_interval)
            if self.stop_pick.is_set(): return None, False

            # PLANUNG = Pick hat geklappt
            if has_planung:
                self._ui_status("Pick: warte auf Planung-Bildschirm...")
                if self._wait_for(PLANUNG_TEMPLATE_PATH, 0.60, planung_wait, poll=0.25):
                    self._ui_status(f"✔ PLANUNG erkannt — '{hero}' gepickt.")
                    return idx, True
                self._ui_status(f"PLANUNG nicht gefunden nach '{hero}' — nächster Held")
            else:
                # Ohne PLANUNG-Template kein Erfolgs-Check → alle Helden durchprobieren
                self._sleep_interruptible(self.stop_pick, planung_wait)
                if idx == len(heroes) - 1:
                    return idx, True
            if loop_pause > 0:
                self._sleep_interruptible(self.stop_pick, loop_pause)

        if has_planung:
            self._save_debug_screenshot("planung")
        return None, False

    # ── Phase C ───────────────────────────────────────────────────────
    def _phase_c_items(self, planung_detected: bool, use_img: bool) -> bool:
        """Kauft das aktive Item-Set. Rückgabe: True, wenn der Kauf gelaufen ist."""
        if not self.cfg.get("item_phase_enabled", True):
            self._ui_status("✔ Pick fertig. Item-Phase deaktiviert.")
            return False
        if not planung_detected or not use_img:
            self._ui_status("✔ Pick fertig — PLANUNG nicht erkannt, keine Items.")
            return False

        self._ui_status("Phase C: PLANUNG erkannt — kaufe Items...")
        self._sleep_interruptible(self.stop_pick, 0.5)

        active_idx = self.cfg.get("active_item_set", 0)
        item_sets  = self.cfg.get("item_sets", DEFAULT_CONFIG["item_sets"])
        active_set = item_sets[active_idx] if active_idx < len(item_sets) else item_sets[0]
        items      = active_set.get("items", [])

        # Neutrale Position einmal suchen — Maus parkt dort nach jedem Kauf,
        # damit Tooltips die nächsten Items nicht verdecken.
        neutral = (self._find_on_screen(NEUTRAL_POS_PATH, 0.65, report=False)
                   if NEUTRAL_POS_PATH.exists() else None)

        for i, item_entry in enumerate(items):
            if self.stop_pick.is_set(): break
            item_path  = DATA_DIR / item_entry.get("file", _item_file(active_idx, i))
            item_label = item_entry.get("label", f"Item {i+1}")
            if not item_path.exists():
                continue  # Kein Template → überspringen

            self._ui_status(f"Phase C: suche {i+1}/{len(items)} — {item_label}")
            item_pos = self._wait_for(item_path, 0.65, 3.0, poll=0.2)
            if item_pos:
                pyautogui.moveTo(*item_pos, duration=0.08)
                pyautogui.click(button="right")   # RECHTSKLICK kauft
                self._ui_status(f"Phase C: ✔ {item_label} gekauft (Rechtsklick)")
                if neutral:
                    pyautogui.moveTo(*neutral, duration=0.05)
                time.sleep(0.3)
            else:
                self._ui_status(f"Phase C: ⚠ {item_label} nicht gefunden — übersprungen")
                time.sleep(0.1)
        return True

    # ── Phase D ───────────────────────────────────────────────────────
    def _phase_d_duplicate_watch(self, hero: str, use_img: bool, force: bool = False) -> bool:
        """
        Beobachtet nach dem Pick den Bildschirm, ob unser Held auch vom
        Gegnerteam genommen wurde (Doppel-Pick → Pick wird zurückgesetzt).

        Signale:
          1. Doppel-Pick-Template (skadi_doppelt.png) ist sichtbar
          2. Das Helden-Suchfeld ist wieder da UND PLANUNG ist weg
             (3x hintereinander, damit kurzes Flackern nicht auslöst)

        Rückgabe: True = Doppel-Pick erkannt → neu picken.
        """
        if not use_img or not (force or self.cfg.get("doppel_check_enabled", True)):
            return False
        has_doppelt = DOPPELT_TEMPLATE_PATH.exists()
        has_field   = FIELD_TEMPLATE_PATH.exists() and PLANUNG_TEMPLATE_PATH.exists()
        if not (has_doppelt or has_field):
            return False

        watch    = self._t("doppel_watch", 60.0)
        deadline = time.monotonic() + watch
        hits     = 0
        self._ui_status(f"Phase D: prüfe Doppel-Pick für '{hero}' ({watch:.0f}s)  |  BACKSPACE = Stop")
        while time.monotonic() < deadline and not self.stop_pick.is_set():
            screen = _grab_screen_gray()
            if has_doppelt and self._find_on_screen(DOPPELT_TEMPLATE_PATH, 0.70,
                                                    screen=screen, report=False):
                return True
            if has_field:
                field_back = self._find_on_screen(FIELD_TEMPLATE_PATH, 0.65,
                                                  screen=screen, report=False)
                planung    = field_back and self._find_on_screen(PLANUNG_TEMPLATE_PATH, 0.60,
                                                                 screen=screen, report=False)
                hits = hits + 1 if (field_back and not planung) else 0
                if hits >= 3:
                    return True
            time.sleep(0.4)
        return False

    # ──────────────────────────────────────────────────────────────────
    # Kalibrierung (Koordinaten)
    # ──────────────────────────────────────────────────────────────────
    def start_calibration(self):
        self.calibrating = True
        with self.calib_lock:
            self.calib_points = []
        self.status_var.set("Kalib 1/4: Maus aufs HELDEN-SUCHFELD hovern, dann F8.")

    def capture_calibration_point(self):
        if not self.calibrating:
            self.status_var.set("Kalibrierung nicht aktiv."); return
        pos = pyautogui.position()
        with self.calib_lock:
            self.calib_points.append((pos.x, pos.y))
            n = len(self.calib_points)
        hints = {1:"Kalib 2/4: PICK-BUTTON Pos.1, dann F8.",
                 2:"Kalib 3/4: PICK-BUTTON Pos.2, dann F8.",
                 3:"Kalib 4/4: PICK-BUTTON Pos.3, dann F8."}
        if n < 4:
            self.status_var.set(f"Punkt {n}/4 gespeichert ({pos.x},{pos.y}).  " + hints.get(n,""))
            return
        with self.calib_lock:
            pts = self.calib_points[:4]; self.calib_points = []
        self.cfg["field_point"]  = list(pts[0])
        self.cfg["pick_points"]  = [list(p) for p in pts[1:4]]
        save_config(self.cfg)
        self.calibrating = False
        self.status_var.set(f"Kalibrierung fertig.  Feld={pts[0]}  Pick={self.cfg['pick_points']}")

    # ──────────────────────────────────────────────────────────────────
    # Feld-Klick
    # ──────────────────────────────────────────────────────────────────
    def click_hero_field(self):
        fp = self.cfg.get("field_point",[])
        if not (isinstance(fp,list) and len(fp)==2):
            self.status_var.set("Feld-Punkt fehlt – bitte kalibrieren."); return
        def _do():
            try:
                fx, fy = fp
                pyautogui.moveTo(fx, fy, duration=0.1)
                pyautogui.click(); time.sleep(0.15); pyautogui.click()
                self.root.after(0, lambda: self.status_var.set(f"Feld angeklickt (2x) bei ({fx},{fy})."))
            except pyautogui.FailSafeException:
                self.root.after(0, lambda: self.status_var.set("Failsafe: Feld-Klick gestoppt."))
        threading.Thread(target=_do, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────
    # Apps
    # ──────────────────────────────────────────────────────────────────
    def kill_steam(self):
        self.stop_all_macros()
        k = kill_processes_by_name({n.lower() for n in STEAM_PROCS})
        self.status_var.set(f"Steam gekillt: {', '.join(sorted(set(k)))}" if k else "Steam: nichts gefunden.")

    def kill_discord(self):
        self.stop_all_macros()
        k = kill_processes_by_name({n.lower() for n in DISCORD_PROCS})
        self.status_var.set(f"Discord gekillt: {', '.join(sorted(set(k)))}" if k else "Discord: nichts gefunden.")

    def kill_steam_discord(self):
        self.stop_all_macros()
        k = kill_processes_by_name({n.lower() for n in STEAM_PROCS | DISCORD_PROCS})
        self.status_var.set(f"Steam+Discord geschlossen: {', '.join(sorted(set(k)))}" if k
                            else "Steam+Discord: nichts gefunden.")

    def kill_games(self):
        self.stop_all_macros()
        k = kill_processes_by_name({n.lower() for n in GAME_PROCS})
        self.status_var.set(f"Games gekillt: {', '.join(sorted(set(k)))}" if k else "Games: nichts gefunden.")

    def ui_start_steam(self):
        self.status_var.set("Steam gestartet." if start_steam() else "Steam Start fehlgeschlagen.")

    def ui_start_discord(self):
        self.status_var.set("Discord gestartet." if start_discord() else "Discord Start fehlgeschlagen.")

    def ui_open_discord_voice_video(self):
        open_discord_voice_video()
        self.status_var.set("Voice & Video geoeffnet.")

    def ui_open_d2_settings_folder(self):
        ok = open_folder(D2_SETTINGS_PATH)
        self.status_var.set("D2 Settings geoeffnet." if ok else f"Ordner nicht gefunden: {D2_SETTINGS_PATH}")

    # ──────────────────────────────────────────────────────────────────
    # Auflösung wechseln
    # ──────────────────────────────────────────────────────────────────
    def _res_current_str(self) -> str:
        try:
            w, h, hz = _get_current_resolution()
            return f"aktuell {w} × {h} · {hz} Hz"
        except Exception:
            return "aktuell: unbekannt"

    def _refresh_res_display(self):
        """Aktuelle Auflösung anzeigen und den passenden Button grün markieren."""
        try:
            cur = _get_current_resolution()
        except Exception:
            cur = None
        self._res_status.config(text=self._res_current_str())
        for mode, btn in self._res_btns.items():
            on = cur == mode
            btn.config(bg=PAL["success"] if on else PAL["btn_bg"],
                       fg=PAL["on_accent"] if on else PAL["text"],
                       font=self._fonts["ui_bold" if on else "ui"])

    def _set_res(self, w: int, h: int, hz: int):
        self.status_var.set(f"Ändere Auflösung auf {w}×{h} @ {hz}Hz ...")

        def _do():
            ok = _apply_resolution(w, h, hz)
            def _update():
                if ok:
                    self.status_var.set(f"✔  Auflösung: {w}×{h} @ {hz}Hz gesetzt.")
                else:
                    self.status_var.set(f"✗  Auflösung {w}×{h} @ {hz}Hz fehlgeschlagen.")
                self._refresh_res_display()
            self.root.after(0, _update)

        threading.Thread(target=_do, daemon=True).start()

    # ──────────────────────────────────────────────────────────────────
    # Globaler Speichern-Button
    # ──────────────────────────────────────────────────────────────────
    def save_all_settings(self):
        """Speichert die gesamte aktuelle Config in die JSON-Datei."""
        try:
            save_config(self.cfg)
            self.status_var.set(f"✔ Alle Einstellungen gespeichert  →  {CONFIG_PATH.name}")
        except Exception as e:
            self.status_var.set(f"✗ Fehler beim Speichern: {e}")

    # ──────────────────────────────────────────────────────────────────
    # Close
    # ──────────────────────────────────────────────────────────────────
    def _auto_close_check(self):
        """Alle 30s prüfen ob ein Spiel läuft.
        Wenn 3 Minuten kein Spiel erkannt → automatisch schließen."""
        AUTO_CLOSE_SECONDS = 180
        try:
            game_names = {n.lower() for n in GAME_PROCS}
            running = any(
                (proc.info["name"] or "").lower() in game_names
                for proc in psutil.process_iter(["name"])
            )
        except Exception:
            running = False

        if running:
            self._last_game_seen = time.time()
        else:
            if time.time() - self._last_game_seen >= AUTO_CLOSE_SECONDS:
                self.on_close()
                return

        self.root.after(30_000, self._auto_close_check)

    def on_close(self):
        self.stop_all_macros()
        try: self.kb_listener.stop()
        except Exception: pass
        self.root.destroy()


# ──────────────────────────────────────────────────────────────────────────────
# Main
# ──────────────────────────────────────────────────────────────────────────────
def main():
    root = tk.Tk()

    try:
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("SkadiTerminal.App.1.0")
    except Exception:
        pass

    _apply_icon(root)

    # Alle Toplevel-Fenster ebenfalls mit Icon
    _orig_init = tk.Toplevel.__init__
    def _patched_init(self, master=None, **kw):
        _orig_init(self, master, **kw)
        try: _apply_icon(self)
        except Exception: pass
    tk.Toplevel.__init__ = _patched_init

    app = SkadiTerminalApp(root)

    root.resizable(True, True)
    root.minsize(WIN_W, 500)
    # Breite fix, Höhe passt sich dem Inhalt an
    app._fit_window()

    def _front():
        try: root.attributes("-topmost", True)
        except Exception: pass
        root.lift()
        try: root.focus_force()
        except Exception: pass
        root.after(1200, lambda: root.attributes("-topmost", False))

    root.after(50, _front)
    root.mainloop()


if __name__ == "__main__":
    main()
