"""Table objects (LAYER, STYLE, LTYPE, DIMSTYLE ...) for the R2004 family."""
import dwgbits as B
import dwgent
from dwgmodel import noent_common, decode_tv


MARKS = {}


def _rd(o, r):
    wide = o.ver not in ('AC1015', 'AC1018')
    ss = dwgent.string_stream(o) if wide else None
    if wide:
        return (lambda: ss.TU()) if ss else (lambda: r.TU())
    return lambda: decode_tv(r.TV(), getattr(o, 'codepage', 30))


def cmc_full(r, rd):
    idx = r.BS(); rgb = r.BL(); cb = r.RC()
    name = rd() if cb & 1 else None
    book = rd() if cb & 2 else None
    return (idx, rgb, cb, name, book)


def xref_part(r, o):
    """64-flag B, xref index+1 BS (absent from R2007 on), xref-dependent B."""
    r.B()
    if o.ver in ('AC1015', 'AC1018'):
        r.BS()
    r.B()


def decode_layer(o):
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd()
    xref_part(r, o)
    fl = r.BS()
    col = cmc_full(r, rd)
    idx, rgb, cb = col[0], col[1], col[2]
    method = (rgb >> 24) & 0xFF if rgb is not None else 0
    aci = idx; true = None
    if method == 0xC3: aci = rgb & 0xFF
    elif method == 0xC2: aci = None; true = ((rgb >> 16) & 255, (rgb >> 8) & 255, rgb & 255)
    return dict(kind='LAYER', name=name, flags=fl, frozen=bool(fl & 1), off=bool(fl & 2), frozen_new_vp=bool(fl & 4), locked=bool(fl & 8), plot=bool(fl & 16),
                lineweight=(fl >> 5) & 0x1F, color=aci, true_color=true, color_rgb=rgb)


def decode_style(o):
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd()
    xref_part(r, o)
    shapefile = r.B(); vertical = r.B()      # first bit = shape file (AutoCAD IsShapeFile on the ltypeshp style)
    flags = (1 if shapefile else 0) | (4 if vertical else 0)
    return flags, name, r, rd


def decode_style_full(o):
    flags, name, r, rd = decode_style(o)
    fixed_h = r.BD(); width = r.BD(); oblique = r.BD(); gen = r.RC(); last_h = r.BD(); font = rd(); bigfont = rd()
    return dict(kind='STYLE', name=name, shape_file=bool(flags & 1), vertical=bool(flags & 4), fixed_height=fixed_h, width_factor=width, oblique=oblique,
                generation=gen, last_height=last_h, font=font, bigfont=bigfont)


def decode_ltype(o):
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd()
    xref_part(r, o)
    desc = rd(); length = r.BD(); align = r.RC(); n = r.RC()
    dashes = []
    for _ in range(r.cnt(n, 8)):
        d = r.BD(); shape = r.BS(); xoff = r.RD(); yoff = r.RD(); scale = r.BD(); rot = r.BD(); flags = r.BS()
        dashes.append(dict(length=d, shape=shape, offset=(xoff, yoff), scale=scale, rotation=rot, flags=flags))
    text_area = None
    if o.ver == 'AC1018' or (any(d['flags'] & 2 for d in dashes) and o.ver != 'AC1015'):
        # complex linetype text area: 256 bytes (R2004) / 512 bytes (R2007+), found from the residual bit count
        nb = 256 if o.ver == 'AC1018' else 512
        text_area = r.rcs(nb)
        raw = bytes(text_area)
        if o.ver == 'AC1018':
            parts = [decode_tv(p.decode('latin1'), getattr(o, 'codepage', 30)) for p in raw.split(b'\0') if p]
        else:
            parts = [t for t in raw.decode('utf-16le', 'replace').split('\0') if t]
        it = iter(parts)
        for dsh in dashes:
            if dsh['flags'] & 2: dsh['text'] = next(it, '')
    return dict(kind='LTYPE', name=name, description=desc, pattern_length=length, alignment=align, dashes=dashes, text_area=text_area)


def decode_block_header(o):
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd()
    xref_part(r, o)
    anonymous = r.B(); hasatts = r.B(); is_xref = r.B(); overlaid = r.B()
    loaded = r.B()
    MARKS['nowned'] = r.p
    nowned = r.BL() if o.ver != 'AC1015' and not is_xref else 0  # xref blocks own no entities: no count
    MARKS['nowned_end'] = r.p
    base = r.BD3()
    xref_path = rd()
    inserts = 0
    while True:
        c = r.RC()
        if c == 0: break
        inserts += 1
    desc = rd()
    psz = r.BL()
    preview = r.rcs(psz) if psz else b''
    units = explodable = scaling = None
    if o.ver not in ('AC1015', 'AC1018'):
        units = r.BS(); explodable = r.B(); scaling = r.RC()
    return dict(kind='BLOCK_HEADER', name=name, anonymous=bool(anonymous), has_attribs=bool(hasatts), is_xref=bool(is_xref), overlaid=bool(overlaid),
                loaded=bool(loaded), nowned=nowned, base=base, xref_path=xref_path, ninserts=inserts, description=desc, preview_size=psz,
                units=units, explodable=explodable, scaling=scaling)


def decode_view(o):
    """VIEW table record (type 61): name, view height/width/centre, target, direction, twist, lens length, clip distances (equal to AutoCAD's named views;
    the mode, render and UCS-association bits after the clip distances are not decoded)."""
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd()
    xref_part(r, o)
    h = r.BD(); w = r.BD(); cx = r.RD(); cy = r.RD()
    return dict(kind='VIEW', name=name, height=h, width=w, center=(cx, cy), target=r.BD3(), direction=r.BD3(), twist=r.BD(), lens=r.BD(), front_clip=r.BD(), back_clip=r.BD())


def decode_ucs(o):
    """UCS table record (type 63): name, origin, X axis, Y axis."""
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd()
    xref_part(r, o)
    return dict(kind='UCS', name=name, origin=r.BD3(), xaxis=r.BD3(), yaxis=r.BD3())


def decode_vport(o):
    """VPORT table record (type 65, model space viewport configuration; '*Active' is the last model space view): view height, width, centre, target,
    direction, twist, lens length, clip distances. Equal to AutoCAD's viewports_table; the grid, snap and corner fields after them are not decoded."""
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd()
    xref_part(r, o)
    h = r.BD(); w = r.BD(); cx = r.RD(); cy = r.RD()
    return dict(kind='VPORT', name=name, height=h, width=w, aspect=(w / h if h else 0.0), center=(cx, cy), target=r.BD3(), direction=r.BD3(), twist=r.BD(), lens=r.BD(), front_clip=r.BD(), back_clip=r.BD())


def decode_dimstyle(o):
    """DIMSTYLE table record (type 69): all dimension variables. Order as in the header variable list, validated against the AutoCAD dump."""
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd()
    xref_part(r, o)
    new = o.ver != 'AC1015'
    wide = o.ver not in ('AC1015', 'AC1018')
    v = dict(kind='DIMSTYLE', name=name)
    try:
        import dwgmodel
        hs = [h for c, h in dwgmodel.owner_and_layer(o)]
        k = 8 if wide else 5
        if len(hs) >= k + 1:
            ks = ('DIMTXSTY', 'DIMLDRBLK', 'DIMBLK', 'DIMBLK1', 'DIMBLK2') + (('DIMLTYPE', 'DIMLTEX1', 'DIMLTEX2') if wide else ())
            v['handles'] = dict(zip(ks, hs[-k:]))
    except Exception: pass
    v['DIMPOST'] = rd(); v['DIMAPOST'] = rd()
    for k in ('DIMSCALE', 'DIMASZ', 'DIMEXO', 'DIMDLI', 'DIMEXE', 'DIMRND', 'DIMDLE', 'DIMTP', 'DIMTM'): v[k] = r.BD()
    if wide:
        v['DIMFXL'] = r.BD(); v['DIMJOGANG'] = r.BD(); v['DIMTFILL'] = r.BS(); v['DIMTFILLCLR'] = cmc_full(r, rd)
    for k in ('DIMTOL', 'DIMLIM', 'DIMTIH', 'DIMTOH', 'DIMSE1', 'DIMSE2'): v[k] = r.B()
    for k in ('DIMTAD', 'DIMZIN', 'DIMAZIN'): v[k] = r.BS()
    if wide: v['DIMARCSYM'] = r.BS()
    for k in ('DIMTXT', 'DIMCEN', 'DIMTSZ', 'DIMALTF', 'DIMLFAC', 'DIMTVP', 'DIMTFAC', 'DIMGAP', 'DIMALTRND'): v[k] = r.BD()
    v['DIMALT'] = r.B(); v['DIMALTD'] = r.BS()
    for k in ('DIMTOFL', 'DIMSAH', 'DIMTIX', 'DIMSOXD'): v[k] = r.B()
    for k in ('DIMCLRD', 'DIMCLRE', 'DIMCLRT'): v[k] = cmc_full(r, rd) if new else (r.BS(),)
    for k in ('DIMADEC', 'DIMDEC', 'DIMTDEC', 'DIMALTU', 'DIMALTTD', 'DIMAUNIT', 'DIMFRAC', 'DIMLUNIT', 'DIMDSEP', 'DIMTMOVE', 'DIMJUST'): v[k] = r.BS()
    v['DIMSD1'] = r.B(); v['DIMSD2'] = r.B()
    for k in ('DIMTOLJ', 'DIMTZIN', 'DIMALTZ', 'DIMALTTZ'): v[k] = r.BS()
    v['DIMUPT'] = r.B(); v['DIMATFIT'] = r.BS()
    if wide:
        v['DIMFXLON'] = r.B()
        try:
            if o.ver not in ('AC1021',):
                v['DIMTXTDIRECTION'] = r.B(); v['DIMALTMZF'] = r.BD(); v['DIMALTMZS'] = rd(); v['DIMMZF'] = r.BD(); v['DIMMZS'] = rd()
            v['DIMLWD'] = r.BS(); v['DIMLWE'] = r.BS()
        except Exception: pass
        return v
    v['DIMLWD'] = r.BS(); v['DIMLWE'] = r.BS()
    return v


def decode_dictionary(o):
    """DICTIONARY (type 42) / ACDBDICTIONARYWDFLT: names in the main/string stream, item handles in the handle stream after owner, reactors and xdictionary.
    Returns dict(kind, names [str], item handles must be resolved by the caller from the handle stream: see dwgmodel.Model.dictionary())."""
    r = dwgent.start_reader(o)
    eed, nre = noent_common(r, o.ver)
    xdic_missing = None
    rd = _rd(o, r)
    n = r.BL()
    if o.ver in ('AC1015', 'AC1018'): r.BS(); r.RC()   # cloning flag BS, hard owner RC
    else: r.RC(); r.RC()
    r.cnt(n, 8)
    names = [rd() for _ in range(n)]
    return dict(kind='DICTIONARY', names=names, nre=nre)


def decode_scale(o):
    """SCALE (class, annotation scale): BS flag, name, BD paper units, BD drawing units, B is unit scale."""
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    flag = r.BS(); name = rd(); paper = r.BD(); drawing = r.BD(); unit = r.B()
    return dict(kind='SCALE', name=name, paper=paper, drawing=drawing, unit_scale=unit)


def decode_mlstyle(o):
    """MLINESTYLE (type 73): name, description, BS flags (file bits measured with AutoCAD: 1 miters, 2 fill, 16 start square cap, 32 start round cap, 64 start inner arcs), fill CMC,
    start/end angle, RC element count, per element BD offset, CMC colour, linetype (BS index before R2018, handle stream later)."""
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    name = rd(); desc = rd(); flags = r.BS(); fill = cmc_full(r, rd) if o.ver != 'AC1015' else (r.BS(), 0, 0, None, None); a0 = r.BD(); a1 = r.BD(); n = r.RC()
    els = []
    for _ in range(n):
        off = r.BD(); col = cmc_full(r, rd) if o.ver != 'AC1015' else (r.BS(), 0, 0, None, None); lt = r.BS() if o.ver != 'AC1032' else None
        m = (col[1] >> 24) & 0xFF if col[1] else 0
        els.append(dict(offset=off, color=256 if m == 0xC0 else 257 if m == 0xC1 else (col[1] & 0xFF) if m == 0xC3 else col[0], rgb=col[1] & 0xFFFFFF if m == 0xC2 else None, ltype_index=lt))
    return dict(kind='MLINESTYLE', name=name, description=desc, flags=flags, fill_color=fill[0], start_angle=a0, end_angle=a1, elements=els)


def decode_mleaderstyle(o):
    """MLEADERSTYLE (class, R2010+): version BS, content type, draw orders, max leader points, first/second segment angle, leader type, line colour, lineweight, landing/dogleg,
    description, arrow size, default text, text attachments and alignment, text colour/height/frame, block fields, scale, annotative flag, break gap, R2010 attach
    directions. Handles (line type, arrow block, text style, content block) are in the handle stream and not resolved here. Field order from the DXF group order,
    checked against AutoCAD (chk_mleaderstyle_dxf.py)."""
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    d = dict(kind='MLEADERSTYLE')
    d['version'] = r.BS(); d['content_type'] = r.BS(); d['draw_mleader_order'] = r.BS(); d['draw_leader_order'] = r.BS(); d['max_points'] = r.BL()
    d['first_angle'] = r.BD(); d['second_angle'] = r.BD(); d['leader_type'] = r.BS()
    d['line_color'] = cmc_full(r, rd)[:3]; d['line_weight'] = r.BL()
    d['landing'] = r.B(); d['landing_gap'] = r.BD(); d['dogleg'] = r.B(); d['dogleg_length'] = r.BD()
    d['description'] = rd(); d['arrow_size'] = r.BD(); d['default_text'] = rd()
    d['text_left_attach'] = r.BS(); d['text_right_attach'] = r.BS(); d['text_angle_type'] = r.BS(); d['text_align'] = r.BS()
    d['text_color'] = cmc_full(r, rd)[:3]; d['text_height'] = r.BD(); d['text_frame'] = r.B(); d['text_always_left'] = r.B(); d['align_space'] = r.BD()
    d['block_color'] = cmc_full(r, rd)[:3]; d['block_scale'] = r.BD3(); d['block_scale_on'] = r.B(); d['block_rotation'] = r.BD(); d['block_rotation_on'] = r.B()
    d['block_connection'] = r.BS(); d['scale'] = r.BD(); d['annotative'] = r.B(); d['overwrite'] = r.B(); d['break_gap'] = r.BD()
    return d


def decode_dictvar(o):
    """DICTIONARYVAR (class): RC int value, TV string value."""
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    rd = _rd(o, r)
    return dict(kind='DICTIONARYVAR', intval=r.RC(), value=rd())


_XR_STR = set(list(range(1, 10)) + [100, 101, 102] + list(range(300, 310)) + list(range(410, 420)) + list(range(430, 440)) + list(range(470, 480)) + [999] + [1000, 1001, 1002, 1003])
_XR_DBL3 = set(list(range(10, 40)) + list(range(110, 140)) + list(range(210, 240)) + [1010, 1011, 1012, 1013])
_XR_DBL = set(list(range(40, 60)) + list(range(140, 150)) + list(range(460, 470)) + [1040, 1041, 1042])
_XR_RS = set(list(range(60, 80)) + list(range(170, 180)) + list(range(270, 290)) + list(range(370, 390)) + list(range(400, 410)) + [1060, 1070])
_XR_RL = set(list(range(90, 100)) + list(range(420, 430)) + list(range(440, 460)) + [1071])
_XR_HANDLE = set(list(range(105, 106)) + list(range(320, 370)) + list(range(390, 400)) + list(range(480, 482)) + [1005])


def decode_xrecord(o):
    """XRECORD (type 79): BL data size, then (RS group code, value) pairs coded as in DXF (strings: RS length [+ code page byte before R2007] + chars,
    10-39 three doubles, 40-59 double, 60-79/170-179/270-289 RS, 90-99 RL, 290-299 RC, 310-319 RC length + bytes, 320-369 8-byte handle, ...).
    Returns dict(kind, data=[(code, value)], cloning)."""
    import struct
    r = dwgent.start_reader(o)
    noent_common(r, o.ver)
    n = r.BL()
    r.cnt(n, 8)
    raw = r.rcs(n)
    wide = o.ver not in ('AC1015', 'AC1018')
    out = []; p = 0; L = len(raw)
    try:
        while p + 2 <= L:
            code = raw[p] | raw[p + 1] << 8; p += 2
            if code in _XR_STR:
                ln = raw[p] | raw[p + 1] << 8; p += 2
                if wide: s = raw[p:p + 2 * ln].decode('utf-16le', 'replace'); p += 2 * ln
                else: p += 1; s = decode_tv(raw[p:p + ln].decode('latin1'), 30); p += ln
                out.append((code, s.rstrip('\0')))
            elif code in _XR_DBL3: out.append((code, struct.unpack_from('<3d', raw, p))); p += 24
            elif code in _XR_DBL: out.append((code, struct.unpack_from('<d', raw, p)[0])); p += 8
            elif code in _XR_RS: out.append((code, struct.unpack_from('<h', raw, p)[0])); p += 2
            elif code in _XR_RL: out.append((code, struct.unpack_from('<i', raw, p)[0])); p += 4
            elif 290 <= code <= 299: out.append((code, raw[p])); p += 1
            elif 310 <= code <= 319: ln = raw[p]; out.append((code, bytes(raw[p + 1:p + 1 + ln]))); p += 1 + ln
            elif code in _XR_HANDLE: out.append((code, int.from_bytes(raw[p:p + 8], 'little'))); p += 8
            elif 1004 == code: ln = raw[p]; out.append((code, bytes(raw[p + 1:p + 1 + ln]))); p += 1 + ln
            else:
                out.append((code, None)); break
    except (IndexError, struct.error):
        pass
    return dict(kind='XRECORD', data=out, size=n, consumed=p)
