#!/usr/bin/env python3
"""chk_header.py FILE.dwg : header variables with the same (case-insensitive) name in parser and AutoCAD dump; prints overlap size and mismatches as JSON. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
h = m.header() if callable(m.header) else m.header
o = {k.lower(): v for k, v in d['header'].items()}
bad = {}; n = 0
for k, v in h.items():
    w = o.get(k.lower())
    if w is None: continue
    if isinstance(v, (int, float)) and isinstance(w, (int, float)) and not isinstance(w, bool):
        n += 1
        if abs(v - w) > 1e-6 * max(1.0, abs(v), abs(w)): bad[k] = (v, w)
    elif isinstance(w, bool) and isinstance(v, (int, bool)):
        n += 1
        if bool(v) != w: bad[k] = (v, w)
    elif isinstance(v, str) and isinstance(w, str):
        n += 1
        if v.lower() != w.lower(): bad[k] = (v, w)
print(json.dumps({'n': n, 'bad': bad}))
