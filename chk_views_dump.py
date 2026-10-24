"""chk_views_dump.py FILE.dwg DUMP.json : named views (height, width, centre, target, direction, twist, lens, clips) and UCS records vs dump.json by name."""
import sys, json, collections, dwgmodel
d = json.load(open(sys.argv[2])); m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
ok = collections.Counter(); bad = collections.Counter(); ex = {}
def near(a, b): return all(abs(x - y) <= 1e-6 * max(1, abs(y)) for x, y in zip(a, b))
def cmp(k, a, b):
    g = near(a if isinstance(a, (list, tuple)) else [a], b if isinstance(b, (list, tuple)) else [b]); (ok if g else bad)[k] += 1
    if not g: ex.setdefault(k, (a, b))
vs = {v['name']: v for v in m.named_views()}
for s in d['views']:
    o = vs.get(s['name'])
    if o is None: bad['view missing'] += 1; continue
    for k, kk in (('height', 'Height'), ('width', 'Width'), ('center', 'CenterPoint'), ('target', 'Target'), ('direction', 'ViewDirection'), ('twist', 'ViewTwist'), ('lens', 'LensLength'), ('front_clip', 'FrontClipDistance'), ('back_clip', 'BackClipDistance')): cmp(k, o[k], s[kk])
us = {v['name']: v for v in m.ucs_list()}
for s in d['ucs']:
    o = us.get(s['name'])
    if o is None: bad['ucs missing'] += 1; continue
    for k in ('origin', 'xaxis', 'yaxis'): cmp('ucs_' + k, o[k], s[k])
vp = collections.defaultdict(list)
for v in m.vports(): vp[v['name']].append(v)
used = collections.Counter()
for s in d['viewports_table']:
    L = vp.get(s['name'], []); i = used[s['name']]; used[s['name']] += 1
    if i >= len(L): bad['vport missing'] += 1; continue
    o = L[i]
    for k, kk in (('height', 'Height'), ('width', 'Width'), ('center', 'CenterPoint'), ('target', 'Target'), ('direction', 'ViewDirection'), ('twist', 'ViewTwist'), ('lens', 'LensLength')): cmp('vp_' + k, o[k], s[kk])
print('ok', sum(ok.values()), 'bad', dict(bad)); print('first', ex)
