"""chk_vpfrozen.py : VIEWPORT frozen_layers (Model.entities) vs the group-331 lists of AutoCAD's own drawing.dxf, for every local file that has both."""
import glob, os, dwgmodel
tot = ok = 0
for f in sorted(glob.glob('corpus/AC10[123]*.dwg')):
    stem = os.path.basename(f)[:-4]; dxf = 'oracle-out/%s/drawing.dxf' % stem
    if not os.path.exists(dxf) or stem[:6] in ('AC1012', 'AC1014', 'AC1015'): continue
    L = open(dxf, errors='replace').read().split('\n')
    dx = {}; cur = None
    for i in range(0, len(L) - 1, 2):
        c, v = L[i].strip(), L[i + 1].strip()
        if c == '0': cur = None
        if c == '0' and v == 'VIEWPORT': cur = {'f': set(), 'h': None}
        elif cur is not None:
            if c == '5' and cur['h'] is None:
                try: cur['h'] = int(v, 16); dx[cur['h']] = cur
                except ValueError: pass
            if c == '331':
                try: cur['f'].add(int(v, 16))
                except ValueError: pass
    try: m = dwgmodel.Model(open(f, 'rb').read())
    except Exception: continue
    n = k = 0; first = None
    for bn, e in m.entities():
        if e['kind'] != 'VIEWPORT' or e['handle'] not in dx: continue
        n += 1
        if set(e['frozen_layers']) == dx[e['handle']]['f']: k += 1
        elif first is None: first = (hex(e['handle']), len(e['frozen_layers']), len(dx[e['handle']]['f']))
    if n: print(stem, 'viewports', n, 'equal', k, first or '')
    tot += n; ok += k
print('total', tot, 'equal', ok)
