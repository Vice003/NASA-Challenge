import sys, json, numpy as np
O=sys.argv[1]
d=json.load(open(f'{O}/data.json')); z=np.load(f'{O}/check.npz')
mask=z['mask']; feat=z['feat'].astype(float); ii,jj=np.where(mask); lat=z['lat2'][ii]; lon=z['lon2'][jj]; lab=z['lab']
dims=d['dims']; w_area=np.cos(np.radians(lat))
KNOWN=[('Atacama (Yungay)',-24.1,-69.9),('Haughton, Devon Island',75.4,-89.8),('McMurdo Dry Valleys',-77.5,162.0),('Askja, Island',65.05,-16.75),('Mauna Loa (HI-SEAS)',19.6,-155.5),('MDRS, Utah',38.4,-110.8),('Death Valley',36.5,-117.0),('Rio Tinto',37.7,-6.55),('Svalbard (AMASE)',79.0,14.0),('Pilbara',-21.5,119.0),('Danakil',14.24,40.3),('Qaidam',37.5,94.0),('Lanzarote',29.0,-13.7),('Negev (Ramon)',30.6,34.8),('Namib',-24.5,15.5),('Flagstaff/SP Crater',35.4,-111.5),('Erfoud, Marokko',31.4,-4.2)]
def dist(la,lo,LA,LO):
    a,b,c,e=map(np.radians,(la,lo,LA,LO)); return 6371*np.arccos(np.clip(np.sin(a)*np.sin(c)+np.cos(a)*np.cos(c)*np.cos(e-b),-1,1))
for t in d['targets']:
    S=np.zeros((len(lat),len(dims)))
    for n,dm in enumerate(dims):
        lo_,hi_=d['rng'][dm]; v=lo_+feat[:,n]/255*(hi_-lo_)
        S[:,n]=np.clip(1-np.abs(v-t['f'][dm])/t['span'][dm],0,1)
    tot=S.mean(1)
    print('\n=====',t['name'],'| best possible per dim:',{dm:round(float(S[:,n].max()),2) for n,dm in enumerate(dims)})
    order=np.argsort(-tot); picked=[]
    for o in order:
        if all(dist(lat[o],lon[o],lat[p],lon[p])>500 for p in picked):
            picked.append(o)
            print(f"{tot[o]*100:5.1f} {lat[o]:7.2f} {lon[o]:8.2f} {d['labels'][lab[o]][:50]:50s}", ' '.join(f"{x*100:3.0f}" for x in S[o]))
        if len(picked)>=12: break
    cw_o=np.argsort(tot); cw=np.cumsum(w_area[cw_o]); cw/=cw[-1]; pct=np.empty(len(tot)); pct[cw_o]=cw
    print('known:', ', '.join(f"{n.split(',')[0].split(' (')[0]} {pct[np.argmin(dist(la,lo,lat,lon))]*100:.0f}% ({dist(la,lo,lat,lon).min():.0f}km)" for n,la,lo in KNOWN))
