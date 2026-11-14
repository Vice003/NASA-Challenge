# Response to `REQUIREMENTS_COMPARISON.md`

From Vicente (Earth side), 2026-11-14, 15:45. Thanks for the careful comparison. This file answers it point by
point. Nothing in your files has been changed.

**Important first:** your comparison refers to schema version 1 of the interface. Since 13:36 the binding plan is
[`../VERARBEITUNGSPLAN.md`](../VERARBEITUNGSPLAN.md), and `ZIELSIGNATUREN.md`, `targets_template.json` and
`check_targets.py` follow **schema 2**. Several of your open questions are already settled there (marked
**decided** below). Items marked **proposal** need a short yes/no from your side; **meeting** items need the team.

## 1. General setup

| # | Your question | Status | Answer |
|---|---|---|---|
| 1 | Use `targets.json` as the single format? | **decided** | Yes. One file `planetary/targets.json`, checked by `check_targets.py`. Your CSV with weights can stay as internal working file; weights live in the scoring (item 10). |
| 3 | Moon: Shackleton or the 9 Artemis regions? | **decided** + **proposal** | Schema 2 has `shackleton_rim` (illuminated ridge, ~15 × 15 km, the size of one Artemis candidate region) and optional `shackleton_psr` (cold trap). Proposal: add Artemis regions as further targets `artemis_<name>` **after M1** if time allows; IDs and size check would be added to `check_targets.py`. |
| 4 | Mars: add Deuteronilus Mensae? Keep Jezero? | **proposal** | Keep Jezero (robotic landing site, no ice, dusty, the classic dry analog). Add `deuteronilus` as second ice target next to `arcadia`: good idea, say yes and I add the ID (20 × 20 km, same rules as Arcadia). |
| 5 | Agree on site centres | **decided** | Centres are only labels. What counts is the polygon `region_geojson` (planetocentric latitude, **longitude east 0…360**), which you choose. Arcadia 40° N / 200° E is fine as a start. |
| 6 | Adopt 100 × 100 km? | **decided: no** | Dropped. A 100 km area mixes crater rim and cold trap, or crater floor and surroundings, and is 20 times larger than an Earth cell (~5 km). **Target sites are 10–20 km** (plan, section 3). `check_targets.py` checks the size. |
| 7 | One scale enough? | **decided** | One scale per target: the site polygon (10–20 km). Landing-site detail (~100 m) enters through terrain at `pixel_m` 100 / 463. Regional context is not compared. |
| 8 | Terrain baseline | **decided** | Moon `pixel_m = 100`, Mars `pixel_m = 463`, computed only with [`../common/terrain.py`](../common/terrain.py) (`terrain_stats(dem, dx, dy, pixel_m)`). The Earth side uses the same function. |
| 9 | Accept the three methods? | **decided** | Yes: `direct`, `quantile`, `direction`. Your concern that absolute values do not transfer between instruments is exactly what `quantile` solves (see 13). |
| 10 | Which dimensions and weights? | **meeting** | Current weights: `vicente/scoring/categories.py`, `TARGETS[...]["weights"]`. Plan check: top 20 stable at ±25 % weight change. Your idea (weights from how well a parameter separates favourites from background) is welcome as a second step, after M2. |
| 13 | `body_percentile` needs global maps | **solution** | See section 2. For Mars it is feasible with the maps you already listed; the Moon thermal inertia stays `null`. |

## 2. `body_percentile`: what it is and how to compute it

For `quantile` features the Earth and target values come from different instruments and units (TES thermal
inertia in J m⁻² K⁻¹ s⁻½ vs. Earth apparent thermal inertia in 1/K). So we compare **ranks**, not values:
"Jezero is higher than X % of the Mars surface" is matched with Earth cells that are higher than X % of the
vegetation-free Earth land. To know X you need the **global** map, not only the value inside the polygon.

Use the shared function (self-test included):

```python
from common.body_percentile import body_percentile, latlon_weights
w = latlon_weights(ti_global.shape[0])               # area weight, rows from +90 to -90
p = body_percentile(ti_global, w, target=ti_median)  # fraction of the body below the target, 0..1
```

| Feature | Global map (from your list) | `body_percentile` |
|---|---|---|
| `thermal_inertia`, Mars | TES thermal inertia, 3 km, global | yes |
| `dust_opacity`, Mars | TES dust optical depth, global | yes |
| `albedo`, Moon | LOLA LDAM, global | yes (Moon albedo uses `quantile`) |
| `rock_abundance` (new, section 4) | Moon: Diviner rock abundance; Mars: THEMIS/IRTM | yes, if global |
| `thermal_inertia`, Moon | none found | leave `null` |

For polar stereographic maps pass the pixel-area map as `weights` instead of `latlon_weights`.

## 3. Parameters

| # | Your parameter → key | Status | Answer |
|---|---|---|---|
| 1 | `slope` → `slope_p50`, `slope_p90` | **decided** | LOLA / MOLA through `common/terrain.py`. |
| 2 | `roughness` → `relief` | **proposal** | Keep `relief` (median of P95 − P5 in 5 × 5 km windows) because the Earth side computes it with the same code. RMS roughness can be added later as a second terrain feature. |
| 3 | `rock_abundance` | **proposal: add** | New feature, method `quantile`, unit `%`. Used for the substrate classes (section 4). |
| 4 | `water_ice` → `ground_ice` | **proposal** | Definition per body, always the **fraction of the polygon area**: Moon = Diviner ice stability depth ≤ 1 m; Mars = SWIM ice consistency > 0. Earth side: permafrost fraction (ESA CCI, being added). |
| 5 | `illumination` | **proposal** | Real LOLA visibility maps are better than latitude, but Earth has no equivalent (averaged over a year, the sun is up ~50 % of the time everywhere on Earth). So: keep `sun_elevation_max` (method `direction`) for scoring; report your illumination value as a description of the Moon site. |
| 6 | `bearing_capacity` → `thermal_inertia` | **proposal** | Thermal inertia alone is only an indirect hint. Proposal in section 4. |
| 7 | `temperature`, Mars source | **open** | Literature with full citation (author, year, table) is fine. |
| 8 | `geology` | **decided: not needed** | `CLAUDE.md`: no global mineralogy in the available time. |
| 9 | `albedo` | **please add** | Mars: TES Lambert albedo (`direct`). Moon: LOLA LDAM (`quantile`, normal albedo at 1064 nm is not the same quantity as MODIS shortwave). |
| 10 | `dust_opacity` | **ok** | TES dust optical depth + `body_percentile`. |
| 11 | `dust_storm_days` | **decided** | Optional, leave `null`. |
| 12 | `pressure` | **open** | Mars team with citation. Moon: vacuum value is already in the template. |
| 13, 15 | `wind_mean`, `humidity` | **proposal: drop from scoring** | Humidity mostly repeats temperature (cold air holds little water: the Antarctic plateau is "drier" than the Atacama), and there is no target value. Mars wind has no map either. Both stay as descriptive Earth columns. Moon values (0) can stay. |
| 14, 16 | `precip`, `ndvi` | **decided** | 0 on both, already filled in. |

## 4. Proposal: substrate classes instead of "bearing capacity"

Bearing capacity is an engineering quantity (kPa) that depends on density, cohesion, friction angle and load
depth. Remote sensing does not measure it. Thermal inertia only sees the top centimetres and is ambiguous
(high values can mean bedrock, cemented crust, ice or scattered rocks). Combined with albedo and rock abundance
it gives **substrate classes**, defined the same way on all three bodies:

| Class | Rule (percentiles on the own body, area-weighted) | Bearing, qualitative |
|---|---|---|
| **1 Deep loose dust** | thermal inertia < P25 **and** albedo > P60 | low, sinkage |
| **2 Sand / loose soil** | thermal inertia < P50, not class 1, rock abundance < P80 | medium |
| **3 Crusted / indurated** | thermal inertia ≥ P50, rock abundance < P80 | high |
| **4 Blocky / rocky** | rock abundance ≥ P80 | high, but obstacles |

- **Percentiles on the own body** make the rule independent of instrument and unit (same idea as `quantile`).
- **Earth side:** thermal inertia = apparent thermal inertia (MODIS), albedo = MODIS snow-free, reference =
  vegetation-free land. Earth has no global rock abundance map in the allowed sources, so class 4 on Earth is
  open (possible later: Sentinel-1 radar roughness). This is a stated limit, not hidden.
- **Moon:** thermal inertia barely varies (fine regolith everywhere) and has no map, so Moon classes rest on
  rock abundance. A better Moon input would be the Diviner H-parameter (density increase with depth), as a
  next step.
- **Numbers:** published in-situ measurements (Surveyor, Apollo and Lunokhod soil mechanics; wheel sinkage of
  Spirit, Opportunity and Curiosity) can give a **range per class**, never a value per site. If your team adds
  ranges, please only with full citation.

In the presentation the dimension would be called **"Substrate (class 1–4)"**, with the sentence that true bearing
capacity needs in-situ measurement, which is exactly what an Earth analog site can be used to test.

What this needs from you: `rock_abundance` with `body_percentile` per target, plus `thermal_inertia` and
`albedo` with `body_percentile` (Mars). The classes are computed in the scoring, you do not enter them.

## 5. Next steps

| Who | What | By |
|---|---|---|
| Moon/Mars team | Start from the **current** `targets_template.json` (schema 2), set polygons (10–20 km) | Sa 17:00 |
| Moon/Mars team | Terrain via `common/terrain.py`, `thermal_inertia` + `albedo` + `body_percentile` for Mars; `check_targets.py` with 0 errors | M1, Sa 20:00 |
| Moon/Mars team | Yes/no on proposals: Deuteronilus, `rock_abundance`, `ground_ice` definition, dropping humidity/wind, substrate classes | Sa 17:00 |
| Vicente | Add agreed IDs/features to template and checker; Earth terrain at 100/463 m; substrate classes in scoring | M1, Sa 20:00 |
| Team meeting | Dimension weights, Artemis regions after M1 | Sa evening |
