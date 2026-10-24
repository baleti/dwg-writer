"""chk_r14_counts.py : entity counts per type of Model14 (all blocks) vs the AutoCAD dump, for the local AC1012/AC1014 files."""
import glob, os, json, collections, dwgmodel
MAP = {'POLYLINE2D': 'POLY', 'POLYLINE3D': 'POLY', 'POLYLINE_PFACE': 'POLY', 'POLYLINE_MESH': 'POLY', 'LWPOLYLINE': 'POLY', 'POLYLINE': 'POLY', 'DIM_LINEAR': 'DIMENSION', 'DIM_ALIGNED': 'DIMENSION', 'DIM_ORDINATE': 'DIMENSION', 'DIM_RADIUS': 'DIMENSION', 'DIM_DIAMETER': 'DIMENSION', 'DIM_ANG3PT': 'DIMENSION', 'DIM_ANG2LN': 'DIMENSION'}
for f in sorted(glob.glob('corpus/AC101[24]_*.dwg')):
    stem = os.path.basename(f)[:-4]
    d = 'oracle-out/%s/dump.json' % stem
    if not os.path.exists(d): continue
    m = dwgmodel.Model(open(f, 'rb').read())
    c = collections.Counter()
    for bn, e in m.entities():
        if e['kind'] in ('VERTEX2D', 'VERTEX3D', 'VERTEX_MESH', 'VERTEX_PFACE', 'VERTEX_PFACE_FACE', 'SEQEND', 'ATTRIB'): continue
        c[MAP.get(e['kind'], e['kind'])] += 1
    j = json.load(open(d))
    t = collections.Counter()
    for blk in j['blocks']:
        for e in blk.get('entities', []):
            if e['t'] in ('ATTRIB',): continue
            t[MAP.get(e['t'], e['t'])] += 1
    diff = {k: (c.get(k, 0), t.get(k, 0)) for k in set(c) | set(t) if c.get(k, 0) != t.get(k, 0)}
    print(stem, 'equal' if not diff else diff)
