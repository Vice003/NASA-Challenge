# Zielsignaturen: Schnittstelle Mond/Mars → Erd-Scoring

Diese Datei beschreibt, wie die Mond- und Mars-Daten an das Erd-Scoring übergeben werden.
Sie richtet sich an die Teammitglieder, die die Planetendaten aufbereiten, **und an deren Claude**.

Kurz: Pro Zielgebiet wird in **einer JSON-Datei** eingetragen, welche Werte das Gebiet auf Mond oder Mars hat.
Das Erd-Scoring vergleicht jede Erdzelle mit diesen Werten. Prüfen (im Repo-Wurzelordner):
`python planetary/check_targets.py planetary/targets.json`

## Ablage

- Vorlage: [`targets_template.json`](targets_template.json) (alle Felder, Messwerte noch `null`). Zum Start kopieren: `cp planetary/targets_template.json planetary/targets.json`
- Ausgefüllte Datei: **`planetary/targets.json`** im Repo-Wurzelordner (Ordner aus dem Teamplan)
- Prüfskript: [`check_targets.py`](check_targets.py), braucht nur Python ohne Zusatzpakete

## Aufbau

```json
{
  "schema_version": 1,
  "targets": {
    "jezero": {
      "body": "Mars",
      "name": "Jezero-Krater",
      "center_lat": 18.44, "center_lon": 77.45,
      "region": "ca. 100 x 100 km um den Kraterboden",
      "features": {
        "albedo": {
          "value": 0.17, "p10": 0.15, "p90": 0.20,
          "unit": "1", "baseline_m": null, "body_percentile": null,
          "source": "TES Lambert-Albedo, Christensen et al. 2001",
          "notes": ""
        }
      }
    }
  }
}
```

Ziel-IDs (wie in `scripts/pipeline.py`): `shackleton` (Mond), `jezero` (Mars), `arcadia` (Mars).

## Felder pro Merkmal

| Feld | Pflicht | Bedeutung |
|---|---|---|
| `value` | ja (oder `null`) | Median über das Zielgebiet. `null`, solange nicht bestimmt. |
| `p10`, `p90` | empfohlen | 10- und 90-%-Perzentil über das Zielgebiet. Zeigt die Spannweite. |
| `unit` | ja | Genau die Einheit aus der Merkmalsliste unten. Nichts umrechnen lassen, selbst umrechnen. |
| `baseline_m` | bei Gelände | Basislänge in Metern, auf der Neigung und Relief berechnet wurden. |
| `body_percentile` | bei Methode `quantile` | Wo liegt der Wert auf dem **ganzen** Himmelskörper? 0 bis 1, flächengewichtet. |
| `source` | ja, sobald `value` gesetzt | Datensatz und Literatur. Wird im Bericht zitiert. |
| `notes` | nein | Freitext, z. B. Einschränkungen. |

## Merkmalsliste

Der Schlüssel links ist fest. Die Methode sagt, wie verglichen wird, und muss nicht eingetragen werden.

| Schlüssel | Einheit | Methode | Mond | Mars | Erd-Gegenstück |
|---|---|---|---|---|---|
| `slope_p50` | deg | direct | LOLA | MOLA | Hangneigung Median, gleiche Basislänge |
| `slope_p90` | deg | direct | LOLA | MOLA | Hangneigung 90 %, gleiche Basislänge |
| `relief` | m | direct | LOLA | MOLA | Höhenspanne P95 − P5 in 5 × 5 km großen Fenstern, gleiche Basislänge |
| `albedo` | 1 | direct | Diviner/LROC, optional | TES-Albedo | MODIS schneefreie Albedo |
| `thermal_inertia` | J m-2 K-1 s-1/2 | quantile | Diviner | TES-TI | scheinbare thermische Trägheit (ATI) |
| `dust_opacity` | 1 | quantile | – | TES/MCS-Staubopazität | MERRA-2 Staub-AOD |
| `dust_storm_days` | d/yr | quantile | – | optional, MARCI/Literatur | MERRA-2 Staubsturmtage |
| `surface_temp_mean` | K | direction | Diviner | Literatur/TES | MODIS Oberflächentemperatur |
| `surface_temp_min` | K | direction | Diviner | Literatur/TES | kältester Monat nachts |
| `diurnal_range` | K | direction | Diviner | Literatur/TES | Tagesgang |
| `pressure` | hPa | direction | Vakuum: 1e-12 | Literatur | MERRA-2 Luftdruck |
| `wind_mean` | m/s | direction | 0 | Literatur/Modell | MERRA-2 Wind |
| `precip` | mm/yr | direction | 0 | 0 | MERRA-2 Niederschlag |
| `humidity` | g/kg | direction | 0 | Literatur | MERRA-2 spezifische Feuchte |
| `ndvi` | 1 | direction | 0 | 0 | MODIS NDVI |
| `ground_ice` | 1 | direction | Diviner-Eisstabilität | Eiskarten (z. B. SWIM) | Kälte- und Schnee-Proxy |
| `sun_elevation_max` | deg | direct | aus Breite | aus Breite | aus Breite |

**Methoden:**
- `direct`: Gleiche physikalische Größe, gleiche Messweise. Verglichen wird der Wert selbst.
- `quantile`: Gleiches Konzept, aber anderes Instrument oder andere Einheit. Verglichen werden Perzentile:
  Liegt das Zielgebiet z. B. beim 40. Perzentil der Mars-Trägheit, wird es mit Erdzellen beim 40. Perzentil
  der Erd-ATI verglichen. Deshalb ist hier `body_percentile` Pflicht.
- `direction`: Die Erde erreicht den Wert nie (z. B. 6 hPa). Bewertet wird, wie weit eine Erdzelle in diese
  Richtung geht. Der Wert dient außerdem als Grenze der Analogie im Bericht.

## Regeln für die Berechnung

1. **Zielgebiet**: das im Teamplan festgelegte Polygon (ca. 100 × 100 km). `value` ist der Median über alle
   Pixel darin, `p10`/`p90` die Perzentile. Polygon in `region` kurz beschreiben.
2. **Basislänge bei Gelände**: Mond 100 m, Mars 463 m (MOLA-Auflösung), laut Teamplan. Die Erdseite rechnet
   dieselben Basislängen. Wer eine andere Basislänge nimmt, trägt sie in `baseline_m` ein; ohne passendes
   Erdmerkmal wird das Merkmal dann übersprungen.
3. **Neigung**: DEM auf die Basislänge gemittelt bzw. neu abgetastet, dann zentrale Differenzen
   (`numpy.gradient`), in Grad. `slope_p50`/`slope_p90` sind Median und 90-%-Perzentil aller Pixel im Zielgebiet.
   **Relief**: Zielgebiet in 5 × 5 km große Fenster teilen, je Fenster Höhe P95 − P5, davon der Median.
   5 km entspricht der Erdzelle (0,05°).
4. **`body_percentile`**: über den ganzen Himmelskörper, flächengewichtet (Gewicht = cos(Breite) bei
   Gittern in Breite/Länge). Beispiel: Anteil der Mars-Oberfläche mit niedrigerer Trägheit als das Zielgebiet.
5. **Einheiten** exakt wie in der Tabelle. Temperatur in Kelvin, Druck in hPa.
6. **Quellen** immer angeben: Produktname und, falls vorhanden, Literatur.

## Für Claude: verbindliche Regeln

- Keine Werte schätzen oder aus dem Gedächtnis eintragen. Unbekannt bleibt `null`.
- Literaturwerte nur mit vollständiger Quelle (Autor, Jahr, Tabelle/Seite), sonst `null`.
- Schlüssel, Ziel-IDs und Einheiten nicht ändern oder übersetzen. Neue Merkmale nur nach Absprache.
- Nach jeder Änderung `python planetary/check_targets.py planetary/targets.json` ausführen und alle Fehler beheben.
- Nichts außerhalb von `planetary/` ändern. Die Erdseite liegt in `vicente/`, die Team-Pipeline in `scripts/`.
- Werte, die bereits aus `scripts/pipeline.py` vorbelegt sind (Quelle „pipeline.py, gerundet“), prüfen und
  mit einer echten Quelle ersetzen oder bestätigen.

## Was mit den Werten passiert

`vicente/scoring/target_scoring.py` liest die Datei und bewertet jede Erdzelle:

- `direct`: S = 1 − |Erdwert − Zielwert| / Spanne, Spanne = Abstand vom Zielwert zur unähnlichsten Erde
  (2.–98. Perzentil, flächengewichtet). So rechnet auch `scripts/rank.py`.
- `quantile`: dasselbe auf Perzentilen statt Werten.
- `direction`: flächengewichtetes Perzentil in Richtung des Zielwerts.

Die Merkmale werden zu Dimensionen (Gelände, Thermik, Staub, …) gemittelt und gewichtet. Für jede Erdzelle
gibt es den Gesamtwert, die stärkste und die schwächste Dimension. Fehlt ein Merkmal (`null`), zählt es nicht;
die Spalte `coverage` zeigt, wie viel des Gewichts mit Zielwerten belegt ist.
