# CLAUDE.md – Analog-Finder (NASA Space Apps Challenge 2026)

Angelegt von Vicente, Stand Sa 14.11.2026, 12:15 MEZ (Repo-Commit 4c65dfc).
Deadline: So 15.11.2026, 23:59 Ortszeit (auf der Space-Apps-Seite bestätigen).

- Challenge: https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/
- Projektplan (Claude Doc): https://claude.ai/artifact/Wb2PgZUsBaBur3NUQG5eU7

## Challenge in einem Satz

Mit offenen Daten von NASA und Partneragenturen (ESA, CSA, JAXA) Orte auf der Erde finden und
charakterisieren, die als Analoga für Mondbasen oder Mars-Landeplätze taugen. Gewünscht sind neue,
nicht schon bekannte Analoga, eine Begründung, was passt und wo die Analogie bricht, und gern
systematische Methoden.

## Ist-Stand im Repo

Lauffähiger Prototyp, siehe `README.md`.

- 143.306 Landzellen der Erde, je 20 Bogenminuten (~37 km), Gelände auf gemeinsame Basis 18,5 km begrenzt.
- Drei Zielorte: Mars Arcadia Planitia, Mars Jezero-Krater, Mond Südpol (Shackleton).
- Neun Dimensionen: Hangneigung, Relief, höchster Sonnenstand, Jahresmitteltemperatur, Niederschlag,
  NDVI, Luftdruck, Bodeneis, Tag-Nacht-Hub.
- Score pro Dimension: 100 = identisch mit dem Zielort, 0 = so unähnlich wie die unähnlichste
  Landfläche (2.–98. Perzentil, flächengewichtet). Gesamtnote = gewichtetes Mittel, Gewichte in der
  Karte verstellbar.
- Gegenprobe gegen 17 bekannte Analoga in `scripts/rank.py` (Atacama für Jezero auf Platz 1).
- `index.html` = fertige Karte, läuft ohne Server.

Dateien:

```
scripts/fetch_data.sh   Eingangsdaten nach data/raw laden (ohne MODIS)
scripts/modis_lst.py    MOD11C3 -> Tag-Nacht-Hub (data/derived/modis_dtr.npz)
scripts/modis_ndvi.py   MOD13C2 -> NDVI-Jahresmittel (data/derived/modis_ndvi.npz)
scripts/pipeline.py     Merkmale + Fingerabdrücke -> out/data.json
scripts/rank.py         Ranking + Gegenprobe im Terminal
scripts/build_page.py   web/template.html + data.json -> index.html
data/derived/           fertige MODIS-Ebenen (im Repo)
```

Pipeline ausführen:

```bash
pip install -r requirements.txt
bash scripts/fetch_data.sh data/raw
cp data/derived/*.npz data/raw/
mkdir -p out
python scripts/pipeline.py data/raw out
python scripts/rank.py out
python scripts/build_page.py web/template.html out/data.json index.html
```

## Offene Punkte (Abgleich Prototyp ↔ Projektplan)

Diese Punkte sind noch nicht entschieden bzw. umgesetzt. Nicht stillschweigend ändern, erst im Team klären.

1. **Datenquellen.** Im Chat wurde beschlossen, nur Quellen zu nutzen, die die Challenge-Seite nennt
   (NASA Earthdata/Worldview/PDS, CSA RADARSAT, ESA Copernicus, JAXA G-Portal).
   Der Prototyp nutzt zusätzlich nicht gelistete Quellen:
   - ETOPO1 (NOAA) → möglicher Ersatz: Copernicus DEM GLO-90 (ESA)
   - WorldClim 2.1 Temperatur → möglicher Ersatz: MODIS-LST-Jahresmittel (MYD11C3, NASA)
   - WorldClim 2.1 Niederschlag → möglicher Ersatz: GPM IMERG monatlich (NASA Earthdata)
   - LOLA/MOLA kommen über Spiegel (fatiando-data, SHTOOLS); die Originaldaten sind NASA-Missionsdaten,
     in der Einreichung als LOLA/MOLA (PDS) zitieren
   - Natural Earth nur für Masken und Ortsnamen – offen, ob das bleiben darf
2. **Terra statt Aqua.** MOD11C3 misst 10:30/22:30 Ortszeit, der Tag-Nacht-Hub wird unterschätzt
   (steht auch in den Grenzen im README). Aqua (MYD11C3, ~13:30/~01:30) liegt näher an Max/Min.
3. **Zielwerte ohne Beleg.** Temperatur, Luftdruck, Bodeneis und Tag-Nacht-Hub der Zielorte sind
   gerundete Schätzungen. Quellen dafür: Diviner Polar Resource Products (Mond), TES-Thermalinertia
   (Putzig & Mellon 2007), Literatur für Marsdruck (~0,6 kPa).
4. **Auflösung.** 37-km-Zellen beschreiben Landschaftstypen, keine Landeplätze. Plan: Top-Kandidaten
   in einer zweiten Stufe feiner nachrechnen (Copernicus DEM, Mond-Basis 100 m, Mars 463 m).
5. **Fehlende Dimensionen.** Thermalinertia (ATI = (1 − Albedo) / (T_Tag − T_Nacht), mit MCD43C3-Albedo),
   Albedo/Staub, Mineralogie, Untergrund.
6. **Download-Skript.** `download_modis.py` (earthaccess; MYD11C3, MCD43C3, MCD12C1 für 2024 bzw. 2022)
   wurde im Chat erstellt, liegt aber noch nicht im Repo und wurde noch nicht ausgeführt.

## Grenzen (gehören auf Projektseite und Demo)

Schwerkraft (Mond 1,62, Mars 3,71 m/s²), Vakuum bzw. ~0,6 kPa Marsatmosphäre (Thermik nur über
Proxys), Sonnenhöhe am Mondpol max. ~1,5°, Strahlung ohne Magnetfeld, Verwitterung durch Wasser und
Biologie, unterschiedliche Instrumente und Wellenlängen.

## Einreichung

- Demo: Video ≤ 30 s mit englischen Untertiteln ODER ≤ 7 Folien auf Englisch, extern öffentlich gehostet.
- Projektseite auf Englisch, genutzte NASA/ESA/CSA/JAXA-Daten explizit nennen.
- Nach der Deadline keine Änderungen möglich.

## Meilensteine

- M1 Sa 20:00 – Datenquellen geklärt, fehlende Daten geladen
- M2 So 13:00 – Ranking mit belegten Zielwerten steht, Gegenprobe bestanden
- M3 So 22:00 – Projektseite und Demo eingereicht (Puffer bis 23:59)

Offen: Teamgröße, Rollen, Projektname.

## Arbeitsweise mit Claude

- Antworten auf Deutsch; Projektseite und Demo auf Englisch.
- Technisch genau, ehrlich, mit konkreten Zahlen.
- Bei Terminal-Befehlen immer erklären, was sie tun.
- Passwörter und Tokens gibt der Nutzer selbst ein, nicht Claude.
- Große Rohdaten (HDF, NetCDF, data/raw, out/) nicht committen, siehe `.gitignore`.
- Commits von Vicente bzw. in seinem Auftrag mit `[Vicente]` im Betreff kennzeichnen.
