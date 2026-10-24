#!/usr/bin/env python3
"""objcmp.py FILE.dwg : per-class OBJECT counts of the parser's object map (Model.objs, fixed types by number, class-based types through the class list)
against the AutoCAD dump object_counts. Differences mean objects absent from the map (loader problem), not decode failures. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
FIXED = {1: 'TEXT', 2: 'ATTRIB', 3: 'ATTDEF', 4: 'BLOCK', 5: 'ENDBLK', 6: 'SEQEND', 7: 'INSERT', 8: 'INSERT', 10: 'VERTEX', 11: 'VERTEX', 12: 'VERTEX', 13: 'VERTEX', 14: 'VERTEX',
         15: 'POLYLINE', 16: 'POLYLINE', 17: 'ARC', 18: 'CIRCLE', 19: 'LINE', 20: 'DIMENSION', 21: 'DIMENSION', 22: 'DIMENSION', 23: 'DIMENSION', 24: 'DIMENSION', 25: 'DIMENSION', 26: 'DIMENSION',
         27: 'POINT', 28: '3DFACE', 29: 'POLYLINE', 30: 'POLYLINE', 31: 'SOLID', 32: 'TRACE', 33: 'SHAPE', 34: 'VIEWPORT', 35: 'ELLIPSE', 36: 'SPLINE', 37: 'REGION', 38: '3DSOLID', 39: 'BODY',
         40: 'RAY', 41: 'XLINE', 42: 'DICTIONARY', 44: 'MTEXT', 45: 'LEADER', 46: 'TOLERANCE', 47: 'MLINE', 49: 'BLOCK_RECORD', 51: 'LAYER', 53: 'STYLE', 57: 'LTYPE', 61: 'VIEW', 63: 'UCS',
         65: 'VPORT', 67: 'APPID', 69: 'DIMSTYLE', 72: 'GROUP', 73: 'MLINESTYLE', 77: 'LWPOLYLINE', 78: 'HATCH', 79: 'XRECORD', 80: 'ACDBPLACEHOLDER', 82: 'LAYOUT'}
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
cl = {c['num']: c['dxf'] for c in m.classes()}
per = {c['num']: c for c in m.classes()}
ours = collections.Counter()
for o in m.objs.values():
    k = FIXED.get(o.type) if o.type < 500 else cl.get(o.type)
    if k and o.type >= 500 and k not in d['object_counts'] and per[o.type]['proxy']: k = 'ACAD_PROXY_OBJECT'  # custom classes AutoCAD cannot load are proxies
    if k: ours[k] += 1
ora = collections.Counter(d['object_counts'])
rows = [(k, ours[k], ora[k]) for k in sorted(set(ours) | set(ora)) if ours[k] != ora[k]]
print(json.dumps({'map_total': len(m.objs), 'ours_total': sum(ours.values()), 'oracle_total': sum(ora.values()), 'diff': {k: [a, b] for k, a, b in rows}}))
