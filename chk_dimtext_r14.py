"""chk_dimtext_r14.py STEM... : R13/R14 DIMENSION text override (user_text) vs AutoCAD DXF group 1, per handle."""
import sys, collections, dwgr14
tot = collections.Counter()
for st in sys.argv[1:]:
    L = open('oracle-out/%s/drawing.dxf' % st, errors='replace').read().split('\n')
    ov = {}; pts = {}; cur = None; sec = None; want = False; isd = False
    for i in range(0, len(L) - 1, 2):
        c, v = L[i].strip(), L[i + 1].rstrip('\r')
        if c == '0' and v.strip() == 'SECTION': want = True; continue
        if c == '2' and want: sec = v.strip(); want = False; continue
        if c == '0': cur = None; isd = v.strip() == 'DIMENSION'; first = True; continue
        if sec not in ('ENTITIES', 'BLOCKS') or not isd: continue
        if c == '5' and first: cur = int(v, 16); ov[cur] = ''; first = False
        elif cur and c == '1': ov[cur] = v
        elif cur and c in ('11', '21', '13', '23', '14', '24', '10', '20'): pts.setdefault(cur, {}).setdefault(c, float(v))
    m = dwgr14.Model14(open('corpus/%s.dwg' % st, 'rb').read())
    for h, o in m.objs.items():
        if h in ov and 20 <= o.type <= 26:
            t = dwgr14.dim_user_text(o); tot['dims'] += 1; tot['equal'] += t == ov[h]
            f = dwgr14.dim_fields(o); q = pts.get(h, {}); cl = lambda a, b: b is None or abs(a - b) <= 1e-6 * max(1, abs(b))
            if 'text_mid' in f and '11' in q: tot['mid'] += 1; tot['mid_equal'] += cl(f['text_mid'][0], q['11']) and cl(f['text_mid'][1], q['21'])
            if 'pt13' in f and '13' in q: tot['p13'] += 1; tot['p13_equal'] += all(cl(f[k][i], q[c]) for k, c, i in (('pt13', '13', 0), ('pt13', '23', 1), ('pt14', '14', 0), ('pt14', '24', 1), ('pt10', '10', 0), ('pt10', '20', 1)) if c in q)
            if ov[h]: tot['overrides'] += 1; tot['override_equal'] += t == ov[h]
            elif t: tot['false_positive'] += 1
print(dict(tot))
