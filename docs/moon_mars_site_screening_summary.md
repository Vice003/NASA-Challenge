# Moon & Mars site screening – summary

Status: 2026-11-15 · Branch `Mars_and_Moon` · Team R6 BL-Stuttgart (Moon & Mars side)

Goal: find **new** landing / base sites on the whole Moon and the whole Mars using only
parameters that the official challenge sources deliver with reliability **A or B**
(see `docs/official_sources_audit.md`). Known landing sites are used only as reference
("is this candidate new?"), never to restrict the search.

---

## 1. What was done

| Step | Result |
|---|---|
| Fixed and extended `pds_test.py` (PDS registry via `pds.peppi`) | 14 curated Moon/Mars datasets, bbox filter (incl. fix for mixed 0..360 / −180..180 longitudes) |
| `landing_sites.py` | reference list: Artemis III regions, PSR craters, Apollo/Chang'e/Chandrayaan-3/SLIM/IM-1/Blue Ghost, Mars landers, M2020/MSL finalists, SWIM ice areas; checks PDS coverage per site |
| Audit of all official APIs (`docs/official_sources_audit.md`) | PDS Registry, **PDS Geosciences ODE** (closed most gaps), CMR, GIBS, Copernicus, ESA OSC, CSA, JAXA – fields, access, reliability |
| `moon_screen.py` | lunar south pole 85–90° S at **240 m** resolution |
| `moon_global_screen.py` | **whole Moon** at ~1.9 km (16 px/deg), polar caps from 240 m LOLA products |
| `mars_screen.py` | **whole Mars** (88° S–88° N) at ~3.7 km (16 px/deg) |
| Results | `data_scripts/results_moon_mars.zip` (candidate CSVs + maps) |

Each script: download raw PDS files → aggregate to a common grid → apply **constraints**
(hard exclusion) → weighted **score** 0..1 from preferences → group neighbouring good
cells into sites → rank, merge sites closer than a minimum distance, flag as *novel*
when far from every known site.

---

## 2. Landing / base-site criteria

Thresholds come from the team criteria document (Artemis, Mars Exploration Zones 2015,
InSight; see `data_scripts/FAVORITES_AND_PARAMETERS.md`) unless marked *ours*.
All values are command-line options.

### Moon

| Parameter | Type | Value | Data |
|---|---|---|---|
| Slope | constraint | south pole: mean ≤ 5° and P90 ≤ 10° at 40 m baseline (team: 0–5°) · global: P90 ≤ 8° at 237 m baseline (*ours*) | LOLA LDSM / LDEM_128 |
| Not in permanent shadow | constraint | PSR fraction < 5 % (pole) / < 50 % (global) | LOLA LPSR |
| Sun visibility | constraint (pole) + score | ≥ 30 % average visibility (*ours*); weight 0.35 (pole) / 0.25 (global) | LOLA AVGVISIB |
| Ice access | score | distance to surface cold trap (pole) or PSR (global), exp(−d / 2 km EVA radius); weight 0.30 | Diviner PRP, LOLA LPSR |
| Slope (preference) | score | weight 0.15 | LOLA |
| Roughness | score | weight 0.10 | LOLA LDRM |
| Rock abundance | score (global only, |lat| ≤ 60°) | 5 % rock cover → 0; weight 0.10 | Diviner GDR L3 |
| Earth visibility (communications) | score | weight 0.10 | LOLA AVGVISIB_EARTH; outside the poles from geometry (near/far side) |
| Reported only | – | Tmax/Tavg, ice-stability depth, regolith temperature anomaly, albedo | Diviner, LOLA |

### Mars

| Parameter | Type | Value | Data |
|---|---|---|---|
| Slope | constraint + score | P90 ≤ 15° at 463 m baseline (InSight < 15°); weight 0.15 | MOLA MEGDR 128 px/deg |
| Elevation (EDL) | constraint | ≤ +2 km MOLA (team: ±2 km) | MOLA |
| Bearing capacity | constraint + score | night thermal inertia 140–1500 SI (InSight > 100–140); weight 0.15 | TES TI 2007 |
| Water | score | rank of water-equivalent hydrogen; weight 0.35 | Odyssey GRS H₂O 5° (|lat| ≤ 57.5°) |
| Solar power | score | annual-mean insolation from latitude; weight 0.15 | computed |
| Roughness | score | relief P95–P5 per 3.7 km cell; weight 0.10 | MOLA |
| Dust | score | low surface-dust cover; weight 0.10 | OMEGA nanophase ferric oxide |
| Reported only | – | albedo, distance to hydrated-mineral sites | OMEGA |

Where a parameter has no data in a cell (e.g. GRS poleward of 57.5°), the score is the
weighted mean of the available parameters (≥ 60 % of the weight required) and the
missing parameters are listed per site.

**Not scored (no A/B source):** Moon rock abundance at the poles, Moon thermal inertia,
Mars rock abundance, Mars surface temperature (THEMIS gives only dawn/dusk snapshots),
Mars dust-storm frequency (TES series not processed yet).

---

## 3. How the data was obtained

All data are **official NASA PDS archives**, no account needed:

1. **Search:** `pds.peppi` (PDS Registry API) for PDS4 products, and the **PDS Geosciences
   ODE REST API** (`oderest.rsl.wustl.edu/live2`) for products not in the registry
   (LOLA illumination/PSR maps, TES thermal inertia, OMEGA maps).
2. **Download:** direct HTTPS from the PDS Geosciences Node
   (`pds-geosciences.wustl.edu`), raw PDS3/PDS4 images + labels.
3. **Read:** raw binary with `numpy` using the label keywords (size, byte order, scaling,
   offset, projection). Checks done before use:
   - projection validated against known features (Shackleton, Faustini, Haworth,
     Shoemaker, Whipple on PSR pixels; Olympus Mons +20 km, Hellas −6 km on Mars);
   - data quirks found and handled: LOLA slope DN 0 = gaps between tracks (69 %),
     Diviner `ice_depth` −999 = "deeper than 2.87 m", undocumented −1 = surface-stable,
     65° polar maps are only complete poleward of ~65°.

---

## 4. Data volume

| | Downloaded | Used in the scoring | Main files |
|---|---|---|---|
| **Moon – south pole (240 m)** | 0.94 GB | 0.94 GB | Diviner PRP south 605 MB, LOLA LDSM/LDRM 85S 115 MB each, AVGVISIB/PSR 85S 51 MB each |
| **Moon – global** | 3.7 GB | ~2.95 GB | LOLA LDEM_128 2.1 GB, 65N/65S illumination + PSR 6 × 82 MB, LDRM_32_50 133 MB, Diviner 32 px/deg 2 × 88 MB |
| **Mars – global** | 2.9 GB | ~2.8 GB | 16 MOLA tiles × 130 MB = 2.1 GB, OMEGA 3 × 207 MB, TES TI 2 × 52 MB, GRS < 1 MB |
| **Total** | **7.4 GB** | **~6.7 GB** | |

Unused downloads (kept for later): Diviner PRP north, LDRM 0.25-quantile and count maps,
Diviner night regolith temperature, OMEGA pyroxene.

Run time on the team laptop (8 cores, 7 GB RAM): south pole ~2 min, whole Moon ~4 min,
whole Mars ~4 min; peak memory ≤ 2.8 GB. The generated `features.npz` caches (55–358 MB)
are not in git; rebuild with `--rebuild`.

---

## 5. Results (top candidates)

Full lists and maps: `data_scripts/results_moon_mars.zip`.

**Moon – south pole (85–90° S):** best sites lie 20–80 km from the NASA anchor points,
e.g. 86.99° S 126.9° E (score 0.58, sun 40 %, Earth 38 %, slope 1.5°, cold trap 0.5 km) and
85.14° S 33.5° E (Earth visibility 83 %).

**Moon – global:** the strongest region is the **north polar near side (67–86° N, 330–45° E)**
– flat (P90 1–3°), PSRs within 0.5–1 km, Earth always visible. Best site 71.1° N 18.0° E
(score 0.76), ~1000 km from any previous landing. No mission currently targets this area.

**Mars – global:** best sites are flat, firm equatorial plains around **Meridiani / Chryse–Mawrth**
and **south of Gale (120–150° E)**: P90 slope < 1°, thermal inertia ~400, 5–7 wt% water-equivalent
hydrogen. Best site 3.9° N 2.9° E (score 0.97), 605 km from Opportunity.

---

## 6. Limitations (state these in the submission)

1. **Mars ice poleward of ±57.5° is missing** (GRS gamma method) → ice-rich high latitudes
   (Phoenix, northern Arcadia) are under-rated. Next step: Odyssey GRS neutron data (IDND, ~20 MB).
2. **Mars "water" at the equator is mostly bound in hydrated minerals**, not ice.
3. **Moon sun visibility is an average**; the length of the longest night (the real advantage
   of polar sites) is not yet scored.
4. **Visible step at ±60° on the Moon map** where the Diviner rock-abundance map ends.
5. **Reference coordinates** of Artemis regions and earlier landings are approximate
   (Slater Plain fully estimated) → the *novel* flag is indicative; replace with NASA's
   official region polygons before publishing.
6. Scores depend on the chosen **weights** (all printed by the scripts and adjustable).
7. Earth's limits as an analog (gravity, vacuum / thin CO₂ atmosphere, radiation) are not
   part of this screening; they belong in the Earth-comparison step.

---

## 7. Reproduce

```bash
cd data_scripts
.venv/bin/python moon_screen.py          # south pole, needs output/raw/moon
.venv/bin/python moon_global_screen.py   # whole Moon, needs output/raw/moon_global
.venv/bin/python mars_screen.py          # whole Mars, needs output/raw/mars
```

Download URLs for every input file are in the `urls.txt` file of each `output/raw/*` folder
(not in git) and in the docstrings of the scripts.
