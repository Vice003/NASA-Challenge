# Requirements comparison: Moon/Mars team vs. `planetary/` interface

As of 2026-11-14. This list puts side by side what the Moon/Mars team planned and can offer (branch `Mars_and_Moon`: `data_scripts/pds_test.py`, `data_scripts/FAVORITES_AND_PARAMETERS.md`) and what the interface spec in this folder expects (`ZIELSIGNATUREN.md`, `targets_template.json`, `check_targets.py`).

**Nothing has been changed on either side.** The last column lists what the team still has to decide.

Column guide:
- **Moon/Mars team**: what we planned, and which data we can deliver.
- **`planetary/` spec**: what Vicente's interface defines.
- **Match**: ✅ agrees · ⚠️ partly / different definition · ❌ missing on one side.

## 1. General setup

| # | Topic | Moon/Mars team | `planetary/` spec | Match | To decide |
|---|---|---|---|---|---|
| 1 | Handover format | CSV, one row per parameter with target range (P10–P90) and weight | `planetary/targets.json`, schema v1, checked by `check_targets.py` | ⚠️ | Use `targets.json` as the single format? |
| 2 | Values per parameter | median + P10–P90 per site | `value` (median) + `p10` / `p90` + `unit` + `source` | ✅ | – |
| 3 | Target sites, Moon | 9 Artemis candidate regions (NASA, Oct 2024), Shackleton later | `shackleton` only | ⚠️ | Shackleton as stand-in, or add Artemis regions as targets? |
| 4 | Target sites, Mars | Arcadia Planitia, Deuteronilus Mensae (shallow ice, SWIM); Jezero/Gale only as comparison | `jezero`, `arcadia` | ⚠️ | Add Deuteronilus? Keep Jezero as a base target (no ice, rover site)? |
| 5 | Site centres | Arcadia: USGS Gazetteer extent 34.7–54.7° N, 165–217° E; Artemis: 84–90° S | shackleton −89.67 / 129.8, jezero 18.44 / 77.45, arcadia 40.0 / 200.0 | ⚠️ | Arcadia centre 40° N / 200° E lies inside our extent: agree on it |
| 6 | Area per target | not fixed; regions up to several hundred km | about 100 × 100 km polygon | ⚠️ | Adopt 100 × 100 km? Polygon corners are still empty in the template |
| 7 | Spatial scale | landing site (~100 m) / base area (1–15 km) / region, per parameter | one area per target, terrain at fixed baselines | ⚠️ | Is one scale enough? |
| 8 | Terrain baseline | open (was an open question for roughness) | Moon 100 m, Mars 463 m (MOLA) | ✅ answers our open point | – |
| 9 | Comparison method | weighted normalised distance or Gower distance | `direct`, `quantile`, `direction` per feature | ⚠️ | Accept the three methods (they cover our concern that absolute values do not transfer) |
| 10 | Weighting | weights from how well a parameter separates favourites from the background; sensitivity analysis | features averaged into dimensions, dimensions weighted; `coverage` column | ⚠️ | Which dimensions and which weights? |
| 11 | Missing values | – | `null`, counts as not covered | ✅ | – |
| 12 | Sources | every dataset with URL and resolution (`parameter_coverage.csv`) | `source` required as soon as `value` is set | ✅ | – |
| 13 | Body-wide statistics | not planned | `body_percentile` required for `quantile` features (area-weighted over the whole Moon or Mars) | ❌ | We need global maps for these features, not only regional ones |

## 2. Parameters and features

| # | Moon/Mars team parameter | `planetary/` key | Method | Match | Data we can offer | To decide |
|---|---|---|---|---|---|---|
| 1 | `slope` (safety, constraint) | `slope_p50`, `slope_p90` | direct | ✅ | Moon: LOLA LDSM/LDEM (PDS registry). Mars: MOLA MEGDR | – |
| 2 | `roughness` (safety) | `relief` = median of (P95 − P5) in 5 × 5 km windows | direct | ⚠️ | Moon: LOLA LDRM, Mini-RF. Mars: MOLA, MOLA vertical roughness (ASU) | Accept the `relief` definition instead of RMS roughness? |
| 3 | `rock_abundance` (safety) | – | – | ❌ | Moon: Diviner rock abundance (PDS registry). Mars: Viking IRTM, 60 km only | Add as a new feature? |
| 4 | `water_ice` (resource) | `ground_ice` (fraction 0–1) | direction | ⚠️ | Moon: Diviner PRP, Mini-RF, LEND, LOLA PSR maps. Mars: Odyssey GRS, SWIM (3 km) | How is the 0–1 fraction defined per body? |
| 5 | `illumination` (energy) | `sun_elevation_max` (from latitude) | direct | ⚠️ | Moon: LOLA average visibility maps, 60–240 m (LOLA data node EXTRAS) | Add real illumination as a feature, or keep latitude only? |
| 6 | `bearing_capacity` (ground) | `thermal_inertia` | quantile | ⚠️ | Mars: TES thermal inertia (global, 3 km), THEMIS TI (100 m, ±60°). Moon: **no thermal inertia map found yet** (only Diviner regolith temperature) | Moon value: leave `null` or find a source? |
| 7 | `temperature` (secondary) | `surface_temp_mean`, `surface_temp_min`, `diurnal_range` | direction | ✅ | Moon: Diviner GHRM, PCP, PRP. Mars: no surface temperature map found, THEMIS night IR only qualitative | Mars source: literature? |
| 8 | `geology` (secondary, low weight) | – | – | ❌ | Moon: space weathering. Mars: GRS elements, TES mineral maps, CRISM | Needed at all? |
| 9 | – | `albedo` | direct | ❌ on our side | Moon: LOLA LDAM (PDS registry). Mars: TES albedo (ASU, 8 ppd) | Add to our script once agreed |
| 10 | dust (only as energy factor) | `dust_opacity` | quantile | ⚠️ | Mars: TES dust optical depth maps (PDS registry, global) | – |
| 11 | – | `dust_storm_days` | quantile | ❌ on our side | no source found yet | optional in spec |
| 12 | filter only (atmosphere) | `pressure` | direction | ⚠️ | literature / model, not map data | Who provides the values and sources? |
| 13 | filter only | `wind_mean` | direction | ❌ on our side | literature / model | same |
| 14 | – | `precip` | direction | ✅ (0 on both) | physical: no water cycle | – |
| 15 | – | `humidity` | direction | ❌ on our side | literature | same |
| 16 | Earth-side filter (vegetation) | `ndvi` | direction | ✅ (0 on both) | physical | – |

## 3. Pre-filled values in `targets_template.json`

Values marked "pipeline.py, gerundet - Quelle offen" need a real source. These are the ones our data could confirm or replace:

| Target | Key | Template value | Possible source on our side |
|---|---|---|---|
| shackleton | `surface_temp_mean` | 103.15 K | Diviner PCP / GHRM |
| shackleton | `diurnal_range` | 150 K | Diviner PCP |
| shackleton | `ground_ice` | 1 | Diviner PRP (ice stability depth) |
| shackleton | `pressure` | 1e-09 hPa | literature |
| jezero | `surface_temp_mean`, `diurnal_range`, `pressure` | 218.15 K, 75 K, 7.5 hPa | literature / TES |
| jezero | `ground_ice` | 0 | SWIM / GRS |
| arcadia | `surface_temp_mean`, `diurnal_range`, `pressure` | 203.15 K, 60 K, 8.5 hPa | literature / TES |
| arcadia | `ground_ice` | 1 | SWIM / GRS |

## 4. Open decisions for the team meeting

- [ ] Final target list (Moon: Shackleton vs. Artemis regions; Mars: add Deuteronilus, keep Jezero?)
- [ ] Area per target: 100 × 100 km and polygon corners
- [ ] New features: `rock_abundance`, real illumination
- [ ] Accept `relief` definition and baselines (100 m / 463 m)
- [ ] Moon thermal inertia: source or `null`
- [ ] Dimensions and weights for scoring
- [ ] Who sources atmosphere values (pressure, wind, humidity)
