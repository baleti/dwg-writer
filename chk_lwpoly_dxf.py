"""chk_lwpoly_dxf.py STEM : LWPOLYLINE vertex count, vertices (10/20), bulges (42) and closed flag (70) of Model.entities() vs AutoCAD's drawing.dxf, per handle."""
import sys, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].strip()) for i in range(0, len(L) - 1, 2)]
sec = None; want = False; ctype = None; ent = {}; cur = None
for c, v in pairs:
    if c == '0' and v == 'SECTION': sec = None; want = True; continue
    if c == '2' and want: sec = v; want = False; continue
    if c == '0' and v == 'ENDSEC': sec = None; continue
    if sec not in ('BLOCKS', 'ENTITIES'): continue
    if c == '0': ctype = v; cur = None
    elif c == '5' and cur is None and ctype == 'LWPOLYLINE': cur = {'v': [], 'cl': 0}; ent[int(v, 16)] = cur
    elif cur is not None:
        try:
            if c == '10': cur['v'].append([float(v), None, 0.0])
            elif c == '20' and cur['v']: cur['v'][-1][1] = float(v)
            elif c == '42' and cur['v']: cur['v'][-1][2] = float(v)
            elif c == '70': cur['cl'] = int(v) & 1
        except ValueError: pass
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
close = lambda a, b: abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
n = cok = vok = 0; ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] != 'LWPOLYLINE': continue
    n += 1
    pts = e.get('pts') or e.get('vertices') or []
    bul = e.get('bulges') or [0.0] * len(pts)
    good = len(pts) == len(d['v']) and all(close(p[0], q[0]) and close(p[1], q[1]) for p, q in zip(pts, d['v'])) and all(close(b or 0.0, q[2]) for b, q in zip(bul, d['v']))
    vok += good
    cok += int(bool(e.get('closed'))) == d['cl']
    if not good and len(ex) < 2: ex.append((hex(e['handle']), len(pts), len(d['v'])))
print(stem, 'lwpolylines', n, 'vertices+bulges equal', vok, 'closed equal', cok, ex)
