"""chk_layers_dxf.py STEM : layer names, ACI colour, linetype, frozen/off/locked flags of Model.layer_table() vs the LAYER table of AutoCAD's drawing.dxf."""
import sys, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].rstrip('\r')) for i in range(0, len(L) - 1, 2)]
sec = None; want = False; ctype = None; layers = {}; cur = None
for c, v in pairs:
    if c == '0' and v.strip() == 'SECTION': sec = None; want = True; continue
    if c == '2' and want: sec = v.strip(); want = False; continue
    if c == '0' and v.strip() == 'ENDSEC': sec = None; continue
    if sec != 'TABLES': continue
    if c == '0': ctype = v.strip(); cur = {} if ctype == 'LAYER' else None
    elif ctype == 'LAYER' and cur is not None:
        if c == '2': cur['n'] = v; layers[v] = cur
        elif c == '62': cur['c'] = int(v)
        elif c == '6': cur['l'] = v
        elif c == '70': cur['f'] = int(v)
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
lt = m.layer_table()
ours = {n.upper(): (n, d) for n, d in lt.items()}
n = nok = cok = lok = fok = 0; missing = 0
for name, d in layers.items():
    o = ours.get(name.upper())
    if o is None: missing += 1; continue
    n += 1
    nok += o[0] == name
    cok += abs(d.get('c', 7)) == (o[1].get('color') or 7) or d.get('c', 7) == 256
    ol = (o[1].get('ltype') or 'CONTINUOUS').upper(); dl = (d.get('l') or 'CONTINUOUS').upper()
    lok += ol == dl
    fok += bool(d.get('f', 0) & 1) == bool(o[1].get('frozen')) and (d.get('c', 7) < 0) == bool(o[1].get('off'))
print(stem, 'layers', len(layers), 'found', n, 'missing', missing, 'name equal', nok, 'colour', cok, 'linetype', lok, 'frozen+off', fok)
