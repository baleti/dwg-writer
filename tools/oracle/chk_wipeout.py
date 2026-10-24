#!/usr/bin/env python3
"""chk_wipeout.py FILE.dwg : WIPEOUT and IMAGE clip boundary (normalised polygon) by handle, parser vs AutoCAD. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
mine = {e['handle']: e for b, e in m.entities() if e['kind'] in ('WIPEOUT', 'IMAGE')}
def close(a, b): return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
res = collections.Counter(); first = {}
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] not in ('WIPEOUT', 'IMAGE') or not isinstance(e['h'], str) or 'clip' not in e: continue
        o = mine.get(int(e['h'], 16))
        if o is None: res['missing'] += 1; continue
        a, c = o['clip'], e['clip']
        if len(c) == len(a) + 1 and tuple(c[0]) == tuple(c[-1]): c = c[:-1]
        if len(a) == len(c) + 1 and tuple(a[0]) == tuple(a[-1]): a = a[:-1]
        ok = len(a) == len(c) and all(close(u[0], v[0]) and close(u[1], v[1]) for u, v in zip(a, c))
        res['ok' if ok else 'bad'] += 1
        if not ok: first.setdefault(e['t'], (e['h'], len(a), len(c)))
print(json.dumps({'res': dict(res), 'first': first}))
