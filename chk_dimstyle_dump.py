"""chk_dimstyle_dump.py FILE.dwg DUMP.json : DIMSTYLE variables of Model.dimstyles() vs AutoCAD's dump.json (numbers and booleans, by style name and variable name)."""
import sys, json, collections, dwgmodel
d = json.load(open(sys.argv[2])); m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
ours = m.dimstyles(); ok = collections.Counter(); bad = collections.Counter(); ex = {}
for s in d['dimstyles']:
    o = ours.get(s['name'])
    if o is None: bad['style missing'] += 1; continue
    for k, v in s.items():
        K = k.upper()
        if K not in o or isinstance(v, (dict, list)): continue
        a = o[K]
        if isinstance(v, bool): a = bool(a)
        if K in ('DIMLWD', 'DIMLWE') and isinstance(v, str):
            if v in ('ByBlock', 'ByLayer', 'ByLwDefault'): v = {'ByBlock': 65534, 'ByLayer': 65535, 'ByLwDefault': 65533}[v]
            else: continue
        if isinstance(v, str) != isinstance(a, str): continue
        good = (abs(float(a) - float(v)) < 1e-6 * max(1, abs(float(v)))) if not isinstance(v, str) else a == v
        (ok if good else bad)[K] += 1
        if not good: ex.setdefault(K, (s['name'], v, a))
print('ok', sum(ok.values()), 'bad', dict(bad)); print('first', ex)
