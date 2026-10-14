# SkadiTerminal

<img src="skaditerminal_1024.png" width="96" alt="Logo">

Dota-2-Helfer für Windows (früher **Gterminal**). Läuft lokal auf dem Gaming-PC –
Bilderkennung, Maus- und Tastatursteuerung brauchen den echten Bildschirm.

## Hotkeys (global, auch im Spiel)

| Taste | Aktion |
|---|---|
| `Ende` | Pick-Makro starten (änderbar unter *Zeiten & Hotkey*) |
| `Pos1` | Enter alle 5 s |
| `Strg + Einfg` | Taste 4 alle 5 s |
| `Backspace` | Alle Makros stoppen |
| `Einfg + Entf` | Steam **und** Discord schließen |
| `Bild↑ + Bild↓` | Spiele schließen |
| `F8` | Punkt bei der Koordinaten-Kalibrierung speichern |

`Ende`, `Pos1` und `Strg + Einfg` wirken nur, wenn **Dota das aktive Fenster** ist – sonst tippen/klicken
sie nicht ins falsche Programm. Laufende Enter-/Taste-4-Makros pausieren außerhalb des Spiels.
Stop, Steam/Discord schließen und Spiele schließen gehen **immer**, egal welches Fenster vorne ist.

Vom Wächter gestartet schließt sich SkadiTerminal 3 Minuten nach Spielende selbst; von Hand gestartet bleibt es offen.

## Pick-Makro (Taste `Ende`)

| Phase | Was passiert |
|---|---|
| **A** | Wartet auf das Helden-Suchfeld (Bild) bzw. nutzt die kalibrierten Koordinaten und klickt 2x |
| **B** | Tippt die Helden der Reihe nach, ENTER, klickt „Auswählen“, wartet auf PLANUNG |
| **D** | **Doppel-Pick-Check:** Haben du und das Gegnerteam denselben Helden genommen, wird neu gepickt – mit dem nächsten Helden aus deiner Liste |

Phase D erkennt den Doppel-Pick über
1. das optionale Template `skadi_doppelt.png` (Konfiguration → Bild-Templates → Karte 4), oder
2. Suchfeld wieder sichtbar **und** PLANUNG verschwunden.

**„Auswählen“ & Auflösung:** Die Bilder werden auch gefunden, wenn das Spiel gestreckt läuft
(z. B. Dota in 1920×1200 auf einem 2560×1440-Bildschirm). Geklickt wird rechts-unten von der
Bildmitte, also sicher auf dem Button. Koordinaten (F8) werden nur benutzt, wenn sie wirklich
kalibriert wurden – die Standardwerte klicken nicht mehr irgendwo ins Heldenraster.

Prüfdauer einstellbar unter *Zeiten & Hotkey → Prüfdauer* (Standard 60 s),
an/aus über den Button „Doppel-Pick-Check“ im Pick-Tab.

## Testen

1. **Erkennung testen** (Tab Konfiguration): prüft alle Templates gegen den aktuellen Bildschirm
   und zeigt die Trefferwerte (ab 0,65 gilt als gefunden).
2. **🧪 Doppel-Pick-Erkennung testen**: startet nur Phase D – ohne zu klicken oder zu tippen.
   Erst den PLANUNG-Bildschirm zeigen, dann zur Heldenauswahl (Suchfeld) wechseln.
   Nach ca. 1–2 s muss „✔ Doppel-Pick ERKANNT“ in der Statuszeile stehen.
   Geht auch ohne Dota: eigene Debug-Screenshots (`debug_*_planung.png`, dann einen mit Heldenauswahl)
   nacheinander im Vollbild bei 100 % öffnen.
3. Normales Spiel (gern Lobby mit Bots): Ablauf A → B → C → D in der Statuszeile verfolgen.

## Wo liegen Templates und Einstellungen?

Im **Google Drive**, nicht neben der EXE – damit jeder PC dieselben Bilder und Presets hat:

```
<Laufwerk>:\Meine Ablage\_060_Projekte\_010_Aktiv\SkadiTerminal\
    skadi_field.png, skadi_auswahl.png, skadi_planung.png, …   (Templates)
    skadi_config.json                                           (Presets, Zeiten)
```

Das Laufwerk (meist `G:`) sucht SkadiTerminal selbst. Die EXE kann irgendwo liegen.
Beim ersten Start holt es fehlende Dateien automatisch aus `Dota2_Draft_Helfer_Maerz` bzw.
`gterminal26` (aus `gterminal_*` wird `skadi_*`; kopiert, nichts wird gelöscht).

Anderer Ordner gewünscht? Eine Textdatei `skadi_datenordner.txt` mit dem Pfad neben die EXE legen.
Ohne Google Drive wird der Ordner der EXE benutzt.

**Andere Auflösung / anderer PC:** Die Templates werden beim Suchen automatisch skaliert
(getestet von 1680×1050 bis 3840×2400). Die passende Skalierung wird pro Auflösung gelernt;
zurücksetzen über *Konfiguration → Skalierung neu lernen*.

**Templates im Repo:** Bilder im Ordner [`templates/`](templates/) werden in die EXE eingebaut
und auf jedem PC automatisch bereitgestellt – auch ohne Google Drive.

## Automatisch starten, wenn Dota läuft (SkadiWaechter)

`waechter/skadi_waechter.pyw` läuft unsichtbar im Hintergrund und startet SkadiTerminal,
sobald `dota2.exe` (oder CS2 & Co.) läuft – **einmal pro Spielsitzung**: Schließt du SkadiTerminal
während des Spiels, bleibt es zu bis zum nächsten Spielstart. SkadiTerminal schließt sich 3 Minuten nach Spielende selbst.
Welche Spiele zählen, steht in **Konfiguration → Spiele-Liste bearbeiten** (gespeichert in `skadi_config.json`);
der Wächter liest dieselbe Liste alle 30 s neu. Dieselbe Liste schließt `Bild↑ + Bild↓` / „✕ Spiele“.
Startet Dota, öffnet der Wächter außerdem **Discord minimiert** (falls nicht schon offen) und
**schließt Discord wieder, wenn Dota beendet wird**. Abschalten: in `skadi_waechter.pyw`
`DISCORD_WITH_GAMES = set()` (gar nicht) bzw. `DISCORD_CLOSE_WITH_GAME = False` (nicht mitschließen).

Der Wächter sucht SkadiTerminal in dieser Reihenfolge:
1. im selben Ordner wie der Wächter (`SkadiTerminal.exe` / `skaditerminal.pyw`)
2. im Google Drive: `…\_010_Aktiv\SkadiTerminal\SkadiTerminal.exe`
3. Notlösung: altes `…\_010_Aktiv\Dota2_Draft_Helfer_Maerz\gterminal.pyw`

**Einrichten:** `build.bat` → aus `dist\` die drei Dateien `SkadiTerminal.exe`, `SkadiWaechter.exe`,
`Autostart_einrichten.bat` in einen Ordner legen (z. B. `…\_010_Aktiv\SkadiTerminal\`) →
`Autostart_einrichten.bat` doppelklicken. Den alten `Prozesswatcher` aus dem Autostart entfernen
(`Win + R` → `shell:startup` → Verknüpfung löschen).

## Einrichten (einmalig pro PC)

`Einrichten.bat` doppelklicken: installiert Python 3.12 (per `winget`, ohne Admin; andere Python-Versionen bleiben unberührt und werden ignoriert, weil es für sie nicht immer fertige Pakete gibt) und alle Pakete
(`pyautogui`, `opencv-python`, `mss`, `pynput`, `pyinstaller`, …) und startet danach auf Wunsch `Aktualisieren.bat`.
Der Microsoft-Store-Platzhalter für `python` wird erkannt und übergangen.

## Aktualisieren (ein Doppelklick)

`Aktualisieren.bat` neben `SkadiTerminal.exe` / `SkadiWaechter.exe` legen und doppelklicken:

1. holt den neuesten Stand von GitHub (mit `git`, sonst als ZIP) nach `%LOCALAPPDATA%\SkadiTerminal\quelle`
2. installiert die Pakete und baut beide EXEs
3. beendet die laufenden Programme, ersetzt die EXEs im Ordner der `.bat` und startet den Wächter neu

Templates, Config und Presets im Datenordner bleiben unberührt. Voraussetzung: einmal `Einrichten.bat` ausgeführt.
Ist eine neuere `Aktualisieren.bat` dabei, liegt sie danach als `Aktualisieren.neu.bat` daneben.

## Bauen

```bat
build.bat
```
Ergebnis: `dist\SkadiTerminal.exe` (Logo ist eingebaut). Am besten nach
`…\_010_Aktiv\SkadiTerminal\` kopieren – dort sucht sie auch der Spielstart-Wächter.
