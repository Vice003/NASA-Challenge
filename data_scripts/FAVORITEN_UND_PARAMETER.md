# Favoriten und Parameter (Mond/Mars-Team)

Stand: 2026-11-14. Dieses Dokument beschreibt, welche Referenz-Sites (Favoriten) wir auf Mond und Mars betrachten und welche Parameter wir aus den Mond- und Marsdaten ableiten. Umgesetzt ist das in [`pds_test.py`](pds_test.py); die aktuelle Datenverfügbarkeit steht in [`output/parameter_coverage.csv`](output/parameter_coverage.csv).

## 1. Favoriten

### Mond: Artemis-Kandidatenregionen (Südpol)

Die neun Regionen aus der NASA-Liste vom 28.10.2024 ([NASA](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/)):

| Region |
| --- |
| Peak near Cabeus B |
| Haworth |
| Malapert Massif |
| Mons Mouton Plateau |
| Mons Mouton |
| Nobile Rim 1 |
| Nobile Rim 2 |
| de Gerlache Rim 2 |
| Slater Plain |

Später zusätzlich: Shackleton.

- Alle Regionen liegen innerhalb von 6° vom Südpol und sind je etwa 15 × 15 km groß ([NASA 2022](https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-moon/)).
- Im Script: Region `moon_artemis` = 90°S bis 84°S, alle Längen. Einzelne Koordinaten der Regionen hat NASA nicht veröffentlicht.
- Stand der Mission: Laut Berichten von Februar 2026 ist Artemis III ein Testflug im Erdorbit, die erste Landung soll mit Artemis IV folgen. Bitte auf nasa.gov bestätigen. Die neun Regionen bleiben unser Referenzsatz, solange NASA sie nicht ändert.

### Mars: Basisstandorte mit oberflächennahem Eis

| Site | Ausdehnung (planetozentrisch, 0–360° E) | Script-Region | Quelle |
| --- | --- | --- | --- |
| Arcadia Planitia | 34.68–54.68° N, 165.0–217.0° E | `mars_arcadia` | [USGS Gazetteer 348](https://planetarynames.wr.usgs.gov/Feature/348) |
| Deuteronilus Mensae | 39.57–50.17° N, 13.7–35.4° E | `mars_deuteronilus` | [USGS Gazetteer 1509](https://planetarynames.wr.usgs.gov/Feature/1509) |

- Beide werden vom SWIM-Projekt als Gebiete mit oberflächennahem Eis in mittleren nördlichen Breiten genannt.
- Offen: welche Exploration Zones aus dem NASA-Workshop 2015 dazukommen. Geplant sind nur die mit Eis-Ressourcen-ROIs.
- `mars_jezero` und `mars_gale` sind im Script als Vergleich vorhanden. Es sind Rover-Landestellen, keine Basis-Favoriten.

## 2. Parameter

Die Parameter stammen aus den veröffentlichten Auswahlkriterien von Artemis, der Mars Exploration Zones 2015 und InSight (Details im Kriteriendokument „Auswahlkriterien Mond & Mars“). Vier Kategorien gelten auf beiden Körpern und werden als Common Base Parameters weitergegeben: **Sicherheit, Ressource, Energie, Boden**.

### Kernparameter

| ID im Script | Parameter | Kategorie | Typ | Schwellwert laut Quellen | Auf Erde übertragbar |
| --- | --- | --- | --- | --- | --- |
| `slope` | Hangneigung | Sicherheit | Constraint | Mond 0–5° (Studie), Mars < 15° (InSight) | ja |
| `roughness` | Rauigkeit | Sicherheit | Constraint | kein Wert; Basislinie mit Erd-Team festlegen | ja |
| `rock_abundance` | Blockdichte | Sicherheit | Constraint | Mars ≤ 10 % (InSight) | ja |
| `water_ice` | Wassereis erreichbar | Ressource | Präferenz | Mond: PSR in 2 km EVA-Radius; Mars: Eis nahe der Oberfläche | ja |
| `illumination` | Beleuchtung | Energie | Constraint | Mond: Sonne über 6,5 Tage; Mars: Breite und Staub | teilweise |
| `bearing_capacity` | Tragfähigkeit | Boden | Constraint | Mars: Thermal Inertia > 100–140 SI (InSight) | ja |

### Nebenparameter

| ID im Script | Parameter | Hinweis |
| --- | --- | --- |
| `temperature` | Temperaturregime | absolute Werte nicht auf die Erde übertragbar, nur als Prozessregime |
| `geology` | Geologische Vielfalt / Mineralogie | wird mitgeführt, aber niedrig gewichtet |

### Nur als Filter (planetenspezifisch, nicht übertragbar)

Breite (Mond ≤ 6° vom Pol, Mars ≤ 50° vom Äquator), Höhe für den Anflug (Mars ±2 km), Erdsichtbarkeit bzw. Relais, Startfenster, Schwerkraft, Strahlung, Atmosphäre.

## 3. Datenquellen je Parameter

`PDS-Registry` = über `pds.peppi` abfragbar. `PDS-Archiv` = als PDS3 archiviert, aber nur per URL ladbar. `extern` = außerhalb der PDS.

| Parameter | Mond | Mars |
| --- | --- | --- |
| Hangneigung | PDS-Registry: LOLA LDSM (Südpol 40 m), LDEM, SLDEM2015 | PDS-Registry: MOLA MEGDR (Hang abgeleitet); extern: HiRISE-DTMs |
| Rauigkeit | PDS-Registry: LOLA LDRM, Mini-RF | PDS-Registry: MOLA MEGDR; extern: MOLA Vertical Roughness (ASU, 7,5 km) |
| Blockdichte | PDS-Registry: Diviner Rock Abundance (GHRM) | extern: Viking IRTM (ASU, **nur 60 km**) |
| Wassereis | PDS-Registry: Diviner PRP, Mini-RF, LEND; extern: LOLA PSR-Karten (60–240 m) | PDS-Registry: Odyssey GRS (H₂O, Neutronen); extern: SWIM (3 km) |
| Beleuchtung | extern: LOLA Average Visibility (60–240 m) | PDS-Registry: TES-Staub-Opazität |
| Tragfähigkeit | PDS-Registry: Diviner Regolith-Temperatur (GHRM) | PDS-Archiv: TES Thermal Inertia (3 km); extern: THEMIS TI (100 m, bis ±60°) |
| Temperatur | PDS-Registry: Diviner GHRM, PRP, PCP | extern: THEMIS-Nacht-IR, nur qualitativ |

Genaue URLs stehen in `PARAMETERS` in `pds_test.py` und in `output/parameter_coverage.csv`.

## 4. Offene Punkte

- [ ] Artemis-Stand auf nasa.gov bestätigen
- [ ] Mars-Exploration-Zones mit Eis-ROIs auswählen
- [ ] Bessere Mars-Blockdichte suchen (TES-Rock-Abundance nicht gefunden)
- [ ] Mars-Oberflächentemperatur: Quelle fehlt
- [ ] Mit Erd-Team abstimmen: Rauigkeits-Basislinie, Skala je Parameter, CSV-Format
- [ ] Werte an den Favoriten gegen den Hintergrund prüfen

## Quellen

- [NASA: Update on Artemis III Moon Landing Regions (28.10.2024)](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/)
- [NASA: Candidate Regions for Landing Next Americans on Moon (19.08.2022)](https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-moon/)
- [Evaluating potential landing sites for the Artemis III mission (arXiv 2406.19863)](https://arxiv.org/html/2406.19863v2)
- [Planetary Society: Humans-to-Mars workshop (2015)](https://www.planetary.org/articles/20151027-humans-mars-workshop)
- [InSight-Missionsbeschreibung, PDS Geosciences Node](https://an.rsl.wustl.edu/helpNoNav/Content/About%20the%20mission/INS/InSight%20mission.htm)
- [SWIM-Projekt (PSI)](https://swim.psi.edu/)
- [USGS Gazetteer of Planetary Nomenclature](https://planetarynames.wr.usgs.gov/)
