#!/usr/bin/env python3
"""chk_hatch.py FILE.dwg : HATCH entities by handle, parser vs AutoCAD dump: pattern, solid, assoc, scale/angle (non-solid), loop count, per-loop segment count, and boundary vertices inside the oracle extents. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
mine = {e['handle']: e for b, e in m.entities() if e['kind'] == 'HATCH'}
def close(a, b): return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
res = collections.Counter(); first = {}
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] != 'HATCH' or not isinstance(e['h'], str): continue
        o = mine.get(int(e['h'], 16))
        if o is None: res['missing'] += 1; continue
        errs = []
        if o['pattern_name'].upper() != e['pattern'].upper(): errs.append('pattern')
        if bool(o['solid']) != bool(e['solid']): errs.append('solid')
        if bool(o['assoc']) != bool(e['assoc']): errs.append('assoc')
        if not e['solid']:
            if not close(o['pattern_scale'], e['pscale']): errs.append('pscale')
            if not close(o['pattern_angle'], e['pangle']): errs.append('pangle')
        if len(o['paths']) != e['nloops']: errs.append('nloops')
        else:
            for a, l in zip(o['paths'], e['loops']):
                if 'poly' in l:
                    pts = [tuple(s[1][:2]) if s[0] == 'P' and len(s) > 1 and isinstance(s[1], tuple) else None for s in a['segs']]
                    if any(x is None for x in pts): continue  # unknown segment layout
                    q = [tuple(v[:2]) for v in l['poly']]
                    if len(q) == len(pts) + 1 and q[0] == q[-1]: q = q[:-1]
                    if len(q) != len(pts) or not all(close(u[0], v[0]) and close(u[1], v[1]) for u, v in zip(pts, q)): errs.append('poly')
                elif len(a['segs']) != len(l.get('curves', [])): errs.append('nsegs')
        x0, y0, _, x1, y1, _ = e['ext']
        tol = 1e-6 * max(1.0, abs(x1 - x0), abs(y1 - y0))
        for path in o['paths']:
            for s in path['segs']:
                for pt in (s[1:3] if s[0] == 'L' else ()):
                    if not (isinstance(pt, tuple) and len(pt) == 2): continue
                    if pt[0] < x0 - tol or pt[0] > x1 + tol or pt[1] < y0 - tol or pt[1] > y1 + tol: errs.append('outside'); break
        for x in set(errs): res[x] += 1; first.setdefault(x, e['h'])
        res['ok' if not errs else 'bad'] += 1
print(json.dumps({'res': dict(res), 'first': first}))
