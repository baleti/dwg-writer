"""chk_layouts_dxf.py STEM : layout names, tab order (71) and paper size (44/45 mm) of Model.layouts() vs the LAYOUT objects of AutoCAD's drawing.dxf."""
import sys, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].rstrip('\r')) for i in range(0, len(L) - 1, 2)]
sec = None; want = False; ctype = None; lay = []; cur = None
for c, v in pairs:
    if c == '0' and v.strip() == 'SECTION': sec = None; want = True; continue
    if c == '2' and want: sec = v.strip(); want = False; continue
    if c == '0' and v.strip() == 'ENDSEC': sec = None; continue
    if sec != 'OBJECTS': continue
    if c == '0': ctype = v.strip(); cur = {} if ctype == 'LAYOUT' else None; 
    if c == '0' and ctype == 'LAYOUT': lay.append(cur)
    elif ctype == 'LAYOUT' and cur is not None:
        try:
            if c == '1': cur['n'] = v  # the layout name is the last group 1 (the first is the page setup name)
            elif c == '71': cur['o'] = int(v)
            elif c == '44' and 'w' not in cur: cur['w'] = float(v)
            elif c == '45' and 'h' not in cur: cur['h'] = float(v)
        except ValueError: pass
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
ours = {l['name']: l for l in m.layouts()}
n = nok = pok = pn = 0; ex = []
for d in lay:
    if 'n' not in d: continue
    n += 1
    o = ours.get(d['n'])
    if o is None: ex.append(('missing', d['n'])); continue
    nok += 1
    if 'w' in d and o.get('paper') and o['paper'][0] > 0:
        pn += 1
        pok += abs(max(o['paper']) - max(d['w'], d['h'])) < 1.0 and abs(min(o['paper']) - min(d['w'], d['h'])) < 1.0
print(stem, 'layouts', n, 'found by name', nok, 'paper size compared', pn, 'equal', pok, ex[:2])
