"""chk_r14.py FILE.dwg : LINE/CIRCLE/ARC/POINT geometry and layer handle of dwgr14 vs the AutoCAD dump (oracle-out/<stem>/dump.json, existing dumps only)."""
import sys, json, os, collections
import dwgr14
path = sys.argv[1]; stem = os.path.basename(path)[:-4]
dump = json.load(open('oracle-out/%s/dump.json' % stem))
d = dwgr14.load(open(path, 'rb').read())
lay = {int(l['handle'], 16): l['name'] for l in dump['layers']}
ok = collections.Counter(); bad = collections.Counter(); first = {}
def wcs(c, n):
    # arbitrary axis algorithm: OCS point -> WCS
    nx, ny, nz = n
    if abs(nx) < 1 / 64 and abs(ny) < 1 / 64: ax = (nz, 0.0, -nx)  # Wy x N
    else: ax = (-ny, nx, 0.0)  # Wz x N
    l = sum(v * v for v in ax) ** .5; ax = tuple(v / l for v in ax)
    ay = (ny * ax[2] - nz * ax[1], nz * ax[0] - nx * ax[2], nx * ax[1] - ny * ax[0])
    return tuple(c[0] * ax[i] + c[1] * ay[i] + c[2] * n[i] for i in range(3))
def close(a, b): return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
for b in dump['blocks']:
    for e in b.get('entities', []):
        if e['t'] not in ('LINE', 'CIRCLE', 'ARC', 'POINT'): continue
        h = int(e['h'], 16) if isinstance(e['h'], str) else e['h']
        o = d['objects'].get(h)
        if o is None: bad[(e['t'], 'missing')] += 1; continue
        try: m = dwgr14.decode_entity(o)
        except Exception as ex: m = None
        err = None
        if m is None: err = 'decode'
        elif e['t'] == 'LINE' and not (close(m['p1'][0], e['a'][0]) and close(m['p1'][1], e['a'][1]) and close(m['p2'][0], e['b'][0]) and close(m['p2'][1], e['b'][1])): err = 'geom'
        elif e['t'] in ('CIRCLE', 'ARC') and not (close(wcs(m['center'], m['ext'])[0], e['c'][0]) and close(m['radius'], e['r'])): err = 'geom'
        elif e['t'] == 'POINT' and not (close(m['p'][0], e['p'][0]) and close(m['p'][1], e['p'][1])): err = 'geom'
        elif lay.get(m['layer_handle']) != e['layer']: err = 'layer'
        if err: bad[(e['t'], err)] += 1; first.setdefault((e['t'], err), hex(h))
        else: ok[e['t']] += 1
print('ok', dict(ok)); print('bad', dict(bad)); print('first', first)
