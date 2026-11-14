"""MCD43C3 (one day per month) -> annual mean shortwave albedo on the 10 arcmin grid.
usage: modis_albedo.py FOLDER_WITH_HDF OUT_DIR
Albedo = mean of black-sky and white-sky shortwave albedo. Months with more than 50 % snow in the
pixel are left out where snow-free months exist, so the value describes the ground, not the snow."""
import sys, glob, numpy as np
from pyhdf.SD import SD, SDC
files = sorted(glob.glob(sys.argv[1] + '/*MCD43C3_A*.hdf')); out = sys.argv[2]; print(len(files), 'files')
s_all = np.zeros((3600, 7200), np.float32); n_all = np.zeros((3600, 7200), np.float32)
s_sf = np.zeros((3600, 7200), np.float32); n_sf = np.zeros((3600, 7200), np.float32)
for f in files:
    h = SD(f, SDC.READ)
    if f == files[0]: print([k for k in h.datasets()][:12]); print(h.select('Albedo_WSA_shortwave').attributes())
    b = h.select('Albedo_BSA_shortwave')[:]; w = h.select('Albedo_WSA_shortwave')[:]; sn = h.select('Percent_Snow')[:]
    ok = (b != 32767) & (w != 32767)
    a = np.where(ok, (b.astype(np.float32) + w.astype(np.float32)) / 2 * 0.001, 0)
    s_all += a; n_all += ok
    sf = ok & (sn <= 50); s_sf += np.where(sf, a, 0); n_sf += sf
alb = np.where(n_sf >= 2, s_sf / np.maximum(n_sf, 1), np.where(n_all >= 1, s_all / np.maximum(n_all, 1), np.nan))
r = np.floor((np.arange(3600) + .5) * 0.05 * 6).astype(int); c = np.floor((np.arange(7200) + .5) * 0.05 * 6).astype(int)
idx = (r[:, None] * 2160 + c[None, :]).ravel(); v = alb.ravel(); m = ~np.isnan(v)
sm = np.bincount(idx[m], v[m], 1080 * 2160); k = np.bincount(idx[m], minlength=1080 * 2160)
A = np.where(k > 0, sm / np.maximum(k, 1), np.nan).reshape(1080, 2160).astype('float32')
np.savez_compressed(out + '/modis_albedo.npz', a=A)
lat = 90 - (np.arange(1080) + .5) / 6; lon = -180 + (np.arange(2160) + .5) / 6
for nme, la, lo in [('Atacama', -24.1, -69.9), ('Haughton', 75.4, -89.8), ('Kunlun', 35.5, 84.83), ('Sahara', 23, 12), ('Amazon', -3, -60), ('Stuttgart', 48.8, 9.2), ('Tibesti', 22.17, 19.5), ('Ellesmere', 80.5, -77.83)]:
    i = np.abs(lat - la).argmin(); j = np.abs(lon - lo).argmin(); print(nme, 'albedo', round(float(A[i, j]), 3))
