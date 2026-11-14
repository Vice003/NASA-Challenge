# planetary/ – Mond- und Mars-Zielsignaturen

Hier werden die Werte der Zielgebiete auf Mond und Mars eingetragen, mit denen das Erd-Scoring jede
Erdzelle vergleicht. Die vollständige Spezifikation steht in `ZIELSIGNATUREN.md`. **Vor jeder Arbeit hier lesen.**

## Kurzfassung

- Ergebnis gehört in `planetary/targets.json`. Start: `cp planetary/targets_template.json planetary/targets.json`.
- Ziel-IDs `shackleton` (Mond), `jezero` (Mars), `arcadia` (Mars). Merkmalsschlüssel und Einheiten exakt wie in
  `ZIELSIGNATUREN.md`, nicht übersetzen oder umbenennen.
- Pro Merkmal: Median über das Zielgebiet in `value`, dazu `p10`/`p90`, `unit`, `source`.
  Gelände zusätzlich `baseline_m` (Mond 100, Mars 463). Methode `quantile` zusätzlich `body_percentile`
  (flächengewichtet über den ganzen Himmelskörper).
- Nach jeder Änderung prüfen: `python planetary/check_targets.py planetary/targets.json`. Erst fertig bei 0 Fehlern.

## Verbindliche Regeln

- Keine Werte schätzen oder aus dem Gedächtnis eintragen. Unbekannt bleibt `null`.
- Literaturwerte nur mit vollständiger Quelle (Autor, Jahr, Tabelle/Seite).
- Vorbelegte Werte mit Quelle „pipeline.py, gerundet - Quelle offen“ prüfen und mit echter Quelle ersetzen
  oder bestätigen.
- Nur in `planetary/` arbeiten. `vicente/` (Erdseite) und `scripts/` (Team-Pipeline) nicht ändern.
- Große Rohdaten (DEM, PDS-Dateien) nicht committen, nur Skripte und `targets.json`.
- Commit-Nachrichten wie im Team: `[Name] Nachricht`.

## Wie die Werte benutzt werden

`vicente/scoring/target_scoring.py` liest `planetary/targets.json` und bewertet jede Erdzelle
(Methoden `direct`, `quantile`, `direction`, siehe `ZIELSIGNATUREN.md`). Testlauf im Repo-Wurzelordner:
`python vicente/scoring/target_scoring.py planetary/targets.json`
(braucht die Erdtabelle `vicente/data/earth/earth_features_025deg.parquet`, die nur bei Vicente lokal liegt).
