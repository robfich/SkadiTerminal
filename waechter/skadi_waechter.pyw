"""
SkadiTerminal-Wächter
Läuft unsichtbar im Hintergrund (Autostart) und startet SkadiTerminal,
sobald Dota 2 (oder ein anderes Spiel aus TARGET_GAMES) läuft.
SkadiTerminal schließt sich selbst wieder, wenn 3 Minuten kein Spiel mehr läuft.
"""
import sys
import time
import subprocess
from pathlib import Path

import psutil

# Spiele, die den Start auslösen sollen
TARGET_GAMES = {"dota2.exe", "cs2.exe", "pioneergame.exe", "ut2004.exe"}

# Wie oft prüfen (Sekunden)
POLL_SECONDS = 2.0

# Mindest-Abstand zwischen Starts (Sekunden), falls ein Spiel mehrfach kurz startet
COOLDOWN_SECONDS = 20.0

# Prozess-/Dateinamen, an denen ein laufendes Terminal erkannt wird
TERMINAL_NAMES = ("skaditerminal", "gterminal")

# Projektordner im Google Drive (unter "Meine Ablage")
GDRIVE_PROJECT_DIR = Path("_060_Projekte") / "_010_Aktiv"

if getattr(sys, "frozen", False):
    HERE = Path(sys.executable).parent
else:
    HERE = Path(__file__).parent


def find_gdrive_root() -> Path | None:
    """Google Drive für Desktop: 'Meine Ablage' bzw. 'My Drive' auf irgendeinem Laufwerk."""
    for letter in "GHIJKLMNOPQRSTUVWXYZDEF":
        for name in ("Meine Ablage", "My Drive"):
            p = Path(f"{letter}:/") / name
            try:
                if p.is_dir():
                    return p
            except OSError:
                pass
    return None


def terminal_candidates() -> list[Path]:
    """Mögliche Orte von SkadiTerminal — der erste, der existiert, wird gestartet."""
    cands = [HERE / "SkadiTerminal.exe", HERE / "skaditerminal.pyw", HERE / "skaditerminal.py",
             HERE.parent / "skaditerminal.py"]                       # waechter/ im Repo-Ordner
    gd = find_gdrive_root()
    if gd:
        aktiv = gd / GDRIVE_PROJECT_DIR
        cands += [aktiv / "SkadiTerminal" / "SkadiTerminal.exe",
                  aktiv / "SkadiTerminal" / "skaditerminal.pyw",
                  aktiv / "Dota2_Draft_Helfer_Maerz" / "gterminal.pyw"]   # alter Stand als Notlösung
    return cands


def find_terminal() -> Path | None:
    return next((p for p in terminal_candidates() if p.exists()), None)


def any_target_game_running() -> bool:
    targets = {n.lower() for n in TARGET_GAMES}
    for p in psutil.process_iter(["name"]):
        try:
            if (p.info["name"] or "").lower() in targets:
                return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def terminal_already_running() -> bool:
    """Erkennt SkadiTerminal/Gterminal — als .exe oder als Python-Skript."""
    exe_names = {f"{n}.exe" for n in TERMINAL_NAMES}
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            name = (p.info["name"] or "").lower()
            if name in exe_names:
                return True
            if name in ("pythonw.exe", "python.exe"):
                cmdline = p.info.get("cmdline") or []
                if any(n in str(arg).lower() for arg in cmdline for n in TERMINAL_NAMES):
                    return True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return False


def start_terminal(path: Path):
    cmd = ["pythonw", str(path)] if path.suffix.lower() in (".pyw", ".py") else [str(path)]
    subprocess.Popen(cmd, cwd=str(path.parent),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    last_launch = 0.0
    while True:
        try:
            if any_target_game_running():
                now = time.time()
                terminal = find_terminal()
                if terminal and not terminal_already_running() and (now - last_launch) >= COOLDOWN_SECONDS:
                    start_terminal(terminal)
                    last_launch = now
        except Exception:
            pass
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
