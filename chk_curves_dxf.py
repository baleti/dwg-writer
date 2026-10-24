"""chk_curves_dxf.py STEM : ELLIPSE (center, major axis, ratio), SPLINE (degree, knot and control point counts) and SOLID (4 corners) of Model.entities() vs AutoCAD's drawing.dxf, per handle."""
import sys, collections, dwgmodel
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
    elif c == '5' and cur is None and ctype in ('ELLIPSE', 'SPLINE', 'SOLID'): cur = {'t': ctype, 'g': collections.defaultdict(list)}; ent[int(v, 16)] = cur
    elif cur is not None:
        try: cur['g'][c].append(float(v))
        except ValueError: pass
close = lambda a, b: abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
c = collections.Counter(); ex = {}
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] != d['t']: continue
    g = d['g']; k = e['kind']
    if k == 'ELLIPSE':
        ok = close(e['center'][0], g['10'][0]) and close(e['center'][1], g['20'][0]) and close(e['major'][0], g['11'][0]) and close(e['major'][1], g['21'][0]) and close(e['ratio'], g['40'][0])
    elif k == 'SPLINE':
        ok = int(e.get('degree', -1)) == int(g['71'][0]) and len(e.get('ctrl') or []) == int(g['73'][0] if '73' in g else 0) and len(e.get('knots') or []) == int(g['72'][0] if '72' in g else 0)
    else:
        pts = e['pts']; xs = [g.get(x, [None])[0] for x in ('10', '11', '12', '13')]; ys = [g.get(x, [None])[0] for x in ('20', '21', '22', '23')]
        ok = all(a is not None and close(p[0], a) and close(p[1], b) for p, a, b in zip(pts, xs, ys))
    c[(k, ok)] += 1
    if not ok: ex.setdefault(k, hex(e['handle']))
print(stem, sorted(c.items()), ex)
