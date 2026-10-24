"""chk_layovr_dxf.py FILE.dwg DXF : Model.layer_overrides() (colour) vs AutoCAD's drawing.dxf: LAYER -> ADSK_XREC_LAYER_COLOR_OVR XRECORD blocks (335 viewport, 420 colour)."""
import sys, dwgmodel
L = open(sys.argv[2], errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].strip()) for i in range(0, len(L) - 1, 2)]
xr = {}; cur = None; typ = None; vp = None
for c, v in pairs:
    if c == '0': typ = v; cur = None; vp = None
    elif c == '5' and typ == 'XRECORD' and cur is None: cur = int(v, 16); xr[cur] = []
    elif cur is not None and c == '335': vp = int(v, 16); xr[cur].append([vp, None])
    elif cur is not None and c == '420' and xr[cur]: xr[cur][-1][1] = int(v) & 0xFFFFFFFF
dicts = {}; cur = None; typ = None; ent = None
for c, v in pairs:
    if c == '0': typ = v; cur = None
    elif c == '5' and typ == 'DICTIONARY' and cur is None: cur = {'h': int(v, 16), 'own': None, 'items': {}}; dicts[cur['h']] = cur
    elif cur is not None and c == '330' and cur['own'] is None: cur['own'] = int(v, 16)
    elif cur is not None and c == '3': ent = v
    elif cur is not None and c == '360' and ent: cur['items'][ent] = int(v, 16)
want = {}
for d in dicts.values():
    x = d['items'].get('ADSK_XREC_LAYER_COLOR_OVR')
    if x in xr: want[d['own']] = {vp: col for vp, col in xr[x]}
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
got = {l: {vp: v.get('color') for vp, v in d.items()} for l, d in m.layer_overrides().items()}
n = sum(len(v) for v in want.values()); ok = sum(1 for l, d in want.items() for vp, c in d.items() if got.get(l, {}).get(vp) == c)
print('layers', len(want), 'override blocks', n, 'equal', ok, 'ours layers', len(got), 'ours blocks', sum(len(v) for v in got.values()))
