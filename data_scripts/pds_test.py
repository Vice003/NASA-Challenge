"""Query NASA PDS for Moon and Mars datasets relevant to the Earth-analog challenge.

For every curated dataset below, the script pulls product metadata from the PDS
Registry (via pds.peppi), flattens the useful fields (coverage, resolution,
download URL, file size, units, ...) and writes them to CSV + JSON in ./output.
Optionally it downloads the small data files directly.

Each dataset is tagged with the analog "dimension" it supports (terrain, thermal,
ice, radar, mineralogy, dust), matching the judging criteria in AGENT_PROMPT.md.

Usage examples
--------------
    python pds_test.py                                  # Moon + Mars, 10 products/dataset
    python pds_test.py --body moon --region moon_south_pole
    python pds_test.py --body mars --region mars_jezero --limit 25
    python pds_test.py --bbox -90 -80 0 360 --body moon  # custom lat_min lat_max lon_min lon_max
    python pds_test.py --list-datasets
    python pds_test.py --body moon --region moon_south_pole --download-max-mb 50

Notes
-----
* Bounding boxes use planetocentric latitude and 0-360 degrees East longitude,
  which is what LOLA, MOLA MEGDR and CRISM labels use.
* The bbox filter only applies to datasets whose labels carry cart:Bounding_Coordinates
  ("spatial": True). Non-spatial datasets (polar products, tables, time series)
  are returned unfiltered and flagged with region_filter_applied = False.
* HiRISE, CTX and THEMIS are not indexed in the PDS4 registry under those names;
  get them from their node archives (PDS Imaging / ASU / HiRISE site).
"""

import argparse
import json
import logging
import sys
import urllib.request
from pathlib import Path

import pandas as pd
import pds.peppi as pep

logging.getLogger("pds.peppi").setLevel(logging.ERROR)

OUT_DIR = Path(__file__).resolve().parent / "output"

# --------------------------------------------------------------------------- #
# Verified context LIDs (Context() lookup is slow, so they are hardcoded)
# --------------------------------------------------------------------------- #
TARGETS = {
    "moon": "urn:nasa:pds:context:target:satellite.earth.moon",
    "mars": "urn:nasa:pds:context:target:planet.mars",
}

# --------------------------------------------------------------------------- #
# Curated datasets. "collections" are versionless collection LIDs; products are
# matched via ops:Provenance.ops:ancestor_refs so every version is found.
# --------------------------------------------------------------------------- #
DATASETS = {
    # ------------------------------- MOON ---------------------------------- #
    "lola_gridded": {
        "body": "moon", "dimension": "terrain",
        "what": "LRO LOLA gridded DEM, slope, roughness, albedo (global + polar tiles)",
        "collections": ["urn:nasa:pds:lro_lola_rdr:data_gridded"],
        "spatial": True,
    },
    "diviner_gdr_l3": {
        "body": "moon", "dimension": "thermal",
        "what": "LRO Diviner Level-3 gridded surface temperatures (files can exceed 1 GB)",
        "collections": ["urn:nasa:pds:lro_diviner_derived1:data_derived_gdr_level3"],
        "spatial": True,
    },
    "diviner_polar_resource": {
        "body": "moon", "dimension": "ice",
        "what": "Diviner Polar Resource Product: Tmax/Tavg and ice-stability depth (N/S pole)",
        "collections": ["urn:nasa:pds:lro_diviner_derived1:data_derived_prp"],
        "spatial": False,
    },
    "diviner_polar_cumulative": {
        "body": "moon", "dimension": "thermal",
        "what": "Diviner Polar Cumulative Product: polar bolometric temperatures by season/local time",
        "collections": ["urn:nasa:pds:lro_diviner_derived1:data_derived_pcp"],
        "spatial": False,
    },
    "minirf_mosaic": {
        "body": "moon", "dimension": "radar",
        "what": "LRO Mini-RF global S-band mosaic (CPR = roughness / ice proxy; SAR analog)",
        "collections": ["urn:nasa:pds:lro_minirf_globalmosaic:data_globalmosaic"],
        "spatial": True,
    },
    "lend_averaged": {
        "body": "moon", "dimension": "ice",
        "what": "LRO LEND averaged neutron maps (hydrogen / water-ice proxy)",
        "collections": ["urn:nasa:pds:lro_lend:data_science_averaged"],
        "spatial": False,
    },
    "space_weathering": {
        "body": "moon", "dimension": "mineralogy",
        "what": "Trang 2020 space-weathering maps (npFe / surface maturity, from Kaguya MI)",
        "collections": ["urn:nasa:pds:trang2020_moon_space_weathering:data"],
        "spatial": True,
    },
    # ------------------------------- MARS ---------------------------------- #
    "mola_megdr": {
        "body": "mars", "dimension": "terrain",
        "what": "MGS MOLA MEGDR gridded topography (4, 16, 128 px/deg)",
        "collections": [
            "urn:nasa:pds:mgs_mola_topography_derived:data_meg004",
            "urn:nasa:pds:mgs_mola_topography_derived:data_meg016",
            "urn:nasa:pds:mgs_mola_topography_derived:data_meg128",
        ],
        "spatial": True,
    },
    "crism_mtrdr": {
        "body": "mars", "dimension": "mineralogy",
        "what": "MRO CRISM MTRDR map-projected targeted cubes + spectral parameters (~18-36 m/px)",
        "collections": ["urn:nasa:pds:mro_crism_mtrdr:data_mtrdr"],
        "spatial": True,
    },
    "grs_elements": {
        "body": "mars", "dimension": "mineralogy",
        "what": "Mars Odyssey GRS element concentrations (H2O, Cl, Fe, Si, K, Th, ... 5x5 deg)",
        "collections": ["urn:nasa:pds:odyssey_grs_elements:data_element_concentrations"],
        "spatial": False,
    },
    "grs_neutron": {
        "body": "mars", "dimension": "ice",
        "what": "Mars Odyssey improved derived neutron data (subsurface hydrogen / ice)",
        "collections": ["urn:nasa:pds:mesick_pdart19_odyssey_idnd:data_idnd"],
        "spatial": False,
    },
    "tes_dust": {
        "body": "mars", "dimension": "dust",
        "what": "MGS TES column dust optical-depth global maps (dust storms)",
        "collections": ["urn:nasa:pds:mgs_tes_atmos_dust-ice:data_derived_maps"],
        "spatial": False,
    },
    "tes_emissivity": {
        "body": "mars", "dimension": "mineralogy",
        "what": "MGS TES recalibrated surface emissivity (thermal-IR mineralogy)",
        "collections": ["urn:nasa:pds:mgs_tes_recalib_atmos:data_derived_surf-emissivity"],
        "spatial": False,
    },
    "sharad_3d": {
        "body": "mars", "dimension": "radar",
        "what": "MRO SHARAD 3D radargrams of polar layered deposits (files are VERY large)",
        "collections": ["urn:nasa:pds:mro_sharad_3d:data"],
        "spatial": True,
    },
}

# lat_min, lat_max, lon_min, lon_max  (planetocentric, 0-360 E)
REGIONS = {
    "global": None,
    "moon_south_pole": ("moon", (-90, -80, 0, 360)),  # Artemis III candidate regions
    "moon_north_pole": ("moon", (80, 90, 0, 360)),
    "mars_north_polar": ("mars", (70, 90, 0, 360)),
    "mars_south_polar": ("mars", (-90, -70, 0, 360)),
    "mars_jezero": ("mars", (17, 20, 76, 79)),      # Perseverance landing site
    "mars_gale": ("mars", (-6.5, -3.5, 136, 139)),  # Curiosity landing site
}

BBOX = "cart:Bounding_Coordinates.cart:"
FIELDS = [
    "lid", "lidvid", "vid", "title", "ref_lid_instrument", "ref_lid_target",
    "pds:Target_Identification.pds:name",
    "lro:LRO_Parameters.lro:product_type",
    "pds:Time_Coordinates.pds:start_date_time", "pds:Time_Coordinates.pds:stop_date_time",
    BBOX + "south_bounding_coordinate", BBOX + "north_bounding_coordinate",
    BBOX + "west_bounding_coordinate", BBOX + "east_bounding_coordinate",
    "cart:Coordinate_Representation.cart:pixel_resolution_x",
    "cart:Coordinate_Representation.cart:pixel_scale_x",
    "ops:Data_File_Info.ops:file_ref", "ops:Data_File_Info.ops:file_size",
    "ops:Data_File_Info.ops:file_name",
    "ops:Label_File_Info.ops:file_ref",
    "pds:Field_Character.pds:name", "pds:Field_Character.pds:unit",
    "pds:Field_Binary.pds:name", "pds:Field_Binary.pds:unit",
    "pds:Element_Array.pds:unit", "pds:Element_Array.pds:data_type",
    "pds:Object_Statistics.pds:minimum", "pds:Object_Statistics.pds:maximum",
    "pds:Special_Constants.pds:missing_constant",
    "description",
]

LABEL_EXT = (".lbl", ".xml", ".txt", ".fmt")


def bbox_clause(lat_min, lat_max, lon_min, lon_max):
    """Overlap test between a product's bounding box and the region."""
    clause = (f"{BBOX}south_bounding_coordinate le {lat_max} and "
              f"{BBOX}north_bounding_coordinate ge {lat_min}")
    if not (lon_min <= 0 and lon_max >= 360):
        clause += (f" and {BBOX}west_bounding_coordinate le {lon_max} and "
                   f"{BBOX}east_bounding_coordinate ge {lon_min}")
    return clause


def first(props, key, default=None):
    v = props.get(key)
    return v[0] if v else default


def to_float(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def flatten(product, key, ds, region_applied):
    """Turn a PDS product into one flat row with the fields we care about."""
    p = product.properties
    files = list(zip(p.get("ops:Data_File_Info.ops:file_ref", []),
                     p.get("ops:Data_File_Info.ops:file_size", [])))
    data_files = [(u, int(s)) for u, s in files if not u.lower().endswith(LABEL_EXT)] \
        or [(u, int(s)) for u, s in files]
    data_url, data_size = max(data_files, key=lambda f: f[1]) if data_files else (None, 0)

    columns = p.get("pds:Field_Character.pds:name") or p.get("pds:Field_Binary.pds:name") or []
    units = p.get("pds:Field_Character.pds:unit") or p.get("pds:Field_Binary.pds:unit") \
        or p.get("pds:Element_Array.pds:unit") or []
    desc = " ".join(d for d in p.get("description", []) if d and len(d) > 20)[:400]

    return {
        "dataset": key,
        "body": ds["body"],
        "dimension": ds["dimension"],
        "lidvid": product.id,
        "title": first(p, "title"),
        "instrument": (first(p, "ref_lid_instrument") or "").rsplit(":", 1)[-1],
        "product_type": first(p, "lro:LRO_Parameters.lro:product_type"),
        "start_time": first(p, "pds:Time_Coordinates.pds:start_date_time"),
        "stop_time": first(p, "pds:Time_Coordinates.pds:stop_date_time"),
        "lat_min": to_float(first(p, BBOX + "south_bounding_coordinate")),
        "lat_max": to_float(first(p, BBOX + "north_bounding_coordinate")),
        "lon_west": to_float(first(p, BBOX + "west_bounding_coordinate")),
        "lon_east": to_float(first(p, BBOX + "east_bounding_coordinate")),
        # units differ between missions (m or km per pixel); pixels/degree is consistent
        "pixel_resolution_as_labelled": to_float(first(p, "cart:Coordinate_Representation.cart:pixel_resolution_x")),
        "pixels_per_degree": to_float(first(p, "cart:Coordinate_Representation.cart:pixel_scale_x")),
        "value_min": to_float(first(p, "pds:Object_Statistics.pds:minimum")),
        "value_max": to_float(first(p, "pds:Object_Statistics.pds:maximum")),
        "data_type": first(p, "pds:Element_Array.pds:data_type"),
        "columns": ";".join(columns[:40]),
        "units": ";".join(dict.fromkeys(u for u in units if u)),
        "data_url": data_url,
        "data_size_mb": round(data_size / 1e6, 2),
        "all_file_urls": " ".join(u for u, _ in files),
        "label_url": first(p, "ops:Label_File_Info.ops:file_ref"),
        "region_filter_applied": region_applied,
        "description": desc,
    }


def bbox_area(r):
    """Approximate footprint in degree^2 (smaller = more local / higher resolution)."""
    if None in (r["lat_min"], r["lat_max"], r["lon_west"], r["lon_east"]):
        return float("inf")
    return (r["lat_max"] - r["lat_min"]) * ((r["lon_east"] - r["lon_west"]) % 360 or 360)


def query_dataset(client, key, ds, bbox, limit):
    region_applied = bool(bbox and ds["spatial"])
    if not region_applied:
        return _fetch(client, key, ds, None, limit)
    # Global maps overlap every region, so pull a wider pool and put the most
    # local (smallest-footprint, usually highest-resolution) products first.
    pool = _fetch(client, key, ds, bbox, max(limit * 10, 200))
    return sorted(pool, key=bbox_area)[:limit]


def _fetch(client, key, ds, bbox, limit):
    rows, seen = [], {}
    region_applied = bbox is not None
    for coll in ds["collections"]:
        q = pep.Products(client).filter(f'ops:Provenance.ops:ancestor_refs eq "{coll}"')
        if region_applied:
            q = q.filter(bbox_clause(*bbox))
        q = q.fields(list(FIELDS))
        for product in q:
            row = flatten(product, key, ds, region_applied)
            lid = row["lidvid"].split("::")[0]
            vid = to_float(row["lidvid"].split("::")[-1]) or 0
            # keep only the newest version of each product
            if lid in seen:
                if vid > seen[lid][0]:
                    rows[seen[lid][1]] = row
                    seen[lid] = (vid, seen[lid][1])
                continue
            seen[lid] = (vid, len(rows))
            rows.append(row)
            if len(rows) >= limit:
                return rows
    return rows


def download(rows, max_mb, out_dir):
    out_dir.mkdir(parents=True, exist_ok=True)
    for r in rows:
        if not r["data_url"] or r["data_size_mb"] > max_mb:
            continue
        for url in r["all_file_urls"].split():
            dest = out_dir / r["dataset"] / url.rsplit("/", 1)[-1]
            if dest.exists():
                continue
            dest.parent.mkdir(parents=True, exist_ok=True)
            print(f"   downloading {url}")
            try:
                urllib.request.urlretrieve(url, dest)
            except Exception as e:  # keep going on single failures
                print(f"   !! failed: {e}")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--body", choices=["moon", "mars", "both"], default="both")
    ap.add_argument("--region", choices=list(REGIONS), default="global")
    ap.add_argument("--bbox", nargs=4, type=float, metavar=("LAT_MIN", "LAT_MAX", "LON_MIN", "LON_MAX"))
    ap.add_argument("--datasets", nargs="+", choices=list(DATASETS), help="subset of datasets")
    ap.add_argument("--limit", type=int, default=10, help="max products per dataset")
    ap.add_argument("--download-max-mb", type=float, default=0,
                    help="download files of products whose data file is <= this size (0 = off)")
    ap.add_argument("--list-datasets", action="store_true")
    args = ap.parse_args()

    if args.list_datasets:
        for k, d in DATASETS.items():
            print(f"{k:26s} {d['body']:5s} {d['dimension']:11s} {d['what']}")
        return

    bbox, region_name = None, args.region
    if args.bbox:
        bbox, region_name = tuple(args.bbox), "custom"
    elif REGIONS[args.region]:
        region_body, bbox = REGIONS[args.region]
        if args.body == "both":
            args.body = region_body
        elif args.body != region_body:
            sys.exit(f"Region {args.region} belongs to {region_body}, not {args.body}")

    bodies = ["moon", "mars"] if args.body == "both" else [args.body]
    selected = {k: d for k, d in DATASETS.items()
                if d["body"] in bodies and (not args.datasets or k in args.datasets)}

    client = pep.PDSRegistryClient()
    all_rows = []
    print(f"Region: {region_name} {bbox or ''}  |  limit {args.limit}/dataset\n")
    for key, ds in selected.items():
        try:
            rows = query_dataset(client, key, ds, bbox, args.limit)
        except Exception as e:
            print(f"[{key}] ERROR: {e}")
            continue
        total_mb = sum(r["data_size_mb"] for r in rows)
        flag = "" if (not bbox or ds["spatial"]) else "  (non-spatial: not region-filtered)"
        print(f"[{key}] {ds['body']}/{ds['dimension']}: {len(rows)} products, {total_mb:,.0f} MB{flag}")
        for r in rows[:3]:
            print(f"    {r['title'][:75]}  [{r['data_size_mb']:,.1f} MB]")
        all_rows.extend(rows)

    if not all_rows:
        print("No products found.")
        return

    OUT_DIR.mkdir(exist_ok=True)
    stem = f"pds_{args.body}_{region_name}"
    df = pd.DataFrame(all_rows)
    df.to_csv(OUT_DIR / f"{stem}.csv", index=False)
    (OUT_DIR / f"{stem}.json").write_text(json.dumps(all_rows, indent=2))
    print(f"\nSaved {len(df)} rows -> {OUT_DIR / (stem + '.csv')} (+ .json)")

    if args.download_max_mb > 0:
        download(all_rows, args.download_max_mb, OUT_DIR / "raw")


if __name__ == "__main__":
    main()
