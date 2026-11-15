"""RETIRED (2026-11-15) - not part of the current scoring system; kept for reference only.

The Moon screening is now restricted to the south pole (moon_screen.py). The result of this
script (best sites on the north polar near side, 67-86 N) is not supported:
  * "ice access" uses the distance to any permanently shadowed LOLA pixel. Near the 10 northern
    candidates covered by the Diviner polar resource product there is no cold trap within 2 km
    (lowest Tmax 172-245 K; nearest cold trap 2.6-20 km away). Shadow is not ice.
  * slope is computed on the cylindrical grid, whose east-west pixel shrinks with cos(lat):
    the east-west P90 slope rises from 11 deg at 60 deg latitude to 29 deg at 88.5 deg while the
    north-south P90 stays at 12-14 deg, so polar cells wrongly fail the 8 deg limit.
  * sun visibility of the candidates (0.46-0.50) is the same as at the equator, and the rock
    abundance layer is missing for every top candidate.

Global screening of the whole Moon for landing / base sites with A/B-rated PDS data.

Grid: simple cylindrical, 16 px/deg (~1.9 km at the equator), 90 S..90 N, 0..360 E.
For the polar caps (|lat| >= 55.2) the LOLA 240 m polar-stereographic products are
sampled onto the same grid. The high-resolution south-pole study is moon_screen.py.

Inputs (output/raw/moon_global, ~5 GB):
  LOLA LDEM_128 (237 m)                    -> slope p50/p90 (237 m baseline), relief       (A)
  LOLA LDRM_32_50                          -> median roughness at 25 m baseline [m]         (A)
  Diviner GDR L3 rock abundance 32 ppd     -> rock fraction, only |lat| <= 60               (A)
  Diviner GDR L3 regolith temp. anomaly    -> fines / regolith proxy (reported only)        (C)
  LOLA AVGVISIB_65N/65S_240M (+ _EARTH)    -> sun / Earth visibility poleward of 55.2       (A)
  LOLA LPSR_65N/65S_240M                   -> permanently shadowed regions, distance to PSR (A)
  LOLA LDAM_10                             -> 1064 nm albedo (reported)                     (A)
Equatorward of 55.2 deg: sun visibility = 0.5 (14-day night everywhere, terrain shadows
ignored) and Earth visibility from the angular distance to the sub-Earth point
(near side 1, far side 0, +-8 deg libration band linear). No cold traps exist there,
so the ice score is 0 (not unknown).

    python moon_global_screen.py
    python moon_global_screen.py --max-slope 10 --top 40
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

from landing_sites import SITES

HERE = Path(__file__).resolve().parent
RAW = HERE / "output" / "raw" / "moon_global"
OUT = HERE / "output" / "moon_global"

R_MOON = 1737.4
PPD = 16
NROW, NCOL = 180 * PPD, 360 * PPD
CELL_KM = np.pi * R_MOON / 180 / PPD


def grid_latlon():
    lat = 90 - (np.arange(NROW) + 0.5) / PPD
    lon = (np.arange(NCOL) + 0.5) / PPD
    return lat, lon


def lola_cyl(name, ppd, nrow, dtype, scale, offset, missing=None, lat_top=90):
    """LOLA/Diviner cylindrical raster (west edge 0 E, top = lat_top) -> grid cell centres."""
    a = np.memmap(RAW / name, dtype=dtype, mode="r")
    ncol = 360 * ppd
    a = a.reshape(nrow, ncol)
    lat, lon = grid_latlon()
    rows = ((lat_top - lat) * ppd).astype(int)
    inside = (rows >= 0) & (rows < nrow)
    cols = (lon * ppd).astype(int)
    out = np.full((NROW, NCOL), np.nan, np.float32)
    v = np.asarray(a[rows[inside][:, None], cols[None, :]]).astype(np.float32)
    if missing is not None:
        v[v == missing] = np.nan
    out[inside] = v * scale + offset
    return out


def ldem_slope():
    """Slope / relief from LDEM_128 (int16 radius), processed in row chunks."""
    n_r, n_c, f = 23040, 46080, 8
    z = np.memmap(RAW / "ldem_128.img", dtype="<i2", mode="r").reshape(n_r, n_c)
    dy = np.pi * R_MOON * 1000 / 180 / 128
    out = {k: np.full((NROW, NCOL), np.nan, np.float32) for k in ("slope_p50", "slope_p90", "relief")}
    step = 64 * f
    for r0 in range(0, n_r, step):
        r1 = min(r0 + step, n_r)
        a0, a1 = max(r0 - 1, 0), min(r1 + 1, n_r)
        blk = np.asarray(z[a0:a1]).astype(np.float32) * 0.5
        lat_px = 90 - (np.arange(a0, a1) + 0.5) / 128
        dx = np.maximum(dy * np.cos(np.radians(lat_px)), 1.0)[:, None]
        gy, gx = np.gradient(blk)
        sl = np.degrees(np.arctan(np.hypot(gx / dx, gy / dy)))[r0 - a0: r0 - a0 + (r1 - r0)]
        zz = blk[r0 - a0: r0 - a0 + (r1 - r0)]
        nr = (r1 - r0) // f
        sb = sl.reshape(nr, f, NCOL, f).transpose(0, 2, 1, 3).reshape(nr, NCOL, -1)
        zb = zz.reshape(nr, f, NCOL, f).transpose(0, 2, 1, 3).reshape(nr, NCOL, -1)
        g0 = r0 // f
        out["slope_p50"][g0:g0 + nr] = np.median(sb, axis=2)
        out["slope_p90"][g0:g0 + nr] = np.percentile(sb, 90, axis=2)
        q = np.percentile(zb, [5, 95], axis=2)
        out["relief"][g0:g0 + nr] = q[1] - q[0]
    # cylindrical slope is unreliable right at the poles (dx -> 0)
    lat, _ = grid_latlon()
    for k in out:
        out[k][np.abs(lat) > 89.5] = np.nan
    return out


def polar_sample(name, scale, offset, south, reducer=None):
    """LOLA 65N/65S 240 m polar-stereographic product -> grid cells with |lat| >= 55.2."""
    n, s = 6420, 0.240
    a = np.memmap(RAW / name, dtype="<i2", mode="r").reshape(n, n)
    v = np.asarray(a).astype(np.float32) * scale + offset
    if reducer is not None:
        v = reducer(v)
    lat, lon = grid_latlon()
    sel = (lat <= -55.2) if south else (lat >= 55.2)
    LA, LO = np.meshgrid(lat[sel], lon, indexing="ij")
    d = 2 * R_MOON * np.tan(np.radians(90 - np.abs(LA)) / 2)
    x = d * np.sin(np.radians(LO))
    y = d * np.cos(np.radians(LO)) * (1 if south else -1)   # south: lon 0 up; north: lon 0 down
    col = np.floor(x / s + n / 2).astype(int)
    row = np.floor(n / 2 - y / s).astype(int)
    # the square map is complete only poleward of ~65 deg; outside the square -> NaN (no clipping!)
    inside = (col >= 0) & (col < n) & (row >= 0) & (row < n)
    vals = np.full(LA.shape, np.nan, np.float32)
    vals[inside] = v[row[inside], col[inside]]
    out = np.full((NROW, NCOL), np.nan, np.float32)
    out[sel] = vals
    return out


def psr_distance_km(v):
    """PSR mask (value > 0.5) -> distance (km) to nearest PSR pixel."""
    return (ndimage.distance_transform_edt(v <= 0.5) * 0.240).astype(np.float32)


def merge(a, b):
    return np.where(np.isnan(a), b, a)


def build_features():
    f = {}
    print("LDEM_128 slope / relief (2.1 GB, chunked) ...")
    f.update(ldem_slope())
    print("roughness, Diviner, albedo ...")
    f["rough_med"] = lola_cyl("ldrm_32_50.img", 32, 5760, "<i2", 0.001, 0.0, -32768)
    f["rock_abund"] = lola_cyl("dgdr_ra_avg_cyl_032_img.img", 32, 3840, "<i2", 0.001, 0.0, -32768, lat_top=60)
    f["regolith_t_anom"] = lola_cyl("dgdr_st_avg_cyl_032_img.img", 32, 3840, "<i2", 0.02, 0.0, -32768, lat_top=60)
    f["albedo_1064"] = lola_cyl("ldam_10_float.img", 10, 1800, "<f4", 1.0, 0.0)
    print("polar illumination / Earth visibility / PSR (240 m) ...")
    lat, lon = grid_latlon()
    LA, LO = np.meshgrid(lat, lon, indexing="ij")
    sun = np.full((NROW, NCOL), 0.5, np.float32)
    ang = np.degrees(np.arccos(np.clip(np.cos(np.radians(LA)) * np.cos(np.radians(LO)), -1, 1)))
    earth = np.clip((98 - ang) / 16, 0, 1).astype(np.float32)
    psr = np.zeros((NROW, NCOL), np.float32)
    dpsr = np.full((NROW, NCOL), np.inf, np.float32)
    for hemi, south in (("65s", True), ("65n", False)):
        sun = merge(polar_sample(f"avgvisib_{hemi}_240m_201608.img", 0.00004, 0.0, south), sun)
        earth = merge(polar_sample(f"avgvisib_{hemi}_240m_201608_earth.img", 0.00004, 0.0, south), earth)
        psr = merge(polar_sample(f"lpsr_{hemi}_240m_201608.img", 0.000025, 0.5, south), psr)
        dpsr = merge(polar_sample(f"lpsr_{hemi}_240m_201608.img", 0.000025, 0.5, south, psr_distance_km), dpsr)
    f["sun_vis"], f["earth_vis"], f["psr"], f["dist_psr_km"] = sun, earth, psr, dpsr
    f["lat"], f["lon"] = LA.astype(np.float32), LO.astype(np.float32)
    return f


def rank01(a):
    v = a[~np.isnan(a)]
    r = np.full(a.shape, np.nan, np.float32)
    r[~np.isnan(a)] = np.searchsorted(np.sort(v), v) / max(len(v) - 1, 1)
    return r


def score(f, args):
    ok = (f["slope_p90"] <= args.max_slope) & (f["psr"] < 0.5) & ~np.isnan(f["slope_p90"])
    parts = dict(
        sun=np.clip(f["sun_vis"], 0, 1),
        ice=np.exp(-np.minimum(f["dist_psr_km"], 1e6) / args.eva_km),
        slope=np.clip(1 - f["slope_p90"] / args.max_slope, 0, 1),
        rough=1 - rank01(f["rough_med"]),
        rock=1 - np.clip(f["rock_abund"] / 0.05, 0, 1),        # 5 % rock cover -> 0
        earth=np.clip(f["earth_vis"], 0, 1),
    )
    W = dict(sun=0.25, ice=0.30, slope=0.15, rough=0.10, rock=0.10, earth=0.10)
    num = sum(W[k] * np.nan_to_num(parts[k], nan=0.0) for k in W)
    den = sum(W[k] * (~np.isnan(parts[k])) for k in W)
    total = np.where(ok & (den >= 0.6), num / np.where(den > 0, den, np.nan), np.nan).astype(np.float32)
    f["_missing"] = np.stack([np.isnan(parts[k]) for k in W])
    return total, W


def gc_km(lat1, lon1, lat2, lon2):
    p1, p2 = np.radians(lat1), np.radians(lat2)
    a = np.sin(p1) * np.sin(p2) + np.cos(p1) * np.cos(p2) * np.cos(np.radians(lon1 - lon2))
    return np.arccos(np.clip(a, -1, 1)) * R_MOON


def find_sites(f, total, args, W):
    thr = np.nanpercentile(total, 100 - args.top_percent)
    good = total >= thr
    lab, n = ndimage.label(good, structure=np.ones((3, 3)))
    idx = np.arange(1, n + 1)
    size = ndimage.sum(good, lab, idx)
    best = ndimage.maximum_position(np.nan_to_num(total, nan=-1), lab, idx)
    known = [(nm, la, lo) for nm, body, la, lo, cat, src in SITES if body == "moon"]
    rows = []
    for sz, (r, c) in zip(size, best):
        if sz < args.min_cells:
            continue
        lat, lon = float(f["lat"][r, c]), float(f["lon"][r, c])
        d, near = min((gc_km(lat, lon, la, lo), nm) for nm, la, lo in known)
        rows.append({
            "lat": round(lat, 2), "lon_E": round(lon, 2), "score": round(float(total[r, c]), 3),
            "area_km2": round(float(sz * CELL_KM ** 2 * np.cos(np.radians(lat))), 1),
            "sun_visibility": round(float(f["sun_vis"][r, c]), 2),
            "earth_visibility": round(float(f["earth_vis"][r, c]), 2),
            "dist_psr_km": round(float(min(f["dist_psr_km"][r, c], 9999)), 1),
            "slope_p50_deg": round(float(f["slope_p50"][r, c]), 2),
            "slope_p90_deg": round(float(f["slope_p90"][r, c]), 2),
            "relief_m": round(float(f["relief"][r, c]), 0),
            "roughness_m": round(float(f["rough_med"][r, c]), 2),
            "rock_abundance": round(float(f["rock_abund"][r, c]), 4),
            "regolith_T_anomaly_K": round(float(f["regolith_t_anom"][r, c]), 2),
            "albedo_1064": round(float(f["albedo_1064"][r, c]), 3),
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
    ext = [0, 360, -90, 90]
    fig, ax = plt.subplots(2, 1, figsize=(16, 14))
    ax[0].imshow(f["albedo_1064"], extent=ext, cmap="gray", aspect="auto")
    ax[0].set_title("LOLA 1064 nm albedo - context (near side centred at 0 E)")
    ax[1].imshow(f["albedo_1064"], extent=ext, cmap="gray", aspect="auto", alpha=0.6)
    im = ax[1].imshow(total, extent=ext, cmap="viridis", aspect="auto")
    fig.colorbar(im, ax=ax[1], fraction=0.02, label="site score (0..1)")
    ax[1].set_title("Base-site score where constraints are met")
    for a in ax:
        for nm, body, la, lo, cat, src in SITES:
            if body == "moon":
                a.plot(lo, la, "r^", ms=5)
        a.set_xlabel("longitude E"); a.set_ylabel("latitude")
    for i, s in sites.iterrows():
        col = "orange" if s["novel"] else "white"
        ax[1].plot(s.lon_E, s.lat, "o", mfc="none", mec=col, ms=9, mew=1.5)
        ax[1].annotate(str(i), (s.lon_E, s.lat), color=col, fontsize=8, xytext=(4, -9), textcoords="offset points")
    fig.tight_layout()
    fig.savefig(path, dpi=110)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-slope", type=float, default=8.0, help="max P90 slope at 237 m baseline [deg]")
    ap.add_argument("--eva-km", type=float, default=2.0)
    ap.add_argument("--top-percent", type=float, default=1.0)
    ap.add_argument("--min-cells", type=int, default=3)
    ap.add_argument("--min-sep-km", type=float, default=50.0)
    ap.add_argument("--novel-km", type=float, default=50.0)
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
    total, W = score(f, args)
    print(f"\nweights: {W}\nconstraints: slope_p90 (237 m) <= {args.max_slope} deg, not in PSR")
    print(f"valid cells: {int(np.sum(~np.isnan(total))):,} of {total.size:,} ({100 * np.mean(~np.isnan(total)):.1f} %)")
    sites, thr = find_sites(f, total, args, W)
    cols = [c for c in sites.columns if not c.startswith("_")]
    sites[cols].to_csv(OUT / "candidates.csv", index_label="rank")
    with pd.option_context("display.width", 260, "display.max_columns", 30):
        print(f"\nTop {len(sites)} candidate sites (score >= {thr:.3f}):")
        print(sites[["lat", "lon_E", "score", "area_km2", "sun_visibility", "earth_visibility", "dist_psr_km",
                     "slope_p90_deg", "roughness_m", "rock_abundance", "params_missing",
                     "nearest_known_site", "dist_known_km", "novel"]].to_string())
    plot(f, total, sites, OUT / "map.png")
    print(f"\nSaved {OUT / 'candidates.csv'}, {OUT / 'map.png'}, {cache}")


if __name__ == "__main__":
    main()
