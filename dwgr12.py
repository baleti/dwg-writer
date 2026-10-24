"""R12 (AC1009) reader, experimental: entity stream records, layer table, simple entities. Layout in NOTES.md ("R12 entity record layout").
Own code, checked against AutoCAD dumps of AC1009_51 and _54 (chk_r12.py)."""
import struct

TYPES = {24: 'VIEWPORT', 15: 'ATTDEF', 1: 'LINE', 2: 'POINT', 3: 'CIRCLE', 7: 'TEXT', 8: 'ARC', 11: 'SOLID', 12: 'BLOCK', 13: 'ENDBLK', 14: 'INSERT', 16: 'ATTRIB', 17: 'SEQEND', 19: 'POLYLINE', 20: 'VERTEX', 23: 'DIMENSION'}


def records(b, start, end):
    p = start
    while p + 4 <= end:
        size = struct.unpack_from('<H', b, p + 2)[0]
        if size < 6 or p + size > len(b): break
        yield b[p:p + size]
        p += size


def layers(b):
    sz, cnt, _, addr = struct.unpack_from('<HHHI', b, 0x2C + 10)
    out = []
    for i in range(cnt):
        e = b[addr + sz * i:addr + sz * (i + 1)]
        name = e[1:33].split(b'\0')[0].decode('latin1')
        col, lt = struct.unpack_from('<hH', e, 35)
        out.append(dict(name=name, flags=e[0], color=abs(col), off=col < 0, ltype=lt))
    return out


def _xdata_end(r, p):
    return p + 2 + struct.unpack_from('<H', r, p)[0]


def _text_tail(mask):
    return (8 if mask & 1 else 0) + (8 if mask & 2 else 0) + (8 if mask & 4 else 0) + (1 if mask & 8 else 0) + (1 if mask & 0x10 else 0) + (1 if mask & 0x20 else 0) + (16 if mask & 0x40 else 0) + (1 if mask & 0x100 else 0)


def _text_end(r, p, kind, mask, end):
    """End position of a TEXT / ATTRIB / ATTDEF data block starting at p (None when the strings do not fit)."""
    try:
        p += 24
        for _ in range(1 if kind == 'TEXT' else 2 if kind == 'ATTRIB' else 3):
            p += 2 + struct.unpack_from('<H', r, p)[0]
        if kind != 'TEXT': p += 1
        p += _text_tail(mask if kind == 'TEXT' else mask >> 1)
        return p
    except struct.error:
        return None


def xdata_items(x):
    """Decode R12 extended data: [tag = group code - 1000][value]; 0 and 3 strings (u8 length), 1 appid (u16), 2 brace, 4 binary (u8 length), 5 handle (8 bytes),
    10-13 points (3 doubles), 40-42 doubles, 70 i16, 71 i32."""
    out = []; i = 0
    try:
        while i < len(x):
            t = x[i]; i += 1
            if t in (0, 3): n = x[i]; out.append((1000 + t, x[i + 1:i + 1 + n].decode('latin1'))); i += 1 + n
            elif t == 4: n = x[i]; out.append((1004, x[i + 1:i + 1 + n])); i += 1 + n
            elif t == 1: out.append((1001, struct.unpack_from('<H', x, i)[0])); i += 2
            elif t == 2: out.append((1002, x[i])); i += 1
            elif t == 5: out.append((1005, x[i:i + 8])); i += 8
            elif 10 <= t <= 13: out.append((1000 + t, struct.unpack_from('<3d', x, i))); i += 24
            elif 40 <= t <= 42: out.append((1000 + t, struct.unpack_from('<d', x, i)[0])); i += 8
            elif t == 70: out.append((1070, struct.unpack_from('<h', x, i)[0])); i += 2
            elif t == 71: out.append((1071, struct.unpack_from('<i', x, i)[0])); i += 4
            else: break
    except (IndexError, struct.error):
        pass
    return out


def decode(r):
    """Decode one record to a dict, or None for types without a decoder. The fixed header is parsed from the front; the data block is taken from the back
    when its length is known from the type and mask, otherwise forward after the handle."""
    t, fl = r[0], r[1]
    kind = TYPES.get(t)
    layer, mask = struct.unpack_from('<HH', r, 4)
    e = dict(kind=kind, type=t, flags=fl, layer_index=layer, mask=mask)
    p = 8
    if fl & 1: e['color'] = r[p]; p += 1
    try:
        if t == 24: p += 1  # viewports carry one more byte before the xdata
        if fl & 0x40 and t not in (12, 13):
            xe = _xdata_end(r, p)
            if xe >= len(r) - 2: raise IndexError
            e['xdata'] = r[p + 2:xe]
            p = xe + 1  # one byte after the xdata block (2 or 3 in the samples); the linetype follows it
        if fl & 2: e['ltype'] = struct.unpack_from('<H', r, p)[0]; p += 2
        if fl & 0x20: p += 1 + r[p]
    except (IndexError, struct.error):
        e['layout_fallback'] = True  # header fields not understood: the data block is located from the CRC (fixed sizes) or by fitting the strings (text)
    end = len(r) - 2
    if kind in ('TEXT', 'ATTRIB', 'ATTDEF') and _text_end(r, p, kind, mask, end) != end:
        for p0 in range(8, 40):  # header fields before the data are unreliable in the block stream: find the start that makes the strings fit exactly
            if _text_end(r, p0, kind, mask, end) == end:
                p = p0; e['layout_fallback'] = True; break
    fixed = {1: 32 if fl & 4 else 48, 2: 16, 3: 24, 8: 40, 11: 64, 20: 16 + (8 if mask & 1 else 0) + (8 if mask & 2 else 0) + (8 if mask & 4 else 0) + (1 if mask & 8 else 0),
             14: 18 + 8 * bin(mask & 15).count('1') + (24 if mask & 0x100 else 0),
             19: (1 if mask & 1 else 0) + (8 if mask & 2 else 0) + (8 if mask & 4 else 0) + (2 if mask & 0x100 else 0)}
    if t in fixed and p != end - fixed[t]:
        e['layout_fallback'] = True
        p = end - fixed[t]  # fixed-size data: the header before it is unreliable in the block stream, so count from the CRC
    d = lambda o: struct.unpack_from('<d', r, o)[0]
    if kind == 'LINE':
        n = (end - p) // 8
        if n == 4: e.update(p1=(d(p), d(p + 8), 0.0), p2=(d(p + 16), d(p + 24), 0.0))
        elif n == 6: e.update(p1=(d(p), d(p + 8), d(p + 16)), p2=(d(p + 24), d(p + 32), d(p + 40)))
    elif kind == 'POINT':
        e['p'] = (d(p), d(p + 8), 0.0)
    elif kind == 'CIRCLE':
        e.update(center=(d(p), d(p + 8), 0.0), radius=d(p + 16))
    elif kind == 'ARC':
        e.update(center=(d(p), d(p + 8), 0.0), radius=d(p + 16), a0=d(p + 24), a1=d(p + 32))
    elif kind == 'SOLID':
        e['pts'] = [(d(p + 16 * i), d(p + 16 * i + 8), 0.0) for i in range(4)]
    elif kind == 'TEXT':
        x, y, h = d(p), d(p + 8), d(p + 16); p += 24
        n = struct.unpack_from('<H', r, p)[0]; p += 2
        s = r[p:p + n].decode('latin1').rstrip('\0'); p += n
        e.update(p=(x, y, 0.0), height=h, text=s, rot=0.0, wf=1.0, halign=0, style_index=0)
        if mask & 1: e['rot'] = d(p); p += 8
        if mask & 2: e['wf'] = d(p); p += 8
        if mask & 4: e['oblique'] = d(p); p += 8
        if mask & 8: e['style_index'] = r[p]; p += 1
        if mask & 0x10: e['gen'] = r[p]; p += 1
        if mask & 0x20: e['halign'] = r[p]; p += 1
        if mask & 0x40: e['align_pt'] = (d(p), d(p + 8), 0.0); p += 16
        if mask & 0x100: e['valign'] = r[p]; p += 1
        if not (e['halign'] or e.get('valign')): e.pop('align_pt', None)  # the stored point equals the insertion point then
    elif kind == 'INSERT':
        bi = struct.unpack_from('<H', r, p)[0]; p += 2
        x, y = d(p), d(p + 8); p += 16
        sx = sy = sz = 1.0; rot = 0.0
        if mask & 1: sx = d(p); p += 8
        if mask & 2: sy = d(p); p += 8
        if mask & 4: rot = d(p); p += 8
        if mask & 8: sz = d(p); p += 8
        ext = (0.0, 0.0, 1.0)
        if mask & 0x100: ext = (d(p), d(p + 8), d(p + 16)); p += 24
        e.update(block_index=bi, ins=(x, y, 0.0), scale=(sx, sy, sz), rot=rot, ext=ext)
    elif kind in ('ATTRIB', 'ATTDEF'):
        x, y, h = d(p), d(p + 8), d(p + 16); p += 24
        def _s(p):
            n = struct.unpack_from('<H', r, p)[0]
            return r[p + 2:p + 2 + n].decode('latin1').rstrip('\0'), p + 2 + n
        text, p = _s(p)
        prompt = None
        if kind == 'ATTDEF': prompt, p = _s(p)
        tag, p = _s(p)
        flags = r[p]; p += 1  # 1 invisible, 2 constant, 4 verify, 8 preset
        m = mask >> 1  # same field bits as TEXT
        e.update(p=(x, y, 0.0), height=h, text=text, tag=tag, prompt=prompt, attflags=flags, invisible=bool(flags & 1), rot=0.0, wf=1.0, halign=0, style_index=0)
        if m & 1: e['rot'] = d(p); p += 8
        if m & 2: e['wf'] = d(p); p += 8
        if m & 4: e['oblique'] = d(p); p += 8
        if m & 8: e['style_index'] = r[p]; p += 1
        if m & 0x10: e['gen'] = r[p]; p += 1
        if m & 0x20: e['halign'] = r[p]; p += 1
        if m & 0x40: e['align_pt'] = (d(p), d(p + 8), 0.0); p += 16
        if m & 0x100: e['valign'] = r[p]; p += 1
        if not (e['halign'] or e.get('valign')): e.pop('align_pt', None)
    elif kind == 'POLYLINE':
        fl2 = 0; sw = ew = 0.0; curve = 0
        if mask & 1: fl2 = r[p]; p += 1
        if mask & 2: sw = d(p); p += 8
        if mask & 4: ew = d(p); p += 8
        if mask & 0x100: curve = struct.unpack_from('<H', r, p)[0]; p += 2
        e.update(pflags=fl2, closed=bool(fl2 & 1), start_width=sw, end_width=ew, curve=curve)
    elif kind == 'VERTEX':
        x, y = d(p), d(p + 8); p += 16
        bulge = 0.0; sw = ew = 0.0; vfl = 0
        if mask & 1: sw = d(p); p += 8
        if mask & 2: ew = d(p); p += 8
        if mask & 4: bulge = d(p); p += 8
        if mask & 8: vfl = r[p]; p += 1
        e.update(p=(x, y, 0.0), bulge=bulge, start_width=sw, end_width=ew, vflags=vfl)
    elif kind == 'DIMENSION':
        e['block_index'] = struct.unpack_from('<H', r, p)[0]  # the picture block (*D<n>) in the block table
    elif kind == 'VIEWPORT':
        q = end - 42
        e.update(center=(d(q), d(q + 8), d(q + 16)), width=d(q + 24), height=d(q + 32), vp_id=struct.unpack_from('<H', r, q + 40)[0])
        items = xdata_items(e.get('xdata', b''))
        pts = [v for c, v in items if c == 1010]; reals = [v for c, v in items if c == 1040]
        e.update(view_target=pts[0] if pts else (0.0, 0.0, 0.0), view_dir=pts[1] if len(pts) > 1 else (0.0, 0.0, 1.0), twist=reals[0] if reals else 0.0,
                 view_height=reals[1] if len(reals) > 1 else e['height'], view_center=(reals[2], reals[3]) if len(reals) > 3 else (e['center'][0], e['center'][1]), lens=reals[4] if len(reals) > 4 else 50.0,
                 frozen=[v for c, v in items if c == 1003])
    elif kind == 'BLOCK':
        n = len(r) - 2
        for ln in range(0, 64):  # name = u16 length + chars right before the CRC
            q = n - ln - 2
            if q >= p + 16 and struct.unpack_from('<H', r, q)[0] == ln and all(32 <= c < 127 for c in r[q + 2:n]):
                e['name'] = r[q + 2:n].decode('latin1'); e['base'] = (d(q - 16), d(q - 8), 0.0); break
    else:
        return e
    return e


def _table(b, i):
    sz, cnt, _, addr = struct.unpack_from('<HHHI', b, 0x2C + 10 * i)
    return [b[addr + sz * k:addr + sz * (k + 1)] for k in range(cnt)]


class _VP:
    type = 34
    handle = 0

    def __init__(self, rec): self.rec = rec


class Model12:
    """Model facade for AC1009 (partial): layers, blocks, entities() with the same entity dicts as Model14 (LINE ARC CIRCLE POINT SOLID TEXT ATTRIB ATTDEF INSERT POLYLINE2D VERTEX2D SEQEND).
    Not read yet: DIMENSION (type 23), paper space, linetype and style tables, header variables."""
    version = 'AC1009'

    def __init__(self, buf):
        self._buf = buf
        self.codepage = 30
        es, ee = struct.unpack_from('<II', buf, 0x14)
        self._main = (es, ee)
        self._bs = struct.unpack_from('<I', buf, 0x1C)[0]
        self._layers = layers(buf)
        self._lt = self._read_ltypes(); self._st = self._read_styles()
        self.layers = {i + 1: l['name'] for i, l in enumerate(self._layers)}
        tb = _table(buf, 0)
        rec_names = []
        for r in records(buf, self._bs, len(buf)):
            if r[0] == 12:
                try: nm = decode(r).get('name')
                except Exception: nm = None
                rec_names.append(nm)
        # table entries flagged 128 are erased and have no BLOCK record; the others follow the records in order
        self.blocks = {}; self._order = []
        k = 0
        for i, e in enumerate(tb):
            if e[0] & 128: continue
            tname = e[1:33].split(b'\0')[0].decode('latin1')
            nm = (rec_names[k] if k < len(rec_names) else None) or tname
            self.blocks[i + 1] = nm; self._order.append(i + 1); k += 1
        self.blocks[0] = '*Model_Space'
        self.model = 0

    def _read_ltypes(self):
        out = []
        for e in _table(self._buf, 3):
            name = e[1:33].split(b'\0')[0].decode('latin1')
            desc = e[35:83].split(b'\0')[0].decode('latin1')
            nd = e[84]; plen = struct.unpack_from('<d', e, 85)[0]
            nd = nd if nd <= 12 else 0
            dashes = [dict(length=struct.unpack_from('<d', e, 93 + 8 * i)[0], shape=0, flags=0, offset=(0.0, 0.0), scale=1.0, rotation=0.0) for i in range(nd)]
            out.append(dict(name=name, description=desc, pattern_length=plen, dashes=dashes))
        return out

    def _read_styles(self):
        out = []
        for e in _table(self._buf, 2):
            name = e[1:33].split(b'\0')[0].decode('latin1')
            h, wf, ob = struct.unpack_from('<3d', e, 35)
            font = e[68:132].split(b'\0')[0].decode('latin1')
            out.append(dict(name=name, height=h, width=wf, oblique=ob, gen=e[59], font=font))
        return out

    def ltypes(self): return {l['name']: l for l in self._lt}

    def styles(self): return {s['name']: s for s in self._st}

    def layer_table(self):
        return {l['name']: dict(color=l['color'], off=l['off'], frozen=bool(l['flags'] & 1), ltype=(self._lt[l['ltype']]['name'] if l['ltype'] < len(self._lt) else None), lineweight_mm=None, true_color=None) for l in self._layers}

    def effective(self, e):
        lt = self.layer_table().get(e.get('layer'), {})
        col = e['color'][0]
        if col == 256: col = lt.get('color', 7)
        lti = e.get('ltype_index')
        ltn = self._lt[lti]['name'] if lti is not None and lti < len(self._lt) else lt.get('ltype')
        if ltn and ltn.upper() == 'CONTINUOUS': ltn = None
        return dict(color=abs(col) if col else col, rgb=None, lineweight_mm=None, ltype=ltn, off=lt.get('off', False), frozen=lt.get('frozen', False))

    def _entity(self, r, block_name, owner):
        d = decode(r)
        if d is None or d['kind'] is None or d['kind'] in ('BLOCK', 'ENDBLK', 'VIEWPORT'): return None
        li = d['layer_index']
        e = dict(kind=d['kind'], handle=0, layer=self.layers.get(li + 1) if li < len(self._layers) else None, owner=owner, entmode=2, handles=[])
        e['color'] = (256 if 'color' not in d else d['color'], None, None)
        if 'ltype' in d: e['ltype_index'] = d['ltype']
        e.update(ext=(0.0, 0.0, 1.0), elev=0.0, thickness=0.0)
        k = d['kind']
        if k == 'DIMENSION':
            bn = self.blocks.get(d['block_index'] + 1)
            e.update(kind='DIM_LINEAR', block_handle=d['block_index'] + 1, block_ref=bn, user_text='')
        elif k in ('LINE', 'POINT', 'CIRCLE', 'ARC'):
            e.update({a: d[a] for a in ('p1', 'p2', 'p', 'center', 'radius', 'a0', 'a1') if a in d})
        elif k == 'SOLID':
            e.update(pts=[q[:2] for q in d['pts']])
        elif k in ('TEXT', 'ATTRIB', 'ATTDEF'):
            e.update(ins=d['p'], align=d.get('align_pt') or d['p'], height=d['height'], text=d['text'], rot=d['rot'], widthf=d['wf'], oblique=d.get('oblique', 0.0), gen=d.get('gen', 0), halign=d['halign'], valign=d.get('valign', 0), style=(self._st[d['style_index']]['name'] if d['style_index'] < len(self._st) else None), mirror_x=False, mirror_y=False)
            if k != 'TEXT': e.update(tag=d['tag'], prompt=d['prompt'], invisible=d['invisible'])
        elif k == 'INSERT':
            bn = self.blocks.get(d['block_index'] + 1)
            e.update(ins=d['ins'], scale=d['scale'], rot=d['rot'], ext=d['ext'], block_handle=d['block_index'] + 1, block_ref=bn, hasattribs=bool(d['flags'] & 0x80))
        elif k == 'POLYLINE':
            e.update(kind='POLYLINE2D', flags=d['pflags'], closed=d['closed'], curve=d['curve'], start_width=d['start_width'], end_width=d['end_width'], thickness=0.0, elev=0.0, ext=(0.0, 0.0, 1.0))
        elif k == 'VERTEX':
            e.update(kind='VERTEX2D', flags=d['vflags'], p=d['p'], start_width=d['start_width'], end_width=d['end_width'], bulge=d['bulge'], tangent=0.0)
        elif k == 'SEQEND':
            pass
        return e

    def entities(self, only_types=None):
        n = 0; last_ins = 0
        es, ee = self._main
        for r in records(self._buf, es, ee):
            try: e = self._entity(r, '*Model_Space', self.model)
            except Exception: continue
            if e:
                n += 1; e['handle'] = n
                if e['kind'] == 'INSERT': last_ins = n
                elif e['kind'] == 'ATTRIB': e['owner'] = last_ins
                yield '*Model_Space', e
        cur = None; idx = 0
        for r in records(self._buf, self._bs, len(self._buf)):
            if r[0] == 12:
                cur = self.blocks.get(self._order[idx]) if idx < len(self._order) else None; idx += 1; continue
            if r[0] == 13: cur = None; continue
            if cur is None: continue
            try: e = self._entity(r, cur, self._order[idx - 1] if 0 < idx <= len(self._order) else 0)
            except Exception: continue
            if e:
                n += 1; e['handle'] = n
                if e['kind'] == 'INSERT': last_ins = n
                elif e['kind'] == 'ATTRIB': e['owner'] = last_ins
                yield cur, e

    def _viewports(self):
        if getattr(self, '_vps', None) is None:
            self._vps = []
            es, ee = self._main
            for r in records(self._buf, es, ee):
                if r[0] == 24:
                    try: self._vps.append(decode(r))
                    except Exception: pass
        return self._vps

    @property
    def objs(self):
        return {i + 1: _VP(v) for i, v in enumerate(self._viewports())}

    def decode_viewport(self, o):
        v = o.rec
        return dict(v, nfrozen=len(v['frozen']), frozen_handles=[], overall=v['vp_id'] == 1)

    def viewport_frozen(self, o): return set(o.rec['frozen'])

    def draw_order(self): return {}
    def object_strings(self, *a, **k): return []
    def dimstyles(self): return {}
    def classes(self): return []
    def proxy_texts(self): return []
    def header(self):
        # variables found at fixed byte offsets (equal to AutoCAD's DXF HEADER on both dumped files; the extents are as stored, AutoCAD recomputes them)
        u = lambda o: struct.unpack_from('<d', self._buf, o)[0]
        h = dict(LTSCALE=u(306), TEXTSIZE=u(314), PDMODE=struct.unpack_from('<h', self._buf, 861)[0], DIMSCALE=u(419), DIMASZ=u(427), DIMEXO=u(435), DIMDLI=u(443), DIMEXE=u(451), DIMTXT=u(475), DIMCEN=u(483), FILLETRAD=u(386), DIMGAP=u(1707),
                 LIMMIN=(u(168), u(176)), LIMMAX=(u(184), u(192)), EXTMIN=(u(120), u(128), 0.0), EXTMAX=(u(144), u(152), 0.0))
        return h

    def layouts(self):
        out = [dict(name='Model', block=self.model, block_name='*Model_Space', paper=(0.0, 0.0), paper_size='', viewports=[])]
        vps = self._viewports()
        if vps:  # the first viewport (id 1) is the overall paper-space viewport and covers the sheet
            v = vps[0]
            out.append(dict(name='Layout1', block=None, block_name='*Paper_Space', paper=(v['width'], v['height']), origin=(v['center'][0] - v['width'] / 2, v['center'][1] - v['height'] / 2), paper_size='', viewports=list(range(1, len(vps) + 1))))
        return out


def _empty_table_api(cls):
    """R12-R14 files carry none of the newer table objects: the accessors exist and return empty results so consumers need no version checks."""
    for n in ('mlstyles', 'mleaderstyles', 'scales', 'dictvars', 'layer_overrides', 'layer_states', 'dictionaries'):
        setattr(cls, n, lambda self: {})
    for n in ('named_views', 'ucs_list', 'vports'):
        setattr(cls, n, lambda self: [])
_empty_table_api(Model12)
