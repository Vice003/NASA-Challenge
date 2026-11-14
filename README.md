# Analog Finder

Where on Earth looks most like a landing site on the Moon or Mars?
The Analog Finder compares 101,278 land cells on Earth (20 arcminutes each, about 37 km) with the
fingerprint of a target site across eleven dimensions, ranks them, and says for every cell where the
analogy holds and where it breaks.

`index.html` is the finished interactive map. It needs no server: open the file in a browser.

This is the coarse first pipeline (`scripts/`). The team's fine pipeline (about 5 km cells, see
`VERARBEITUNGSPLAN.md`) is replacing it; until that passes its checks, this one is the fallback.

## Target sites

| Target | Location | Why |
|---|---|---|
| Mars, Arcadia Planitia | 40° N, 200° E | flat plain with near-surface ice |
| Mars, Jezero Crater | 18.4° N, 77.5° E | Perseverance landing site |
| Moon, South Pole (Shackleton) | 89.7° S | Artemis region |

## Dimensions

Target values carry a label: **measured** (from LOLA or MOLA with the same code as on Earth),
**computed** (geometry or physics), **literature** (rounded value for a well-established property)
or **estimate** (rough value where instruments differ between the bodies; counts half by default).

| Dimension | Earth | Target value |
|---|---|---|
| Slope (18.5 km baseline) | ETOPO1 | measured |
| Relief (spread of elevation over about 90 km) | ETOPO1 | measured |
| Highest sun elevation | latitude and axial tilt | computed |
| Mean surface temperature | MODIS Terra + Aqua LST, 2003–2024 | literature (Mars), estimate (Moon) |
| Annual precipitation | MERRA-2, 2003–2024 | computed (0) |
| Vegetation (NDVI) | MODIS MOD13C2, 2003–2024 | computed (0) |
| Air pressure | MERRA-2 | literature (Mars), computed (Moon) |
| Ground ice | estimate from mean surface temperature | literature |
| Apparent thermal inertia, (1 − albedo) / day-night swing | MODIS MCD43C3 and LST | estimate (Mars), none (Moon) |
| Albedo | MODIS MCD43C3, snow-free | estimate |
| Dust optical depth | MERRA-2 | estimate (Mars), computed (Moon) |

The multi-year Earth layers come from `vicente/derived/`. Cells that are permanent ice, or more than
half water, forest, cropland or city (MODIS MCD12C1), are removed before ranking.

## Method

For each dimension, 100 points means identical to the target site and 0 points means as unlike it
as the least similar land on Earth (2nd to 98th percentile, area-weighted). The total is the weighted
mean over the dimensions that have both a target value and a value for the cell; missing values stay
missing and are never replaced by 0. A cell is ranked when at least 80% of the weight is covered.
Where a target value lies outside what Earth offers, no cell reaches 100 points, so the number shows
how far the analogy holds.

The terrain of all three bodies is limited to the same wavelength (18.5 km) so that slope and relief
are comparable.

## Result (default weights)

| Target | Best match | Points | Known analog check |
|---|---|---|---|
| Mars, Arcadia Planitia | Kunlun Mountains, northern Tibet | 69 | Qaidam Basin ahead of nearly all land (above 99.5%), Haughton Crater above 93% |
| Mars, Jezero Crater | Tibesti Mountains, Chad | 73 | Atacama above 99%, Death Valley above 93% |
| Moon, South Pole | Ellesmere Island, Canada | 66 | Svalbard and Haughton Crater above 99% |

Checks (`python scripts/rank.py out`, also shown in the map):

| Check | Arcadia | Jezero | Moon |
|---|---|---|---|
| Humid, vegetated land: mean rank (should be low) | 17% | 37% | 23% |
| Top 20 regions kept when all weights vary by ±25% (mean of 200 runs) | 91% | 95% | 91% |
| Same, worst run | 45% | 85% | 80% |
| Top 20 regions outside every known analog | 19 | 18 | 19 |

The method is not told which sites are known analogs. The list of known sites is the team's
(`vicente/scoring/categories.py`).

## Limits

- Cells are about 37 km wide and the terrain baseline is 18.5 km: landscape types, not landing sites.
- ETOPO1 (NOAA) is the one input that is not a NASA or ESA product. The fine pipeline uses the
  Copernicus DEM.
- Albedo, thermal inertia and dust are measured with different instruments on each body. Their target
  values are rough estimates and should be compared by rank once measured values exist
  (`planetary/targets.json`).
- The lunar temperature target is a rough estimate. Nothing on Earth comes close, so it changes the
  score but not the order.
- Ground ice on Earth is estimated from temperature.
- Mineralogy and the subsurface (lava tubes) are missing.
- Gravity, vacuum and radiation cannot be reproduced anywhere on Earth.

## Run it yourself

```bash
pip install -r requirements.txt
bash scripts/fetch_data.sh data/raw      # elevation models and place names
mkdir -p out
python scripts/pipeline.py data/raw out data/derived vicente/derived   # -> out/data.json
python scripts/rank.py out                                             # ranking and checks -> out/controls.json
python scripts/build_page.py web/template.html out/data.json index.html out/controls.json
```

`scripts/modis_landcover.py` builds `data/derived/modis_landcover.npz` from MCD12C1. The scripts
`modis_lst.py`, `modis_ndvi.py` and `modis_albedo.py` produced the single-year 2023 layers the first
version used; the pipeline now reads the 2003–2024 layers in `vicente/derived/` instead.

## Data sources

- NASA MODIS: MOD11C3, MYD11C3, MOD13C2, MCD43C3, MCD12C1, version 061 (LP DAAC)
- NASA MERRA-2 (GES DISC)
- LOLA topography of the Moon, 10 arcminutes (fatiando-data)
- MOLA spherical harmonic model MarsTopo719 (SHTOOLS example data)
- ETOPO1 (NOAA), 10 arcminutes (fatiando-data)
- Natural Earth, for place names only
