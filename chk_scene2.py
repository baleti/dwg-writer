import sys, collections, dwgmodel
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
L = open(sys.argv[2], errors='replace').read().split('\n')
sec = None; cur = None; blk = None
dx = collections.Counter()
for i in range(0, len(L) - 1, 2):
    g, v = L[i].strip(), L[i + 1].strip()
    if g == '0':
        cur = v
        if v in ('SECTION', 'ENDSEC'): sec = None
        elif sec in ('ENTITIES', 'BLOCKS') and v not in ('BLOCK', 'ENDBLK'): dx[v] += 1
    elif g == '2' and cur == 'SECTION': sec = v
mine = collections.Counter(e['kind'] for b, e in m.entities())
for k in sorted(set(dx) | set(mine)):
    if k in ('SECTION','ENDSEC'): continue
    print('%-12s mine %6d oracle %6d %s' % (k, mine[k], dx[k], '' if mine[k] == dx[k] else ('<--' if mine[k] else 'not decoded')))
