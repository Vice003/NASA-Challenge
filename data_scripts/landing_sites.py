"""Known / candidate NASA landing sites on the Moon and Mars + PDS data coverage check.

For every site, the script asks the PDS Registry how many products of each
*spatial* dataset in pds_test.DATASETS overlap a small box around the site
(capped at --cap per dataset, because peppi's count() is broken).

Coordinates: planetocentric latitude, 0-360 deg East longitude.
COORDINATES ARE APPROXIMATE (crater / region centres, ~0.5-1 deg) and must be
verified against the official sources before publishing (see "source" column).
Artemis III region shapes are ~15x15 km; NASA's official region polygons are
not in this list - here only the named feature they are anchored to is used.

Besides the point list SITES, two area lists are used by the screening scripts to
compare candidates with the agencies' picks by area instead of by point:
  MOON_SOUTH_AREAS  NASA Artemis regions as rough areas (anchor + radius)  -> moon_screen.py
  MARS_STUDY_AREAS  human-base study areas as lat/lon boxes                -> mars_screen.py

    python landing_sites.py                # all sites, writes output/landing_sites_coverage.csv
    python landing_sites.py --body moon
"""

import argparse
import logging

import pandas as pd
import pds.peppi as pep

from pds_test import DATASETS, OUT_DIR, bbox_clause

logging.getLogger("pds.peppi").setLevel(logging.ERROR)

# name, body, lat, lon_E, category, source
SITES = [
    # ---- Moon: Artemis III candidate regions (NASA, Oct 2024 update: 9 regions) ----
    ("Peak near Cabeus B", "moon", -82.5, 307.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Haworth", "moon", -87.4, 355.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Malapert Massif", "moon", -86.0, 3.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Mons Mouton Plateau", "moon", -84.5, 32.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Mons Mouton", "moon", -84.0, 31.0, "Artemis III region (2024)", "NASA 2024-10-28"),
    ("Nobile Rim 1 / 2", "moon", -85.3, 53.5, "Artemis III region (2024)", "NASA 2024-10-28 (Nobile crater centre)"),
    ("de Gerlache Rim 2", "moon", -88.5, 272.9, "Artemis III region (2022+2024)", "NASA; ESA (de Gerlache centre)"),
    ("Slater Plain", "moon", -88.0, 110.0, "Artemis III region (2024)", "NASA 2024-10-28 - coords UNVERIFIED"),
    # ---- Moon: 2022 regions dropped/kept + key PSR craters ----
    ("Peak near Shackleton", "moon", -89.005, 125.31, "Artemis III region (2022)",
     "point inside the region, Pena-Asensio et al. 2024 (arXiv 2406.19863, point 1223)"),
    ("Connecting Ridge (Shackleton-de Gerlache)", "moon", -89.4, 260.0, "Artemis III region (2022)", "NASA 2022-08-19 - coords approx"),
    ("Faustini Rim A", "moon", -88.087, 98.36, "Artemis III region (2022)",
     "point inside the region, Pena-Asensio et al. 2024 (arXiv 2406.19863, point 744)"),
    ("Shackleton crater (PSR)", "moon", -89.67, 129.78, "PSR / ice target", "Wikipedia/IAU"),
    ("Cabeus (LCROSS impact, PSR)", "moon", -84.9, 324.5, "PSR / confirmed water ice", "LCROSS 2009"),
    # ---- Moon: previous landings (coordinates approximate, from memory - verify before citing) ----
    ("Apollo 11", "moon", 0.67, 23.47, "landed 1969 (approx coords)", "NASA - verify"),
    ("Apollo 12", "moon", -3.01, 336.58, "landed 1969 (approx coords)", "NASA - verify"),
    ("Apollo 14", "moon", -3.65, 342.53, "landed 1971 (approx coords)", "NASA - verify"),
    ("Apollo 15", "moon", 26.13, 3.63, "landed 1971 (approx coords)", "NASA - verify"),
    ("Apollo 16", "moon", -8.97, 15.50, "landed 1972 (approx coords)", "NASA - verify"),
    ("Apollo 17", "moon", 20.19, 30.77, "landed 1972 (approx coords)", "NASA - verify"),
    ("Chang'e 3", "moon", 44.12, 340.49, "landed 2013, CNSA (approx coords)", "CNSA - verify"),
    ("Chang'e 4", "moon", -45.44, 177.60, "landed 2019, CNSA far side (approx coords)", "CNSA - verify"),
    ("Chang'e 5", "moon", 43.06, 308.08, "landed 2020, CNSA (approx coords)", "CNSA - verify"),
    ("Chang'e 6", "moon", -41.6, 206.0, "landed 2024, CNSA far side (approx coords)", "CNSA - verify"),
    ("Chandrayaan-3", "moon", -69.37, 32.32, "landed 2023, ISRO (approx coords)", "ISRO - verify"),
    ("SLIM", "moon", -13.3, 25.2, "landed 2024, JAXA (approx coords)", "JAXA - verify"),
    ("IM-1 Odysseus", "moon", -80.13, 1.44, "landed 2024 (approx coords)", "NASA CLPS - verify"),
    ("Blue Ghost M1", "moon", 18.56, 61.81, "landed 2025, Mare Crisium (approx coords)", "NASA CLPS - verify"),
    # ---- Mars: active / past landing sites ----
    ("Jezero crater (Perseverance)", "mars", 18.4, 77.5, "landed 2021", "NASA JPL"),
    ("Gale crater (Curiosity)", "mars", -5.4, 137.8, "landed 2012", "NASA JPL"),
    ("Meridiani Planum (Opportunity)", "mars", -1.9, 354.5, "landed 2004", "NASA JPL"),
    ("Gusev / Columbia Hills (Spirit)", "mars", -14.6, 175.5, "landed 2004; M2020 finalist", "NASA JPL"),
    ("Elysium Planitia (InSight)", "mars", 4.5, 135.6, "landed 2018", "NASA JPL"),
    ("Phoenix site (Vastitas Borealis)", "mars", 68.2, 234.3, "landed 2008, ground ice", "NASA JPL"),
    ("Utopia Planitia (Zhurong, CNSA)", "mars", 25.1, 109.9, "landed 2021 (non-NASA)", "CNSA"),
    ("Chryse Planitia (Viking 1)", "mars", 22.27, 312.05, "landed 1976 (approx coords)", "NASA - verify"),
    ("Utopia Planitia (Viking 2)", "mars", 47.64, 134.29, "landed 1976 (approx coords)", "NASA - verify"),
    ("Ares Vallis (Pathfinder)", "mars", 19.13, 326.78, "landed 1997 (approx coords)", "NASA - verify"),
    # ---- Mars: finalist candidates that were NOT chosen ----
    ("NE Syrtis", "mars", 17.8, 77.1, "M2020 finalist", "Mars 2020 site selection"),
    ("Mawrth Vallis", "mars", 24.0, 341.0, "MSL + M2020 candidate", "MSL site selection"),
    ("Eberswalde crater (delta)", "mars", -23.9, 326.7, "MSL finalist", "MSL site selection"),
    ("Holden crater", "mars", -26.4, 325.1, "MSL finalist", "MSL site selection"),
    ("Oxia Planum (Rosalind Franklin, ESA)", "mars", 18.3, 335.4, "ESA ExoMars target", "ESA"),
    # ---- Mars: human-mission candidate areas (ice resources) ----
    ("Arcadia Planitia", "mars", 40.0, 200.0, "SWIM ice target / human EZ", "SWIM, Morgan et al. 2021"),
    ("Deuteronilus Mensae", "mars", 44.0, 22.0, "SWIM ice target / human EZ", "SWIM, Morgan et al. 2021"),
]

# Mars: human-base study areas as boxes (USGS Gazetteer extents, see FAVORITES_AND_PARAMETERS.md),
# planetocentric latitude, 0-360 E. Both are plains / fretted terrain thousands of km wide, so
# "distance to the centre point" says nothing; mars_screen.py checks whether a candidate lies inside.
# name, lat_min, lat_max, lon_min, lon_max
MARS_STUDY_AREAS = [
    ("Arcadia Planitia", 34.68, 54.68, 165.0, 217.0),
    ("Deuteronilus Mensae", 39.57, 50.17, 13.7, 35.4),
]

# NASA Artemis regions at the lunar south pole as ROUGH AREAS (anchor + radius), used by
# moon_screen.py to compare candidates with NASA's picks. NASA has not published region
# outlines that we could retrieve, so each area is "anchor + radius large enough to contain
# the ~15x15 km region". Where the anchor is a crater centre (permanently shadowed, an ice
# target and never a landing site) the radius is crater radius + 10 km so that it reaches the
# sunlit rim. Large radii flatter NASA's side ("best cell anywhere in the circle").
# name, NASA list, lat, lon_E, radius_km, anchor note
MOON_SOUTH_AREAS = [
    ("Haworth", "2024", -87.4, 355.0, 35.0, "crater centre + crater radius ~25 km + 10 km"),
    ("Malapert Massif", "2024", -86.0, 3.0, 15.0, "massif anchor (approx)"),
    ("Nobile Rim 1", "2024", -85.3, 53.5, 48.0, "Nobile crater centre + crater radius ~38 km + 10 km"),
    ("de Gerlache Rim 2", "2024", -88.5, 272.9, 26.0, "crater centre + crater radius ~16 km + 10 km"),
    ("Slater Plain", "2024", -88.0, 110.0, 25.0, "Slater crater centre (UNVERIFIED) + 25 km"),
    ("Peak near Shackleton", "2022", -89.005, 125.31, 7.5, "point inside the region (Pena-Asensio et al. 2024)"),
    ("Faustini Rim A", "2022", -88.087, 98.36, 7.5, "point inside the region (Pena-Asensio et al. 2024)"),
    ("Connecting Ridge", "2022", -89.4, 260.0, 15.0, "approx anchor"),
    # outside the 85 S grid of moon_screen.py -> listed, not scored
    ("Nobile Rim 2", "2024", -84.20, 60.70, 7.5, "best point of the region (Pena-Asensio et al. 2024)"),
    ("Mons Mouton Plateau", "2024", -84.5, 32.0, 15.0, "approx anchor"),
    ("Mons Mouton", "2024", -84.0, 31.0, 15.0, "approx anchor"),
    ("Peak near Cabeus B", "2024", -82.5, 307.0, 15.0, "approx anchor"),
]


def site_box(lat, lon, half=1.0):
    """Small box around the site; near the lunar poles widen longitude (1 deg lon ~ 0-1 km)."""
    lon_half = 15.0 if abs(lat) > 80 else half
    lon_min, lon_max = lon - lon_half, lon + lon_half
    if lon_min < 0 or lon_max > 360:          # wraps the 0/360 seam -> whole longitude band
        lon_min, lon_max = 0, 360
    return (max(lat - half, -90), min(lat + half, 90), lon_min, lon_max)


def coverage(client, ds, box, cap):
    """Count overlapping products (up to cap) and the best pixels/degree among them."""
    n, best_ppd = 0, 0.0
    wanted = [s.lower() for s in ds.get("title_contains", [])]
    for coll in ds["collections"]:
        q = (pep.Products(client)
             .filter(f'ops:Provenance.ops:ancestor_refs eq "{coll}"')
             .filter(bbox_clause(*box))
             .fields(["lid", "title", "cart:Coordinate_Representation.cart:pixel_scale_x",
                      "ops:Harvest_Info.ops:harvest_date_time"]))
        for p in q:
            title = p.properties.get("title", [""])[0].lower()
            if wanted and not any(w in title for w in wanted):
                continue
            n += 1
            ppd = p.properties.get("cart:Coordinate_Representation.cart:pixel_scale_x", ["0"])[0]
            try:
                best_ppd = max(best_ppd, float(ppd))
            except ValueError:
                pass
            if n >= cap:
                return f"{cap}+", best_ppd
    return str(n), best_ppd


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--body", choices=["moon", "mars", "both"], default="both")
    ap.add_argument("--cap", type=int, default=50)
    args = ap.parse_args()

    client = pep.PDSRegistryClient()
    rows = []
    for name, body, lat, lon, cat, src in SITES:
        if args.body != "both" and body != args.body:
            continue
        box = site_box(lat, lon)
        row = {"site": name, "body": body, "lat": lat, "lon_E": lon, "category": cat, "source": src}
        for key, ds in DATASETS.items():
            if ds["body"] != body or not ds["spatial"]:
                continue
            n, ppd = coverage(client, ds, box, args.cap)
            row[key] = n
            row[key + "_max_ppd"] = ppd
        rows.append(row)
        cov = {k: v for k, v in row.items() if k in DATASETS}
        print(f"{name:42s} {cov}")

    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "landing_sites_coverage.csv"
    pd.DataFrame(rows).to_csv(out, index=False)
    print(f"\nSaved -> {out}")


if __name__ == "__main__":
    main()
