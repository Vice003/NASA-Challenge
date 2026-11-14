# Favourite Sites and Parameters (Moon/Mars team)

As of 2026-11-14. This document lists the reference sites (favourites) we study on the Moon and Mars and the parameters we derive from lunar and Martian data. The implementation is in [`pds_test.py`](pds_test.py); current data availability is in [`output/parameter_coverage.csv`](output/parameter_coverage.csv).

## 1. Favourite sites

### Moon: Artemis candidate regions (south pole)

The nine regions from NASA's list of 28 Oct 2024 ([NASA](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/)):

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

Later also: Shackleton.

- All regions lie within 6° of the south pole and are each about 15 × 15 km ([NASA 2022](https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-moon/)).
- In the script: region `moon_artemis` = 90°S to 84°S, all longitudes. NASA has not published coordinates for the individual regions.
- Mission status: reports from February 2026 say Artemis III is now an Earth-orbit test flight and the first landing moves to Artemis IV. Confirm on nasa.gov. The nine regions remain our reference set until NASA changes them.

### Mars: base sites with shallow ice

| Site | Extent (planetocentric, 0–360° E) | Script region | Source |
| --- | --- | --- | --- |
| Arcadia Planitia | 34.68–54.68° N, 165.0–217.0° E | `mars_arcadia` | [USGS Gazetteer 348](https://planetarynames.wr.usgs.gov/Feature/348) |
| Deuteronilus Mensae | 39.57–50.17° N, 13.7–35.4° E | `mars_deuteronilus` | [USGS Gazetteer 1509](https://planetarynames.wr.usgs.gov/Feature/1509) |

- Both are named by the SWIM project as areas with shallow ice in the northern mid-latitudes.
- Open: which Exploration Zones from the 2015 NASA workshop to add. Only those with ice resource ROIs are planned.
- `mars_jezero` and `mars_gale` exist in the script as comparison sites. They are rover landing sites, not base favourites.

## 2. Parameters

The parameters come from the published selection criteria of Artemis, the 2015 Mars Exploration Zones and InSight (details in the criteria document "Auswahlkriterien Mond & Mars"). Four categories apply on both bodies and are handed over as Common Base Parameters: **safety, resource, energy, ground**.

### Core parameters

| Script ID | Parameter | Category | Type | Threshold from sources | Transferable to Earth |
| --- | --- | --- | --- | --- | --- |
| `slope` | Slope | Safety | Constraint | Moon 0–5° (study), Mars < 15° (InSight) | yes |
| `roughness` | Roughness | Safety | Constraint | no value; baseline to be agreed with Earth team | yes |
| `rock_abundance` | Rock abundance | Safety | Constraint | Mars ≤ 10 % (InSight) | yes |
| `water_ice` | Accessible water ice | Resource | Preference | Moon: PSR within 2 km EVA radius; Mars: ice near the surface | yes |
| `illumination` | Illumination | Energy | Constraint | Moon: sunlight over 6.5 days; Mars: latitude and dust | partly |
| `bearing_capacity` | Bearing capacity | Ground | Constraint | Mars: thermal inertia > 100–140 SI (InSight) | yes |

### Secondary parameters

| Script ID | Parameter | Note |
| --- | --- | --- |
| `temperature` | Temperature regime | absolute values do not transfer to Earth, only as a process regime |
| `geology` | Geological diversity / mineralogy | kept, but with low weight |

### Filters only (planet-specific, not transferable)

Latitude (Moon ≤ 6° from the pole, Mars ≤ 50° from the equator), elevation for entry and landing (Mars ±2 km), Earth visibility or relay, launch windows, gravity, radiation, atmosphere.

## 3. Data sources per parameter

`PDS registry` = queryable via `pds.peppi`. `PDS archive` = archived as PDS3, download by URL only. `external` = outside the PDS.

| Parameter | Moon | Mars |
| --- | --- | --- |
| Slope | PDS registry: LOLA LDSM (south pole 40 m), LDEM, SLDEM2015 | PDS registry: MOLA MEGDR (slope derived); external: HiRISE DTMs |
| Roughness | PDS registry: LOLA LDRM, Mini-RF | PDS registry: MOLA MEGDR; external: MOLA vertical roughness (ASU, 7.5 km) |
| Rock abundance | PDS registry: Diviner rock abundance (GHRM) | external: Viking IRTM (ASU, **60 km only**) |
| Water ice | PDS registry: Diviner PRP, Mini-RF, LEND; external: LOLA PSR maps (60–240 m) | PDS registry: Odyssey GRS (H₂O, neutrons); external: SWIM (3 km) |
| Illumination | external: LOLA average visibility (60–240 m) | PDS registry: TES dust opacity |
| Bearing capacity | PDS registry: Diviner regolith temperature (GHRM) | PDS archive: TES thermal inertia (3 km); external: THEMIS TI (100 m, up to ±60°) |
| Temperature | PDS registry: Diviner GHRM, PRP, PCP | external: THEMIS night IR, qualitative only |

Exact URLs are in `PARAMETERS` in `pds_test.py` and in `output/parameter_coverage.csv`.

## 4. Open items

- [ ] Confirm Artemis status on nasa.gov
- [ ] Select Mars Exploration Zones with ice ROIs
- [ ] Find a better Mars rock abundance map (TES rock abundance not located)
- [ ] Mars surface temperature: no source yet
- [ ] Agree with the Earth team: roughness baseline, scale per parameter, CSV format
- [ ] Check values at the favourite sites against the background

## Sources

- [NASA: Update on Artemis III Moon Landing Regions (28 Oct 2024)](https://www.nasa.gov/news-release/nasa-provides-update-on-artemis-iii-moon-landing-regions/)
- [NASA: Candidate Regions for Landing Next Americans on Moon (19 Aug 2022)](https://www.nasa.gov/news-release/nasa-identifies-candidate-regions-for-landing-next-americans-on-moon/)
- [Evaluating potential landing sites for the Artemis III mission (arXiv 2406.19863)](https://arxiv.org/html/2406.19863v2)
- [Planetary Society: Humans-to-Mars workshop (2015)](https://www.planetary.org/articles/20151027-humans-mars-workshop)
- [InSight mission description, PDS Geosciences Node](https://an.rsl.wustl.edu/helpNoNav/Content/About%20the%20mission/INS/InSight%20mission.htm)
- [SWIM project (PSI)](https://swim.psi.edu/)
- [USGS Gazetteer of Planetary Nomenclature](https://planetarynames.wr.usgs.gov/)
