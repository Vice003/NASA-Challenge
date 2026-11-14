#!/usr/bin/env bash
# Downloads elevation models and place names to data/raw. Earth climate layers come from vicente/derived.
set -euo pipefail
D="${1:-data/raw}"; mkdir -p "$D"; cd "$D"
dl(){ curl -sSL -o "$2" "$1"; echo "$2"; }
dl https://github.com/fatiando-data/earth-topography-10arcmin/releases/download/v1/earth-topography-10arcmin.nc earth_topo.nc
dl https://github.com/fatiando-data/moon-topography-10arcmin/releases/download/v1/moon-topography-10arcmin.nc moon_topo.nc
dl https://raw.githubusercontent.com/SHTOOLS/SHTOOLS/master/examples/ExampleDataFiles/MarsTopo719.shape MarsTopo719.shape
NE=https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master
for f in 10m_physical/ne_10m_geography_regions_polys 50m_cultural/ne_50m_admin_0_countries 10m_cultural/ne_10m_populated_places_simple; do
  for e in shp shx dbf prj cpg; do dl "$NE/$f.$e" "$(basename "$f").$e"; done
done
