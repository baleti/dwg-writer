import sys, collections, dwgmodel
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
L = open(sys.argv[2], errors='replace').read().split('\n')
sec = None; cur = None; blk = None
dx = collections.defaultdict(collections.Counter)
for i in range(0, len(L) - 1, 2):
    g, v = L[i].strip(), L[i + 1].strip()
    if g == '0':
        cur = v
        if v == 'SECTION': sec = None
        elif v == 'ENDSEC': sec = None
        elif sec == 'ENTITIES' and v not in ('ENDSEC',): dx['*Model_Space'][v] += 1
        elif sec == 'BLOCKS' and v not in ('BLOCK', 'ENDBLK', 'ENDSEC') and blk: dx[blk][v] += 1
    elif g == '2' and cur == 'SECTION': sec = v
    elif g == '2' and cur == 'BLOCK' and sec == 'BLOCKS': blk = v
mine = collections.defaultdict(collections.Counter)
for b, e in m.entities():
    mine[b][e['kind']] += 1
ok = bad = 0; det = []
for b in dx:
    for k in ('LINE', 'LWPOLYLINE', 'INSERT', 'TEXT', 'ARC', 'CIRCLE'):
        a, c = mine[b][k], dx[b][k]
        if a == c: ok += 1
        else: bad += 1; det.append((b, k, a, c))
print('block/type pairs equal', ok, 'differ', bad)
print(det[:8])
