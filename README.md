# Analog Finder

Where on Earth looks most like a landing site on the Moon or Mars?
The Analog Finder compares 143,306 land cells on Earth (20 arcminutes each, about 37 km)
with the fingerprint of a target site across nine dimensions and ranks them by similarity.

`index.html` is the finished interactive map. It needs no server: open the file in a browser.

## Target sites

| Target | Location | Why |
|---|---|---|
| Mars, Arcadia Planitia | 40° N, 200° E | flat plain with near-surface ice |
| Mars, Jezero Crater | 18.4° N, 77.5° E | Perseverance landing site |
| Moon, South Pole (Shackleton) | 89.7° S | Artemis region |

## Dimensions

| Dimension | Earth | Moon / Mars |
|---|---|---|
| Slope (18.5 km baseline) | ETOPO1 | LOLA, MOLA (measured) |
| Relief (spread of elevation over about 90 km) | ETOPO1 | LOLA, MOLA (measured) |
| Highest sun elevation | from latitude and axial tilt | from latitude and axial tilt |
| Mean annual temperature | WorldClim 2.1 | literature value, rounded |
| Annual precipitation | WorldClim 2.1 | 0 |
| Vegetation (NDVI) | NASA MODIS/Terra MOD13C2, 2023 | 0 |
| Air pressure | from elevation (standard atmosphere) | literature value, rounded |
| Ground ice | estimate from mean annual temperature | yes / no |
| Day-night swing | NASA MODIS/Aqua MYD11C3, 2023 | rough estimate |

## Method

For each dimension, 100 points means identical to the target site and 0 points means as unlike it
as the least similar land on Earth (2nd to 98th percentile, area-weighted). The total score is the
weighted mean, and the weights can be changed in the map. Where a target value lies outside what
Earth offers, no cell reaches 100 points, so the number shows how far the analogy holds.

The terrain of all three bodies is limited to the same wavelength (18.5 km) so that slope and
relief are comparable. Glaciers, ice shelves and sea are hidden.

Cross-check: the method does not know the established analog sites. For Jezero the Atacama comes
out first, and for the lunar south pole Haughton Crater and the McMurdo Dry Valleys rank above
99 to 100% of the land area.

## Result (all weights equal)

| Target | Best match | Points |
|---|---|---|
| Mars, Arcadia Planitia | Kunlun Mountains, northern Tibet | 66 |
| Mars, Jezero Crater | Atacama | 73 |
| Moon, South Pole | Victoria Land (Antarctica) and Ellesmere Island | 57 |

## Limits

- The 18.5 km baseline describes landscape types, not landing sites.
- MODIS/Aqua observes at about 13:30 and 01:30 local time, close to but not exactly at the daily
  maximum and minimum.
- The target values for temperature, air pressure, ground ice and day-night swing are rounded
  estimates and still need sources.
- Mineralogy, dust and the subsurface (lava tubes) are missing.
- Gravity, vacuum and radiation cannot be reproduced anywhere on Earth.

## Run it yourself

```bash
pip install -r requirements.txt
bash scripts/fetch_data.sh data/raw                 # terrain, climate, Natural Earth
cp data/derived/*.npz data/raw/                     # ready-made MODIS layers
mkdir -p out
python scripts/pipeline.py data/raw out             # features and fingerprints -> out/data.json
python scripts/rank.py out                          # ranking and cross-check in the terminal
python scripts/build_page.py web/template.html out/data.json index.html
```

The raw MODIS data (24 files, about 1.7 GB) is not in the repo. To rebuild the layers in
`data/derived`, download the products `MYD11C3` and `MOD13C2` (version 061, all months of 2023)
through [Earthdata Search](https://search.earthdata.nasa.gov/) into one folder and run:

```bash
python scripts/modis_lst.py  FOLDER_WITH_HDF data/raw   # day-night swing  -> modis_dtr.npz
python scripts/modis_ndvi.py FOLDER_WITH_HDF data/raw   # annual mean NDVI -> modis_ndvi.npz
```

## Data sources

- NASA MODIS/Aqua MYD11C3 and MODIS/Terra MOD13C2, version 061 (LP DAAC)
- LOLA topography of the Moon, 10 arcminutes (fatiando-data)
- MOLA spherical harmonic model MarsTopo719 (SHTOOLS example data)
- ETOPO1 (NOAA), 10 arcminutes (fatiando-data)
- WorldClim 2.1, bio1 and bio12 (via the R package letsR)
- Natural Earth (glaciers, ice shelves, regions, countries, places)

The terms of use of each source still apply. The input data is therefore fetched by script and
not redistributed in the repo.
