# CLAUDE.md – Analog-Finder (NASA Space Apps Challenge 2026)

Angelegt von Vicente.

Stand: Sa 14.11.2026, 17:15 MEZ. Deadline: So 15.11.2026, 23:59 Ortszeit (auf der Space-Apps-Seite bestätigen).

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

## Abdeckung der Challenge-Dimensionen (Stand 14.11., 17:15)

Die Challenge nennt acht Dimensionen. Diese Tabelle gehört in ähnlicher Form auf die Projektseite: was passt,
was teilweise, was nicht, und warum.

| # | Dimension (Challenge) | Stand | Abgedeckt durch | Lücke / Grenze |
|---|---|---|---|---|
| 1 | Geologie, Mineralogie, Oberflächenmaterial | ⚠️ teilweise | Albedo, scheinbare thermische Trägheit, Untergrund-Klassen, Umgebungsklassen „dunkles Gestein“ (Basalt) und „Salzpfanne“ (Evaporit) | echte Mineralogie bewusst ausgeschlossen (siehe Entscheidungen); in der Story über Beispielorte zeigen |
| 2 | Gelände, Höhe, Neigung, Rauheit, Krater | ✅ fast vollständig | Copernicus GLO-90: Höhe, Neigung bei 90/100/463 m, Relief, landefreundliche Fläche | keine globale Kraterkarte der Erde in den erlaubten Quellen; bekannte Krater nur in der Analoga-Liste |
| 3 | Temperatur, Beleuchtung, Extreme | ✅ | MODIS-Temperatur 2003–2024, Tagesgang, Jahresgang, Extreme, Frost-Tau, Sonnenstand | echte Beleuchtungskarte nur auf dem Mond (LOLA) |
| 4 | Wasser, Eis, Permafrost, Ressourcen | ⚠️ teilweise | Schnee, Dauereis, Niederschlag, Kälte als Eis-Ersatzwert | ESA-CCI-Permafrost geplant |
| 5 | Staub, Wind, Erosion, Prozesse | ✅ | MERRA-2: Staub-AOD, Staubemission, Staubsturm- und Sturmtage, Wind; Dünenfelder | Erosion nur indirekt (Staubemission); MERRA-2 grob (~55 km) |
| 6 | Biologie, Extremophile, Bewohnbarkeit, Biosignaturen | ❌ schwach | NDVI (Vegetationsfreiheit), Hyperaridität | UV-Strahlung geplant; Biosignaturen aus dem All nicht messbar |
| 7 | Höhlen, Lavaröhren, Untergrund | ❌ fehlt | höchstens Hinweis über Klasse „dunkles Gestein“ (junge Basaltfelder) | keine globalen Daten in den erlaubten Quellen; als Grenze benennen |
| 8 | Landung, Mobilität, Robotik, Bau | ⚠️ teilweise | landefreundliche Fläche, Neigung, Untergrund-Klassen, Stürme, Staub | Erreichbarkeit des Testgeländes geplant (Bevölkerungsdichte) |

### Geplante Ergänzungen der Erdseite (nach dem Höhenmodell-Lauf)

| Merkmal | Quelle (erlaubt) | Wofür | Aufwand |
|---|---|---|---|
| Permafrost | ESA CCI Permafrost (ESA Open Science Catalog) | Dimension 4, ersetzt den Temperatur-Ersatzwert für Bodeneis (Plan, Korrektur 10) | ca. 30 Min. |
| UV-Strahlung | NASA OMI (GES DISC) | Dimension 6: zusammen mit Hyperaridität und Kälte ein Indikator „Grenze des Lebens“ | ca. 1–1,5 Std. |
| Erreichbarkeit | NASA SEDAC Bevölkerungsdichte | Dimension 8: Abgeschiedenheit bzw. Nutzbarkeit als Testgelände | ca. 30 Min. |

## Ideen für den kreativen Ansatz (noch nicht beschlossen)

Die Challenge lädt ausdrücklich zu Statistik, Ähnlichkeitsmetriken, ML und interaktiven Anwendungen ein.

1. **Robustheitskarte (Monte Carlo)** – empfohlen: Scoring 1.000-mal mit zufällig variierten Gewichten; je Ort der
   Anteil der Läufe, in denen er in den Top 50 landet. Trennt robuste von Spezial-Analoga, deckt Prüfung 3 im Plan ab.
2. **Analog-Raum mit ML** – Kür: Clustering der vegetationsfreien Erdzellen ohne unsere Regeln (findet die Maschine
   dieselben Umgebungsklassen?) und 2D-Darstellung des Merkmalsraums, Mond/Mars-Zielorte als Sterne in der Punktwolke.
   Braucht die Zielwerte aus `planetary/targets.json`.
3. **Interaktive Karte mit Zwillingssuche** – Kernprodukt (Rolle C): Ziel wählen, Klick zeigt Profil (Netzdiagramm,
   passt/bricht, Klasse, Flags, Verlässlichkeit A/B/C), Markierung bekannt/NEU, umgekehrte Suche, Worldview-Link.
4. Kleinere Ideen: Steckbriefe für die Top-Neufunde; „Welche Mission würde hier testen?“ aus der stärksten Dimension.

## Offene Vorschläge (warten auf Antwort)

Stehen in `planetary/RESPONSE_REQUIREMENTS.md`; Antwort des Mond/Mars-Teams angefragt bis Sa 17:00.

- [ ] Luftfeuchte (`humidity`) und Mars-Wind (`wind_mean`) aus dem Scoring nehmen (Luftfeuchte wiederholt vor allem
      die Temperatur, für beide gibt es keine Mars-Karte)
- [ ] Neues Merkmal `rock_abundance` (nur Mond, Diviner) für die Untergrund-Klassen 1–4
- [ ] Untergrund-Klassen 1–4 statt eines „bearing capacity“-Werts
- [ ] Deuteronilus Mensae als zweites Mars-Eisziel; Artemis-Kandidatenregionen als weitere Mondziele nach M1
- [ ] Dimensionsgewichte (Team-Meeting)

## Repo-Struktur

```
VERARBEITUNGSPLAN.md  verbindlicher Plan für alle
common/      gemeinsamer Code (terrain.py, body_percentile.py), Änderungen nur nach Absprache
vicente/     Erdseite fein (0,05°, 2003–2024), Kategorien, Scoring; derived/ im Format von data/derived
planetary/   Mond/Mars-Zielwerte: targets.json, Spezifikation, Prüfskript, eigene CLAUDE.md,
             Abgleich mit dem Mond/Mars-Team (REQUIREMENTS_COMPARISON.md, RESPONSE_REQUIREMENTS.md)
scripts/     erste Pipeline (37-km-Zellen), Rückfallebene bis M2
web/         Karte; index.html ist die fertige Karte der ersten Pipeline
data/        kleine Ergebnisdateien (npz, CSV, GeoJSON)
```

Jede Rolle ändert nur ihre Ordner (Plan Abschnitt 6).

Python: rasterio, xarray, numpy, scipy, pyproj, earthaccess. Große Rohdaten nicht ins Repo.

## Rollen

- A – Erddaten (Vicente): MODIS, MERRA-2, Copernicus DEM, Merkmale, Kategorien, Scoring der feinen Pipeline
- B – Mond/Mars (Mert, Jimale; Branch `Mars_and_Moon`): PDS/ODE-Daten, Zielorte, `planetary/targets.json`
- C – Karte + Story: Web-Karte, Projektseite, Demo. Erste Pipeline und Karte bisher von Niko (`scripts/`, `index.html`)
- Offen: feste Zuordnung von C, Projektname

### Wer liefert welche Daten

- **Erde – nur Vicente (A):** alles in `vicente/` und `vicente/derived/` stammt aus Erddaten (NASA MODIS, MERRA-2,
  GPM IMERG; ESA Copernicus DEM). Mond- und Marsdaten werden auf der Erdseite **nicht** heruntergeladen.
- **Mond und Mars – nur das Mond/Mars-Team (B):** LOLA, Diviner, MOLA, TES, OMEGA, Odyssey GRS aus PDS/ODE, eingetragen
  in `planetary/targets.json`. Übersicht der Produkte: `docs/official_sources_audit.md` im Branch `Mars_and_Moon`.
- **Bisher in der Vorlage vorbelegt:** nur physikalisch eindeutige Werte (kein Niederschlag, keine Vegetation, Vakuum),
  berechnete Werte (höchster Sonnenstand) und gerundete Schätzwerte aus `scripts/pipeline.py` (Quelle offen, Note C).
- **Gemeinsam:** `common/terrain.py` und `common/body_percentile.py`, damit beide Seiten gleich rechnen.
  Erst wenn die Planetenwerte eingetragen sind, vergleicht das Scoring in allen Dimensionen.

### Lokale Arbeitsumgebung (Vicente)

- Rohdaten-Ergebnisse und Zwischenstände liegen **nur lokal** in `~/SpaceApps/analog-finder/` (Klimadateien
  `data/earth/clim/*.npz`, Merkmalstabellen `data/earth/earth_features_*.parquet`), nicht im Repo (bis 180 MB pro Datei).
  Für das Team: als GitHub-Release-Anhang bereitstellen (Plan Abschnitt 2).
- `~/SpaceApps/analog-finder/common` ist eine Verknüpfung auf `NASA-Challenge/common`.
- Earthdata-Login liegt in `~/.netrc`; für MERRA-2/IMERG musste die App „NASA GESDISC DATA ARCHIVE“ im Earthdata-Profil
  freigegeben werden.

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
- [x] Erdmerkmale fein, alle 2003–2024: Temperatur (Terra + Aqua), Albedo inkl. schneefrei, Landbedeckung, Schnee, NDVI,
      Gelände (GLO-90 global), MERRA-2 Staub/Staubsturmtage/Wind/Sturmtage/Druck/Feuchte/Niederschlag; im Team-Format in `vicente/derived/`
- [x] Umgebungsklassen kalibriert: 13 von 14 Testorten richtig (Plan, Änderungsprotokoll)
- [x] Gelände bei 100/463 m mit `common/terrain.py` (in Tabelle und `vicente/derived/`)
- [ ] Korrekturen 5, 6, 9–12 aus dem Plan; Ergänzungen Permafrost, UV, Erreichbarkeit
- [x] Schnittstelle Mond/Mars (`planetary/`, Schema 2, Verlässlichkeit A/B/C), gemeinsamer Code (`common/`)
- [x] Abgleich mit dem Mond/Mars-Team: `REQUIREMENTS_COMPARISON.md` (Mert) und `RESPONSE_REQUIREMENTS.md` (Vicente)
- [x] `planetary/targets.json` mit 27 Orten (automatisch, `planetary/compute_targets.py`, von Vicente wegen M1).
      Offen: Mars-Albedo (OMEGA), Staub (TES), Bodeneis (GRS), Mond-Orte nördlich 85° S ohne Diviner, genauere Koordinaten (Gale liegt auf dem Zentralberg, Haworth im Schatten)
- [ ] Antwort auf die offenen Vorschläge (siehe oben)
- [ ] Copernicus-Data-Space-Konto (nur für Sentinel-1 nötig)
- [ ] Ranking, Kontrollen, `results/` für die Karte
- [ ] Web-Karte auf feine Ergebnisse, Projektseite, Demo

## Arbeitsweise mit Claude

- Antworten auf Deutsch; Projektseite und Demo auf Englisch.
- Technisch genau, ehrlich, mit konkreten Zahlen.
- Bei Terminal-Befehlen immer erklären, was sie tun.
- Passwörter und Tokens gibt der Nutzer selbst ein, nicht Claude.
