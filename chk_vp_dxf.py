"""chk_vp_dxf.py STEM : VIEWPORT centre (10/20), width (40), height (41), view height (45), view centre (12/22) and twist (51) of Model.entities() vs AutoCAD's drawing.dxf, per handle."""
import sys, math, collections, dwgmodel
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
    elif c == '5' and cur is None and ctype == 'VIEWPORT': cur = {}; ent[int(v, 16)] = cur
    elif cur is not None:
        try:
            if c in ('10', '20', '40', '41', '45', '12', '22', '51') and c not in cur: cur[c] = float(v)
        except ValueError: pass
close = lambda a, b: abs(a - b) <= 1e-5 * max(1.0, abs(a), abs(b))
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
c = collections.Counter(); ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] != 'VIEWPORT': continue
    chk = {'center': close(e['center'][0], d.get('10', e['center'][0])) and close(e['center'][1], d.get('20', e['center'][1])),
           'size': close(e['width'], d.get('40', e['width'])) and close(e['height'], d.get('41', e['height'])),
           'viewh': close(e['view_height'], d.get('45', e['view_height'])),
           'viewc': close(e['view_center'][0], d.get('12', e['view_center'][0])) and close(e['view_center'][1], d.get('22', e['view_center'][1])),
           'twist': close(math.sin(e['twist']), math.sin(math.radians(d.get('51', 0.0)))) and close(math.cos(e['twist']), math.cos(math.radians(d.get('51', 0.0))))}
    for k, v in chk.items(): c[(k, v)] += 1
    if not all(chk.values()) and len(ex) < 2: ex.append((hex(e['handle']), [k for k, v in chk.items() if not v]))
print(stem, 'viewports', sum(1 for _ in [1]) and sum(v for (k, ok), v in c.items() if k == 'center'), {k: sum(v for (kk, ok), v in c.items() if kk == k and ok) for k in ('center', 'size', 'viewh', 'viewc', 'twist')}, ex)
