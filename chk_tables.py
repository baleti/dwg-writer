import sys, dwgmodel
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
L = open(sys.argv[2], errors='replace').read().split('\n')
cur = None; sec = None; tab = None; layers = []; blocks = []
for i in range(0, len(L) - 1, 2):
    g, v = L[i].strip(), L[i + 1].strip()
    if g == '0':
        if v == 'SECTION': sec = None
        cur = v
    elif g == '2' and cur == 'SECTION': sec = v
    elif g == '2' and cur == 'TABLE': tab = v
    elif g == '2' and cur == 'LAYER' and sec == 'TABLES': layers.append(v)
    elif g == '2' and cur == 'BLOCK_RECORD' and sec == 'TABLES': blocks.append(v)
ml = sorted(m.layers.values()); mb = sorted(m.blocks.values())
print('layers mine', len(ml), 'oracle', len(layers), 'common', len(set(ml) & set(layers)))
print('blocks mine', len(mb), 'oracle', len(blocks), 'common', len(set(mb) & set(blocks)))
print([x for x in ml if x not in layers][:5], [x for x in layers if x not in ml][:5])
print([x for x in mb if x not in blocks][:5], [x for x in blocks if x not in mb][:5])
