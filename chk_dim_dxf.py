"""chk_dim_dxf.py STEM : DIMENSION picture block name (2), text override (1), dimstyle (3) and measurement (42) of Model.entities() vs AutoCAD's drawing.dxf, per handle."""
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
    elif c == '5' and cur is None and ctype == 'DIMENSION': cur = {'b': None, 't': None, 's': None, 'm': None}; ent[int(v, 16)] = cur
    elif cur is not None:
        if c == '2' and cur['b'] is None: cur['b'] = v
        elif c == '1' and cur['t'] is None: cur['t'] = v
        elif c == '3' and cur['s'] is None: cur['s'] = v
        elif c == '42' and cur['m'] is None:
            try: cur['m'] = float(v)
            except ValueError: pass
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
n = bok = tok = mn = mok = 0; ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or not e['kind'].startswith('DIM_'): continue
    n += 1
    nm = (e.get('block_ref') or '').split('~')[0]
    if nm.startswith('*D') and (d['b'] or '').startswith('*D') or nm.upper() == (d['b'] or '').upper(): bok += 1
    elif len(ex) < 2: ex.append((hex(e['handle']), e.get('block_ref'), d['b']))
    if (e.get('user_text') or '') == (d['t'] or ''): tok += 1
    if d['m'] is not None and e.get('measurement') is not None:
        mn += 1
        if abs(e['measurement'] - d['m']) <= 1e-6 * max(1, abs(d['m'])): mok += 1
print(stem, 'dimensions', n, 'block equal', bok, 'text override equal', tok, 'measurement compared', mn, 'equal', mok, ex)
