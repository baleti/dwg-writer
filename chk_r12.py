"""chk_r12.py STEM : dwgr12 vs the AutoCAD dump (model space entity counts and LINE/ARC/CIRCLE/TEXT/INSERT geometry, in stream order)."""
import sys, json, struct, collections
import dwgr12
stem = sys.argv[1]
b = open('corpus/%s.dwg' % stem, 'rb').read()
es, ee = struct.unpack_from('<II', b, 0x14)
dump = json.load(open('oracle-out/%s/dump.json' % stem))
lay = dwgr12.layers(b)
tr = collections.defaultdict(list)
for blk in dump['blocks']:
    if blk['name'] == '*Model_Space':
        for e in blk['entities']: tr[e['t']].append(e)
ours = collections.defaultdict(list)
for r in dwgr12.records(b, es, ee):
    e = dwgr12.decode(r)
    if e and e['kind']: ours[e['kind']].append(e)
close = lambda a, c: abs(a - c) <= 1e-6 * max(1.0, abs(a), abs(c))
for k in ('LINE', 'ARC', 'CIRCLE', 'POINT', 'SOLID', 'TEXT', 'INSERT'):
    n = bad = 0; lbad = 0
    for e, t in zip(ours[k], tr[k]):
        n += 1
        if k == 'LINE': ok = close(e['p1'][0], t['a'][0]) and close(e['p2'][1], t['b'][1])
        elif k == 'ARC': ok = close(e['center'][0], t['c'][0]) and close(e['radius'], t['r']) and close(e['a1'], t['a1'])
        elif k == 'CIRCLE': ok = close(e['center'][1], t['c'][1]) and close(e['radius'], t['r'])
        elif k == 'POINT': ok = close(e['p'][0], t['p'][0])
        elif k == 'SOLID': ok = close(e['pts'][3][0], t['v'][3][0])
        elif k == 'TEXT': ok = e['text'] == t['s'] and close(e.get('align_pt', e['p'])[0], t['al'][0] if e.get('align_pt') else t['p'][0]) and close(e['rot'], t['rot']) and close(e['wf'], t['wf'])
        else: ok = close(e['ins'][0] * e['ext'][2], t['p'][0]) and close(e['rot'], t['rot']) and all(close(a, c) for a, c in zip(e['scale'], t['sc']))
        if not ok: bad += 1
        if lay[e['layer_index']]['name'] != t['layer']: lbad += 1
    print(k, 'ours', len(ours[k]), 'truth', len(tr[k]), 'compared', n, 'geom bad', bad, 'layer bad', lbad)
