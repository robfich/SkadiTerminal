# Templates (mitgeliefert)

**Enthalten:** `skadi_field.png` (Suchfeld) und `skadi_auswahl.png` („Auswählen“), aufgenommen bei 1920 × 1200.
**Fehlt noch:** `skadi_planung.png` – das bisherige Bild war fast komplett schwarz (Schriftzug nicht getroffen)
und wurde deshalb nicht übernommen. Bitte im Spiel neu aufnehmen (Konfiguration → Bild-Templates erfassen → 3. PLANUNG).

Hier liegen die Bild-Templates, die SkadiTerminal mitbringt. Sie werden in die EXE eingebaut
und beim Start in den Datenordner kopiert – aber nur, wenn dort noch keins mit dem Namen liegt.
Eigene Aufnahmen gehen also nie verloren.

## Bilder hinzufügen

Auf GitHub in diesem Ordner **Add file → Upload files** und die PNGs hineinziehen, z. B. aus
`G:\Meine Ablage\_060_Projekte\_010_Aktiv\Dota2_Draft_Helfer_Maerz\`:

| Datei | Wofür |
|---|---|
| `gterminal_field.png` / `skadi_field.png` | Helden-Suchfeld |
| `gterminal_auswahl.png` / `skadi_auswahl.png` | „Auswählen“-Button |
| `gterminal_planung.png` / `skadi_planung.png` | PLANUNG-Schriftzug (Pick erfolgreich) |
| `gterminal_neutral.png` / `skadi_neutral.png` | Leere Stelle im Shop |
| `gterminal_<Set>_<Item>.png` | Item-Bilder, z. B. `gterminal_5_1.png` |
| `skadi_doppelt.png` | optional: Doppel-Pick-Hinweis |

Alte `gterminal_*`-Namen sind ok, sie werden automatisch zu `skadi_*`.
`debug_*`-Bilder bitte **nicht** hochladen.

## Auflösung

Die Bilder müssen **nicht** zur Auflösung des PCs passen: SkadiTerminal skaliert sie beim Suchen
automatisch und merkt sich pro Auflösung, welche Skalierung passt.
Ausgangsauflösung ist die Spielauflösung aus der Config (Standard 1920 × 1200) bzw. der Eintrag in
`skadi_templates.json`, den SkadiTerminal beim Aufnehmen selbst schreibt.
