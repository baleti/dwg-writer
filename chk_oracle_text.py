"""chk_oracle_text.py FILE.dwg : multiset comparison of TEXT/MTEXT (text, insertion point, height/rotation) and HATCH (pattern, solid, loop count) with the AutoCAD dump."""
import sys, json, os, collections
import dwgmodel, dwgscene, dwg2text
path = sys.argv[1]
d = json.load(open('oracle-out/%s/dump.json' % os.path.basename(path)[:-4]))
m = dwgmodel.Model(open(path, 'rb').read())
def key(t, x, y): return (t.strip(), round(x, 2), round(y, 2))
ours = collections.Counter(); theirs = collections.Counter()
hat_o = collections.Counter(); hat_t = collections.Counter()
for b, e in m.entities():
    if e['kind'] in ('TEXT', 'MTEXT') and e.get('text') and e['text'].strip():
        t = dwg2text.strip_mtext(e['text']).replace('\n', ' ') if e['kind'] == 'MTEXT' else e['text']
        ip = e['align'] if e['kind'] == 'TEXT' and e.get('align') else e['ins']  # compare the alignment point: AutoCAD recomputes the insertion point of justified text, the stored one is stale
        w = ip if e['kind'] == 'MTEXT' else dwgscene.ocs_to_wcs((ip[0], ip[1], e.get('elev', e['ins'][2] if len(e['ins']) > 2 else 0.0)), tuple(e.get('ext', (0, 0, 1))))  # MTEXT insertion is already WCS
        ours[(e['kind'],) + key(t, w[0], w[1])] += 1
    elif e['kind'] == 'HATCH':
        hat_o[(e['pattern_name'], bool(e['solid']), len(e['paths']))] += 1
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] in ('TEXT', 'MTEXT') and not e.get('s', '').strip(): continue  # empty text is not extracted
        if e['t'] == 'TEXT':
            ap = e['al'] if e.get('al') and (e['al'][0] or e['al'][1]) else e['p']
            theirs[('TEXT',) + key(e['s'], ap[0], ap[1])] += 1
        elif e['t'] == 'MTEXT': theirs[('MTEXT',) + key(e['s'].replace('\r\n', ' ').replace('\n', ' ').replace('\\P', ' '), e['p'][0], e['p'][1])] += 1
        elif e['t'] == 'HATCH': hat_t[(e['pattern'], bool(e['solid']), int(e['nloops']))] += 1
def cmp(a, b, name):
    common = sum((a & b).values()); print(name, 'ours', sum(a.values()), 'oracle', sum(b.values()), 'common', common)
    return a - b, b - a
for name, a, b in (('text', ours, theirs), ('hatch', hat_o, hat_t)):
    xo, xt = cmp(a, b, name)
    print('  only ours', [k for k in list(xo)[:3]], '\n  only oracle', [k for k in list(xt)[:3]])
