# Analog-Finder

Wo auf der Erde sieht es einem Landeplatz auf Mond oder Mars am ähnlichsten?
Der Analog-Finder vergleicht 143.306 Landzellen der Erde (je 20 Bogenminuten, rund 37 km)
in neun Dimensionen mit dem Fingerabdruck eines Zielorts und rankt sie nach Ähnlichkeit.

`index.html` ist die fertige interaktive Karte. Sie läuft ohne Server: Datei im Browser öffnen.

## Zielorte

| Zielort | Lage | Warum |
|---|---|---|
| Mars, Arcadia Planitia | 40° N, 200° O | flache Ebene mit oberflächennahem Eis |
| Mars, Jezero-Krater | 18,4° N, 77,5° O | Landeplatz von Perseverance |
| Mond, Südpol (Shackleton) | 89,7° S | Artemis-Region |

## Dimensionen

| Dimension | Erde | Mond / Mars |
|---|---|---|
| Hangneigung (18,5 km Basis) | ETOPO1 | LOLA, MOLA (gemessen) |
| Relief (Höhenstreuung über rund 90 km) | ETOPO1 | LOLA, MOLA (gemessen) |
| Höchster Sonnenstand | aus Breite und Achsneigung | aus Breite und Achsneigung |
| Jahresmitteltemperatur | WorldClim 2.1 | Literaturwert, gerundet |
| Jahresniederschlag | WorldClim 2.1 | 0 |
| Vegetation (NDVI) | NASA MODIS/Terra MOD13C2, 2023 | 0 |
| Luftdruck | aus der Höhe (Standardatmosphäre) | Literaturwert, gerundet |
| Bodeneis | Schätzung aus der Jahresmitteltemperatur | ja / nein |
| Tag-Nacht-Hub | NASA MODIS/Terra MOD11C3, 2023 | grobe Schätzung |

## Methode

Für jede Dimension gilt: 100 Punkte heißt identisch mit dem Zielort, 0 Punkte heißt so unähnlich
wie die unähnlichste Landfläche der Erde (2. bis 98. Perzentil, flächengewichtet). Die Gesamtnote
ist das gewichtete Mittel, die Gewichte sind in der Karte verstellbar. Liegt ein Zielwert außerhalb
dessen, was die Erde bietet, erreicht keine Zelle 100 Punkte. So zeigt die Zahl, wie weit die
Analogie trägt.

Das Gelände aller drei Körper ist auf dieselbe Wellenlänge (18,5 km) begrenzt, damit Hangneigung
und Relief vergleichbar sind. Gletscher, Eisschelfe und Meer sind ausgeblendet.

Gegenprobe: Die Methode kennt die etablierten Analoge nicht. Für Jezero landet die Atacama auf
Platz 1, für den Mond-Südpol liegen Haughton und die McMurdo-Trockentäler vor 99 bis 100 % der
Landfläche.

## Ergebnis (alle Gewichte gleich)

| Zielort | Bester Treffer | Punkte |
|---|---|---|
| Mars, Arcadia Planitia | Kunlun, Nordtibet | 65 |
| Mars, Jezero-Krater | Atacama | 72 |
| Mond, Südpol | Viktorialand (Antarktis) und Ellesmere Island | 57 |

## Grenzen

- Die Basis von 18,5 km beschreibt Landschaftstypen, keine Landeplätze.
- MODIS/Terra misst gegen 10:30 und 22:30 Uhr Ortszeit. Der wahre Tageshub ist größer.
- Die Zielwerte für Temperatur, Luftdruck, Bodeneis und Tag-Nacht-Hub sind gerundete Schätzungen
  und müssen noch mit Quellen belegt werden.
- Es fehlen Mineralogie, Staub und Untergrund (Lavaröhren).
- Schwerkraft, Vakuum und Strahlung lassen sich auf der Erde nirgends nachbilden.

## Selbst rechnen

```bash
pip install -r requirements.txt
bash scripts/fetch_data.sh data/raw                 # Gelände, Klima, Natural Earth
cp data/derived/*.npz data/raw/                     # fertige MODIS-Ebenen
mkdir -p out
python scripts/pipeline.py data/raw out             # Merkmale und Fingerabdrücke -> out/data.json
python scripts/rank.py out                          # Ranking und Gegenprobe im Terminal
python scripts/build_page.py web/template.html out/data.json index.html
```

Die MODIS-Rohdaten (24 Dateien, rund 1,7 GB) liegen nicht im Repo. Wer die Ebenen in
`data/derived` neu erzeugen will, lädt über [Earthdata Search](https://search.earthdata.nasa.gov/)
die Produkte `MOD11C3` und `MOD13C2` (Version 061, alle Monate 2023) in einen Ordner und ruft auf:

```bash
python scripts/modis_lst.py  ORDNER_MIT_HDF data/raw   # Tag-Nacht-Hub  -> modis_dtr.npz
python scripts/modis_ndvi.py ORDNER_MIT_HDF data/raw   # NDVI-Jahresmittel -> modis_ndvi.npz
```

## Datenquellen

- NASA MODIS/Terra MOD11C3 und MOD13C2, Version 061 (LP DAAC)
- LOLA-Topografie des Mondes, 10 Bogenminuten (fatiando-data)
- MOLA-Kugelfunktionsmodell MarsTopo719 (SHTOOLS-Beispieldaten)
- ETOPO1 (NOAA), 10 Bogenminuten (fatiando-data)
- WorldClim 2.1, bio1 und bio12 (über das R-Paket letsR)
- Natural Earth (Gletscher, Eisschelfe, Regionen, Länder, Orte)

Die Nutzungsbedingungen der einzelnen Quellen gelten weiter. Die Eingangsdaten werden deshalb
per Skript geladen und nicht im Repo verteilt.
