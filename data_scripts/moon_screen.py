"""Screen the lunar south pole (85-90 S) for landing / base sites with A/B-rated PDS data.

Note: in LDSM, DN 0 (= exactly 45 deg) marks gaps between LOLA tracks (69 % of pixels) and is masked.

Inputs (download first, ~1 GB total, see RAW below):
  LOLA  LDSM_85S_40M            slope at 40 m baseline           [deg]       (A)
  LOLA  LDRM_85S_40M            roughness at 40 m baseline       [m]         (A)
  LOLA  AVGVISIB_85S_060M       average sun visibility           [0..1]      (A)
  LOLA  AVGVISIB_85S_060M_EARTH average Earth visibility         [0..1]      (A)
  LOLA  LPSR_85S_060M           permanently shadowed regions     [0/1]       (A)
  Diviner PRP south             Tmax / Tavg / ice-stability depth (triangles) (A for T, B for ice)

Everything is aggregated to a 240 m polar-stereographic grid (6x6 LOLA 40 m pixels,
4x4 60 m pixels). Projection: LOLA polar stereographic, spherical R = 1737.4 km,
"longitude 0 up, 90 E right" (validated: Shackleton, Faustini, Haworth, Shoemaker
fall on PSR pixels).

Rock abundance: NOT available here (Diviner rock abundance only reaches 80 S);
LOLA roughness is used instead.

Sunlight (v2): scored on the best-lit 60 m pixel of each 240 m cell, stretched between the
minimum allowed value (--min-sun) and the best usable cell on the map. The cell average
barely differs between usable cells (0.30-0.62), so with the old raw average sunlight did
not influence the ranking (--sun-measure raw reproduces the old list). Length of the
longest night is NOT scored: no such product exists in the LOLA archive.

Cells outside 85 S (corners of the square map) are excluded: no Diviner data there.

NASA's Artemis regions are compared as rough areas (landing_sites.MOON_SOUTH_AREAS), not as
points: crater centres are permanently shadowed ice targets, the regions lie beside them.

Output (output/moon_south/):
  features.npz            all per-cell layers + lat/lon
  candidates.csv          ranked candidate sites (connected groups of good cells)
  nasa_vs_candidates.csv  best usable cell of every NASA area under the same scoring, next to the candidates
  map.png                 score map with candidates and NASA areas

    python moon_screen.py                     # default weights / thresholds
    python moon_screen.py --max-slope 8 --top 30
    python moon_screen.py --sun-measure raw   # old sunlight term
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from scipy import ndimage

from landing_sites import MOON_SOUTH_AREAS

HERE = Path(__file__).resolve().parent
RAW = HERE / "output" / "raw" / "moon"
OUT = HERE / "output" / "moon_south"

R_MOON = 1737.4  # km
CELL = 0.240     # km
N_CELL = 1264    # 1264 * 0.24 km = 303.36 km = full LOLA 85S map width
HALF = N_CELL * CELL / 2


# ----------------------------------------------------------------------------- #
# I/O helpers
# ----------------------------------------------------------------------------- #
def read_lola(name, n, scale, offset, missing=None):
    """Raw PDS3 int16 polar image -> float32 (memory-mapped, scaled)."""
    a = np.memmap(RAW / name, dtype="<i2", mode="r", shape=(n, n))
    return a, scale, offset, missing


def block_reduce(src, factor, start, funcs):
    """Aggregate a (memmapped) image into N_CELL x N_CELL blocks, chunked over rows."""
    a, scale, offset, missing = src
    out = {k: np.full((N_CELL, N_CELL), np.nan, np.float32) for k in funcs}
    rows_per_chunk = 64
    for r0 in range(0, N_CELL, rows_per_chunk):
        r1 = min(r0 + rows_per_chunk, N_CELL)
        blk = a[start + r0 * factor: start + r1 * factor, start: start + N_CELL * factor]
        blk = blk.astype(np.float32)
        if missing is not None:
            blk[blk == missing] = np.nan
        blk = blk * scale + offset
        blk = blk.reshape(r1 - r0, factor, N_CELL, factor).transpose(0, 2, 1, 3).reshape(r1 - r0, N_CELL, -1)
        for k, f in funcs.items():
            out[k][r0:r1] = f(blk)
    return out


def grid_latlon():
    c = (np.arange(N_CELL) + 0.5) * CELL - HALF
    x = c[None, :].repeat(N_CELL, 0)          # km, positive right (90 E)
    y = -c[:, None].repeat(N_CELL, 1)         # km, positive up (lon 0)
    r = np.hypot(x, y)
    lat = -90 + np.degrees(2 * np.arctan(0.5 * r / R_MOON))
    lon = np.degrees(np.arctan2(x, y)) % 360
    return lat, lon


def latlon_to_cell(lat, lon):
    d = 2 * R_MOON * np.tan(np.radians(90 - np.abs(lat)) / 2)
    x = d * np.sin(np.radians(lon))
    y = d * np.cos(np.radians(lon))
    col = np.floor((x + HALF) / CELL).astype(int)
    row = np.floor((HALF - y) / CELL).astype(int)
    return row, col


def read_prp():
    """Diviner South Polar Resource Product: fixed-width table of triangles."""
    # comma-separated despite the fixed-width label; header line holds the column names
    df = pd.read_csv(RAW / "dlre_prp_south.tab", skipinitialspace=True,
                     usecols=["tri_clon", "tri_clat", "temp_avg", "temp_max", "ice_depth"])
    df.columns = ["clon", "clat", "temp_avg", "temp_max", "ice_depth"]
    # ice_depth semantics (label + check against temp_max):
    #   0      ice stable at the surface (Tmax ~107 K)
    #   -1     undocumented, occurs only in the coldest triangles (Tmax 51-97 K) -> also surface-stable
    #   -999   ice only stable deeper than 2.87 m -> encode as 3.0 (not "missing")
    df.loc[df.ice_depth == -999, "ice_depth"] = 3.0
    df.loc[df.ice_depth < 0, "ice_depth"] = 0.0
    df = df.mask(df <= -998)
    df = df[df.clat < -84.9]
    return df


def grid_points(df, cols):
    row, col = latlon_to_cell(df.clat.values, df.clon.values)
    ok = (row >= 0) & (row < N_CELL) & (col >= 0) & (col < N_CELL)
    idx = row[ok] * N_CELL + col[ok]
    out = {}
    for c in cols:
        v = df[c].values[ok]
        good = ~np.isnan(v)
        s = np.bincount(idx[good], v[good], N_CELL * N_CELL)
        n = np.bincount(idx[good], minlength=N_CELL * N_CELL)
        with np.errstate(invalid="ignore"):
            out[c] = (s / n).reshape(N_CELL, N_CELL).astype(np.float32)
    # fill small gaps (cells without a triangle centre) from neighbours
    for c in cols:
        a = out[c]
        miss = np.isnan(a)
        if miss.any():
            near = ndimage.distance_transform_edt(miss, return_distances=False, return_indices=True)
            filled = a[tuple(near)]
            dist = ndimage.distance_transform_edt(miss)
            a[miss & (dist <= 3)] = filled[miss & (dist <= 3)]
    return out


# ----------------------------------------------------------------------------- #
def build_features():
    print("reading LOLA slope / roughness (40 m) ...")
    p90 = lambda b: np.nanpercentile(b, 90, axis=2)
    mean = lambda b: np.nanmean(b, axis=2)
    f = {}
    s = block_reduce(read_lola("ldsm_85s_40m.img", 7584, 0.0015, 45.0, missing=0), 6, 0, {"slope_mean": mean, "slope_p90": p90,
                      "slope_cov": lambda b: np.mean(~np.isnan(b), axis=2)})
    f.update(s)
    r = block_reduce(read_lola("ldrm_85s_40m.img", 7584, 0.001, 0.0, missing=-32768), 6, 0,
                     {"rough_med": lambda b: np.nanmedian(b, axis=2)})
    f.update(r)

    print("reading LOLA illumination / Earth visibility / PSR (60 m) ...")
    # 60 m grid edge is 60 m outside the 40 m grid edge -> skip 1 pixel, then 4x4 blocks
    f.update(block_reduce(read_lola("avgvisib_85s_060m_201608.img", 5058, 0.00004, 0.0), 4, 1,
                          {"sun_mean": mean, "sun_max": lambda b: np.nanmax(b, axis=2)}))
    f.update(block_reduce(read_lola("avgvisib_85s_060m_201608_earth.img", 5058, 0.00004, 0.0), 4, 1,
                          {"earth_mean": mean}))
    psr_src = read_lola("lpsr_85s_060m_201608.img", 5058, 0.000025, 0.5)
    f.update(block_reduce(psr_src, 4, 1, {"psr_frac": lambda b: np.nanmean(b > 0.5, axis=2)}))

    print("distance to nearest PSR (60 m resolution) ...")
    a = np.asarray(psr_src[0][1:1 + N_CELL * 4, 1:1 + N_CELL * 4])
    not_psr = (a.astype(np.float32) * 0.000025 + 0.5) <= 0.5
    d = ndimage.distance_transform_edt(not_psr).astype(np.float32) * 0.060   # km
    f["dist_psr_km"] = d.reshape(N_CELL, 4, N_CELL, 4).min(axis=(1, 3))
    del a, not_psr, d

    print("reading Diviner Polar Resource Product (2.9 M triangles) ...")
    prp = read_prp()
    f.update(grid_points(prp, ["temp_avg", "temp_max", "ice_depth"]))

    # nearest surface cold trap (ice stable at the surface, PRP). "Stable within 1 m" covers
    # 57 % of the area incl. sunlit terrain and is therefore not selective.
    # NOTE: shallow subsurface ice (a few cm) is also stable under sunlit ground with a low
    # annual mean temperature, so the two classes are kept apart.
    f.update(grid_points(prp.assign(surface_ice=(prp.ice_depth <= 0).astype(float)), ["surface_ice"]))
    cold = f["surface_ice"] >= 0.5
    f["dist_coldtrap_km"] = (ndimage.distance_transform_edt(~cold) * CELL).astype(np.float32)
    shallow = f["ice_depth"] <= 0.10
    f["dist_shallow_ice_km"] = (ndimage.distance_transform_edt(~shallow) * CELL).astype(np.float32)

    f["lat"], f["lon"] = grid_latlon()
    return f


def score(f, args):
    """Constraints -> mask; preferences -> 0..1 score. All choices printed for the write-up."""
    ok = (
        (f["slope_mean"] <= args.max_slope)
        & (f["slope_p90"] <= args.max_slope * 2)
        & (f["psr_frac"] < 0.05)                 # base must be in sunlight
        & (f["sun_mean"] >= args.min_sun)
        & ~np.isnan(f["rough_med"])
        & (f["slope_cov"] >= args.min_coverage)   # avoid cells with only a few LOLA track pixels
        & (f["lat"] <= -85.0)                     # corners of the square map: no Diviner data beyond 85 S
    )
    # Sunlight. "best" (default): best-lit 60 m pixel of the cell (where a solar array would stand),
    # stretched so that the minimum allowed value scores 0 and the best usable cell on the map 1.
    # "mean": same stretch on the 240 m cell average. "raw": cell average used directly (old behaviour).
    if args.sun_measure == "raw":
        s_sun = np.clip(f["sun_mean"], 0, 1)
    else:
        sun = f["sun_max"] if args.sun_measure == "best" else f["sun_mean"]
        hi = float(np.nanmax(np.where(ok, sun, np.nan)))
        s_sun = np.clip((sun - args.min_sun) / (hi - args.min_sun), 0, 1)
    # 1 at a surface cold trap (Diviner PRP: ice stable at surface), 0.37 at the EVA radius
    s_ice = np.exp(-f["dist_coldtrap_km"] / args.eva_km)
    s_slope = np.clip(1 - f["slope_mean"] / args.max_slope, 0, 1)
    rough = f["rough_med"]
    s_rough = 1 - np.clip(rough / np.nanpercentile(rough, 95), 0, 1)
    s_earth = np.clip(f["earth_mean"], 0, 1)
    W = dict(sun=0.35, ice=0.30, slope=0.15, rough=0.10, earth=0.10)
    total = (W["sun"] * s_sun + W["ice"] * s_ice + W["slope"] * s_slope
             + W["rough"] * s_rough + W["earth"] * s_earth)
    total = np.where(ok, total, np.nan).astype(np.float32)
    return total, ok, W, dict(sun=s_sun, ice=s_ice, slope=s_slope, rough=s_rough, earth=s_earth)


def area_xy(lat, lon):
    """Polar-stereographic x/y (km) of a lat/lon point, same frame as the grid."""
    d = 2 * R_MOON * np.tan(np.radians(90 - abs(lat)) / 2)
    return d * np.sin(np.radians(lon)), d * np.cos(np.radians(lon))


def nearest_area(x, y):
    """(distance to the edge of the nearest NASA rough area in km, 0 = inside; its name)."""
    return min((max(float(np.hypot(x - area_xy(la, lo)[0], y - area_xy(la, lo)[1])) - R, 0.0), name)
               for name, lst, la, lo, R, note in MOON_SOUTH_AREAS)


def find_sites(f, total, args):
    thr = np.nanpercentile(total, 100 - args.top_percent)
    good = total >= thr
    lab, n = ndimage.label(good, structure=np.ones((3, 3)))
    idx = np.arange(1, n + 1)
    size = ndimage.sum(good, lab, idx)
    keep = idx[size >= args.min_cells]
    rows = []
    for k in keep:
        m = lab == k
        best = np.nanargmax(np.where(m, total, np.nan))
        r, c = divmod(best, N_CELL)
        lat, lon = float(f["lat"][r, c]), float(f["lon"][r, c])
        # distance to the edge of the nearest NASA rough area (0 = inside it)
        dmin, near = nearest_area((c + 0.5) * CELL - HALF, HALF - (r + 0.5) * CELL)
        rows.append({
            "lat": round(lat, 3), "lon_E": round(lon, 2),
            "score": round(float(total[r, c]), 3),
            "area_km2": round(float(m.sum() * CELL ** 2), 2),
            "sun_visibility": round(float(f["sun_mean"][r, c]), 3),
            "sun_best_60m": round(float(f["sun_max"][r, c]), 3),
            "earth_visibility": round(float(f["earth_mean"][r, c]), 3),
            "slope_mean_deg": round(float(f["slope_mean"][r, c]), 2),
            "slope_p90_deg": round(float(f["slope_p90"][r, c]), 2),
            "roughness_m": round(float(f["rough_med"][r, c]), 3),
            "slope_data_coverage": round(float(f["slope_cov"][r, c]), 2),
            "dist_psr_km": round(float(f["dist_psr_km"][r, c]), 2),
            "dist_surface_coldtrap_km": round(float(f["dist_coldtrap_km"][r, c]), 2),
            "dist_ice_within_10cm_km": round(float(f["dist_shallow_ice_km"][r, c]), 2),
            "ice_stability_depth_m": round(float(f["ice_depth"][r, c]), 2),
            "temp_max_K": round(float(f["temp_max"][r, c]), 1),
            "temp_avg_K": round(float(f["temp_avg"][r, c]), 1),
            "nearest_nasa_area": near,
            "dist_to_nasa_area_km": round(float(dmin), 1),
            "inside_nasa_area": bool(dmin <= 0),
            "novel": bool(dmin > args.novel_km),
            "_rc": (r, c),
        })
    if not rows:
        return pd.DataFrame(columns=["score", "novel", "_rc"]), thr
    df = pd.DataFrame(rows).sort_values("score", ascending=False).reset_index(drop=True)
    # merge clusters: keep the best site, drop others closer than --min-sep-km (polar-stereo distance)
    xy = [((c + 0.5) * CELL - HALF, HALF - (r + 0.5) * CELL) for r, c in df["_rc"]]
    keep_idx = []
    for i, (x, y) in enumerate(xy):
        if all(np.hypot(x - xy[j][0], y - xy[j][1]) >= args.min_sep_km for j in keep_idx):
            keep_idx.append(i)
    df = df.loc[keep_idx].head(args.top).reset_index(drop=True)
    df.index += 1
    return df, thr


def nasa_comparison(f, total, ok, sites):
    """NASA rough areas next to the own candidates, all under the same scoring.

    For every NASA area: share of usable ground, its best usable cell (score, percentile among
    all usable cells, the rank it would take in the candidate list, parameters) and its best-lit
    usable cell. Areas whose anchor lies outside 85 S are listed but not scored.
    """
    x = ((np.arange(N_CELL) + 0.5) * CELL - HALF)[None, :]
    y = (HALF - (np.arange(N_CELL) + 0.5) * CELL)[:, None]
    tv = np.sort(total[ok])

    def cell(r, c, prefix=""):
        s = float(total[r, c])
        d = {"lat": round(float(f["lat"][r, c]), 2), "lon_E": round(float(f["lon"][r, c]), 1), "score": round(s, 3),
             "pct_of_usable": round(100 * np.searchsorted(tv, s) / len(tv), 1),
             "would_rank": int((sites["score"] > s).sum()) + 1 if s >= sites["score"].min() else f">{len(sites)}",
             "sun_avg": round(float(f["sun_mean"][r, c]), 2), "sun_best_60m": round(float(f["sun_max"][r, c]), 2),
             "earth": round(float(f["earth_mean"][r, c]), 2), "slope_mean_deg": round(float(f["slope_mean"][r, c]), 1),
             "dist_coldtrap_km": round(float(f["dist_coldtrap_km"][r, c]), 1)}
        return {prefix + k: v for k, v in d.items()}

    rows = []
    for name, lst, la, lo, R, note in MOON_SOUTH_AREAS:
        row = {"group": f"NASA {lst}", "name": name, "radius_km": R, "anchor": note}
        x0, y0 = area_xy(la, lo)
        m = (np.hypot(x - x0, y - y0) <= R) & (f["lat"] <= -85.0)
        if la > -85.0:
            row["status"] = "outside the 85 S grid - not scored"
        elif not ok[m].any():
            row["status"] = "no usable cell"
        else:
            row["status"] = "scored"
            row["usable_pct"] = round(100 * float(ok[m].mean()), 1)
            row["usable_km2"] = round(float(ok[m].sum()) * CELL ** 2, 1)
            r, c = divmod(int(np.nanargmax(np.where(m, total, np.nan))), N_CELL)
            row.update(cell(r, c))
            r, c = divmod(int(np.argmax(np.where(m & ok, f["sun_max"], -1))), N_CELL)
            row.update(cell(r, c, "bestlit_"))
            row["candidates_inside"] = " ".join(
                f"#{i}" for i, s in sites.iterrows()
                if np.hypot((s["_rc"][1] + 0.5) * CELL - HALF - x0, HALF - (s["_rc"][0] + 0.5) * CELL - y0) <= R)
        rows.append(row)
    for i, s in sites.iterrows():
        row = {"group": "candidate", "name": f"#{i}", "status": "scored"}
        row.update(cell(*s["_rc"]))
        row["would_rank"] = i
        row["inside_nasa_area"] = s["nearest_nasa_area"] if s["inside_nasa_area"] else ""
        rows.append(row)
    return pd.DataFrame(rows)


def plot(f, total, sites, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    ext = [-HALF, HALF, -HALF, HALF]
    fig, ax = plt.subplots(1, 2, figsize=(16, 8))
    ax[0].imshow(f["sun_mean"], extent=ext, cmap="gray", vmin=0, vmax=0.8)
    ax[0].imshow(np.ma.masked_less(f["psr_frac"], 0.5), extent=ext, cmap="Blues", alpha=0.6, vmin=0, vmax=1)
    ax[0].set_title("Average sun visibility (grey) and PSRs (blue) - LOLA")
    ax[1].imshow(f["sun_mean"], extent=ext, cmap="gray", vmin=0, vmax=0.8, alpha=0.5)
    im = ax[1].imshow(total, extent=ext, cmap="viridis")
    fig.colorbar(im, ax=ax[1], fraction=0.046, label="site score (0..1)")
    ax[1].set_title("Base-site score where constraints are met")
    for a in ax:
        for name, lst, la, lo, R, note in MOON_SOUTH_AREAS:
            if la > -85:
                continue
            x0, y0 = area_xy(la, lo)
            a.add_patch(plt.Circle((x0, y0), R, fill=False, ec="red", lw=1, ls="-" if lst == "2024" else "--"))
            a.annotate(name, (x0, y0 + R), color="red", fontsize=7, ha="center", xytext=(0, 2), textcoords="offset points")
        a.set_xlim(-HALF, HALF); a.set_ylim(-HALF, HALF)
        a.set_xlabel("km (90 E ->)"); a.set_ylabel("km (lon 0 ^)")
    for i, s in sites.iterrows():
        r, c = s["_rc"]
        x = (c + 0.5) * CELL - HALF; y = HALF - (r + 0.5) * CELL
        ax[1].plot(x, y, "o", mfc="none", mec="orange" if s["novel"] else "white", ms=9, mew=1.5)
        ax[1].annotate(str(i), (x, y), color="orange" if s["novel"] else "white", fontsize=8,
                       xytext=(4, -8), textcoords="offset points")
    fig.suptitle("Lunar south pole 85-90 S - red circles: NASA Artemis regions as rough areas "
                 "(solid 2024 list, dashed 2022 only), orange: candidates outside them, white: inside")
    fig.tight_layout()
    fig.savefig(path, dpi=130)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-slope", type=float, default=5.0, help="max mean slope per 240 m cell [deg]")
    ap.add_argument("--min-sun", type=float, default=0.3, help="min average sun visibility [0..1]")
    ap.add_argument("--sun-measure", choices=["best", "mean", "raw"], default="best",
                    help="sunlight score: best-lit 60 m pixel of the cell (stretched), cell average (stretched), "
                         "or raw cell average (old behaviour)")
    ap.add_argument("--min-coverage", type=float, default=0.3, help="min fraction of 40 m slope pixels with data per cell")
    ap.add_argument("--eva-km", type=float, default=2.0, help="EVA radius for ice access [km]")
    ap.add_argument("--top-percent", type=float, default=2.0, help="best x %% of valid cells form sites")
    ap.add_argument("--min-cells", type=int, default=4, help="min contiguous cells (4 = 0.23 km2)")
    ap.add_argument("--novel-km", type=float, default=0.0,
                    help="km outside every NASA rough area to count as new (0 = anything outside)")
    ap.add_argument("--min-sep-km", type=float, default=5.0, help="merge candidates closer than this")
    ap.add_argument("--top", type=int, default=25)
    ap.add_argument("--rebuild", action="store_true", help="recompute features from raw files")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    cache = OUT / "features.npz"
    if cache.exists() and not args.rebuild:
        f = dict(np.load(cache))
    else:
        f = build_features()
        np.savez_compressed(cache, **f)

    total, ok, W, parts = score(f, args)
    print(f"\nweights: {W}   sunlight measure: {args.sun_measure}")
    print(f"constraints: mean slope <= {args.max_slope} deg, p90 slope <= {2 * args.max_slope} deg, "
          f"not in PSR, sun visibility >= {args.min_sun}, "
          f"slope data coverage >= {args.min_coverage}, inside 85 S")
    print(f"valid cells: {ok.sum():,} of {ok.size:,} ({100 * ok.mean():.1f} %)")

    sites, thr = find_sites(f, total, args)
    cols = [c for c in sites.columns if not c.startswith("_")]
    sites[cols].to_csv(OUT / "candidates.csv", index_label="rank")
    print(f"\nTop {len(sites)} candidate sites (score >= {thr:.3f}):")
    with pd.option_context("display.width", 250, "display.max_columns", 30):
        print(sites[["lat", "lon_E", "score", "area_km2", "sun_visibility", "sun_best_60m", "earth_visibility",
                     "slope_mean_deg", "dist_surface_coldtrap_km", "temp_max_K",
                     "nearest_nasa_area", "dist_to_nasa_area_km", "novel"]].to_string())
        cmp = nasa_comparison(f, total, ok, sites)
        cmp.to_csv(OUT / "nasa_vs_candidates.csv", index=False)
        print("\nNASA rough areas under the same scoring (best usable cell of each area):")
        print(cmp[cmp.group != "candidate"][["name", "group", "radius_km", "status", "usable_pct", "score", "pct_of_usable",
                                             "would_rank", "sun_avg", "sun_best_60m", "earth", "dist_coldtrap_km",
                                             "candidates_inside"]].to_string(index=False))
    plot(f, total, sites, OUT / "map.png")
    print(f"\nSaved {OUT / 'candidates.csv'}, {OUT / 'nasa_vs_candidates.csv'}, {OUT / 'map.png'}, {cache}")


if __name__ == "__main__":
    main()
