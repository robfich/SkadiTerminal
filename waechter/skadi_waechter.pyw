"""
SkadiTerminal-Wächter
Läuft unsichtbar im Hintergrund (Autostart) und startet SkadiTerminal,
sobald Dota 2 (oder ein anderes Spiel aus TARGET_GAMES) läuft — EINMAL pro Spielsitzung:
Wer SkadiTerminal während des Spiels schließt, bekommt es erst beim nächsten Spielstart wieder.
Startet außerdem Discord (minimiert), wenn Dota 2 startet — Discord bleibt danach offen.
Endet die Spielsitzung, schließt der Wächter SkadiTerminal (nur wenn er es selbst gestartet hat).
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

# So viele Prüfungen hintereinander muss ein Spiel weg sein, bevor die Sitzung als beendet gilt
# (verhindert Neustarts, wenn ein Spiel kurz neu startet, z. B. nach einem Update)
SESSION_END_POLLS = 3

# Discord mitstarten (minimiert), wenn eines dieser Spiele startet (leere Menge = aus).
# Discord wird NICHT wieder geschlossen.
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
    """Discord minimiert (nur im Tray) über den offiziellen Updater starten."""
    for base in (os.environ.get("LOCALAPPDATA"), os.environ.get("APPDATA")):
        if not base:
            continue
        updater = Path(base) / "Discord" / "Update.exe"
        if updater.exists():
            try:
                subprocess.Popen([str(updater), "--processStart", "Discord.exe",
                                  "--process-start-args", "--start-minimized"],
                                 stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                return True
            except OSError:
                pass
    return False


def close_auto_terminals():
    """Schließt SkadiTerminal, wenn es vom Wächter (mit --auto) gestartet wurde.
    Von Hand gestartete Fenster bleiben offen."""
    exe_names = {f"{n}.exe" for n in TERMINAL_NAMES}
    for p in psutil.process_iter(["name", "cmdline"]):
        try:
            name = (p.info["name"] or "").lower()
            cmdline = [str(a).lower() for a in (p.info.get("cmdline") or [])]
            is_terminal = name in exe_names or (
                name in ("pythonw.exe", "python.exe")
                and any(n in a for a in cmdline for n in TERMINAL_NAMES))
            if is_terminal and "--auto" in cmdline:
                p.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass


class Session:
    """Merkt sich, ob eine Spielsitzung läuft — mit kurzer Nachlaufzeit beim Beenden."""
    def __init__(self):
        self.active = False
        self._missing = 0

    def update(self, running: bool) -> str | None:
        """Liefert 'start' beim Sitzungsbeginn, 'end' beim Sitzungsende, sonst None."""
        if running:
            self._missing = 0
            if not self.active:
                self.active = True
                return "start"
        elif self.active:
            self._missing += 1
            if self._missing >= SESSION_END_POLLS:
                self.active = False
                return "end"
        return None


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
    game_session    = Session()     # irgendein Spiel aus der Liste → SkadiTerminal
    discord_session = Session()     # Dota-Start → Discord starten
    games, games_loaded = load_games(), time.time()
    while True:
        try:
            if time.time() - games_loaded > CONFIG_REFRESH_SECONDS:
                games, games_loaded = load_games(), time.time()
            names = running_process_names()

            # SkadiTerminal: nur EINMAL beim Sitzungsbeginn starten. Wird es während
            # des Spiels geschlossen, bleibt es zu bis zum nächsten Spielstart.
            event = game_session.update(bool(names & games))
            if event == "start":
                terminal = find_terminal()
                if terminal and not terminal_already_running():
                    start_terminal(terminal)
            elif event == "end":
                close_auto_terminals()          # Spiel zu → SkadiTerminal zu (Discord bleibt)

            # Discord: mit Dota starten (minimiert); wird nicht wieder geschlossen
            if DISCORD_WITH_GAMES:
                if discord_session.update(bool(names & DISCORD_WITH_GAMES)) == "start" \
                        and not (names & DISCORD_PROCS):
                    start_discord()
        except Exception:
            pass
        time.sleep(POLL_SECONDS)


if __name__ == "__main__":
    main()
