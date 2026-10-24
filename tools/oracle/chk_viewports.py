#!/usr/bin/env python3
"""chk_viewports.py FILE.dwg : VIEWPORT entities, parser vs AutoCAD dump (matched by paper centre/size; oracle 'h' is height, not handle).
Compares view_center, view_height, scale (=height/view_height), view_dir, twist, frozen-layer count. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
def k(c, w, h): return (round(c[0], 3), round(c[1], 3), round(w, 3), round(h, 3))
ora = {}
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] == 'VIEWPORT': ora.setdefault(k(e['c'], e['w'], e['h']), []).append(e)
def close(a, b): return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
res = collections.Counter(); bad = []
for b, e in m.entities():
    if e['kind'] != 'VIEWPORT': continue
    o = ora.get(k(e['center'], e['width'], e['height']))
    if not o: res['unmatched'] += 1; bad.append(('unmatched', e['handle'])); continue
    o = o.pop(0)
    errs = []
    if not (close(e['view_center'][0], o['vc'][0]) and close(e['view_center'][1], o['vc'][1])): errs.append('view_center')
    if not close(e['view_height'], o['vh']): errs.append('view_height')
    if not all(close(a, c) for a, c in zip(e['view_dir'], o['vd'])): errs.append('view_dir')
    if not close(e['twist'], o['twist']): errs.append('twist')
    if e['nfrozen'] != len(o['frozen']): errs.append('nfrozen')
    for x in errs: res[x] += 1; bad.append((x, e['handle']))
    res['ok' if not errs else 'bad'] += 1
print(dict(res), bad[:5])
