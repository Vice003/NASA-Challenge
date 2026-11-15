"""Mars dust target values from the PDS TES dust maps -> data/mars_dust_targets.json and .csv

usage: mars_dust_targets.py FOLDER_WITH_DAT planetary/targets.json OUT_DIR

Source: NASA PDS Atmospheres Node, bundle mgs_tes_atmos_dust-ice, collection data_IR_Dust_Optical_Depth_Maps
(Montabone, Smith, Wolff, Cantor 2023, doi 10.17189/kwez-jq47): daily maps of column dust optical depth,
9.3 micron absorption, 6 deg lon x 3 deg lat, Mars years 24-27. Here: every tenth sol.
Value per site = median over all sols of CDODTOT (total column above the local surface) in the grid cell
nearest to the site. body_percentile = area-weighted rank of that value on the map of per-cell medians."""
import sys, glob, json, csv, re, warnings
import numpy as np
warnings.filterwarnings('ignore', 'All-NaN slice')
sys.path.insert(0, '.')
from common.body_percentile import body_percentile, latlon_weights
folder, targets_file, out = sys.argv[1:4]
files = sorted(glob.glob(folder + '/**/TES_CDODMAP_IR_MY*_SOY*.dat', recursive=True))
my = np.array([int(re.search(r'MY(\d+)_SOY(\d+)', f).group(1)) for f in files])
soy = np.array([int(re.search(r'MY(\d+)_SOY(\d+)', f).group(2)) for f in files])
tot = np.full((len(files), 60, 60), np.nan); c610 = tot.copy()
for n, f in enumerate(files):
    a = np.loadtxt(f, skiprows=1)                       # LON LAT CDODNUM CDODTW CDODREL CDOD610 ... CDODTOT CDODTOTUNC
    if n == 0: lon = a[:60, 0]; lat = a[::60, 1]
    tot[n] = np.where(a[:, 8] > -900, a[:, 8], np.nan).reshape(60, 60)
    c610[n] = np.where(a[:, 5] > -900, a[:, 5], np.nan).reshape(60, 60)
assert lat[0] > lat[-1] and lon[0] == -180
nvalid = np.isfinite(tot).sum(0)
clim = np.where(nvalid >= 20, np.nanmedian(tot, 0), np.nan)        # per-cell median over all sols
clim_no25 = np.where(np.isfinite(tot[my != 25]).sum(0) >= 15, np.nanmedian(tot[my != 25], 0), np.nan)
w = latlon_weights(60)
print(f'{len(files)} maps, MY {my.min()}-{my.max()}; cells with a climatology: {np.isfinite(clim).mean() * 100:.0f} %')
print(f'Across all Mars grid cells: median {np.nanmedian(clim):.3f}, p10 {np.nanpercentile(clim, 10):.3f}, p90 {np.nanpercentile(clim, 90):.3f}')

T = json.load(open(targets_file))['targets']
items = T.items() if isinstance(T, dict) else [(x['id'], x) for x in T]
SRC = ('TES column dust optical depth maps, NASA PDS Atmospheres Node, bundle mgs_tes_atmos_dust-ice '
       '(Montabone, Smith, Wolff, Cantor 2023, doi:10.17189/kwez-jq47)')
r = lambda x: None if x is None or not np.isfinite(x) else float(f'{x:.4g}')
res, rows = {}, []
for tid, v in items:
    if str(v.get('body', '')).lower() != 'mars': continue
    la, lo = v['center_lat'], ((v['center_lon'] + 180) % 360) - 180
    i = int(np.abs(lat - la).argmin()); j = int(np.abs(((lon - lo + 180) % 360) - 180).argmin())
    s = tot[:, i, j]; ok = np.isfinite(s)
    if ok.sum() < 20:
        res[tid] = dict(value=None, notes=f'only {int(ok.sum())} valid sols in the TES grid cell'); continue
    med, p10, p90 = np.median(s[ok]), np.percentile(s[ok], 10), np.percentile(s[ok], 90)
    med_no25 = np.median(s[ok & (my != 25)]); bp = body_percentile(clim, w, med)
    res[tid] = dict(value=r(med), p10=r(p10), p90=r(p90), unit='1', pixel_m=178000, body_percentile=r(bp),
                    source=SRC, reliability='B',
                    notes=(f'9.3 micron absorption optical depth, total column (CDODTOT); median of {int(ok.sum())} sols '
                           f'(every 10th sol, MY24-27); grid cell 6 x 3 deg centred {lat[i]:.1f} N, {lon[j]:.0f} E, so a regional value; '
                           f'median without MY25 (global dust storm) {med_no25:.3g}; normalised to 610 Pa: {np.nanmedian(c610[:, i, j]):.3g}; '
                           'x 2.6 gives an equivalent visible optical depth; compare with Earth by rank only'))
    rows.append([tid, v['name'], la, v['center_lon'], r(med), r(p10), r(p90), r(med_no25), r(np.nanmedian(c610[:, i, j])), r(bp), int(ok.sum()), f'{lat[i]:.1f}', f'{lon[j]:.0f}'])
json.dump(dict(feature='dust_opacity', method='quantile', generated_by='scripts/mars_dust_targets.py', targets=res),
          open(out + '/mars_dust_targets.json', 'w'), indent=1, ensure_ascii=False)
hdr = ['id', 'name', 'lat', 'lon_e', 'dust_opacity_median', 'p10', 'p90', 'median_without_MY25', 'median_cdod610', 'mars_percentile', 'valid_sols', 'cell_lat', 'cell_lon']
csv.writer(open(out + '/mars_dust_targets.csv', 'w', newline='')).writerows([hdr] + rows)
print(f"{'site':22s} {'median':>7s} {'p10':>6s} {'p90':>6s} {'noMY25':>7s} {'at610Pa':>8s} {'Mars pct':>9s} {'sols':>5s}  cell")
for x in rows: print(f'{x[0]:22s} {x[4]:7.3f} {x[5]:6.3f} {x[6]:6.3f} {x[7]:7.3f} {x[8]:8.3f} {x[9] * 100:8.0f}% {x[10]:5d}  {x[11]}N {x[12]}E')
