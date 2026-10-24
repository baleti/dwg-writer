"""Header variables (AcDb:Header) for the R2000 / R2004 layouts: the leading part of the bit-coded variable list.
Provenance: order of the variables from the public DWG format description (read, not copied), values validated against the AutoCAD dump
(oracle-out dump.json header) on corpus files; anything not validated is marked in NOTES.md."""
import struct
import dwgbits as B
import dwgfmt as F
import dwgload


def header_bits(buf, info, ver):
    h = dwgload.section(buf, info, 'AcDb:Header') if info else None
    return h


def header_vars(buf, info, ver):
    """Header variables of a loaded file (R2004 family): dict, see decode_header. AC1015 and AC1021 are not supported yet."""
    if ver == 'AC1015':
        import dwgfmt as _F
        hv = _F.section_r13_r2000(buf, _F.read_r13_r2000(buf)['locators'][0])[0]
        v = decode_header(hv, ver, 0)
        for k in ('DIMASO', 'DIMSHO', 'PLINEGEN', 'ORTHOMODE', 'REGENMODE', 'FILLMODE', 'QTEXTMODE', 'PSLTSCALE', 'LIMCHECK', 'USRTIMER', 'SKPOLY', 'ANGDIR', 'SPLFRAME', 'MIRRTEXT', 'WORLDVIEW', 'TILEMODE', 'PLIMCHECK', 'VISRETAIN', 'DISPSILH', 'PELLIPSE'):
            v.pop(k, None)  # R2000 order of the flag group differs (44 bits, not located bit by bit)
        return v
    if ver not in ('AC1018', 'AC1021', 'AC1024', 'AC1027', 'AC1032'): return {}
    h = dwgload.section(buf, info, 'AcDb:Header')
    start = {'AC1018': 160, 'AC1021': 192, 'AC1024': 224, 'AC1027': 227, 'AC1032': 227}[ver]  # after sentinel, sizes (and a 3-bit field from R2013)
    v = decode_header(h, ver, start)
    if ver != 'AC1018':
        try: v.update(_wide_handles(h, ver))
        except Exception: pass
    return v


_WIDE_HNAMES = ('CLAYER', 'TEXTSTYLE', 'CELTYPE', 'CMATERIAL', 'DIMSTYLE', 'CMLSTYLE', 'PUCSNAME', 'PUCSORTHOREF', 'PUCSBASE', 'UCSNAME', 'UCSORTHOREF',
                'UCSBASE', 'DIMTXSTY', 'DIMLDRBLK', 'DIMBLK', 'DIMBLK1', 'DIMBLK2', 'DIMLTYPE', 'DIMLTEX1', 'DIMLTEX2', 'BLOCK_CONTROL', 'LAYER_CONTROL',
                'STYLE_CONTROL', 'LTYPE_CONTROL', 'VIEW_CONTROL', 'UCS_CONTROL', 'VPORT_CONTROL', 'APPID_CONTROL', 'DIMSTYLE_CONTROL', 'DICT_GROUP',
                'DICT_MLINESTYLE', 'DICT_NAMED_OBJECTS', 'DICT_LAYOUTS', 'DICT_PLOTSETTINGS', 'DICT_PLOTSTYLES', 'DICT_MATERIALS', 'DICT_COLORS',
                'DICT_VISUALSTYLE', 'DICT_UNKNOWN', 'PAPER_SPACE_BLOCK', 'MODEL_SPACE_BLOCK', 'BYLAYER_LTYPE', 'BYBLOCK_LTYPE', 'CONTINUOUS_LTYPE',
                'INTERFEREOBJVS', 'INTERFEREVPVS')


def _wide_handles(h, ver):
    """R2007+ handle stream of the header (starts about 35 bits before 'bit size' after the data start; located by the first six references being
    absolute and non-zero). Returns {name: handle} for the references of _WIDE_HNAMES (validated vs AutoCAD's header handles)."""
    if ver == 'AC1021': base, bs = 192, int.from_bytes(h[20:24], 'little')
    else: base, bs = 224, int.from_bytes(h[24:28], 'little')
    for off in range(-60, 12):
        r = B.Bits(h, base + bs + off)
        try:
            hs = [r.H() for _ in range(len(_WIDE_HNAMES))]
        except IndexError: continue
        if ver in ('AC1021', 'AC1024'): hs = hs[:38] + [(5, 0)] + hs[38:]  # no DICT_UNKNOWN slot before R2013
        if all(c == 5 and 0 < x < 1 << 64 for c, x in hs[:5]) and all(c == 5 for c, x in hs[:6]):
            return {k: x for k, (c, x) in zip(_WIDE_HNAMES, hs) if x}
    return {}


def decode_header(h, ver, start=20 * 8):
    v = {}
    try:
        _decode(h, ver, start, v)
    except IndexError:
        v['_truncated'] = True
    return v


def _decode(h, ver, start, v):
    new = ver != 'AC1015'  # R2004 and later
    wide = ver in ('AC1021', 'AC1024', 'AC1027', 'AC1032')  # R2007+: strings live in a separate stream, no data bits
    tv = (lambda: None) if wide else None
    """Returns a dict with the variables of the first part of the list. h = section data incl. 16-byte sentinel and RL size."""
    r = B.Bits(h, start)
    r.BD(); r.BD(); r.BD(); r.BD()
    if not wide:
        r.TV(); r.TV(); r.TV(); r.TV()
    r.BL(); r.BL()
    for k in ('DIMASO', 'DIMSHO', 'PLINEGEN', 'ORTHOMODE', 'REGENMODE', 'FILLMODE', 'QTEXTMODE', 'PSLTSCALE', 'LIMCHECK'):
        v[k] = r.B()
    if new: r.B()  # undocumented flag, R2004 only
    for k in ('USRTIMER', 'SKPOLY', 'ANGDIR', 'SPLFRAME', 'MIRRTEXT', 'WORLDVIEW', 'TILEMODE', 'PLIMCHECK', 'VISRETAIN', 'DISPSILH', 'PELLIPSE'):
        v[k] = r.B()
    if ver == 'AC1015':
        # R2000 stores 8..24 more bits of flags / small codes here (the amount differs per file): locate the PROXYGRAPHICS / TREEDEPTH pair (TREEDEPTH is 3020 by default)
        base = r.p; r.p = base + 24
        for k in range(0, 49):
            q = B.Bits(h, base + k)
            try:
                if q.BS() in (0, 1) and q.BS() == 3020 and 1 <= q.BS() <= 5: r.p = base + k; break
            except Exception: pass
    for k in ('PROXYGRAPHICS', 'TREEDEPTH', 'LUNITS', 'LUPREC', 'AUNITS', 'AUPREC', 'ATTMODE', 'PDMODE'):
        v[k] = r.BS()
    if new: r.BL(); r.BL(); r.BL()
    for k in ('USERI1', 'USERI2', 'USERI3', 'USERI4', 'USERI5', 'SPLINESEGS', 'SURFU', 'SURFV', 'SURFTYPE', 'SURFTAB', 'SURFX', 'SPLINETYPE', 'SHADEDGE',
              'SHADEDIF', 'UNITMODE', 'MAXACTVP', 'ISOLINES', 'CMLJUST', 'TEXTQLTY'):
        v[k] = r.BS()
    for k in ('LTSCALE', 'TEXTSIZE', 'TRACEWID', 'SKETCHINC', 'FILLETRAD', 'THICKNESS', 'ANGBASE', 'PDSIZE', 'PLINEWID', 'USERR1', 'USERR2', 'USERR3',
              'USERR4', 'USERR5', 'CHAMFERA', 'CHAMFERB', 'CHAMFERC', 'CHAMFERD', 'FACETRES', 'CMLSCALE', 'CELTSCALE'):
        v[k] = r.BD()
    if not wide: r.TV()  # MENUNAME (R2004 and earlier)
    for k in ('TDCREATE', 'TDUPDATE'):
        v[k] = (r.BL(), r.BL())
    if new: r.BL(); r.BL(); r.BL()
    for k in ('TDINDWG', 'TDUSRTIMER'):
        v[k] = (r.BL(), r.BL())
    v['CECOLOR'] = (r.BS(), r.BL(), r.RC()) if new else (r.BS(),)
    v['_handseed_pos'] = r.p
    v['HANDSEED'] = r.H()
    v['_handseed_end'] = r.p
    H = (lambda: None) if wide else r.H  # R2007+: handle references live in a separate handle stream
    for k in ('CLAYER', 'TEXTSTYLE', 'CELTYPE'):
        v[k] = H()
    if wide: v['CMATERIAL'] = H()
    v['DIMSTYLE'] = H(); v['CMLSTYLE'] = H()
    v['PSVPSCALE'] = r.BD()
    v['PINSBASE'] = r.BD3(); v['PEXTMIN'] = r.BD3(); v['PEXTMAX'] = r.BD3(); v['PLIMMIN'] = r.RD2(); v['PLIMMAX'] = r.RD2(); v['PELEVATION'] = r.BD()
    v['PUCSORG'] = r.BD3(); v['PUCSXDIR'] = r.BD3(); v['PUCSYDIR'] = r.BD3()  # origin, X axis, Y axis
    for k in ('PUCSNAME', 'PUCSORTHOREF'): v[k] = H()
    v['PUCSORTHOVIEW'] = r.BS(); v['PUCSBASE'] = H()
    for _ in range(6): r.BD3()  # PUCSORGTOP / BOTTOM / LEFT / RIGHT / FRONT / BACK
    v['INSBASE'] = r.BD3(); v['EXTMIN'] = r.BD3(); v['EXTMAX'] = r.BD3(); v['LIMMIN'] = r.RD2(); v['LIMMAX'] = r.RD2()
    v['ELEVATION'] = r.BD()
    v['UCSORG'] = r.BD3(); v['UCSXDIR'] = r.BD3(); v['UCSYDIR'] = r.BD3()
    v['UCSNAME'] = H()
    v['UCSORTHOREF'] = H(); v['UCSORTHOVIEW'] = r.BS(); v['UCSBASE'] = H()
    for _ in range(6): r.BD3()
    if not wide: r.TV(); r.TV()  # DIMPOST, DIMAPOST
    for k in ('DIMSCALE', 'DIMASZ', 'DIMEXO', 'DIMDLI', 'DIMEXE', 'DIMRND', 'DIMDLE', 'DIMTP', 'DIMTM'):
        v[k] = r.BD()
    if wide: r.BD(); r.BD(); r.BS(); r.BS(); r.BL(); r.RC()  # DIMFXL, DIMJOGANG, DIMTFILL, DIMTFILLCLR (CMC)
    for k in ('DIMTOL', 'DIMLIM', 'DIMTIH', 'DIMTOH', 'DIMSE1', 'DIMSE2'): v[k] = r.B()
    for k in ('DIMTAD', 'DIMZIN', 'DIMAZIN'): v[k] = r.BS()
    if wide: v['DIMARCSYM'] = r.BS()
    for k in ('DIMTXT', 'DIMCEN', 'DIMTSZ', 'DIMALTF', 'DIMLFAC', 'DIMTVP', 'DIMTFAC', 'DIMGAP', 'DIMALTRND'): v[k] = r.BD()
    v['DIMALT'] = r.B(); v['DIMALTD'] = r.BS()
    for k in ('DIMTOFL', 'DIMSAH', 'DIMTIX', 'DIMSOXD'): v[k] = r.B()
    for k in ('DIMCLRD', 'DIMCLRE', 'DIMCLRT'): v[k] = (r.BS(), r.BL(), r.RC()) if new else (r.BS(),)
    for k in ('DIMADEC', 'DIMDEC', 'DIMTDEC', 'DIMALTU', 'DIMALTTD', 'DIMAUNIT', 'DIMFRAC', 'DIMLUNIT', 'DIMDSEP', 'DIMTMOVE', 'DIMJUST'): v[k] = r.BS()
    v['DIMSD1'] = r.B(); v['DIMSD2'] = r.B()
    for k in ('DIMTOLJ', 'DIMTZIN', 'DIMALTZ', 'DIMALTTZ'): v[k] = r.BS()
    v['DIMUPT'] = r.B(); v['DIMATFIT'] = r.BS()
    if wide: r.B()  # DIMFXLON
    for k in ('DIMTXSTY', 'DIMLDRBLK', 'DIMBLK', 'DIMBLK1', 'DIMBLK2'): v[k] = H()
    if wide:
        for _ in range(3): H()  # DIMLTYPE, DIMLTEX1, DIMLTEX2
    if wide:
        # R2007+: handle references and strings live in separate streams, so only the data-stream items follow (order checked against the AutoCAD dump on
        # AC1021/1024/1027/1032: DIMLWD .. DGNFRAME equal to the dump, INSUNITS 4 = millimetres)
        if ver != 'AC1021': r.B(); r.BD(); r.BD()  # DIMTXTDIRECTION, DIMALTMZF, DIMMZF
        v['DIMLWD'] = r.BS(); v['DIMLWE'] = r.BS(); v['TSTACKALIGN'] = r.BS(); v['TSTACKSIZE'] = r.BS()
        v['FLAGS'] = r.BL(); v['INSUNITS'] = r.BS(); v['CEPSNTYPE'] = r.BS()
        for k in ('SORTENTS', 'INDEXCTL', 'HIDETEXT', 'XCLIPFRAME', 'DIMASSOC', 'HALOGAP'): v[k] = r.RC()
        v['OBSCOLOR'] = r.BS(); v['INTERSECTIONCOLOR'] = r.BS(); v['OBSLTYPE'] = r.RC(); v['INTERSECTIONDISPLAY'] = r.RC()
        v['CAMERADISPLAY'] = r.B(); r.BL(); r.BL(); r.BD()
        for k in ('STEPSPERSEC', 'STEPSIZE', '3DDWFPREC', 'LENSLENGTH', 'CAMERAHEIGHT'): v[k] = r.BD()
        v['SOLIDHIST'] = r.RC(); v['SHOWHIST'] = r.RC()
        for k in ('PSOLWIDTH', 'PSOLHEIGHT', 'LOFTANG1', 'LOFTANG2', 'LOFTMAG1', 'LOFTMAG2'): v[k] = r.BD()
        v['LOFTPARAM'] = r.BS(); v['LOFTNORMALS'] = r.RC()
        for k in ('LATITUDE', 'LONGITUDE', 'NORTHDIRECTION'): v[k] = r.BD()
        v['TIMEZONE'] = r.BL(); v['LIGHTGLYPHDISPLAY'] = r.RC(); v['TILEMODELIGHTSYNCH'] = r.RC(); v['DWFFRAME'] = r.RC(); v['DGNFRAME'] = r.RC()
        r.B(); v['INTERFERECOLOR'] = (r.BS(), r.BL(), r.RC()); v['CSHADOW'] = r.RC(); v['SHADOWPLANELOCATION'] = r.BD()
        fl = v['FLAGS']
        if fl is not None: v['LWDISPLAY'] = not (fl & 0x200); v['CELWEIGHT'] = fl & 0x1F
        return
    v['DIMLWD'] = r.BS(); v['DIMLWE'] = r.BS()
    for k in ('BLOCK_CONTROL', 'LAYER_CONTROL', 'STYLE_CONTROL', 'LTYPE_CONTROL', 'VIEW_CONTROL', 'UCS_CONTROL', 'VPORT_CONTROL', 'APPID_CONTROL', 'DIMSTYLE_CONTROL'):
        v[k] = H()
    if ver == 'AC1015': v['VPENT_CONTROL'] = H()
    for k in ('DICT_GROUP', 'DICT_MLINESTYLE', 'DICT_NAMED_OBJECTS'): v[k] = H()
    v['TSTACKALIGN'] = r.BS(); v['TSTACKSIZE'] = r.BS()
    if not wide: v['HYPERLINKBASE'] = r.TV(); v['STYLESHEET'] = r.TV()
    for k in ('DICT_LAYOUTS', 'DICT_PLOTSETTINGS', 'DICT_PLOTSTYLES'): v[k] = H()
    if ver != 'AC1015':
        v['DICT_MATERIALS'] = H(); v['DICT_COLORS'] = H()
    v['FLAGS'] = r.BL()
    v['INSUNITS'] = r.BS()
    v['_p'] = r.p
