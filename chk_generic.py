"""chk_generic.py file.dwg file.dxf KIND  : compares decoded entities of KIND with the oracle DXF (BLOCKS+ENTITIES), as sets of rounded tuples."""
import sys, dwgmodel
SPEC = {
    'ELLIPSE': (('10', '20', '11', '21', '40', '41', '42'), lambda e: (e['center'][0], e['center'][1], e['major'][0], e['major'][1], e['ratio'], e['a0'], e['a1'])),
    'POINT': (('10', '20', '30'), lambda e: tuple(e['p'])),
    'SOLID': (('10', '20', '11', '21'), lambda e: (e['pts'][0][0], e['pts'][0][1], e['pts'][1][0], e['pts'][1][1])),
    'VIEWPORT': (('10', '20', '40', '41', '45'), lambda e: (e['center'][0], e['center'][1], e['width'], e['height'], e['view_height'])),
    'SPLINE': (('10', '20', '71', '73', '74'), lambda e: (e['ctrl'][0][0], e['ctrl'][0][1], e['degree'], len(e['ctrl']), len(e['fit'])) if e['ctrl'] else (e['fit'][0][0], e['fit'][0][1], e['degree'], 0, len(e['fit']))),
}
kind = sys.argv[3]
codes, fn = SPEC[kind]
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
L = open(sys.argv[2], errors='replace').read().split('\n')
dx = []; cur = None; sec = None
def fin():
    if cur and cur.get('t') == kind and sec in ('ENTITIES', 'BLOCKS'):
        dx.append(tuple(round(cur.get(c, 0.0), 3) for c in codes))
for i in range(0, len(L) - 1, 2):
    g, v = L[i].strip(), L[i + 1].strip()
    if g == '0':
        fin(); cur = {'t': v}
        if v == 'SECTION': sec = None
    elif g == '2' and cur and cur['t'] == 'SECTION': sec = v
    elif cur is not None and g in codes:
        try: cur.setdefault(g, float(v))
        except ValueError: pass
fin()
mine = [tuple(round(x, 3) for x in fn(e)) for b, e in m.entities() if e['kind'] == kind]
sd, sm = set(dx), set(mine)
print(kind, 'mine', len(mine), 'oracle', len(dx), 'oracle found', len(sd & sm), 'mine found', len(sm & sd))
print(sorted(sd - sm)[:2], sorted(sm - sd)[:2])
