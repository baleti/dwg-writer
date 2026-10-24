"""chk_text_dxf.py STEM : TEXT string and height (group 1 / 40) of Model.entities() vs AutoCAD's drawing.dxf, per handle (MTEXT: group 1+3 concatenated)."""
import sys, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip('\r'), L[i + 1].rstrip('\r')) for i in range(0, len(L) - 1, 2)]
sec = None; want = False; ctype = None; ent = {}; cur = None
for c, v in pairs:
    c = c.strip()
    if c == '0' and v.strip() == 'SECTION': sec = None; want = True; continue
    if c == '2' and want: sec = v.strip(); want = False; continue
    if c == '0' and v.strip() == 'ENDSEC': sec = None; continue
    if sec not in ('BLOCKS', 'ENTITIES'): continue
    if c == '0': ctype = v.strip(); cur = None
    elif c == '5' and cur is None and ctype in ('TEXT', 'MTEXT'): cur = {'t': ctype, 'txt': '', 'h': None}; ent[int(v, 16)] = cur
    elif cur is not None:
        if c == '1': cur['txt'] = cur['txt'] + v if cur['t'] == 'MTEXT' else v
        elif c == '3': cur['txt'] = v + cur['txt']  # MTEXT: continuation chunks (group 3) precede group 1
        elif c == '40' and cur['h'] is None:
            try: cur['h'] = float(v)
            except ValueError: pass
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
n = ok = hn = hok = 0; ex = []
for bn, e in m.entities():
    d = ent.get(e['handle'])
    if d is None or e['kind'] != d['t']: continue
    n += 1
    a = e.get('text') or ''
    if a == d['txt']: ok += 1
    elif len(ex) < 3: ex.append((hex(e['handle']), a[:40], d['txt'][:40]))
    h = e.get('height') if e['kind'] == 'TEXT' else e.get('text_height')
    if h is not None and d['h'] is not None:
        hn += 1
        if abs(h - d['h']) <= 1e-6 * max(1, abs(h)): hok += 1
print(stem, 'text', n, 'string equal', ok, 'height compared', hn, 'equal', hok, ex)
