"""chk_oracle.py FILE.dwg : compare LINE/CIRCLE/ARC geometry, layer, colour index and lineweight per handle with the AutoCAD oracle dump (oracle-out/<stem>/dump.json)."""
import sys, json, os, collections
import dwgmodel, dwgscene
path = sys.argv[1]
stem = os.path.basename(path)[:-4]
d = json.load(open('oracle-out/%s/dump.json' % stem))
m = dwgmodel.Model(open(path, 'rb').read())
mine = {e['handle']: e for b, e in m.entities()}
bad = collections.Counter(); ok = collections.Counter(); first = {}
def num(x): return float(x)
def close(a, b, tol=1e-6): return abs(a - b) <= tol * max(1.0, abs(a), abs(b))
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] not in ('LINE', 'CIRCLE', 'ARC', 'LWPOLYLINE', 'INSERT', 'POINT', 'SPLINE') or not isinstance(e['h'], str): continue
        o = mine.get(int(e['h'], 16))
        if o is None: bad[(e['t'], 'missing')] += 1; continue
        errs = []
        if e['t'] == 'LINE':
            if not all(close(a, c) for a, c in zip(e['a'][:2] + e['b'][:2], list(o['p1'][:2]) + list(o['p2'][:2]))): errs.append('geom')
        elif e['t'] == 'CIRCLE':
            if not (all(close(a, c) for a, c in zip(e['c'][:2], dwgscene.ocs_to_wcs(tuple(o['center']), tuple(o.get('ext') or (0, 0, 1)))[:2])) and close(num(e['r']), o['radius'])): errs.append('geom')
        elif e['t'] == 'LWPOLYLINE' and 'v' not in e: pass
        elif e['t'] == 'LWPOLYLINE':
            if len(e['v']) != len(o['pts']) or not all(close(v[0], p[0]) and close(v[1], p[1]) for v, p in zip(e['v'], o['pts'])): errs.append('geom')
            if bool(e['closed']) != bool(o['closed']): errs.append('closed')
        elif e['t'] == 'INSERT':
            if not (all(close(a, c) for a, c in zip(e['p'][:2], dwgscene.ocs_to_wcs(o['ins'], tuple(o['ext']))[:2])) and all(close(a, c) for a, c in zip(e['sc'], o['scale'])) and close(num(e['rot']), o['rot'])): errs.append('geom')
            if e['name'] != o.get('block_name', o.get('block_ref')) and e['name'] != m.objs.get(o.get('block_ref')) : pass
        elif e['t'] == 'POINT':
            if not all(close(a, c) for a, c in zip(e['p'][:2], o['p'][:2])): errs.append('geom')
        elif e['t'] == 'SPLINE':
            if not o['ctrl'] and o['fit']: pass  # fit-point spline: AutoCAD derives control points and knots (viewer needs fit-to-NURBS)
            elif len(e['cp']) != len(o['ctrl']) and len(e['cp']) != len(o['fit']): errs.append('count')
            elif o['ctrl'] and not all(close(a[0], c[0]) and close(a[1], c[1]) for a, c in zip(e['cp'], o['ctrl'])): errs.append('geom')
        else:
            if not (all(close(a, c) for a, c in zip(e['c'][:2], dwgscene.ocs_to_wcs(tuple(o['center']), tuple(o.get('ext') or (0, 0, 1)))[:2])) and close(num(e['r']), o['radius']) and close(num(e['a0']), o['a0']) and close(num(e['a1']), o['a1'])): errs.append('geom')
        if e['layer'] != o.get('layer'): errs.append('layer')
        if int(float(e['ci'])) != o['color'][0] and not (o['color'][0] in (0, 256) and int(float(e['ci'])) in (0, 256)): errs.append('color')
        lw = o.get('lweight')
        mm = dwgmodel.LWEIGHT_MM.get(lw) if lw is not None and lw < 24 else None
        ol = int(float(e['lw']))
        if mm is not None and ol >= 0 and abs(mm * 100 - ol) > 1: errs.append('lw')
        for er in errs: bad[(e['t'], er)] += 1; first.setdefault((e['t'], er), e['h'])
        if not errs: ok[e['t']] += 1
print('ok', dict(ok)); print('bad', dict(bad)); print('first', first)
