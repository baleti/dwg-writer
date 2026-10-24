"""MLEADERSTYLE records vs AutoCAD drawing.dxf (matched by handle): usage chk_mleaderstyle_dxf.py FILE.dwg DRAWING.dxf"""
import sys, dwgmodel
FIELDS = {170: 'content_type', 171: 'draw_mleader_order', 172: 'draw_leader_order', 90: 'max_points', 40: 'first_angle', 41: 'second_angle', 173: 'leader_type',
          92: 'line_weight', 290: 'landing', 42: 'landing_gap', 291: 'dogleg', 43: 'dogleg_length', 44: 'arrow_size', 174: 'text_left_attach', 178: 'text_right_attach',
          175: 'text_angle_type', 176: 'text_align', 45: 'text_height', 292: 'text_frame', 297: 'text_always_left', 46: 'align_space', 293: 'block_scale_on',
          141: 'block_rotation', 294: 'block_rotation_on', 177: 'block_connection', 142: 'scale', 295: 'overwrite', 296: 'annotative', 143: 'break_gap'}
def dxf_styles(path):
    L = [l.rstrip('\n') for l in open(path, encoding='latin-1')]
    out = []; i = 0
    while i + 1 < len(L):
        if L[i].strip() == '0' and L[i+1] == 'MLEADERSTYLE':
            j = i + 2; g = {}
            while j + 1 < len(L) and L[j].strip() != '0':
                g.setdefault(int(L[j]), L[j+1]); j += 2
            out.append(g); i = j
        else: i += 1
    return out
if __name__ == '__main__':
    m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
    mine = {format(h, 'X'): d for h, d in m.mleaderstyles().items()}
    ok = bad = 0
    for g in dxf_styles(sys.argv[2]):
        d = mine.get(g.get(5))
        if d is None: bad += 1; print('missing', g.get(5)); continue
        for c, k in FIELDS.items():
            if c not in g: continue
            a = d[k]; b = float(g[c])
            if k == 'line_weight' and a > 2**31: a -= 2**32
            if k in ('first_angle', 'second_angle', 'block_rotation'): b = b  # DXF writes degrees? compared raw below
            if abs(a - b) < 1e-9: ok += 1
            else: bad += 1; print('diff', g.get(5), k, a, b)
    print('equal', ok, 'differ', bad)
