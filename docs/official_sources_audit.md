# Audit of the official challenge sources (APIs + Python libraries)

Status: 2026-11-14. Every source listed in `AGENT_PROMPT.md` was queried live with
small requests (metadata only). Product names, counts, file sizes and px/deg values were
**seen in an API response**. Resolutions written with "~" (e.g. M³ ~140 m, HRSC ~50–100 m,
SHARAD, LEND, the TES record years) are from instrument documentation, not from the API,
and should be checked before citing. Items marked *[unverified]* were not tested at all.

Reliability scale used throughout:
- **A** = direct measurement of the parameter, documented product, adequate resolution
- **B** = direct measurement but coarse / patchy coverage, **or** a well-established proxy
- **C** = weak proxy or needs our own non-trivial derivation
- **–** = not available from the official sources

---

## 1. Access overview

| Source | Interface we tested | Search without login | Download | Python access |
|---|---|---|---|---|
| NASA PDS Registry | REST `pds.mcp.nasa.gov/api/search/1` | yes | yes, direct HTTPS | `pds.peppi` 0.9.0 (works; `count()` returns None) |
| PDS MCP server | `pds.peppi.mcp_server` (FastMCP) | – | – | exposes only 2 tools: target search, instrument-host search. A richer `qb_mcp.py` adds one `querypdsdata` tool |
| **PDS Geosciences ODE** (behind the "LRO PDS Geosciences" resource) | REST `oderest.rsl.wustl.edu/live2` | yes | yes, direct HTTPS | plain HTTP/JSON (no library needed) |
| NASA Earthdata Search | CMR REST `cmr.earthdata.nasa.gov/search` | yes | needs free **Earthdata Login** *[unverified for each DAAC]* | `earthaccess` / plain HTTP |
| NASA Worldview | GIBS WMTS (1,345 layer identifiers) | yes | yes (map tiles) | WMTS / `owslib` |
| CSA RCM / RADARSAT-1 | portal `donnees-data.asc-csa.gc.ca` **timed out**; same datasets via `open.canada.ca` CKAN API | yes | RADARSAT-1: GeoTIFF over FTP per continent. RCM: only acquisition footprints (CSV/WMS) are open; imagery via EODMS *[unverified]* | CKAN JSON + FTP |
| Copernicus Data Space | STAC `stac.dataspace.copernicus.eu/v1` (428 collections) + OData | yes | needs free CDSE account *[unverified]* | `pystac-client` |
| ESA Open Science Catalog | static STAC on GitHub (`esa-earthcode.github.io/open-science-catalog-metadata`) – 366 products | yes | links to each product's own host | `pystac` |
| JAXA G-Portal | web portal + CSW; CSW endpoint returned HTML to our scripted request | partly | **account + SFTP key required** (seen on portal) | none tested |

**Key finding:** ODE indexes far more Moon/Mars products than the `pds.peppi` registry,
including HiRISE, CTX, THEMIS, LOLA PSR/illumination maps, TES thermal inertia and OMEGA.
The gaps we reported earlier ("not in the registry") are mostly closed by ODE.

---

## 2. What fields each API returns

### PDS Registry (`pds.peppi`)
Per product: `lidvid`, `title`, target / instrument / host LIDs, start/stop time,
`cart:Bounding_Coordinates` (N/S/E/W), `pixel_resolution`, `pixel_scale` (px/deg),
map projection, `Object_Statistics` min/max, table column names + units
(`Field_Character`), data file URLs, sizes, MD5, label URL.
Pitfalls found: longitudes are mixed (0..360 vs −180..180, one product has W=180/E=−180),
only products whose labels carry `cart:` fields can be bbox-filtered, `count()` is broken.

### ODE REST
~50 fields per product, e.g. `pdsid`, `ihid/iid/pt`, `Minimum/Maximum_latitude`,
`Westernmost/Easternmost_longitude`, `Footprint_geometry` (WKT polygon), `Map_resolution`
(px/deg), `Map_scale`, `Incidence/Emission/Phase_angle`, `Solar_time` (local time),
`Solar_longitude` (Mars season), `UTC_start/stop_time`, `Product_files` (URL + KB),
`LabelURL`, `External_url`. Server-side bbox filter (`minlat/maxlat/westernlon/easternlon`)
works (tested at Jezero).

### CMR (Earthdata Search)
Per collection (UMM-C): short name, version, provider/DAAC, temporal range, spatial
extent, horizontal resolution, processing level, cloud-hosted flag, DOI, related URLs.
Per granule: file URLs, size, footprint, time. **CMR returns metadata only; values come from the files.**

### GIBS / Worldview
WMTS layers = **rendered colour tiles** (PNG/JPEG) with a colour map, not physical values.
Good for visual checks and screenshots of candidates, **not** for computing scores (reliability C if used numerically).

### Copernicus STAC
Per collection: id, title, temporal extent, bbox, assets (COG / NetCDF / SAFE), license.
Per item: footprint, datetime, cloud cover (optical), polarisation/mode (SAR), asset hrefs.

### CSA (open.canada.ca CKAN)
Per dataset: title, licence (`ca-ogl-lgo` = Open Government Licence Canada), resources
(format + URL). RADARSAT-1 resources are GeoTIFF folders per region (Africa, Antarctica,
Australia, USA, ...). RCM resources are acquisition footprints only.

### ESA Open Science Catalog
STAC collections with title, themes, variables, missions, links to the data host.
Relevant products found: **`esa-cci-permafrost`**, CALIPSO dust optical depth +
climatologies, S3 broadband/spectral albedo (Arctic/Greenland), Alpine snow products,
Cryosat-2 mountain glacier elevation change.

---

## 3. Moon – what can be inferred, and how reliably

| Parameter | Best official product(s) | Resolution | What it really measures | Rel. |
|---|---|---|---|---|
| Slope | LOLA `LDSM` slope maps (ODE `GDRDSM`, registry) ; LOLA `LDEM`, SLDEM2015 | 20–240 m (pole), 59 m (SLDEM) | laser altimetry → slope | **A** |
| Roughness | LOLA `LDRM` roughness, `RMMAS` median abs. slope, `RMHE` Hurst exponent (ODE) ; Mini-RF CPR | 40 m–1 km ; Mini-RF ~240 m | topographic roughness (LOLA) ; radar roughness at cm–dm scale (Mini-RF) | **A** (LOLA) / B (Mini-RF) |
| Rock abundance | Diviner GHRM rock abundance (slope-adjusted midnight) – **only 70 S–70 N**; Diviner GDR L3 rock abundance only to 80 S | 128 ppd ≈ 240 m | fraction of surface covered by rocks > ~1 m, from night-time cooling | **A** below 80° / **– at the pole** (use LOLA roughness as proxy, C) |
| Ice accessibility | LOLA PSR maps `LPSR_85S_060M` (ODE `GDRPSR`) ; Diviner PRP (ice-stability depth, Tmax) ; LEND neutrons ; Mini-RF CPR ; LAMP (UV) | PSR 60–240 m ; PRP ~km ; LEND ~10s of km | where it is cold/dark enough for ice (A for "could exist"), hydrogen (LEND, B), radar (C, ambiguous with roughness) | **B** (combined) |
| Illumination | LOLA average sun visibility `AVGVISIB_85S_060M` (+ `_EARTH` = Earth visibility for comms) ; sky visibility `GDRSKY` | 60–240 m | modelled % time sunlit from LOLA topography | **A** |
| Bearing capacity | Diviner regolith temperature at midnight (GHRM) ; rock abundance | 128 ppd | night-time temperature of fines → regolith thermophysics | **C** (proxy) |
| Thermal inertia | no Diviner thermal-inertia / H-parameter product in PDS (GHRM list checked: only rock abundance, channel 6–9 BT, bolometric T, regolith T) | – | regolith-temperature anomaly is the closest proxy | **C** |
| Temperature | Diviner GDR L2/L3, PCP (polar, by season + local time), PRP, GCP, RCP | 128 ppd (≈240 m) global; polar products ~250 m | radiometric surface temperature | **A** |
| Geology | LROC WAC TiO₂ map, LROC 7-colour mosaics, Kaguya MI maps, Chandrayaan-1 M³, Lunar Prospector & Kaguya GRS elements, space-weathering maps | WAC ~400 m; M³ 140 m; GRS ~0.5–5° | composition / maturity | **A–B** (poorer at the pole: low sun, space-weathering map only ±60°) |
| Albedo | LOLA `LDAM` 1064 nm normal albedo ; LROC Hapke maps | 4–20 ppd (≈1.5–7.5 km) | normal albedo at 1064 nm (laser) | **A** (but ≠ broadband visible albedo used on Earth → compare as rank) |
| Dust | – (no atmosphere; levitated-dust data not in scope) | – | – | – |
| Dust-storm frequency | not applicable | – | – | – |
| Atmosphere | vacuum (physical constant). LAMP measures exosphere, irrelevant for analogs | – | – | **A** (constant) |
| Terrain models (bonus) | LROC NAC DTMs (668), ASP DTMs (101), Kaguya TC DTMs | 2–5 m (NAC) | local stereo topography | **A** but sparse |

## 4. Mars – what can be inferred, and how reliably

| Parameter | Best official product(s) | Resolution | What it really measures | Rel. |
|---|---|---|---|---|
| Slope | MOLA MEGDR (registry + ODE) ; HiRISE DTMs (ODE: 1,370, e.g. 5 at Jezero, 700–1,070 MB each) ; HRSC DTMs (ODE: 9,286) | MOLA 463 m ; HRSC ~50–100 m ; HiRISE ~1 m | altimetry / stereo | **A** (regional MOLA, local HiRISE) |
| Roughness | MOLA MEGDR (derive) ; MOLA PEDR shots ; HiRISE/HRSC DTMs | 463 m / local | topographic roughness (derived by us) | **B** |
| Rock abundance | no rock-abundance product found in ODE/registry ; HiRISE images allow manual boulder counts | – | – | **– / C** |
| Ice accessibility | Odyssey GRS H₂O (5°) + neutron (IDND/DND/AND) ; SHARAD radargrams (40,154 RDR + 4 3D cubes) ; MARSIS ; CRISM/OMEGA hydrated minerals | GRS ~300 km ; SHARAD ~0.3–3 km along track | hydrogen in top ~1 m (GRS, B), subsurface radar reflectors (SHARAD, B but needs interpretation) | **B** |
| Illumination | computed from latitude/season ; TES/THEMIS dust opacity for attenuation | – | orbital geometry (exact) + dust | **A** (geometry) / B (with dust) |
| Bearing capacity | via thermal inertia (below) | 3 km / 100 m | grain size / induration proxy | **C** (proxy) |
| Thermal inertia | **TES global TI maps** `GLOBAL_TI_DAY/NIGHT_2007` (ODE `TIMAP`, 20 ppd ≈ 3 km, 25–51 MB) ; THEMIS IR (derive TI yourself) | 3 km | thermal inertia (SI units) | **A** |
| Temperature | **THEMIS IR projected brightness temperature** (ODE `IRPBT2/4`, ~100 m, with `Solar_time` + `Solar_longitude`) ; TES TSDR | ~100 m (THEMIS) | brightness temperature at one local time per image (not a climatology) | **B** |
| Geology | CRISM MTRDR/TRDR (targeted, 18–36 m) ; CRISM MRDR (multispectral mosaic) ; **OMEGA global maps** (olivine, pyroxene, ferric, hydrated sites; 40 ppd) ; GRS elements ; TES emissivity | 18 m–5° | mineralogy | **A** (where covered) |
| Albedo | **OMEGA `ALBEDO_R1080` global NIR albedo** (40 ppd ≈ 1.5 km, 203 MB) ; THEMIS VIS albedo (per image) | 1.5 km / ~100 m | 1.08 µm Lambert-type albedo | **A** (NIR ≠ broadband → compare as rank) |
| Dust | TES dust optical depth maps (registry) ; OMEGA nanophase ferric oxide map (surface dust cover) | daily global maps, coarse | column dust opacity (A) ; surface dust (B) | **A / B** |
| Dust-storm frequency | derive from TES dust-opacity time series (MY24–MY27 ≈ 1999–2004) | coarse | storm occurrence in ~3 Mars years | **B** (short record) |
| Atmosphere | TES atmospheric recalibration (opacity), MGS radio occultation (T/p profiles), TGO ACS/NOMAD (ODE lists mostly telecommand products) | coarse | T, p, opacity profiles | **B** |
| Terrain models (bonus) | HiRISE DTMs, HRSC DTMs, CTX EDR (166,241 images; DTMs not archived as products) | 1 m – 100 m | stereo topography | **A** but patchy |

## 5. Earth counterparts available (for the comparison side)

All found in CMR unless noted. Resolution as stated in CMR.

| Parameter | Product (short name) | Res. | Period | Rel. vs Moon/Mars |
|---|---|---|---|---|
| Slope / roughness | NASADEM_HGT, SRTMGL1, ASTGTM v3 ; Copernicus DEM GLO-30/90 (STAC `cop-dem-glo-30-dged-cog`) ; GEDI02_A | 30 m / 90 m | 2000 / 2010–15 | **A** (same quantity, set same baseline) |
| Rock abundance | – (no global product) ; proxy: ASTER emissivity AG100, bare-soil (Europe only, CLMS) | 100 m | | **C** |
| Ice / permafrost | **ESA CCI Permafrost** (ESA OSC) ; MOD10CM snow cover ; GRACE mascons ; NSIDC ground-ice map *[not found by our CMR IDs]* | ~1 km / 0.05° / 0.5° | | **B** |
| Illumination | computed from latitude + DEM horizon | – | | **A** |
| Thermal inertia | apparent thermal inertia from MODIS LST day–night + MCD43 albedo (derived) ; Copernicus LST daily cycle (3–5 km hourly) | 0.05° | | **B** (ATI ≠ TI → rank) |
| Temperature | MOD11C3 / MYD11C3 LST monthly ; Sentinel-3 SLSTR LST ; CLMS hourly LST | 0.05° / 1 km / 3–5 km | 2000– | **A** as values, but ranges never overlap Moon PSRs → "direction" method |
| Geology | EMITL2BMIN (minerals, 60 m, 2022–, arid belt only) ; ASTER AG100 emissivity ; AST_L1T | 60–100 m | | **A–B** |
| Albedo | MCD43C3 (0.05°) ; S3 albedo (ESA OSC) | 0.05° | 2000– | **A** (broadband) |
| Dust | M2TMNXAER (MERRA-2 AOD, 0.5×0.625°) ; MCD19A2 (1 km AOD) ; CALIPSO dust climatology (ESA OSC) ; S3 SLSTR AOD ; S5P aerosol index | 1 km – 0.5° | 1980– | **A** (opacity ↔ opacity, rank) |
| Dust-storm frequency | MERRA-2 daily AOD thresholds ; CALIPSO dust layers | 0.5° | 1980– | **B** |
| Atmosphere / wind / humidity | M2TMNXSLV, M2TMNXFLX ; GPM_3IMERGM precip | 0.5° / 0.1° | | **A** (as limits of analogy) |
| Vegetation (exclusion) | MOD13C2 NDVI ; MCD12C1 land cover ; MOD44W water mask | 0.05° / 250 m | | **A** |
| SAR (↔ Mini-RF / SHARAD) | Sentinel-1 GRD (STAC + ASF via CMR) ; RADARSAT-1 GeoTIFF (CSA FTP) ; ALOS PALSAR RTC (ASF) | 10–30 m | 1995– | **B** (C-band ≠ S-band ; compare CPR-like ratios only with care) |
| Visual check | GIBS/Worldview layers (MODIS LST, NDVI, MERRA-2 AOD, ASTER GDEM relief, …) | tiles | | visual only |

---

## 6. Consequences for the project

1. **Add ODE as a second query path** next to `pds.peppi`. It closes these gaps from
   official sources: Moon illumination + PSR maps (LOLA), Mars thermal inertia (TES TIMAP),
   Mars albedo + mineral maps (OMEGA), Mars surface temperature (THEMIS IR BT), HiRISE/HRSC DTMs.
2. **Still missing from the official sources:** Mars rock abundance, Moon thermal inertia
   (only a proxy), a ground-ice map for Earth in CMR (use ESA CCI Permafrost), global rock
   abundance on Earth.
3. **Compare by rank, not by value,** for every pair where wavelength/method differs: albedo
   (1064 nm / 1.08 µm vs MODIS broadband), thermal inertia (TI vs ATI), radar (S vs C band),
   temperature (Moon PSR 25–100 K never reached on Earth).
4. **Use GIBS/Worldview only for visual confirmation,** never as numeric input.
5. **Access:** PDS, ODE, CMR search, GIBS, ESA OSC and CSA RADARSAT-1 need no account.
   Earthdata downloads, Copernicus downloads and JAXA need (free) accounts → create them early.

## Endpoints used

- PDS Registry API: `https://pds.mcp.nasa.gov/api/search/1/products`
- ODE REST: `https://oderest.rsl.wustl.edu/live2/?query=iipy|product&output=JSON&odemetadb=moon|mars`
- CMR: `https://cmr.earthdata.nasa.gov/search/collections.umm_json?short_name=...`
- GIBS: `https://gibs.earthdata.nasa.gov/wmts/epsg4326/best/1.0.0/WMTSCapabilities.xml`
- Copernicus STAC: `https://stac.dataspace.copernicus.eu/v1/collections`
- CSA via CKAN: `https://open.canada.ca/data/api/action/package_search?q=RADARSAT-1`
- ESA OSC: `https://esa-earthcode.github.io/open-science-catalog-metadata/catalog.json`
- Diviner product page: `https://pds-geosciences.wustl.edu/missions/lro/diviner.htm`
