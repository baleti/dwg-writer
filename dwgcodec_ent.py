"""Entity codecs on top of dwgcodec (own code). Field orders: found by experiment / end-position checks in dwgent.py, here made symmetric."""
import dwgcodec as C
from dwgcodec import register, R2010, R2013, WIDE

UP = (0.0, 0.0, 1.0)


def _g(d, k, default):
    return d[k] if k in d else default


# ------------------------------------------------------------------ TEXT / ATTRIB / ATTDEF
def text_fields(rw, d):
    rd = rw.reading
    if rd:
        fl = rw.RC()
    else:
        ins = d['ins']
        fl = 0
        if _g(d, 'elev', 0.0) == 0.0: fl |= 1
        if _g(d, 'align', ins) == ins: fl |= 2
        if _g(d, 'oblique', 0.0) == 0.0: fl |= 4
        if _g(d, 'rot', 0.0) == 0.0: fl |= 8
        if _g(d, 'widthf', 1.0) == 1.0: fl |= 0x10
        if _g(d, 'gen', 0) == 0: fl |= 0x20
        if _g(d, 'halign', 0) == 0: fl |= 0x40
        if _g(d, 'valign', 0) == 0: fl |= 0x80
        rw.RC(fl)
    d['elev'] = 0.0 if fl & 1 else rw.RD(d.get('elev'))
    ins = d['ins'] = rw.RD2(d.get('ins'))
    if fl & 2:
        d['align'] = ins
    elif rd:
        d['align'] = (rw.DD(None, ins[0]), rw.DD(None, ins[1]))
    else:
        rw.DD(d['align'][0], ins[0]); rw.DD(d['align'][1], ins[1])
    d['ext'] = rw.BE(_g(d, 'ext', UP)); d['thickness'] = rw.BT(_g(d, 'thickness', 0.0))
    d['oblique'] = 0.0 if fl & 4 else rw.RD(d.get('oblique'))
    d['rot'] = 0.0 if fl & 8 else rw.RD(d.get('rot'))
    d['height'] = rw.RD(d.get('height'))
    d['widthf'] = 1.0 if fl & 0x10 else rw.RD(d.get('widthf'))
    d['text'] = rw.T(d.get('text', ''))
    d['gen'] = 0 if fl & 0x20 else rw.BS(d.get('gen'))
    d['halign'] = 0 if fl & 0x40 else rw.BS(d.get('halign'))
    d['valign'] = 0 if fl & 0x80 else rw.BS(d.get('valign'))


def c_text(rw, d):
    text_fields(rw, d)


def h_text(rw, d):
    d['style'] = rw.href(d.get('style'), 5)


def c_attrib(rw, d):
    text_fields(rw, d)
    ver = rw.ver
    if ver in R2010: d['version'] = rw.RC(d.get('version', 0))
    if ver == 'AC1032':
        d['attr_type'] = rw.RC(d.get('attr_type', 1))
        if d['attr_type'] > 1:
            raise NotImplementedError('multiline attribute')
    d['tag'] = rw.T(d.get('tag', ''))
    d['field_length'] = rw.BS(d.get('field_length', 0)); d['attflags'] = rw.RC(d.get('attflags', 0))
    if ver in R2010: d['lock_position'] = rw.B(d.get('lock_position', 0))
    if d['type'] == 3:
        if ver in R2010: d['version2'] = rw.RC(d.get('version2', 0))
        d['prompt'] = rw.T(d.get('prompt', ''))


register(1, c_text, h_text)
register(2, c_attrib, h_text)
register(3, c_attrib, h_text)


# ------------------------------------------------------------------ INSERT
def c_insert(rw, d):
    rd = rw.reading
    d['ins'] = rw.BD3(d.get('ins'))
    if rd:
        sf = rw.BB()
        if sf == 0: sx = rw.RD(); sy = rw.DD(None, sx); sz = rw.DD(None, sx)
        elif sf == 1: sx = 1.0; sy = rw.DD(None, 1.0); sz = rw.DD(None, 1.0)
        elif sf == 2: sx = rw.RD(); sy = sz = sx
        else: sx = sy = sz = 1.0
        d['scale'] = (sx, sy, sz)
    else:
        sx, sy, sz = _g(d, 'scale', (1.0, 1.0, 1.0))
        if sx == 1.0 and sy == 1.0 and sz == 1.0: rw.BB(3)
        elif sx == sy == sz: rw.BB(2); rw.RD(sx)
        elif sx == 1.0: rw.BB(1); rw.DD(sy, 1.0); rw.DD(sz, 1.0)
        else: rw.BB(0); rw.RD(sx); rw.DD(sy, sx); rw.DD(sz, sx)
    d['rot'] = rw.BD(_g(d, 'rot', 0.0)); d['ext'] = rw.BD3(_g(d, 'ext', UP))
    d['has_attribs'] = rw.B(_g(d, 'has_attribs', 0))
    if d['has_attribs'] and rw.ver != 'AC1015':
        d['nowned'] = rw.BL(len(d['attribs']) if not rd else None)


def h_insert(rw, d):
    d['bheader'] = rw.href(d.get('bheader'), 5)
    if d['has_attribs']:
        if rw.ver == 'AC1015':
            d['first_attrib'] = rw.href(d.get('first_attrib'), 4); d['last_attrib'] = rw.href(d.get('last_attrib'), 4)
        else:
            if rw.reading:
                d['attribs'] = [rw.href() for _ in range(d['nowned'])]
            else:
                for a in d['attribs']: rw.href(a, 4)
        d['seqend'] = rw.href(d.get('seqend'), 4)


register(7, c_insert, h_insert)


# ------------------------------------------------------------------ LWPOLYLINE
def c_lwpolyline(rw, d):
    rd = rw.reading
    if rd:
        fl = rw.BS()
    else:
        fl = _g(d, 'flags', 0) & ~(1 | 2 | 4 | 8 | 16 | 32 | 1024)
        if _g(d, 'const_width', 0.0): fl |= 4
        if _g(d, 'elevation', 0.0): fl |= 8
        if _g(d, 'thickness', 0.0): fl |= 2
        if _g(d, 'ext', UP) != UP: fl |= 1
        if d.get('bulges') and (any(d['bulges']) or _g(d, 'flags', 0) & 16): fl |= 16
        if d.get('widths'): fl |= 32
        if d.get('ids'): fl |= 1024
        rw.BS(fl)
    d['flags'] = fl
    d['const_width'] = rw.BD(d.get('const_width')) if fl & 4 else 0.0
    d['elevation'] = rw.BD(d.get('elevation')) if fl & 8 else 0.0
    d['thickness'] = rw.BD(d.get('thickness')) if fl & 2 else 0.0
    d['ext'] = rw.BD3(d.get('ext')) if fl & 1 else UP
    if rd:
        n = rw.BL()
        nb = rw.BL() if fl & 16 else 0
        ni = rw.BL() if fl & 1024 else 0
        nw = rw.BL() if fl & 32 else 0
        pts = []
        for i in range(n):
            if i == 0: pts.append(rw.RD2())
            else: pts.append((rw.DD(None, pts[-1][0]), rw.DD(None, pts[-1][1])))
        d['pts'] = pts
        d['bulges'] = [rw.BD() for _ in range(nb)]
        d['ids'] = [rw.BL() for _ in range(ni)]
        d['widths'] = [(rw.BD(), rw.BD()) for _ in range(nw)]
    else:
        pts = d['pts']
        rw.BL(len(pts))
        if fl & 16: rw.BL(len(pts))
        if fl & 1024: rw.BL(len(d['ids']))
        if fl & 32: rw.BL(len(d['widths']))
        for i, p in enumerate(pts):
            if i == 0: rw.RD2(p)
            else: rw.DD(p[0], pts[i - 1][0]); rw.DD(p[1], pts[i - 1][1])
        if fl & 16:
            for b in d['bulges']: rw.BD(b)
        if fl & 1024:
            for x in d['ids']: rw.BL(x)
        if fl & 32:
            for a, b in d['widths']: rw.BD(a); rw.BD(b)


register(77, c_lwpolyline)


# ------------------------------------------------------------------ small ones
def c_solid(rw, d):
    d['thickness'] = rw.BT(_g(d, 'thickness', 0.0)); d['elev'] = rw.BD(_g(d, 'elev', 0.0))
    if rw.reading:
        d['pts'] = [rw.RD2() for _ in range(4)]
    else:
        for p in d['pts']: rw.RD2(p)
    d['ext'] = rw.BE(_g(d, 'ext', UP))


register(31, c_solid)
register(32, c_solid)       # TRACE


def c_ellipse(rw, d):
    d['center'] = rw.BD3(d.get('center')); d['major'] = rw.BD3(d.get('major')); d['ext'] = rw.BD3(_g(d, 'ext', UP))
    d['ratio'] = rw.BD(d.get('ratio')); d['a0'] = rw.BD(_g(d, 'a0', 0.0)); d['a1'] = rw.BD(_g(d, 'a1', 6.283185307179586))


register(35, c_ellipse)


def c_ray(rw, d):
    d['p'] = rw.BD3(d.get('p')); d['v'] = rw.BD3(d.get('v'))


register(40, c_ray)
register(41, c_ray)


def c_3dface(rw, d):
    rd = rw.reading
    if rd:
        noflags = rw.B(); zzero = rw.B()
        p0 = (rw.RD(), rw.RD(), 0.0 if zzero else rw.RD())
        pts = [p0]
        for _ in range(3):
            x = rw.DD(None, pts[-1][0]); y = rw.DD(None, pts[-1][1]); z = rw.DD(None, pts[-1][2])
            pts.append((x, y, z))
        d['pts'] = pts
        d['invisible'] = 0 if noflags else rw.BS()
    else:
        pts = d['pts']
        inv = _g(d, 'invisible', 0)
        zz = pts[0][2] == 0.0
        rw.B(1 if inv == 0 else 0); rw.B(zz)
        rw.RD(pts[0][0]); rw.RD(pts[0][1])
        if not zz: rw.RD(pts[0][2])
        for i in range(1, 4):
            for k in range(3): rw.DD(pts[i][k], pts[i - 1][k])
        if inv: rw.BS(inv)


register(28, c_3dface)


def c_block(rw, d):
    d['name'] = rw.T(d.get('name', ''))


register(4, c_block)
register(5, lambda rw, d: None)
register(6, lambda rw, d: None)       # SEQEND


# ------------------------------------------------------------------ POLYLINE2D / VERTEX2D
def c_polyline2d(rw, d):
    d['flags'] = rw.BS(_g(d, 'flags', 0)); d['curve'] = rw.BS(_g(d, 'curve', 0))
    d['start_width'] = rw.BD(_g(d, 'start_width', 0.0)); d['end_width'] = rw.BD(_g(d, 'end_width', 0.0))
    d['thickness'] = rw.BT(_g(d, 'thickness', 0.0)); d['elev'] = rw.BD(_g(d, 'elev', 0.0)); d['ext'] = rw.BE(_g(d, 'ext', UP))
    if rw.ver != 'AC1015':
        d['nowned'] = rw.BL(len(d['vertices']) if not rw.reading else None)


def h_polyline2d(rw, d):
    if rw.ver == 'AC1015':
        d['first'] = rw.href(d.get('first'), 4); d['last'] = rw.href(d.get('last'), 4)
    elif rw.reading:
        d['vertices'] = [rw.href() for _ in range(d['nowned'])]
    else:
        for v in d['vertices']: rw.href(v, 4)
    d['seqend'] = rw.href(d.get('seqend'), 4)


register(15, c_polyline2d, h_polyline2d)


def c_vertex2d(rw, d):
    rd = rw.reading
    d['flags'] = rw.RC(_g(d, 'flags', 0)); d['p'] = rw.BD3(d.get('p'))
    if rd:
        sw = rw.BD()
        ew = -sw if sw < 0 else rw.BD()
        d['start_width'] = abs(sw); d['end_width'] = ew
        d['same_width'] = sw < 0
    else:
        sw = d.get('start_width', 0.0); ew = d.get('end_width', 0.0)
        if d.get('same_width'): rw.BD(-sw)
        else: rw.BD(sw); rw.BD(ew)
    d['bulge'] = rw.BD(_g(d, 'bulge', 0.0))
    if rw.ver in R2010: d['vid'] = rw.BL(_g(d, 'vid', 0))
    d['tangent'] = rw.BD(_g(d, 'tangent', 0.0))


register(10, c_vertex2d)


def c_polyline3d(rw, d):
    d['flags'] = rw.RC(_g(d, 'flags', 0)); d['flags2'] = rw.RC(_g(d, 'flags2', 0))
    if rw.ver != 'AC1015':
        d['nowned'] = rw.BL(len(d['vertices']) if not rw.reading else None)


def c_vertex3d(rw, d):
    d['flags'] = rw.RC(_g(d, 'flags', 32)); d['p'] = rw.BD3(d.get('p'))


register(16, c_polyline3d, h_polyline2d)
register(11, c_vertex3d)


# ------------------------------------------------------------------ DIMENSION (types 20 ORDINATE .. 26 DIAMETER)
def c_dimension(rw, d):
    rd = rw.reading
    t = d['type']
    if rw.ver in R2010: d['dim_version'] = rw.RC(_g(d, 'dim_version', 0))
    d['ext'] = rw.BD3(_g(d, 'ext', UP)); d['text_mid'] = rw.RD2(d.get('text_mid')); d['elevation'] = rw.BD(_g(d, 'elevation', 0.0))
    d['dflags'] = rw.RC(_g(d, 'dflags', 0))
    d['user_text'] = rw.T(_g(d, 'user_text', ''))
    d['text_rot'] = rw.BD(_g(d, 'text_rot', 0.0)); d['horiz_dir'] = rw.BD(_g(d, 'horiz_dir', 0.0))
    d['ins_scale'] = rw.BD3(_g(d, 'ins_scale', (1.0, 1.0, 1.0))); d['ins_rot'] = rw.BD(_g(d, 'ins_rot', 0.0))
    d['attach'] = rw.BS(_g(d, 'attach', 5)); d['ls_style'] = rw.BS(_g(d, 'ls_style', 1)); d['ls_factor'] = rw.BD(_g(d, 'ls_factor', 1.0))
    d['measurement'] = rw.BD(_g(d, 'measurement', 0.0))
    if rw.ver in WIDE:
        d['unknown_b'] = rw.B(_g(d, 'unknown_b', 0)); d['flip1'] = rw.B(_g(d, 'flip1', 0)); d['flip2'] = rw.B(_g(d, 'flip2', 0))
    d['clone_pt'] = rw.RD2(_g(d, 'clone_pt', (0.0, 0.0)))
    if t == 21:
        for k in ('pt13', 'pt14', 'pt10'): d[k] = rw.BD3(d.get(k))
        d['ext_rot'] = rw.BD(_g(d, 'ext_rot', 0.0)); d['dim_rot'] = rw.BD(_g(d, 'dim_rot', 0.0))
    elif t == 22:
        for k in ('pt13', 'pt14', 'pt10'): d[k] = rw.BD3(d.get(k))
        d['ext_rot'] = rw.BD(_g(d, 'ext_rot', 0.0))
    elif t == 23:
        for k in ('pt10', 'pt13', 'pt14', 'pt15'): d[k] = rw.BD3(d.get(k))
    elif t == 24:
        d['pt16'] = rw.RD2(d.get('pt16'))
        for k in ('pt13', 'pt14', 'pt15', 'pt10'): d[k] = rw.BD3(d.get(k))
    elif t in (25, 26):
        d['pt10'] = rw.BD3(d.get('pt10')); d['pt15'] = rw.BD3(d.get('pt15')); d['leader_len'] = rw.BD(_g(d, 'leader_len', 0.0))
    elif t == 20:
        for k in ('pt10', 'pt13', 'pt14'): d[k] = rw.BD3(d.get(k))
        d['oflags'] = rw.RC(_g(d, 'oflags', 0))


def h_dimension(rw, d):
    d['dimstyle'] = rw.href(d.get('dimstyle'), 5)
    d['dimblock'] = rw.href(d.get('dimblock'), 5)


for _t in range(20, 27): register(_t, c_dimension, h_dimension)


# ------------------------------------------------------------------ LEADER
def c_leader(rw, d):
    rd = rw.reading
    d['unknown_b'] = rw.B(_g(d, 'unknown_b', 0))
    d['annotation'] = rw.BS(_g(d, 'annotation', 3)); d['path'] = rw.BS(_g(d, 'path', 0))
    if rd:
        n = rw.BL(); d['pts'] = [rw.BD3() for _ in range(n)]
    else:
        rw.BL(len(d['pts']))
        for p in d['pts']: rw.BD3(p)
    d['end_proj'] = rw.BD3(_g(d, 'end_proj', (0.0, 0.0, 0.0))); d['ext'] = rw.BD3(_g(d, 'ext', UP))
    d['xdir'] = rw.BD3(_g(d, 'xdir', (1.0, 0.0, 0.0))); d['block_offset'] = rw.BD3(_g(d, 'block_offset', (0.0, 0.0, 0.0)))
    d['annot_offset'] = rw.BD3(_g(d, 'annot_offset', (0.0, 0.0, 0.0)))
    if rw.ver in ('AC1015', 'AC1018'):
        d['box_height'] = rw.BD(_g(d, 'box_height', 0.0)); d['box_width'] = rw.BD(_g(d, 'box_width', 0.0))
    d['hookline_dir'] = rw.B(_g(d, 'hookline_dir', 0)); d['arrowhead'] = rw.B(_g(d, 'arrowhead', 1))
    d['arrow_type'] = rw.BS(_g(d, 'arrow_type', 0)); d['b1'] = rw.B(_g(d, 'b1', 0)); d['b2'] = rw.B(_g(d, 'b2', 0))


def h_leader(rw, d):
    d['annot_h'] = rw.href(d.get('annot_h', 0), 4)
    d['dimstyle'] = rw.href(d.get('dimstyle'), 5)


register(45, c_leader, h_leader)


# ------------------------------------------------------------------ MLINE
def c_mline(rw, d):
    rd = rw.reading
    d['scale'] = rw.BD(_g(d, 'scale', 1.0)); d['justification'] = rw.RC(_g(d, 'justification', 0))
    d['base'] = rw.BD3(d.get('base')); d['ext'] = rw.BD3(_g(d, 'ext', UP))
    d['flags'] = rw.BS(_g(d, 'flags', 1)); d['nlines'] = rw.RC(d.get('nlines'))
    nv = rw.BS(len(d['vertices']) if not rd else None)
    if rd: d['vertices'] = [None] * nv
    for i in range(nv):
        v = d['vertices'][i] if not rd else {}
        v['p'] = rw.BD3(v.get('p')); v['dir'] = rw.BD3(v.get('dir')); v['miter'] = rw.BD3(v.get('miter'))
        if rd: v['elements'] = []
        for k in range(d['nlines']):
            ps, ar = v['elements'][k] if not rd else ([], [])
            if rd:
                ps = [rw.BD() for _ in range(rw.BS())]; ar = [rw.BD() for _ in range(rw.BS())]
                v['elements'].append((ps, ar))
            else:
                rw.BS(len(ps))
                for x in ps: rw.BD(x)
                rw.BS(len(ar))
                for x in ar: rw.BD(x)
        d['vertices'][i] = v


def h_mline(rw, d):
    d['mlstyle'] = rw.href(d.get('mlstyle', 0), 5)


register(47, c_mline, h_mline)


# ------------------------------------------------------------------ MTEXT
def c_mtext(rw, d):
    rd = rw.reading
    ver = rw.ver
    d['ins'] = rw.BD3(d.get('ins')); d['ext'] = rw.BD3(_g(d, 'ext', UP)); d['xdir'] = rw.BD3(_g(d, 'xdir', (1.0, 0.0, 0.0)))
    d['width'] = rw.BD(d.get('width'))
    if ver in WIDE: d['rect_height'] = rw.BD(_g(d, 'rect_height', 0.0))
    d['text_height'] = rw.BD(d.get('text_height')); d['attachment'] = rw.BS(_g(d, 'attachment', 1)); d['drawdir'] = rw.BS(_g(d, 'drawdir', 5))
    d['ext_h'] = rw.BD(_g(d, 'ext_h', 0.0)); d['ext_w'] = rw.BD(_g(d, 'ext_w', 0.0))
    d['text'] = rw.T(d.get('text', ''))
    d['ls_style'] = rw.BS(_g(d, 'ls_style', 1)); d['ls_factor'] = rw.BD(_g(d, 'ls_factor', 1.0)); d['unknown_b'] = rw.B(_g(d, 'unknown_b', 0))
    if ver != 'AC1015':
        d['bg_flags'] = rw.BL(_g(d, 'bg_flags', 0))
        if d['bg_flags'] & 1:
            d['bg_scale'] = rw.BD(_g(d, 'bg_scale', 1.5)); d['bg_color'] = (rw.BS(_g(d, 'bg_color', (0, 0, 0))[0]), rw.BL(_g(d, 'bg_color', (0, 0, 0))[1]),
                                                                           rw.RC(_g(d, 'bg_color', (0, 0, 0))[2])) if not rd else (rw.BS(), rw.BL(), rw.RC())
            d['bg_transp'] = rw.BL(_g(d, 'bg_transp', 0))
    if ver == 'AC1032':
        # R2018 column / annotation block: kept verbatim from the original (new entities use the default no-column block)
        if rd:
            d['tail'] = [rw.m.bit() for _ in range(rw.main_end - rw.m.p)]
        else:
            rw.m.bits.extend(d['tail'] if d.get('tail') is not None else mtext_tail_2018(d))


def mtext_tail_2018(d):
    """R2018 MTEXT trailer for an entity without columns / annotation scales (layout found by differential experiments with AutoCAD):
    12 constant bits, attachment BS, x direction (3 BD), insertion point (3 BD), width, rect height, extents width, extents height, BD 0."""
    import dwgbitw as W
    w = W.BitWriter()
    w.bits.extend([1, 0, 1, 0, 0, 0, 0, 0, 1, 0, 0, 1])
    w.BS(d['attachment'])
    w.BD3(d['xdir']); w.BD3(d['ins'])
    w.BD(d['width']); w.BD(d.get('rect_height', 0.0)); w.BD(d['ext_w']); w.BD(d['ext_h']); w.BD(0.0)
    return w.bits


def h_mtext(rw, d):
    d['style'] = rw.href(d.get('style'), 5)


register(44, c_mtext, h_mtext)


# ------------------------------------------------------------------ SPLINE
def c_spline(rw, d):
    rd = rw.reading
    ver = rw.ver
    d['scenario'] = rw.BL(_g(d, 'scenario', 1))
    if ver in R2013:
        d['sflags'] = rw.BL(_g(d, 'sflags', 0)); d['kparam'] = rw.BL(_g(d, 'kparam', 0))
        sc = 2 if (d['sflags'] & 1) else d['scenario']
    else:
        sc = d['scenario']
    d['degree'] = rw.BL(_g(d, 'degree', 3))
    if sc == 1:
        d['rational'] = rw.B(_g(d, 'rational', 0)); d['closed'] = rw.B(_g(d, 'closed', 0)); d['periodic'] = rw.B(_g(d, 'periodic', 0))
        d['knot_tol'] = rw.BD(_g(d, 'knot_tol', 1e-7)); d['ctrl_tol'] = rw.BD(_g(d, 'ctrl_tol', 1e-7))
        if rd:
            nk = rw.BL(); nc = rw.BL(); weighted = rw.B()
            d['knots'] = [rw.BD() for _ in range(nk)]
            d['ctrl'] = []; d['weights'] = []
            for _ in range(nc):
                d['ctrl'].append(rw.BD3())
                if weighted: d['weights'].append(rw.BD())
        else:
            weighted = bool(d.get('weights'))
            rw.BL(len(d['knots'])); rw.BL(len(d['ctrl'])); rw.B(weighted)
            for k in d['knots']: rw.BD(k)
            for i, c in enumerate(d['ctrl']):
                rw.BD3(c)
                if weighted: rw.BD(d['weights'][i])
    elif sc == 2:
        d['fit_tol'] = rw.BD(_g(d, 'fit_tol', 0.0)); d['tan0'] = rw.BD3(_g(d, 'tan0', (0.0, 0.0, 0.0))); d['tan1'] = rw.BD3(_g(d, 'tan1', (0.0, 0.0, 0.0)))
        if rd:
            nf = rw.BL(); d['fit'] = [rw.BD3() for _ in range(nf)]
        else:
            rw.BL(len(d['fit']))
            for p in d['fit']: rw.BD3(p)


register(36, c_spline)


# ------------------------------------------------------------------ HATCH
def hatch_path(rw, p, ver):
    rd = rw.reading
    p['flags'] = rw.BL(_g(p, 'flags', 0))
    if p['flags'] & 2:       # polyline path
        bulges = p.get('bulge_flag')
        if not rd: bulges = any(s[2] for s in p['segs'])
        p['bulge_flag'] = rw.B(bulges); p['closed'] = rw.B(_g(p, 'closed', 1))
        if rd:
            n = rw.BL(); p['segs'] = []
            for _ in range(n):
                pt = rw.RD2(); b = rw.BD() if p['bulge_flag'] else 0.0
                p['segs'].append(('P', pt, b))
        else:
            rw.BL(len(p['segs']))
            for _, pt, b in p['segs']:
                rw.RD2(pt)
                if bulges: rw.BD(b)
    else:
        if rd:
            n = rw.BL(); p['segs'] = []
            for _ in range(n):
                t = rw.RC()
                if t == 1: p['segs'].append(('L', rw.RD2(), rw.RD2()))
                elif t == 2: p['segs'].append(('A', rw.RD2(), rw.BD(), rw.BD(), rw.BD(), rw.B()))
                elif t == 3: p['segs'].append(('E', rw.RD2(), rw.RD2(), rw.BD(), rw.BD(), rw.BD(), rw.B()))
                elif t == 4:
                    deg = rw.BL(); rat = rw.B(); per = rw.B(); nk = rw.BL(); nc = rw.BL()
                    kn = [rw.BD() for _ in range(nk)]; cp = []
                    for _ in range(nc):
                        pt = rw.RD2(); w = rw.BD() if rat else 1.0; cp.append((pt, w))
                    fit = None
                    if ver in WIDE:
                        nf = rw.BL()
                        if nf: fit = ([rw.RD2() for _ in range(nf)], rw.RD2(), rw.RD2())
                    p['segs'].append(('S', deg, rat, per, kn, cp, fit))
                else:
                    raise ValueError('hatch seg type %d' % t)
        else:
            rw.BL(len(p['segs']))
            for s in p['segs']:
                t = s[0]
                if t == 'L': rw.RC(1); rw.RD2(s[1]); rw.RD2(s[2])
                elif t == 'A': rw.RC(2); rw.RD2(s[1]); rw.BD(s[2]); rw.BD(s[3]); rw.BD(s[4]); rw.B(s[5])
                elif t == 'E': rw.RC(3); rw.RD2(s[1]); rw.RD2(s[2]); rw.BD(s[3]); rw.BD(s[4]); rw.BD(s[5]); rw.B(s[6])
                elif t == 'S':
                    _, deg, rat, per, kn, cp, fit = s
                    rw.RC(4); rw.BL(deg); rw.B(rat); rw.B(per); rw.BL(len(kn)); rw.BL(len(cp))
                    for k in kn: rw.BD(k)
                    for pt, w in cp:
                        rw.RD2(pt)
                        if rat: rw.BD(w)
                    if ver in WIDE:
                        if fit: rw.BL(len(fit[0])); [rw.RD2(x) for x in fit[0]]; rw.RD2(fit[1]); rw.RD2(fit[2])
                        else: rw.BL(0)
    p['nboundary'] = rw.BL(_g(p, 'nboundary', 0))


def c_hatch(rw, d):
    rd = rw.reading
    ver = rw.ver
    if ver != 'AC1015':
        g = d.setdefault('gradient', {})
        g['is_gradient'] = rw.BL(_g(g, 'is_gradient', 0)); g['reserved'] = rw.BL(_g(g, 'reserved', 0))
        g['angle'] = rw.BD(_g(g, 'angle', 0.0)); g['shift'] = rw.BD(_g(g, 'shift', 0.0)); g['single_color'] = rw.BL(_g(g, 'single_color', 0))
        g['tint'] = rw.BD(_g(g, 'tint', 0.0))
        if rd:
            n = rw.BL(); g['colors'] = []
            for _ in range(n):
                v = rw.BD(); c = (rw.BS(), rw.BL(), rw.RC()); g['colors'].append((v, c))
        else:
            rw.BL(len(g.get('colors', [])))
            for v, c in g.get('colors', []): rw.BD(v); rw.BS(c[0]); rw.BL(c[1]); rw.RC(c[2])
        g['name'] = rw.T(_g(g, 'name', ''))
    d['elev'] = rw.BD(_g(d, 'elev', 0.0)); d['ext'] = rw.BD3(_g(d, 'ext', UP)); d['pattern_name'] = rw.T(_g(d, 'pattern_name', 'SOLID'))
    d['solid'] = rw.B(_g(d, 'solid', 1)); d['assoc'] = rw.B(_g(d, 'assoc', 0))
    npaths = rw.BL(len(d['paths']) if not rd else None)
    if rd: d['paths'] = [dict() for _ in range(npaths)]
    for p in d['paths']: hatch_path(rw, p, ver)
    d['style'] = rw.BS(_g(d, 'style', 0)); d['pattern_type'] = rw.BS(_g(d, 'pattern_type', 1))
    if not d['solid']:
        d['pattern_angle'] = rw.BD(_g(d, 'pattern_angle', 0.0)); d['pattern_scale'] = rw.BD(_g(d, 'pattern_scale', 1.0))
        d['pattern_double'] = rw.B(_g(d, 'pattern_double', 0))
        if rd:
            n = rw.BS(); d['pattern_lines'] = []
            for _ in range(n):
                a = rw.BD(); p0 = (rw.BD(), rw.BD()); off = (rw.BD(), rw.BD()); nd = rw.BS()
                d['pattern_lines'].append((a, p0, off, [rw.BD() for _ in range(nd)]))
        else:
            rw.BS(len(d['pattern_lines']))
            for a, p0, off, dl in d['pattern_lines']:
                rw.BD(a); rw.BD(p0[0]); rw.BD(p0[1]); rw.BD(off[0]); rw.BD(off[1]); rw.BS(len(dl))
                for x in dl: rw.BD(x)
    if any(p['flags'] & 4 for p in d['paths']):
        d['pixel'] = rw.BD(_g(d, 'pixel', 0.0))
    if rd:
        n = rw.BL(); d['seeds'] = [rw.RD2() for _ in range(n)]
    else:
        rw.BL(len(d['seeds']))
        for s in d['seeds']: rw.RD2(s)


def h_hatch(rw, d):
    for p in d['paths']:
        if rw.reading: p['boundary'] = [rw.href() for _ in range(p['nboundary'])]
        else:
            for b in p.get('boundary', []): rw.href(b, 4)


register(78, c_hatch, h_hatch)


# ------------------------------------------------------------------ VIEWPORT (34)
def c_viewport(rw, d):
    rd = rw.reading
    wide = rw.ver in WIDE
    d['center'] = rw.BD3(d.get('center')); d['width'] = rw.BD(d.get('width')); d['height'] = rw.BD(d.get('height'))
    d['view_target'] = rw.BD3(_g(d, 'view_target', (0.0, 0.0, 0.0))); d['view_dir'] = rw.BD3(_g(d, 'view_dir', (0.0, 0.0, 1.0)))
    d['twist'] = rw.BD(_g(d, 'twist', 0.0)); d['view_height'] = rw.BD(d.get('view_height')); d['lens'] = rw.BD(_g(d, 'lens', 50.0))
    d['front_clip'] = rw.BD(_g(d, 'front_clip', 0.0)); d['back_clip'] = rw.BD(_g(d, 'back_clip', 0.0)); d['snap_angle'] = rw.BD(_g(d, 'snap_angle', 0.0))
    d['view_center'] = rw.RD2(_g(d, 'view_center', (0.0, 0.0))); d['snap_base'] = rw.RD2(_g(d, 'snap_base', (0.0, 0.0)))
    d['snap_spacing'] = rw.RD2(_g(d, 'snap_spacing', (10.0, 10.0))); d['grid_spacing'] = rw.RD2(_g(d, 'grid_spacing', (10.0, 10.0)))
    d['circle_zoom'] = rw.BS(_g(d, 'circle_zoom', 1000))
    if wide: d['grid_major'] = rw.BS(_g(d, 'grid_major', 5))
    d['nfrozen'] = rw.BL(len(d['frozen']) if not rd else None)
    d['status'] = rw.BL(_g(d, 'status', 0))
    d['stylesheet'] = rw.T(_g(d, 'stylesheet', ''))
    d['render_mode'] = rw.RC(_g(d, 'render_mode', 0)); d['ucs_at_origin'] = rw.B(_g(d, 'ucs_at_origin', 0)); d['ucs_per_vp'] = rw.B(_g(d, 'ucs_per_vp', 1))
    d['ucs_origin'] = rw.BD3(_g(d, 'ucs_origin', (0.0, 0.0, 0.0))); d['ucs_x'] = rw.BD3(_g(d, 'ucs_x', (1.0, 0.0, 0.0))); d['ucs_y'] = rw.BD3(_g(d, 'ucs_y', (0.0, 1.0, 0.0)))
    d['ucs_elev'] = rw.BD(_g(d, 'ucs_elev', 0.0)); d['ucs_ortho'] = rw.BS(_g(d, 'ucs_ortho', 0))
    if rw.ver != 'AC1015': d['shade_plot'] = rw.BS(_g(d, 'shade_plot', 0))
    if wide:
        d['default_lights'] = rw.B(_g(d, 'default_lights', 1)); d['lighting_type'] = rw.RC(_g(d, 'lighting_type', 1))
        d['brightness'] = rw.BD(_g(d, 'brightness', 0.0)); d['contrast'] = rw.BD(_g(d, 'contrast', 0.0))
        d['ambient'] = (rw.BS(_g(d, 'ambient', (0, 0, 0))[0]), rw.BL(_g(d, 'ambient', (0, 0, 0))[1]), rw.RC(_g(d, 'ambient', (0, 0, 0))[2])) if not rd else (rw.BS(), rw.BL(), rw.RC())


def h_viewport(rw, d):
    rd = rw.reading
    if rd:
        d['frozen'] = [rw.href() for _ in range(d['nfrozen'])]
        d['tail_h'] = []
        while rw.more_handles(): d['tail_h'].append(rw.href())
    else:
        for x in d['frozen']: rw.href(x, 4)
        codes = [5, 5, 5, 4, 5, 4, 3] if rw.ver in WIDE else ([5, 5, 5, 5] if rw.ver == 'AC1015' else [5, 5, 5])
        tail = d.get('tail_h') or [0] * len(codes)
        for c, x in zip(codes, tail): rw.href(x, c)


register(34, c_viewport, h_viewport)


# ------------------------------------------------------------------ MULTILEADER (class based, R2010+; layout as in dwgent.decode_multileader)
def _cmc3(rw, v):
    return (rw.BS(v[0] if v else 0), rw.BL(v[1] if v else 0xC1000000), rw.RC(v[2] if v else 0))


def _list(rw, lst, item):
    """count (BL) + items; reading builds the list"""
    n = rw.BL(len(lst) if not rw.reading else None)
    if rw.reading: lst = [None] * n
    return [item(x) for x in lst]


def c_mleader(rw, d):
    rd = rw.reading
    if rw.ver not in ('AC1024', 'AC1027', 'AC1032'): raise NotImplementedError('MULTILEADER codec needs R2010+')
    d['cver'] = rw.BS(_g(d, 'cver', 2))
    if d['cver'] != 2: raise NotImplementedError('MULTILEADER class version %r' % d['cver'])
    roots = _list(rw, d.get('roots', []), lambda n: n or {})
    d['roots'] = roots
    for n in roots:
        n['has_last'] = rw.B(_g(n, 'has_last', 1)); n['has_dogleg'] = rw.B(_g(n, 'has_dogleg', 1))
        n['conn'] = rw.BD3(n.get('conn')); n['dir'] = rw.BD3(_g(n, 'dir', (1.0, 0.0, 0.0)))
        n['breaks'] = _list(rw, n.get('breaks', []), lambda b: (rw.BD3(b[0] if b else None), rw.BD3(b[1] if b else None)))
        n['branch'] = rw.BL(_g(n, 'branch', 0)); n['land'] = rw.BD(_g(n, 'land', 0.0))

        def line(L):
            L = L or {}
            L['pts'] = _list(rw, L.get('pts', []), lambda p: rw.BD3(p))
            L['breaks'] = _list(rw, L.get('breaks', []), lambda b: (rw.BD3(b[0] if b else None), rw.BD3(b[1] if b else None)))
            L['index'] = rw.BL(_g(L, 'index', 0)); L['path'] = rw.BS(_g(L, 'path', 0)); L['color'] = _cmc3(rw, L.get('color'))
            L['lw'] = rw.BL(_g(L, 'lw', 0xFFFFFFFF)); L['arrow'] = rw.BD(_g(L, 'arrow', 0.0)); L['flags'] = rw.BL(_g(L, 'flags', 0))
            return L
        n['lines'] = _list(rw, n.get('lines', []), line)
        n['attach'] = rw.BS(_g(n, 'attach', 0))
    c = d.setdefault('ctx', {})
    c['scale'] = rw.BD(c.get('scale')); c['base'] = rw.BD3(c.get('base')); c['th'] = rw.BD(c.get('th')); c['arrow'] = rw.BD(c.get('arrow')); c['gap'] = rw.BD(c.get('gap'))
    c['left'] = rw.BS(c.get('left')); c['right'] = rw.BS(c.get('right')); c['align'] = rw.BS(c.get('align')); c['attach_type'] = rw.BS(c.get('attach_type'))
    c['has_text'] = rw.B(c.get('has_text'))
    if c['has_text']:
        c['text'] = rw.T(c.get('text'))
        c['normal'] = rw.BD3(c.get('normal')); c['loc'] = rw.BD3(c.get('loc')); c['dir'] = rw.BD3(c.get('dir')); c['rot'] = rw.BD(c.get('rot'))
        c['width'] = rw.BD(c.get('width')); c['height'] = rw.BD(c.get('height')); c['lsf'] = rw.BD(c.get('lsf')); c['lss'] = rw.BS(c.get('lss'))
        c['color'] = _cmc3(rw, c.get('color')); c['alignment'] = rw.BS(c.get('alignment')); c['flow'] = rw.BS(c.get('flow')); c['bgcolor'] = _cmc3(rw, c.get('bgcolor'))
        c['bgscale'] = rw.BD(c.get('bgscale')); c['bgtrans'] = rw.BL(c.get('bgtrans')); c['bgfill'] = rw.B(c.get('bgfill')); c['bgmask'] = rw.B(c.get('bgmask'))
        c['coltype'] = rw.BS(c.get('coltype')); c['hauto'] = rw.B(c.get('hauto')); c['colw'] = rw.BD(c.get('colw')); c['colg'] = rw.BD(c.get('colg'))
        c['colrev'] = rw.B(c.get('colrev')); c['colsizes'] = _list(rw, c.get('colsizes', []), lambda x: rw.BD(x)); c['wordbreak'] = rw.B(c.get('wordbreak'))
    c['has_block'] = rw.B(c.get('has_block'))
    if c['has_block']:
        c['bnormal'] = rw.BD3(c.get('bnormal')); c['bloc'] = rw.BD3(c.get('bloc')); c['bscale'] = rw.BD3(c.get('bscale')); c['brot'] = rw.BD(c.get('brot'))
        c['bcolor'] = _cmc3(rw, c.get('bcolor')); c['bmat'] = [rw.BD(x) for x in (c.get('bmat') or [None] * 16)]
    c['base2'] = rw.BD3(c.get('base2')); c['basedir'] = rw.BD3(c.get('basedir')); c['basevert'] = rw.BD3(c.get('basevert')); c['normrev'] = rw.B(c.get('normrev'))
    d['unk20'] = rw.raw_bits(20, d.get('unk20'))
    m = d.setdefault('own', {})
    m['flags'] = rw.BL(m.get('flags')); m['type'] = rw.BS(m.get('type')); m['color'] = _cmc3(rw, m.get('color')); m['lw'] = rw.BL(m.get('lw'))
    m['landing'] = rw.B(m.get('landing')); m['dogleg'] = rw.B(m.get('dogleg')); m['dlen'] = rw.BD(m.get('dlen')); m['asize'] = rw.BD(m.get('asize'))
    m['content'] = rw.BS(m.get('content')); m['tleft'] = rw.BS(m.get('tleft')); m['tright'] = rw.BS(m.get('tright')); m['tangle'] = rw.BS(m.get('tangle'))
    m['talign'] = rw.BS(m.get('talign')); m['tcolor'] = _cmc3(rw, m.get('tcolor')); m['tframe'] = rw.B(m.get('tframe'))
    m['bcolor'] = _cmc3(rw, m.get('bcolor')); m['bscale'] = rw.BD3(m.get('bscale')); m['brot'] = rw.BD(m.get('brot')); m['bconn'] = rw.BS(m.get('bconn')); m['annot'] = rw.B(m.get('annot'))
    m['labels'] = _list(rw, m.get('labels', []), lambda x: (rw.BS(x[0] if x else None), rw.BD(x[1] if x else None)))
    m['tdneg'] = rw.B(m.get('tdneg')); m['v178'] = rw.BS(m.get('v178')); m['v179'] = rw.BS(m.get('v179')); m['v45'] = rw.BD(m.get('v45')); m['attdir'] = rw.BS(m.get('attdir'))
    m['bot'] = rw.BS(m.get('bot')); m['top'] = rw.BS(m.get('top'))
    if rw.ver != 'AC1024': m['ext'] = rw.B(m.get('ext'))
    # strings after the first one (block attribute label texts ...): kept verbatim
    if rd:
        d['sstail'] = [rw.s.bit() for _ in range(rw.s_end - rw.s.p)] if rw.s is not None else []
    else:
        if d.get('sstail'): rw.s.bits.extend(d['sstail']); rw.nstr = max(rw.nstr, 1)


C.CLASS_ENT['MULTILEADER'] = c_mleader


# ------------------------------------------------------------------ WIPEOUT / IMAGE (class based; layout as in dwgent.decode_wipeout; image definition handles verbatim)
def c_wipeout(rw, d):
    d['cv'] = rw.BL(_g(d, 'cv', 0))
    d['pt0'] = rw.BD3(d.get('pt0')); d['uvec'] = rw.BD3(d.get('uvec')); d['vvec'] = rw.BD3(d.get('vvec')); d['size'] = rw.RD2(d.get('size'))
    d['display'] = rw.BS(_g(d, 'display', 7)); d['clipping'] = rw.B(_g(d, 'clipping', 1))
    d['brightness'] = rw.RC(_g(d, 'brightness', 50)); d['contrast'] = rw.RC(_g(d, 'contrast', 50)); d['fade'] = rw.RC(_g(d, 'fade', 0))
    if rw.ver in ('AC1024', 'AC1027', 'AC1032'): d['clip_mode'] = rw.B(_g(d, 'clip_mode', 0))
    d['clip_type'] = rw.BS(_g(d, 'clip_type', 2))
    if d['clip_type'] == 2:
        n = rw.BL(len(d['clip']) if not rw.reading else None)
    else:
        n = 2
    if rw.reading: d['clip'] = [None] * n
    d['clip'] = [rw.RD2(p) for p in d['clip']]


C.CLASS_ENT['WIPEOUT'] = c_wipeout
C.CLASS_ENT['IMAGE'] = c_wipeout
