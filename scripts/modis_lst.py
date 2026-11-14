import sys, glob, numpy as np
from pyhdf.SD import SD, SDC
files = sorted(glob.glob(sys.argv[1] + '/*MOD11C3_A2023*.hdf')); out = sys.argv[2]
sd = np.zeros((3600, 7200)); sn = np.zeros((3600, 7200)); n = np.zeros((3600, 7200)); sdy = np.zeros((3600, 7200))
for f in files:
    h = SD(f, SDC.READ)
    if f == files[0]: print(list(h.datasets())[:6], h.select('LST_Day_CMG').attributes())
    d = h.select('LST_Day_CMG')[:].astype(float) * 0.02; nt = h.select('LST_Night_CMG')[:].astype(float) * 0.02
    ok = (d > 0) & (nt > 0)
    sd += np.where(ok, d - nt, 0); sdy += np.where(ok, (d + nt) / 2, 0); n += ok
    print(f.split('_A2023')[1][:3], 'valid share', round(ok.mean(), 3))
dtr = np.where(n >= 6, sd / np.maximum(n, 1), np.nan); mean = np.where(n >= 6, sdy / np.maximum(n, 1), np.nan)
# bin 0.05 deg pixels into the 10 arcmin grid (1080 x 2160)
r = np.floor((np.arange(3600) + .5) * 0.05 * 6).astype(int); c = np.floor((np.arange(7200) + .5) * 0.05 * 6).astype(int)
idx = (r[:, None] * 2160 + c[None, :]).ravel()
def binmean(a):
    v = a.ravel(); ok = ~np.isnan(v)
    s = np.bincount(idx[ok], v[ok], 1080 * 2160); k = np.bincount(idx[ok], minlength=1080 * 2160)
    return np.where(k > 0, s / np.maximum(k, 1), np.nan).reshape(1080, 2160)
D = binmean(dtr); M = binmean(mean)
np.savez_compressed(out + '/modis_dtr.npz', a=D.astype('float32'))
lat = 90 - (np.arange(1080) + .5) / 6; lon = -180 + (np.arange(2160) + .5) / 6
for nme, la, lo in [('Atacama', -24.1, -69.9), ('Haughton', 75.4, -89.8), ('Kunlun', 35.83, 88.5), ('Sahara', 23, 12), ('Amazon', -3, -60), ('Stuttgart', 48.8, 9.2), ('Tibesti', 21, 17.5)]:
    i = np.abs(lat - la).argmin(); j = np.abs(lon - lo).argmin(); print(nme, 'DTR', round(D[i, j], 1), 'K, mean LST', round(M[i, j] - 273.15, 1), 'C')
print('global land DTR percentiles', np.nanpercentile(D, [2, 50, 98, 99.9]))
