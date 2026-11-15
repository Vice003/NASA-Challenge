# Analog Finder

Where on Earth looks most like a landing site on the Moon or Mars?
The Analog Finder compares 101,278 land cells on Earth (20 arcminutes each, about 37 km) with the
fingerprint of a target site across eleven dimensions, ranks them, and says for every cell where the
analogy holds and where it breaks.

`index.html` is the finished interactive map. It needs no server: open the file in a browser.

This is the coarse first pipeline (`scripts/`). The team's fine pipeline (about 5 km cells, see
`VERARBEITUNGSPLAN.md`) is replacing it; until that passes its checks, this one is the fallback.

> **Fine pipeline (0.05°, about 5 km, all 27 targets):** code, results and web app now live in their own repository,
> [Vice003/analog-finder](https://github.com/Vice003/analog-finder).
> Web app: https://vice003.github.io/analog-finder/ · results (German): https://vice003.github.io/analog-finder/ergebnisse.html.
> The copy in `vicente/` here is kept for reference.

## Target sites

14 targets, following the Moon and Mars team's list (`data_scripts/FAVORITES_AND_PARAMETERS.md`, branch `Mars_and_Moon`).

| Target | Location | Role |
|---|---|---|
| Mars, Arcadia Planitia | 40.0° N, 200.0° E | base candidate with shallow ice |
| Mars, Deuteronilus Mensae | 44.9° N, 24.5° E | base candidate with shallow ice |
| Mars, Jezero Crater | 18.4° N, 77.5° E | rover landing site, for comparison |
| Mars, Gale Crater | 4.6° S, 137.4° E | rover landing site, for comparison |
| Moon, Peak near Cabeus B | 83.5° S, 300.0° E | Artemis candidate region |
| Moon, Haworth | 86.8° S, 337.4° E | Artemis candidate region |
| Moon, Malapert Massif | 86.0° S, 359.8° E | Artemis candidate region |
| Moon, Mons Mouton Plateau | 85.4° S, 31.7° E | Artemis candidate region |
| Moon, Mons Mouton | 84.6° S, 29.0° E | Artemis candidate region |
| Moon, Nobile Rim 1 | 85.4° S, 37.4° E | Artemis candidate region |
| Moon, Nobile Rim 2 | 84.0° S, 60.0° E | Artemis candidate region |
| Moon, de Gerlache Rim 2 | 88.2° S, 295.4° E | Artemis candidate region |
| Moon, Slater Plain | 87.5° S, 124.5° E | Artemis candidate region |
| Moon, Shackleton rim | 89.7° S, 129.8° E | south pole reference site |

The centres of the nine Artemis regions are **approximate**. NASA has published their names and maps
(October 2024), not coordinates; the centres here follow the named features. Each region is about 15 km
across, smaller than one cell of this pipeline, so neighbouring regions get almost the same fingerprint.
Measured polygons belong in `planetary/targets.json`.

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

| Target | Best match | Points | New in top 20 | Top 20 kept |
|---|---|---|---|---|
| Mars, Arcadia Planitia | Kunlun Mountains, China | 69 | 19 | 92% |
| Mars, Deuteronilus Mensae | Kunlun Mountains, China | 78 | 19 | 91% |
| Mars, Jezero Crater | Tibesti Mountains, Chad | 73 | 18 | 95% |
| Mars, Gale Crater | Atacama Desert, Chile | 71 | 18 | 94% |
| Moon, all ten sites | Ellesmere Island, Canada | 63–67 | 17–19 | 91–96% |

"New in top 20": regions outside the radius of every known analog. "Top 20 kept": share of the top 20
regions found again when every weight varies by ±25% (mean of 100 random runs).

All ten lunar sites lead to the same region. They share the same estimated temperature, ice and albedo
values and differ only in terrain and sun elevation, and at 18.5 km the terrain differences are too
small to change the order. Telling the Artemis regions apart needs the fine pipeline and measured
Diviner and LOLA values.

Known analogs as a check (`python scripts/rank.py out`, also shown in the map): the Atacama ranks above
99% of the land for Jezero and Gale, the Qaidam Basin above 99.5% for Arcadia and 83% for Deuteronilus,
Haughton Crater and Svalbard above 99% for every lunar site. Humid, vegetated land ranks at 17% (ice
sites), 35–37% (rover sites) and 21–23% (Moon) on average; it should be low.

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
