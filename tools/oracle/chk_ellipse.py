#!/usr/bin/env python3
"""chk_ellipse.py FILE.dwg : ELLIPSE by handle, parser vs AutoCAD (centre, major axis, ratio, start/end parameter). Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
mine = {e['handle']: e for b, e in m.entities() if e['kind'] == 'ELLIPSE'}
def close(a, b): return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
res = collections.Counter(); first = {}
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] != 'ELLIPSE' or not isinstance(e['h'], str): continue
        o = mine.get(int(e['h'], 16))
        if o is None: res['missing'] += 1; continue
        errs = []
        if not all(close(a, c) for a, c in zip(e['c'], o['center'])): errs.append('center')
        if not all(close(a, c) for a, c in zip(e['maj'], o['major'])): errs.append('major')
        if not close(e['ratio'], o['ratio']): errs.append('ratio')
        if not (close(e['p0'], o['a0']) and close(e['p1'], o['a1'])): errs.append('params')
        for x in errs: res[x] += 1; first.setdefault(x, (e['h'], e['c'], o['center']))
        res['ok' if not errs else 'bad'] += 1
print(json.dumps({'res': dict(res), 'first': first}))
