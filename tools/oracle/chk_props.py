#!/usr/bin/env python3
"""chk_props.py FILE.dwg : entity-level properties per handle, parser vs AutoCAD dump (only types whose dump 'h' is a handle string):
visibility (invis), linetype scale, entity linetype (ByLayer / ByBlock / name), colour method + index + true colour, transparency. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
mine = {e['handle']: e for b, e in m.entities()}
ok = collections.Counter(); bad = collections.Counter(); first = {}
def close(a, b): return abs(a - b) <= 1e-9 * max(1.0, abs(a), abs(b))
for b in d['blocks']:
    for e in b.get('entities', []):
        if not isinstance(e['h'], str): continue
        o = mine.get(int(e['h'], 16))
        if o is None: continue
        errs = []
        if 'vis' in e and bool(e['vis']) == bool(o.get('invis', 0) & 1): errs.append('vis')
        if 'lts' in e and o.get('ltscale') is not None and not close(float(e['lts']), o['ltscale']): errs.append('ltscale')
        lf = o.get('ltflags')
        if lf is not None and 'lt' in e:
            if lf == 0: nm = 'ByLayer'
            elif lf == 1: nm = 'ByBlock'
            elif lf == 2: nm = 'CONTINUOUS'
            else:
                ob = m.objs.get(o['handle']); nm = None
                if ob is not None:
                    nm = next((m.tables.get('LTYPE', {}).get(v) for c, v in dwgmodel.resolve_handles(ob) if v in m.objs and m.objs[v].type == 57), None)
            if nm is None or nm.lower() != str(e['lt']).lower(): errs.append('ltype')
        cm = e.get('cm'); col = o['color']
        if cm in ('ByLayer', 'ByBlock'):
            want = 256 if cm == 'ByLayer' else 0
            if col[0] != want and not (col[1] is not None and (col[1] >> 24) in (0xC0, 0xC1)): errs.append('colormethod')
        if 'alpha' in e and col[2] is not None:
            a = col[2] & 0xFF if col[2] > 255 else col[2]
            # AutoCAD alpha 0..255 (0 = fully transparent) vs stored transparency word 0x02000000 | alpha
            if (col[2] >> 24) == 2 and (col[2] & 0xFF) != int(e['alpha']): errs.append('alpha')
        for x in errs: bad[(e['t'], x)] += 1; first.setdefault((e['t'], x), (e['h'], {k: e.get(k) for k in ('vis', 'lt', 'lts', 'cm', 'ci', 'alpha')}, {k: o.get(k) for k in ('invis', 'ltflags', 'ltscale', 'color')}))
        if not errs: ok[e['t']] += 1
print(dict(ok)); print('bad', dict(bad));
for k, v in list(first.items())[:6]: print(k, v)
