"""Non-entity object codecs (tables, dictionaries) on top of dwgcodec (own code)."""
import dwgcodec as C
from dwgcodec import R2010, R2013, WIDE

OBJ = {}          # type -> (main, handles)


def reg(otype, main, handles=None):
    OBJ[otype] = (main, handles)


def _g(d, k, default):
    return d[k] if k in d else default


def entry_head(rw, d):
    """name + xref flags common to all table entries"""
    d['name'] = rw.T(_g(d, 'name', ''))
    d['f64'] = rw.B(_g(d, 'f64', 0))
    if rw.ver in ('AC1015', 'AC1018'): d['xref_idx'] = rw.BS(_g(d, 'xref_idx', 0))
    d['xref_dep'] = rw.B(_g(d, 'xref_dep', 0))


def cmc_full(rw, v):
    """table colour: BS index, BL rgb, RC flags (bit0 name, bit1 book name follow as text)"""
    rd = rw.reading
    if rd:
        idx = rw.BS(); rgb = rw.BL(); fl = rw.RC()
        name = rw.T() if fl & 1 else None
        book = rw.T() if fl & 2 else None
        return (idx, rgb, fl, name, book)
    idx, rgb, fl, name, book = v
    rw.BS(idx); rw.BL(rgb); rw.RC(fl)
    if fl & 1: rw.T(name)
    if fl & 2: rw.T(book)
    return v


def ref_list(rw, d, key, n, code):
    if rw.reading:
        d[key] = [rw.href() for _ in range(n)]
    else:
        for x in d[key]: rw.href(x, code)


# ---------------------------------------------------------------- LAYER
def c_layer(rw, d):
    entry_head(rw, d)
    d['flags'] = rw.BS(_g(d, 'flags', 0x10))
    if rw.ver == 'AC1015':
        d['color'] = (rw.BS(_g(d, 'color', (7,))[0]),)
    else:
        d['color'] = cmc_full(rw, _g(d, 'color', (7, 0, 0, None, None)))


def h_layer(rw, d):
    d['xref'] = rw.href(_g(d, 'xref', 0), 5)
    d['plotstyle'] = rw.href(d.get('plotstyle'), 5)
    if rw.ver in WIDE: d['material'] = rw.href(_g(d, 'material', 0), 5)
    d['ltype'] = rw.href(d.get('ltype'), 5)
    if rw.ver in R2013: d['extra'] = rw.href(_g(d, 'extra', 0), 5)


reg(51, c_layer, h_layer)


# ---------------------------------------------------------------- STYLE
def c_style(rw, d):
    entry_head(rw, d)
    d['shapefile'] = rw.B(_g(d, 'shapefile', 0)); d['vertical'] = rw.B(_g(d, 'vertical', 0))      # bit order checked against AutoCAD IsShapeFile/IsVertical (ltypeshp style: first bit set)
    d['fixed_height'] = rw.BD(_g(d, 'fixed_height', 0.0)); d['width_factor'] = rw.BD(_g(d, 'width_factor', 1.0))
    d['oblique'] = rw.BD(_g(d, 'oblique', 0.0)); d['generation'] = rw.RC(_g(d, 'generation', 0)); d['last_height'] = rw.BD(_g(d, 'last_height', 0.2))
    d['font'] = rw.T(_g(d, 'font', 'txt')); d['bigfont'] = rw.T(_g(d, 'bigfont', ''))


def h_xref_only(rw, d):
    d['xref'] = rw.href(_g(d, 'xref', 0), 5)


reg(53, c_style, h_xref_only)


# ---------------------------------------------------------------- APPID
def c_appid(rw, d):
    entry_head(rw, d)
    d['unknown'] = rw.RC(_g(d, 'unknown', 0))


reg(67, c_appid, h_xref_only)


# ---------------------------------------------------------------- LTYPE
def c_ltype(rw, d):
    rd = rw.reading
    entry_head(rw, d)
    d['description'] = rw.T(_g(d, 'description', ''))
    d['pattern_length'] = rw.BD(_g(d, 'pattern_length', 0.0)); d['alignment'] = rw.RC(_g(d, 'alignment', 65))
    n = rw.RC(len(d.get('dashes', [])) if not rd else None)
    if rd: d['dashes'] = [dict() for _ in range(n)]
    for s in d['dashes']:
        s['length'] = rw.BD(_g(s, 'length', 0.0)); s['shape'] = rw.BS(_g(s, 'shape', 0))
        s['offset'] = rw.RD2(_g(s, 'offset', (0.0, 0.0))); s['scale'] = rw.BD(_g(s, 'scale', 1.0)); s['rotation'] = rw.BD(_g(s, 'rotation', 0.0))
        s['flags'] = rw.BS(_g(s, 'flags', 0))
    has_text = d['dashes'] and any(s['flags'] & 2 for s in d['dashes'])
    if rw.ver in ('AC1015', 'AC1018') or has_text:
        nb = 256 if rw.ver in ('AC1015', 'AC1018') else 512
        if rd:
            d['text_area'] = bytes(rw.m.RC() for _ in range(nb))
        else:
            ta = d.get('text_area') or bytes(nb)
            for c in ta: rw.m.RC(c)


def h_ltype(rw, d):
    d['xref'] = rw.href(_g(d, 'xref', 0), 5)
    for s in d['dashes']:
        s['style'] = rw.href(_g(s, 'style', 0), 5)       # one (usually null) text style reference per dash


reg(57, c_ltype, h_ltype)


# ---------------------------------------------------------------- BLOCK_HEADER
def c_block_header(rw, d):
    rd = rw.reading
    entry_head(rw, d)
    d['anonymous'] = rw.B(_g(d, 'anonymous', 0)); d['has_attribs'] = rw.B(_g(d, 'has_attribs', 0)); d['is_xref'] = rw.B(_g(d, 'is_xref', 0))
    d['overlaid'] = rw.B(_g(d, 'overlaid', 0)); d['loaded'] = rw.B(_g(d, 'loaded', 0))
    if rw.ver != 'AC1015' and not d['is_xref']:
        d['nowned'] = rw.BL(len(d['owned']) if not rd else None)
    else:
        d['nowned'] = 0
    d['base'] = rw.BD3(_g(d, 'base', (0.0, 0.0, 0.0)))
    d['xref_path'] = rw.T(_g(d, 'xref_path', ''))
    if rd:
        n = 0
        while rw.RC(): n += 1
        d['ninserts'] = n
    else:
        for _ in range(len(d.get('inserts', []))): rw.RC(1)
        rw.RC(0)
    d['description'] = rw.T(_g(d, 'description', ''))
    if rd:
        n = rw.BL(); d['preview'] = bytes(rw.m.RC() for _ in range(n))
    else:
        pv = d.get('preview', b'')
        rw.BL(len(pv))
        for c in pv: rw.m.RC(c)
    if rw.ver in WIDE:
        d['units'] = rw.BS(_g(d, 'units', 0)); d['explodable'] = rw.B(_g(d, 'explodable', 1)); d['scaling'] = rw.RC(_g(d, 'scaling', 0))


def h_block_header(rw, d):
    rd = rw.reading
    d['xref'] = rw.href(_g(d, 'xref', 0), 5)
    if not d['is_xref'] and not d['overlaid']:
        d['block'] = rw.href(d.get('block'), 3)
    if rw.ver == 'AC1015':
        d['first'] = rw.href(_g(d, 'first', 0), 4); d['last'] = rw.href(_g(d, 'last', 0), 4)
    elif rd:
        d['owned'] = [rw.href() for _ in range(d['nowned'])]
    else:
        for x in d['owned']: rw.href(x, 3)
    if not d['is_xref'] and not d['overlaid']:
        d['endblk'] = rw.href(d.get('endblk'), 3)
    if rd:
        d['inserts'] = [rw.href() for _ in range(d['ninserts'])]
    else:
        for x in d['inserts']: rw.href(x, 4)
    d['layout'] = rw.href(_g(d, 'layout', 0), 5)


reg(49, c_block_header, h_block_header)


# ---------------------------------------------------------------- control objects (entries are soft owners, a few extra fixed handles follow)
CONTROL_EXTRA = {48: 2, 56: 2}      # BLOCK_CONTROL: model + paper space; LTYPE_CONTROL: ByLayer + ByBlock


def c_control(rw, d):
    d['nentries'] = rw.BL(len(d['entries']) if not rw.reading else None)
    if d['type'] == 68: d['unknown'] = rw.RC(_g(d, 'unknown', 0))


def h_control(rw, d):
    rd = rw.reading
    if rd:
        d['entries'] = [rw.href() for _ in range(d['nentries'])]
        d['extras'] = []
        while rw.more_handles():
            d['extras'].append(rw.href())
    else:
        for x in d['entries']: rw.href(x, 2)
        for x in d.get('extras', []): rw.href(x, 3)


for _t in (48, 50, 52, 56, 60, 62, 64, 66, 68): reg(_t, c_control, h_control)


# ---------------------------------------------------------------- DICTIONARY
def c_dictionary(rw, d):
    rd = rw.reading
    n = rw.BL(len(d['items']) if not rd else None)
    d['cloning'] = rw.BS(_g(d, 'cloning', 1)); d['hard_owner'] = rw.RC(_g(d, 'hard_owner', 0))
    if rd: d['items'] = [[None, None] for _ in range(n)]
    for it in d['items']: it[0] = rw.T(it[0])


def h_dictionary(rw, d):
    for it in d['items']:
        it[1] = rw.href(it[1], 2)


reg(42, c_dictionary, h_dictionary)


# ---------------------------------------------------------------- MLINESTYLE (type 73)
def c_mlstyle(rw, d):
    d['name'] = rw.T(_g(d, 'name', 'STANDARD')); d['description'] = rw.T(_g(d, 'description', ''))
    d['flags'] = rw.BS(_g(d, 'flags', 0))
    if rw.ver == 'AC1015': d['fill'] = (rw.BS(_g(d, 'fill', (256,))[0]),)
    else: d['fill'] = cmc_full(rw, _g(d, 'fill', (256, 0, 0, None, None)))
    d['start_angle'] = rw.BD(_g(d, 'start_angle', 1.5707963267948966)); d['end_angle'] = rw.BD(_g(d, 'end_angle', 1.5707963267948966))
    n = rw.RC(len(d['elements']) if not rw.reading else None)
    if rw.reading: d['elements'] = [{} for _ in range(n)]
    for e in d['elements']:
        e['offset'] = rw.BD(_g(e, 'offset', 0.0))
        if rw.ver == 'AC1015': e['color'] = (rw.BS(_g(e, 'color', (256,))[0]),)
        else: e['color'] = cmc_full(rw, _g(e, 'color', (256, 0, 0, None, None)))
        if rw.ver != 'AC1032': e['ltype_index'] = rw.BS(_g(e, 'ltype_index', 32767))


def h_mlstyle(rw, d):
    if rw.ver == 'AC1032':
        for e in d['elements']: e['ltype'] = rw.href(_g(e, 'ltype', 0), 5)


reg(73, c_mlstyle, h_mlstyle)


# ---------------------------------------------------------------- API
def decode(o, codepage=30, strict=True, key=None):
    main, hnd = OBJ[key if key is not None else o.type]
    rw = C.RW.for_read(o, codepage)
    d = {'type': o.type, 'handle': o.handle}
    rw.m.H()
    C.object_head(rw, d)
    main(rw, d)
    if strict and rw.m.p != rw.main_end:
        raise ValueError('decoder ended at %d, expected %d' % (rw.m.p, rw.main_end))
    C.object_handles(rw, d)
    if hnd: hnd(rw, d)
    d['_extra_h'] = []
    while rw.more_handles():
        d['_extra_h'].append(rw.h.H())
    d['_h'] = list(rw.hlist)
    if rw.nonul: d['_nonul'] = True
    return d


def encode(ver, d, codepage=30, key=None):
    main, hnd = OBJ[key if key is not None else d['type']]
    rw = C.RW.for_write(ver, d['handle'], codepage, d.get('_h'))
    rw.nonul = d.get('_nonul', False)
    rw.m.H(0, d['handle'])
    C.object_head(rw, d)
    main(rw, d)
    C.object_handles(rw, d)
    if hnd: hnd(rw, d)
    for c, v in d.get('_extra_h', []): rw.h.H(c, v)
    return C.finish(rw, d['type'], d['handle'])


# ---------------------------------------------------------------- LAYOUT (type 82 in the R2004 family; class based in AC1015)
def c_layout(rw, d):
    rd = rw.reading
    d['page_setup'] = rw.T(_g(d, 'page_setup', '')); d['printer'] = rw.T(_g(d, 'printer', ''))
    d['plot_flags'] = rw.BS(_g(d, 'plot_flags', 0))
    d['margins'] = tuple(rw.BD(x) for x in (_g(d, 'margins', (0.0,) * 4)))
    d['paper'] = tuple(rw.BD(x) for x in (_g(d, 'paper', (0.0, 0.0))))
    d['paper_size'] = rw.T(_g(d, 'paper_size', ''))
    d['plot_origin'] = tuple(rw.BD(x) for x in (_g(d, 'plot_origin', (0.0, 0.0))))
    d['paper_units'] = rw.BS(_g(d, 'paper_units', 0)); d['rotation'] = rw.BS(_g(d, 'rotation', 0)); d['plot_type'] = rw.BS(_g(d, 'plot_type', 0))
    d['window'] = tuple(rw.BD(x) for x in (_g(d, 'window', (0.0,) * 4)))
    if rw.ver in ('AC1015',):
        d['plot_view_name'] = rw.T(_g(d, 'plot_view_name', ''))
    d['real_world_units'] = rw.BD(_g(d, 'real_world_units', 1.0)); d['drawing_units'] = rw.BD(_g(d, 'drawing_units', 1.0))
    d['style_sheet'] = rw.T(_g(d, 'style_sheet', ''))
    d['scale_type'] = rw.BS(_g(d, 'scale_type', 0)); d['scale_factor'] = rw.BD(_g(d, 'scale_factor', 1.0))
    d['image_origin'] = tuple(rw.BD(x) for x in (_g(d, 'image_origin', (0.0, 0.0))))
    if rw.ver != 'AC1015':
        d['shade_plot'] = rw.BS(_g(d, 'shade_plot', 0)); d['shade_res'] = rw.BS(_g(d, 'shade_res', 0)); d['custom_dpi'] = rw.BS(_g(d, 'custom_dpi', 0))
    d['name'] = rw.T(_g(d, 'name', ''))
    d['tab_order'] = rw.BL(_g(d, 'tab_order', 0)); d['flags'] = rw.BS(_g(d, 'flags', 1))
    d['ucs_origin'] = rw.BD3(_g(d, 'ucs_origin', (0.0, 0.0, 0.0)))
    d['limmin'] = rw.RD2(_g(d, 'limmin', (0.0, 0.0))); d['limmax'] = rw.RD2(_g(d, 'limmax', (12.0, 9.0)))
    d['insbase'] = rw.BD3(_g(d, 'insbase', (0.0, 0.0, 0.0)))
    d['ucs_x'] = rw.BD3(_g(d, 'ucs_x', (1.0, 0.0, 0.0))); d['ucs_y'] = rw.BD3(_g(d, 'ucs_y', (0.0, 1.0, 0.0)))
    d['elevation'] = rw.BD(_g(d, 'elevation', 0.0)); d['ucs_ortho'] = rw.BS(_g(d, 'ucs_ortho', 0))
    d['extmin'] = rw.BD3(_g(d, 'extmin', (1e20, 1e20, 1e20))); d['extmax'] = rw.BD3(_g(d, 'extmax', (-1e20, -1e20, -1e20)))
    if rw.ver != 'AC1015':
        d['nviewports'] = rw.BL(len(d['viewports']) if not rd else None)


def h_layout(rw, d):
    rd = rw.reading
    if rw.ver != 'AC1015': d['plot_style'] = rw.href(_g(d, 'plot_style', 0), 5)
    if rw.ver in WIDE: d['h_extra'] = rw.href(_g(d, 'h_extra', 0), 4)
    d['block'] = rw.href(d.get('block'), 4)
    d['last_viewport'] = rw.href(_g(d, 'last_viewport', 0), 4)
    d['ucs_base'] = rw.href(_g(d, 'ucs_base', 0), 5); d['ucs_named'] = rw.href(_g(d, 'ucs_named', 0), 5)
    if rw.ver != 'AC1015':
        if rd: d['viewports'] = [rw.href() for _ in range(d['nviewports'])]
        else:
            for v in d['viewports']: rw.href(v, 4)


for _k in (82, 'LAYOUT'): reg(_k, c_layout, h_layout)


# ---------------------------------------------------------------- DIMSTYLE (69); field order from the public layout, checked by end position on AutoCAD files
_D_HEAD = [('DIMPOST', 'T'), ('DIMAPOST', 'T'), ('DIMSCALE', 'D'), ('DIMASZ', 'D'), ('DIMEXO', 'D'), ('DIMDLI', 'D'), ('DIMEXE', 'D'), ('DIMRND', 'D'), ('DIMDLE', 'D'),
           ('DIMTP', 'D'), ('DIMTM', 'D')]
_D_2007A = [('DIMFXL', 'D'), ('DIMJOGANG', 'D'), ('DIMTFILL', 'S'), ('DIMTFILLCLR', 'C')]
_D_MID = [('DIMTOL', 'B'), ('DIMLIM', 'B'), ('DIMTIH', 'B'), ('DIMTOH', 'B'), ('DIMSE1', 'B'), ('DIMSE2', 'B'), ('DIMTAD', 'S'), ('DIMZIN', 'S'), ('DIMAZIN', 'S')]
_D_2007B = [('DIMARCSYM', 'S')]
_D_REST = [('DIMTXT', 'D'), ('DIMCEN', 'D'), ('DIMTSZ', 'D'), ('DIMALTF', 'D'), ('DIMLFAC', 'D'), ('DIMTVP', 'D'), ('DIMTFAC', 'D'), ('DIMGAP', 'D'), ('DIMALTRND', 'D'),
           ('DIMALT', 'B'), ('DIMALTD', 'S'), ('DIMTOFL', 'B'), ('DIMSAH', 'B'), ('DIMTIX', 'B'), ('DIMSOXD', 'B'), ('DIMCLRD', 'S'), ('DIMCLRE', 'S'), ('DIMCLRT', 'S'),
           ('DIMADEC', 'S'), ('DIMDEC', 'S'), ('DIMTDEC', 'S'), ('DIMALTU', 'S'), ('DIMALTTD', 'S'), ('DIMAUNIT', 'S'), ('DIMFRAC', 'S'), ('DIMLUNIT', 'S'), ('DIMDSEP', 'S'),
           ('DIMTMOVE', 'S'), ('DIMJUST', 'S'), ('DIMSD1', 'B'), ('DIMSD2', 'B'), ('DIMTOLJ', 'S'), ('DIMTZIN', 'S'), ('DIMALTZ', 'S'), ('DIMALTTZ', 'S'), ('DIMUPT', 'B'),
           ('DIMFIT', 'S')]
_D_2007C = [('DIMFXLON', 'B')]
_D_2010 = [('DIMTXTDIRECTION', 'B'), ('DIMALTMZF', 'D'), ('DIMALTMZS', 'T'), ('DIMMZF', 'D'), ('DIMMZS', 'T')]
_D_TAIL = [('DIMLWD', 'S'), ('DIMLWE', 'S'), ('DIMFLAG', 'B')]
_DEFAULTS = {'D': 0.0, 'S': 0, 'B': 0, 'T': '', 'C': (0, 0, 0, None, None)}


def c_dimstyle(rw, d):
    entry_head(rw, d)
    fields = _D_HEAD + (_D_2007A if rw.ver in WIDE else []) + _D_MID + (_D_2007B if rw.ver in WIDE else []) + _D_REST + (_D_2007C if rw.ver in WIDE else []) \
        + (_D_2010 if rw.ver in R2010 else []) + _D_TAIL
    for name, k in fields:
        if name in ('DIMCLRD', 'DIMCLRE', 'DIMCLRT') and rw.ver != 'AC1015': k = 'C'
        v = _g(d, name, _DEFAULTS[k])
        if k == 'D': d[name] = rw.BD(v)
        elif k == 'S': d[name] = rw.BS(v)
        elif k == 'B': d[name] = rw.B(v)
        elif k == 'T': d[name] = rw.T(v)
        elif k == 'C': d[name] = cmc_full(rw, v)


def h_dimstyle(rw, d):
    d['xref'] = rw.href(_g(d, 'xref', 0), 5)
    d['style'] = rw.href(_g(d, 'style', 0), 5)
    names = ['ldrblk', 'blk', 'blk1', 'blk2'] + (['ltype', 'ltex1', 'ltex2'] if rw.ver in WIDE else [])
    for n in names: d[n] = rw.href(_g(d, n, 0), 5)


reg(69, c_dimstyle, h_dimstyle)


# ---------------------------------------------------------------- XRECORD (79): data kept as bytes; helpers in dwgdoc build / read the group code stream
def c_xrecord(rw, d):
    rd = rw.reading
    if rd:
        n = rw.BL(); d["data"] = bytes(rw.m.RC() for _ in range(n))
    else:
        rw.BL(len(d["data"]))
        for c in d['data']: rw.m.RC(c)
    d['cloning'] = rw.BS(_g(d, 'cloning', 1))


def h_xrecord(rw, d):
    rd = rw.reading
    if rd:
        d['hrefs'] = []
        while rw.more_handles(): d['hrefs'].append(rw.href())
    else:
        for x in d.get('hrefs', []): rw.href(x, 4)


reg(79, c_xrecord, h_xrecord)
