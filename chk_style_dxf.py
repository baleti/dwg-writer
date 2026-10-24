"""chk_style_dxf.py STEM : TEXT/MTEXT/ATTRIB text style name of Model.entities() vs AutoCAD's drawing.dxf (group 7), per handle."""
import sys, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].strip()) for i in range(0, len(L) - 1, 2)]
sec = None; want = False; ctype = None; ent = {}; cur = None
for c, v in pairs:
    if c == '0' and v == 'SECTION': sec = None; want = True; continue
    if c == '2' and want: sec = v; want = False; continue
    if c == '0' and v == 'ENDSEC': sec = None; continue
    if sec not in ('BLOCKS', 'ENTITIES'): continue
    if c == '0': ctype = v; cur = None
    elif c == '5' and cur is None and ctype in ('TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'): cur = {'s': None}; ent[int(v, 16)] = cur
    elif cur is not None and c == '7': cur['s'] = v
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
n = ok = 0; ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] not in ('TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'): continue
    n += 1
    a = (e.get('style') or '').upper(); b = (d['s'] or 'STANDARD').upper()  # DXF omits group 7 for STANDARD
    if a == b: ok += 1
    elif len(ex) < 3: ex.append((hex(e['handle']), e.get('style'), d['s']))
print(stem, 'text entities', n, 'style equal', ok, ex)
