"""chk_hatch_dxf.py STEM : HATCH pattern name, solid flag and boundary path count of Model.entities() vs AutoCAD's drawing.dxf (groups 2, 70, 91), per handle."""
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
    elif c == '5' and cur is None and ctype == 'HATCH': cur = {}; ent[int(v, 16)] = cur
    elif cur is not None:
        if c == '2' and 'n' not in cur: cur['n'] = v
        elif c == '70' and 's' not in cur: cur['s'] = int(v)
        elif c == '91' and 'p' not in cur: cur['p'] = int(v)
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
n = ok = 0; ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] != 'HATCH': continue
    n += 1
    good = (e.get('pattern_name') or '').upper() == (d.get('n') or '').upper() and int(bool(e.get('solid'))) == d.get('s') and len(e['paths']) == d.get('p')
    if good: ok += 1
    elif len(ex) < 3: ex.append((hex(e['handle']), e.get('pattern_name'), e.get('solid'), len(e['paths']), d))
print(stem, 'hatches', n, 'equal', ok, ex)
