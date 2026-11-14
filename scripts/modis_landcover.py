"""MCD12C1 (IGBP, Type 1) -> share of each 10 arcmin cell covered by classes the plan filters out.
usage: modis_landcover.py FOLDER_WITH_HDF OUT_DIR
excluded = water (0) + forests (1-5) + croplands (12) + urban (13) + cropland/natural mosaic (14)
also written: share of permanent snow and ice (15) and of barren land (16)."""
import sys, glob, numpy as np
from pyhdf.SD import SD, SDC
f = sorted(glob.glob(sys.argv[1] + '/*MCD12C1*.hdf'))[0]; out = sys.argv[2]
p = SD(f, SDC.READ).select('Land_Cover_Type_1_Percent')[:]            # (3600, 7200, 17), percent
ok = p[..., 0] <= 100                                                 # 255 = fill
excl = p[..., [0, 1, 2, 3, 4, 5, 12, 13, 14]].astype(np.float32).sum(-1) / 100
snow = p[..., 15].astype(np.float32) / 100; barren = p[..., 16].astype(np.float32) / 100
r = np.floor((np.arange(3600) + .5) * 0.05 * 6).astype(int); c = np.floor((np.arange(7200) + .5) * 0.05 * 6).astype(int)
idx = (r[:, None] * 2160 + c[None, :]).ravel(); m = ok.ravel()
def binmean(a):
    s = np.bincount(idx[m], a.ravel()[m], 1080 * 2160); k = np.bincount(idx[m], minlength=1080 * 2160)
    return np.where(k > 0, s / np.maximum(k, 1), np.nan).reshape(1080, 2160).astype('float32')
E, S, B = binmean(excl), binmean(snow), binmean(barren)
np.savez_compressed(out + '/modis_landcover.npz', excluded=E, snow=S, barren=B)
lat = 90 - (np.arange(1080) + .5) / 6; lon = -180 + (np.arange(2160) + .5) / 6
for nme, la, lo in [('Atacama', -24.1, -69.9), ('Haughton', 75.4, -89.8), ('Kunlun', 35.83, 88.5), ('Amazon', -3, -60), ('Stuttgart', 48.8, 9.2), ('Greenland ice', 72, -40), ('Dry Valleys', -77.5, 162)]:
    i = np.abs(lat - la).argmin(); j = np.abs(lon - lo).argmin(); print(nme, 'excluded', round(float(E[i, j]), 2), 'snow/ice', round(float(S[i, j]), 2), 'barren', round(float(B[i, j]), 2))
