"""Known / candidate NASA landing sites on the Moon and Mars + PDS data coverage check.

For every site, the script asks the PDS Registry how many products of each
*spatial* dataset in pds_test.DATASETS overlap a small box around the site
(capped at --cap per dataset, because peppi's count() is broken).

Coordinates: planetocentric latitude, 0-360 deg East longitude.
COORDINATES ARE APPROXIMATE (crater / region centres, ~0.5-1 deg) and must be
verified against the official sources before publishing (see "source" column).
Artemis III region shapes are ~15x15 km; NASA's official region polygons are
not in this list - here only the named feature they are anchored to is used.

    python landing_sites.py                 # all sites, writes output/landing_sites_coverage.csv
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
    ("Peak near Shackleton", "moon", -89.0, 200.0, "Artemis III region (2022)", "NASA 2022-08-19 - coords approx"),
    ("Connecting Ridge (Shackleton-de Gerlache)", "moon", -89.4, 260.0, "Artemis III region (2022)", "NASA 2022-08-19 - coords approx"),
    ("Faustini Rim A", "moon", -87.3, 77.0, "Artemis III region (2022)", "NASA 2022; ESA (Faustini centre)"),
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
