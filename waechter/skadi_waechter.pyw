"""
SkadiTerminal-Wächter
Läuft unsichtbar im Hintergrund (Autostart) und startet SkadiTerminal,
sobald Dota 2 (oder ein anderes Spiel aus TARGET_GAMES) läuft.
Startet außerdem Discord, wenn Dota 2 startet (einmal pro Spielsitzung).
SkadiTerminal schließt sich selbst wieder, wenn 3 Minuten kein Spiel mehr läuft.
"""
import os
import sys
import time
import subprocess
import json
from pathlib import Path

import psutil

# Spiele, die den Start auslösen sollen. Wird überschrieben durch die Liste "games" in
# skadi_config.json (in SkadiTerminal unter Konfiguration → Spiele-Liste bearbeiten).
TARGET_GAMES = {"dota2.exe", "cs2.exe", "pioneergame.exe", "ut2004.exe"}
CONFIG_REFRESH_SECONDS = 30.0

# Wie oft prüfen (Sekunden)
POLL_SECONDS = 2.0

# Mindest-Abstand zwischen Starts (Sekunden), falls ein Spiel mehrfach kurz startet
COOLDOWN_SECONDS = 20.0

# Discord mitstarten, wenn eines dieser Spiele startet (leere Menge = aus)
DISCORD_WITH_GAMES = {"dota2.exe"}
DISCORD_PROCS      = {"discord.exe", "discordcanary.exe", "discordptb.exe"}

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


def config_candidates() -> list[Path]:
    cands = [HERE / "skadi_config.json"]
    gd = find_gdrive_root()
    if gd:
        cands.append(gd / GDRIVE_PROJECT_DIR / "SkadiTerminal" / "skadi_config.json")
    return cands


def load_games() -> set[str]:
    """Spieleliste aus der SkadiTerminal-Config; ohne Config die Standardliste."""
    for p in config_candidates():
        try:
            games = json.loads(p.read_text(encoding="utf-8")).get("games")
            if games:
                return {g.strip().lower() for g in games if g and g.strip()}
        except (OSError, ValueError, AttributeError):
            continue
    return {g.lower() for g in TARGET_GAMES}


def find_terminal() -> Path | None:
    return next((p for p in terminal_candidates() if p.exists()), None)


def running_process_names() -> set[str]:
    names = set()
    for p in psutil.process_iter(["name"]):
        try:
            names.add((p.info["name"] or "").lower())
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    return names


def any_target_game_running() -> bool:
    return bool(running_process_names() & load_games())


def start_discord() -> bool:
    """Discord über den offiziellen Updater starten (wie der Start-Button in SkadiTerminal)."""
    for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if not base:
            continue
        updater = Path(base) / "Discord" / "Update.exe"
        if updater.exists():
            try:
                subprocess.Popen([str(updater), "--processStart", "Discord.exe"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
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
    cmd.append("--auto")       # SkadiTerminal schließt sich dann nach Spielende selbst
    subprocess.Popen(cmd, cwd=str(path.parent),
                     stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)


def main():
    last_launch = 0.0
    discord_game_was_running = False
    games, games_loaded = load_games(), time.time()
    while True:
        try:
            if time.time() - games_loaded > CONFIG_REFRESH_SECONDS:
                games, games_loaded = load_games(), time.time()
            names = running_process_names()

            # Discord: nur beim Übergang "Dota aus → Dota an", damit ein bewusst
            # geschlossenes Discord nicht ständig wieder aufgeht
            discord_game = bool(names & DISCORD_WITH_GAMES)
            if discord_game and not discord_game_was_running and not (names & DISCORD_PROCS):
                start_discord()
            discord_game_was_running = discord_game

            if names & games:
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
