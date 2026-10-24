"""chk_attrib_dxf.py STEM : ATTRIB/ATTDEF tag (2) and value (1) of Model.entities() vs AutoCAD's drawing.dxf, per handle."""
import sys, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].rstrip('\r')) for i in range(0, len(L) - 1, 2)]
sec = None; want = False; ctype = None; ent = {}; cur = None
for c, v in pairs:
    if c == '0' and v.strip() == 'SECTION': sec = None; want = True; continue
    if c == '2' and want: sec = v.strip(); want = False; continue
    if c == '0' and v.strip() == 'ENDSEC': sec = None; continue
    if sec not in ('BLOCKS', 'ENTITIES'): continue
    if c == '0': ctype = v.strip(); cur = None
    elif c == '5' and cur is None and ctype in ('ATTRIB', 'ATTDEF'): cur = {'t': ctype, 'tag': None, 'val': None}; ent[int(v, 16)] = cur
    elif cur is not None:
        if c == '2' and cur['tag'] is None: cur['tag'] = v.strip()
        elif c == '1' and cur['val'] is None: cur['val'] = v
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
n = tok = vok = 0; ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] != d['t']: continue
    n += 1
    if (e.get('tag') or '').upper() == (d['tag'] or '').upper(): tok += 1
    elif len(ex) < 3: ex.append((hex(e['handle']), e.get('tag'), d['tag']))
    if (e.get('text') or '') == (d['val'] or ''): vok += 1
print(stem, 'attribs', n, 'tag equal', tok, 'value equal', vok, ex)
