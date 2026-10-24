"""Version-aware entity decoding on top of dwgload objects (R2004 family first)."""
import dwgbits as B


LAST_READER = None
MARKS = {}
STRPOS = []  # (start_bit, end_bit) of every inline string read through make_rd (inline-string versions only)


def make_rd(o, r, ss):
    wide = o.ver not in ('AC1015', 'AC1018')
    if wide:
        return (lambda: ss.TU()) if ss else (lambda: r.TU())
    def f():
        p0 = r.p
        v = r.TV()
        STRPOS.append((p0, r.p))
        return v
    return f


def start_reader(o):
    global LAST_READER
    del STRPOS[:]
    r = B.Bits(o.raw, o.data_bit)
    LAST_READER = r
    if o.ver == 'AC1018':
        pass  # type and bitsize already consumed by loader
    r.H()
    return r


def cmc(r, ver):
    idx = r.BS()
    rgb = alpha = None
    if ver != 'AC1015':
        if idx & 0x8000 and not idx & 0x4000: rgb = r.BL()  # 0xC000: colour-book colour, referenced by handle, no inline value (found by experiment)
        if idx & 0x2000: alpha = r.BL()
        idx &= 0x1FFF
    return idx, rgb, alpha


_ANNO_W = 'AnnotativeData'.encode('utf-16le'); _ANNO_N = b'AnnotativeData'


def annotative_flag(eed):
    """True/False from the 'AnnotativeData' extended data block ({ version, annotative flag }: two 1070 integers inside braces), None when the entity has none. The
    block is written for annotative entities (flag 1); the integers are the RS values after code 70 ('F')."""
    for app, raw in eed:
        raw = bytes(raw)
        for nm in (_ANNO_W, _ANNO_N):
            i = raw.find(nm)
            if i < 0: continue
            p = i + len(nm); vals = []
            while p < len(raw):
                c = raw[p]; p += 1
                if c == 0x46 and p + 2 <= len(raw): vals.append(int.from_bytes(raw[p:p + 2], 'little')); p += 2
                elif c == 0x02: p += 1
                elif c == 0x00: p += 0
                else: break
            if len(vals) >= 2: return bool(vals[1])
            return None
    return None


def common_entity(r, ver):
    e = {}
    eed = []
    while True:
        n = r.BS()
        if n == 0: break
        app = r.H()
        eed.append((app, r.rcs(n)))
    e['eed'] = eed
    an = annotative_flag(eed)
    if an is not None: e['annotative'] = an
    if r.B():
        sz = r.BLL() if ver in ('AC1024', 'AC1027', 'AC1032') else r.RL()
        r.p += sz * 8
    MARKS['entmode'] = r.p
    e['entmode'] = r.BB()
    e['nreactors'] = r.BL()
    e['xdicmissing'] = r.B()
    if ver in ('AC1027', 'AC1032'): e['hasbinary'] = r.B()
    e['color'] = cmc(r, ver)
    e['ltscale'] = r.BD()
    e['ltflags'] = r.BB()
    e['plotflags'] = r.BB()
    if ver not in ('AC1015', 'AC1018'):
        e['material'] = r.BB(); e['shadow'] = r.RC()
        if ver != 'AC1021':
            r.B(); r.B(); r.B()
    e['invis'] = r.BS()
    e['lweight'] = r.RC()
    return e


def decode_line(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    z0 = r.B(); x1 = r.RD(); x2 = r.DD(x1); y1 = r.RD(); y2 = r.DD(y1)
    z1 = z2 = 0.0
    if not z0: z1 = r.RD(); z2 = r.DD(z1)
    e.update(kind='LINE', p1=(x1, y1, z1), p2=(x2, y2, z2), thickness=r.BT(), ext=r.BE())
    return e


def decode_circle_arc(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    c = r.BD3(); rad = r.BD(); th = r.BT(); ex = r.BE()
    e.update(kind='CIRCLE' if o.type == 18 else 'ARC', center=c, radius=rad, thickness=th, ext=ex)
    if o.type == 17: e.update(a0=r.BD(), a1=r.BD())
    return e


def string_stream(o):
    """R2007+ objects keep strings in a separate stream just before the handle stream. Returns a Bits reader or None. [GEN]"""
    end = o.handle_bit
    r = B.Bits(o.raw, end - 1)
    if not r.bit():
        return None
    p = end - 1 - 16
    r = B.Bits(o.raw, p)
    size = r.RS()
    if size & 0x8000:
        p -= 16
        r = B.Bits(o.raw, p)
        hi = r.RS()
        size = (size & 0x7FFF) | (hi << 15)
    return B.Bits(o.raw, p - size)


def decode_text(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = string_stream(o) if wide else None
    fl = r.RC()
    elev = 0.0 if fl & 1 else r.RD()
    ins = r.RD2()
    al = ins if fl & 2 else (r.DD(ins[0]), r.DD(ins[1]))
    ex = r.BE(); th = r.BT()
    obl = 0.0 if fl & 4 else r.RD()
    rot = 0.0 if fl & 8 else r.RD()
    h = r.RD()
    wf = 1.0 if fl & 0x10 else r.RD()
    txt = make_rd(o, r, ss)()
    gen = 0 if fl & 0x20 else r.BS()
    ha = 0 if fl & 0x40 else r.BS()
    va = 0 if fl & 0x80 else r.BS()
    e.update(kind='TEXT', elev=elev, ins=ins, align=al, ext=ex, thickness=th, oblique=obl, rot=rot, height=h, widthf=wf, text=txt, gen=gen, halign=ha, valign=va)
    return e


def decode_lwpolyline(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    fl = r.BS()
    cw = r.BD() if fl & 4 else 0.0
    el = r.BD() if fl & 8 else 0.0
    th = r.BD() if fl & 2 else 0.0
    nm = r.BD3() if fl & 1 else (0.0, 0.0, 1.0)
    n = r.BL()
    nb = r.BL() if fl & 16 else 0
    nids = r.BL() if fl & 1024 else 0
    nw = r.BL() if fl & 32 else 0
    pts = []
    for i in range(r.cnt(n, 2)):
        if i == 0: pts.append(r.RD2())
        else: pts.append((r.DD(pts[-1][0]), r.DD(pts[-1][1])))
    bul = [r.BD() for _ in range(r.cnt(nb, 2))]
    ids = [r.BL() for _ in range(r.cnt(nids, 2))]
    wid = [(r.BD(), r.BD()) for _ in range(r.cnt(nw, 4))]
    e.update(kind='LWPOLYLINE', flags=fl, closed=bool(fl & 512), constwidth=cw, elev=el, thickness=th, ext=nm, pts=pts, bulges=bul, widths=wid)
    return e


def decode_insert(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    ip = r.BD3()
    sf = r.BB()
    if sf == 0: sx = r.RD(); sy = r.DD(sx); sz = r.DD(sx)
    elif sf == 1: sx = 1.0; sy = r.DD(1.0); sz = r.DD(1.0)
    elif sf == 2: sx = r.RD(); sy = sz = sx
    else: sx = sy = sz = 1.0
    rot = r.BD(); ex = r.BD3(); ha = r.B()
    nowned = r.BL() if ha and o.ver != 'AC1015' else 0
    e.update(kind='INSERT', ins=ip, scale=(sx, sy, sz), rot=rot, ext=ex, hasattribs=ha)
    return e


def decode_minsert(o):
    """MINSERT (8): INSERT fields followed by the array description."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    ip = r.BD3()
    sf = r.BB()
    if sf == 0: sx = r.RD(); sy = r.DD(sx); sz = r.DD(sx)
    elif sf == 1: sx = 1.0; sy = r.DD(1.0); sz = r.DD(1.0)
    elif sf == 2: sx = r.RD(); sy = sz = sx
    else: sx = sy = sz = 1.0
    rot = r.BD(); ex = r.BD3(); ha = r.B()
    if ha and o.ver != 'AC1015': r.BL()
    cols = r.BS(); rows = r.BS(); cs = r.BD(); rs = r.BD()
    e.update(kind='MINSERT', ins=ip, scale=(sx, sy, sz), rot=rot, ext=ex, hasattribs=ha, cols=cols, rows=rows, col_spacing=cs, row_spacing=rs)
    return e


def decode_point(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e.update(kind='POINT', p=r.BD3(), thickness=r.BT(), ext=r.BE(), xangle=r.BD())
    return e


def decode_solid(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    th = r.BT(); el = r.BD()
    pts = [r.RD2() for _ in range(4)]
    e.update(kind='SOLID' if o.type == 31 else 'TRACE', thickness=th, elev=el, pts=pts, ext=r.BE())
    return e


def decode_3dface(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    noflags = r.B(); zzero = r.B()
    p0 = (r.RD(), r.RD(), 0.0 if zzero else r.RD())
    pts = [p0]
    for _ in range(3):
        x = r.DD(pts[-1][0]); y = r.DD(pts[-1][1]); z = r.DD(pts[-1][2])
        pts.append((x, y, z))
    inv = 0 if noflags else r.BS()
    e.update(kind='3DFACE', pts=pts, invisible=inv)
    return e


def decode_ellipse(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e.update(kind='ELLIPSE', center=r.BD3(), major=r.BD3(), ext=r.BD3(), ratio=r.BD(), a0=r.BD(), a1=r.BD())
    return e


def decode_ray(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e.update(kind='RAY' if o.type == 40 else 'XLINE', p=r.BD3(), v=r.BD3())
    return e


def decode_mtext(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    ins = r.BD3(); ex = r.BD3(); xd = r.BD3(); w = r.BD()
    h = r.BD() if o.ver not in ('AC1015', 'AC1018') else None
    th = r.BD(); att = r.BS(); dd = r.BS(); eh = r.BD(); ew = r.BD()
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = string_stream(o) if wide else None
    txt = make_rd(o, r, ss)()
    ls_style = r.BS(); ls_factor = r.BD(); r.B()
    bg = 0; bg_scale = bg_col = bg_trans = None
    if o.ver != 'AC1015':
        bg = r.BL()
        if bg & 1:
            bg_scale = r.BD(); bg_col = (r.BS(), r.BL(), r.RC()); bg_trans = r.BL()  # fill scale, background colour (full CMC: BS index, BL rgb, RC flags), transparency
        elif bg & 0x10:
            pass
    if o.ver == 'AC1032':
        r.p = expected_end(o)  # R2018 adds ~364 bits of trailing data (column / annotation) that is not decoded yet
    e.update(kind='MTEXT', ins=ins, ext=ex, xdir=xd, width=w, height=h, text_height=th, attachment=att, drawdir=dd, ext_h=eh, ext_w=ew, text=txt, ls_style=ls_style, ls_factor=ls_factor, bgflags=bg, bg_scale=bg_scale, bg_color=bg_col, bg_transparency=bg_trans)
    return e


def decode_spline(o):
    """SPLINE. The scenario field and (R2013+) the flag bit 0 disagree on which layout (1 = NURBS control data, 2 = fit data) is stored; both are tried and the one that ends exactly at the end of the main data wins."""
    r0 = start_reader(o)
    common_entity(r0, o.ver)
    scenario0 = r0.BL(); sflags = 0
    if o.ver in ('AC1027', 'AC1032'): sflags = r0.BL()
    order = [2, 1] if sflags & 1 else [scenario0, 3 - scenario0 if scenario0 in (1, 2) else 1]
    exp_end = expected_end(o)
    first = None
    for sc in order:
        try:
            e = _spline_layout(o, sc)
        except (ValueError, IndexError):
            continue
        end = LAST_READER.p
        if first is None: first = e
        if end == exp_end: return e
    if first is None: raise ValueError('spline layout')
    return first


def _spline_layout(o, scenario):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    r.BL()
    if o.ver in ('AC1027', 'AC1032'):
        r.BL(); r.BL()  # spline flags, knot parameterisation (R2013+)
    degree = r.BL()
    ctrl = []; fit = []; knots = []; weights = []
    rational = closed = periodic = False
    tan0 = tan1 = None
    if scenario == 1:  # EXP: scenario 1 carries the NURBS control data, 2 the fit data (end position equals the handle stream start)
        rational = bool(r.B()); closed = bool(r.B()); periodic = bool(r.B())
        r.BD(); r.BD()  # knot / control tolerances
        nk = r.BL(); nc = r.BL(); weighted = bool(r.B())
        knots = [r.BD() for _ in range(r.cnt(nk, 2))]
        for _ in range(r.cnt(nc, 6)):
            ctrl.append(r.BD3())
            if weighted: weights.append(r.BD())
    elif scenario == 2:
        r.BD()  # fit tolerance
        tan0 = r.BD3(); tan1 = r.BD3()  # begin / end tangents
        nf = r.BL()
        fit = [r.BD3() for _ in range(r.cnt(nf, 6))]
    else:
        raise ValueError('scenario')
    e.update(kind='SPLINE', scenario=scenario, degree=degree, rational=rational, closed=closed, periodic=periodic, knots=knots, ctrl=ctrl, weights=weights, fit=fit, tan0=tan0, tan1=tan1)
    return e


def expected_end(o):
    """Bit position where the main data of o should end after a correct decode: start of the string area (R2007+ with string stream) or of the handle stream."""
    if o.ver in ('AC1015', 'AC1018'):
        return o.handle_bit
    end = o.handle_bit
    if B.Bits(o.raw, end - 1).bit():
        p = end - 1 - 16
        size = B.Bits(o.raw, p).RS()
        if size & 0x8000:
            p -= 16
            size = (size & 0x7FFF) | (B.Bits(o.raw, p).RS() << 15)
        return p - size
    return end - 1  # trailing zero flag bit


def _text_like(o, r, e):
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = string_stream(o) if wide else None
    fl = r.RC()
    elev = 0.0 if fl & 1 else r.RD()
    ins = r.RD2()
    al = ins if fl & 2 else (r.DD(ins[0]), r.DD(ins[1]))
    ex = r.BE(); th = r.BT()
    obl = 0.0 if fl & 4 else r.RD()
    rot = 0.0 if fl & 8 else r.RD()
    h = r.RD()
    wf = 1.0 if fl & 0x10 else r.RD()
    rd = make_rd(o, r, ss)
    txt = rd()
    gen = 0 if fl & 0x20 else r.BS()
    ha = 0 if fl & 0x40 else r.BS()
    va = 0 if fl & 0x80 else r.BS()
    e.update(elev=elev, ins=ins, align=al, ext=ex, thickness=th, oblique=obl, rot=rot, height=h, widthf=wf, text=txt, gen=gen, halign=ha, valign=va)
    return rd


def decode_attrib(o):
    """ATTRIB (2) and ATTDEF (3)."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    rd = _text_like(o, r, e)
    if o.ver in ('AC1024', 'AC1027', 'AC1032'):
        e['version'] = r.RC()
    if o.ver in ('AC1027', 'AC1032') or (o.ver == 'AC1024' and o.type == 3):
        pass
    if o.ver == 'AC1032':
        e['attr_type'] = r.RC()
        if e['attr_type'] > 1:
            # multiline attribute (R2018): 37 bits of annotation header (EXP), then the embedded MTEXT fields; strings follow in the order
            # attribute text, MTEXT text, tag, prompt. The trailing flags are not located; the reader is parked at the data end.
            r.p += 37
            ins = r.BD3(); ex = r.BD3(); xd = r.BD3(); w = r.BD(); mh = r.BD(); th = r.BD(); att = r.BS(); dd = r.BS(); eh = r.BD(); ew = r.BD()
            mtext = rd(); tag = rd()
            prompt = rd() if o.type == 3 else None
            r.p = expected_end(o)
            if mtext: e['text'] = mtext  # full text; the first string is only the first line
            e.update(kind='ATTRIB' if o.type == 2 else 'ATTDEF', tag=tag, field_length=0, attflags=None, prompt=prompt, multiline=True, mtext=mtext, text_first=e.get('text'),
                     mtext_ins=ins, mtext_xdir=xd, mtext_width=w, mtext_height=th, mtext_attachment=att)
            return e
    tag = rd()
    flen = r.BS(); flags = r.RC()
    if o.ver in ('AC1021', 'AC1024', 'AC1027', 'AC1032'): e['lock_position'] = r.B()
    if o.type == 3 and o.ver in ('AC1024', 'AC1027', 'AC1032'):
        r.RC()  # second version byte before the prompt in ATTDEF (EXP: 8 zero bits)
    prompt = rd() if o.type == 3 else None
    e.update(kind='ATTRIB' if o.type == 2 else 'ATTDEF', tag=tag, field_length=flen, attflags=flags, prompt=prompt)
    return e


def decode_polyline2d(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    fl = r.BS(); curve = r.BS(); sw = r.BD(); ew = r.BD(); th = r.BT(); el = r.BD(); ex = r.BE()
    nowned = r.BL() if o.ver != 'AC1015' else 0
    e.update(kind='POLYLINE2D', flags=fl, closed=bool(fl & 1), curve=curve, start_width=sw, end_width=ew, thickness=th, elev=el, ext=ex, nvert=nowned)
    return e


def decode_vertex2d(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    fl = r.RC(); p = r.BD3(); sw = r.BD()
    ew = -sw if sw < 0 else r.BD()
    bulge = r.BD()
    vid = r.BL() if o.ver in ('AC1024', 'AC1027', 'AC1032') else 0
    tan = r.BD()
    e.update(kind='VERTEX2D', flags=fl, p=p, start_width=abs(sw), end_width=ew, bulge=bulge, vid=vid, tangent=tan)
    return e


def decode_seqend(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e['kind'] = 'SEQEND'
    return e


def decode_viewport(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = string_stream(o) if wide else None
    e.update(kind='VIEWPORT', center=r.BD3(), width=r.BD(), height=r.BD())
    e.update(view_target=r.BD3(), view_dir=r.BD3(), twist=r.BD(), view_height=r.BD(), lens=r.BD(), front_clip=r.BD(), back_clip=r.BD(),
             snap_angle=r.BD(), view_center=r.RD2(), snap_base=r.RD2(), snap_spacing=r.RD2(), grid_spacing=r.RD2(), circle_zoom=r.BS())
    if wide: e['grid_major'] = r.BS()
    nfrozen = r.BL(); e['status'] = r.BL()
    e['stylesheet'] = (ss.TU() if ss else r.TU()) if wide else r.TV()
    e['render_mode'] = r.RC(); e['ucs_at_origin'] = r.B(); e['ucs_per_vp'] = r.B()
    e.update(ucs_origin=r.BD3(), ucs_x=r.BD3(), ucs_y=r.BD3(), ucs_elev=r.BD(), ucs_ortho=r.BS())
    if o.ver != 'AC1015': e['shade_plot'] = r.BS()
    if wide:
        e['default_lights'] = r.B(); e['lighting_type'] = r.RC(); e['brightness'] = r.BD(); e['contrast'] = r.BD()
        r.BS(); r.BL(); r.RC()  # ambient light colour (full CMC)
    e['nfrozen'] = nfrozen
    return e


def decode_layout(o):
    """LAYOUT (type 82 in the R2004 family): PLOTSETTINGS part followed by layout part."""
    r = start_reader(o)
    eed = []
    while True:
        n = r.BS()
        if n == 0: break
        eed.append((r.H(), r.rcs(n)))
    r.BL()
    if o.ver != 'AC1015': r.B()
    if o.ver in ('AC1027', 'AC1032'): r.B()
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = string_stream(o) if wide else None
    rd = (lambda: ss.TU()) if wide and ss else ((lambda: r.TU()) if wide else (lambda: r.TV()))
    e = dict(kind='LAYOUT', eed=eed)
    e.update(page_setup=rd(), printer=rd(), plot_flags=r.BS(), margins=(r.BD(), r.BD(), r.BD(), r.BD()), paper=(r.BD(), r.BD()), paper_size=rd(),
             plot_origin=(r.BD(), r.BD()), paper_units=r.BS(), rotation=r.BS(), plot_type=r.BS(), window=(r.BD(), r.BD(), r.BD(), r.BD()))
    if o.ver == 'AC1015': e['plot_view'] = rd()  # R2000 only
    e.update(real_world_units=r.BD(), drawing_units=r.BD(), style_sheet=rd(), scale_type=r.BS(), scale_factor=r.BD(), image_origin=(r.BD(), r.BD()))
    if o.ver != 'AC1015': e.update(shade_plot=r.BS(), shade_res=r.BS(), custom_dpi=r.BS())
    e.update(name=rd(), tab_order=r.BL(), flags=r.BS(), ucs_origin=r.BD3(), limmin=r.RD2(), limmax=r.RD2(), insbase=r.BD3(), ucs_x=r.BD3(), ucs_y=r.BD3(),
             elevation=r.BD(), ucs_ortho=r.BS(), extmin=r.BD3(), extmax=r.BD3(), nviewports=r.BL())
    return e


def decode_hatch(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = string_stream(o) if wide else None
    rd = (lambda: ss.TU()) if wide and ss else ((lambda: r.TU()) if wide else (lambda: r.TV()))
    grad = dict(is_gradient=0)
    if o.ver != 'AC1015':
        grad['is_gradient'] = r.BL(); r.BL()
        grad.update(angle=r.BD(), shift=r.BD(), single_color=r.BL(), tint=r.BD())
        ncol = r.BL(); cols = []
        for _ in range(r.cnt(ncol, 8)):
            v = r.BD(); c = (r.BS(), r.BL(), r.RC()); cols.append((v, c))
        grad['colors'] = cols; grad['name'] = rd()
    elev = r.BD(); ext = r.BD3(); pname = rd(); solid = r.B(); assoc = r.B(); npaths = r.BL()
    paths = []
    has_pixel = False
    for _ in range(r.cnt(npaths, 2)):
        fl = r.BL(); segs = []
        if fl & 2:
            bulges = r.B(); closed = r.B(); n = r.BL()
            for _ in range(r.cnt(n, 128)):
                p = r.RD2(); b = r.BD() if bulges else 0.0
                segs.append(('P', p, b))
            path = dict(flags=fl, closed=bool(closed), segs=segs)
        else:
            n = r.BL()
            for _ in range(r.cnt(n, 8)):
                t = r.RC()
                if t == 1: segs.append(('L', r.RD2(), r.RD2()))
                elif t == 2: segs.append(('A', r.RD2(), r.BD(), r.BD(), r.BD(), r.B()))
                elif t == 3: segs.append(('E', r.RD2(), r.RD2(), r.BD(), r.BD(), r.BD(), r.B()))
                elif t == 4:
                    deg = r.BL(); rat = r.B(); per = r.B(); nk = r.BL(); nc = r.BL()
                    kn = [r.BD() for _ in range(r.cnt(nk, 2))]; cp = []
                    for _ in range(r.cnt(nc, 128)):
                        pt = r.RD2(); w = r.BD() if rat else 1.0; cp.append((pt, w))
                    fit = None
                    if o.ver in ('AC1024', 'AC1027', 'AC1032'):
                        nf = r.BL()  # EXP: a fit point count (BL), not a flag bit
                        if nf:
                            fit = ([r.RD2() for _ in range(r.cnt(nf, 128))], r.RD2(), r.RD2())
                    segs.append(('S', deg, rat, per, kn, cp, fit))
                else:
                    raise ValueError('hatch seg type %d' % t)
            path = dict(flags=fl, segs=segs)
        path['nboundary'] = r.BL()
        paths.append(path)
    style = r.BS(); ptype = r.BS()
    pattern = None; angle = scale = 0.0; double = 0
    if not solid:
        angle = r.BD(); scale = r.BD(); double = r.B(); nlines = r.BS(); pattern = []
        for _ in range(r.cnt(nlines, 8)):
            a = r.BD(); p0 = (r.BD(), r.BD()); off = (r.BD(), r.BD()); nd = r.BS()
            pattern.append((a, p0, off, [r.BD() for _ in range(r.cnt(nd, 2))]))
    if any(p['flags'] & 4 for p in paths):  # EXP: 'derived' path flag => pixel size present
        pixel = r.BD()
    else:
        pixel = None
    nseeds = r.BL(); seeds = [r.RD2() for _ in range(r.cnt(nseeds, 128))]
    e.update(kind='HATCH', gradient=grad, elev=elev, ext=ext, pattern_name=pname, solid=solid, assoc=assoc, paths=paths, style=style, pattern_type=ptype,
             pattern_angle=angle, pattern_scale=scale, pattern_double=double, pattern_lines=pattern, pixel=pixel, seeds=seeds)
    return e


DIM_NAMES = {20: 'DIM_ORDINATE', 21: 'DIM_LINEAR', 22: 'DIM_ALIGNED', 23: 'DIM_ANG3PT', 24: 'DIM_ANG2LN', 25: 'DIM_RADIUS', 26: 'DIM_DIAMETER'}


def decode_dimension(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = string_stream(o) if wide else None
    rd = make_rd(o, r, ss)
    if o.ver in ('AC1024', 'AC1027', 'AC1032'):
        e['dim_version'] = r.RC()
    e.update(ext=r.BE() if False else r.BD3(), text_mid=r.RD2(), elevation=r.BD(), dflags=r.RC(), user_text=rd(), text_rot=r.BD(), horiz_dir=r.BD(),
             ins_scale=r.BD3(), ins_rot=r.BD(), attach=r.BS(), ls_style=r.BS(), ls_factor=r.BD(), measurement=r.BD())
    if wide:
        e['unknown_b'] = r.B(); e['flip1'] = r.B(); e['flip2'] = r.B()
    e['clone_pt'] = r.RD2()
    t = o.type
    if t == 21:
        e.update(pt13=r.BD3(), pt14=r.BD3(), pt10=r.BD3(), ext_rot=r.BD(), dim_rot=r.BD())
    elif t == 22:
        e.update(pt13=r.BD3(), pt14=r.BD3(), pt10=r.BD3(), ext_rot=r.BD())
    elif t == 23:
        e.update(pt10=r.BD3(), pt13=r.BD3(), pt14=r.BD3(), pt15=r.BD3())
    elif t == 24:
        e.update(pt16=r.RD2(), pt13=r.BD3(), pt14=r.BD3(), pt15=r.BD3(), pt10=r.BD3())
    elif t in (25, 26):
        e.update(pt10=r.BD3(), pt15=r.BD3(), leader_len=r.BD())
    elif t == 20:
        e.update(pt10=r.BD3(), pt13=r.BD3(), pt14=r.BD3(), oflags=r.RC())
    e['kind'] = DIM_NAMES[t]
    return e


def decode_polyline_pface(o):
    """POLYLINE_PFACE (29): polyface mesh header."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    nv = r.BS(); nf = r.BS()
    nowned = r.BL() if o.ver != 'AC1015' else 0
    e.update(kind='POLYLINE_PFACE', nverts=nv, nfaces=nf, nvert=nowned)
    return e


def decode_polyline_mesh(o):
    """POLYLINE_MESH (30): M x N polygon mesh header."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    fl = r.BS(); curve = r.BS(); m = r.BS(); n = r.BS(); msd = r.BS(); nsd = r.BS()
    nowned = r.BL() if o.ver != 'AC1015' else 0
    e.update(kind='POLYLINE_MESH', flags=fl, curve=curve, m=m, n=n, m_closed=bool(fl & 1), n_closed=bool(fl & 32), nvert=nowned)
    return e


def decode_vertex_pface(o):
    """VERTEX_MESH (12) / VERTEX_PFACE (13): flags + point."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e.update(kind='VERTEX_PFACE' if o.type == 13 else 'VERTEX_MESH', flags=r.RC(), p=r.BD3())
    return e


def decode_vertex_pface_face(o):
    """VERTEX_PFACE_FACE (14): four signed 1-based vertex indices (0 = unused, negative = invisible edge)."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e.update(kind='VERTEX_PFACE_FACE', idx=[r.BS() for _ in range(4)])
    e['idx'] = [i - 65536 if i > 32767 else i for i in e['idx']]
    return e


def decode_polyline3d(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    fl1 = r.RC(); fl2 = r.RC()
    nowned = r.BL() if o.ver != 'AC1015' else 0
    e.update(kind='POLYLINE3D', flags=fl1, flags2=fl2, closed=bool(fl2 & 1), nvert=nowned)
    return e


def decode_vertex3d(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e.update(kind='VERTEX3D', flags=r.RC(), p=r.BD3())
    return e


def decode_leader(o):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    r.B()
    ann = r.BS(); path = r.BS(); n = r.BL()
    pts = [r.BD3() for _ in range(r.cnt(n, 6))]
    e.update(kind='LEADER', annotation=ann, path=path, pts=pts, end_proj=r.BD3(), ext=r.BD3(), xdir=r.BD3(), block_offset=r.BD3())
    if o.ver in ('AC1018', 'AC1021') and ann != 3:
        # R2004 leaders with a text/tolerance/insert annotation carry 144 further bits that are not decoded yet (the points above are right)
        r.p = expected_end(o)
        return e
    if o.ver in ('AC1015', 'AC1018', 'AC1021'):
        e['box_height'] = r.BD(); e['box_width'] = r.BD()  # R2000 / R2004 / R2007 layout (found by experiment on corpus files, exact end)
    else:
        e['annot_offset'] = r.BD3()
    e['hookline_dir'] = r.B(); e['arrowhead'] = r.B()
    e['arrow_type'] = r.BS(); r.B(); r.B()  # two unknown bits (always 0 in the corpus)
    if o.ver == 'AC1015':
        r.BS(); r.BS(); r.B(); r.B()
    elif o.ver == 'AC1018':
        r.p = expected_end(o)  # the 14 trailing bits vary in the first bit (6 of 28 leaders in real drawings misaligned under BS BS B B); the fields are unused
    elif o.ver == 'AC1021':
        r.B(); r.B(); r.BS(); r.B(); r.B()  # EXP: ends exactly on all R2007 leaders of the sample (BS BS B B only by coincidence of the values)
    return e


def decode_wipeout(o, kind='WIPEOUT'):
    """WIPEOUT / IMAGE style entity (class based)."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    cv = r.BL()
    e.update(kind=kind, class_version=cv, pt0=r.BD3(), uvec=r.BD3(), vvec=r.BD3(), size=r.RD2(), display=r.BS(), clipping=r.B(),
             brightness=r.RC(), contrast=r.RC(), fade=r.RC())
    if o.ver in ('AC1024', 'AC1027', 'AC1032'):
        e['clip_mode'] = r.B()
    ct = r.BS(); n = r.BL() if ct == 2 else 2
    e['clip_type'] = ct
    e['clip'] = [r.RD2() for _ in range(r.cnt(n, 128))]
    return e


def decode_image(o):
    return decode_wipeout(o, 'IMAGE')


def decode_imagedef(o):
    """IMAGEDEF object: class version, pixel size, file path, loaded flag, resolution unit, default pixel size."""
    r = start_reader(o)
    while True:
        n = r.BS()
        if n == 0: break
        r.H(); r.p += 8 * n
    r.BL()
    if o.ver != 'AC1015': r.B()
    if o.ver in ('AC1027', 'AC1032'): r.B()
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = string_stream(o) if wide else None
    rd = make_rd(o, r, ss)
    cv = r.BL(); size = r.RD2(); path = rd(); loaded = r.B(); unit = r.RC(); pix = r.RD2()
    return dict(kind='IMAGEDEF', class_version=cv, size=size, path=path, loaded=bool(loaded), res_unit=unit, pixel_size=pix)


def all_strings(o):
    """Every TU string in the string stream of an R2007+ object (class-based objects without a dedicated decoder: MULTILEADER, TABLE ...)."""
    if o.ver not in ('AC1021', 'AC1024', 'AC1027', 'AC1032'): return []
    ss = string_stream(o)
    if ss is None: return []
    end = o.handle_bit - 1 - 16
    out = []
    try:
        while ss.p < end - 1:
            n = ss.BS()
            if n is None or n <= 0 or n > 4000 or ss.p + 16 * n > end: break
            t = ''.join(chr(ss.RS()) for _ in range(n))
            out.append(t)
    except Exception:
        pass
    return out


def decode_acis(o, kind):
    """REGION / 3DSOLID / BODY: the ACIS data is kept raw (e['acis'] = ('sat', text) | ('sab', bytes)); dwgacis.parse() / faces() turn it into geometry."""
    import dwgacis
    r = start_reader(o)
    e = common_entity(r, o.ver)
    fmt, data = dwgacis.acis_data(o)
    e.update(kind=kind, acis=(fmt, data))
    r.p = expected_end(o)
    globals()['LAST_READER'] = r
    return e


def decode_ole2frame(o):
    """OLE2FRAME (type 74): BS flags, BS mode, BL length, OLE data. The data starts with a u16 and three 3D doubles (upper left, upper right, lower right
    corner of the frame in WCS, found by comparison with AutoCAD extents); the rest is the OLE compound file."""
    import struct
    r = start_reader(o)
    e = common_entity(r, o.ver)
    flags = r.BS(); mode = r.BS(); n = r.BL()
    data = r.rcs(r.cnt(n, 8)) if n else b''
    corners = None
    if len(data) >= 74:
        v = struct.unpack_from('<9d', data, 2)
        corners = [v[0:3], v[3:6], v[6:9]]
    xs = [c[0] for c in corners] if corners else []; ys = [c[1] for c in corners] if corners else []
    e.update(kind='OLE2FRAME', flags=flags, mode=mode, data_len=n, corners=corners, bounds=(min(xs), min(ys), max(xs), max(ys)) if corners else None, ole=data)
    r.p = expected_end(o) if o.ver not in ('AC1015', 'AC1018') else o.handle_bit
    globals()['LAST_READER'] = r
    return e


def decode_generic_text(o, kind):
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e.update(kind=kind, strings=all_strings(o))
    return e


def decode_table(o):
    """ACAD_TABLE: the entity starts like an INSERT (ins point, BB scale flag, rotation, extrusion, has-attribs); the cells are drawn by the anonymous *T block
    (block space = table frame with the origin at the insertion point), so this is all the viewer needs. Strings (cell texts) from the string stream."""
    e = decode_generic_text(o, 'ACAD_TABLE')
    try:
        r = start_reader(o); common_entity(r, o.ver)
        ip = r.BD3(); sf = r.BB()
        if sf == 0: sx = r.RD(); sy = r.DD(sx); sz = r.DD(sx)
        elif sf == 1: sx = 1.0; sy = r.DD(1.0); sz = r.DD(1.0)
        elif sf == 2: sx = r.RD(); sy = sz = sx
        else: sx = sy = sz = 1.0
        rot = r.BD(); ex = r.BD3()
        e.update(ins=ip, scale=(sx, sy, sz), rot=rot, ext=ex)
    except Exception:
        pass
    return e


def decode_underlay(o, kind):
    """PDFUNDERLAY / DGNUNDERLAY / DWFUNDERLAY: normal, insertion point, rotation, scale, display flags, contrast, fade, clip boundary (checked on AC1032_26: ends at the data end,
    equal to the AutoCAD dump position and scale). The definition (file path, sheet) is the object behind the first hard pointer."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    n = r.BD3(); ins = r.BD3(); rot = r.BD(); sc = r.BD3()
    fl = r.RC(); contrast = r.RC(); fade = r.RC()
    nb = r.BL()
    clip = [r.RD2() for _ in range(r.cnt(nb, 128))]
    e.update(kind=kind, ext=n, ins=ins, rot=rot, scale=sc, flags=fl, contrast=contrast, fade=fade, clip=clip, clip_on=bool(fl & 1), on=bool(fl & 2), mono=bool(fl & 4))
    return e


def decode_mline(o):
    """MLINE (47): scale, justification, base point, extrusion, flags (1 vertices, 2 closed, 4/8 suppress caps), element count, vertices with direction, miter and per element
    segment parameters (first value = offset of the element along the miter). Ends exactly at the data end on AC1032 (580 spare bits only in the string area)."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    sc = r.BD(); just = r.RC(); base = r.BD3(); ext = r.BD3(); flags = r.BS(); nl = r.RC(); nv = r.BS()
    verts = []
    for _ in range(r.cnt(nv, 3)):
        v = r.BD3(); d = r.BD3(); mi = r.BD3(); els = []
        for _ in range(nl):
            ps = [r.BD() for _ in range(r.cnt(r.BS(), 2))]
            ar = [r.BD() for _ in range(r.cnt(r.BS(), 2))]
            els.append((ps, ar))
        verts.append(dict(p=v, dir=d, miter=mi, elements=els))
    lines = []
    for k in range(nl):
        pts = []
        for vt in verts:
            ps = vt['elements'][k][0]
            off = ps[0] if ps else 0.0
            pts.append((vt['p'][0] + vt['miter'][0] * off, vt['p'][1] + vt['miter'][1] * off, vt['p'][2] + vt['miter'][2] * off))
        lines.append(pts)
    e.update(kind='MLINE', scale=sc, justification=just, base=base, ext=ext, flags=flags, closed=bool(flags & 2), nlines=nl, vertices=verts, lines=lines)
    return e


def decode_dim_class(o, kind):
    """Class-based dimension variants (ARC_DIMENSION): the common dimension fields as in decode_dimension, then arc point, the two extension line points, the arc centre and
    two further BD (1.0 in the samples); 12 trailing bits are skipped. Measurement, text position, arc point and extension points equal the AutoCAD dump (AC1032_00, 5 of 5).
    The picture is the anonymous *D block found through the handle stream."""
    r = start_reader(o)
    e = common_entity(r, o.ver)
    e['kind'] = kind
    try:
        wide = o.ver not in ('AC1015', 'AC1018')
        ss = string_stream(o) if wide else None
        rd = make_rd(o, r, ss)
        if o.ver in ('AC1024', 'AC1027', 'AC1032'): e['dim_version'] = r.RC()
        e.update(ext=r.BD3(), text_mid=r.RD2(), elevation=r.BD(), dflags=r.RC(), user_text=rd(), text_rot=r.BD(), horiz_dir=r.BD(), ins_scale=r.BD3(), ins_rot=r.BD(),
                 attach=r.BS(), ls_style=r.BS(), ls_factor=r.BD(), measurement=r.BD())
        if wide:
            e['unknown_b'] = r.B(); e['flip1'] = r.B(); e['flip2'] = r.B()
        e['clone_pt'] = r.RD2()
        e.update(arc_pt=r.BD3(), pt13=r.BD3(), pt14=r.BD3(), center=r.BD3())
        r.BD(); r.BD()
    except Exception:
        pass
    r.p = expected_end(o)
    globals()['LAST_READER'] = r
    return e


BMAT_N = 16


def decode_multileader(o):
    """MULTILEADER (R2010+): full layout in spec order (found by experiment; 54 of 54 AC1032 objects end exactly at the end of the main data):
    BS version, BL roots {B,B, 3BD connection, 3BD direction, breaks, BL branch, BD landing, lines {points, breaks, BL index, BS path, CMC colour, BL lineweight,
    BD arrow size, BL flags}, BS attachment direction}, context data (scale, base point, text height, arrow size, landing gap, 4 BS, content: text or block),
    base point/direction/vertical, B, 20 bits (not interpreted), the MLEADER own properties (override flags, line type/colour/weight, landing, dogleg, arrow,
    content type, text attachments/colour/frame, block scale...)."""
    e = decode_generic_text(o, 'MULTILEADER')
    try:
        r = start_reader(o); common_entity(r, o.ver)
        ss = string_stream(o) if o.ver not in ('AC1015', 'AC1018') else None
        ver = r.BS()
        if ver not in (1, 2): return e
        nroots = r.BL() if ver == 2 else 1  # class version 1 (R2007): exactly one root, no BL count
        if not 0 <= nroots <= 16: return e
        roots = []
        for _ in range(nroots):
            n = {}
            n['has_last'] = r.B(); n['has_dogleg'] = r.B()
            n['conn'] = r.BD3(); n['dir'] = r.BD3()
            n['breaks'] = [(r.BD3(), r.BD3()) for _ in range(r.cnt(r.BL(), 12))]
            n['branch'] = r.BL(); n['land'] = r.BD()
            lines = []
            for _ in range(r.cnt(r.BL(), 6)):
                L = {}
                L['pts'] = [r.BD3() for _ in range(r.cnt(r.BL(), 6))]
                L['breaks'] = [(r.BD3(), r.BD3()) for _ in range(r.cnt(r.BL(), 12))]
                L['index'] = r.BL()
                if ver == 2: L['path'] = r.BS(); L['color'] = _cmc3(r); L['lw'] = r.BL(); L['arrow'] = r.BD(); L['flags'] = r.BL()
                lines.append(L)
            n['lines'] = lines
            if ver == 2: n['attach'] = r.BS()
            roots.append(n)
        n0 = roots[0] if roots else dict(conn=(0.0, 0.0, 0.0), dir=(1.0, 0.0, 0.0), land=0.0, lines=[])
        end = (n0['conn'][0] + n0['dir'][0] * n0['land'], n0['conn'][1] + n0['dir'][1] * n0['land'], n0['conn'][2] + n0['dir'][2] * n0['land'])
        e.update(leader_conn=n0['conn'], leader_dir=n0['dir'], leader_land=n0['land'], leader_lines=[L['pts'] for L in n0['lines']], leader_end=end,
                 leader_roots=nroots, roots=roots)
        c = {}
        c['scale'] = r.BD(); c['base'] = r.BD3(); c['th'] = r.BD(); c['arrow'] = r.BD(); c['gap'] = r.BD()
        c['left'] = r.BS(); c['right'] = r.BS(); c['align'] = r.BS(); c['attach_type'] = r.BS()
        c['has_text'] = r.B()
        if c['has_text']:
            c['text'] = ss.TU() if ss else None
            c['normal'] = r.BD3(); c['loc'] = r.BD3(); c['dir'] = r.BD3(); c['rot'] = r.BD(); c['width'] = r.BD(); c['height'] = r.BD(); c['lsf'] = r.BD()
            c['lss'] = r.BS(); c['color'] = _cmc3(r); c['alignment'] = r.BS(); c['flow'] = r.BS(); c['bgcolor'] = _cmc3(r); c['bgscale'] = r.BD()
            c['bgtrans'] = r.BL(); c['bgfill'] = r.B(); c['bgmask'] = r.B(); c['coltype'] = r.BS(); c['hauto'] = r.B(); c['colw'] = r.BD(); c['colg'] = r.BD()
            c['colrev'] = r.B(); c['colsizes'] = [r.BD() for _ in range(r.cnt(r.BL(), 2))]; c['wordbreak'] = r.B()
        c['has_block'] = r.B()
        if c['has_block']:
            c['bnormal'] = r.BD3(); c['bloc'] = r.BD3(); c['bscale'] = r.BD3(); c['brot'] = r.BD(); c['bcolor'] = _cmc3(r); c['bmat'] = [r.BD() for _ in range(BMAT_N)]
        c['base2'] = r.BD3(); c['basedir'] = r.BD3(); c['basevert'] = r.BD3(); c['normrev'] = r.B()
        e['ctx'] = c
        if c.get('has_text') and c.get('loc') and c['th'] and 0 < c['th'] < 1e5:
            e.update(text_loc=c['loc'], text_height=c['th'] * (c['scale'] or 1.0), arrow_size=c['arrow'], text_color=c['color'], text_rot=c['rot'],
                     text_width=c['width'], text_align=c['alignment'], text_attach=(c['left'], c['right']), text_dir=c['dir'])
        m = {}
        if ver == 2: r.p += 20  # 20 bits not interpreted (flags 9, 9 in the samples)
        m['flags'] = r.BL(); m['type'] = r.BS(); m['color'] = _cmc3(r); m['lw'] = r.BL(); m['landing'] = r.B(); m['dogleg'] = r.B(); m['dlen'] = r.BD(); m['asize'] = r.BD()
        m['content'] = r.BS(); m['tleft'] = r.BS(); m['tright'] = r.BS(); m['tangle'] = r.BS(); m['talign'] = r.BS(); m['tcolor'] = _cmc3(r); m['tframe'] = r.B()
        m['bcolor'] = _cmc3(r); m['bscale'] = r.BD3(); m['brot'] = r.BD(); m['bconn'] = r.BS(); m['annot'] = r.B()
        if ver == 2:
            m['narrow'] = r.BL(); m['labels'] = [(r.BS(), r.BD()) for _ in range(r.cnt(m['narrow'], 4))]  # block attribute labels: index, width (text in the string stream, attdef handle in the handle stream)
            m['tdneg'] = r.B(); m['v178'] = r.BS()
            m['v179'] = r.BS(); m['v45'] = r.BD(); m['attdir'] = r.BS(); m['bot'] = r.BS(); m['top'] = r.BS(); m['ext'] = r.B() if o.ver != 'AC1024' else 0
        e['own'] = m
        e['full'] = (r.p == expected_end(o))
        if not e['full'] and ver == 1: r.p = expected_end(o)  # R2007 tail (19 bits after the block connection / annotative flag) not interpreted
    except Exception:
        pass
    return e


def _cmc3(r):
    """CMC as stored in the MULTILEADER data: BS index, BL rgb word (0xC1000000 = by layer style), RC flags."""
    return (r.BS(), r.BL(), r.RC())


# ---- native fast path (dwgfast/, optional): bit-identical results for the hot entity types ----
PY_DECODERS = {}
try:
    import os as _os
    if _os.environ.get('DWG_NO_FAST'): raise ImportError
    import dwgfast as _fast
    if not hasattr(_fast, 'decode_entity'): raise ImportError  # stale build
except ImportError:
    _fast = None
if _fast is not None:
    _VERS = {'AC1015': 15, 'AC1018': 18, 'AC1021': 21, 'AC1024': 24, 'AC1027': 27, 'AC1032': 32}

    class _End:
        __slots__ = ('p',)

        def __init__(self, p): self.p = p

    def _wrap(py_dec):
        _decode = _fast.decode_entity

        def dec(o):
            global LAST_READER
            r = _decode(o.type, o.raw, o.data_bit, o.handle_bit, _VERS[o.ver])
            if r is None: return py_dec(o)
            LAST_READER = _End(r[1])
            return r[0]
        dec.__name__ = py_dec.__name__
        return dec

    for _n in ('decode_line', 'decode_circle_arc', 'decode_point', 'decode_solid', 'decode_3dface', 'decode_ellipse', 'decode_ray', 'decode_lwpolyline', 'decode_insert',
               'decode_minsert', 'decode_polyline2d', 'decode_vertex2d', 'decode_seqend', 'decode_vertex3d', 'decode_polyline3d', 'decode_vertex_pface', 'decode_vertex_pface_face',
               'decode_polyline_pface', 'decode_polyline_mesh', 'decode_spline', 'decode_text', 'decode_attrib', 'decode_mtext', 'decode_hatch', 'decode_dimension'):
        PY_DECODERS[_n] = globals()[_n]
        globals()[_n] = _wrap(globals()[_n])
