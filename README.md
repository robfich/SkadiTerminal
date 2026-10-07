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

## Pick-Makro (Taste `Ende`)

| Phase | Was passiert |
|---|---|
| **A** | Wartet auf das Helden-Suchfeld (Bild) bzw. nutzt die kalibrierten Koordinaten und klickt 2x |
| **B** | Tippt die Helden der Reihe nach, ENTER, klickt „Auswählen“, wartet auf PLANUNG |
| **C** | Kauft das aktive Item-Set per Rechtsklick (einmal pro Match) |
| **D** | **Doppel-Pick-Check:** Haben du und das Gegnerteam denselben Helden genommen, wird neu gepickt – mit dem nächsten Helden aus deiner Liste |

Phase D erkennt den Doppel-Pick über
1. das optionale Template `skadi_doppelt.png` (Konfiguration → Bild-Templates → Karte 5), oder
2. Suchfeld wieder sichtbar **und** PLANUNG verschwunden.

Prüfdauer einstellbar unter *Zeiten & Hotkey → Prüfdauer* (Standard 60 s),
an/aus über den Button „Doppel-Check“ im Pick-Tab.

## Testen

1. **Erkennung testen** (Tab Konfiguration): prüft alle Templates gegen den aktuellen Bildschirm
   und zeigt die Trefferwerte (ab 0,65 gilt als gefunden).
2. **🧪 Doppel-Pick-Erkennung testen**: startet nur Phase D – ohne zu klicken oder zu tippen.
   Erst den PLANUNG-Bildschirm zeigen, dann zur Heldenauswahl (Suchfeld) wechseln.
   Nach ca. 1–2 s muss „✔ Doppel-Pick ERKANNT“ in der Statuszeile stehen.
   Geht auch ohne Dota: eigene Debug-Screenshots (`debug_*_planung.png`, dann einen mit Heldenauswahl)
   nacheinander im Vollbild bei 100 % öffnen.
3. Normales Spiel (gern Lobby mit Bots): Ablauf A → B → C → D in der Statuszeile verfolgen.

## Bauen

```bat
build.bat
```
Ergebnis: `dist\SkadiTerminal.exe` (Logo `skaditerminal.ico` ist eingebaut). Templates (`skadi_*.png`) und
`skadi_config.json` liegen neben der EXE.

## Umstieg von Gterminal

Beim ersten Start werden vorhandene `gterminal_*.png` und `gterminal_config.json`
automatisch nach `skadi_*` **kopiert** (die alten Dateien bleiben). Im Launcher,
der Dota überwacht, den EXE-Namen auf `SkadiTerminal.exe` ändern.
