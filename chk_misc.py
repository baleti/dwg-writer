import sys, dwgload, dwgent
d = dwgload.load(open(sys.argv[1], 'rb').read())
L = open(sys.argv[2], errors='replace').read().split('\n')
dx = {'CIRCLE': set(), 'ARC': set(), 'TEXT': set()}; cur = None; sec = None
def fin(c):
    if c and sec in ('ENTITIES', 'BLOCKS') and c['t'] in dx:
        dx[c['t']].add((round(c.get('10', 0), 3), round(c.get('20', 0), 3), round(c.get('40', 0), 3), c.get('1', '') if c['t'] == 'TEXT' else ''))
for i in range(0, len(L) - 1, 2):
    g, v = L[i].strip(), L[i + 1].rstrip('\r')
    if g == '0':
        fin(cur); cur = {'t': v.strip()}
        if v.strip() == 'SECTION': sec = None
    elif g == '2' and cur and cur['t'] == 'SECTION': sec = v.strip()
    elif cur is not None:
        if g == '1' and '1' not in cur: cur['1'] = v
        elif g in ('10', '20', '40'):
            try: cur.setdefault(g, float(v))
            except ValueError: pass
mine = {'CIRCLE': set(), 'ARC': set(), 'TEXT': set()}; err = 0
for o in d['objects'].values():
    try:
        if o.type in (17, 18):
            e = dwgent.decode_circle_arc(o); mine[e['kind']].add((round(e['center'][0], 3), round(e['center'][1], 3), round(e['radius'], 3), ''))
        elif o.type == 1:
            e = dwgent.decode_text(o)
            if 'text' in e: mine['TEXT'].add((round(e['ins'][0], 3), round(e['ins'][1], 3), round(e['height'], 3), e['text']))
    except Exception: err += 1
for k in mine: print(k, 'mine', len(mine[k]), 'oracle', len(dx[k]), 'oracle found', len(dx[k] & mine[k]))
print('errors', err)
if len(sys.argv) > 3:
    print(sorted(mine['TEXT'])[:3]); print(sorted(dx['TEXT'])[:3])
