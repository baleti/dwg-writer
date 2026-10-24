import sys, dwgmodel
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
L = open(sys.argv[2], errors='replace').read().split('\n')
dx = []; cur = None; sec = None
def fin():
    if cur and cur.get('t') == 'MTEXT' and sec in ('ENTITIES', 'BLOCKS'):
        dx.append((''.join(cur['3']) + cur.get('1', ''), round(cur.get('10', 0), 3), round(cur.get('20', 0), 3), round(cur.get('40', 0), 3)))
for i in range(0, len(L) - 1, 2):
    g, v = L[i].strip(), L[i + 1].rstrip('\r')
    if g == '0':
        fin(); cur = {'t': v.strip(), '3': []}
        if v.strip() == 'SECTION': sec = None
    elif g == '2' and cur and cur['t'] == 'SECTION': sec = v.strip()
    elif cur is not None and cur['t'] == 'MTEXT':
        if g == '1': cur['1'] = v
        elif g == '3': cur['3'].append(v)
        elif g in ('10', '20', '40'):
            try: cur.setdefault(g, float(v))
            except ValueError: pass
mine = [(e['text'], round(e['ins'][0], 3), round(e['ins'][1], 3), round(e['text_height'], 3)) for b, e in m.entities() if e['kind'] == 'MTEXT']
sd, sm = set(dx), set(mine)
print('mtext mine', len(mine), 'oracle', len(dx), 'oracle found', len(sd & sm))
print(sorted(sd - sm)[:2]); print(sorted(sm - sd)[:2])
