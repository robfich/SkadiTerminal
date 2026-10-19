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

Vom Wächter gestartet schließt sich SkadiTerminal, sobald das Spiel beendet ist; von Hand gestartet bleibt es offen.

## Pick-Makro (Taste `Ende`)

| Phase | Was passiert |
|---|---|
| **A** | Wartet auf das Helden-Suchfeld (Bild) bzw. nutzt die kalibrierten Koordinaten und klickt 2x |
| **B** | Tippt die Helden der Reihe nach, ENTER, klickt „Auswählen“, wartet auf PLANUNG oder den Item-Shop |
| **C** | Kauft die **Startitems des gepickten Helden** per Rechtsklick im Shop (siehe unten) |
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

## Was wird ins Suchfeld getippt?

Nicht das Kürzel, sondern der **Anfang des vollen Heldennamens** – mindestens 4 Buchstaben und so lang,
dass kein anderer Held diese Buchstabenfolge im Namen hat (Dota sucht nach Namensteilen, „pa“ fände
sonst Pangolier). Beispiele: `pa` → „phantom a“, `pl` → „phantom l“, `sf` → „shadow f“, `wk` → „wrai“,
`jugg` → „jugg“. Beim Überfahren eines Helden steht in der Hinweiszeile, was getippt wird.
Eigene Begriffe sind in `skadi_config.json` unter `"search_terms": {"pa": "phantom assassin"}` möglich.

## Startitems pro Held (Drag & Drop)

**Rechtsklick auf einen Helden → „Items hinzufügen …“** öffnet den Item-Editor:

- Items aus dem Shop unten in die Kaufliste ziehen (oder doppelklicken)
- in der Liste ziehen = Reihenfolge ändern · rausziehen oder Rechtsklick = entfernen
- Helden mit Items haben im Raster einen Punkt: `wk •`

Nach dem Pick wartet Phase C auf den Shop („Startgegenstände“) und kauft die Liste der Reihe nach per
Rechtsklick. Gesucht wird in Farbe (Observer/Sentry Ward werden nicht verwechselt), das Inventar links
wird ignoriert, gestreckte Auflösungen (1920×1200 auf 2560×1440) funktionieren.
An/aus: Schalter **„Startitems kaufen“** im Pick-Tab.

Die Item-Bilder liegen in `items/` (aus einem Shop-Screenshot in 1920×1200 ausgeschnitten,
`items/match/` = oberer Teil ohne Lagerzahl für die Suche) und werden in die EXE gepackt.
Neue Items: Bild nach `items/<key>.png`, oberen Teil nach `items/match/<key>.png`, Eintrag in `items/items.json`.

## Helden-Icons

Im Helden-Raster, im Held-Pool und in der Startitem-Auswahl steht vor jedem Kürzel das Minimap-Icon;
der volle Name erscheint beim Überfahren in der Hinweiszeile über den Presets (bewusst ohne
Tooltip-Fenster – die blitzten unter Windows ständig auf). Die Icons stammen aus
[bontscho/dota2-minimap-hero-sprites](https://github.com/bontscho/dota2-minimap-hero-sprites) (MIT,
Bilder © Valve) und liegen in `items/heroes/<kürzel>.png`. Neuere Helden, die dort fehlen
(Primal Beast, Muerta, Marci, Kez, Ringmaster, Largo), werden ohne Icon angezeigt.

## Dota-Einstellungen mitnehmen (Button „D2 Settings“)

Deine Dota-Einstellungen sind ins Programm eingebaut (`items/dota_settings/` – Tasten, Spieleinstellungen,
Grafik, Hero-Builds, Kontrollgruppen, Chat). Das Fenster „D2 Settings“ zeigt:

- **Meine Einstellungen** – „Als Ordner speichern …“ legt die Ordner `local` + `remote` (plus LIESMICH)
  an einen Ort deiner Wahl; „Backups öffnen“ zeigt die automatischen Sicherungen.
- **Steam-Accounts auf diesem PC** (aus `Steam\userdata\<Account-ID>\570`, mit Namen aus
  `loginusers.vdf`):
  - **Übernehmen** – kopiert die Einstellungen auf diesen Account (Dota muss zu sein; vorher wird
    ein ZIP-Backup nach `dota_backups/` im Datenordner geschrieben). Fragt Steam beim nächsten Start
    nach einem Cloud-Konflikt: „Lokale Dateien“ behalten.
  - **Sichern** – speichert die aktuellen Einstellungen dieses Accounts als *deine* Einstellungen im
    Google-Drive-Datenordner (`dota_settings/`); die haben danach Vorrang vor den eingebauten.
- **Steam-ID umrechnen** – SteamID64, `[U:1:…]`, `STEAM_0:…`, Freundes-/Account-ID oder Dotabuff-/Stratz-/
  Steam-Profil-Link einfügen → alle Formen zum Kopieren + Links zu Steam, Dotabuff, Stratz, OpenDota.

Nicht enthalten (bewusst, das Repo ist öffentlich): Freundesliste, Stummschalt-Liste, Statistiken,
letztes Match, Steam-Cloud-Verwaltung (`remotecache.vdf`).

## Was wird gespeichert?

Alles in `skadi_config.json` im Datenordner (Google Drive) – **sofort bei jeder Änderung**, nicht erst beim
Beenden: Auswahl (wird beim nächsten Start wiederhergestellt), Presets, Startitems pro Held, Schalter,
Zeiten, Spiele-Liste. Gespeichert wird über eine Hilfsdatei, damit die Config auch heil bleibt, wenn das
Programm mitten im Schreiben beendet wird.

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
während des Spiels, bleibt es zu bis zum nächsten Spielstart. Spiel zu = SkadiTerminal zu.
Welche Spiele zählen, steht in **Konfiguration → Spiele-Liste bearbeiten** (gespeichert in `skadi_config.json`);
der Wächter liest dieselbe Liste alle 30 s neu. Dieselbe Liste schließt `Bild↑ + Bild↓` / „✕ Spiele“.
Startet Dota, öffnet der Wächter außerdem **Discord minimiert** (falls nicht schon offen); Discord
bleibt danach offen. Abschalten: in `skadi_waechter.pyw` `DISCORD_WITH_GAMES = set()`.
**Endet das Spiel, schließt der Wächter SkadiTerminal** (nur wenn er es selbst gestartet hat –
von Hand geöffnet bleibt es offen).

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

## Versionen auf GitHub

| Branch | Inhalt |
|---|---|
| `main` | stabile Version – holt `Aktualisieren.bat` |
| `final` | gesicherter Stand 1.0 (vor der Item-Funktion), wird nicht mehr verändert |
| `workinprogress` | Testversion mit den neuesten Funktionen – holt `Aktualisieren_WIP.bat` |

Zurück zur stabilen Version: einfach wieder `Aktualisieren.bat` starten.

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
