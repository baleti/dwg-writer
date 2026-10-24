#!/usr/bin/env python3
"""maprange.py FILE.dwg : handle-level object map check. Handles in the AutoCAD dump 'objects' list but absent from Model.objs (missing), and handles in the map that AutoCAD does not list (extra); missing handles are summarised as contiguous runs. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
oh = set()
for o in d['objects']:
    try: oh.add(int(o[0], 16))
    except (ValueError, TypeError): pass
miss = sorted(oh - set(m.objs)); extra = len(set(m.objs) - oh)
runs = []
for h in miss:
    if runs and h == runs[-1][1] + 1: runs[-1][1] = h
    else: runs.append([h, h])
print(json.dumps({'oracle': len(oh), 'map': len(m.objs), 'missing': len(miss), 'extra': extra, 'runs': len(runs), 'max_oracle': max(oh) if oh else 0, 'max_map': max(m.objs) if m.objs else 0, 'first_runs': runs[:4]}))
