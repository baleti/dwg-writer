#!/usr/bin/env python3
"""countcmp.py FILE.dwg : per-type entity count, parser (Model.entities) vs AutoCAD oracle (sum of block entity_counts). Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
ora = collections.Counter()
for b in d['blocks']:
    for k, v in b['entity_counts'].items(): ora[k] += v
m = dwgmodel.Model(open(p, 'rb').read())
def norm(k):
    k = str(k)
    if k.startswith('DIM_'): return 'DIMENSION'
    if k.startswith('POLYLINE'): return 'POLYLINE'
    return k
ours = collections.Counter(norm(e.get('kind')) for b, e in m.entities() if not str(e.get('kind')).startswith(('VERTEX', 'SEQEND', 'ATTRIB')))
ora = collections.Counter({k: v for k, v in ora.items() if not k.startswith(('VERTEX', 'SEQEND', 'ATTRIB'))})
for k in sorted(set(ora) | set(ours), key=str):
    if ora[k] != ours[k]: print(f'{k}\tours {ours[k]}\toracle {ora[k]}')
