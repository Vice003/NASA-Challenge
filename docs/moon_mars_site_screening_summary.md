# Moon & Mars site screening – summary (scoring system v2)

Status: 2026-11-15 · Branch `Mars_and_Moon` · Team R6 BL-Stuttgart (Moon & Mars side)

Goal: find candidate areas for a base on the **lunar south pole** and on **Mars** using only
parameters that the official challenge sources deliver with reliability **A or B**
(see `docs/official_sources_audit.md`), and show how they compare with the sites NASA and
other agencies picked. The candidate areas are the targets for the Earth-analog search.

Scope decisions:
- **Moon: south pole only (85–90° S).** The earlier whole-Moon screen is retired (section 8).
- **Mars: whole planet within ±50° latitude** (Mars Exploration Zone criterion).
- The results are **areas**, not landing spots. The data cannot certify a landing site (section 6).

---

## 1. The program

| Script | What it does |
|---|---|
| `pds_test.py` | asks the PDS registry (`pds.peppi`) which products exist for 14 curated datasets; writes metadata only |
| `landing_sites.py` | reference lists: `SITES` (41 + 3 points: landings, finalists, study areas), `MOON_SOUTH_AREAS` (NASA Artemis regions as rough areas), `MARS_STUDY_AREAS` (human-base study areas as boxes). Run on its own it counts PDS products per site |
| `moon_screen.py` | lunar south pole at 240 m |
| `mars_screen.py` | Mars at ~3.7 km (16 px/deg) |
| `moon_global_screen.py` | **retired**, kept for reference |

Both screening scripts follow the same five steps:

1. **Read** the raw PDS files with numpy (scale, offset and size from the labels).
2. **Grid:** reduce every layer to one grid, with statistics per cell.
3. **Limits:** a cell that fails any hard limit is dropped ("usable cells" are the rest).
4. **Score:** each usable cell gets a weighted sum of 0..1 terms.
5. **Sites:** the best 1–2 % of the usable cells are grouped where they touch; the best cell
   of each group of at least 4 cells is reported as the site, groups closer than a minimum
   distance to a better one are dropped.

Each run writes `candidates.csv`, `nasa_vs_candidates.csv` (the agencies' areas under the
same scoring, next to the candidates) and `map.png` to `data_scripts/output/<body>/`.
The current files are in `data_scripts/results_moon_mars.zip`.

---

## 2. Scoring system – Moon south pole (`moon_screen.py`)

Grid: 240 m polar stereographic, 85–90° S. 45,278 cells are usable (3.6 % of the cap).

**Hard limits**

| Limit | Value | Data |
|---|---|---|
| Slope | mean ≤ 5° and P90 ≤ 10° per cell, 40 m baseline | LOLA LDSM_85S_40M |
| Slope data | ≥ 30 % of the cell's 40 m pixels measured (69 % of all pixels are gaps between tracks) | LOLA LDSM |
| Not in permanent shadow | shadowed fraction < 5 % | LOLA LPSR_85S_060M |
| Sunlight | average sun visibility of the cell ≥ 30 % | LOLA AVGVISIB_85S_060M |
| Inside the grid | latitude ≤ −85° (the map corners have no Diviner data) | – |

**Score**

| Term | Weight | How it is computed | Data |
|---|---|---|---|
| Sunlight | 0.35 | best-lit 60 m pixel of the cell, stretched: 0 at the 30 % minimum, 1 at the best usable cell on the map (0.86) | LOLA AVGVISIB |
| Ice access | 0.30 | exp(−d / 2 km), d = distance to the nearest surface cold trap (ice stable at the surface) | Diviner polar resource product |
| Slope | 0.15 | 1 − mean slope / 5° | LOLA LDSM |
| Roughness | 0.10 | 1 − roughness / 95th percentile | LOLA LDRM_85S_40M |
| Earth visibility | 0.10 | average Earth visibility | LOLA AVGVISIB (Earth) |

Why the best-lit pixel: the cell average differs very little between usable cells
(0.30–0.62), so with the raw average the top sites had the same sunlight as an average
usable cell (0.38) and distance to a cold trap decided everything. The best-lit pixel is
where a solar array would stand. `--sun-measure raw` reproduces the old list.

**Sites:** best 2 % of the usable cells, groups ≥ 4 cells (0.23 km²), 5 km apart, top 25.
A site is "novel" when it lies outside every NASA rough area.

**NASA comparison:** NASA has not published region outlines that we could retrieve. Each
Artemis region is therefore a rough area: an anchor plus a radius large enough to contain
the ~15 × 15 km region. Where the anchor is a crater centre (permanently shadowed: an ice
target, never a landing site) the radius is crater radius + 10 km so that it reaches the
sunlit rim.

---

## 3. Scoring system – Mars (`mars_screen.py`)

Grid: 16 px/deg (~3.7 km at the equator). 31.7 % of the grid cells are usable.

**Hard limits**

| Limit | Value | Data |
|---|---|---|
| Latitude | within ±50° (Exploration Zone criterion; excludes Phoenix-type sites for power and season, not for ground properties) | – |
| Elevation | ≤ +2 km (entry, descent, landing) | MOLA MEGDR 128 px/deg |
| Slope | P90 ≤ 15° at 463 m baseline (regional filter only) | MOLA |
| Thermal inertia | 140–1500 (below 140: thick dust; InSight used 100–140) | TES night thermal inertia 2007 |

**Two site classes, ranked separately**

| Class | Latitude | What the water signal means |
|---|---|---|
| E – equatorial | below 35° | hydrogen mostly bound in hydrated minerals |
| M – mid-latitude | 35–50° | shallow ground ice expected (not proven by this dataset alone) |

35° is about the lowest latitude at which a fresh impact has exposed ground ice
(Dundas et al. 2023 – verify before citing). With one common ranking the equatorial
hydrated-mineral signal pushed every mid-latitude ice area out of the list.

**Score** (weights sum to 1)

| Term | Weight | How it is computed | Data |
|---|---|---|---|
| Water | 0.41 | percentile rank of water-equivalent hydrogen within the class | Odyssey GRS H₂O, 5° bins |
| Slope | 0.18 | 1 − P90 slope / 15° | MOLA |
| Sunlight | 0.18 | annual-mean insolation relative to the equator, from latitude | computed |
| Roughness | 0.12 | 1 − relief (P95 − P5 per cell) / 95th percentile | MOLA |
| Low dust | 0.12 | 1 − percentile rank of the surface-dust index | OMEGA nanophase ferric oxide |

- **Thermal inertia is pass/fail only.** As a preference it rewarded values up to 400 and
  with them rockier ground (`--ti-in-score` restores it).
- **A layer without data counts as average** (median of the class) and is listed in
  `params_missing`. Dropping it and re-weighting the rest favoured exactly the cells without
  dust data: 21 % of the usable mid-latitude cells, but 81 % of the best ones
  (`--drop-missing` restores that).
- **Water error:** the GRS error (1 σ, including correction factors) is carried along.
  `score_lo` / `score_hi` are the score for water −/+ 1 σ. Tier 1 = the site cannot be told
  apart from the best site of its class.

**Sites:** per class the best 1 % of the usable cells, groups ≥ 4 cells, 150 km apart,
top 15. "Novel" = more than 200 km from every known site and outside the study-area boxes
(Arcadia Planitia, Deuteronilus Mensae).

---

## 4. Data

All data are official NASA PDS archives, no account needed.

1. **Search:** `pds.peppi` (PDS Registry API) and the PDS Geosciences ODE REST API
   (`oderest.rsl.wustl.edu/live2`) for products not in the registry (LOLA illumination and
   shadow maps, TES thermal inertia, OMEGA maps).
2. **Download:** direct HTTPS from the PDS Geosciences Node; URLs are in the `urls.txt` of
   each `output/raw/*` folder (not in git).
3. **Checks done:**
   - projection: named craters fall on shadow pixels; MOLA elevations at ten lander sites
     match the commonly cited values to about 20 m; TES thermal inertia at Pathfinder and
     Viking 1 is close to the published landing-site values;
   - LOLA slope DN 0 marks gaps between tracks (69 % of pixels, 21 % near the pole, 77 % at
     85° S) and is masked;
   - Diviner `ice_depth` −999 = "deeper than 2.87 m", undocumented −1 = surface-stable.

| | Downloaded | Main files |
|---|---|---|
| Moon – south pole | 0.94 GB | Diviner polar resource product south 605 MB, LOLA slope / roughness 85S 115 MB each, illumination / shadow 85S 51 MB each |
| Mars | 2.9 GB | 16 MOLA tiles 2.1 GB, OMEGA maps 3 × 207 MB, TES thermal inertia 2 × 52 MB, GRS < 1 MB |

How precise the layers are:

| Layer | Grid | Limit |
|---|---|---|
| LOLA slope (Moon) | 40 m | 69 % of pixels unmeasured; baseline 30–120 m |
| LOLA sunlight / shadow | 60 m | computed from the elevation model, at ground level |
| Diviner cold traps | ~0.5 km | temperature measured; ice depth is a thermal model |
| MOLA elevation | 463 m | no lander-scale slopes |
| TES thermal inertia | 3 km | not reliable at high latitude |
| GRS water | 5° bins, smoothed over 10° (~600 km) | ± 0.5–0.8 wt% at the candidates, top metre only |

Run time on the team laptop (7 GB RAM) from the cached features: south pole ~10 s,
Mars ~5 min. The `features.npz` caches are not in git; rebuild with `--rebuild`.

---

## 5. Results

### Moon – south pole (25 sites)

| Rank | Location | Score | Sunlight (cell average / best spot) | Earth view | Cold trap | NASA area |
|---|---|---|---|---|---|---|
| 1 | 88.86° S, 132.2° E | 0.556 | 0.52 / 0.72 | 0.53 | 1.6 km | Peak near Shackleton |
| 2 | 86.97° S, 127.9° E | 0.554 | 0.52 / 0.56 | 0.45 | 1.0 km | – (own; plain 14 km outside the Slater area) |
| 3 | 87.89° S, 169.1° E | 0.548 | 0.39 / 0.47 | 0.39 | 0.5 km | – (own) |
| 4 | 85.52° S, 120.7° E | 0.519 | 0.42 / 0.44 | 0.32 | 0.5 km | – (own) |
| 5 | 86.99° S, 135.3° E | 0.514 | 0.47 / 0.59 | 0.39 | 1.0 km | – (own; same plain as 2) |
| 6 | 89.45° S, 223.3° E | 0.504 | 0.54 / 0.86 | 0.57 | 5.9 km | Connecting Ridge |
| 7 | 87.75° S, 264.3° E | 0.489 | 0.45 / 0.49 | 0.54 | 1.5 km | de Gerlache Rim 2 |
| 8 | 87.18° S, 140.8° E | 0.488 | 0.32 / 0.35 | 0.37 | 0.5 km | – (own) |

- 7 of the 25 sites lie inside NASA areas, 18 outside.
- Medians of the 25: sunlight 0.43 (best spot 0.49), Earth view 0.51, slope 2.4°, cold trap 1.1 km.

NASA's areas under the same scoring (best usable cell of each area):

| NASA area | List | Usable ground | Score | Rank it would take | Sunlight (average / best spot) | Cold trap |
|---|---|---|---|---|---|---|
| Peak near Shackleton | 2022 | 5.4 % | 0.575 | 1 | 0.62 / 0.86 | 4.8 km |
| Connecting Ridge | 2022 | 0.4 % | 0.531 | 4 | 0.50 / 0.79 | 1.7 km |
| Nobile Rim 1 | 2024 | 0.9 % | 0.512 | 6 | 0.58 / 0.77 | 4.0 km |
| de Gerlache Rim 2 | 2024 | 1.6 % | 0.512 | 6 | 0.57 / 0.83 | 6.0 km |
| Slater Plain | 2024 | 1.7 % | 0.470 | 12 | 0.34 / 0.38 | 0.2 km |
| Malapert Massif | 2024 | 0.4 % | 0.447 | 20 | 0.56 / 0.70 | 11.2 km |
| Haworth | 2024 | 0.4 % | 0.435 | 25 | 0.48 / 0.59 | 2.1 km |
| Faustini Rim A | 2022 | 0.1 % | 0.311 | below 25 | 0.33 / 0.45 | 3.9 km |

Nobile Rim 2, Mons Mouton, Mons Mouton Plateau and Peak near Cabeus B lie outside the
85° S grid and are not scored. An area's best cell can score higher than any site inside
it because a site needs at least 4 touching cells.

### Mars – equatorial class (15 regions)

All 15 lie in one belt east of Meridiani Planum: 0–23° E, 11° S–9° N.

| ID | Location | Score (range from water error) | Water | Thermal inertia | Elevation | Group size |
|---|---|---|---|---|---|---|
| E1 | 0.6° S, 6.8° E | 0.983 (0.956–0.993) | 6.3 ± 0.6 wt% | 187 | −1.0 km | 145,816 km² |
| E2 | 2.3° N, 2.8° E | 0.979 (0.952–0.985) | 6.4 ± 0.6 wt% | 214 | −1.4 km | 19,281 km² |
| E3 | 4.2° S, 19.5° E | 0.978 (0.954–0.993) | 6.2 ± 0.5 wt% | 148 | −0.4 km | 616 km² |

### Mars – mid-latitude class (15 regions)

Six lie inside Arcadia Planitia (M2, M7, M9, M11, M13, M15) and four on its edges
(M3, M6, M8, M14); four lie at the northern edge of Arabia Terra (M1, M4, M5, M12) and one
in Utopia (M10).

| ID | Location | Score (range from water error) | Water | Thermal inertia | Elevation | Group size |
|---|---|---|---|---|---|---|
| M1 | 35.0° N, 343.5° E | 0.919 (0.840–0.943) | 5.2 ± 0.6 wt% | 230 | −4.2 km | 55,854 km² |
| M2 | 38.6° N, 203.1° E | 0.912 (0.837–0.959) | 5.0 ± 0.6 wt% | 196 | −3.9 km | 17,453 km² (inside Arcadia, 165 km from its centre) |
| M3 | 49.9° N, 162.8° E | 0.909 (0.825–0.911) | 5.4 ± 0.7 wt% | 260 | −3.9 km | 212 km² |

All 30 regions are tier 1: within the water map's error none can be told apart from the
best of its class. Read the lists as regions, not as rankings.

Agency sites under the same scoring (best usable cell within 50 km, percentile within the class):

| Site | Class | Score | Percentile |
|---|---|---|---|
| Gusev (Spirit) | E | 0.961 | 100.0 |
| Meridiani (Opportunity) | E | 0.935 | 99.4 |
| Gale (Curiosity) | E | 0.930 | 99.3 |
| Mawrth Vallis | E | 0.874 | 96.9 |
| Arcadia Planitia | M | 0.843 | 95.4 |
| Deuteronilus Mensae | M | 0.840 | 94.9 |
| Elysium (InSight) | E | 0.820 | 89.7 |
| Utopia (Viking 2) | M | 0.777 | 82.5 |
| Oxia Planum (ExoMars) | E | 0.776 | 80.1 |
| Jezero (Perseverance) / NE Syrtis | E | 0.683 | 57.5 |
| Eberswalde | E | 0.663 | 52.2 |
| Holden | E | 0.631 | 43.6 |
| Ares Vallis (Pathfinder) | E | 0.622 | 41.2 |
| Utopia (Zhurong) | E | 0.619 | 40.3 |
| Chryse (Viking 1) | E | 0.555 | 23.2 |
| Phoenix | – | outside the ±50° limit | – |

---

## 6. Limitations (state these in the submission)

**Moon**
1. **Length of the longest night is not scored.** No such product exists in the LOLA
   archive (only average sunlight, permanent shadow, sky visibility); it would have to be
   computed from the elevation model. Average sunlight does not tell how long the night is.
2. **The best-lit pixel describes where power would come from, not the whole site.**
   Connecting Ridge has 0.86 at its best spot but 0.54 on average. Sites are small
   (0.2–2.3 km²).
3. **Four NASA regions lie outside the 85° S grid** (Nobile Rim 2, Mons Mouton, Mons Mouton
   Plateau, Peak near Cabeus B). The 75° S LOLA products (slope, illumination, shadow) would
   allow an extension.
4. **NASA areas are rough areas, not NASA's outlines.** The Slater Plain anchor is
   unverified. Large radii flatter NASA's side (best cell anywhere in the circle).
5. **Sites 17 and 21 have no view of Earth** (Earth visibility is only a 0.10 preference).
6. **Slope rests on 30–80 % of a cell's pixels**, the rest are gaps between LOLA tracks.

**Mars**
7. **Water map resolution and error:** about 600 km after smoothing, ± 0.5–0.8 wt%, top
   metre only. It decides the region, not the cell; all 30 regions are tied within the error.
8. **Equatorial water is hydrated minerals, not ice.** Mid-latitude ice is expected, not
   shown, by GRS. Sites M1 and M4 lie within 1° of the class boundary, where the
   hydrated-mineral signal of Arabia Terra may still dominate.
9. **Thermal inertia limit (open decision):** 13 of the 30 regions have a thermal inertia
   below 181, the lowest value at any agency site in our comparison. Raising `--min-ti`
   from 140 to 180 would remove them.
10. **Slope at a 463 m baseline** passes 96 % of the planet and says nothing at lander scale.
11. **Groups are split at the 0°/360° meridian**, so group sizes next to it are under-reported.

**Both**
12. **Not scored (no A/B source):** rock abundance (Moon poles, Mars), Mars dust storms and
    dust dimming of sunlight, Mars surface temperature.
13. **Scores depend on the weights.** With weights varied by ±50 % the best 1–2 % of the
    cells overlapped by about 80–85 % (tested on the previous version).
14. **Earth's limits as an analog** (gravity, vacuum / thin CO₂ atmosphere, radiation) are
    not part of this screening; they belong in the Earth-comparison step.

---

## 7. Reproduce

```bash
cd data_scripts
.venv/bin/python moon_screen.py    # south pole, needs output/raw/moon
.venv/bin/python mars_screen.py    # Mars, needs output/raw/mars
```

Switches back to the previous system:

| Switch | Effect |
|---|---|
| `moon_screen.py --sun-measure raw` | sunlight as raw cell average |
| `mars_screen.py --max-abs-lat 88` | no latitude limit |
| `mars_screen.py --ice-lat 99` | one site class |
| `mars_screen.py --ti-in-score` | thermal inertia as a preference |
| `mars_screen.py --drop-missing` | drop layers without data and re-weight |

---

## 8. Retired: whole-Moon screen

`moon_global_screen.py` searched the whole Moon and put its best sites on the north polar
near side (67–86° N). That result is not supported and the script is no longer used:

- "Ice access" was the distance to any permanently shadowed pixel. For the 10 northern
  candidates covered by the Diviner polar resource product there is no cold trap within
  2 km (lowest peak temperature 172–245 K; nearest cold trap 2.6–20 km away).
- Slope on the cylindrical grid is biased near the poles: the east–west P90 slope rises
  from 11° at 60° latitude to 29° at 88.5°, while north–south stays at 12–14°. NASA's own
  Artemis regions failed its slope limit.
- Sun visibility of its candidates (0.46–0.50) equals that of the equator.
