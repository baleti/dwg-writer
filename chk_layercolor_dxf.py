"""chk_layercolor_dxf.py STEM : entity layer and effective ACI colour of Model.entities() vs AutoCAD's drawing.dxf (group 8; group 62, else the layer colour from TABLES)."""
import sys, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].strip()) for i in range(0, len(L) - 1, 2)]
sec = None; want = False; ctype = None; hnd = None; layer_col = {}; ent = {}; cur = None
for c, v in pairs:
    if c == '0' and v == 'SECTION': sec = None; want = True; continue
    if c == '2' and want: sec = v; want = False; continue
    if c == '0' and v == 'ENDSEC': sec = None; continue
    if sec == 'TABLES':
        if c == '0': ctype = v; cur = {'n': None, 'c': None} if v == 'LAYER' else None
        elif ctype == 'LAYER' and cur is not None:
            if c == '2': cur['n'] = v
            if c == '62': cur['c'] = int(v)
            if cur['n'] and cur['c'] is not None: layer_col[cur['n']] = abs(cur['c'])
    elif sec in ('BLOCKS', 'ENTITIES'):
        if c == '0': ctype = v; hnd = None; cur = None
        elif c == '5' and hnd is None and ctype not in ('BLOCK', 'ENDBLK'): hnd = int(v, 16); cur = {'c': None, 'ly': None}; ent[hnd] = cur
        elif cur is not None and c == '62': cur['c'] = int(v)
        elif cur is not None and c == '8': cur['ly'] = v
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
n = lok = cok = cn = 0; ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] in ('VERTEX2D', 'VERTEX3D', 'SEQEND', 'ATTRIB', 'VERTEX_MESH', 'VERTEX_PFACE', 'VERTEX_PFACE_FACE'): continue
    n += 1
    if e.get('layer') == d['ly']: lok += 1
    elif len(ex) < 3: ex.append((hex(e['handle']), e.get('layer'), d['ly']))
    if d['c'] is not None and d['c'] in (0, 256): continue  # by block / by layer
    truth = abs(d['c']) if d['c'] is not None else layer_col.get(d['ly'])
    cn += 1
    if m.effective(e)['color'] == truth: cok += 1
print(stem, 'entities', n, 'layer equal', lok, 'colour compared', cn, 'equal', cok, ex)
