import sys, json, re, base64, warnings
import numpy as np, xarray as xr, rdata, pyshtools as pysh, shapefile
from scipy.ndimage import uniform_filter
from shapely.geometry import shape, Point
from shapely import STRtree, points as shp_points
warnings.filterwarnings('ignore')
D, OUT = sys.argv[1], sys.argv[2]
KM = 18.53  # common baseline in km (10 arcmin on Earth)

# ---------- Earth rasters on the 10' grid (1080 x 2160, north-up, lon -180..180, cell centres)
def packed(f):
    o = rdata.conversion.convert(rdata.parser.parse_file(f'{D}/{f}'))
    if isinstance(o, dict): o = list(o.values())[0]
    d = o.definition[0]
    g = {k: float(v) for k, v in re.findall(r'(ncols|nrows|xmin|xmax|ymin|ymax)=([-\d.]+)', d)}
    return np.asarray(o.values).ravel().reshape(int(g['nrows']), int(g['ncols'])), g
temp, _ = packed('temp.rda'); prec, _ = packed('prec.rda')
NR, NC = temp.shape
lat = 90 - (np.arange(NR) + .5) / 6; lon = -180 + (np.arange(NC) + .5) / 6
land = ~np.isnan(temp)

topo = xr.open_dataset(f'{D}/earth_topo.nc').topography  # grid-registered, lat asc
topo = topo.interp(latitude=lat, longitude=lon).values
elev = np.where(topo > 0, topo, 0.0)

# NDVI: MODIS MOD13C2 2023 annual mean (see modis_ndvi.py); missing on land -> bare
ndvi = np.load(f'{D}/modis_ndvi.npz')['a'].astype(float)
ndvi_missing = np.isnan(ndvi) & land
ndvi = np.where(np.isnan(ndvi), 0.0, ndvi).clip(0, None)

# ---------- terrain metrics at a constant ~18.5 km baseline
coslat = np.cos(np.radians(lat))
k = np.clip(np.round(1 / coslat), 1, 24).astype(int)   # E-W pixels per 18.5 km
def band(fn):
    out = np.empty((NR, NC))
    for kk in np.unique(k):
        rows = np.where(k == kk)[0]
        out[rows] = fn(kk)[rows]
    return out
sm = band(lambda kk: uniform_filter(elev, size=(1, kk), mode=('nearest', 'wrap')))
dzdy = np.gradient(sm, axis=0) / (KM * 1000)
dzdx = band(lambda kk: (np.roll(sm, -kk, 1) - np.roll(sm, kk, 1)) / (2 * kk)) / (KM * 1000 * (coslat * k)[:, None])
slope = np.degrees(np.arctan(np.hypot(dzdx, dzdy)))
slope55 = band(lambda kk: uniform_filter(slope, size=(3, 3 * kk), mode=('nearest', 'wrap')))
def std_win(kk):
    m = uniform_filter(sm, size=(5, 5 * kk), mode=('nearest', 'wrap'))
    m2 = uniform_filter(sm ** 2, size=(5, 5 * kk), mode=('nearest', 'wrap'))
    return np.sqrt(np.clip(m2 - m ** 2, 0, None))
relief = band(std_win)

# ---------- other dimensions
sun = np.minimum(90, 90 - np.abs(lat) + 23.44)[:, None] * np.ones((1, NC))
press = 1013.25 * (1 - 2.25577e-5 * elev) ** 5.25588
ice = np.clip((-1 - temp) / 7, 0, 1)    # permafrost proxy from mean annual air temperature
dtr = np.load(f'{D}/modis_dtr.npz')['a'].astype(float)      # MODIS MOD11C3 2023: mean of (day LST - night LST)
print('dtr missing on land', float((np.isnan(dtr) & land).sum() / land.sum()))
dtr = np.where(np.isnan(dtr), 0.0, dtr).clip(0, None)
albedo = np.load(f'{D}/modis_albedo.npz')['a'].astype(float)   # MODIS MCD43C3 2023, shortwave, snow-free where possible
print('albedo missing on land', float((np.isnan(albedo) & land).sum() / land.sum()))
albedo = np.where(np.isnan(albedo), np.nanmedian(albedo[land]), albedo)
ati = (1 - albedo) / np.maximum(dtr, 1.0)      # apparent thermal inertia, 1/K

# ---------- glacier mask + names
def read(name):
    sf = shapefile.Reader(f'{D}/{name}', encoding='utf-8')
    fields = [f[0] for f in sf.fields[1:]]
    return [(shape(s.shape.__geo_interface__), dict(zip(fields, s.record))) for s in sf.iterShapeRecords()]
LON, LAT = np.meshgrid(lon, lat)
gl = [g for g, _ in read('ne_10m_glaciated_areas')] + [g for g, _ in read('ne_10m_antarctic_ice_shelves_polys')]
tree = STRtree(gl)
idx = np.where(land.ravel())[0]
pts = shp_points(LON.ravel()[idx], LAT.ravel()[idx])
hit = tree.query(pts, predicate='within')[0]
glac = np.zeros(NR * NC, bool); glac[idx[np.unique(hit)]] = True; glac = glac.reshape(NR, NC)

# ---------- aggregate 2x2 -> 20' grid
def agg(a, w):
    a = np.where(w, a, np.nan).reshape(NR // 2, 2, NC // 2, 2)
    return np.nanmean(a, axis=(1, 3))
# land cover prefilter (CLAUDE.md): drop cells with > 50 % water + forest + cropland + urban (MCD12C1)
lc_excl = np.nan_to_num(np.load(f'{D}/modis_landcover.npz')['excluded'].astype(float), nan=0.0)
print('land cells dropped by land cover filter', float((land & ~glac & (lc_excl > 0.5)).sum() / (land & ~glac).sum()))
valid = land & ~glac & (lc_excl <= 0.5)
n_valid = valid.reshape(NR // 2, 2, NC // 2, 2).sum(axis=(1, 3))
mask = n_valid >= 2
F_raw = dict(slope=agg(slope55, valid), relief=agg(relief, valid), sun=agg(sun, valid), temp=agg(temp, valid),
             prec=agg(prec, valid), ndvi=agg(ndvi, valid), press=agg(press, valid), ice=agg(ice, valid), ati=agg(ati, valid), albedo=agg(albedo, valid))
lat2 = lat.reshape(-1, 2).mean(1); lon2 = lon.reshape(-1, 2).mean(1)

TR = dict(slope=lambda x: np.log10(x + .01), relief=lambda x: np.log10(x + 1), sun=lambda x: x, temp=lambda x: x,
          prec=lambda x: np.log10(x + 10), ndvi=lambda x: x, press=lambda x: np.log10(np.maximum(x, 1e-9)), ice=lambda x: x, ati=lambda x: np.log10(np.maximum(x, 1e-4)), albedo=lambda x: x)
RNG = dict(slope=(-2, 1.2), relief=(0, 3.6), sun=(0, 90), temp=(-60, 35), prec=(1, 4.1), ndvi=(0, 0.92), press=(2.6, 3.01), ice=(0, 1), ati=(-2.3, 0), albedo=(0, 0.9))
DIMS = list(RNG)
Q = {}
for d in DIMS:
    lo, hi = RNG[d]
    Q[d] = np.round((np.clip(TR[d](F_raw[d]), lo, hi) - lo) / (hi - lo) * 255)

# ---------- Moon / Mars targets: same metrics, same baseline, from LOLA / MOLA
def patch_metrics(coeffs, radius_km, lat0, lon0, n=9):
    """slope (mean over 55 km) and relief (std over 92 km) at the site, sampled on an 18.53 km grid"""
    h = (n - 1) / 2
    xs = (np.arange(n) - h) * KM
    X, Y = np.meshgrid(xs, -xs)                      # km east, km north
    rho = np.hypot(X, Y) / radius_km; az = np.arctan2(X, Y)
    p0 = np.radians(lat0)
    la = np.arcsin(np.sin(p0) * np.cos(rho) + np.cos(p0) * np.sin(rho) * np.cos(az))
    lo = np.radians(lon0) + np.arctan2(np.sin(az) * np.sin(rho) * np.cos(p0), np.cos(rho) - np.sin(p0) * np.sin(la))
    z = coeffs.expand(lat=np.degrees(la).ravel(), lon=np.degrees(lo).ravel() % 360).reshape(n, n)
    gy, gx = np.gradient(z, KM * 1000)
    sl = np.degrees(np.arctan(np.hypot(gx, gy)))
    c = int(h)
    return float(sl[c-1:c+2, c-1:c+2].mean()), float(z[c-2:c+3, c-2:c+3].std()), float(z[c, c])

mars = pysh.SHCoeffs.from_file(f'{D}/MarsTopo719.shape', lmax=719)
mars.coeffs[:, 0, 0] = 0; mars.coeffs[0, 2, 0] = 0          # drop mean radius and flattening
mars = pysh.SHCoeffs.from_array(mars.coeffs[:, :576, :576])   # band-limit to the 18.5 km half wavelength
moon_grid = xr.open_dataset(f'{D}/moon_topo.nc').topography.values[:-1, :-1]
moon = pysh.SHGrid.from_array(moon_grid).expand()
moon = pysh.SHCoeffs.from_array(moon.coeffs[:, :296, :296]); moon.coeffs[:, 0, 0] = 0

def earth_check(lat0, lon0):
    i = np.abs(lat2 - lat0).argmin(); j = np.abs(lon2 - lon0).argmin()
    return {d: float(F_raw[d][i, j]) for d in DIMS}

TARGETS = [
  dict(id='arcadia', body='Mars', name='Arcadia Planitia', lat=40.0, lon=200.0, R=3389.5, co=mars,
       temp=-70, prec=0, ndvi=0, press=8.5, ice=1, ati=(1 - 0.25) / 60, albedo=0.25, sun=min(90, 90 - 40 + 25.19)),
  dict(id='jezero', body='Mars', name='Jezero Crater', lat=18.44, lon=77.45, R=3389.5, co=mars,
       temp=-55, prec=0, ndvi=0, press=7.5, ice=0, ati=(1 - 0.17) / 75, albedo=0.17, sun=90.0),
  dict(id='shackleton', body='Moon', name='South Pole (Shackleton)', lat=-89.67, lon=129.8, R=1737.4, co=moon,
       temp=-170, prec=0, ndvi=0, press=1e-9, ice=1, ati=(1 - 0.15) / 150, albedo=0.15, sun=90 - 89.67 + 1.54),
]
for t in TARGETS:
    t['slope'], t['relief'], t['z'] = patch_metrics(t.pop('co'), t.pop('R'), t['lat'], t['lon'])
    t['raw'] = {d: t[d] for d in DIMS}
    t['f'] = {d: float(TR[d](np.float64(t[d]))) for d in DIMS}
    # span: target -> least similar land on Earth (2nd..98th percentile, area weighted)
    w = np.cos(np.radians(lat2))[:, None] * np.ones_like(F_raw['temp'])
    t['span'] = {}
    for d in DIMS:
        v = (Q[d][mask] / 255) * (RNG[d][1] - RNG[d][0]) + RNG[d][0]
        o = np.argsort(v); cw = np.cumsum(w[mask][o]); cw /= cw[-1]
        p2, p98 = v[o][np.searchsorted(cw, .02)], v[o][np.searchsorted(cw, .98)]
        t['span'][d] = float(max(abs(p2 - t['f'][d]), abs(p98 - t['f'][d])))
    for d in DIMS: t.pop(d, None)
    print(t['id'], {k: round(v, 3) for k, v in t['raw'].items()}, 'z', round(t['z']))

# ---------- labels
regions = read('ne_10m_geography_regions_polys'); countries = read('ne_50m_admin_0_countries')
places = shapefile.Reader(f'{D}/ne_10m_populated_places_simple', encoding='utf-8')
pf = [f[0] for f in places.fields[1:]]
P = [dict(zip(pf, r)) for r in places.records()]
plat = np.radians([p['latitude'] for p in P]); plon = np.radians([p['longitude'] for p in P])
print('region fields', [k for k in regions[0][1]][:30]); print('country fields de', [k for k in countries[0][1] if 'DE' in k.upper()][:5])
def nm(rec, *keys):
    for kx in keys:
        for kk in (kx, kx.lower(), kx.upper()):
            if rec.get(kk): return str(rec[kk]).title() if str(rec[kk]).isupper() else str(rec[kk])
    return ''
rg = [g for g, _ in regions]; rarea = np.array([g.area for g in rg]); rtree = STRtree(rg)
cg = [g for g, _ in countries]; ctree = STRtree(cg)
ii, jj = np.where(mask)
pts = shp_points(lon2[jj], lat2[ii])
def assign(tree, areas=None):
    a, b = tree.query(pts, predicate='within')
    res = np.full(len(pts), -1)
    if areas is None: res[a] = b
    else:
        o = np.argsort(-areas[b]); res[a[o]] = b[o]     # smallest polygon wins
    return res
ri = assign(rtree, rarea); ci = assign(ctree)
miss = np.where(ci < 0)[0]
if len(miss): ci[miss] = ctree.nearest(pts[miss])
labels, lab_idx, lab_of = [], {}, np.zeros(len(pts), int)
for n in range(len(pts)):
    cn = nm(countries[ci[n]][1], 'NAME_EN', 'NAME')
    if ri[n] >= 0: lab = f"{nm(regions[ri[n]][1], 'NAME_EN', 'NAME')}, {cn}"
    else:
        la, lo = np.radians(lat2[ii[n]]), np.radians(lon2[jj[n]])
        dd = np.arccos(np.clip(np.sin(la) * np.sin(plat) + np.cos(la) * np.cos(plat) * np.cos(plon - lo), -1, 1)) * 6371
        m = dd.argmin()
        lab = f"near {P[m]['name']}, {cn}" if dd[m] < 400 else cn
    if lab not in lab_idx: lab_idx[lab] = len(labels); labels.append(lab)
    lab_of[n] = lab_idx[lab]
print('cells', len(pts), 'labels', len(labels), 'glaciated 10min cells', int(glac.sum()), 'ndvi missing on valid land', float((ndvi_missing & valid).sum() / valid.sum()))

feat = np.stack([Q[d][mask] for d in DIMS], 1).astype(np.uint8)
out = dict(nr=NR // 2, nc=NC // 2, dims=DIMS, rng=RNG, targets=TARGETS, labels=labels,
           mask=base64.b64encode(np.packbits(mask.ravel()).tobytes()).decode(),
           feat=base64.b64encode(feat.tobytes()).decode(),
           lab=base64.b64encode(lab_of.astype('<u2').tobytes()).decode())
json.dump(out, open(f'{OUT}/data.json', 'w'), ensure_ascii=False)
np.savez(f'{OUT}/check.npz', mask=mask, feat=feat, lat2=lat2, lon2=lon2, lab=lab_of, **{f'raw_{d}': F_raw[d] for d in DIMS})
for nme, la, lo in [('Atacama', -24.1, -69.9), ('Haughton', 75.4, -89.8), ('Lhasa-Plateau', 33, 88), ('Sahara', 23, 12), ('Amazon', -3, -60)]:
    print(nme, {k: round(v, 2) for k, v in earth_check(la, lo).items()})
