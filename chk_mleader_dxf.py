"""chk_mleader_dxf.py STEM : MULTILEADER text (group 304) and text location (12/22) of Model.entities() vs AutoCAD's drawing.dxf, per handle; LEADER vertex count (76)."""
import sys, collections, dwgmodel
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
    elif c == '5' and cur is None and ctype in ('MULTILEADER', 'LEADER'): cur = {'t': ctype, 'txt': None, 'x': None, 'y': None, 'n': None}; ent[int(v, 16)] = cur
    elif cur is not None:
        try:
            if c == '304' and cur['txt'] is None: cur['txt'] = v
            elif c == '12' and cur['x'] is None: cur['x'] = float(v)
            elif c == '22' and cur['y'] is None: cur['y'] = float(v)
            elif c == '76' and cur['n'] is None: cur['n'] = int(v)
        except ValueError: pass
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
close = lambda a, b: abs(a - b) <= 1e-5 * max(1.0, abs(a), abs(b))
c = collections.Counter(); ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None: continue
    if e['kind'] == 'MULTILEADER' and d['t'] == 'MULTILEADER':
        c['ml'] += 1
        if d['txt'] is not None: c['ml_txt'] += 1; c['ml_txt_ok'] += (e.get('text') or '') == d['txt']
        tl = e.get('text_loc')
        if d['x'] is not None and tl: c['ml_loc'] += 1; c['ml_loc_ok'] += close(tl[0], d['x']) and close(tl[1], d['y'])
    elif e['kind'] == 'LEADER' and d['t'] == 'LEADER':
        c['ld'] += 1
        if d['n'] is not None: c['ld_n'] += 1; c['ld_n_ok'] += len(e['pts']) == d['n']
print(stem, dict(c))
