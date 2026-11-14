"""Global screening of Mars for landing / base sites with A/B-rated PDS data.

Grid: simple cylindrical, 16 px/deg (~3.7 km at the equator), 88 S..88 N
(limit of the MOLA 128 px/deg MEGDR tiles), longitude 0..360 E.

Inputs (output/raw/mars, ~3 GB, see pds_test.py / docs/official_sources_audit.md):
  MOLA MEGDR 128 px/deg (megt*hb)    -> slope (463 m baseline) median/p90, relief, elevation   (A)
  TES thermal inertia 2007 (night)   -> bearing-capacity proxy / dust traps                     (A)
  Odyssey GRS H2O 5x5 smoothed       -> water-equivalent hydrogen, top ~1 m, only |lat|<57.5    (B, ~300 km)
  OMEGA nanophase ferric oxide       -> surface dust cover                                      (B)
  OMEGA 1.08 um albedo               -> reported                                                (A)
  OMEGA hydrous mineral sites (CSV)  -> science bonus (distance to nearest site)               (A where mapped)
  latitude                           -> annual-mean solar insolation (computed, obliquity 25.19 deg) (A)

Not available from the official sources and therefore not scored: rock abundance,
surface temperature (only THEMIS snapshots, see docs), dust-storm frequency (TES
time series not yet processed).

Output (output/mars_global/): features.npz, candidates.csv, map.png

    python mars_screen.py
    python mars_screen.py --max-abs-lat 50 --max-elev 0   # current human-EDL envelope
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

from landing_sites import SITES

HERE = Path(__file__).resolve().parent
RAW = HERE / "output" / "raw" / "mars"
OUT = HERE / "output" / "mars_global"

R_MARS = 3396.19          # km
PPD = 16                  # target grid
NROW, NCOL = 176 * PPD, 360 * PPD   # 88 N .. 88 S
MOLA_PPD, F = 128, 8      # block factor MOLA -> grid


def grid_latlon():
    lat = 88 - (np.arange(NROW) + 0.5) / PPD
    lon = (np.arange(NCOL) + 0.5) / PPD
    return lat, lon


# ----------------------------------------------------------------------------- #
def mola_features():
    """Slope (central differences on the 463 m grid) and relief per 3.7 km cell, tile by tile."""
    out = {k: np.full((NROW, NCOL), np.nan, np.float32)
           for k in ("elev", "slope_p50", "slope_p90", "relief")}
    tiles = {"88n": 88, "44n": 44, "00n": 0, "44s": -44}
    dy = np.pi * R_MARS * 1000 / 180 / MOLA_PPD          # m per MOLA pixel in latitude
    for tname, top in tiles.items():
        for lon0 in (0, 90, 180, 270):
            path = RAW / f"megt{tname}{lon0:03d}hb.img"
            z = np.fromfile(path, dtype=">i2").reshape(5632, 11520).astype(np.float32)
            lat_px = top - (np.arange(5632) + 0.5) / MOLA_PPD
            dx = dy * np.cos(np.radians(lat_px))[:, None]
            gy, gx = np.gradient(z)
            slope = np.degrees(np.arctan(np.hypot(gx / dx, gy / dy)))
            del gx, gy
            r0 = int(round((88 - top) * PPD)); c0 = lon0 * PPD
            nr, nc = 5632 // F, 11520 // F
            sb = slope.reshape(nr, F, nc, F).transpose(0, 2, 1, 3).reshape(nr, nc, -1)
            zb = z.reshape(nr, F, nc, F).transpose(0, 2, 1, 3).reshape(nr, nc, -1)
            out["slope_p50"][r0:r0 + nr, c0:c0 + nc] = np.median(sb, axis=2)
            out["slope_p90"][r0:r0 + nr, c0:c0 + nc] = np.percentile(sb, 90, axis=2)
            out["elev"][r0:r0 + nr, c0:c0 + nc] = zb.mean(axis=2)
            q = np.percentile(zb, [5, 95], axis=2)
            out["relief"][r0:r0 + nr, c0:c0 + nc] = q[1] - q[0]
            print(f"  MOLA tile {path.name} done")
            del z, slope, sb, zb
    return out


def sample_cyl(path, ppd, dtype, scale=1.0, offset=0.0, missing=None, west=-180.0):
    """Global simple-cylindrical raster (lat +90 at top) -> value at each grid-cell centre."""
    nrow, ncol = 180 * ppd, 360 * ppd
    a = np.fromfile(path, dtype=dtype).reshape(nrow, ncol)
    lat, lon = grid_latlon()
    rows = np.clip(((90 - lat) * ppd).astype(int), 0, nrow - 1)
    lon_w = np.where(lon - west >= 360, lon - 360, lon)
    cols = np.clip(((lon_w - west) % 360 * ppd).astype(int), 0, ncol - 1)
    v = a[rows[:, None], cols[None, :]].astype(np.float32)
    if missing is not None:
        v[v == missing] = np.nan
    return v * scale + offset


def grs_h2o():
    """GRS water-equivalent hydrogen (wt%), 5x5 deg smoothed map, bilinearly interpolated.

    Only defined within +-57.5 deg (gamma-ray method); poleward stays NaN. At low latitudes
    the hydrogen sits mostly in hydrated minerals / adsorbed water, not in ice.
    """
    df = pd.read_csv(RAW / "h2o_sr_5x5.tab", sep=r"\s+", header=None, names=["lat", "lon", "h2o", "s", "s2"])
    df.loc[df.h2o > 9000, "h2o"] = np.nan
    g = np.full((36, 72), np.nan, np.float32)
    r = ((90 - df.lat) // 5).astype(int); c = ((df.lon % 360) // 5).astype(int)
    g[r, c] = df.h2o.values
    valid = ~np.isnan(g)
    near = ndimage.distance_transform_edt(~valid, return_distances=False, return_indices=True)
    gf = g[tuple(near)]
    gf = np.concatenate([gf[:, -1:], gf, gf[:, :1]], axis=1)          # wrap longitude
    lat, lon = grid_latlon()
    rr = (90 - lat) / 5 - 0.5
    cc = (lon % 360) / 5 - 0.5 + 1
    R, C = np.meshgrid(rr, cc, indexing="ij")
    out = ndimage.map_coordinates(gf, [R, C], order=1, mode="nearest").astype(np.float32)
    out[np.abs(lat) > 57.5, :] = np.nan
    return out


def insolation_rel(lat_deg, obliquity=25.19):
    """Annual-mean daily top-of-atmosphere insolation, relative to the equator (circular orbit)."""
    ls = np.radians(np.arange(0, 360, 1.0))
    dec = np.arcsin(np.sin(np.radians(obliquity)) * np.sin(ls))
    phi = np.radians(lat_deg)[:, None]
    cosh0 = np.clip(-np.tan(phi) * np.tan(dec[None, :]), -1, 1)
    h0 = np.arccos(cosh0)
    q = h0 * np.sin(phi) * np.sin(dec) + np.cos(phi) * np.cos(dec) * np.sin(h0)
    qm = q.mean(axis=1)
    return (qm / qm[np.argmin(np.abs(lat_deg))]).astype(np.float32)


def hydrous_distance_km():
    df = pd.read_csv(RAW / "hydrous_sites_geo_map.csv", header=None, names=["lon", "lat", "x", "id"])
    lat, lon = grid_latlon()
    mask = np.zeros((NROW, NCOL), bool)
    r = ((88 - df.lat) * PPD).astype(int); c = ((df.lon % 360) * PPD).astype(int)
    ok = (r >= 0) & (r < NROW)
    mask[r[ok], c[ok]] = True
    d_px = ndimage.distance_transform_edt(~mask).astype(np.float32)   # in cells (lat-scale)
    return d_px * (np.pi * R_MARS / 180 / PPD)                          # km (approx, ignores cos(lat) in lon)


def build_features():
    f = {}
    print("MOLA slope / relief (16 tiles, 128 px/deg) ...")
    f.update(mola_features())
    print("TES thermal inertia, OMEGA, GRS ...")
    f["ti_night"] = sample_cyl(RAW / "global_ti_night_2007.img", 20, ">i2", missing=0)
    f["ti_day"] = sample_cyl(RAW / "global_ti_day_2007.img", 20, ">i2", missing=0)
    f["albedo_1um"] = sample_cyl(RAW / "albedo_r1080_equ_map.img", 40, "<i2", 1.4522365285e-05, 5.2414565669e-01, -32768)
    f["nanophase_ferric"] = sample_cyl(RAW / "ferric_nnphs_equ_map.img", 40, "<i2", 1.0866524335e-05, 6.8393632054e-01, -32768)
    f["olivine"] = sample_cyl(RAW / "olivine_osp1_equ_map.img", 40, "<i2", 4.4635829172e-06, 1.1862403290e+00, -32768)
    f["h2o_wt"] = grs_h2o()
    f["dist_hydrous_km"] = hydrous_distance_km()
    lat, lon = grid_latlon()
    f["insolation_rel"] = np.repeat(insolation_rel(lat)[:, None], NCOL, axis=1)
    f["lat"], f["lon"] = np.meshgrid(lat, lon, indexing="ij")
    f["lat"] = f["lat"].astype(np.float32); f["lon"] = f["lon"].astype(np.float32)
    return f


def rank01(a):
    """Area-weighted-free percentile rank in 0..1, NaN stays NaN."""
    v = a[~np.isnan(a)]
    r = np.full(a.shape, np.nan, np.float32)
    r[~np.isnan(a)] = np.searchsorted(np.sort(v), v) / max(len(v) - 1, 1)
    return r


def score(f, args):
    ok = (
        (f["slope_p90"] <= args.max_slope)
        & (f["elev"] <= args.max_elev)
        & (np.abs(f["lat"]) <= args.max_abs_lat)
        & (f["ti_night"] >= args.min_ti)          # InSight: TI > 100-140 SI (no deep dust)
        & (f["ti_night"] <= 1500)                   # exclude polar ice / bedrock-saturated artefacts
    )
    s_ice = rank01(f["h2o_wt"])
    s_ti = np.clip((f["ti_night"] - args.min_ti) / (400 - args.min_ti), 0, 1)
    s_slope = np.clip(1 - f["slope_p90"] / args.max_slope, 0, 1)
    s_rough = 1 - np.clip(f["relief"] / np.nanpercentile(f["relief"], 95), 0, 1)
    s_sun = np.clip(f["insolation_rel"], 0, 1)
    s_dust = 1 - rank01(f["nanophase_ferric"])
    W = dict(ice=0.35, bearing=0.15, slope=0.15, rough=0.10, sun=0.15, dust=0.10)
    parts = dict(ice=s_ice, bearing=s_ti, slope=s_slope, rough=s_rough, sun=s_sun, dust=s_dust)
    # weighted mean over the parameters that have data in a cell (e.g. no GRS poleward of 57.5 deg)
    num = sum(W[k] * np.nan_to_num(parts[k], nan=0.0) for k in W)
    den = sum(W[k] * (~np.isnan(parts[k])) for k in W)
    total = num / np.where(den > 0, den, np.nan)
    total = np.where(ok & (den >= 0.6), total, np.nan).astype(np.float32)   # need >= 60 % of the weight
    f["_missing"] = np.stack([np.isnan(parts[k]) for k in W])
    return total, ok, W


def gc_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(np.radians(lon1 - lon2))
    return np.arccos(np.clip(a, -1, 1)) * R_MARS


def find_sites(f, total, args, W):
    thr = np.nanpercentile(total, 100 - args.top_percent)
    good = total >= thr
    lab, n = ndimage.label(good, structure=np.ones((3, 3)))
    idx = np.arange(1, n + 1)
    size = ndimage.sum(good, lab, idx)
    best = ndimage.maximum_position(np.nan_to_num(total, nan=-1), lab, idx)
    known = [(name, lat, lon) for name, body, lat, lon, cat, src in SITES if body == "mars"]
    rows = []
    for k, sz, (r, c) in zip(idx, size, best):
        if sz < args.min_cells:
            continue
        lat, lon = float(f["lat"][r, c]), float(f["lon"][r, c])
        d, near = min((gc_km(lat, lon, la, lo), nm) for nm, la, lo in known)
        rows.append({
            "lat": round(lat, 2), "lon_E": round(lon, 2), "score": round(float(total[r, c]), 3),
            "area_km2": round(float(sz * (np.pi * R_MARS / 180 / PPD) ** 2 * np.cos(np.radians(lat))), 0),
            "weh_wt_pct": round(float(f["h2o_wt"][r, c]), 1),
            "thermal_inertia": round(float(f["ti_night"][r, c]), 0),
            "slope_p50_deg": round(float(f["slope_p50"][r, c]), 2),
            "slope_p90_deg": round(float(f["slope_p90"][r, c]), 2),
            "relief_m": round(float(f["relief"][r, c]), 0),
            "elev_m": round(float(f["elev"][r, c]), 0),
            "insolation_rel": round(float(f["insolation_rel"][r, c]), 2),
            "nanophase_ferric": round(float(f["nanophase_ferric"][r, c]), 3),
            "albedo_1um": round(float(f["albedo_1um"][r, c]), 3),
            "dist_hydrous_site_km": round(float(f["dist_hydrous_km"][r, c]), 0),
            "beyond_50deg": bool(abs(lat) > 50),
            "params_missing": ",".join(k for k, m in zip(W, f["_missing"][:, r, c]) if m),
            "nearest_known_site": near, "dist_known_km": round(float(d), 0),
            "novel": bool(d > args.novel_km), "_rc": (r, c),
        })
    if not rows:
        return pd.DataFrame(columns=["score", "_rc", "novel"]), thr
    df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    keep = []
    for i, s in df.iterrows():
        if all(gc_km(s.lat, s.lon_E, df.lat[j], df.lon_E[j]) >= args.min_sep_km for j in keep):
            keep.append(i)
    df = df.loc[keep].head(args.top).reset_index(drop=True)
    df.index += 1
    return df, thr


def plot(f, total, sites, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ext = [0, 360, -88, 88]
    fig, ax = plt.subplots(2, 1, figsize=(16, 14))
    ax[0].imshow(f["elev"], extent=ext, cmap="terrain", aspect="auto")
    ax[0].set_title("MOLA elevation (m) - context")
    ax[1].imshow(f["elev"], extent=ext, cmap="gray", aspect="auto", alpha=0.6)
    im = ax[1].imshow(total, extent=ext, cmap="viridis", aspect="auto")
    fig.colorbar(im, ax=ax[1], fraction=0.02, label="site score (0..1)")
    ax[1].set_title("Base-site score where constraints are met")
    for a in ax:
        for name, body, lat, lon, cat, src in SITES:
            if body == "mars":
                a.plot(lon, lat, "r^", ms=6)
                a.annotate(name.split(" (")[0], (lon, lat), color="red", fontsize=6, xytext=(3, 3), textcoords="offset points")
        a.set_xlabel("longitude E"); a.set_ylabel("latitude")
    for i, s in sites.iterrows():
        col = "orange" if s["novel"] else "white"
        ax[1].plot(s.lon_E, s.lat, "o", mfc="none", mec=col, ms=9, mew=1.5)
        ax[1].annotate(str(i), (s.lon_E, s.lat), color=col, fontsize=8, xytext=(4, -9), textcoords="offset points")
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-slope", type=float, default=15.0, help="max P90 slope at 463 m baseline [deg] (InSight < 15)")
    ap.add_argument("--max-elev", type=float, default=2000.0, help="max MOLA elevation [m] (EDL)")
    ap.add_argument("--max-abs-lat", type=float, default=88.0, help="latitude filter (88 = whole data coverage)")
    ap.add_argument("--min-ti", type=float, default=140.0, help="min night thermal inertia [SI] (InSight 100-140)")
    ap.add_argument("--top-percent", type=float, default=1.0)
    ap.add_argument("--min-cells", type=int, default=4)
    ap.add_argument("--min-sep-km", type=float, default=150.0, help="merge candidates closer than this")
    ap.add_argument("--novel-km", type=float, default=200.0, help="distance from known sites to count as new")
    ap.add_argument("--top", type=int, default=30)
    ap.add_argument("--rebuild", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "features.npz"
    if cache.exists() and not args.rebuild:
        f = dict(np.load(cache))
    else:
        f = build_features()
        np.savez_compressed(cache, **f)

    total, ok, W = score(f, args)
    print(f"\nweights: {W}")
    print(f"constraints: slope_p90 <= {args.max_slope} deg, elevation <= {args.max_elev} m, "
          f"|lat| <= {args.max_abs_lat}, {args.min_ti} <= TI <= 1500")
    print(f"valid cells: {int(np.nansum(~np.isnan(total))):,} of {total.size:,} "
          f"({100 * np.mean(~np.isnan(total)):.1f} %)")
    sites, thr = find_sites(f, total, args, W)
    cols = [c for c in sites.columns if not c.startswith("_")]
    sites[cols].to_csv(OUT / "candidates.csv", index_label="rank")
    with pd.option_context("display.width", 260, "display.max_columns", 30):
        print(f"\nTop {len(sites)} candidate sites (score >= {thr:.3f}):")
        print(sites[["lat", "lon_E", "score", "area_km2", "weh_wt_pct", "params_missing", "thermal_inertia", "slope_p90_deg",
                     "relief_m", "elev_m", "insolation_rel", "dist_hydrous_site_km", "nearest_known_site",
                     "dist_known_km", "novel"]].to_string())
    plot(f, total, sites, OUT / "map.png")
    print(f"\nSaved {OUT / 'candidates.csv'}, {OUT / 'map.png'}, {cache}")


if __name__ == "__main__":
    main()
