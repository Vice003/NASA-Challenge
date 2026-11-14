"""Analog Finder, coarse pipeline (20 arcmin cells): Earth features + Moon/Mars fingerprints -> out/data.json

usage: pipeline.py RAW_DIR OUT_DIR [DERIVED_DIR] [VICENTE_DERIVED_DIR]

Earth inputs are NASA/ESA products only, except the elevation model (ETOPO1, NOAA) that the
18.5 km terrain baseline needs, and Natural Earth, which is used for place names only.
Missing values stay missing (NaN -> code 255); they are never replaced by 0."""
import sys, json, ast, base64, warnings
import numpy as np, xarray as xr, pyshtools as pysh, shapefile
from scipy.ndimage import uniform_filter
from shapely.geometry import shape
from shapely import STRtree, points as shp_points
warnings.filterwarnings('ignore')
D, OUT = sys.argv[1], sys.argv[2]
DER = sys.argv[3] if len(sys.argv) > 3 else 'data/derived'
VIC = sys.argv[4] if len(sys.argv) > 4 else 'vicente/derived'
KM = 18.53            # common terrain baseline in km (10 arcmin on Earth)
NR, NC = 1080, 2160   # 10 arcmin grid, north-up, lon -180..180, cell centres
lat = 90 - (np.arange(NR) + .5) / 6; lon = -180 + (np.arange(NC) + .5) / 6
def layer(folder, name, key='a'): return np.load(f'{folder}/{name}.npz')[key].astype(float)

# ---------- Earth layers (2003-2024 climatologies from vicente/derived, same grid)
temp = layer(VIC, 'lst_mean')            # MODIS Terra+Aqua land surface temperature, deg C
prec = layer(VIC, 'prec')                # MERRA-2 precipitation, mm/yr
press = layer(VIC, 'pressure')           # MERRA-2 surface pressure, hPa
dtr = layer(VIC, 'modis_dtr')            # MODIS day-night swing, max - min of 4 overpasses, K
ndvi = layer(VIC, 'modis_ndvi').clip(0, None)   # MODIS NDVI
albedo = layer(VIC, 'albedo_snowfree')   # MODIS MCD43C3 shortwave albedo, snow-free
dust = layer(VIC, 'dust_aod')            # MERRA-2 dust aerosol optical depth
snow = np.nan_to_num(layer(DER, 'modis_landcover', 'snow'), nan=0.0)   # MCD12C1 share of permanent snow and ice
lc_excl = np.nan_to_num(layer(DER, 'modis_landcover', 'excluded'), nan=0.0)  # MCD12C1: water+forest+crop+urban share
land = ~np.isnan(temp)

topo = xr.open_dataset(f'{D}/earth_topo.nc').topography.interp(latitude=lat, longitude=lon).values
elev = np.where(topo > 0, topo, 0.0)

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

# ---------- derived dimensions
sun = np.minimum(90, 90 - np.abs(lat) + 23.44)[:, None] * np.ones((1, NC))
ice = np.clip((1 - temp) / 6, 0, 1)      # ground-ice estimate: 1 at mean surface temp <= -5 C, 0 above +1 C
ati = np.where(dtr > 5, (1 - albedo) / dtr, np.nan)   # apparent thermal inertia; meaningless at small swings

# ---------- masks and aggregation 2x2 -> 20 arcmin
valid = land & (snow < 0.5) & (lc_excl <= 0.5)
print('land 10min cells', int(land.sum()), '| permanent snow/ice', round(float((land & (snow >= .5)).sum() / land.sum()), 3),
      '| dropped by land cover filter', round(float((land & (snow < .5) & (lc_excl > .5)).sum() / land.sum()), 3))
def agg(a):
    a = np.where(valid, a, np.nan).reshape(NR // 2, 2, NC // 2, 2)
    return np.nanmean(a, axis=(1, 3))
mask = valid.reshape(NR // 2, 2, NC // 2, 2).sum(axis=(1, 3)) >= 2
landmask = land.reshape(NR // 2, 2, NC // 2, 2).any(axis=(1, 3))
F_raw = dict(slope=agg(slope55), relief=agg(relief), sun=agg(sun), temp=agg(temp), prec=agg(prec), ndvi=agg(ndvi),
             press=agg(press), ice=agg(ice), ati=agg(ati), albedo=agg(albedo), dust=agg(dust))
lat2 = lat.reshape(-1, 2).mean(1); lon2 = lon.reshape(-1, 2).mean(1)

TR = dict(slope=lambda x: np.log10(x + .01), relief=lambda x: np.log10(x + 1), sun=lambda x: x, temp=lambda x: x,
          prec=lambda x: np.log10(x + 10), ndvi=lambda x: x, press=lambda x: np.log10(np.maximum(x, 1e-9)), ice=lambda x: x,
          ati=lambda x: np.log10(np.maximum(x, 1e-4)), albedo=lambda x: x, dust=lambda x: np.log10(np.maximum(x, 1e-3)))
RNG = dict(slope=(-2, 1.2), relief=(0, 3.6), sun=(0, 90), temp=(-60, 50), prec=(1, 4.1), ndvi=(0, 0.92), press=(2.6, 3.03),
           ice=(0, 1), ati=(-2.3, 0), albedo=(0, 0.9), dust=(-3, 0))
DIMS = list(RNG)
Q = {}
for d in DIMS:
    lo, hi = RNG[d]
    q = np.round((np.clip(TR[d](F_raw[d]), lo, hi) - lo) / (hi - lo) * 254)
    Q[d] = np.where(np.isnan(F_raw[d]), 255, q)
    print(f'{d:7s} missing in {float((Q[d][mask] == 255).mean()) * 100:5.1f} % of cells')

# ---------- Moon / Mars targets: same terrain metrics, same baseline, from LOLA / MOLA
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
    return float(sl[c-1:c+2, c-1:c+2].mean()), float(z[c-2:c+3, c-2:c+3].std())

mars_sh = pysh.SHCoeffs.from_file(f'{D}/MarsTopo719.shape', lmax=719)
mars_sh.coeffs[:, 0, 0] = 0; mars_sh.coeffs[0, 2, 0] = 0    # drop mean radius and flattening
mars_sh = pysh.SHCoeffs.from_array(mars_sh.coeffs[:, :576, :576])   # band-limit to the 18.5 km half wavelength
moon_grid = xr.open_dataset(f'{D}/moon_topo.nc').topography.values[:-1, :-1]
moon = pysh.SHGrid.from_array(moon_grid).expand()
moon = pysh.SHCoeffs.from_array(moon.coeffs[:, :296, :296]); moon.coeffs[:, 0, 0] = 0

# Where each target value comes from: M = measured here from LOLA/MOLA, C = computed or physical,
# L = rounded literature value for a well-established property (still needs a citable source),
# E = rough estimate where instruments or methods differ between the bodies; counts half by default.
# None = no usable target value; the dimension is then not scored for that target.
MARS_SRC = dict(slope='M', relief='M', sun='C', prec='C', ndvi='C', temp='L', press='L', ice='L', ati='E', albedo='E', dust='E')
MOON_SRC = dict(slope='M', relief='M', sun='C', prec='C', ndvi='C', press='C', dust='C', temp='E', ice='L', albedo='E', ati='E')
MARS_EST = dict(MARS_SRC, temp='E', press='E')   # sites where even temperature and pressure are my rough values
def mars(id, name, lat, lon, kind, src=MARS_SRC, **v):
    v.setdefault('prec', 0); v.setdefault('ndvi', 0); v.setdefault('dust', 0.5); v['sun'] = min(90, 90 - abs(lat) + 25.19)
    return dict(id=id, body='Mars', name=name, lat=lat, lon=lon, kind=kind, approx=False, R=3389.5, co=mars_sh, src=src, v=v)
def moonsite(id, name, lat, lon, approx=True, kind='Artemis candidate region'):
    v = dict(temp=-170, prec=0, ndvi=0, press=1e-9, ice=1, ati=None, albedo=0.15, dust=0, sun=90 - abs(lat) + 1.54)
    return dict(id=id, body='Moon', name=name, lat=lat, lon=lon % 360, kind=kind, approx=approx, R=1737.4, co=moon, src=MOON_SRC, v=v)
ICE, ROVER = 'Base candidate with shallow ice', 'Rover landing site, for comparison'
# Lunar region centres are approximate: NASA has published names and maps of the nine regions (Oct 2024), not
# coordinates. Centres follow the named features and the 2022 region list; Slater Plain from Wueller et al. 2026.
TARGETS = [
  mars('arcadia', 'Arcadia Planitia', 40.0, 200.0, ICE, temp=-70, press=8.5, ice=1, ati=(1 - 0.25) / 60, albedo=0.25),
  mars('deuteronilus', 'Deuteronilus Mensae', 44.9, 24.5, ICE, src=MARS_EST, temp=-65, press=8.0, ice=1, ati=(1 - 0.20) / 60, albedo=0.20),
  mars('jezero', 'Jezero Crater', 18.44, 77.45, ROVER, temp=-55, press=7.5, ice=0, ati=(1 - 0.17) / 75, albedo=0.17),
  mars('gale', 'Gale Crater', -4.59, 137.44, ROVER, temp=-50, press=8.4, ice=0, ati=(1 - 0.20) / 75, albedo=0.20),
  moonsite('cabeus_b', 'Peak near Cabeus B', -83.5, -60.0),
  moonsite('haworth', 'Haworth', -86.8, -22.6),
  moonsite('malapert', 'Malapert Massif', -85.99, -0.23),
  moonsite('mouton_plateau', 'Mons Mouton Plateau', -85.4, 31.7),
  moonsite('mouton', 'Mons Mouton', -84.6, 29.0),
  moonsite('nobile_1', 'Nobile Rim 1', -85.4, 37.4),
  moonsite('nobile_2', 'Nobile Rim 2', -84.0, 60.0),
  moonsite('de_gerlache_2', 'de Gerlache Rim 2', -88.2, -64.6),
  moonsite('slater', 'Slater Plain', -87.5, 124.5),
  moonsite('shackleton', 'Shackleton rim', -89.67, 129.8, approx=False, kind='South pole reference site'),
]
w = np.cos(np.radians(lat2))[:, None] * np.ones((NR // 2, NC // 2))
for t in TARGETS:
    v = t.pop('v'); v['slope'], v['relief'] = patch_metrics(t.pop('co'), t.pop('R'), t['lat'], t['lon'])
    t['raw'] = {d: v[d] for d in DIMS}
    t['f'] = {d: (None if v[d] is None else float(TR[d](np.float64(v[d])))) for d in DIMS}
    t['span'] = {}
    for d in DIMS:   # span: target -> least similar land on Earth (2nd..98th percentile, area weighted)
        if t['f'][d] is None: t['span'][d] = None; continue
        ok = mask & (Q[d] != 255)
        x = (Q[d][ok] / 254) * (RNG[d][1] - RNG[d][0]) + RNG[d][0]
        o = np.argsort(x); cw = np.cumsum(w[ok][o]); cw /= cw[-1]
        p2, p98 = x[o][np.searchsorted(cw, .02)], x[o][np.searchsorted(cw, .98)]
        t['span'][d] = float(max(abs(p2 - t['f'][d]), abs(p98 - t['f'][d])))
    print(t['id'], {kk: (None if vv is None else round(vv, 3)) for kk, vv in t['raw'].items()})

# ---------- known analog sites: one list for the whole team (vicente/scoring/categories.py)
EN = {'Atacama-Wueste (Yungay, Kern)': 'Atacama (Yungay), Chile', 'Altiplano / Licancabur': 'Altiplano / Licancabur',
      'McMurdo Dry Valleys': 'McMurdo Dry Valleys, Antarctica', 'Dome C / Concordia': 'Dome C / Concordia, Antarctica',
      'Haughton-Krater / Devon Island': 'Haughton Crater, Devon Island', 'Island, Hochland': 'Iceland highlands',
      'Utah, MDRS Hanksville': 'MDRS Hanksville, Utah', 'Mojave-Wueste': 'Mojave Desert', 'Ries-Krater': 'Ries Crater, Germany',
      'Mistastin-Krater': 'Mistastin Crater, Canada', 'Qaidam-Becken': 'Qaidam Basin, China', 'Namib-Wueste': 'Namib Desert',
      'Negev / Ramon-Krater (D-MARS)': 'Negev / Ramon Crater (D-MARS)', 'Lonar-Krater': 'Lonar Crater, India',
      'Rio Tinto': 'Río Tinto, Spain', 'Sudbury': 'Sudbury, Canada', 'Pilbara': 'Pilbara, Australia'}
known = []
try:
    src = open(f'{VIC}/../scoring/categories.py', encoding='utf-8').read()
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Assign) and getattr(node.targets[0], 'id', '') == 'KNOWN_ANALOGS':
            known = [[EN.get(n, n), float(la), float(lo), float(r)] for n, la, lo, r, *_ in ast.literal_eval(node.value)]
except OSError:
    pass
print('known analog sites', len(known))

# ---------- labels (Natural Earth, names only)
def read(name):
    sf = shapefile.Reader(f'{D}/{name}', encoding='utf-8')
    fields = [f[0] for f in sf.fields[1:]]
    return [(shape(s.shape.__geo_interface__), dict(zip(fields, s.record))) for s in sf.iterShapeRecords()]
regions = read('ne_10m_geography_regions_polys'); countries = read('ne_50m_admin_0_countries')
places = shapefile.Reader(f'{D}/ne_10m_populated_places_simple', encoding='utf-8')
pf = [f[0] for f in places.fields[1:]]
P = [dict(zip(pf, r)) for r in places.records()]
plat = np.radians([p['latitude'] for p in P]); plon = np.radians([p['longitude'] for p in P])
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
print('cells', len(pts), 'labels', len(labels))

feat = np.stack([Q[d][mask] for d in DIMS], 1).astype(np.uint8)
b64 = lambda a: base64.b64encode(a).decode()
out = dict(nr=NR // 2, nc=NC // 2, dims=DIMS, rng=RNG, targets=TARGETS, labels=labels, known=known,
           mask=b64(np.packbits(mask.ravel()).tobytes()), land=b64(np.packbits(landmask.ravel()).tobytes()),
           feat=b64(feat.tobytes()), lab=b64(lab_of.astype('<u2').tobytes()))
json.dump(out, open(f'{OUT}/data.json', 'w'), ensure_ascii=False)
for nme, la, lo in [('Atacama', -22.17, -69.83), ('Haughton', 75.4, -89.8), ('Kunlun', 35.5, 84.83), ('Sahara', 23, 12), ('Ireland', 53, -8)]:
    i = np.abs(lat2 - la).argmin(); j = np.abs(lon2 - lo).argmin()
    print(nme, mask[i, j], {d: round(float(F_raw[d][i, j]), 3) for d in DIMS})
