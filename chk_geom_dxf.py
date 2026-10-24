"""chk_geom_dxf.py STEM : first point (group 10/20) and radius/height/rotation of Model.entities() vs AutoCAD's drawing.dxf, per handle, for LINE CIRCLE ARC TEXT MTEXT INSERT POINT."""
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
    if c == '0': ctype = v; cur = None; hnd = None
    elif c == '5' and cur is None and ctype not in ('BLOCK', 'ENDBLK'): cur = {'t': ctype}; ent[int(v, 16)] = cur
    elif cur is not None:
        try: f = float(v)
        except ValueError: continue
        if c in ('10', '20', '40', '50', '11', '21') and c not in cur: cur[c] = f
KEY = {'LINE': 'p1', 'CIRCLE': 'center', 'ARC': 'center', 'TEXT': 'ins', 'INSERT': 'ins', 'POINT': 'p', 'MTEXT': 'ins'}
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
c = collections.Counter(); ex = {}
close = lambda a, b: abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
for bn, e in m.entities():
    d = ent.get(e['handle'])
    k = e['kind']
    if d is None or k not in KEY or d['t'] != k or '10' not in d: continue
    p = e.get(KEY[k])
    if p is None: continue
    # DXF gives OCS coordinates: compare as stored (x, y), flipped x for extrusion (0,0,-1)
    x = p[0]; ext = e.get('ext') or (0, 0, 1)
    ok = (close(x, d['10']) or (ext[2] < 0 and close(-x, d['10']))) and close(p[1], d['20'])
    if k in ('CIRCLE', 'ARC'): ok = ok and close(e['radius'], d.get('40', e['radius']))
    c[(k, ok)] += 1
    if not ok: ex.setdefault(k, (hex(e['handle']), p[:2], d['10'], d['20']))
print(stem, sorted(c.items()), ex)
