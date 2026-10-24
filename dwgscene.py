"""Flatten a Model into 2D drawing primitives per layout (for viewers / SVG). Own code.
Primitive tuples: ('line', pts[list of (x,y)], layer, color) ; ('text', (x,y), height, rotation_rad, string, layer, color, style) ; ('hatch', loops, layer, color, solid)
"""
import math
import dwgmodel

# ---- ACI palette (generated, public knowledge: hue steps of 15 degrees, 10 shades per hue) ----
def _aci_palette():
    base = {0: (0, 0, 0), 1: (255, 0, 0), 2: (255, 255, 0), 3: (0, 255, 0), 4: (0, 255, 255), 5: (0, 0, 255), 6: (255, 0, 255), 7: (255, 255, 255),
            8: (65, 65, 65), 9: (128, 128, 128)}
    pal = dict(base)
    import colorsys
    vals = [(1.0, 1.0), (0.5, 1.0), (1.0, 0.8), (0.5, 0.8), (1.0, 0.6), (0.5, 0.6), (1.0, 0.5), (0.5, 0.5), (1.0, 0.3), (0.5, 0.3)]
    for i in range(10, 250):
        hue = ((i - 10) // 10) * 15.0 / 360.0
        s, v = vals[(i - 10) % 10]
        r, g, b = colorsys.hsv_to_rgb(hue, s, v)
        pal[i] = (round(r * 255), round(g * 255), round(b * 255))
    for k, g in enumerate((51, 91, 132, 173, 214, 255)):
        pal[250 + k] = (g, g, g)
    return pal


ACI = _aci_palette()


def _norm(v):
    n = math.sqrt(sum(c * c for c in v))
    return tuple(c / n for c in v) if n else v


def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def ocs_axes(n):
    """Arbitrary axis algorithm."""
    n = _norm(n)
    if abs(n[0]) < 1 / 64 and abs(n[1]) < 1 / 64:
        ax = _norm(_cross((0, 1, 0), n))
    else:
        ax = _norm(_cross((0, 0, 1), n))
    ay = _norm(_cross(n, ax))
    return ax, ay, n


def ocs_to_wcs(p, n):
    if n == (0.0, 0.0, 1.0):
        return p
    ax, ay, az = ocs_axes(n)
    return tuple(ax[i] * p[0] + ay[i] * p[1] + az[i] * (p[2] if len(p) > 2 else 0.0) for i in range(3))


class Mat:
    """2D affine (a b tx; c d ty) used for INSERT nesting."""
    __slots__ = ('a', 'b', 'c', 'd', 'tx', 'ty')

    def __init__(self, a=1.0, b=0.0, c=0.0, d=1.0, tx=0.0, ty=0.0):
        self.a, self.b, self.c, self.d, self.tx, self.ty = a, b, c, d, tx, ty

    def apply(self, x, y):
        return (self.a * x + self.b * y + self.tx, self.c * x + self.d * y + self.ty)

    def mul(self, o):  # self after o
        return Mat(self.a * o.a + self.b * o.c, self.a * o.b + self.b * o.d, self.c * o.a + self.d * o.c, self.c * o.b + self.d * o.d,
                   self.a * o.tx + self.b * o.ty + self.tx, self.c * o.tx + self.d * o.ty + self.ty)

    def det(self):
        return self.a * self.d - self.b * self.c

    def rot(self):
        return math.atan2(self.c, self.a)

    def scale_x(self):
        return math.hypot(self.a, self.c)


def arc_points(cx, cy, r, a0, a1, ccw=True, step=None):
    if ccw:
        while a1 <= a0: a1 += 2 * math.pi
    else:
        while a1 >= a0: a1 -= 2 * math.pi
    n = max(8, int(abs(a1 - a0) / (2 * math.pi) * 64) + 1)
    return [(cx + r * math.cos(a0 + (a1 - a0) * i / n), cy + r * math.sin(a0 + (a1 - a0) * i / n)) for i in range(n + 1)]


def bulge_points(p0, p1, bulge, n=24):
    if abs(bulge) < 1e-12:
        return [p1]
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    d = math.hypot(dx, dy)
    if d == 0: return [p1]
    theta = 4 * math.atan(bulge)
    r = d / (2 * math.sin(theta / 2))
    # centre
    mx, my = (p0[0] + p1[0]) / 2, (p0[1] + p1[1]) / 2
    h = r * math.cos(theta / 2)
    nx, ny = -dy / d, dx / d
    cx, cy = mx + nx * h, my + ny * h
    a0 = math.atan2(p0[1] - cy, p0[0] - cx)
    pts = []
    m = max(2, int(abs(theta) / (2 * math.pi) * 64) + 1)
    for i in range(1, m + 1):
        a = a0 + theta * i / m
        pts.append((cx + abs(r) * math.cos(a), cy + abs(r) * math.sin(a)))
    pts[-1] = p1
    return pts


def fit_to_nurbs(fit, t0=None, t1=None):
    """Cubic clamped B-spline through fit points exactly as AutoCAD derives it (verified against AutoCAD's control points 11 of 11 by c6, and 7 of 7 here):
    chord-length parameters, knots [0]*4 + t_1..t_(n-2) + [T]*4, n fit points -> n+2 control points, end conditions = the given tangents when non-zero,
    else natural (second derivative zero). Returns (knots, ctrl) or None."""
    n = len(fit) - 1
    pts = [tuple(p[:3]) for p in fit]
    u = [0.0]
    for i in range(n):
        u.append(u[-1] + math.dist(pts[i], pts[i + 1]))
    if n < 1 or u[-1] <= 0: return None
    T = u[-1]
    knots = [u[0]] * 4 + u[1:n] + [T] * 4
    m = n + 3
    def nb(i, k, t):
        return _nb(knots, i, k, t, T)
    def d1(i, t):
        a = b = 0.0
        den = knots[i + 3] - knots[i]
        if den > 1e-14: a = 3.0 / den * nb(i, 2, t)
        den = knots[i + 4] - knots[i + 1]
        if den > 1e-14: b = 3.0 / den * nb(i + 1, 2, t)
        return a - b
    def d2(i, t):
        # second derivative of the cubic basis: 3/(k_{i+3}-k_i) * N'_{i,2} - 3/(k_{i+4}-k_{i+1}) * N'_{i+1,2}, N' of degree 2 = 2/(..)*N_{.,1} - 2/(..)*N_{.,1}
        def dn2(j, tt):
            a = b = 0.0
            den = knots[j + 2] - knots[j]
            if den > 1e-14: a = 2.0 / den * nb(j, 1, tt)
            den = knots[j + 3] - knots[j + 1]
            if den > 1e-14: b = 2.0 / den * nb(j + 1, 1, tt)
            return a - b
        a = b = 0.0
        den = knots[i + 3] - knots[i]
        if den > 1e-14: a = 3.0 / den * dn2(i, t)
        den = knots[i + 4] - knots[i + 1]
        if den > 1e-14: b = 3.0 / den * dn2(i + 1, t)
        return a - b
    te = T - 1e-12
    have0 = bool(t0) and any(t0); have1 = bool(t1) and any(t1)
    A = [[nb(c, 3, u[0]) for c in range(m)]]
    A.append([d1(c, u[0]) for c in range(m)] if have0 else [d2(c, u[0]) for c in range(m)])
    for t in u[1:n]: A.append([nb(c, 3, t) for c in range(m)])
    A.append([d1(c, te) for c in range(m)] if have1 else [d2(c, te) for c in range(m)])
    A.append([nb(c, 3, T) for c in range(m)])
    rhs = [pts[0], tuple(t0) if have0 else (0.0, 0.0, 0.0)] + pts[1:n] + [tuple(t1) if have1 else (0.0, 0.0, 0.0), pts[n]]
    ctrl = []
    for c in range(3):
        M = [A[r][:] + [rhs[r][c]] for r in range(m)]
        for col in range(m):
            piv = max(range(col, m), key=lambda r: abs(M[r][col]))
            if abs(M[piv][col]) < 1e-14: return None
            M[col], M[piv] = M[piv], M[col]
            for r in range(m):
                if r != col and M[r][col]:
                    f = M[r][col] / M[col][col]
                    M[r] = [x - f * y for x, y in zip(M[r], M[col])]
        ctrl.append([M[r][m] / M[r][r] for r in range(m)])
    return knots, [(ctrl[0][i], ctrl[1][i], ctrl[2][i]) for i in range(m)]


def _nb(knots, i, k, t, tend):
    if k == 0:
        return 1.0 if (knots[i] <= t < knots[i + 1]) or (t == tend and knots[i] < knots[i + 1] == tend) else 0.0
    a = b = 0.0
    d1 = knots[i + k] - knots[i]
    if d1 > 1e-14: a = (t - knots[i]) / d1 * _nb(knots, i, k - 1, t, tend)
    d2 = knots[i + k + 1] - knots[i + 1]
    if d2 > 1e-14: b = (knots[i + k + 1] - t) / d2 * _nb(knots, i + 1, k - 1, t, tend)
    return a + b


def bspline_points(deg, knots, ctrl, weights=None, n=None):
    """Evaluate a (rational) B-spline with the Cox-de Boor recursion."""
    m = len(ctrl)
    if m == 0 or len(knots) < m + deg + 1:
        return [(c[0], c[1]) for c in ctrl]
    t0, t1 = knots[deg], knots[m]
    n = n or max(16, 8 * m)

    def basis(i, k, t):
        if k == 0:
            return 1.0 if (knots[i] <= t < knots[i + 1]) or (t == t1 and knots[i] < knots[i + 1] == t1) else 0.0
        a = b = 0.0
        d1 = knots[i + k] - knots[i]
        if d1 > 1e-14: a = (t - knots[i]) / d1 * basis(i, k - 1, t)
        d2 = knots[i + k + 1] - knots[i + 1]
        if d2 > 1e-14: b = (knots[i + k + 1] - t) / d2 * basis(i + 1, k - 1, t)
        return a + b

    pts = []
    for s in range(n + 1):
        t = t0 + (t1 - t0) * s / n
        x = y = w = 0.0
        for i in range(m):
            bv = basis(i, deg, t)
            if bv:
                wi = weights[i] if weights else 1.0
                x += bv * wi * ctrl[i][0]; y += bv * wi * ctrl[i][1]; w += bv * wi
        if w: pts.append((x / w, y / w))
    return pts


class Scene:
    def __init__(self, buf):
        self.m = dwgmodel.Model(buf)
        self.by_block = {}
        verts = {}
        for blk, e in self.m.entities():
            self.by_block.setdefault(blk, []).append(e)
        self.blk_base = {}
        for h, o in self.m.objs.items():
            if o.type == 49:
                try:
                    import dwgtab
                    bh = dwgtab.decode_block_header(o)
                    self.blk_base[bh['name']] = bh['base']
                except Exception:
                    pass
        self._group_polylines()
        self._apply_draw_order()

    def _apply_draw_order(self):
        """SORTENTSTABLE draw order: stable sort of each block's entities by sort key (default: own handle)."""
        order = self.m.draw_order()
        if not order: return
        names = self.m.blocks
        for bh, keys in order.items():
            ents = self.by_block.get(names.get(bh))
            if ents: ents.sort(key=lambda e: keys.get(e['handle'], e['handle']))

    def _group_polylines(self):
        """Attach VERTEX2D entities to their POLYLINE2D by handle order (vertices follow the polyline until SEQEND)."""
        for blk, ents in self.by_block.items():
            ents.sort(key=lambda e: e['handle'])
            cur = None
            for e in ents:
                if e['kind'] in ('POLYLINE2D', 'POLYLINE3D', 'POLYLINE_PFACE', 'POLYLINE_MESH'):
                    cur = e; e['verts'] = e.pop('verts_pre', []); e['faces'] = e.pop('faces_pre', [])
                elif e['kind'] in ('VERTEX2D', 'VERTEX3D', 'VERTEX_PFACE', 'VERTEX_MESH') and cur is not None:
                    cur['verts'].append(e)
                elif e['kind'] == 'VERTEX_PFACE_FACE' and cur is not None:
                    cur['faces'].append(e)
                elif e['kind'] == 'SEQEND':
                    cur = None

    def color_of(self, e, layer_color=7):
        ef = self.m.effective(e)
        if ef['rgb'] is not None: return ef['rgb']
        return ef['color'] if ef['color'] else layer_color

    def line_style(self, e, mat):
        """(lineweight_mm or None, dash tuple or None) for an entity; dashes are drawing-space lengths, abs values alternate dash/gap."""
        ef = self.m.effective(e)
        dash = None
        lt = self.m.ltypes().get(ef['ltype']) if ef['ltype'] else None
        if lt and lt['dashes']:
            sx = mat.scale_x()
            dash = tuple(abs(d['length']) * sx for d in lt['dashes'])
            if not any(dash): dash = None
        return ef['lineweight_mm'], dash

    def layer_color(self, name):
        d = self.m.layer_table().get(name)
        if not d: return 7
        return d['true_color'] if d.get('true_color') else (d['color'] or 7)

    def block_content(self, name):
        return self.by_block.get(name, [])

    def hidden_layers(self):
        if not hasattr(self, '_hidden'):
            self._hidden = set()
            for n, d in self.m.layer_table().items():
                if d['frozen'] or d['off']: self._hidden.add(n)
        return self._hidden

    def flatten(self, block_name, mat=None, depth=0, parent_color=None, hide=None, parent_style=None):
        mat = mat or Mat()
        out = []
        if depth > 8: return out
        hide = self.hidden_layers() if hide is None else hide
        pend = None

        def finish():
            if pend is None: return
            for j in range(pend[0], len(out)):
                if out[j][0] == 'line' and len(out[j]) == 4: out[j] = out[j] + pend[1:]
        for e in self.block_content(block_name):
            finish(); pend = None
            k = e['kind']
            if e.get('layer') in hide or (e.get('invis') and k != 'ATTDEF'): continue
            if k in ('ATTDEF',): continue
            lc = self.layer_color(e['layer']) if e.get('layer') else 7
            col = self.color_of(e, lc if isinstance(lc, int) else 7)
            if col == 0 and parent_color is not None: col = parent_color  # ByBlock
            layer = e.get('layer')
            st = self.line_style(e, mat)
            if parent_style is not None:  # ByBlock lineweight / linetype take the INSERT's
                if e.get('lweight') == 30: st = (parent_style[0], st[1])
                if self.m.effective(e)['ltype'] == 'ByBlock': st = (st[0], parent_style[1])
            pend = (len(out),) + st
            ext = tuple(e.get('ext', (0.0, 0.0, 1.0)))
            def W(x, y, z=0.0):
                wx, wy, wz = ocs_to_wcs((x, y, z), ext)
                return mat.apply(wx, wy)
            if k == 'LINE':
                out.append(('line', [mat.apply(e['p1'][0], e['p1'][1]), mat.apply(e['p2'][0], e['p2'][1])], layer, col))
            elif k == 'CIRCLE':
                c = e['center']
                out.append(('line', [W(x, y, c[2]) for x, y in arc_points(c[0], c[1], e['radius'], 0, 2 * math.pi)], layer, col))
            elif k == 'ARC':
                c = e['center']
                out.append(('line', [W(x, y, c[2]) for x, y in arc_points(c[0], c[1], e['radius'], e['a0'], e['a1'])], layer, col))
            elif k == 'OLE2FRAME' and e.get('bounds'):
                x0, y0, x1, y1 = e['bounds']
                out.append(('line', [mat.apply(x0, y0), mat.apply(x1, y0), mat.apply(x1, y1), mat.apply(x0, y1), mat.apply(x0, y0)], layer, col))
            elif k in ('REGION', '3DSOLID', 'BODY', 'SURFACE', 'EXTRUDEDSURFACE', 'LOFTEDSURFACE', 'REVOLVEDSURFACE', 'SWEPTSURFACE', 'PLANESURFACE', 'NURBSURFACE'):  # ACIS wireframe seen from above (edges as lines, ellipses exact)
                try:
                    import dwgacis
                    w = e.get('_wire')
                    if w is None:
                        pr = dwgacis.parse(e); w = e['_wire'] = dwgacis.wire(pr[1]) if pr else []
                    for seg in w: out.append(('line', [mat.apply(p[0], p[1]) for p in seg], layer, col))
                except Exception:
                    pass
            elif k == 'ELLIPSE':
                c = e['center']; mj = e['major']; r = e['ratio']
                a, b = mj[0], mj[1]
                a0, a1 = e['a0'], e['a1']
                if a1 <= a0: a1 += 2 * math.pi
                n = max(24, int((a1 - a0) / (2 * math.pi) * 96))
                pts = []
                for i in range(n + 1):
                    t = a0 + (a1 - a0) * i / n
                    pts.append(mat.apply(c[0] + a * math.cos(t) - b * r * math.sin(t), c[1] + b * math.cos(t) + a * r * math.sin(t)))
                out.append(('line', pts, layer, col))
            elif k == 'LWPOLYLINE':
                pts = e['pts']; bul = e['bulges']
                path = [W(pts[0][0], pts[0][1], e['elev'])] if pts else []
                n = len(pts)
                for i in range(1, n + (1 if e['closed'] else 0)):
                    p0 = pts[i - 1]; p1 = pts[i % n]
                    b = bul[i - 1] if i - 1 < len(bul) else 0.0
                    for q in bulge_points(p0, p1, b):
                        path.append(W(q[0], q[1], e['elev']))
                if path: out.append(('line', path, layer, col))
            elif k == 'POLYLINE2D' and e.get('verts'):
                vs = [(v['p'][0], v['p'][1], v['bulge']) for v in e['verts'] if not (v['flags'] & 16)]
                if vs:
                    path = [W(vs[0][0], vs[0][1])]
                    n = len(vs)
                    for i in range(1, n + (1 if e['closed'] else 0)):
                        p0 = vs[i - 1]; p1 = vs[i % n]
                        for q in bulge_points(p0[:2], p1[:2], p0[2]):
                            path.append(W(q[0], q[1]))
                    out.append(('line', path, layer, col))
            elif k == 'POLYLINE3D' and e.get('verts'):
                vs = [v['p'] for v in e['verts'] if not (v['flags'] & 16)]
                if e['closed'] and vs: vs = vs + [vs[0]]
                out.append(('line', [mat.apply(p[0], p[1]) for p in vs], layer, col))
            elif k == 'POLYLINE_PFACE' and e.get('verts'):
                vp = [v['p'] for v in e['verts']]
                for f in e.get('faces', []):
                    ids = [i for i in f['idx'] if i != 0]
                    seg = []
                    for a, b2 in zip(ids, ids[1:] + ids[:1]):
                        if abs(a) - 1 < len(vp) and abs(b2) - 1 < len(vp) and a > 0:  # a negative index hides the edge that starts there
                            out.append(('line', [mat.apply(vp[abs(a) - 1][0], vp[abs(a) - 1][1]), mat.apply(vp[abs(b2) - 1][0], vp[abs(b2) - 1][1])], layer, col))
            elif k == 'POLYLINE_MESH' and e.get('verts') and e['m'] * e['n'] <= len(e['verts']):
                vp = [v['p'] for v in e['verts']]; M, N = e['m'], e['n']
                for i in range(M):
                    row = [vp[i * N + j] for j in range(N)]
                    if e['n_closed'] and row: row = row + [row[0]]
                    out.append(('line', [mat.apply(p[0], p[1]) for p in row], layer, col))
                for j in range(N):
                    colv = [vp[i * N + j] for i in range(M)]
                    if e['m_closed'] and colv: colv = colv + [colv[0]]
                    out.append(('line', [mat.apply(p[0], p[1]) for p in colv], layer, col))
            elif k == 'LEADER':
                out.append(('line', [mat.apply(p[0], p[1]) for p in e['pts']], layer, col))
            elif k == 'SPLINE':
                if e['ctrl']:
                    pts = bspline_points(e['degree'], e['knots'], e['ctrl'], e['weights'] or None)
                else:
                    pts = [(p[0], p[1]) for p in e['fit']]
                    if len(pts) >= 2 and not e.get('closed'):
                        try:
                            kn = fit_to_nurbs(e['fit'], e.get('tan0'), e.get('tan1'))
                            if kn: pts = bspline_points(3, kn[0], kn[1])
                        except Exception:
                            pass
                if pts: out.append(('line', [mat.apply(x, y) for x, y in pts], layer, col))
            elif k == 'MULTILEADER':
                for pts in e.get('leader_lines') or []:
                    poly = [(p[0], p[1]) for p in pts] + [(e['leader_conn'][0], e['leader_conn'][1]), (e['leader_end'][0], e['leader_end'][1])]
                    out.append(('line', [mat.apply(x, y) for x, y in poly], layer, col))
                if e.get('text_loc') and e.get('strings'):
                    import dwg2text
                    txt = '\n'.join(x for x in (dwg2text.strip_mtext(t).strip() for t in e['strings']) if x)
                    if txt:
                        x, y = mat.apply(e['text_loc'][0], e['text_loc'][1])
                        out.append(('text', (x, y), e['text_height'] * mat.scale_x(), mat.rot(), txt, layer, col, 0))
            elif k in ('SOLID', 'TRACE'):
                p = e['pts']
                loop = [p[0], p[1], p[3], p[2], p[0]]
                out.append(('line', [W(x, y, e['elev']) for x, y in loop], layer, col))
            elif k == 'MLINE':
                for ln in e['lines']:
                    pts = [mat.apply(q[0], q[1]) for q in ln]
                    if e['closed'] and len(pts) > 2: pts.append(pts[0])
                    if len(pts) > 1: out.append(('line', pts, layer, col))
            elif k == '3DFACE':
                p = e['pts']
                out.append(('line', [mat.apply(q[0], q[1]) for q in (p[0], p[1], p[2], p[3], p[0])], layer, col))
            elif k == 'POINT':
                x, y = mat.apply(e['p'][0], e['p'][1])
                out.append(('line', [(x - 0.5, y), (x + 0.5, y)], layer, col))
            elif k in ('TEXT', 'ATTRIB'):
                if e.get('text'):
                    x, y = W(e['align'][0] if e.get('halign') or e.get('valign') else e['ins'][0], e['align'][1] if e.get('halign') or e.get('valign') else e['ins'][1], e['elev'])
                    out.append(('text', (x, y), e['height'] * mat.scale_x(), e['rot'] + mat.rot(), e['text'], layer, col, e.get('halign', 0)))
            elif k == 'MTEXT':
                x, y = mat.apply(e['ins'][0], e['ins'][1])
                ang = math.atan2(e['xdir'][1], e['xdir'][0]) + mat.rot()
                out.append(('text', (x, y), e['text_height'] * mat.scale_x(), ang, e['text'], layer, col, ('mtext', e['attachment'])))
            elif k == 'HATCH':
                loops = []
                for p in e['paths']:
                    pts = []
                    for sg in p['segs']:
                        if sg[0] == 'P': pts.append(sg[1])
                        elif sg[0] == 'L': pts.extend([sg[1], sg[2]])
                        elif sg[0] == 'A':
                            for x, y in arc_points(sg[1][0], sg[1][1], sg[2], sg[3], sg[4], bool(sg[5])): pts.append((x, y))
                        elif sg[0] == 'E':
                            c = sg[1]; mj = sg[2]; r = sg[3]; a0, a1 = sg[4], sg[5]
                            if a1 <= a0: a1 += 2 * math.pi
                            for i in range(33):
                                t = a0 + (a1 - a0) * i / 32
                                pts.append((c[0] + mj[0] * math.cos(t) - mj[1] * r * math.sin(t), c[1] + mj[1] * math.cos(t) + mj[0] * r * math.sin(t)))
                        elif sg[0] == 'S':
                            pts.extend(bspline_points(sg[1], sg[4], [c[0] for c in sg[5]], [c[1] for c in sg[5]]) if False else [c[0] for c in sg[5]])
                    if pts: loops.append([W(x, y, e['elev']) for x, y in pts])
                out.append(('hatch', loops, layer, col, bool(e['solid'])))
            elif k in ('INSERT', 'MINSERT') or (k == 'ACAD_TABLE' and 'ins' in e):
                bname = e.get('block_ref')
                if bname is None: continue
                base = self.blk_base.get(bname, (0.0, 0.0, 0.0))
                sx, sy, sz = e['scale']
                ins = ocs_to_wcs(e['ins'], ext)
                c, s = math.cos(e['rot']), math.sin(e['rot'])
                ncol, nrow = (max(e.get('cols', 1), 1), max(e.get('rows', 1), 1)) if k == 'MINSERT' else (1, 1)
                if ncol * nrow > 40000: continue
                for ir in range(nrow):
                    for ic in range(ncol):
                        # array offset in the rotated insert frame (not scaled); block space -> world: translate(ins) * rotate * scale * translate(-base)
                        dx = ic * e.get('col_spacing', 0.0) if k == 'MINSERT' else 0.0
                        dy = ir * e.get('row_spacing', 0.0) if k == 'MINSERT' else 0.0
                        ox, oy = ins[0] + c * dx - s * dy, ins[1] + s * dx + c * dy
                        m2 = Mat(c * sx, -s * sy, s * sx, c * sy, ox, oy).mul(Mat(1, 0, 0, 1, -base[0], -base[1]))
                        out.extend(self.flatten(bname, mat.mul(m2), depth + 1, parent_color=col, hide=hide, parent_style=st))
            elif k.startswith('DIM_'):
                bname = e.get('block_ref')
                if bname: out.extend(self.flatten(bname, mat, depth + 1, hide=hide))
        finish()
        return out


def clip_polyline(pts, xmin, ymin, xmax, ymax):
    """Liang-Barsky clip of a polyline against a rectangle: returns list of polylines."""
    out = []; cur = []
    for i in range(len(pts) - 1):
        x0, y0 = pts[i]; x1, y1 = pts[i + 1]
        dx, dy = x1 - x0, y1 - y0
        t0, t1 = 0.0, 1.0
        ok = True
        for p, q in ((-dx, x0 - xmin), (dx, xmax - x0), (-dy, y0 - ymin), (dy, ymax - y0)):
            if p == 0:
                if q < 0: ok = False; break
            else:
                t = q / p
                if p < 0:
                    if t > t1: ok = False; break
                    t0 = max(t0, t)
                else:
                    if t < t0: ok = False; break
                    t1 = min(t1, t)
        if not ok:
            if len(cur) > 1: out.append(cur)
            cur = []
            continue
        a = (x0 + t0 * dx, y0 + t0 * dy); b = (x0 + t1 * dx, y0 + t1 * dy)
        if cur and abs(cur[-1][0] - a[0]) < 1e-9 and abs(cur[-1][1] - a[1]) < 1e-9:
            cur.append(b)
        else:
            if len(cur) > 1: out.append(cur)
            cur = [a, b]
        if t1 < 1.0:
            out.append(cur); cur = []
    if len(cur) > 1: out.append(cur)
    return out


def render_layout(sc, lay):
    """Paper-space primitives of a layout: own entities + each viewport's model-space content (rectangular clip, frozen layers, scale, twist)."""
    m = sc.m
    prims = list(sc.flatten(lay['block_name'] if lay['block'] is None else m.blocks[lay['block']]))
    ox, oy = lay.get('origin', (0.0, 0.0))
    border = [(ox, oy), (ox + lay['paper'][0], oy), (ox + lay['paper'][0], oy + lay['paper'][1]), (ox, oy + lay['paper'][1]), (ox, oy)]
    if lay['name'].lower() == 'model': return prims
    prims.append(('line', border, None, 8))
    model_name = next((n for n in m.blocks.values() if n.lower() == '*model_space'), None)
    for vh in lay['viewports']:
        o = m.objs[vh]
        try:
            import dwgent
            v = m.decode_viewport(o) if hasattr(m, 'decode_viewport') else dwgent.decode_viewport(o)
        except Exception:
            continue
        if v['width'] <= 0 or v['height'] <= 0 or v['view_height'] <= 0: continue
        pc = v['center']
        if v.get('overall', abs(v['view_center'][0] - pc[0]) < 1e-6 and abs(v['view_center'][1] - pc[1]) < 1e-6 and abs(v['view_height'] - v['height']) < 1e-6):
            continue  # the paper-space overall viewport
        # frozen layers of this viewport
        if hasattr(m, 'viewport_frozen'):
            frozen = m.viewport_frozen(o)
        else:
            hs = dwgmodel.resolve_handles(o)
            first_layer = next((x for c, x in hs if c == 5), None)
            frozen = set()
            for c, x in hs:
                if x in m.objs and m.objs[x].type == 51 and x != first_layer and len(frozen) < v['nfrozen']:
                    frozen.add(m.layers.get(x))
        hide = set(sc.hidden_layers()) | frozen
        s = v['height'] / v['view_height']
        tx, ty = v['view_target'][0], v['view_target'][1]
        tw = v['twist']
        ct, st = math.cos(-tw), math.sin(-tw)
        vcx, vcy = v['view_center']
        # model -> paper: p = pc + s * (R(-twist) * (P - target) - viewcenter)
        a, b, c_, d = s * ct, -s * st, s * st, s * ct
        mt = Mat(a, b, c_, d, pc[0] - s * (ct * (0) - 0) - s * (vcx * 1) * 0, 0)
        # compose explicitly: translate(-target) then rotate/scale then translate(pc - s*viewcenter)
        M = Mat(1, 0, 0, 1, pc[0] - s * vcx, pc[1] - s * vcy).mul(Mat(s * ct, -s * st, s * st, s * ct, 0, 0)).mul(Mat(1, 0, 0, 1, -tx, -ty))
        content = sc.flatten(model_name, M, hide=hide)
        xmin, xmax = pc[0] - v['width'] / 2, pc[0] + v['width'] / 2
        ymin, ymax = pc[1] - v['height'] / 2, pc[1] + v['height'] / 2
        for p in content:
            if p[0] == 'line':
                for seg in clip_polyline(p[1], xmin, ymin, xmax, ymax): prims.append(('line', seg, p[2], p[3]) + tuple(p[4:]))
            elif p[0] == 'text':
                if xmin <= p[1][0] <= xmax and ymin <= p[1][1] <= ymax: prims.append(p)
            elif p[0] == 'hatch':
                loops = []
                for l in p[1]:
                    cl = [(min(max(x, xmin), xmax), min(max(y, ymin), ymax)) for x, y in l]
                    loops.append(cl)
                prims.append(('hatch', loops, p[2], p[3], p[4]))
        prims.append(('line', [(xmin, ymin), (xmax, ymin), (xmax, ymax), (xmin, ymax), (xmin, ymin)], None, 8))
    return prims
