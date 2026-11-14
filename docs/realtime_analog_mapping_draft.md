# Real-time Moon/Mars → Earth Analog Mapper: Design Draft (v0, rough)

Team R6 BL-Stuttgart, NASA Space Apps 2026. Status: **draft for discussion**. Items marked **[verify]** have not been checked against the source yet.

**Goal**
- (a) A user clicks a lunar or Martian point or region in a web map. Within about 1 s the system returns ranked Earth cells, each with per-dimension similarity scores and a "where the analogy breaks" note.
- (b) A systematic sweep surfaces high-similarity Earth cells that lie **far from well-known analogs**. These are the novelty candidates.

All heavy work runs offline. The online path is a lookup plus a brute-force vector scan.

---

## 1. Architecture

```
OFFLINE (Python: rasterio/xarray/numpy, run once, minutes to hours)
┌──────────────┐   ┌────────────────────┐   ┌──────────────────────┐   ┌──────────────┐   ┌────────────────────┐
│ 1 INGEST     │──▶│ 2 RESAMPLE         │──▶│ 3 FEATURES per cell  │──▶│ 4 NORMALIZE  │──▶│ 5 INDEX / ARTEFACTS│
│ PDS (peppi,  │   │ common ~10 km cell │   │ slope, relief, rough,│   │ per-body     │   │ earth_feat.npy     │
│ pds_test.py) │   │ Earth 0.1° latlon  │   │ Tavg/Tmax/ΔT, ice,   │   │ percentile   │   │ (N×F float32/uint8)│
│ Earthdata/   │   │ Moon polar-stereo  │   │ albedo, Fe/Cl/H2O,   │   │ rank (+ abs  │   │ moon_feat.npy      │
│ CMR, Coper-  │   │ Mars 0.2° latlon   │   │ dust τ, NDVI(mask)   │   │ for "direct" │   │ mars_feat.npy      │
│ nicus, NSIDC │   │ (same phys. scale) │   │ + coverage flags     │   │ features)    │   │ novelty_km per     │
└──────────────┘   └────────────────────┘   └──────────────────────┘   └──────────────┘   │ Earth cell; sweep  │
                                                                                          │ hotspots.geojson   │
                                                                                          └─────────┬──────────┘
ONLINE (<1 s)                                                                                       │ loaded in RAM
┌────────────┐  click (body,lat,lon)  ┌──────────────────────────────────────────────────────────────▼─────────┐
│ Web map    │───────────────────────▶│ FastAPI /analogs                                                       │
│ Moon|Mars  │                        │ 1 cell = grid.lookup(lat,lon)                    O(1)                  │
│ (left)     │◀───────────────────────│ 2 q = planet_feat[cell]                          O(1)                  │
│ Earth map  │  JSON top-k + scores   │ 3 S_d = per-dim score vs ALL Earth cells (numpy) ~2M×12 → 20–60 ms     │
│ (right)    │  + "breaks" + novelty  │ 4 total = Σ w_d S_d (user weights); argpartition top-500               │
└────────────┘                        │ 5 spatial NMS (≥50 km apart) → top-20; attach novelty_km, flags        │
                                      │ 6 explain(): template text from S_d + raw values + fixed limits        │
                                      └────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Feature dimensions

**Scale rule.** Features are computed on every body at roughly the same *physical* cell size and the same slope baseline. They are not computed at the same angular size. Moon: 30.3 km/°. Mars: 59.2 km/°. Earth: 111.2 km/°.

Match types used in the table:
- **D** (direct): the same physical quantity in the same units, and the value ranges overlap.
- **S** (scaled): the same quantity, but the ranges or wavelengths differ, so only relative or rank comparison is meaningful.
- **P** (proxy): a different quantity that stands in for the same concept.

| Dim | Feature(s) per cell | Moon source (pds_test.py key) | Mars source | Earth counterpart (official / common) | Match |
|---|---|---|---|---|---|
| Terrain | mean slope (°) at fixed ~2–4 km baseline; local relief (p95–p5 elev.); roughness (std of detrended elev.) | `lola_gridded`: LDEM_16 (66 MB, ~1.9 km/px) for the index; one LDEM_1024 polar tile (944 MB, ~30 m) only for refinement | `mola_megdr` 16 px/deg (33 MB, ~3.7 km/px); 4 px/deg (2 MB) for quick tests | 30-arc-sec global DEM (GMTED2010 or ETOPO 2022 **[verify size/licence]**) for the index; Copernicus DEM GLO-90/30 or SRTM tiles for refining top candidates | **D** for slope/relief at a matched baseline. Absolute elevation is **not** used. |
| Thermal | T_avg, T_max, diurnal/seasonal range ΔT | `diviner_polar_resource` (605 MB/pole: Tmax/Tavg) or `diviner_polar_cumulative` (~240 MB each). **Avoid** `diviner_gdr_l3` (1.9 GB each). | **Gap**: there is no surface-temperature product in DATASETS. THEMIS is not in the PDS4 registry. Skip in MVP. | MODIS LST monthly CMG 0.05° (MOD11C3 **[verify short name]**) → annual mean/max/range | **S only.** Lunar PSR ~25–100 K vs Earth's coldest surfaces ~180–190 K: the absolute ranges **never overlap**. Use **rank within each body**, meaning "as extreme on Earth as this cell is on the Moon". |
| Ice / water | ice-stability depth, H abundance, permafrost presence | `diviner_polar_resource` (ice-stability depth, m); `lend_averaged` (4–18 MB) | `grs_elements` h2o_sr_5x5 (0.2 MB, already downloaded); `grs_neutron` (11–45 MB) | NSIDC Circum-Arctic Map of Permafrost and Ground-Ice Conditions **[verify ID]**; MODIS-derived "fraction of months LST < 0 °C" | **P.** Lunar cold-trapped volatiles ≠ terrestrial permafrost. Mars ground ice ↔ permafrost is a closer **S/P** match. |
| Albedo / surface | normal or broadband albedo | `lola_gridded` LDAM_4/10 (4–26 MB, 1064 nm normal albedo) | (TES albedo is not in DATASETS. Skip.) | MODIS MCD43C3 albedo 0.05° **[verify]** | **S** (different wavelength and definition) |
| Mineralogy | Fe, Cl, (Si, K, Th) abundance; mineral-class presence | `space_weathering` npFe (156 MB, 30 px/deg). Weak link, so stretch only. | `grs_elements` Fe, Cl, … (5°×5° ≈ 300 km!); `tes_emissivity` endmembers; `crism_mtrdr` for site refinement only (18–36 m, per-scene) | EMIT L2B minerals (hematite/goethite → Fe-oxides, gypsum → sulfates, clays) **[verify product + arid-only coverage]**; ASTER mineral indices for refinement | **P.** Elemental abundance (gamma rays) vs surface mineral spectra (VSWIR). GRS footprint is far coarser than an Earth cell, so it is down-weighted. |
| Dust / atmosphere | column dust optical depth (mean, seasonal max) | N/A (no atmosphere) | `tes_dust` global maps (0.26 MB each) | MERRA-2 aerosol monthly, dust AOD (M2TMNXAER / DUEXTTAU **[verify]**) | **S** (IR ~9 µm vs 550 nm; different atmospheres) |
| Radar | CPR / roughness at the radar wavelength | `minirf_mosaic` CPR (4.2 GB global 128 ppd). Stretch only: a windowed read of the polar rows via GDAL `/vsicurl/` is ~0.2 GB **[verify range reads work]**. | `sharad_3d` (26–160 GB): **do not use** | Sentinel-1 GRD (C-band VV/VH), RADARSAT-1/RCM | **P.** S-band circular vs C-band linear polarization. A cross-pol ratio is only a rough proxy. |
| Earth-only mask | NDVI, (precipitation) | none (0 by definition) | none | MODIS NDVI CMG (MOD13C2 **[verify]**) | Used as a **penalty**, not as a similarity dimension |

**Non-mappable limits** are never scored. They are appended to every result as fixed text:
- **Gravity**: Moon 0.165 g, Mars 0.38 g.
- **Atmosphere**: Moon has a near-vacuum exosphere. Mars has ~0.6 kPa of CO₂. As a result, Earth convection, wind and weathering have no lunar equivalent.
- **Radiation**: neither body has a global magnetic field, so there is no Earth-like shielding from galactic cosmic rays and solar particle events. Moon has no atmosphere at all.
- **Day length**: lunar day ≈ 29.5 Earth days. Mars sol ≈ 24.6 h.
- **Regolith**: lunar regolith is agglutinate-rich, angular and unweathered by water.
- **Biology**: Earth analogs carry biology. That is a contamination issue, or an opportunity for extremophile research.
- **Temperature**: PSR temperatures are unreachable on Earth.

---

## 3. Normalization and similarity

1. **Domain per body.**
   - Earth: land cells only, with ocean and inland water masked.
   - Moon: the global grid for global products, and the polar region for polar-only products. Rank *within that domain*, and document which domain was used.
   - Mars: global.
2. **Transform.** For every feature f and body B, take the percentile rank q = P_B(x) ∈ [0,1], computed with `scipy.stats.rankdata` and divided by N.
   - For **D** features (slope, relief), offer a toggle for an absolute comparison `exp(-(Δx/σ_f)²)`, with σ_f documented (e.g. 5° for slope).
3. **Per-dimension score.**
   - `S_d = 1 − mean_{f∈d} |q_planet,f − q_earth,f|`, which lies in [0,1] (1 = same rank position).
   - Missing data (e.g. EMIT outside arid zones, or a Mars thermal gap) → the dimension is skipped for that pair and reported as "no data". It does not count as 0.
4. **Total.**
   - `Total = Σ w_d S_d / Σ w_d` over the available dimensions, multiplied by `(1 − λ·q_NDVI)` with λ ≈ 0.5.
   - Report a **coverage** value (how many dimensions were scored) next to the total.
   - User sliders set w_d. Defaults: terrain 1, thermal 1, ice 1, mineralogy 0.5, dust 0.5, albedo 0.5.
5. **Why this is explainable.**
   - Every number in the total traces back to "Moon cell is at the 3rd percentile of lunar T_avg (52 K); Earth cell is at the 2nd percentile of Earth LST (−38 °C) → S_thermal = 0.99".
   - The UI shows raw values in native units side by side with the ranks.
   - There is no black-box ML in the MVP. Possible stretch: PCA/UMAP view of the feature space, and a Mahalanobis variant to handle correlated features.
6. **"Where the analogy breaks".** This note is generated as:
   - every dimension with S_d < 0.5 ("thermal: Earth cell is a mid-latitude desert, rank 0.6 vs lunar 0.02"),
   - plus every dimension with no data,
   - plus every match type P ("ice comparison is proxy only"),
   - plus the fixed non-mappable list.
7. **Positive control.** Before trusting the method, check whether Haughton / Devon Island, Antarctic Dry Valleys and Atacama rank high for plausible targets (polar ice, Mars arid terrain). If they do, the novel hits are credible. If not, fix the features. This is a strong point for the judges.

---

## 4. Grid and scale (hackathon budget)

| Body | Index grid | Cell size | Cells (approx.) | Refinement for top candidates |
|---|---|---|---|---|
| Earth | 0.1° lat/lon, land only (fallback 0.25° if time is short) | ~11 km N-S | ~1.9 M land (0.25°: ~0.3 M) *estimate: 29 % land × cell count* | 0.01° (~1 km) windows around the top-20 using Copernicus DEM / MODIS 1 km / EMIT scenes |
| Moon | polar stereographic, 10 km px, −90°…−75° (MVP: south pole only) | 10 km | ~(2×455 km/10 km)² ≈ 8 k | LDEM_1024 tile (944 MB) for one Artemis III region only |
| Mars | 0.2° lat/lon | ~11.8 km | ~1.6 M global; MVP uses Jezero ± 3°, Gale ± 3° and polar strips | MOLA 128 ppd; CRISM MTRDR scenes |

- H3 (resolution 5, ~250 km² cells) is an option but adds dependency and projection work. Plain lat/lon arrays plus a cos(lat) area weight are enough for the MVP.
- **Data volume, MVP:**
  - Moon ≈ LDEM_16 66 MB + LDAM 4 MB + Diviner PRP south 605 MB + LEND ~20 MB ≈ **0.7 GB**.
  - Mars ≈ MOLA 16 ppd 33 MB + GRS tables ~2 MB + TES dust ~5 MB ≈ **40 MB**.
  - Earth: MODIS CMG monthly products are each tens of MB × 12 months × a few products. The 30-arc-sec DEM is a few GB **[verify]**. MERRA-2 monthly is small.
  - Total: **≈ 2–5 GB**.
- **Avoid:** `diviner_gdr_l3` (1.9 GB × many), `minirf_mosaic` full download (4.2 GB each), `LDEM_128` (4.2 GB), all LDEM_1024 tiles (12 × 944 MB), `sharad_3d` (26–160 GB), a global Copernicus GLO-30.
- **Known scale mismatch.** GRS (~300 km) and TES dust (coarse) are broadcast to the 10 km cells and flagged `coarse=True`. The UI shows them at reduced weight (×0.5 by default).

---

## 5. Real-time serving

**Index.** A plain **numpy brute-force scan** with all arrays held in RAM. FAISS or a BallTree is not needed.
- Earth matrix: 1.9 M × ~12 features as float32 ≈ 90 MB, or 23 MB as uint8 percentiles.
- One query is ~23 M abs/sub/mul operations, which takes about 20–60 ms in numpy on a laptop *(estimate; benchmark in phase 3)*.
- `np.argpartition` for the top 500, then greedy NMS on haversine distance, then the top 20.
- Novelty distances are precomputed per Earth cell, so they add no query cost.
- A tree index would not help anyway. Weights change per request, and the per-dimension scores must be computed for every cell regardless.

**API (FastAPI).**
- `GET /analogs?body=moon&lat=-89.5&lon=222&k=20&w_terrain=1&...` returns JSON, roughly 10 KB, with:
  - `query{cell, raw, ranks}`
  - `results[{lat, lon, total, coverage, S_d{...}, raw_earth{...}, novelty_km, nearest_known, breaks[...]}]`
- `GET /scoremap?...` (stretch) returns a 0.5° uint8 PNG of the Earth score field (~260 k px).
- **Offline/static fallback.** Precompute the top 50 for every MVP planetary cell under the default weights as `topk_{body}.json`. That is about 8 k Moon cells × 50 × ~60 B ≈ 25 MB, so split it per region or keep only the top 20. With the fallback the demo runs from `file://` even if the server dies. Weights stay adjustable client-side by re-ranking the stored top 500 using the stored S_d values.

**Front end (Leaflet, two synced panes).**
- Left: Moon/Mars. Right: Earth.
- **Planet basemap for an offline demo:** render our own hillshade PNG from LDEM_16 or MOLA and add it as `L.imageOverlay`, using `L.CRS.Simple` for the polar-stereographic Moon. Online alternative: NASA Moon/Mars Trek WMTS tiles **[verify endpoints]**.
- **Earth basemap:** NASA GIBS tiles (the same imagery as Worldview) when online; our own DEM hillshade or Natural Earth offline.
- **Results:** markers coloured by total score, with a ring for "novel" (> D₀ from a known analog). The side panel shows bar charts per dimension, raw values, and the "breaks" text.

**Latency budget.** Click → request (~5 ms local / ~50–150 ms Wi-Fi) → server compute 30–80 ms → JSON 10 KB → render 20 markers (<20 ms). That totals **≈ 0.1–0.3 s**, well under 1 s. Refinement at 0.01° stays offline and runs only for the candidates shown in the final pitch.

---

## 6. Novelty detection

1. **Known-analog gazetteer** (`known_analogs.csv`: name, lat, lon, radius_km, source_url).
   - Seed list: Atacama, Haughton Crater / Devon Island, Death Valley, Antarctic Dry Valleys, Iceland, Hawaii (Mauna Kea, Kilauea), Svalbard, Rio Tinto, Mojave, Utah MDRS, Pilbara, plus any others the team sources.
   - **Every entry needs a citation the team has actually checked.** Do not invent any.
   - Large regions (Iceland, Atacama) get large radii.
2. **`novelty_km`** = haversine distance from each Earth cell to the nearest gazetteer circle edge, computed offline with a BallTree.
   - `novel = novelty_km > D₀` (default 200 km, adjustable with a slider).
3. **Systematic sweep (offline).**
   - Loop over every planetary cell in the MVP target regions: Artemis III south-pole regions, Jezero, Gale, and the Mars polar strip.
   - Collect each cell's top 100 Earth cells and count how often each Earth cell appears, weighted by score.
   - Run DBSCAN (haversine, eps ≈ 30 km) on high-frequency cells to get **candidate regions** (polygons, area, mean score, dominant target).
   - Output `hotspots.geojson`: an "Earth map of under-studied analog hotspots", with known ones greyed out. This map answers part (b) directly.
4. **Partial-match profiles.**
   - Turn each candidate's S_d vector into a label, e.g. "terrain ✔ ice ✔ thermal ✘" (thresholds 0.75 / 0.5).
   - Group candidates by profile, so judges see *what kind* of analog each one is, for example "mobility/terrain testbed" vs "cold-trap thermal analog".
5. **Sanity check per candidate (manual, top 5–10).**
   - Open NASA Worldview at the bbox and take a screenshot. Worldview permalinks encode bbox/layers/time in the URL; the exact parameter format is **[verify]**.
   - Check for cloud or snow artefacts, open water, cropland or urban areas, and MODIS fill values.
   - Run a quick literature search ("<place> Mars analog" / "lunar analog"). If papers exist, move the place into the gazetteer and mark it "known".
   - Record the result in `candidates_review.csv` as: verdict, screenshot path, notes.

---

## 7. Phased build plan (3 parallel tracks; times are person-hours, rough)

| Phase | Work | Time | Output |
|---|---|---|---|
| 0 | Fix grids, feature list, file formats; write gazetteer with sources | 0.5–1 h | `grids.py`, `known_analogs.csv` |
| 1a Earth | DEM → slope/relief/roughness at 0.25° first (0.1° if time); MODIS LST annual stats; NDVI mask; MERRA-2 dust | 3–4 h | `earth_feat.npy` + metadata |
| 1b Moon | LDEM_16 → polar-stereo 10 km terrain; Diviner PRP (Tavg, Tmax, ice depth); LDAM albedo | 2–3 h | `moon_feat.npy` |
| 1c Mars | MOLA 16 ppd terrain; GRS H2O/Fe/Cl (5° broadcast); TES dust | 1.5–2 h | `mars_feat.npy` |
| 2 | Rank transform, scoring, NMS, breaks text, positive-control check (CLI) | 1.5–2 h | `score.py`, sanity table |
| 3 | FastAPI + Leaflet two-pane UI, sliders, static fallback export | 2–3 h | working demo |
| 4 | Novelty sweep + DBSCAN hotspots; Worldview review of top 5–10 | 2 h | `hotspots.geojson`, screenshots |
| 5 | Write-up, dataset list with URLs/licences, demo video | 2 h | submission |

**MVP (first ~6–8 h wall-clock with 3 people):**
- 4 dimensions: terrain, thermal (Moon only), ice, dust/mineralogy (Mars only).
- Moon south pole plus Jezero and Gale.
- Earth at 0.25°, the click → top-20 flow working, and the novelty flag.

**Stretch:**
- Earth at 0.1° plus 0.01° refinement.
- Mini-RF ↔ Sentinel-1 radar.
- EMIT mineralogy.
- The score heat-map layer.
- A Moon north pole and global Mars index.
- Process analogs (dust-storm seasonality, freeze–thaw cycle counts).

**Main risks and mitigations:**
- *Earth data download/processing time* (DEM, MODIS): start with 0.25° CMG products and a coarse DEM. Cache intermediate GeoTIFFs.
- *Polar projections and the 0/360 vs ±180 longitude conventions*: one helper module with unit tests on known points (e.g. Shackleton crater ~89.7°S **[verify coords]**).
- *Thermal mismatch criticised as meaningless*: say upfront that the comparison is rank-based ("relative extremeness"), and show raw K/°C next to it.
- *Mars has no thermal source* in our list: be transparent, or add THEMIS thermal inertia from the ASU archive if time allows **[verify availability]**.
- *Coarse GRS/TES* dominating results: down-weight them and show the `coarse` flag.
- *"Novel" hits that are artefacts* (clouds, water, ice-sheet interior): the NDVI and water mask, plus the Worldview review step.
- *Rediscovering Antarctica everywhere* for lunar thermal queries: this is expected. The novelty filter and the partial-match profiles push non-Antarctic hits, e.g. high-altitude cold deserts, to the surface.

---

## 8. Open questions and assumptions

1. **Rank within domain vs absolute.** Assumed: rank for S/P features, with an absolute option for D features. Do judges accept "relative extremeness"? We need one clear sentence in the pitch.
2. **Lunar domain.** Should ranks be computed over the polar region only or the global Moon? Polar-only exaggerates contrasts inside the PSR region. Decide in phase 2.
3. **Cell size of ~10 km** is a compromise. Artemis III candidate regions are ~15 km across **[verify]**, so a single cell barely resolves them. Refinement is needed for the final story.
4. **Earth DEM product for the index** (GMTED2010 vs ETOPO 2022 vs a downsampled Copernicus GLO-90) has not been chosen: check size, licence and whether it is acceptable as an "official resource".
5. **Exact Earth product short names** (MOD11C3, MCD43C3, MOD13C2, M2TMNXAER, the EMIT L2B mineral product, the NSIDC permafrost ID) are from memory. **[verify all in Earthdata Search / CMR before use]**.
6. **Gazetteer completeness** decides what counts as "novel". It needs sourced entries. A missing known site would be mis-reported as novel.
7. **Mini-RF via `/vsicurl/`** windowed reads are untested. A smaller polar-stereographic LOLA DEM may also exist in the registry, which would make refinement cheaper than the 944 MB tiles **[check with pds_test.py --region moon_south_pole --limit 50]**.
8. **Biology/habitability** is treated as a penalty (NDVI), not as a dimension. Extremophile value could be added later as a separate "research value" tag rather than a similarity score.
9. **peppi `Products.count()` returns None** (a known bug), so dataset sizes come from iteration plus the `ops:Data_File_Info` sizes in our CSVs.
10. **Assumed**: the demo runs on one laptop, so loading ~100 MB into RAM is fine. The web demo needs internet only for the GIBS/Trek tiles; the offline fallback uses our own hillshades.
