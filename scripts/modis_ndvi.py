import sys, glob, numpy as np
from pyhdf.SD import SD, SDC
files = sorted(glob.glob(sys.argv[1] + '/*MOD13C2_A2023*.hdf')); out = sys.argv[2]; print(len(files), 'files')
s = np.zeros((3600, 7200)); n = np.zeros((3600, 7200))
for f in files:
    h = SD(f, SDC.READ)
    if f == files[0]:
        print(list(h.datasets())[:4]); a = h.select('CMG 0.05 Deg Monthly NDVI').attributes(); print({k: a[k] for k in ('scale_factor', '_FillValue', 'valid_range')})
    v = h.select('CMG 0.05 Deg Monthly NDVI')[:].astype(float)
    ok = v >= -2000
    s += np.where(ok, v / 10000.0, 0); n += ok
nd = np.where(n >= 6, s / np.maximum(n, 1), np.nan)
r = np.floor((np.arange(3600) + .5) * 0.05 * 6).astype(int); c = np.floor((np.arange(7200) + .5) * 0.05 * 6).astype(int)
idx = (r[:, None] * 2160 + c[None, :]).ravel(); v = nd.ravel(); ok = ~np.isnan(v)
sm = np.bincount(idx[ok], v[ok], 1080 * 2160); k = np.bincount(idx[ok], minlength=1080 * 2160)
N = np.where(k > 0, sm / np.maximum(k, 1), np.nan).reshape(1080, 2160); np.savez_compressed(out + '/modis_ndvi.npz', a=N.astype('float32'))
lat = 90 - (np.arange(1080) + .5) / 6; lon = -180 + (np.arange(2160) + .5) / 6
for nme, la, lo in [('Atacama', -24.1, -69.9), ('Haughton', 75.4, -89.8), ('Kunlun', 35.83, 88.5), ('Sahara', 23, 12), ('Amazon', -3, -60), ('Stuttgart', 48.8, 9.2), ('Dry Valleys', -77.5, 162)]:
    i = np.abs(lat - la).argmin(); j = np.abs(lon - lo).argmin(); print(nme, round(float(N[i, j]), 3))
