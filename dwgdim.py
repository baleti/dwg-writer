"""Anonymous geometry block for aligned / linear dimensions (own code): extension lines, dimension line halves, filled arrowheads, MTEXT and
definition points, from the dimension style values. AutoCAD regenerates it anyway; other viewers need it."""
import math


def _fmt(v, dec, lfac=1.0):
    return ('%.*f' % (dec, v * lfac))


def build_linear_block(doc, d, dimstyle_name):
    ds = doc.get(doc.dimstyles()[dimstyle_name.lower()])
    sc = ds['DIMSCALE'] or 1.0
    asz, exo, exe, txt, gap = ds['DIMASZ'] * sc, ds['DIMEXO'] * sc, ds['DIMEXE'] * sc, ds['DIMTXT'] * sc, ds['DIMGAP'] * sc
    p1 = d['pt13'][:2]; p2 = d['pt14'][:2]; q2 = d['pt10'][:2]
    if d['type'] == 21: ang = d['dim_rot']
    else: ang = math.atan2(p2[1] - p1[1], p2[0] - p1[0])
    ux, uy = math.cos(ang), math.sin(ang); nx, ny = -uy, ux
    off = (q2[0] - p2[0]) * nx + (q2[1] - p2[1]) * ny
    q1 = (p1[0] + nx * ((q2[0] - p1[0]) * nx + (q2[1] - p1[1]) * ny), p1[1] + ny * ((q2[0] - p1[0]) * nx + (q2[1] - p1[1]) * ny))
    sgn = 1 if off >= 0 else -1
    ents = []
    def line(a, b): ents.append(('L', a, b))
    for p, q in ((p1, q1), (p2, q2)):
        s = (p[0] + nx * sgn * exo, p[1] + ny * sgn * exo)
        e = (q[0] + nx * sgn * exe, q[1] + ny * sgn * exe)
        line(s, e)
    L = math.dist(q1, q2)
    sign_u = 1 if ((q2[0] - q1[0]) * ux + (q2[1] - q1[1]) * uy) >= 0 else -1
    ex, ey = ux * sign_u, uy * sign_u            # unit vector from q1 to q2
    text = d['user_text'] or ''
    meas = ('%s' % _fmt(d['measurement'], ds['DIMDEC'], ds['DIMLFAC'] or 1.0))
    body = text.replace('<>', meas) if text else meas
    mid = ((q1[0] + q2[0]) / 2, (q1[1] + q2[1]) / 2)
    import dwgfont
    tw = dwgfont.text_width(body, txt) * dwgfont.style_factor(None)
    half = tw / 2 + gap
    tad = ds['DIMTAD']
    if tad == 0 and L > 2 * asz + 2 * half:
        line((q1[0] + ex * asz * 0, q1[1] + ey * 0), (mid[0] - ex * half, mid[1] - ey * half))
        line((q2[0], q2[1]), (mid[0] + ex * half, mid[1] + ey * half))
    else:
        line(q1, q2)
    for tip, dirv in ((q1, (ex, ey)), (q2, (-ex, -ey))):
        b = (tip[0] + dirv[0] * asz, tip[1] + dirv[1] * asz)
        hw = asz / 6
        ents.append(('S', [(b[0] + nx * hw, b[1] + ny * hw), (b[0] - nx * hw, b[1] - ny * hw), tip, tip]))
    tpos = mid if tad == 0 else (mid[0] + nx * sgn * (gap + txt / 2 if False else gap), mid[1] + ny * sgn * gap)
    ents.append(('T', tpos if tad == 0 else (mid[0] + nx * sgn * gap, mid[1] + ny * sgn * gap), '\\A1;' + body, txt, 5 if tad == 0 else 8, ang))
    ents.append(('P', p1)); ents.append(('P', p2)); ents.append(('P', q2))
    d['text_mid'] = tpos if tad == 0 else (mid[0] + nx * sgn * gap, mid[1] + ny * sgn * gap)
    return ents


def make_block(doc, ents, layer='0'):
    bh = doc.add_block('*D')       # anonymous blocks are stored as '*D'; AutoCAD numbers them on load
    bd = doc.get(bh); bd['anonymous'] = 1; doc.put(bd)
    if 'defpoints' not in doc.layers(): doc.add_layer('Defpoints', plot=False)
    for e in ents:
        k = e[0]
        if k == 'L': doc.add_line(e[1], e[2], block=bh, layer=layer, color=0, lweight=-2)
        elif k == 'S': doc.add_solid(e[1], block=bh, layer=layer, color=0)
        elif k == 'T': doc.add_mtext((e[1][0], e[1][1], 0.0), e[2], e[3], attachment=e[4], rot=e[5], block=bh, layer=layer, color=0)
        elif k == 'A': doc.add_arc(e[1], e[2], e[3] % (2 * math.pi), e[4] % (2 * math.pi), block=bh, layer=layer, color=0, lweight=-2)
        elif k == 'P': doc.add_point(e[1], block=bh, layer='Defpoints', color=0)
    return bh


def build_radial_block(doc, d, dimstyle_name):
    """radius (25) and diameter (26) dimensions: d['pt10'] = centre (radius) / far chord point (diameter), d['pt15'] = chord point"""
    ds = doc.get(doc.dimstyles()[dimstyle_name.lower()])
    sc = ds['DIMSCALE'] or 1.0
    asz, txt, gap, cen = ds['DIMASZ'] * sc, ds['DIMTXT'] * sc, ds['DIMGAP'] * sc, ds['DIMCEN'] * sc
    ents = []
    p10, p15 = d['pt10'][:2], d['pt15'][:2]
    pre = 'R' if d['type'] == 25 else '%%c'
    if d['type'] == 25:
        c, ch = p10, p15
        r = math.dist(c, ch)
        ux, uy = ((ch[0] - c[0]) / r, (ch[1] - c[1]) / r) if r else (1.0, 0.0)
    else:
        ch, far = p15, p10
        c = ((ch[0] + far[0]) / 2, (ch[1] + far[1]) / 2)
        r = math.dist(ch, far) / 2
        ux, uy = ((ch[0] - c[0]) / r, (ch[1] - c[1]) / r) if r else (1.0, 0.0)
    nx, ny = -uy, ux
    meas = _fmt(d['measurement'], ds['DIMDEC'], ds['DIMLFAC'] or 1.0)
    body = (d['user_text'] or (pre + meas)).replace('<>', meas)
    import dwgfont
    tw = dwgfont.text_width(body, txt) * dwgfont.style_factor(None)
    def arrow(tip, dirv):
        b = (tip[0] + dirv[0] * asz, tip[1] + dirv[1] * asz); hw = asz / 6
        ents.append(('S', [(b[0] + nx * hw, b[1] + ny * hw), (b[0] - nx * hw, b[1] - ny * hw), tip, tip]))
        return b
    arrow(ch, (-ux, -uy))
    tc = (ch[0] + ux * (asz + gap + tw / 2 + gap), ch[1] + uy * (asz + gap + tw / 2 + gap))
    ls = (ch[0] - ux * asz, ch[1] - uy * asz)
    ents.append(('L', ls, (tc[0] - ux * (tw / 2 + gap), tc[1] - uy * (tw / 2 + gap))))
    if d['type'] == 26:
        far = p10
        arrow(far, (ux, uy)); ents.append(('L', (far[0] + ux * asz * 0, far[1]), ls)) if False else ents.append(('L', (far[0] - ux * asz, far[1] - uy * asz), ls))
    else:
        ents.append(('L', (c[0] - cen, c[1]), (c[0] + cen, c[1]))); ents.append(('L', (c[0], c[1] - cen), (c[0], c[1] + cen)))
    ents.append(('T', tc, '\\A1;' + body, txt, 5, 0.0))
    ents.append(('P', ch)); ents.append(('P', c if d['type'] == 25 else p10))
    d['text_mid'] = tc
    return ents


def build_angular_block(doc, d, dimstyle_name):
    """3-point angular dimension (type 23): pt15 vertex, pt13 / pt14 end points of the two legs, pt10 a point on the dimension arc"""
    ds = doc.get(doc.dimstyles()[dimstyle_name.lower()])
    sc = ds['DIMSCALE'] or 1.0
    asz, exo, exe, txt, gap = ds['DIMASZ'] * sc, ds['DIMEXO'] * sc, ds['DIMEXE'] * sc, ds['DIMTXT'] * sc, ds['DIMGAP'] * sc
    c = d['pt15'][:2]; p1 = d['pt13'][:2]; p2 = d['pt14'][:2]; q = d['pt10'][:2]
    r = math.dist(c, q)
    a1 = math.atan2(p1[1] - c[1], p1[0] - c[0]); a2 = math.atan2(p2[1] - c[1], p2[0] - c[0])
    sweep = (a2 - a1) % (2 * math.pi)
    d['measurement'] = sweep
    ents = []
    for p, a in ((p1, a1), (p2, a2)):
        dist = math.dist(c, p)
        ux, uy = math.cos(a), math.sin(a)
        s = max(dist, 0) + exo; e = r + exe
        if s < e: ents.append(('L', (c[0] + ux * s, c[1] + uy * s), (c[0] + ux * e, c[1] + uy * e)))
    ents.append(('A', c, r, a1, a1 + sweep))
    hw = asz / 6
    for a, sgn in ((a1, 1), (a1 + sweep, -1)):
        tip = (c[0] + r * math.cos(a), c[1] + r * math.sin(a))
        tx, ty = -math.sin(a) * sgn, math.cos(a) * sgn         # tangent pointing into the arc
        b = (tip[0] + tx * asz, tip[1] + ty * asz); nx, ny = math.cos(a), math.sin(a)
        ents.append(('S', [(b[0] + nx * hw, b[1] + ny * hw), (b[0] - nx * hw, b[1] - ny * hw), tip, tip]))
    deg = math.degrees(sweep)
    body = (d['user_text'] or '%s\\U+00B0' % ('%.*f' % (ds['DIMDEC'], deg))).replace('<>', '%.*f\\U+00B0' % (ds['DIMDEC'], deg))
    am = a1 + sweep / 2
    import dwgfont
    tw = dwgfont.text_width(body.split(";")[-1], txt) * dwgfont.style_factor(None)
    rad = r + gap + tw / 2 * abs(math.cos(am)) + txt / 2 * abs(math.sin(am))
    tc = (c[0] + rad * math.cos(am), c[1] + rad * math.sin(am))
    ents.append(('T', tc, '\\A1;' + body, txt, 5, 0.0))
    ents.append(('P', p1)); ents.append(('P', p2)); ents.append(('P', q)); ents.append(('P', c))
    d['text_mid'] = tc
    return ents


def build_ordinate_block(doc, d, dimstyle_name):
    """ordinate dimension (type 20): pt10 origin, pt13 feature point, pt14 leader end point; d['oflags'] & 64 = X-type (value is the x offset)"""
    ds = doc.get(doc.dimstyles()[dimstyle_name.lower()])
    sc = ds['DIMSCALE'] or 1.0
    txt, gap, exo = ds['DIMTXT'] * sc, ds['DIMGAP'] * sc, ds['DIMEXO'] * sc
    o = d['pt10'][:2]; f = d['pt13'][:2]; e = d['pt14'][:2]
    xtype = bool(d.get('oflags', 0) & 64)
    val = abs(f[0] - o[0]) if xtype else abs(f[1] - o[1])
    d['measurement'] = val
    meas = _fmt(val, ds['DIMDEC'], ds['DIMLFAC'] or 1.0)
    body = (d['user_text'] or meas).replace('<>', meas)
    ents = []
    if xtype:
        s = (f[0], f[1] + (exo if e[1] >= f[1] else -exo)); ents.append(('L', s, (f[0], e[1])))
        tc = (f[0], e[1] + (gap + txt / 2 if e[1] >= f[1] else -(gap + txt / 2))); rot = 1.5707963267948966
        tc = (f[0] - 0.0, tc[1])
    else:
        s = (f[0] + (exo if e[0] >= f[0] else -exo), f[1]); ents.append(('L', s, (e[0], f[1])))
        import dwgfont
        tw = dwgfont.text_width(body, txt) * dwgfont.style_factor(None)
        tc = (e[0] + (gap + tw / 2 if e[0] >= f[0] else -(gap + tw / 2)), f[1]); rot = 0.0
    ents.append(('T', tc, '\\A1;' + body, txt, 5, rot))
    ents.append(('P', f)); ents.append(('P', o)); ents.append(('P', e))
    d['text_mid'] = tc
    return ents
