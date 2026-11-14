"""
Bewertet Erdzellen gegen die gemessenen Zielsignaturen aus planetary/targets.json
(Spezifikation: planetary/ZIELSIGNATUREN.md).

Je Merkmal eine von drei Methoden:
  direct     S = 1 - |Erdwert - Zielwert| / Spanne, Spanne = Abstand vom Zielwert zur unaehnlichsten Erde
             (2.-98. Perzentil, flaechengewichtet). Wie scripts/rank.py im Team-Repo.
  quantile   dasselbe auf Perzentilen: Erd-Perzentil gegen body_percentile des Ziels.
  direction  flaechengewichtetes Perzentil in Richtung des Zielwerts (die Erde erreicht ihn nie).
Merkmale ohne Zielwert (null) oder ohne passendes Erdmerkmal werden uebersprungen und gemeldet.

Benutzung:
    from scoring.target_scoring import load_targets, score_target
    T = load_targets("planetary/targets.json")
    s = score_target(df, T["jezero"])       # dim_*, feat_*, total, coverage, best_dim, worst_dim

Aufruf:  python scoring/target_scoring.py [pfad/targets.json] [tabelle.parquet]
         ohne Pfad: ../planetary/targets.json, ersatzweise die Vorlage daneben
"""

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent))
from categories import TARGETS as PROFILES, _weighted_pct, classify, mark_known, top_sites, ENV_CLASSES  # noqa: E402

# Ziel-ID (VERARBEITUNGSPLAN.md, Abschnitt 3) -> Gewichtsprofil aus categories.py
PROFILE_OF = {"shackleton_rim": "mond_suedpol", "shackleton_psr": "mond_suedpol",
              "jezero": "mars_aequatorial", "arcadia": "mars_eis_mittelbreiten"}

# Merkmal -> (Methode, Dimension, Erdspalte bzw. Funktion)
FEATURES = {
    "slope_p50":         ("direct",    "gelaende",    "baseline"),
    "slope_p90":         ("direct",    "gelaende",    "baseline"),
    "relief":            ("direct",    "gelaende",    "baseline"),
    "albedo":            ("direct",    "oberflaeche", lambda d: d["albedo_snowfree"].fillna(d["albedo_sw_mean"])
                          if "albedo_snowfree" in d else d.get("albedo_sw_mean")),
    "thermal_inertia":   ("quantile",  "oberflaeche", "ati"),
    "dust_opacity":      ("quantile",  "staub_wind",  "DUEXTTAU_mean"),
    "dust_storm_days":   ("quantile",  "staub_wind",  "dust_storm_days"),
    "wind_mean":         ("direction", "staub_wind",  "SPEED_mean"),
    "surface_temp_mean": ("direction", "thermik",     "lst_mean"),
    "surface_temp_min":  ("direction", "thermik",     "lst_cold_mean"),
    "diurnal_range":     ("direction", "thermik",     "lst_diurnal_mean"),
    "pressure":          ("direction", "atmosphaere", lambda d: d["PS_hpa"] if "PS_hpa" in d else d.get("pressure_est_hpa")),
    "humidity":          ("direction", "atmosphaere", "QV2M_gkg"),
    "precip":            ("direction", "trockenheit", "precip_mm_yr"),
    "ndvi":              ("direction", "leben",       "ndvi_mean"),
    # wie scripts/pipeline.py: Eis-Proxy aus der Jahresmitteltemperatur (hier Oberflaeche statt Luft)
    "ground_ice":        ("direction", "eis_wasser",  lambda d: ((272.15 - d["lst_mean"]) / 7).clip(0, 1)
                          if "lst_mean" in d else None),
    # hoechster Sonnenstand aus Breite und Achsneigung. Methode Richtung (Plan, Korrektur 15):
    # die Erde erreicht die ca. 1,5 Grad am Mond-Suedpol nie (Minimum ca. 23,4 Grad an den Polen)
    "sun_elevation_max": ("direction", "beleuchtung", lambda d: np.minimum(90, 90 - d["lat"].abs() + 23.44)),
}
# Gelaende: Erdspalte nach Pixelgroesse (Plan, Abschnitt 4), berechnet mit common/terrain.py
# durch earth/dem_features.py (Lauf mit 100 m und 463 m). Bis dahin fehlen diese Spalten und werden uebersprungen.
TERRAIN_COLS = {
    ("slope_p50", 100): "slope_p50_100m", ("slope_p90", 100): "slope_p90_100m", ("relief", 100): "relief_100m",
    ("slope_p50", 463): "slope_p50_463m", ("slope_p90", 463): "slope_p90_463m", ("relief", 463): "relief_463m",
}
EXCLUDED_LC = {1, 2, 3, 4, 5, 12, 13, 14}  # Wald, Acker, Siedlung, Acker-Mosaik (IGBP), wie scripts/modis_landcover.py


def ranking_mask(df):
    """
    Zellen, die ins Ranking duerfen (Plan, Abschnitt 5 und Korrektur 8): kein Wasser (> 50 %), kein Eisschild,
    keine Zelle mit Wald/Acker/Siedlung als Hauptklasse.
    """
    c = lambda k: df[k] if k in df else pd.Series(np.nan, index=df.index)
    water = c("water_pct") > 50
    # Eis nur, wo es auch im waermsten Monat kalt bleibt: MODIS haelt Salzpfannen fuer Schnee (Uyuni)
    ice = ((c("snow_perm_frac") >= 0.8) | (c("snow_ice_pct") >= 60)) & (c("lst_warm_mean").fillna(0) < 280)
    lc = c("landcover").isin(EXCLUDED_LC)
    return ~(water | ice | lc)


def reference_mask(df):
    """Erd-Referenz fuer den Rang-Abgleich (Korrektur 7): vegetationsfreies, eisfreies Land."""
    from categories import _barren
    return ranking_mask(df) & _barren(df).fillna(False)


def load_targets(path):
    data = json.load(open(path, encoding="utf-8"))
    out = {}
    for tid, t in data["targets"].items():
        t = dict(t, id=tid)
        out[tid] = t
    return out


def _earth_values(df, key, feat):
    how = FEATURES[key][2]
    if how == "baseline":
        col = TERRAIN_COLS.get((key, int(feat.get("baseline_m") or 0)))
        return (df[col] if col in df else None), col
    if callable(how):
        v = how(df)
        return (None if v is None else pd.Series(np.asarray(v, dtype="float64"), index=df.index)), "berechnet"
    return (df[how] if how in df else None), how


def _wquantile(x, w, qs):
    ok = x.notna().to_numpy()
    v, ww = x.to_numpy()[ok], w.to_numpy()[ok]
    o = np.argsort(v)
    cw = np.cumsum(ww[o]); cw /= cw[-1]
    return [v[o][min(np.searchsorted(cw, q), len(v) - 1)] for q in qs]


def score_target(df, target, verbose=True):
    """Bewertung aller Zeilen von df fuer ein Ziel aus targets.json."""
    w = pd.Series(np.cos(np.radians(df["lat"].to_numpy())), index=df.index)
    prof = PROFILES[PROFILE_OF[target["id"]]]
    rank_ok = ranking_mask(df)
    ref = reference_mask(df)
    out = pd.DataFrame(index=df.index)
    used, skipped = [], []
    dims = {}
    for key, feat in target["features"].items():
        if key not in FEATURES:
            skipped.append((key, "unbekanntes Merkmal"))
            continue
        tv = feat.get("value")
        if tv is None:
            skipped.append((key, "kein Zielwert"))
            continue
        method, dim, _ = FEATURES[key]
        if key == "albedo" and target.get("body") == "Moon":
            method = "quantile"  # Mond-Albedo (LROC, 643 nm) ist nicht dieselbe Groesse wie MODIS-Kurzwelle
        x, col = _earth_values(df, key, feat)
        if x is None:
            skipped.append((key, f"Erdmerkmal fehlt ({col})"))
            continue
        x = x.astype("float64")
        if method == "direct":
            p2, p98 = _wquantile(x, w, [0.02, 0.98])
            span = max(abs(p2 - tv), abs(p98 - tv)) or 1e-9
            s = (1 - (x - tv).abs() / span).clip(0, 1)
        elif method == "quantile":
            bp = feat.get("body_percentile")
            if bp is None:
                skipped.append((key, "body_percentile fehlt"))
                continue
            # Perzentil relativ zur Erd-Referenz (vegetations- und eisfreies Land), flaechengewichtet
            xr, wr = x[ref & x.notna()], w[ref & x.notna()]
            if len(xr) < 100:
                skipped.append((key, "zu wenig Referenzzellen"))
                continue
            o = np.argsort(xr.to_numpy())
            xs, cw = xr.to_numpy()[o], np.cumsum(wr.to_numpy()[o])
            pe = pd.Series(np.interp(x.to_numpy(), xs, cw / cw[-1]), index=x.index).where(x.notna())
            s = (1 - (pe - bp).abs() / max(bp, 1 - bp)).clip(0, 1)
        else:  # direction
            med = _wquantile(x, w, [0.5])[0]
            pe = _weighted_pct(x, w)
            s = pe if tv > med else 1 - pe
        out[f"feat_{key}"] = s
        dims.setdefault(dim, []).append(s)
        used.append((key, method, col))

    for dim, parts in dims.items():
        out[f"dim_{dim}"] = pd.concat(parts, axis=1).mean(axis=1, skipna=True)
    weights = {d: prof["weights"].get(d, 0) for d in dims if prof["weights"].get(d, 0) > 0}
    if weights:
        S = out[[f"dim_{d}" for d in weights]]
        S.columns = list(weights)
        W = pd.Series(weights)
        avail = S.notna()
        out["total"] = (S.fillna(0) * W).sum(axis=1) / (avail * W).sum(axis=1).replace(0, np.nan)
        out["total"] = out["total"].where(rank_ok)  # Wasser, Eisschild, Wald/Acker/Siedlung nicht ins Ranking
        out["in_ranking"] = rank_ok
        out["coverage"] = (avail * W).sum(axis=1) / sum(v for v in prof["weights"].values() if v > 0)
        arr = S.to_numpy(dtype="float64")
        has = avail.any(axis=1).to_numpy()
        names = np.array(list(weights), dtype=object)
        best = np.full(len(S), None, dtype=object); worst = best.copy()
        if has.any():
            best[has] = names[np.nanargmax(arr[has], axis=1)]
            worst[has] = names[np.nanargmin(arr[has], axis=1)]
        out["best_dim"], out["worst_dim"] = best, worst
    else:
        out["total"] = np.nan; out["coverage"] = 0.0; out["best_dim"] = None; out["worst_dim"] = None

    if verbose:
        print(f"\n{target['id']} ({target.get('body')}): {len(used)} Merkmale bewertet, {len(skipped)} uebersprungen")
        for k, m, c in used:
            print(f"   + {k:18s} {m:9s} <- {c}")
        for k, why in skipped:
            print(f"   - {k:18s} {why}")
    return out


if __name__ == "__main__":
    here = Path(__file__).resolve().parent.parent
    # Standard: ausgefuellte Datei im Repo (planetary/targets.json), sonst die Vorlage
    candidates = [here.parent / "planetary" / "targets.json", here.parent / "planetary" / "targets_template.json",
                  here / "schnittstelle" / "targets_template.json"]
    tpath = Path(sys.argv[1]) if len(sys.argv) > 1 else next(p for p in candidates if p.exists())
    table = here / "data" / "earth" / (sys.argv[2] if len(sys.argv) > 2 else "earth_features_025deg.parquet")
    df = pd.read_parquet(table)
    df["env_class"] = classify(df)
    names = {c["id"]: c["name"] for c in ENV_CLASSES}
    T = load_targets(tpath)
    print(f"Zielsignaturen: {tpath}\nErdtabelle:     {table.name} ({len(df):,} Zellen)")
    for tid, t in T.items():
        s = score_target(df, t)
        if s["total"].notna().sum() == 0:
            continue
        idx = top_sites(df, s["total"], n=10, min_km=200)
        top = df.loc[idx, ["lat", "lon", "env_class"]].join(s.loc[idx, ["total", "coverage", "best_dim", "worst_dim"]])
        known = mark_known(top)
        print(f"   Top 10 (Datenabdeckung {s['coverage'].mean():.0%}):")
        for i, r in top.iterrows():
            tag = f"bekannt: {known[i]}" if isinstance(known[i], str) else "NEU"
            print(f"     {r.lat:7.2f} {r.lon:8.2f}  {r.total:.2f}  {names[r.env_class]:30.30s}  "
                  f"passt: {r.best_dim:11s} bricht: {r.worst_dim:11s}  {tag}")
