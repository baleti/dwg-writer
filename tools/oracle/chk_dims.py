#!/usr/bin/env python3
"""chk_dims.py FILE.dwg : DIMENSION entities by handle, parser vs AutoCAD dump (measurement, text position, user text, definition points for linear/aligned). Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel, dwgscene
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
mine = {e['handle']: e for b, e in m.entities() if e['kind'].startswith('DIM_')}
def close(a, b): return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
res = collections.Counter(); first = {}
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] != 'DIMENSION' or not isinstance(e['h'], str): continue
        o = mine.get(int(e['h'], 16))
        if o is None: res['missing'] += 1; continue
        errs = []
        if not close(o['measurement'], e['meas']): errs.append('meas')
        w = dwgscene.ocs_to_wcs((o['text_mid'][0], o['text_mid'][1], o['elevation']), tuple(o['ext']))
        if not all(close(a, c) for a, c in zip(w[:2], e['tp'][:2])): errs.append('text_pos')
        if (o['user_text'] or '') != (e['text'] or ''): errs.append('text')
        if o['kind'] == 'DIM_ALIGNED' and 'x1' in e:
            if not (all(close(a, c) for a, c in zip(o['pt13'][:2], e['x1'][:2])) and all(close(a, c) for a, c in zip(o['pt14'][:2], e['x2'][:2]))): errs.append('defpts')
        for x in errs: res[x] += 1; first.setdefault(x, (e['h'], o['kind']))
        res['ok' if not errs else 'bad'] += 1
print(json.dumps({'res': dict(res), 'first': first}))
