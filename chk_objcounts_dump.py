"""chk_objcounts_dump.py FILE.dwg DUMP.json : object counts per DXF class name (Model.objs types mapped to names) vs dump.json object_counts; prints keys that differ."""
import sys, json, collections, dwgmodel
FIXED = {1: 'TEXT', 2: 'ATTRIB', 3: 'ATTDEF', 4: 'BLOCK', 5: 'ENDBLK', 6: 'SEQEND', 7: 'INSERT', 8: 'INSERT', 10: 'VERTEX', 11: 'VERTEX', 12: 'VERTEX', 13: 'VERTEX', 14: 'VERTEX', 15: 'POLYLINE', 16: 'POLYLINE',
         17: 'ARC', 18: 'CIRCLE', 19: 'LINE', 20: 'DIMENSION', 21: 'DIMENSION', 22: 'DIMENSION', 23: 'DIMENSION', 24: 'DIMENSION', 25: 'DIMENSION', 26: 'DIMENSION', 27: 'POINT', 28: '3DFACE', 29: 'POLYLINE',
         30: 'POLYLINE', 31: 'SOLID', 32: 'TRACE', 33: 'SHAPE', 34: 'VIEWPORT', 35: 'ELLIPSE', 36: 'SPLINE', 37: 'REGION', 38: '3DSOLID', 39: 'BODY', 40: 'RAY', 41: 'XLINE', 42: 'DICTIONARY', 44: 'MTEXT',
         45: 'LEADER', 46: 'TOLERANCE', 47: 'MLINE', 48: 'BLOCK_CONTROL', 49: 'BLOCK_RECORD', 50: 'LAYER_CONTROL', 51: 'LAYER', 52: 'STYLE_CONTROL', 53: 'STYLE', 56: 'LTYPE_CONTROL', 57: 'LTYPE',
         60: 'VIEW_CONTROL', 61: 'VIEW', 62: 'UCS_CONTROL', 63: 'UCS', 64: 'VPORT_CONTROL', 65: 'VPORT', 66: 'APPID_CONTROL', 67: 'APPID', 68: 'DIMSTYLE_CONTROL', 69: 'DIMSTYLE', 70: 'VP_ENT_HDR_CONTROL',
         71: 'VP_ENT_HDR', 72: 'GROUP', 73: 'MLINESTYLE', 74: 'OLE2FRAME', 77: 'LWPOLYLINE', 78: 'HATCH', 79: 'XRECORD', 80: 'ACDBPLACEHOLDER', 82: 'LAYOUT'}
d = json.load(open(sys.argv[2])); m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
cm = {c['num']: c['dxf'] for c in m.classes()}
c = collections.Counter()
for o in m.objs.values(): c[FIXED.get(o.type) if o.type < 500 else cm.get(o.type)] += 1
au = d['object_counts']; er = d.get('erased_counts', {}); diff = {}
for k in set(au) | set(c):
    if k is None: continue
    if au.get(k, 0) != c.get(k, 0) - er.get(k, 0): diff[k] = (c.get(k, 0) - er.get(k, 0), au.get(k, 0))  # AutoCAD's counts exclude erased objects
print('classes', len(au), 'differ', len(diff), json.dumps(dict(sorted(diff.items(), key=lambda x: -abs(x[1][0] - x[1][1])))))
