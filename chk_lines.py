import sys, dwgload, dwgent
def dxf_lines(path):
    s=set(); cur=None
    L=open(path,errors='replace').read().split('\n')
    sec=None
    for i in range(0,len(L)-1,2):
        g,v=L[i].strip(),L[i+1].strip()
        if g=='0':
            if cur and cur.get('t')=='LINE' and sec=='ENTITIES': s.add(tuple(round(cur.get(k,0.0),3) for k in('10','20','11','21')))
            cur={'t':v}
            if v=='SECTION': sec=None
        elif g=='2' and cur and cur.get('t')=='SECTION': sec=v
        elif cur is not None and g in('10','20','11','21'):
            try: cur[g]=float(v)
            except: pass
    return s
d=dwgload.load(open(sys.argv[1],'rb').read())
mine=set(); n=0; err=0
for o in d['objects'].values():
    if o.type==19:
        try:
            e=dwgent.decode_line(o); n+=1
            mine.add((round(e['p1'][0],3),round(e['p1'][1],3),round(e['p2'][0],3),round(e['p2'][1],3)))
        except Exception: err+=1
dx=dxf_lines(sys.argv[2])
print(n,err,len(mine),len(dx),len(mine&dx))
