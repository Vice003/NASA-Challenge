# CLAUDE.md – Analog-Finder (NASA Space Apps Challenge 2026)

Angelegt von Vicente.

Stand: Sa 14.11.2026, 13:45 MEZ. Deadline: So 15.11.2026, 23:59 Ortszeit (auf der Space-Apps-Seite bestätigen).

> **Verbindlich für alle Verarbeitungsschritte: [`VERARBEITUNGSPLAN.md`](VERARBEITUNGSPLAN.md).**
> Bei Widerspruch zu dieser Datei gilt der Plan. Vor jeder Arbeit an Daten, Merkmalen, Scoring oder Karte lesen.
> Seit 13:30 geändert: Zielorte 10–20 km statt 100 km · Erdgitter 0,05° flächengewichtet statt EASE-Grid 10 km ·
> Gelände für alle Körper mit `common/terrain.py` · Erdklima 2003–2024 aus Terra + Aqua · eine gemeinsame Metrik ·
> Mond/Mars-Zielwerte über `planetary/targets.json` (Regeln in `planetary/CLAUDE.md`).

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

## Zielorte (10–20 km, siehe VERARBEITUNGSPLAN.md Abschnitt 3)

~~Zielgebiete je ~100 × 100 km Polygon~~ – verworfen am 14.11., 13:30: mischt Kraterrand und Kältefalle bzw.
Kraterboden und Umland, und ist 20-mal größer als die 5-km-Erdzelle.

| ID | Ziel | Körper | Größe | Daten |
| --- | --- | --- | --- | --- |
| `shackleton_rim` | Beleuchteter Kamm Shackleton–de Gerlache | Mond | ca. 15 × 15 km | LOLA-Polar-DEM, Diviner PRP, optional Mini-RF |
| `shackleton_psr` | Dauerhaft beschatteter Kraterboden (optional) | Mond | nach Bedarf | LOLA, Diviner PRP |
| `jezero` | Jezero-Krater, Landestelle/Delta | Mars | ca. 10 × 10 km | MOLA, TES-Thermalinertia, TES-Albedo |
| `arcadia` | Arcadia Planitia (fällt als erstes weg, wenn Zeit knapp) | Mars | ca. 20 × 20 km | MOLA, TES-TI, TES-Albedo/-Staub |

## Entscheidungen (nicht ohne Rücksprache ändern)

- **Nur Datenquellen, die die Challenge-Seite nennt.** Kein Google Earth Engine.
  Erde: NASA Earthdata + ESA Copernicus. Mond/Mars: NASA PDS (bzw. USGS/PGDA-Spiegel der PDS-Produkte).
- **Skalen angleichen:** Jedes Merkmal wird auf beiden Körpern gleich berechnet. Mond-Vergleiche mit
  100-m-Pixeln, Mars-Vergleiche mit 463-m-Pixeln (MOLA). Gelände ausschließlich mit `common/terrain.py`.
- ~~**Kacheln:** EASE-Grid 2.0 (`EPSG:6933`), Erde global 10 km~~ – ersetzt: Erdgitter 0,05° geographisch
  (MODIS-CMG, ca. 5 km), alle Statistiken flächengewichtet mit cos(Breite). Plan Abschnitt 2.
- ~~**Grob nach fein:** DEM nur in Kandidatenzonen~~ – ersetzt: Copernicus GLO-90 ist global verarbeitet
  (`vicente/earth/dem_features.py`), ein Vorfilter würde unbekannte Analoga aussortieren.
- **Vorfilter:** Kacheln mit > 50 % Wald + Acker + Siedlung + Wasser (MCD12C1-Klassenanteile) fliegen raus.
- **Kein Deep Learning**, keine globale Mineralogie (CRISM/OMEGA) – nicht seriös in 37 h.

## Daten

### Erde
| Produkt | Zweck | Auflösung | Zugang |
| --- | --- | --- | --- |
| MOD11C3 + MYD11C3 v061 (Terra + Aqua) | LST, monatlich, 2003–2024, 4 Überflugzeiten | 0,05° | Earthdata, `earthaccess` |
| MCD43C3 v061 | Albedo (WSA, Kurzwelle, auch schneefrei), jeweils der 15. jedes Monats 2024 | 0,05° | Earthdata |
| MCD12C1 v061 | Landbedeckung 2022 (neuestes Jahr), Klassenanteile | 0,05° | Earthdata |
| MOD13C2, MOD10CM v061 | NDVI und Schnee, monatlich, 2003–2024 | 0,05° | Earthdata |
| MERRA-2 | Staub, Staubstürme, Wind, Luftdruck, Feuchte, Niederschlag 2003–2024 | 0,5° × 0,625° | Earthdata (GES DISC) |
| Copernicus DEM GLO-90 | Topographie, global | 90 m, 1°-Kacheln | `s3://copernicus-dem-90m` (ohne Konto) |
| Sentinel-1 (optional) | Radar VH/VV, nur Top-Kandidaten | 10 m | Copernicus Data Space |
| NASA Worldview, Sentinel-2 | visuelle Prüfung der Kandidaten | – | Browser |

Details und Skripte: `vicente/README.md`. ~~Aqua statt Terra~~ – ersetzt: Terra + Aqua, Tagesgang = höchster
minus niedrigster der 4 Überflugwerte (Plan, Korrektur 12). Aqua allein unterschätzt den Tagesgang stärker.

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

Verbindlich: VERARBEITUNGSPLAN.md Abschnitt 5 (eine Implementierung, derzeit `vicente/scoring/target_scoring.py`).
Kurz: `direct` S = 1 − |Erde − Ziel| / Spanne (P2…P98, flächengewichtet, wie `scripts/rank.py`); `quantile` dasselbe
auf Perzentilen gegen vegetations- und eisfreies Land; `direction` für Werte, die die Erde nie erreicht.
Gesamtwert nur zum Sortieren, gezeigt wird das Profil. Masken: Wasser, Eisschild, Wald/Acker/Siedlung.

~~Robuste z-Differenz mit MAD, Wasserstein, S = exp(−D²/2), geometrisches Mittel~~ – nie so umgesetzt
(`scripts/rank.py` rechnet linear mit Spanne); ersetzt durch die Metrik oben.

- Validierung: Positivkontrolle (bekannte Analoga oben in ≥ 1 Dimension), Negativkontrolle (feuchte
  Mittelbreiten unten), Robustheit (Top 20 stabil bei ±25 % Gewichtsänderung). Plan Abschnitt 8.
- ~~„Neu“-Filter: 50-km-Puffer~~ – ersetzt: gemeinsame Liste `data/known_analogs.csv` mit Radius je Ort.

## Grenzen (gehören auf Projektseite und Demo)

Schwerkraft (Mond 1,62, Mars 3,71 m/s²), Vakuum bzw. ~0,6 kPa Marsatmosphäre (Thermik nur über Proxys),
Sonnenhöhe am Mondpol max. ~1,5°, Strahlung ohne Magnetfeld, Verwitterung durch Wasser und Biologie,
unterschiedliche Instrumente/Wellenlängen (z. B. Sentinel-1 C-Band linear vs. Mini-RF S-Band zirkular).

## Repo-Struktur

```
VERARBEITUNGSPLAN.md  verbindlicher Plan für alle
common/      gemeinsamer Code (terrain.py), Änderungen nur nach Absprache
vicente/     Erdseite fein (0,05°, 2003–2024), Kategorien, Scoring; derived/ im Format von data/derived
planetary/   Mond/Mars-Zielwerte: targets.json, Spezifikation, Prüfskript, eigene CLAUDE.md
scripts/     erste Pipeline (37-km-Zellen), Rückfallebene bis M2
web/         Karte; index.html ist die fertige Karte der ersten Pipeline
data/        kleine Ergebnisdateien (npz, CSV, GeoJSON)
```

Jede Rolle ändert nur ihre Ordner (Plan Abschnitt 6).

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
- [x] Projektplan als Doc; verbindlicher `VERARBEITUNGSPLAN.md` (13:30)
- [x] Earthdata-Login angelegt (inkl. Freigabe GES DISC für MERRA-2/IMERG)
- [x] Erste Pipeline mit Karte (`scripts/`, `index.html`, 37-km-Zellen) – Rückfallebene
- [x] Erdmerkmale fein: Albedo, Landbedeckung, Schnee, NDVI, Gelände (GLO-90 global), MERRA-2 Staub/Wind/Druck/Niederschlag
- [ ] Erdmerkmale fein: Temperatur 2003–2024 und Staubsturmtage (laufen), Gelände bei 100/463 m, Korrekturen 4–12 aus dem Plan
- [x] Schnittstelle Mond/Mars (`planetary/`), gemeinsame Geländefunktion (`common/terrain.py`)
- [ ] Zielpolygone (10–20 km) festlegen und `planetary/targets.json` füllen
- [ ] Copernicus-Data-Space-Konto (nur für Sentinel-1 nötig)
- [ ] Ranking, Kontrollen, `results/` für die Karte
- [ ] Web-Karte auf feine Ergebnisse, Projektseite, Demo

## Arbeitsweise mit Claude

- Antworten auf Deutsch; Projektseite und Demo auf Englisch.
- Technisch genau, ehrlich, mit konkreten Zahlen.
- Bei Terminal-Befehlen immer erklären, was sie tun.
- Passwörter und Tokens gibt der Nutzer selbst ein, nicht Claude.
