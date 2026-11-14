"""Ranking and controls for out/data.json. Same scoring as the map page.
usage: rank.py OUT_DIR   -> prints the ranking, writes OUT_DIR/controls.json

score(cell) = 100 * sum_d w_d * s_d / sum_d w_d over dimensions that have a target value and a cell value,
s_d = 1 - |Earth - target| / span_d. Default weight 1, or 0.5 where the target value is a rough estimate (class E).
Cells need at least 80 % of the active weight covered to be ranked."""
import sys, json, base64, numpy as np
O = sys.argv[1]
d = json.load(open(f'{O}/data.json'))
dims = d['dims']; nr, nc = d['nr'], d['nc']
mask = np.unpackbits(np.frombuffer(base64.b64decode(d['mask']), np.uint8))[:nr * nc].reshape(nr, nc).astype(bool)
feat = np.frombuffer(base64.b64decode(d['feat']), np.uint8).reshape(-1, len(dims))
lab = np.frombuffer(base64.b64decode(d['lab']), '<u2')
ii, jj = np.where(mask); lat = 90 - (ii + .5) * 180 / nr; lon = -180 + (jj + .5) * 360 / nc
area = np.cos(np.radians(lat))
def dist(la, lo, LA, LO):
    a, b, c, e = map(np.radians, (la, lo, LA, LO))
    return 6371 * np.arccos(np.clip(np.sin(a) * np.sin(c) + np.cos(a) * np.cos(c) * np.cos(e - b), -1, 1))
def sims(t):
    S = np.full(feat.shape, np.nan)
    for n, dm in enumerate(dims):
        if t['f'][dm] is None: continue
        lo_, hi_ = d['rng'][dm]; v = lo_ + feat[:, n] / 254 * (hi_ - lo_)
        S[:, n] = np.where(feat[:, n] == 255, np.nan, np.clip(1 - np.abs(v - t['f'][dm]) / t['span'][dm], 0, 1))
    return S
def default_w(t): return np.array([0.0 if t['f'][dm] is None else (0.5 if t['src'][dm] == 'E' else 1.0) for dm in dims])
def score(S, w):
    ok = ~np.isnan(S); num = np.nansum(S * w, 1); den = (ok * w).sum(1)
    sc = np.where(den > 0, 100 * num / np.maximum(den, 1e-9), np.nan)
    return np.where(den / w.sum() >= 0.8, sc, np.nan)
def pct_of(sc):
    v = np.where(np.isnan(sc), -1, sc); o = np.argsort(v); cw = np.cumsum(area[o]); cw /= cw[-1]
    p = np.empty(len(sc)); p[o] = cw * 100; return p
def top(sc, n=20, sep=500):
    picked = []
    for o in np.argsort(-np.where(np.isnan(sc), -1, sc)):
        if all(dist(lat[o], lon[o], lat[p], lon[p]) > sep for p in picked): picked.append(o)
        if len(picked) >= n: break
    return picked
def is_known(o):
    for name, la, lo, r in d['known']:
        if dist(lat[o], lon[o], la, lo) <= r: return name
    return None

POS = dict(arcadia=['Qaidam Basin, China', 'Haughton Crater, Devon Island'], jezero=['Atacama (Yungay), Chile', 'Death Valley'],
           shackleton=['Haughton Crater, Devon Island', 'Svalbard (AMASE)'])
ndvi_i, prec_i = dims.index('ndvi'), dims.index('prec')
def phys(n, dm): lo_, hi_ = d['rng'][dm]; return lo_ + feat[:, n] / 254 * (hi_ - lo_)
humid = (phys(ndvi_i, 'ndvi') > 0.5) & (10 ** phys(prec_i, 'prec') - 10 > 800) & (feat[:, ndvi_i] != 255)
rng = np.random.default_rng(0); controls = {}
for t in d['targets']:
    S = sims(t); w = default_w(t); sc = score(S, w); pc = pct_of(sc); best = top(sc)
    print(f"\n===== {t['body']}, {t['name']}  (weights: {' '.join(f'{a}={b:g}' for a, b in zip(dims, w))})")
    for o in best[:10]:
        k = is_known(o)
        print(f"{sc[o]:5.1f} {lat[o]:7.2f} {lon[o]:8.2f} {('known: ' + k if k else 'NEW'):34.34s} {d['labels'][lab[o]][:46]:46s}", ' '.join('  -' if np.isnan(x) else f'{x * 100:3.0f}' for x in S[o]))
    pos = []
    for name in POS[t['id']]:
        k = next(x for x in d['known'] if x[0] == name); dd = dist(k[1], k[2], lat, lon); c = dd.argmin()
        if dd[c] > 100: pos.append(dict(site=name, covered=False)); continue
        dimp = {dm: float(pct_of(np.where(np.isnan(S[:, n]), np.nan, S[:, n]))[c]) for n, dm in enumerate(dims) if w[n] > 0 and not np.isnan(S[c, n])}
        bd = max(dimp, key=dimp.get)
        pos.append(dict(site=name, covered=True, total_pct=float(pc[c]), best_dim=bd, best_dim_pct=dimp[bd]))
    neg = float(np.average(pc[humid], weights=area[humid]))
    # robustness: +-25 % on every weight, 200 draws; share of the baseline top 20 found again within 500 km
    keep = []
    for _ in range(200):
        t2 = top(score(S, w * rng.uniform(0.75, 1.25, len(w))))
        keep.append(np.mean([min(dist(lat[b], lon[b], lat[x], lon[x]) for x in t2) <= 500 for b in best]))
    controls[t['id']] = dict(positive=pos, negative_humid_mean_pct=neg, robustness_top20_kept=float(np.mean(keep)),
                             robustness_top20_kept_min=float(np.min(keep)), new_in_top20=int(sum(is_known(o) is None for o in best)))
    print('positive:', [(p['site'], round(p.get('total_pct', -1)), p.get('best_dim'), round(p.get('best_dim_pct', -1))) for p in pos])
    print(f"negative (humid, vegetated cells) mean percentile: {neg:.0f} | top 20 kept under +-25 % weights: mean {np.mean(keep) * 100:.0f} %, min {np.min(keep) * 100:.0f} % | new among top 20: {controls[t['id']]['new_in_top20']}")
controls['humid_cells'] = int(humid.sum()); controls['cells'] = int(len(lat))
json.dump(controls, open(f'{O}/controls.json', 'w'), indent=1)
