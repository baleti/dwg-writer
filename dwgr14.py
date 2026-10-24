"""R13/R14 (AC1012, AC1014) reader, experimental. Own code; layouts found by experiment against AutoCAD dumps of AC1012_46 (see NOTES.md).
Object = [RS size][BS type][H handle][EED: BS size, H app, bytes][39 header bits, not decoded][BS colour][4 bits][entity data][handles][CRC].
Entity data uses plain BD codes (no DD compression, no z-is-zero flags)."""
import struct
import bisect
import collections
import dwgbits as B
import dwgobj

ENTITY_TYPES = {36: 'SPLINE', 44: 'MTEXT', 1: 'TEXT', 2: 'ATTRIB', 3: 'ATTDEF', 4: 'BLOCK', 5: 'ENDBLK', 6: 'SEQEND', 7: 'INSERT', 8: 'MINSERT', 10: 'VERTEX2D', 11: 'VERTEX3D', 12: 'VERTEX_MESH', 13: 'VERTEX_PFACE', 14: 'VERTEX_PFACE_FACE', 15: 'POLYLINE2D', 16: 'POLYLINE3D', 29: 'POLYLINE_PFACE', 30: 'POLYLINE_MESH',
                17: 'ARC', 18: 'CIRCLE', 19: 'LINE', 27: 'POINT', 28: '3DFACE', 31: 'SOLID', 35: 'ELLIPSE', 45: 'LEADER', 40: 'RAY', 41: 'XLINE'}
CLASS_KINDS = {}  # class number -> kind, filled from the class table by Model14
DECODABLE_TYPES = (1, 2, 3, 6, 7, 10, 11, 12, 13, 14, 15, 16, 29, 30, 17, 18, 19, 27, 28, 31, 35, 36, 40, 41, 44, 45) + tuple(range(500, 600))
DECODABLE = ('LINE', 'CIRCLE', 'ARC', 'POINT', 'SOLID', 'TEXT', 'INSERT', 'MTEXT', 'ATTRIB', 'ATTDEF', 'POLYLINE2D', 'VERTEX2D', 'ACAD_PROXY_ENTITY', 'POLYLINE3D', 'VERTEX3D', 'POLYLINE_PFACE', 'POLYLINE_MESH', 'VERTEX_MESH', 'VERTEX_PFACE', 'VERTEX_PFACE_FACE', 'SEQEND', 'LWPOLYLINE', '3DFACE', 'SPLINE', 'HATCH', 'ELLIPSE', 'RAY', 'XLINE', 'LEADER')
TABLE_TYPES = {51: 'LAYER', 49: 'BLOCK_HEADER', 53: 'STYLE', 57: 'LTYPE'}


class Obj14:
    __slots__ = ('handle', 'type', 'raw', 'ver')


def load(buf):
    d = dwgobj.load_r2000(buf)
    objs = {}
    for h, o in d['objects'].items():
        raw = o.raw
        if len(raw) > 4 and raw[1] & 0x80: raw = b'\0\0' + raw[4:]  # modular short size > 32767: four size bytes, the rest of the reader expects two
        x = Obj14(); x.handle = h; x.type = o.type; x.raw = raw; x.ver = 'AC1014'
        objs[h] = x
    return dict(version='AC1014', objects=objs, raw=d)


def _skip_eed(r):
    n = r.BS()
    while n:
        r.H(); r.rcs(n); n = r.BS()


def table_name(o):
    """Name of a LAYER / BLOCK_HEADER / STYLE / LTYPE object (single-byte string, BS length), at 34 bits after the EED."""
    r = B.Bits(o.raw, 16); r.BS(); r.H(); _skip_eed(r); r.p += 34
    n = r.BS()
    return bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')


def block_header(o):
    """BLOCK_HEADER: name, first and last entity handles (the entities of a block are the handles in [first, last]), BLOCK entity handle, ENDBLK handle."""
    r = B.Bits(o.raw, 16); r.BS(); r.H(); _skip_eed(r); r.p += 34
    n = r.BS(); name = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')
    r.p += 16
    hs = []
    total = (len(o.raw) - 2) * 8
    try:
        while r.p < total - 4 and len(hs) < 10: hs.append(r.H())
    except Exception:
        pass
    out = dict(name=name, handles=hs)
    # EXP: [(4 control), (3 xdic), (5), (3 BLOCK), (4 first), (4 last), (3 ENDBLK)] -- nulls give shorter lists
    vals = [v for c, v in hs]
    if len(vals) >= 4:
        out.update(block=vals[-4], first=vals[-3], last=vals[-2], endblk=vals[-1])
        M = (1 << 64) - 1
        if out['first'] > M or out['block'] > M:  # name area misparsed (146 of 453 headers in AC1014_49): the handle list starts early and glues bytes together; the low 64 bits are the real first handle and the BLOCK entity precedes it
            out['first'] &= M; out['block'] = out['first'] - 1
    return out


def _start(o, shift=0):
    """Position after the common entity header. Layout (found by correlating the header bits with the AutoCAD dump, AC1014_06/_48): 32 bits of unknown content (bit 5 = explicit
    colour), graphic-present B, entmode BB, nreactors BL, isbylayerlt B, nolinks B, colour BS, linetype scale BD, invisibility BS. Objects with persistent reactors have a longer
    header (BL carries a count byte), which the former fixed 39+4 bit skip got wrong."""
    r = B.Bits(o.raw, 16); r.BS(); r.H(); _skip_eed(r)
    r.p += 32 + shift
    gr = r.B()
    if gr:  # cached graphics: size follows (RL) -- skip it
        sz = r.RL(); r.p += sz * 8
    r.BB(); r.BL(); r.B(); r.B()
    col = r.BS(); r.BD(); r.BS()
    return r, col


def dim_fields(o):
    """DIMENSION fields (R13/R14): extrusion 3BD, text midpoint 2RD, elevation BD, 8 flag bits, text override (BS length + bytes), text rotation BD, horizontal direction BD,
    insertion scale 3BD, insertion rotation BD, then 12 (2RD) and, for linear/aligned dimensions, 13, 14, 10 (3BD each). Text override 422 of 422 and text midpoint
    equal to AutoCAD's DXF (chk_dimtext_r14.py)."""
    d = dict(user_text='')
    try:
        r, col = _start(o); r.BD3(); mid = (r.RD(), r.RD()); el = r.BD(); r.p += 8
        n = r.BS()
        if 0 < n < 512: d['user_text'] = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')
        elif n != 0: return dict(user_text='')
        d['text_mid'] = (mid[0], mid[1], el)
        d['text_rot'] = r.BD(); r.BD(); r.BD3(); r.BD(); r.RD(); r.RD()
        if o.type in (21, 22): d['pt13'] = r.BD3(); d['pt14'] = r.BD3(); d['pt10'] = r.BD3()
    except Exception:
        pass
    return d


def dim_user_text(o):
    return dim_fields(o)['user_text']


def _handles(r, o):
    hs = []
    total = (len(o.raw) - 2) * 8
    try:
        while r.p < total - 4 and len(hs) < 8: hs.append(r.H())
    except Exception:
        pass
    return hs


def decode_entity(o, shift=0):
    t = o.type
    kind = ENTITY_TYPES.get(t) or (CLASS_KINDS.get(t) if t >= 500 else None)
    if kind not in DECODABLE: return None
    r, col = _start(o, shift)
    e = dict(kind=kind, color=(col, None, None), handle=o.handle)
    if kind == 'LINE':
        e.update(p1=r.BD3(), p2=r.BD3(), thickness=r.BD(), ext=r.BD3())
    elif kind in ('CIRCLE', 'ARC'):
        e.update(center=r.BD3(), radius=r.BD(), thickness=r.BD(), ext=r.BD3())
        if kind == 'ARC': e.update(a0=r.BD(), a1=r.BD())
    elif kind == 'ELLIPSE':
        e.update(center=r.BD3(), major=r.BD3(), ext=r.BD3(), ratio=r.BD(), a0=r.BD(), a1=r.BD())
    elif kind == 'LEADER':
        r.B(); ann = r.BS(); path = r.BS(); n = r.BL()
        if n > 10000: raise ValueError('leader points')
        pts = [r.BD3() for _ in range(n)]
        e.update(annotation=ann, path=path, pts=pts, end_proj=r.BD3(), ext=r.BD3(), xdir=r.BD3(), block_offset=r.BD3())
    elif kind in ('RAY', 'XLINE'):
        e.update(p=r.BD3(), v=r.BD3())
    elif kind == 'POINT':
        e.update(p=r.BD3(), thickness=r.BD(), ext=r.BD3(), angle=r.BD())
    elif kind == 'SOLID':
        th = r.BD(); el = r.BD(); pts = [(r.RD(), r.RD()) for _ in range(4)]
        e.update(thickness=th, elev=el, pts=pts, ext=r.BD3())
    elif kind == 'TEXT':
        elev = r.BD(); ins = (r.RD(), r.RD()); al = (r.RD(), r.RD()); ex = r.BD3(); th = r.BD(); obl = r.BD(); rot = r.BD(); hh = r.BD(); wf = r.BD()
        n = r.BS(); txt = bytes(r.RC() for _ in range(n)).decode('latin1')
        e.update(elev=elev, ins=ins, align=al, ext=ex, thickness=th, oblique=obl, rot=rot, height=hh, widthf=wf, text=txt, gen=r.BS(), halign=r.BS(), valign=r.BS())
    elif kind in ('ATTRIB', 'ATTDEF'):
        elev = r.BD(); ins = (r.RD(), r.RD()); al = (r.RD(), r.RD()); ex = r.BD3(); th = r.BD(); obl = r.BD(); rot = r.BD(); hh = r.BD(); wf = r.BD()
        n = r.BS(); txt = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')
        gen = r.BS(); ha = r.BS(); va = r.BS()
        n = r.BS(); tag = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')
        prompt = ''
        if kind == 'ATTDEF':
            r.p += 10  # EXP: 10 undecoded bits (field length / flags), then the prompt
            n = r.BS(); prompt = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')
        e.update(elev=elev, ins=ins, align=al, ext=ex, thickness=th, oblique=obl, rot=rot, height=hh, widthf=wf, text=txt, gen=gen, halign=ha, valign=va, tag=tag, prompt=prompt)
    elif kind == 'HATCH':
        elev = r.BD(); ext = r.BD3()
        n = r.BS(); pname = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')
        solid = r.B(); assoc = r.B(); npaths = r.BL()
        if npaths > 10000: raise ValueError('hatch paths')
        paths = []
        for _ in range(npaths):
            fl = r.BL(); segs = []
            if fl & 2:
                bulges = r.B(); closed = r.B(); nv = r.BL()
                if nv > 100000: raise ValueError('hatch polyline')
                for _ in range(nv):
                    p = (r.RD(), r.RD()); b = r.BD() if bulges else 0.0
                    segs.append(('P', p, b))
                path = dict(flags=fl, closed=bool(closed), segs=segs)
            else:
                nseg = r.BL()
                if nseg > 100000: raise ValueError('hatch segs')
                for _ in range(nseg):
                    t = r.RC()
                    if t == 1: segs.append(('L', (r.RD(), r.RD()), (r.RD(), r.RD())))
                    elif t == 2: segs.append(('A', (r.RD(), r.RD()), r.BD(), r.BD(), r.BD(), r.B()))
                    elif t == 3: segs.append(('E', (r.RD(), r.RD()), (r.RD(), r.RD()), r.BD(), r.BD(), r.BD(), r.B()))
                    elif t == 4:
                        deg = r.BL(); rat = r.B(); per = r.B(); nk = r.BL(); nc = r.BL()
                        kn = [r.BD() for _ in range(nk)]; cp = []
                        for _ in range(nc):
                            pt = (r.RD(), r.RD()); w = r.BD() if rat else 1.0; cp.append((pt, w))
                        segs.append(('S', deg, rat, per, kn, cp, None))
                    else:
                        raise ValueError('hatch seg type %d' % t)
                path = dict(flags=fl, segs=segs)
            path['nboundary'] = r.BL()
            paths.append(path)
        style = r.BS(); ptype = r.BS()
        pattern = None; angle = scale = 0.0; double = 0
        if not solid:
            angle = r.BD(); scale = r.BD(); double = r.B(); nlines = r.BS(); pattern = []
            for _ in range(nlines):
                a = r.BD(); p0 = (r.BD(), r.BD()); off = (r.BD(), r.BD()); nd = r.BS()
                pattern.append((a, p0, off, [r.BD() for _ in range(nd)]))
        pixel = r.BD() if any(p['flags'] & 4 for p in paths) else None
        nseeds = r.BL()
        if nseeds > 100000: raise ValueError('hatch seeds')
        seeds = [(r.RD(), r.RD()) for _ in range(nseeds)]
        e.update(kind='HATCH', gradient=dict(is_gradient=0), elev=elev, ext=ext, pattern_name=pname, solid=solid, assoc=assoc, paths=paths, style=style, pattern_type=ptype,
                 pattern_angle=angle, pattern_scale=scale, pattern_double=double, pattern_lines=pattern, pixel=pixel, seeds=seeds)
    elif kind == 'SPLINE':
        sc = r.BL(); deg = r.BL(); knots = []; ctrl = []; weights = []; fit = []; rat = cl = per = False
        if sc == 1:
            rat = bool(r.B()); cl = bool(r.B()); per = bool(r.B()); r.BD(); r.BD(); nk = r.BL(); nc = r.BL(); wt = r.B()
            if nk > 100000 or nc > 100000: raise ValueError('spline counts')
            knots = [r.BD() for _ in range(nk)]
            for _ in range(nc):
                ctrl.append(r.BD3())
                if wt: weights.append(r.BD())
        elif sc == 2:
            r.BD(); r.BD3(); r.BD3(); nf = r.BL()
            if nf > 100000: raise ValueError('spline counts')
            fit = [r.BD3() for _ in range(nf)]
        e.update(scenario=sc, degree=deg, rational=rat, closed=cl, periodic=per, knots=knots, ctrl=ctrl, weights=weights, fit=fit, tan0=None, tan1=None)
    elif kind == '3DFACE':
        e.update(pts=[r.BD3() for _ in range(4)], invis=r.BS())
    elif kind == 'LWPOLYLINE':
        fl = r.BS()
        cw = r.BD() if fl & 4 else None; el = r.BD() if fl & 8 else 0.0; th = r.BD() if fl & 2 else 0.0; nm = r.BD3() if fl & 1 else (0.0, 0.0, 1.0)
        n = r.BL(); nb = r.BL() if fl & 16 else 0; nw = r.BL() if fl & 32 else 0
        if n > 100000 or nb > 100000 or nw > 100000: raise ValueError('lwpolyline counts')
        pts = [(r.RD(), r.RD()) for _ in range(n)]
        bul = [r.BD() for _ in range(nb)]
        wid = [(r.BD(), r.BD()) for _ in range(nw)]
        e.update(flags=fl, closed=bool(fl & 512), constwidth=cw, elev=el, thickness=th, ext=nm, pts=pts, bulges=bul, widths=wid)
    elif kind == 'POLYLINE2D':
        fl = r.BS(); curve = r.BS(); sw = r.BD(); ew = r.BD(); th = r.BD(); el = r.BD(); ex = r.BD3()
        e.update(kind='POLYLINE2D', flags=fl, closed=bool(fl & 1), curve=curve, start_width=sw, end_width=ew, thickness=th, elev=el, ext=ex)
    elif kind == 'ACAD_PROXY_ENTITY':
        pass  # no graphics in the samples (GraphicsMetafileType NoMetafile): the entity is only counted, its layer comes from the handle list
    elif kind == 'POLYLINE3D':
        fl1 = r.RC(); fl2 = r.RC()
        e.update(flags=fl2, curve=fl1, closed=bool(fl2 & 1))
    elif kind == 'POLYLINE_PFACE':
        e.update(nverts=r.BS(), nfaces=r.BS())
    elif kind == 'POLYLINE_MESH':
        fl = r.BS(); curve = r.BS(); m_ = r.BS(); n_ = r.BS(); r.BS(); r.BS()
        e.update(flags=fl, curve=curve, m=m_, n=n_, m_closed=bool(fl & 1), n_closed=bool(fl & 32))
    elif kind in ('VERTEX_MESH', 'VERTEX_PFACE'):
        fl = r.RC(); p = r.BD3()
        e.update(flags=fl, p=p)
    elif kind == 'VERTEX_PFACE_FACE':
        e.update(idx=[r.BS() for _ in range(4)])
    elif kind == 'VERTEX3D':
        fl = r.RC(); p = r.BD3()
        e.update(flags=fl, p=p)
    elif kind == 'VERTEX2D':
        fl = r.RC(); p = r.BD3(); sw = r.BD(); ew = r.BD(); bu = r.BD(); tg = r.BD()
        e.update(flags=fl, p=p, start_width=abs(sw), end_width=ew, bulge=bu, tangent=tg)
    elif kind == 'MTEXT':
        ins = r.BD3(); ex = r.BD3(); xd = r.BD3(); w = r.BD(); th = r.BD(); att = r.BS(); dr = r.BS(); eh = r.BD(); ew = r.BD()
        n = r.BS(); txt = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')
        e.update(ins=ins, ext=ex, xdir=xd, width=w, text_height=th, attachment=att, text=txt)
    elif kind == 'INSERT':
        ins = r.BD3(); sc = (r.BD(), r.BD(), r.BD()); rot = r.BD(); ex = r.BD3(); ha = r.B()
        e.update(ins=ins, scale=sc, rot=rot, ext=ex, hasattribs=ha)
    hs = _handles(r, o)
    e['handles'] = hs
    e['layer_handle'] = next((v for c, v in hs if c == 5), None)
    return e


def ltype_info(o):
    """LTYPE (57): name, description, pattern length, dashes (length, shape code, shape flags); equal to the AutoCAD dump on AC1014_18."""
    r = B.Bits(o.raw, 16); r.BS(); r.H(); _skip_eed(r); r.p += 34
    n = r.BS(); name = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\0')
    r.B(); r.BS(); r.B()
    n = r.BS(); desc = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\0')
    pl = r.BD(); r.RC(); nd = r.RC()
    dashes = []
    for _ in range(min(nd, 64)):
        ln = r.BD(); cs = r.BS(); xo = r.RD(); yo = r.RD(); sc = r.BD(); ro = r.BD(); sf = r.BS()
        dashes.append(dict(length=ln, shape=cs, flags=sf, offset=(xo, yo), scale=sc, rotation=ro))
    return dict(name=name, description=desc, pattern_length=pl, dashes=dashes)


def style_info(o):
    """STYLE (53): name, fixed height, width factor, oblique, generation, font file, big font (equal to the AutoCAD dump on AC1014_18)."""
    r = B.Bits(o.raw, 16); r.BS(); r.H(); _skip_eed(r); r.p += 34
    n = r.BS(); name = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\0')
    r.B(); r.BS(); r.B()
    shape = r.B(); vert = r.B(); h = r.BD(); wf = r.BD(); ob = r.BD(); gen = r.RC(); lh = r.BD()
    n = r.BS(); font = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\0')
    n = r.BS(); big = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\0')
    return dict(name=name, shape=bool(shape), vertical=bool(vert), height=h, width=wf, oblique=ob, gen=gen, last_height=lh, font=font, bigfont=big)


def layer_info(o):
    """LAYER: name, frozen/off/locked flags (bits 4, 5, 7 of the byte before the colour) and ACI colour (BS at +8 bits after the name)."""
    r = B.Bits(o.raw, 16); r.BS(); r.H(); _skip_eed(r); r.p += 34
    n = r.BS(); name = bytes(r.RC() for _ in range(n)).decode('latin1').rstrip('\x00')
    fl = r.bits(8); col = r.BS()
    return dict(name=name, frozen=bool(fl & 8), off=bool(fl & 4), locked=bool(fl & 1), color=abs(col) if col not in (None, 256) else 7)


class Model14:
    """Model facade for AC1012/AC1014 files with the parts of dwgmodel.Model that dwg2text and dwgscene use."""
    version = 'AC1014'

    def __init__(self, buf):
        import dwgmodel
        self._dec = dwgmodel.decode_tv
        d = load(buf)
        try:
            for c in dwgobj.parse_classes_r2000(d['raw']['classes']) or []:
                if c['dxf'] in ('LWPOLYLINE', 'HATCH', 'ACAD_PROXY_ENTITY'): CLASS_KINDS[c['num']] = c['dxf']
                elif c.get('item') == 498 and c['dxf'] not in ('MLINE', 'WIPEOUT', 'IMAGE', 'OLE2FRAME', 'MTEXT', 'LEADER'): CLASS_KINDS[c['num']] = 'ACAD_PROXY_ENTITY'  # third-party entity classes (Tangent TCH_*): AutoCAD lists them as proxy entities
        except Exception:
            pass
        self._buf = buf
        self._raw = d['raw']
        self.objs = d['objects']
        self.codepage = struct.unpack_from('<H', buf, 0x13)[0]
        self.tables = {'LAYER': {}, 'BLOCK_HEADER': {}, 'STYLE': {}, 'LTYPE': {}}
        self._layers = {}
        self._bh = {}
        for h, o in self.objs.items():
            try:
                if o.type == 51:
                    li = layer_info(o); li['name'] = self._dec(li['name'], self.codepage)
                    if li['name'].upper() == 'DEFPOINTS': li['name'] = 'Defpoints'  # R13/R14 store the name in capitals, AutoCAD shows the canonical spelling
                    self.tables['LAYER'][h] = li['name']; self._layers[li['name']] = li
                elif o.type == 49:
                    bi = block_header(o); bi['name'] = self._dec(bi['name'], self.codepage); self._bh[h] = bi; self.tables['BLOCK_HEADER'][h] = bi['name']
                elif o.type in (53, 57):
                    self.tables[TABLE_TYPES[o.type]][h] = self._dec(table_name(o), self.codepage)
            except Exception:
                continue
        self.layers = self.tables['LAYER']
        self._fix_block_headers()
        self._layer_ltypes()
        # anonymous blocks are stored without a number: make them unique like the other versions
        self.blocks = {}
        for h, n in self.tables['BLOCK_HEADER'].items():
            self.blocks[h] = n + '~%x' % h if n.startswith('*') and n[1:2] in 'UXDE' and len(n) <= 2 else n
        self.ranges = sorted((bi['first'], bi['last'], h) for h, bi in self._bh.items() if bi.get('first') and bi.get('last') and not bi['name'].upper().startswith('*MODEL'))
        self.model = next((h for h, n in self.blocks.items() if n.upper() == '*MODEL_SPACE'), None)

    def _layer_ltypes(self):
        """Layer linetype: the (5, handle) of the layer's handle list that names an LTYPE object; the list is found by scanning the end of the object for a parse that holds one."""
        ltobj = {h for h, o in self.objs.items() if o.type == 57}
        self.ltypes()
        for h, o in self.objs.items():
            if o.type != 51: continue
            li = self._layers.get(self.tables['LAYER'].get(h))
            if li is None: continue
            total = (len(o.raw) - 2) * 8
            for s0 in range(total - 12, max(total - 400, 0), -1):
                r = B.Bits(o.raw, s0); hs = []
                try:
                    while r.p < total - 4 and len(hs) < 8: hs.append(r.H())
                except Exception:
                    continue
                lt = next((v for c, v in hs if c == 5 and v in ltobj), None)
                if lt is not None and len(hs) >= 3:
                    li['ltype'] = self._lt_by_handle.get(lt); break

    def _fix_block_headers(self):
        """Block headers whose handle list is misaligned (long names): the last four handles must be [BLOCK (type 4), first, last, ENDBLK (type 5)] of existing objects; search the handle stream backwards for a start position that parses to such a tail."""
        for h, bi in self._bh.items():
            b_, e_ = bi.get('block'), bi.get('endblk')
            if b_ in self.objs and self.objs[b_].type == 4 and e_ in self.objs and self.objs[e_].type == 5: continue
            o = self.objs[h]; total = (len(o.raw) - 2) * 8
            for s0 in range(total - 12, max(total - 700, 0), -1):
                r = B.Bits(o.raw, s0); hs = []
                try:
                    while r.p < total - 4 and len(hs) < 8: hs.append(r.H())
                except Exception:
                    continue
                if len(hs) < 4: continue
                v = [x for c, x in hs[-4:]]; c4 = [c for c, x in hs[-4:]]
                if c4 == [3, 4, 4, 3] and v[0] in self.objs and self.objs[v[0]].type == 4 and v[3] in self.objs and self.objs[v[3]].type == 5 and self.objs[v[3]].handle == v[3]:
                    bi.update(block=v[0], first=v[1], last=v[2], endblk=v[3]); break

    def layer_table(self):
        if getattr(self, '_lt', None) is None:
            self._lt = self._layer_table()
        return self._lt

    def _layer_table(self):
        return {n: dict(color=li['color'], off=li['off'], frozen=li['frozen'], ltype=li.get('ltype'), lineweight_mm=None, true_color=None) for n, li in self._layers.items()}

    def effective(self, e):
        lt = self.layer_table().get(e.get('layer'), {})
        col = e['color'][0]
        if col == 256: col = lt.get('color', 7)
        self.ltypes()
        lth = e.get('ltype_handle')
        ltn = self._lt_by_handle.get(lth) if lth else lt.get('ltype')
        if ltn and ltn.upper() in ('CONTINUOUS', 'BYLAYER', 'BYBLOCK'): ltn = None
        return dict(color=abs(col) if col else col, rgb=None, lineweight_mm=None, ltype=ltn, off=lt.get('off', False), frozen=lt.get('frozen', False))

    def _tail(self, o):
        """Handle list at the end of any entity object, found by scanning for a parse that ends at the object end and holds (5, layer) as first or second handle."""
        total = (len(o.raw) - 2) * 8
        best = None
        lay = self.layers
        if 20 <= o.type <= 26:  # dimensions: layer, entity links, dimstyle, *D block; the list may run a few bits past the nominal end, so parse it tolerantly from the layer handle
            for s in range(total - 8, max(60, total - 420), -1):
                r = B.Bits(o.raw, s)
                try: h = r.H()
                except Exception: continue
                if h[0] != 5 or h[1] not in lay: continue
                hs = [h]
                try:
                    while len(hs) < 12 and r.p < total - 3: hs.append(r.H())
                except Exception:
                    pass
                while hs and not (hs[-1][0] == 5 and hs[-1][1] in self.objs and self.objs[hs[-1][1]].type == 49): hs.pop()  # padding bits read as junk handles after the *D block handle
                if len(hs) >= 3: best = hs
            return best
        for s in range(total - 8, max(60, total - 440), -1):
            r = B.Bits(o.raw, s); hs = []
            try:
                while r.p < total - 3 and len(hs) < 8: hs.append(r.H())
            except Exception:
                continue
            if r.p > total or total - r.p > 7 or not hs: continue
            idx = [i for i, (c, v) in enumerate(hs) if c == 5 and v in lay]
            if not idx: continue
            if idx[0] == 0 or (idx[0] == 1 and hs[0][0] in (3, 4) and hs[0][1] < (1 << 20)): best = hs
        return best

    def _next(self, h):
        o = self.objs.get(h)
        if o is None: return None
        hs = None
        if o.type in DECODABLE_TYPES:
            try:
                hs = decode_entity(o)['handles']
            except Exception:
                hs = None
        if hs is None: hs = self._tail(o)
        if hs is None: return h + 1
        i = next((k for k, (c, v) in enumerate(hs) if c == 5 and v in self.layers), None)
        if i is None: return h + 1
        rest = hs[i + 1:]
        while rest and rest[0][0] == 5: rest = rest[1:]  # linetype handle
        LINK = (2, 4, 6, 8, 10, 12)
        if len(rest) < 2 or rest[0][0] not in LINK or rest[1][0] not in LINK: return h + 1
        c, v = rest[1]
        if c == 6: return h + 1
        if c == 8: return h - 1
        if c == 10: return h + v
        if c == 12: return h - v
        return v or h + 1

    def _links(self, h):
        """(prev, next) entity handles from the link handles after the layer / linetype handles, or None."""
        o = self.objs.get(h)
        if o is None: return None
        hs = None
        if o.type in DECODABLE_TYPES:
            try: hs = decode_entity(o)['handles']
            except Exception: hs = None
        if hs is None: hs = self._tail(o)
        if hs is None: return None
        i = next((k for k, (c, v) in enumerate(hs) if c == 5 and v in self.layers), None)
        if i is None: return None
        rest = hs[i + 1:]
        while rest and rest[0][0] == 5: rest = rest[1:]
        LINK = (2, 4, 6, 8, 10, 12)
        if len(rest) < 2 or rest[0][0] not in LINK or rest[1][0] not in LINK: return None
        def rel(c, v):
            return {6: h + 1, 8: h - 1, 10: h + v, 12: h - v}.get(c, v or None)
        return rel(*rest[0]), rel(*rest[1])

    def _sorted_handles(self):
        if getattr(self, '_sh', None) is None: self._sh = sorted(self.objs)
        return self._sh

    def _build_owners(self):
        """Entities with a leading owner handle belong to that block header; the others (entmode 2/1) are walked from the first/last handles of model and paper space."""
        if hasattr(self, '_own'): return
        own = {}
        for bh, bi in self._bh.items():
            if not bi['name'].upper().startswith(('*MODEL', '*PAPER')): continue
            first, last = bi.get('first'), bi.get('last')
            if not first or not last: continue
            cur = first; n = 0; seen = set()
            while cur and n < 300000 and cur not in seen:  # the chain may jump backwards (AEC files); only a cycle ends it
                seen.add(cur); own.setdefault(cur, bh); n += 1
                if cur == last: break
                nxt = self._next(cur)
                if nxt is None or nxt == cur: break
                if nxt not in self.objs:  # a misaligned header gave no usable link: continue with the next stored handle
                    i = bisect.bisect_right(self._sorted_handles(), cur)
                    if i >= len(self._sh): break
                    nxt = self._sh[i]
                cur = nxt
        self._own = own

    def _entmode(self, o):
        """Entity mode from the common header [B graphic flag][graphic RL size + bytes][RL bit size][BB entmode]: 2 model space, 1 paper space, 0 owner handle
        (equal to AutoCAD on all LINEs of 6 R13/R14 files, about 190,000 entities); None when the header does not parse."""
        try:
            r = B.Bits(o.raw, 16); r.BS(); r.H(); _skip_eed(r)
            if r.B():
                n = r.RL()
                if n > len(o.raw): return None
                r.p += 8 * n
            r.RL()
            return r.BB()
        except Exception:
            return None

    def owner_block(self, h, hs=None):
        self._build_owners()
        o_ = self.objs.get(h)
        em = self._entmode(o_) if o_ is not None and o_.type not in (49, 51, 53, 57) and not (20 <= o_.type <= 26 and False) else None
        if em == 2: return self.model
        if em == 0 and o_ is not None:
            if getattr(self, '_blk', None) is None:  # BLOCK .. ENDBLK brackets in handle order: the header whose BLOCK entity precedes the entity (the stored owner offsets are not reliable in AEC files)
                self._blk = sorted((bi['block'], bi.get('endblk') or 0, bh) for bh, bi in self._bh.items() if bi.get('block') and not bi['name'].upper().startswith(('*MODEL', '*PAPER')))
                self._blk_first = [x[0] for x in self._blk]
            i = bisect.bisect_right(self._blk_first, h) - 1
            if i >= 0 and self._blk[i][0] < h and (not self._blk[i][1] or h < self._blk[i][1]): return self._blk[i][2]
            if getattr(self, '_b45', None) is None:  # BLOCK (4) / ENDBLK (5) objects in handle order; a bracket whose BLOCK belongs to no block header is a dead copy that AutoCAD does not load
                self._b45 = sorted((x, self.objs[x].type) for x in self.objs if self.objs[x].type in (4, 5)); self._b45h = [x[0] for x in self._b45]
                self._known_blocks = {bi['block'] for bi in self._bh.values() if bi.get('block')}
            k = bisect.bisect_right(self._b45h, h) - 1
            if k >= 0 and self._b45[k][1] == 4 and self._b45[k][0] not in self._known_blocks: return -1
            if getattr(self, '_rng', None) is None:
                self._rng = sorted((bi['first'], bi['last'], bh) for bh, bi in self._bh.items() if bi.get('first') and bi.get('last') and bi['first'] <= bi['last'] and not bi['name'].upper().startswith(('*MODEL', '*PAPER')))
                self._rng_first = [x[0] for x in self._rng]
            i = bisect.bisect_right(self._rng_first, h) - 1
            if i >= 0 and self._rng[i][0] <= h <= self._rng[i][1]: return self._rng[i][2]
        if em == 1:
            if getattr(self, '_paper', None) is None:
                self._paper = next((bh for bh, bi in self._bh.items() if bi['name'].upper().startswith('*PAPER')), self.model)
            return self._paper
        if hs:
            c, v = hs[0]
            if c != 3:
                tgt = {12: h - v, 10: h + v, 8: h - 1, 6: h + 1}.get(c, v)
                if tgt in self._bh: return tgt
                if tgt not in self.objs: return -1  # an owner handle that is not a block header: orphan / erased entity, AutoCAD does not load it
        if h not in self._own:  # not reached by the first..last walks (chain break): follow the previous-entity links back to an entity with a known block
            cur = h; seen = set()
            for _ in range(200000):
                if cur in seen or cur not in self.objs: break
                seen.add(cur)
                lk = self._links(cur)
                if not lk or not lk[0] or lk[0] == cur: break
                cur = lk[0]
                if cur in self._own:
                    self._own[h] = self._own[cur]; break
        return self._own.get(h, self.model)

    def owner_block_range(self, h):
        """Handle ranges of the block headers: innermost block whose [first, last] contains the entity, else model space."""
        best = None
        for a, b, bh in self.ranges:
            if a <= h <= b and (best is None or (b - a) < (best[1] - best[0])): best = (a, b, bh)
        return best[2] if best else self.model

    def _dim_blocks(self):
        used = set()
        for h, o in self.objs.items():
            if 20 <= o.type <= 26:
                hs = self._tail(o)
                for c, v in hs or []:
                    if v in self.blocks and self.tables['BLOCK_HEADER'].get(v, '').upper().startswith('*D'): used.add(v)
        return used

    def _vertex3d(self, h):
        o = self.objs.get(h)
        if o is None or o.type not in (11, 12, 13, 14): return None
        try:
            return decode_entity(o)
        except Exception:
            return None

    def entities(self, only_types=None):
        self._att_owner = {}
        if getattr(self, '_dimused', None) is None: self._dimused = self._dim_blocks()  # AutoCAD drops *D picture blocks that no DIMENSION points at
        for h in sorted(self.objs):
            o = self.objs[h]
            if 20 <= o.type <= 26:  # DIMENSION: only the picture block (*D) is read
                hs = self._tail(o)
                if not hs: continue
                bh = next((v for c, v in hs if v in self.blocks and self.tables['BLOCK_HEADER'].get(v, '').upper().startswith('*D')), None)
                lh = next((v for c, v in hs if c == 5 and v in self.layers), None)
                owner = self.owner_block(h, hs)
                yield self.blocks.get(owner), dict(kind='DIM_' + {20: 'ORDINATE', 21: 'LINEAR', 22: 'ALIGNED', 23: 'ANG3PT', 24: 'ANG2LN', 25: 'RADIUS', 26: 'DIAMETER'}[o.type],
                                                  handle=h, color=(256, None, None), layer=self.layers.get(lh), owner=owner, entmode=2, block_handle=bh, block_ref=self.blocks.get(bh), **dim_fields(o))
                continue
            if o.type not in DECODABLE_TYPES or (o.type >= 500 and o.type not in CLASS_KINDS): continue
            try:
                e = decode_entity(o)
            except Exception:
                continue
            if e is None: continue
            lh = e.get('layer_handle')
            def _bad(x):
                return any(k_ in x and (x[k_] is None or (isinstance(x[k_], tuple) and None in (x[k_] if k_ in ('major', 'ext', 'v', 'xdir', 'end_proj') else x[k_][:2]))) for k_ in ('p1', 'p2', 'center', 'radius', 'p', 'ins', 'ratio', 'a0', 'a1', 'major', 'ext', 'v', 'xdir', 'end_proj'))
            if (lh not in self.layers or _bad(e)) and e['kind'] in ('LINE', 'ARC', 'CIRCLE', 'POINT', 'TEXT', 'INSERT', 'SOLID', 'ELLIPSE'):
                for sh in (-24, -23, -18, -8, 8, 16, 24, -16):  # header 8-24 bits shorter or longer in some entities (EXP: -8/+8 fix most junk-looking arcs)
                    try:
                        e2 = decode_entity(o, sh)
                    except Exception:
                        continue
                    if e2 and e2.get('layer_handle') in self.layers and not _bad(e2):
                        e = e2; lh = e2['layer_handle']; break
            if lh not in self.layers:  # decoder did not reach the handle area exactly (ATTDEF/ATTRIB have more fields): locate it by scanning
                hs2 = self._tail(o)
                if hs2:
                    e['handles'] = hs2; lh = next((v for c, v in hs2 if c == 5 and v in self.layers), lh)
            if _bad(e): continue  # undecodable BD code (junk object)
            e['layer'] = self.layers.get(lh)
            e['ltype_handle'] = next((v for c, v in e['handles'] if c == 5 and v in self.objs and self.objs[v].type == 57), None)
            owner = self.owner_block(h, e['handles'])
            if owner == -1: continue  # orphan / erased entity: its owner handle does not exist
            if owner in self.blocks and self.tables['BLOCK_HEADER'].get(owner, '').upper().startswith('*D') and owner not in self._dimused: continue
            if e['kind'] in ('VERTEX3D', 'VERTEX_MESH', 'VERTEX_PFACE', 'VERTEX_PFACE_FACE'): continue  # attached to its polyline through the first/last vertex handles
            if e['kind'] in ('POLYLINE3D', 'POLYLINE_PFACE', 'POLYLINE_MESH'):
                v4 = [v for c, v in e['handles'] if c == 4 and v]
                if len(v4) >= 2:
                    vs_ = [vd for vd in (self._vertex3d(x) for x in range(v4[-2], v4[-1] + 1)) if vd]
                    e['verts_pre'] = [v for v in vs_ if v['kind'] != 'VERTEX_PFACE_FACE']; e['faces_pre'] = [v for v in vs_ if v['kind'] == 'VERTEX_PFACE_FACE']
            if e['kind'] in ('POLYLINE2D', 'POLYLINE3D', 'POLYLINE_PFACE', 'POLYLINE_MESH'): self._poly_owner = owner
            elif e['kind'] in ('VERTEX2D', 'VERTEX3D', 'SEQEND') and getattr(self, '_poly_owner', None) is not None: owner = self._poly_owner
            e['owner'] = owner
            if e['kind'] == 'INSERT' and e.get('hasattribs'):
                v4 = [v for c, v in e['handles'] if c == 4]
                if len(v4) >= 2 and v4[-1] >= v4[-2] > 0:
                    for ah in range(v4[-2], v4[-1] + 1): self._att_owner[ah] = h
            if e['kind'] == 'ATTRIB' and h in self._att_owner: e['owner'] = self._att_owner[h]
            e.setdefault('entmode', 2)
            if e['kind'] == 'INSERT':
                hs_ = e['handles']
                if hs_ and hs_[0][0] != 3 and self.owner_block(h, hs_) in self._bh and self.owner_block(h, hs_) != self.model: hs_ = hs_[1:]  # leading owner handle is the containing block, not the inserted one
                bh = next((v for c, v in hs_ if c == 5 and v in self.blocks), None)
                e['block_handle'] = bh; e['block_ref'] = self.blocks.get(bh)
            if e['kind'] in ('TEXT', 'MTEXT', 'ATTRIB', 'ATTDEF'):
                self.styles(); e['style_handle'] = next((v for c, v in e['handles'] if c == 5 and v in self._st_by_handle), None); e['style'] = self._st_by_handle.get(e['style_handle']); e['text'] = self._dec(e['text'].rstrip('\x00'), self.codepage)
                if e.get('tag'): e['tag'] = self._dec(e['tag'], self.codepage)
            yield self.blocks.get(owner), e

    def decode_viewport(self, o):
        """R13/R14 VIEWPORT: centre, width, height in the data; view target/direction, twist, view height, view centre, lens and the frozen layer handles are in the MVIEW extended data (EXP, equal to the dump on AC1012_50)."""
        r, col = _start(o)
        c = r.BD3(); w = r.BD(); h = r.BD()
        r2 = B.Bits(o.raw, 16); r2.BS(); r2.H(); n = r2.BS(); mv = None
        while n:
            r2.H(); data = r2.rcs(n)
            if data[:8].startswith(b'\x00\x05MVIEW') or b'MVIEW' in data[:12]: mv = data
            n = r2.BS()
        v = dict(center=c, width=w, height=h, view_target=(0.0, 0.0, 0.0), view_dir=(0.0, 0.0, 1.0), twist=0.0, view_height=h, view_center=(c[0], c[1]), lens=50.0, frozen_handles=[], nfrozen=0)
        if mv:
            i = 0; out = []
            while i < len(mv):
                code = mv[i]; i += 1
                if code == 0:
                    ln = mv[i]; i += 1 + 2 + ln
                elif code == 2: i += 1
                elif code in (40, 41, 42): out.append((code, struct.unpack_from('<d', mv, i)[0])); i += 8
                elif code in (10, 11, 12, 13): out.append((code, struct.unpack_from('<3d', mv, i))); i += 24
                elif code == 70: out.append((70, struct.unpack_from('<h', mv, i)[0])); i += 2
                elif code == 71: out.append((71, struct.unpack_from('<i', mv, i)[0])); i += 4
                elif code == 3:
                    out.append((3, int.from_bytes(mv[i:i + 8], 'big'))); i += 8
                else: break
            pts = [x for k, x in out if k == 10]; reals = [x for k, x in out if k == 40]
            if len(pts) >= 2 and len(reals) >= 5:
                v.update(view_target=pts[0], view_dir=pts[1], twist=reals[0], view_height=reals[1], view_center=(reals[2], reals[3]), lens=reals[4])
            v['frozen_handles'] = [x for k, x in out if k == 3]
            v['nfrozen'] = len(v['frozen_handles'])
        return v

    def viewport_frozen(self, o):
        v = self.decode_viewport(o)
        return {self.layers.get(h) for h in v['frozen_handles']} - {None}

    def draw_order(self): return {}
    def object_strings(self, *a, **k): return []
    def dimstyles(self): return {}
    def ltypes(self):
        if getattr(self, '_lts', None) is None:
            self._lts = {}; self._lt_by_handle = {}
            for h, o in self.objs.items():
                if o.type == 57:
                    try:
                        d = ltype_info(o); d['name'] = self._dec(d['name'], self.codepage); d['handle'] = h
                        self._lts[d['name']] = d; self._lt_by_handle[h] = d['name']
                    except Exception:
                        continue
        return self._lts
    def styles(self):
        if getattr(self, '_sts', None) is None:
            self._sts = {}; self._st_by_handle = {}
            for h, o in self.objs.items():
                if o.type == 53:
                    try:
                        d = style_info(o); d['name'] = self._dec(d['name'], self.codepage); d['handle'] = h
                        self._sts[d['name']] = d; self._st_by_handle[h] = d['name']
                    except Exception:
                        continue
        return self._sts
    def classes(self): return []
    def proxy_texts(self): return []
    @staticmethod
    def _hdr_tail(hv, p):
        """Variables after LTSCALE (found by walking the documented order and comparing with AutoCAD's DXF HEADER): the 21 BD of LTSCALE..CELTSCALE, MENUNAME, 4 date pairs,
        CECOLOR, HANDSEED and 5 table handles, paper-space values, then INSBASE, EXTMIN, EXTMAX, LIMMIN, LIMMAX."""
        q = B.Bits(hv, p); v = {}
        for k in ('LTSCALE', 'TEXTSIZE', 'TRACEWID', 'SKETCHINC', 'FILLETRAD', 'THICKNESS', 'ANGBASE', 'PDSIZE', 'PLINEWID', 'USERR1', 'USERR2', 'USERR3', 'USERR4', 'USERR5',
                  'CHAMFERA', 'CHAMFERB', 'CHAMFERC', 'CHAMFERD', 'FACETRES', 'CMLSCALE', 'CELTSCALE'): v[k] = q.BD()
        n = q.BS(); [q.RC() for _ in range(n)]
        for k in ('TDCREATE', 'TDUPDATE', 'TDINDWG', 'TDUSRTIMER'): v[k] = (q.BL(), q.BL())
        v['CECOLOR'] = q.BS(); q.H()
        for _ in range(5): q.H()
        q.BD3(); q.BD3(); q.BD3(); q.RD(); q.RD(); q.RD(); q.RD()  # PINSBASE, PEXTMIN, PEXTMAX, PLIMMIN, PLIMMAX
        q.BD(); q.BD3(); q.BD3(); q.BD3(); q.H()  # PELEVATION, PUCSORG / X / Y axis, PUCSNAME
        v['INSBASE'] = q.BD3(); v['EXTMIN'] = q.BD3(); v['EXTMAX'] = q.BD3(); v['LIMMIN'] = (q.RD(), q.RD()); v['LIMMAX'] = (q.RD(), q.RD())
        return v

    def header(self):
        """LTSCALE and TEXTSIZE of the bit-coded header section: the first pair of consecutive full-precision doubles in a plausible range after the fixed prefix (4 BD, 4 TV, 2 BL). The variable order of the section is not decoded; this scan equals AutoCAD's DXF HEADER on 9 of 9 R13/R14 files."""
        if getattr(self, '_hdr', None) is None:
            self._hdr = {}
            try:
                import math
                hv = self._raw['hdrvars']
                r = B.Bits(hv, 0)
                for _ in range(4): r.BD()
                for _ in range(4):
                    n = r.BS(); [r.RC() for _ in range(n)]
                r.BL(); r.BL(); p0 = r.p
                for p in range(p0, min(len(hv) * 8 - 300, p0 + 500)):
                    try:
                        if B.Bits(hv, p).bits(2) != 0 or B.Bits(hv, p + 66).bits(2) != 0: continue
                        a = B.Bits(hv, p + 2).RD(); b = B.Bits(hv, p + 68).RD()
                    except Exception:
                        continue
                    if math.isfinite(a) and math.isfinite(b) and 1e-3 <= a <= 1e6 and 1e-3 <= b <= 1e6:
                        self._hdr = dict(LTSCALE=a, TEXTSIZE=b)
                        try:
                            self._hdr.update(self._hdr_tail(hv, p))
                        except Exception:
                            pass
                        break
            except Exception:
                pass
        return self._hdr
    def layouts(self):
        out = [dict(name='Model', block=None, block_name=self.blocks.get(self.model, '*MODEL_SPACE'), paper=(0.0, 0.0), paper_size='', viewports=[])]
        vps = collections.defaultdict(list)
        for h in sorted(self.objs):
            o = self.objs[h]
            if o.type == 34:
                try:
                    hs = self._tail(o) or []
                except Exception:
                    hs = []
                vps[self.owner_block(h, hs)].append(h)
        k = 0
        for bh, bi in self._bh.items():
            if not bi['name'].upper().startswith('*PAPER'): continue
            k += 1
            vh = vps.get(bh, [])
            paper = (0.0, 0.0); origin = (0.0, 0.0)
            if vh:
                v = self.decode_viewport(self.objs[vh[0]]); origin = (v['center'][0] - v['width'] / 2, v['center'][1] - v['height'] / 2); paper = (v['width'], v['height'])  # the overall viewport covers the paper
            out.append(dict(name='Layout%d' % k, block=bh, block_name=self.blocks[bh], paper=paper, origin=origin, paper_size='', viewports=vh))
        return out


def _empty_table_api(cls):
    """R12-R14 files carry none of the newer table objects: the accessors exist and return empty results so consumers need no version checks."""
    for n in ('mlstyles', 'mleaderstyles', 'scales', 'dictvars', 'layer_overrides', 'layer_states', 'dictionaries'):
        setattr(cls, n, lambda self: {})
    for n in ('named_views', 'ucs_list', 'vports'):
        setattr(cls, n, lambda self: [])
_empty_table_api(Model14)
