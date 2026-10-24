"""MLINESTYLE per name vs AutoCAD drawing.dxf: usage chk_mlstyle_dxf.py FILE.dwg DRAWING.dxf"""
import sys, math, dwgmodel
def dxf_styles(path):
    L = [l.rstrip('\n') for l in open(path, encoding='latin-1')]
    out = {}; i = 0
    while i + 1 < len(L):
        if L[i].strip() == '0' and L[i+1] == 'MLINESTYLE':
            j = i + 2; g = []
            while j + 1 < len(L) and L[j].strip() != '0':
                g.append((int(L[j]), L[j+1])); j += 2
            d = dict(els=[])
            for c, v in g:
                if c == 2: d['name'] = v
                elif c == 70: d['flags'] = int(v)
                elif c == 51: d['a0'] = float(v)
                elif c == 52: d['a1'] = float(v)
                elif c == 49: d['els'].append([float(v), None])
                elif c == 62 and d['els'] and d['els'][-1][1] is None: d['els'][-1][1] = int(v)
            out[d['name']] = d; i = j
        else: i += 1
    return out
if __name__ == '__main__':
    m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
    mine = m.mlstyles(); ref = dxf_styles(sys.argv[2])
    ok = bad = 0
    for n, d in ref.items():
        k = next((x for x in mine if x.upper() == n.upper()), None)
        if k is None: bad += 1; print('missing', n); continue
        s = mine[k]
        good = s['flags'] == d['flags'] and len(s['elements']) == len(d['els']) and all(abs(e['offset'] - x[0]) < 1e-9 and (x[1] is None or e['color'] == x[1]) for e, x in zip(s['elements'], d['els'])) and abs(math.degrees(s['start_angle']) - d['a0']) < 1e-6 and abs(math.degrees(s['end_angle']) - d['a1']) < 1e-6
        if good: ok += 1
        else: bad += 1; print('diff', n, s['flags'], d['flags'], [(e['offset'], e['color']) for e in s['elements']], d['els'])
    print('equal', ok, 'differ', bad)
