# planetary/

Mond- und Mars-Zielsignaturen für das Erd-Scoring.

| Datei | Inhalt |
|---|---|
| [`ZIELSIGNATUREN.md`](ZIELSIGNATUREN.md) | Spezifikation: Felder, Merkmale, Einheiten, Berechnungsregeln |
| [`targets_template.json`](targets_template.json) | Vorlage für `shackleton`, `jezero`, `arcadia`, Messwerte noch `null` |
| [`check_targets.py`](check_targets.py) | Prüft die ausgefüllte Datei, nur Python ohne Zusatzpakete |
| [`CLAUDE.md`](CLAUDE.md) | Regeln für Claude bei der Arbeit in diesem Ordner |
| `targets.json` | **wird hier angelegt**: die ausgefüllten Werte |

Start im Repo-Wurzelordner:

```bash
cp planetary/targets_template.json planetary/targets.json
```

```bash
python planetary/check_targets.py planetary/targets.json
```
