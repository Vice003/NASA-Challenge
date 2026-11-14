# CLAUDE.md – Analog-Finder (NASA Space Apps Challenge 2026)

Angelegt von Vicente.

Stand: Sa 14.11.2026, 12:00 MEZ. Deadline: So 15.11.2026, 23:59 Ortszeit (auf der Space-Apps-Seite bestätigen).

## Challenge

„Identify Earth Locations that Analog the Permanent Moon Base Locations and Mars“
https://www.spaceappschallenge.org/2026/challenges/permanent-moon-base-locations-and-mars/

Aufgabe: Mit offenen Daten von NASA und Partneragenturen Orte auf der Erde finden und charakterisieren,
die als Analoga für Mondbasen oder Mars-Landeplätze taugen. Ausdrücklich gewünscht: neue, nicht schon
bekannte Analoga; sagen, was passt und wo die Analogie bricht; systematische Methoden sind willkommen.

Projektplan (Claude Doc): https://claude.ai/artifact/Wb2PgZUsBaBur3NUQG5eU7

## Kernidee

Globale, mehrdimensionale Ähnlichkeitssuche statt Einzelort. Jede Erdkachel bekommt pro Dimension einen
Score S_d ∈ [0, 1]. Gezeigt wird immer das Profil pro Dimension; der Gesamtindex dient nur zum Sortieren.
Bekannte Analoga (Atacama, Haughton, Devon Island, Mauna Kea, Island, McMurdo-Trockentäler, Rio Tinto,
Death Valley …) werden markiert, aus dem „Neu“-Ranking genommen und als Positivkontrolle genutzt.

## Zielgebiete (je ~100 × 100 km Polygon)

| Ziel | Körper | Daten |
| --- | --- | --- |
| Südpol-Kraterrand, Shackleton–de-Gerlache-Kamm | Mond | LOLA-Polar-DEM, Diviner PRP, optional Mini-RF |
| Jezero-Krater | Mars | MOLA, TES-Thermalinertia, TES-Albedo |
| Arcadia Planitia (fällt als erstes weg, wenn Zeit knapp) | Mars | MOLA, TES-TI, TES-Albedo/-Staub |

## Entscheidungen (nicht ohne Rücksprache ändern)

- **Nur Datenquellen, die die Challenge-Seite nennt.** Kein Google Earth Engine.
  Erde: NASA Earthdata + ESA Copernicus. Mond/Mars: NASA PDS (bzw. USGS/PGDA-Spiegel der PDS-Produkte).
- **Skalen angleichen:** Jedes Merkmal wird auf beiden Körpern mit gleicher Basislänge berechnet.
  Mond-Vergleiche auf 100 m, Mars-Vergleiche auf 463 m (MOLA-Auflösung).
- **Kacheln:** flächentreues Gitter EASE-Grid 2.0 (`EPSG:6933`). Erde global 10 km. Mond-Ziele 5 km,
  Mars-Ziele 10 km.
- **Grob nach fein:** Stufe 1 global mit MODIS-CMG-Produkten (Thermik, Albedo, Landbedeckung) →
  Kandidatenzonen. Stufe 2 lädt nur dort das Copernicus DEM und rechnet Topographie.
- **Vorfilter:** Kacheln mit > 50 % Wald + Acker + Siedlung + Wasser (MCD12C1-Klassenanteile) fliegen raus.
- **Kein Deep Learning**, keine globale Mineralogie (CRISM/OMEGA) – nicht seriös in 37 h.

## Daten

### Erde
| Produkt | Zweck | Auflösung | Zugang |
| --- | --- | --- | --- |
| MYD11C3 v061 (Aqua) | LST Tag/Nacht, monatlich, 2024 (12 Dateien) | 0,05° | Earthdata, `earthaccess` |
| MCD43C3 v061 | Albedo (BSA/WSA, Kurzwelle), jeweils der 15. jedes Monats 2024 | 0,05° | Earthdata |
| MCD12C1 v061 | Landbedeckung 2022 (neuestes Jahr), Klassenanteile | 0,05° | Earthdata |
| Copernicus DEM GLO-90 | Topographie, nur Kandidatenzonen | 90 m, 1°-Kacheln | Copernicus Data Space (Konto) oder `s3://copernicus-dem-90m` (ohne Konto, gleiches ESA-Produkt) |
| Sentinel-1 (optional) | Radar VH/VV, nur Top-Kandidaten | 10 m | Copernicus Data Space |
| NASA Worldview, Sentinel-2 | visuelle Prüfung der Kandidaten | – | Browser |

Aqua statt Terra: Überflugzeiten (~13:30 / ~01:30) liegen näher an Tagesmax/-min → besser für ATI.

### Mond / Mars
| Produkt | Auflösung | Quelle |
| --- | --- | --- |
| LOLA `LDEM_80S_80MPP_ADJ` (80–90° S) | 80 m, polarstereographisch | https://pgda.gsfc.nasa.gov/products/90 |
| Diviner PRP `DLRE_PRP_SOUTH.TAB` (Jahresmittel/-max T, Eistiefe) | Polargitter, ASCII | PDS / ODE |
| Mini-RF CPR (optional) | – | PDS, Quelle noch offen |
| MOLA DEM global | 463 m, 2 GB | https://planetarymaps.usgs.gov/mosaic/Mars_MGS_MOLA_DEM_mosaic_global_463m.tif |
| TES-Thermalinertia (Putzig & Mellon 2007) | 20 ppd (~3 km) | https://pds-geosciences.wustl.edu/missions/mgs/tes-timap.html |
| TES-Albedo, TES-Staubkarte | 4–8 ppd | https://www.mars.asu.edu/data |

## Merkmale pro Dimension

| Dimension | Merkmale | Erde | Mond | Mars |
| --- | --- | --- | --- | --- |
| Topographie | Slope Median/P90, RMS-Rauigkeit nach Ebenen-Detrending, Höhenspanne | Copernicus DEM → 100/463 m | LOLA → 100 m | MOLA 463 m |
| Thermophysik | Mars: Thermalinertia; Mond: Kälte | ATI = (1 − Albedo) / (T_Tag − T_Nacht); Jahresmin/-mittel LST | Diviner PRP | TES-TI |
| Helligkeit/Staub | Albedo, Staub | MCD43C3; optional MYD08_M3 | – | TES-Albedo/-Staub |
| Radar (optional) | Depolarisation | Sentinel-1 VH/VV | Mini-RF CPR | – |

## Metrik

- Skalare: robuste z-Differenz z = (x_Kachel − x_Ziel) / σ_d, σ_d = MAD über alle Erdkacheln.
- Verteilungen (Slope): 1D-Wasserstein-Distanz der Histogramme, durch σ_d geteilt.
- S_d = exp(−D_d² / 2); S_ges = geometrisches Mittel der S_d (nur zum Sortieren).
- Ranking nur für Kacheln mit S_d > 0,5 in ≥ 2 Dimensionen.
- Validierung: Positivkontrolle (bekannte Analoga oben in ≥ 1 Dimension), Negativkontrolle (feuchte
  Mittelbreiten unten), Robustheit (Top 50 stabil bei 5 vs. 10 km und leicht geänderten Gewichten).
- „Neu“-Filter: 50-km-Puffer um bekannte Analoga.

## Grenzen (gehören auf Projektseite und Demo)

Schwerkraft (Mond 1,62, Mars 3,71 m/s²), Vakuum bzw. ~0,6 kPa Marsatmosphäre (Thermik nur über Proxys),
Sonnenhöhe am Mondpol max. ~1,5°, Strahlung ohne Magnetfeld, Verwitterung durch Wasser und Biologie,
unterschiedliche Instrumente/Wellenlängen (z. B. Sentinel-1 C-Band linear vs. Mini-RF S-Band zirkular).

## Repo-Struktur (geplant)

```
analog-finder/
  earth/      Earthdata- und DEM-Download, Merkmale
  planetary/  Downloads, Reprojektion, Ziel-Signaturen
  scoring/    Metrik, Kontrollen, Ranking
  web/        MapLibre-Karte (GitHub Pages)
  data/       kleine Ergebnisdateien (CSV, GeoJSON)
```

Python: rasterio, xarray, numpy, scipy, pyproj, earthaccess. Große Rohdaten nicht ins Repo.

## Rollen

- A – Erddaten: Accounts, MODIS, Gitter, Thermik-Merkmale, Zonen-Vorauswahl, DEM, Feinanalyse
- B – Mond/Mars + Metrik: Downloads, Reprojektion, Ziel-Signaturen, Scores, Kontrollen, Ranking
- C – Karte + Story: Web-Karte (ab Sa 16:00 mit Platzhalterdaten), Projektseite, Demo
- Offen: Teamgröße, Zuordnung, Projektname

## Zeitplan / Meilensteine

- M1 Sa 20:00 – Ziel-Signaturen und globale Thermik-Merkmale fertig, DEM-Download startet (nachts)
- M2 So 13:00 – Ranking steht, Kontrollen bestanden
- M3 So 22:00 – Einreichung komplett (Puffer bis 23:59)

## Einreichung

- Demo: Video ≤ 30 s mit englischen Untertiteln ODER ≤ 7 Folien auf Englisch, extern öffentlich gehostet.
- Projektseite auf Englisch; genutzte NASA/ESA/CSA/JAXA-Daten explizit nennen.
- Nach der Deadline keine Änderungen möglich.

## Aktueller Stand

- [x] Challenge und Ressourcen gelesen
- [x] Projektplan als Doc
- [x] `download_modis.py` geschrieben (MYD11C3, MCD43C3, MCD12C1 via earthaccess) – noch nicht ausgeführt
- [ ] Earthdata-Login anlegen: https://urs.earthdata.nasa.gov/users/new
- [ ] Copernicus-Data-Space-Konto anlegen: https://dataspace.copernicus.eu
- [ ] Zielpolygone festlegen
- [ ] MODIS-Download ausführen
- [ ] Mond/Mars-Daten laden
- [ ] Merkmalsskripte Erde und Mond/Mars
- [ ] Metrik, Kontrollen, Ranking
- [ ] Web-Karte, Projektseite, Demo

## Arbeitsweise mit Claude

- Antworten auf Deutsch; Projektseite und Demo auf Englisch.
- Technisch genau, ehrlich, mit konkreten Zahlen.
- Bei Terminal-Befehlen immer erklären, was sie tun.
- Passwörter und Tokens gibt der Nutzer selbst ein, nicht Claude.
