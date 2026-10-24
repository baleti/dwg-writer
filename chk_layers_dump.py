"""chk_layers_dump.py FILE.dwg DUMP.json : LAYER records (off, frozen, locked, plot, linetype, ACI colour, lineweight code vs AutoCAD's name) vs dump.json, by layer name."""
import sys, json, collections, dwgmodel
d = json.load(open(sys.argv[2])); m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
ours = m.layer_table()
ok = collections.Counter(); bad = collections.Counter(); ex = {}; lw = collections.Counter()
def cmp(k, a, b):
    g = a == b; (ok if g else bad)[k] += 1
    if not g: ex.setdefault(k, (a, b))
for s in d['layers']:
    o = ours.get(s['name'])
    if o is None: bad['missing'] += 1; continue
    cmp('off', o['off'], s['IsOff']); cmp('frozen', o['frozen'], s['IsFrozen']); cmp('locked', o['locked'], s['IsLocked']); cmp('plot', o['plot'], s['IsPlottable'])
    cmp('ltype', (o['ltype'] or '').lower(), s['LinetypeObjectId']['n'].lower())
    if s['Color'].get('method') == 'ByAci': cmp('aci', o['color'], s['Color']['index'])
    lw[(o['lineweight'], s['LineWeight'])] += 1
print('ok', sum(ok.values()), 'bad', dict(bad)); print('first', ex); print('lw', dict(lw))
