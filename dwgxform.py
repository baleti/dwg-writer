"""Geometric edits on decoded entities (own code): translate / rotate / uniform scale / mirror in the XY plane (z follows translate and scale).
    doc.transform(h, Transform.rotate((cx, cy), angle_rad))   # any entity with a codec; dimension blocks and attributes follow"""
import math

TWO_PI = 2 * math.pi


class Transform:
    """x' = A x + t on the XY plane; `refl` marks a reflection (A has negative determinant); `s` is the uniform scale factor."""

    def __init__(self, a=1.0, b=0.0, c=0.0, d=1.0, tx=0.0, ty=0.0, tz=0.0, s=1.0, refl=False, zs=1.0, mirror_axis=0.0):
        self.a, self.b, self.c, self.d, self.tx, self.ty, self.tz, self.s, self.refl, self.zs, self.axis = a, b, c, d, tx, ty, tz, s, refl, zs, mirror_axis
        self.rot = math.atan2(c, a) if not refl else 0.0

    @staticmethod
    def translate(dx, dy, dz=0.0):
        return Transform(tx=dx, ty=dy, tz=dz)

    @staticmethod
    def rotate(center, ang):
        c, s = math.cos(ang), math.sin(ang)
        cx, cy = center[0], center[1]
        return Transform(c, -s, s, c, cx - (c * cx - s * cy), cy - (s * cx + c * cy))

    @staticmethod
    def scale(center, f):
        cx, cy = center[0], center[1]
        return Transform(f, 0.0, 0.0, f, cx - f * cx, cy - f * cy, 0.0, abs(f), False, f)       # f < 0 is a point reflection = rotation by pi (determinant > 0), not a mirror

    @staticmethod
    def mirror(p1, p2):
        phi = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
        c, s = math.cos(2 * phi), math.sin(2 * phi)
        # reflection about the line through p1 with direction phi
        a, b, cc, d = c, s, s, -c
        tx = p1[0] - (a * p1[0] + b * p1[1]); ty = p1[1] - (cc * p1[0] + d * p1[1])
        return Transform(a, b, cc, d, tx, ty, refl=True, mirror_axis=phi)

    @staticmethod
    def _z(v):
        return 0.0 if abs(v) < 1e-12 else v           # no 6e-17 style residue from cos(pi/2)

    def pt(self, p):
        z = p[2] * self.zs + self.tz if len(p) > 2 else None
        x, y = self._z(self.a * p[0] + self.b * p[1] + self.tx), self._z(self.c * p[0] + self.d * p[1] + self.ty)
        return (x, y) if z is None else (x, y, z)

    def vec(self, v):
        x, y = self._z(self.a * v[0] + self.b * v[1]), self._z(self.c * v[0] + self.d * v[1])
        return (x, y) if len(v) == 2 else (x, y, v[2] * self.zs)

    def ang(self, th):
        """direction angle after the transform"""
        return (2 * self.axis - th) if self.refl else th + self.rot

    def norm(self, a):
        return a % TWO_PI


def _p3(t, p):
    q = t.pt(tuple(p) if len(p) > 2 else tuple(p) + (0.0,))
    return q


def _apply_mleader(d, t, doc):
    """MULTILEADER: points transformed, directions rotated, lengths scaled (no mirror)"""
    if t.refl: raise NotImplementedError('mirror of MULTILEADER')
    def nv(v):
        x = t.vec(v); n = math.sqrt(x[0] ** 2 + x[1] ** 2 + x[2] ** 2) or 1.0
        return (x[0] / n, x[1] / n, x[2] / n)
    for r in d['roots']:
        r['conn'] = t.pt(r['conn']); r['dir'] = nv(r['dir']); r['land'] *= t.s
        r['breaks'] = [(t.pt(a), t.pt(b)) for a, b in r['breaks']]
        for L in r['lines']:
            L['pts'] = [t.pt(p) for p in L['pts']]; L['breaks'] = [(t.pt(a), t.pt(b)) for a, b in L['breaks']]; L['arrow'] *= t.s
    c = d['ctx']
    c['base'] = t.pt(c['base']); c['base2'] = t.pt(c['base2']); c['basedir'] = nv(c['basedir']); c['basevert'] = nv(c['basevert'])
    for k in ('th', 'arrow', 'gap'): c[k] *= t.s
    if c['has_text']:
        c['loc'] = t.pt(c['loc']); c['dir'] = nv(c['dir']); c['rot'] += t.rot
        for k in ('width', 'height', 'colw', 'colg'): c[k] *= t.s
    if c['has_block']:
        c['bloc'] = t.pt(c['bloc']); c['brot'] += t.rot
    d['own']['dlen'] *= t.s; d['own']['asize'] *= t.s
    doc.put(d)
    return [d['handle']]


def apply(doc, h, t):
    """transform entity h in place (stored through doc.put); returns the handles touched"""
    d = doc.get(h)
    ty = d['type']
    touched = [h]
    if d.get('key') == 'MULTILEADER':
        return _apply_mleader(d, t, doc)
    if d.get('key') in ('WIPEOUT', 'IMAGE'):
        d['pt0'] = t.pt(d['pt0']); d['uvec'] = t.vec(d['uvec']); d['vvec'] = t.vec(d['vvec'])      # frame vectors carry rotation, scale and mirror
        doc.put(d)
        return [h]
    if d.get('generic'): raise NotImplementedError('type %d has no geometry codec' % ty)
    if ty == 19:
        d['p1'] = _p3(t, d['p1']); d['p2'] = _p3(t, d['p2'])
    elif ty in (18, 17):
        d['center'] = _p3(t, d['center']); d['radius'] = d['radius'] * t.s
        if ty == 17:
            a0, a1 = d['a0'], d['a1']
            if t.refl: a0, a1 = t.ang(a1), t.ang(a0)
            else: a0, a1 = t.ang(a0), t.ang(a1)
            d['a0'], d['a1'] = t.norm(a0), t.norm(a1)
    elif ty == 27:
        d['p'] = _p3(t, d['p'])
    elif ty == 77:
        d['pts'] = [t.pt(p) for p in d['pts']]
        d['elevation'] = d['elevation'] * t.zs + t.tz
        if d['const_width']: d['const_width'] *= t.s
        d['widths'] = [(a * t.s, b * t.s) for a, b in d['widths']]
        if t.refl: d['bulges'] = [-b for b in d['bulges']]
    elif ty in (1, 2, 3):
        ins = t.pt(d['ins']); d['elev'] = d['elev'] * t.zs + t.tz
        d['align'] = t.pt(d.get('align', d['ins'])); d['ins'] = ins
        d['height'] = d['height'] * t.s
        if not t.refl: d['rot'] = t.norm(d['rot'] + t.rot)
    elif ty == 44:
        d['ins'] = _p3(t, d['ins']); x = t.vec(d['xdir']); n = math.hypot(x[0], x[1]) or 1.0
        d['xdir'] = (t._z(x[0] / n), t._z(x[1] / n), d['xdir'][2])
        d['text_height'] *= t.s; d['width'] *= t.s; d['ext_h'] *= t.s; d['ext_w'] *= t.s; d['rect_height'] = d.get('rect_height', 0.0) * t.s
    elif ty == 7:
        d['ins'] = _p3(t, d['ins'])
        sx, sy, sz = d['scale']
        d['scale'] = (sx * t.s * (-1 if t.refl else 1), sy * t.s, sz * t.s)
        d['rot'] = t.norm(d['rot'] + t.rot) if not t.refl else t.norm(2 * t.axis - d['rot'])
        for a in d.get('attribs', []):
            touched += apply(doc, a, t)
        if doc.ver == 'AC1015' and d['has_attribs']:
            a = d['first_attrib']
            while a:
                ad = doc.get(a); touched += apply(doc, a, t); a = ad['next'] if not ad['xdic_missing'] and ad['next'] != 0 else 0
    elif ty == 35:
        d['center'] = _p3(t, d['center']); m = t.vec(d['major']); d['major'] = (m[0], m[1], m[2])
        if t.refl:
            a0, a1 = d['a0'], d['a1']
            # reflection reverses the sweep direction: the arc runs between the mirrored parameters
            d['a0'], d['a1'] = t.norm(-a1), t.norm(-a0)
            d['ext'] = tuple(d['ext'])
    elif ty in (31, 32):
        d['pts'] = [t.pt(p) for p in d['pts']]; d['elev'] = d['elev'] * t.zs + t.tz
    elif ty == 28:
        d['pts'] = [_p3(t, p) for p in d['pts']]
    elif ty in (40, 41):
        d['p'] = _p3(t, d['p']); v = t.vec(d['v']); n = math.hypot(*v[:2]) or 1.0; d['v'] = (v[0] / n, v[1] / n, d['v'][2])
    elif ty == 36:
        for k in ('ctrl', 'fit'):
            if d.get(k): d[k] = [_p3(t, p) for p in d[k]]
        for k in ('tan0', 'tan1'):
            if d.get(k): d[k] = tuple(t.vec(d[k]))
    elif ty == 78:
        for p in d['paths']:
            segs = []
            for s in p['segs']:
                k = s[0]
                if k == 'P': segs.append(('P', t.pt(s[1]), -s[2] if t.refl else s[2]))
                elif k == 'L': segs.append(('L', t.pt(s[1]), t.pt(s[2])))
                elif k == 'A':
                    c, r, a0, a1, ccw = s[1], s[2], s[3], s[4], s[5]
                    if t.refl: a0, a1, ccw = t.ang(a0), t.ang(a1), 0 if ccw else 1
                    else: a0, a1 = t.ang(a0), t.ang(a1)
                    segs.append(('A', t.pt(c), r * t.s, t.norm(a0), t.norm(a1), ccw))
                elif k == 'E':
                    m = t.vec(s[2])
                    segs.append(('E', t.pt(s[1]), m, s[3], s[4], s[5], s[6] if not t.refl else 1 - s[6]))
                elif k == 'S':
                    _, deg, rat, per, kn, cp, fit = s
                    segs.append(('S', deg, rat, per, kn, [(t.pt(q), w) for q, w in cp], fit))
                else: segs.append(s)
            p['segs'] = segs
        if not d['solid']:
            d['pattern_angle'] = t.norm(t.ang(d['pattern_angle'])); d['pattern_scale'] *= t.s
            nl = []
            for a, base, off, dashes in d['pattern_lines']:
                nl.append((t.norm(t.ang(a)), t.pt(base), tuple(t.vec(off)), [x * t.s for x in dashes]))
            d['pattern_lines'] = nl
        d['seeds'] = [t.pt(p) for p in d['seeds']]
    elif ty == 45:
        d['pts'] = [_p3(t, p) for p in d['pts']]; d['end_proj'] = tuple(t.vec(d['end_proj']))
    elif 20 <= ty <= 26:
        for k in ('pt10', 'pt13', 'pt14', 'pt15'):
            if k in d: d[k] = _p3(t, d[k])
        if 'pt16' in d: d['pt16'] = t.pt(d['pt16'])
        d['text_mid'] = t.pt(d['text_mid'])
        d['measurement'] = d['measurement'] * t.s
        if 'ext_rot' in d and not t.refl: d['ext_rot'] = t.norm(d['ext_rot'] + t.rot)
        if 'dim_rot' in d and not t.refl: d['dim_rot'] = t.norm(d['dim_rot'] + t.rot)
        if d.get('text_rot') and not t.refl: d['text_rot'] = t.norm(d['text_rot'] + t.rot)
        bh = d.get('dimblock')
        if bh and doc.exists(bh):
            for e in doc.chain(bh):
                try: touched += apply(doc, e, t)
                except NotImplementedError: pass    # MTEXT/POINT/LINE/SOLID are covered; unknown kinds are left
    elif ty == 15:
        for v in d['vertices']:
            vd = doc.get(v); vd['p'] = _p3(t, vd['p']); doc.put(vd); touched.append(v)
        d['elev'] = d['elev'] * t.zs + t.tz
    elif ty == 16:
        for v in d['vertices']:
            vd = doc.get(v); vd['p'] = _p3(t, vd['p']); doc.put(vd); touched.append(v)
    else:
        raise NotImplementedError('transform of type %d' % ty)
    doc.put(d)
    return touched
