"""chk_insert_dxf.py STEM : INSERT block name, scale (41/42/43) and rotation (50) of Model.entities() vs AutoCAD's drawing.dxf, per handle."""
import sys, math, dwgmodel
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
    elif c == '5' and cur is None and ctype == 'INSERT': cur = {'n': None, 'sc': [1.0, 1.0, 1.0], 'r': 0.0}; ent[int(v, 16)] = cur
    elif cur is not None:
        try:
            if c == '2' and cur['n'] is None: cur['n'] = v
            elif c == '41': cur['sc'][0] = float(v)
            elif c == '42': cur['sc'][1] = float(v)
            elif c == '43': cur['sc'][2] = float(v)
            elif c == '50': cur['r'] = math.radians(float(v))
        except ValueError: pass
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
n = nok = sok = rok = 0; ex = []
close = lambda a, b: abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] != 'INSERT': continue
    n += 1
    nm = (e.get('block_true_name') or e.get('block_ref') or '').split('~')[0]
    if nm.upper() == (d['n'] or '').upper() or (nm.startswith('*') and (d['n'] or '').startswith('*')): nok += 1
    elif len(ex) < 3: ex.append((hex(e['handle']), e.get('block_ref'), d['n']))
    if all(close(a, b) for a, b in zip(e['scale'], d['sc'])): sok += 1
    if close(math.sin(e['rot']), math.sin(d['r'])) and close(math.cos(e['rot']), math.cos(d['r'])): rok += 1
print(stem, 'inserts', n, 'name equal', nok, 'scale equal', sok, 'rotation equal', rok, ex)
