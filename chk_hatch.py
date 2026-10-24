import sys, collections, dwgmodel
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
L = open(sys.argv[2], errors='replace').read().split('\n')
dx = []; cur = None; sec = None
def fin():
    if cur and cur.get('t') == 'HATCH' and sec in ('ENTITIES', 'BLOCKS'):
        dx.append((cur.get('2', ''), cur.get('70'), cur.get('91')))
for i in range(0, len(L) - 1, 2):
    g, v = L[i].strip(), L[i + 1].strip()
    if g == '0':
        fin(); cur = {'t': v}
        if v == 'SECTION': sec = None
    elif g == '2' and cur and cur['t'] == 'SECTION': sec = v
    elif cur is not None and cur['t'] == 'HATCH' and g in ('2', '70', '91'): cur.setdefault(g, v)
fin()
mine = [(e['pattern_name'], str(e['solid']), str(len(e['paths']))) for b, e in m.entities() if e['kind'] == 'HATCH']
cd = collections.Counter(dx); cm = collections.Counter(mine)
print('hatch mine', len(mine), 'oracle', len(dx), 'multiset equal', cd == cm)
print(list((cd - cm).items())[:3], list((cm - cd).items())[:3])
