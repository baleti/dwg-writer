"""Oracle comparison: per-type entity counts of our R2000 decoder vs an ODA-converted DXF (BLOCKS+ENTITIES sections). Usage: compare_dxf.py file.dwg file.dxf"""
import sys, collections
import dwgobj as O
TYPES = {19: 'LINE', 1: 'TEXT', 17: 'ARC', 18: 'CIRCLE', 77: 'LWPOLYLINE', 7: 'INSERT'}


def dxf_counts(path):
    L = open(path, errors='replace').read().split('\n')
    c = collections.Counter(); sec = None
    for i in range(0, len(L) - 1, 2):
        g, v = L[i].strip(), L[i + 1].strip()
        if g == '0' and v == 'SECTION': sec = L[i + 3].strip()
        elif g == '0' and sec in ('ENTITIES', 'BLOCKS'): c[v] += 1
    return c


if __name__ == '__main__':
    d = O.load_r2000(open(sys.argv[1], 'rb').read())
    mine = collections.Counter(TYPES[o.type] for o in d['objects'].values() if o.type in TYPES)
    theirs = dxf_counts(sys.argv[2])
    for k in TYPES.values():
        print(f'{k:11s} mine {mine[k]:6d} oracle {theirs[k]:6d} {"OK" if mine[k]==theirs[k] else "DIFF"}')
