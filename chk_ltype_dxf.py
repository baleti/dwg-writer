"""chk_ltype_dxf.py STEM : effective linetype of Model.entities() vs AutoCAD's drawing.dxf (entity group 6, else the layer's linetype)."""
import sys, collections, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].strip()) for i in range(0, len(L) - 1, 2)]
sec = None; want = False; ctype = None; hnd = None; layer_lt = {}; ent = {}; cur = None
for c, v in pairs:
    if c == '0' and v == 'SECTION': sec = None; want = True; continue
    if c == '2' and want: sec = v; want = False; continue
    if c == '0' and v == 'ENDSEC': sec = None; continue
    if sec == 'TABLES':
        if c == '0': ctype = v; cur = {'n': None, 'l': None} if v == 'LAYER' else None; 
        elif ctype == 'LAYER' and cur is not None:
            if c == '2': cur['n'] = v
            if c == '6': cur['l'] = v
            if cur['n'] and cur['l']: layer_lt[cur['n']] = cur['l']
    elif sec in ('BLOCKS', 'ENTITIES'):
        if c == '0': ctype = v; hnd = None; cur = None
        elif c == '5' and hnd is None and ctype not in ('BLOCK', 'ENDBLK'): hnd = int(v, 16); cur = {'l': None, 'ly': None}; ent[hnd] = cur
        elif cur is not None and c == '6': cur['l'] = v
        elif cur is not None and c == '8': cur['ly'] = v
norm = lambda x: None if (not x or x.upper() in ('CONTINUOUS', 'BYLAYER', 'BYBLOCK')) else x.upper()
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
n = ok = 0; ex = []
for bn, e in m.entities():
    if e['handle'] not in ent or e['kind'] in ('VERTEX2D', 'VERTEX3D', 'SEQEND', 'ATTRIB'): continue
    d = ent[e['handle']]
    truth = d['l'] if d['l'] and d['l'].upper() != 'BYLAYER' else layer_lt.get(d['ly'])
    if d['l'] and d['l'].upper() == 'BYBLOCK': continue
    mine = m.effective(e)['ltype']
    n += 1
    if norm(mine) == norm(truth): ok += 1
    elif len(ex) < 3: ex.append((hex(e['handle']), mine, truth, d['l'], d['ly']))
print(stem, 'entities', n, 'equal', ok, ex)
