"""chk_tables_dump.py FILE.dwg DUMP.json : STYLE (font, big font, width factor, oblique, fixed height, last height) and LTYPE (pattern length, dash lengths, count) records vs AutoCAD's dump.json, by name."""
import sys, json, collections, dwgmodel
d = json.load(open(sys.argv[2])); m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
ok = collections.Counter(); bad = collections.Counter(); ex = {}
def cmp(k, a, b):
    g = (abs(float(a) - float(b)) < 1e-6 * max(1, abs(float(b)))) if not isinstance(b, str) else str(a).lower() == b.lower()
    (ok if g else bad)[k] += 1
    if not g: ex.setdefault(k, (a, b))
st = m.styles()
for s in d['textstyles']:
    o = st.get(s['name'])
    if o is None: bad['style missing'] += 1; continue
    cmp('font', o['font'], s['FileName']); cmp('bigfont', o['bigfont'], s['BigFontFileName']); cmp('width', o['width_factor'], s['XScale'])
    cmp('oblique', o['oblique'], s['ObliquingAngle']); cmp('fixed_height', o['fixed_height'], s['TextSize']); cmp('last_height', o['last_height'], s['PriorSize'])
lt = m.ltypes()
for s in d['linetypes']:
    if s['name'] in ('ByBlock', 'ByLayer'): continue
    o = lt.get(s['name'])
    if o is None: bad['ltype missing'] += 1; continue
    cmp('lt_len', o['pattern_length'], s['pattern_length']); cmp('lt_ndash', len(o['dashes']), s['num_dashes'])
    if len(o['dashes']) == s['num_dashes']:
        for a, b in zip(o['dashes'], s['dashes']): cmp('lt_dash', a['length'], b['length'])
print('ok', sum(ok.values()), 'bad', dict(bad)); print('first', ex)
