import sys, dwgload, dwgent
d = dwgload.load(open(sys.argv[1], 'rb').read())
L = open(sys.argv[2], errors='replace').read().split('\n')
dp = set(); di = set(); cur = None; sec = None
def fin(c):
    if c and sec in ('ENTITIES', 'BLOCKS'):
        if c['t'] == 'LWPOLYLINE': dp.add((c['n'], tuple(c['p'][:4])))
        if c['t'] == 'INSERT': di.add((c.get('2', ''), round(c.get('10', 0), 3), round(c.get('20', 0), 3)))
for i in range(0, len(L) - 1, 2):
    g, v = L[i].strip(), L[i + 1].strip()
    if g == '0':
        fin(cur); cur = {'t': v, 'p': [], 'n': 0}
        if v == 'SECTION': sec = None
    elif g == '2' and cur and cur['t'] == 'SECTION': sec = v
    elif cur is not None:
        if cur['t'] == 'LWPOLYLINE':
            if g == '90': cur['n'] = int(v)
            elif g in ('10', '20'): cur['p'].append(round(float(v), 3))
        elif cur['t'] == 'INSERT':
            if g == '2': cur.setdefault('2', v)
            elif g in ('10', '20'):
                try: cur.setdefault(g, float(v))
                except ValueError: pass
mp = set(); mi = set(); err = 0; blocks = {}
for o in d['objects'].values():
    if o.type == 4: pass
    try:
        if o.type == 77:
            e = dwgent.decode_lwpolyline(o); f = []
            for p in e['pts'][:2]: f += [round(p[0], 3), round(p[1], 3)]
            mp.add((len(e['pts']), tuple(f)))
        elif o.type == 7:
            e = dwgent.decode_insert(o); mi.add((round(e['ins'][0], 3), round(e['ins'][1], 3)))
    except Exception: err += 1
print('LWPOLY mine', len(mp), 'oracle', len(dp), 'found', len(dp & mp))
print('INSERT positions mine', len(mi), 'oracle', len(di), 'found', len({(x, y) for _, x, y in di} & mi))
print('errors', err)
