"""Object-level editing for the R2004 family: object stream + handle map rebuild, entity re-encoding by bit splicing."""
import struct
import dwgfmt as F
import dwgbits as B
import dwgbitw as W
import dwgload
import dwgent


def mc_u(v):
    out = bytearray()
    while True:
        c = v & 0x7F; v >>= 7
        if v: out.append(c | 0x80)
        else: out.append(c); break
    return bytes(out)


def mc_s(v):
    neg = v < 0
    v = abs(v)
    out = bytearray()
    while True:
        c = v & 0x7F; v >>= 7
        if v:
            out.append(c | 0x80)
        else:
            if c & 0x40:  # sign bit collides: need another byte
                out.append(c | 0x80); out.append(0x40 if neg else 0x00)
            else:
                out.append(c | (0x40 if neg else 0))
            break
    return bytes(out)


def handles_section(omap):
    """omap: {handle: offset in the objects section} -> Handles section plaintext (chunks of <= ~2032 bytes, deltas reset per chunk)."""
    items = sorted(omap.items())
    out = bytearray()
    chunk = bytearray(); ph = po = 0
    def flush():
        nonlocal chunk
        if not chunk: return
        n = len(chunk) + 2
        body = struct.pack('>H', n) + bytes(chunk)
        out.extend(body); out.extend(struct.pack('>H', F.crc16(body, 0xC0C1)))
        chunk = bytearray()
    for h, off in items:
        chunk += mc_u(h - ph) + mc_s(off - po)
        ph, po = h, off
        if len(chunk) >= 2030:  # EXP: AutoCAD closes a chunk once its pair bytes reach 2030
            flush(); ph = po = 0
    flush()
    tail = struct.pack('>H', 2)
    out.extend(tail); out.extend(struct.pack('>H', F.crc16(tail, 0xC0C1)))
    return bytes(out)


def objects_section(raws):
    """raws: list of (handle, raw bytes) in desired order -> (plaintext, {handle: offset}). Sections start with 4 zero bytes in the originals (first object at offset 4)."""
    buf = bytearray(b'\0\0\0\0')
    omap = {}
    for h, raw in raws:
        omap[h] = len(buf)
        buf += raw
    return bytes(buf), omap


def handle_stream_end(o):
    """Exact end bit of the handle stream (handles take >= 8 bits, padding < 8 bits)."""
    if o.ver not in ('AC1015', 'AC1018'):
        # R2010+: the handle stream is the last 'hsize' bits before the CRC; recompute from the layout
        raise NotImplementedError
    r = B.Bits(o.raw, o.handle_bit)
    end = (len(o.raw) - 2) * 8
    while end - r.p >= 8:
        r.H()
    return r.p


def _ms(v):
    if v < 0x8000: return struct.pack('<H', v)
    return struct.pack('<HH', (v & 0x7FFF) | 0x8000, v >> 15)


def splice_entity(o, new_spec, spec_start, spec_end):
    """Return new raw bytes for object o with the entity specific part [spec_start, spec_end) replaced by the bit string new_spec (BitWriter)."""
    raw = o.raw
    if o.ver in ('AC1015', 'AC1018'):
        hs_end = handle_stream_end(o)
        w = W.BitWriter()
        w.copy_bits(raw, 16, spec_start)
        w.bits.extend(new_spec.bits)
        new_handle_bit = 16 + len(w)  # relative to start incl. size field
        w.copy_bits(raw, spec_end, hs_end)
        while len(w) % 8: w.bits.append(1)  # EXP: padding bits are ones
        body = w.tobytes()
        # patch bitsize RL: right after the type BS
        r = B.Bits(raw, 16); r.BS()
        rl_pos = r.p - 16
        pw = W.BitWriter(); pw.bits = [(body[i >> 3] >> (7 - (i & 7))) & 1 for i in range(len(body) * 8)]
        newbits = pw.bits
        v = (new_handle_bit - 16)  # bits from after the size field up to the handle stream start
        for k in range(32):
            newbits[rl_pos + k] = (v >> (7 - (k % 8) + 8 * (k // 8)) ) & 1 if False else 0
        # write RL little endian bytewise msb-first
        patch = W.BitWriter(); patch.RL(v)
        for k in range(32): newbits[rl_pos + k] = patch.bits[k]
        pw.bits = newbits
        body = pw.tobytes()
        out = _ms(len(body)) + body
        return out + struct.pack('<H', F.crc16(out, 0xC0C1))
    return _splice_r2010(o, new_spec, spec_start, spec_end)


def _split_header_r2010(raw):
    sz = raw[0] | (raw[1] << 8); n = 2
    if sz & 0x8000:
        sz = (sz & 0x7FFF) | ((raw[2] | (raw[3] << 8)) << 15); n = 4
    v = sh = 0; nmc = 0
    while True:
        c = raw[n + nmc]; v |= (c & 0x7F) << sh; sh += 7; nmc += 1
        if not c & 0x80: break
    return sz, n, v, nmc


def _splice_r2010(o, new_spec, spec_start, spec_end):
    raw = o.raw
    sz, n, hsize, nmc = _split_header_r2010(raw)
    body_start = (n + nmc) * 8
    end = (len(raw) - 2) * 8
    r = B.Bits(raw, o.handle_bit)
    while end - r.p >= 8:
        r.H()
    real_end = r.p
    w = W.BitWriter()
    w.copy_bits(raw, body_start, spec_start)
    w.bits.extend(new_spec.bits)
    w.copy_bits(raw, spec_end, o.handle_bit)
    new_handle = len(w)
    w.copy_bits(raw, o.handle_bit, real_end)
    while len(w) % 8: w.bits.append(1)
    body = w.tobytes()
    new_hsize = len(w) - new_handle
    head = _ms(len(body)) + mc_u(new_hsize)
    out = head + body
    return out + struct.pack('<H', F.crc16(out, 0xC0C1))


# ---- entity specific encoders (inverse of dwgent decoders); each returns a BitWriter ----
def enc_line(e, orig_tail=None):
    """orig_tail: the original bits of thickness/extrusion (some writers store the default extrusion explicitly) - copied when given."""
    w = W.BitWriter()
    z0 = e['p1'][2] == 0.0 and e['p2'][2] == 0.0
    w.B(z0); w.RD(e['p1'][0]); w.DD(e['p2'][0], e['p1'][0]); w.RD(e['p1'][1]); w.DD(e['p2'][1], e['p1'][1])
    if not z0:
        w.RD(e['p1'][2]); w.DD(e['p2'][2], e['p1'][2])
    if orig_tail is not None: w.bits.extend(orig_tail)
    else: w.BT(e['thickness']); w.BE(e['ext'])
    return w


def enc_circle_arc(e):
    w = W.BitWriter()
    w.BD3(e['center']); w.BD(e['radius']); w.BT(e['thickness']); w.BE(e['ext'])
    if e['kind'] == 'ARC': w.BD(e['a0']); w.BD(e['a1'])
    return w


def enc_point(e):
    w = W.BitWriter()
    w.BD3(e['p']); w.BT(e['thickness']); w.BE(e['ext']); w.BD(e['xangle'])
    return w


def enc_ellipse(e):
    w = W.BitWriter()
    w.BD3(e['center']); w.BD3(e['major']); w.BD3(e['ext']); w.BD(e['ratio']); w.BD(e['a0']); w.BD(e['a1'])
    return w


def enc_lwpolyline(e):
    w = W.BitWriter()
    fl = e['flags']
    w.BS(fl)
    if fl & 4: w.BD(e['constwidth'])
    if fl & 8: w.BD(e['elev'])
    if fl & 2: w.BD(e['thickness'])
    if fl & 1: w.BD3(e['ext'])
    pts = e['pts']
    w.BL(len(pts))
    if fl & 16: w.BL(len(e['bulges']))
    if fl & 1024: w.BL(len(e['ids']))
    if fl & 32: w.BL(len(e['widths']))
    for i, p in enumerate(pts):
        if i == 0: w.RD2(p)
        else: w.DD(p[0], pts[i - 1][0]); w.DD(p[1], pts[i - 1][1])
    for b in e['bulges']: w.BD(b)
    for v in e.get('ids', []): w.BL(v)
    for a, b in e['widths']: w.BD(a); w.BD(b)
    return w


ENCODERS = {19: enc_line, 17: enc_circle_arc, 18: enc_circle_arc, 27: enc_point, 35: enc_ellipse, 77: enc_lwpolyline}


def spec_range(o, decode):
    """(start, end, fields) of the entity-specific bit range of o."""
    r = dwgent.start_reader(o); dwgent.common_entity(r, o.ver); s0 = r.p
    e = decode(o)
    return s0, dwgent.LAST_READER.p, e


def edit_entity(o, decode, mutate):
    """Decode o, apply mutate(fields) and return the new raw bytes."""
    s0, s1, e = spec_range(o, decode)
    mutate(e)
    if o.type == 19:
        r = B.Bits(o.raw, s0); z0 = r.B(); r.RD(); r.DD(0.0); r.RD(); r.DD(0.0)
        if not z0: r.RD(); r.DD(0.0)
        tail = [(o.raw[i >> 3] >> (7 - (i & 7))) & 1 for i in range(r.p, s1)]
        return splice_entity(o, enc_line(e, tail), s0, s1)
    return splice_entity(o, ENCODERS[o.type](e), s0, s1)


def apply_edits(buf, new_raws, rewrite=None):
    """Rebuild the objects and handles sections with the objects of new_raws {handle: raw bytes} replaced (or added), return the new file bytes."""
    import dwgwrite
    info = F.r2004_open(buf)
    hs = F.r2004_section_data(buf, info, 'AcDb:Handles')
    od = F.r2004_section_data(buf, info, 'AcDb:AcDbObjects')
    omap, ok = F.object_map_r13_r2000(hs, (0, 0, len(hs)))
    d = dwgload.load(buf)
    order = sorted(omap.items(), key=lambda kv: kv[1])
    raws = []
    for h, off in order:
        raws.append((h, new_raws.get(h, d['objects'][h].raw)))
    for h, raw in new_raws.items():
        if h not in omap: raws.append((h, raw))
    new_od, new_omap = objects_section(raws)
    return dwgwrite.rewrite_r2004(buf, {'AcDb:AcDbObjects': new_od, 'AcDb:Handles': handles_section(new_omap)})


# ---------------------------------------------------------------- handle streams
def parse_handles_raw(o):
    """[(code, value)] of the handle stream exactly as stored (relative codes unresolved) and the bit position where it really ends."""
    if o.ver in ('AC1015', 'AC1018'):
        end = (len(o.raw) - 2) * 8
        start = o.handle_bit
    else:
        sz, n, hsize, nmc = _split_header_r2010(o.raw)
        end = (len(o.raw) - 2) * 8
        start = o.handle_bit
    r = B.Bits(o.raw, start)
    out = []
    while end - r.p >= 8:
        out.append(r.H())
    return out, r.p


def emit_handles(lst):
    w = W.BitWriter()
    for c, v in lst:
        w.H(c, v)
    return w


def assemble(o, body_bits, handle_bits):
    """Build a complete object (size, header, data, handles, padding ones, CRC) from the bit strings before/after the handle stream start.
    R2004/AC1015: body_bits = everything after the 2-byte size field up to the handle stream start (the bitsize RL is patched here).
    R2010+: body_bits = everything after the MC up to the handle stream start."""
    if o.ver in ('AC1015', 'AC1018'):
        bits = list(body_bits.bits)
        bitsize = len(bits)
        r = B.Bits(o.raw, 16); r.BS(); rl_pos = r.p - 16
        pw = W.BitWriter(); pw.RL(bitsize)
        bits[rl_pos:rl_pos + 32] = pw.bits
        bits.extend(handle_bits.bits)
        while len(bits) % 8: bits.append(1)
        w = W.BitWriter(); w.bits = bits
        body = w.tobytes()
        out = _ms(len(body)) + body
        return out + struct.pack('<H', F.crc16(out, 0xC0C1))
    bits = list(body_bits.bits) + list(handle_bits.bits)
    while len(bits) % 8: bits.append(1)
    hsize = len(bits) - len(body_bits.bits)
    w = W.BitWriter(); w.bits = bits
    body = w.tobytes()
    out = _ms(len(body)) + mc_u(hsize) + body
    return out + struct.pack('<H', F.crc16(out, 0xC0C1))


def body_start(o):
    if o.ver in ('AC1015', 'AC1018'): return 16
    sz, n, hsize, nmc = _split_header_r2010(o.raw)
    return (n + nmc) * 8


def split_object(o):
    """Original pieces: (body_bits_before_handles as BitWriter, handles list)."""
    w = W.BitWriter(); w.copy_bits(o.raw, body_start(o), o.handle_bit)
    hs, _ = parse_handles_raw(o)
    return w, hs


def own_handle_range(o):
    """bit range [start,end) of the object's own handle H inside the raw bits (right after the type)."""
    r = B.Bits(o.raw, o.data_bit)
    s = r.p
    r.H()
    return s, r.p


class Editor:
    """In-memory editor for an R2004-family file: entities can be modified, added (cloned from a template entity) and deleted."""

    def __init__(self, buf):
        import dwgmodel
        self.buf = buf
        self.model = dwgmodel.Model(buf)
        self.objs = self.model.objs
        self.new = {}        # handle -> raw (modified or added)
        self.deleted = set()
        self.max_handle = max(self.objs)
        self.owner_of = {e['handle']: b for b, e in self.model.entities()}

    # -- helpers
    def raw(self, h):
        if h in self.new: return self.new[h]
        return self.objs[h].raw

    def _as_obj(self, h):
        """Object view of a possibly modified raw (re-parsed)."""
        o = self.objs.get(h)
        if h in self.new and o is not None:
            n = dwgload.Obj(); n.handle = h; n.ver = o.ver; n.codepage = o.codepage; n.raw = self.new[h]
            # recompute positions with the loader logic
            import copy
            return _reparse(n)
        return o

    def alloc_handle(self):
        self.max_handle += 1
        return self.max_handle

    def block_handle(self, name):
        for h, n in self.model.blocks.items():
            if n.lower() == name.lower(): return h
        raise KeyError(name)

    # -- owner list maintenance (R2004+: BLOCK_HEADER stores owned entity handles + count)
    def _block_update_owned(self, block_h, add=None, remove=None):
        import dwgtab
        o = self._as_obj(block_h)
        info = dwgtab.decode_block_header(o)
        p0 = dwgtab.MARKS['nowned']; p1 = dwgtab.MARKS['nowned_end']
        n = info['nowned']
        body = W.BitWriter()
        bs = body_start(o)
        body.copy_bits(o.raw, bs, p0)
        newn = n + (1 if add is not None else 0) - (1 if remove is not None else 0)
        body.BL(newn)
        body.copy_bits(o.raw, p1, o.handle_bit)
        hs, _ = parse_handles_raw(o)
        # absolute handles for locating BLOCK / ENDBLK / owned entities
        absv = [self._abs(c, v, block_h) for c, v in hs]
        idx_block = next(i for i, a in enumerate(absv) if a in self.objs and self.objs[a].type == 4)
        idx_end = next(i for i, a in enumerate(absv) if a in self.objs and self.objs[a].type == 5)
        if add is not None:
            hs.insert(idx_end, (3, add))
        if remove is not None:
            for i in range(idx_block + 1, idx_end):
                if absv[i] == remove:
                    del hs[i]; break
            else:
                raise KeyError('entity %x not owned by block' % remove)
        self.new[block_h] = assemble(o, body, emit_handles(hs))

    @staticmethod
    def _abs(c, v, own):
        if c in (2, 3, 4, 5): return v
        if c == 6: return own + 1
        if c == 8: return own - 1
        if c == 10: return own + v
        if c == 12: return own - v
        return v

    # -- public API
    def modify(self, h, mutate):
        import dwgmodel
        o = self._as_obj(h)
        dec = dwgmodel.ENT_DECODERS[o.type]
        s0, s1, e = spec_range(o, dec)
        mutate(e)
        enc = ENCODERS[o.type]
        if o.type == 19:
            r = B.Bits(o.raw, s0); z0 = r.B(); r.RD(); r.DD(0.0); r.RD(); r.DD(0.0)
            if not z0: r.RD(); r.DD(0.0)
            tail = [(o.raw[i >> 3] >> (7 - (i & 7))) & 1 for i in range(r.p, s1)]
            spec = enc_line(e, tail)
        else:
            spec = enc(e)
        self.new[h] = splice_entity(o, spec, s0, s1)

    def clone_entity(self, template_h, mutate, layer=None, block=None):
        """New entity with a new handle copied from template_h; mutate edits the decoded fields; layer: name; block: owner block name (R2004+: updates its owned list)."""
        import dwgmodel
        t = self._as_obj(template_h)
        dec = dwgmodel.ENT_DECODERS[t.type]
        s0, s1, e = spec_range(t, dec)
        mutate(e)
        spec = ENCODERS[t.type](e) if t.type != 19 else None
        if t.type == 19:
            r = B.Bits(t.raw, s0); z0 = r.B(); r.RD(); r.DD(0.0); r.RD(); r.DD(0.0)
            if not z0: r.RD(); r.DD(0.0)
            tail = [(t.raw[i >> 3] >> (7 - (i & 7))) & 1 for i in range(r.p, s1)]
            spec = enc_line(e, tail)
        nh = self.alloc_handle()
        hs0, hs1 = own_handle_range(t)
        bs = body_start(t)
        body = W.BitWriter()
        body.copy_bits(t.raw, bs, hs0)
        body.H(0, nh)
        body.copy_bits(t.raw, hs1, s0)
        body.bits.extend(spec.bits)
        body.copy_bits(t.raw, s1, t.handle_bit)
        hs, _ = parse_handles_raw(t)
        # entity mode of the new entity: 2 model space, 1 first paper space, 0 inside another block (explicit owner handle)
        if block is None: block = self.owner_of.get(template_h)
        tgt_owner = self.block_handle(block) if block is not None else None
        tn = (block or '').lower()
        want = 2 if tn == '*model_space' else (1 if tn == '*paper_space' else 0)
        rr = dwgent.start_reader(t); dwgent.common_entity(rr, t.ver)
        em_old = dwgent.MARKS['entmode']
        old_mode = B.Bits(t.raw, em_old).BB()
        out = []
        first_layer_done = False
        for i, (c, v) in enumerate(hs):
            if c in (6, 8, 10, 12):
                out.append((4 if i == 0 else 5, self._abs(c, v, template_h)))
            else:
                out.append((c, v))
        if want != old_mode:
            # patch the 2 entmode bits in the already assembled body and fix the handle list (owner handle only for mode 0)
            em_new = em_old - bs - (hs1 - hs0) + len(_hbits(nh))
            nb = body.bits
            pat = W.BitWriter(); pat.BB(want)
            nb[em_new:em_new + 2] = pat.bits
            if old_mode == 0 and want != 0:
                out.pop(0)
            elif old_mode != 0 and want == 0:
                out.insert(0, (4, tgt_owner))
            elif old_mode == 0 and want == 0:
                pass
        elif want == 0:
            out[0] = (4, tgt_owner)
        if layer is not None:
            lh = next(h for h, n in self.model.layers.items() if n == layer)
            for i, (c, v) in enumerate(out):
                if c == 5 and v in self.objs and self.objs[v].type == 51:
                    out[i] = (5, lh); break
        owner_h = None
        if block is None: block = self.owner_of.get(template_h)
        if block is not None:
            owner_h = self.block_handle(block)
        raw = assemble(t, body, emit_handles(out))
        self.new[nh] = raw
        if owner_h is not None and t.ver != 'AC1015':
            self._block_update_owned(owner_h, add=nh)
        return nh

    # -- AC1015 entity chains: every entity holds prev/next handles (implicit h-1 / h+1 when the 'nolinks' bit is set)
    def _nolinks_pos(self, o):
        rr = dwgent.start_reader(o); dwgent.common_entity(rr, o.ver)
        r = B.Bits(o.raw, dwgent.MARKS['entmode']); r.BB(); r.BL()
        return r.p

    def _links(self, h):
        """(prev, next) absolute handles of an AC1015 entity (0 = none)."""
        o = self._as_obj(h)
        if B.Bits(o.raw, self._nolinks_pos(o)).B():
            return h - 1, h + 1
        hs, _ = parse_handles_raw(o)
        i = next(k for k, (c, v) in enumerate(hs) if c == 5)
        return self._abs(*hs[i - 2], h), self._abs(*hs[i - 1], h)

    def _set_links(self, h, prev, nxt):
        o = self._as_obj(h)
        pos = self._nolinks_pos(o)
        was_implicit = bool(B.Bits(o.raw, pos).B())
        implicit = (prev == h - 1 and nxt == h + 1)
        hs, _ = parse_handles_raw(o)
        i = next(k for k, (c, v) in enumerate(hs) if c == 5)
        if not was_implicit:
            del hs[i - 2:i]; i -= 2
        if not implicit:
            hs[i:i] = [(4, prev), (4, nxt)]
        body = W.BitWriter(); body.copy_bits(o.raw, body_start(o), o.handle_bit)
        body.bits[pos - body_start(o)] = 1 if implicit else 0
        self.new[h] = assemble(o, body, emit_handles(hs))

    def _block_chain_update(self, e, p, n):
        """Block header first/last entity handles after unlinking entity e (prev p, next n)."""
        for bh, bname in self.model.blocks.items():
            o = self._as_obj(bh)
            hs, _ = parse_handles_raw(o)
            absv = [self._abs(c, v, bh) for c, v in hs]
            ib = next((i for i, a in enumerate(absv) if a in self.objs and self.objs[a].type == 4), None)
            if ib is None or ib + 2 >= len(hs): continue
            if absv[ib + 1] == e or absv[ib + 2] == e:
                if absv[ib + 1] == e: hs[ib + 1] = (4, n if n else 0)
                if absv[ib + 2] == e: hs[ib + 2] = (4, p if p else 0)
                body = W.BitWriter(); body.copy_bits(o.raw, body_start(o), o.handle_bit)
                self.new[bh] = assemble(o, body, emit_handles(hs))
                return

    def delete_entity(self, h, block=None):
        if self.model.version == 'AC1015':
            p, n = self._links(h)
            if p in self.objs and p not in self.deleted:
                pp, _ = self._links(p); self._set_links(p, pp, n)
            if n in self.objs and n not in self.deleted:
                _, nn = self._links(n); self._set_links(n, p, nn)
            self._block_chain_update(h, p, n)
            self.deleted.add(h)
            return
        self.deleted.add(h)
        if block is not None:
            self._block_update_owned(self.block_handle(block), remove=h)

    def save(self):
        import dwgwrite
        if self.model.version == 'AC1021':
            raise NotImplementedError('AC1021 (R2007) is read-only: no container writer yet')
        if self.model.version == 'AC1015':
            import dwgobj as O
            d = O.load_r2000(self.buf)
            order = [o.handle for o in sorted(d['objects'].values(), key=lambda o: o.offset)]
            raws = [(h, self.raw(h)) for h in order if h not in self.deleted]
            raws += [(h, self.new[h]) for h in sorted(self.new) if h not in d['objects']]
            return dwgwrite.rewrite_r2000(self.buf, raws, self._header_r2000(d), handles_section)
        info = F.r2004_open(self.buf)
        hs = F.r2004_section_data(self.buf, info, 'AcDb:Handles')
        omap, ok = F.object_map_r13_r2000(hs, (0, 0, len(hs)))
        order = [h for h, off in sorted(omap.items(), key=lambda kv: kv[1])]
        raws = []
        for h in order:
            if h in self.deleted: continue
            raws.append((h, self.raw(h)))
        for h in sorted(self.new):
            if h not in omap: raws.append((h, self.new[h]))
        od, nm = objects_section(raws)
        plain = {'AcDb:AcDbObjects': od, 'AcDb:Handles': handles_section(nm)}
        hd = self._header_with_seed()
        if hd is not None: plain['AcDb:Header'] = hd
        return dwgwrite.rewrite_r2004(self.buf, plain)

    def _header_r2000(self, d):
        """AC1015 header variables section with HANDSEED updated in place (same search as for the R2004 family)."""
        h = F.read_r13_r2000(self.buf)
        s0, z0 = h['locators'][0][1], h['locators'][0][2]
        sec = bytearray(self.buf[s0:s0 + z0])
        mx = max(d['objects'])
        r0 = find_seed(sec, mx, d['objects'], start=20 * 8)
        if r0 is None: return None
        p, pend, v = r0
        new_seed = max(self.max_handle, max(self.new) if self.new else 0) + (v - mx)
        w = W.BitWriter(); w.H(0, new_seed)
        if len(w) != pend - p: return None
        for i, bit in enumerate(w.bits):
            pos = p + i
            if bit: sec[pos >> 3] |= 0x80 >> (pos & 7)
            else: sec[pos >> 3] &= ~(0x80 >> (pos & 7)) & 0xFF
        sz, = struct.unpack_from('<I', sec, 16)
        struct.pack_into('<H', sec, 20 + sz, F.crc16(bytes(sec[16:20 + sz]), 0xC0C1))
        return bytes(sec)

    def _header_with_seed(self):
        """Update HANDSEED in AcDb:Header: the seed is stored as a code-0 handle a little above the largest object handle. Replaced in place
        when the byte length of the handle does not change (always true for small edits); the section CRC is recomputed."""
        info = F.r2004_open(self.buf)
        hd = bytearray(F.r2004_section_data(self.buf, info, 'AcDb:Header'))
        mx = max(self.objs)
        r0 = find_seed(hd, mx, self.objs, follow=self.model.version == 'AC1018', ver=self.model.version)
        if r0 is None: return None
        new_seed = max(self.max_handle, max(self.new) if self.new else 0) + (r0[2] - mx)
        w = W.BitWriter(); w.H(0, new_seed)
        if len(w) != r0[1] - r0[0]:
            return None  # byte length changed: leave the header alone
        for i, bit in enumerate(w.bits):
            pos = r0[0] + i
            if bit: hd[pos >> 3] |= 0x80 >> (pos & 7)
            else: hd[pos >> 3] &= ~(0x80 >> (pos & 7)) & 0xFF
        if self.model.version == 'AC1018':
            sz, = struct.unpack_from('<I', hd, 16); crcpos = 20 + sz
        else:
            crcpos = len(hd) - 18
        struct.pack_into('<H', hd, crcpos, F.crc16(bytes(hd[16:crcpos]), 0xC0C1))
        return bytes(hd)


_HDR_START = {'AC1018': 160, 'AC1024': 224, 'AC1027': 227, 'AC1032': 227}


def find_seed(sec, mx, objs, follow=True, start=0, ver=None):
    """Bit position (p0, p1, value) of HANDSEED in a header section: a code-0 handle in (mx, mx+0x200]. For R2000/R2004 the seed is followed
    by the CLAYER, TEXTSTYLE and CELTYPE handle references (code 5, existing objects), which rejects false matches elsewhere in the section."""
    if ver in _HDR_START:                                    # exact position from the header variable decoder (the search below can hit other handles)
        import dwghdr
        hv = dwghdr.decode_header(bytes(sec), ver, _HDR_START[ver])
        if '_handseed_pos' in hv and '_handseed_end' in hv and not hv.get('_truncated'):
            c, v = hv['HANDSEED']
            if c == 0 and mx < v <= mx + 0x200: return hv['_handseed_pos'], hv['_handseed_end'], v
    for p in range(start, len(sec) * 8 - 40):
        r = B.Bits(sec, p)
        try:
            c, v = r.H()
        except Exception:
            continue
        if c == 0 and mx < v <= mx + 0x200:
            end = r.p
            if follow:
                try:
                    ok = True
                    for _ in range(3):
                        c2, v2 = r.H()
                        ok = ok and c2 == 5 and v2 in objs
                except Exception:
                    ok = False
                if not ok: continue
            return p, end, v
    return None



def _hbits(v):
    w = W.BitWriter(); w.H(0, v); return w.bits


def _reparse(n):
    """Fill type/data_bit/handle_bit of an Obj built from a raw."""
    ver = n.ver
    if ver in ('AC1015', 'AC1018'):
        r = B.Bits(n.raw, 16); n.type = r.BS(); bitsize = r.RL(); n.data_bit = r.p; n.handle_bit = 16 + bitsize
    else:
        sz, ln, hsize, nmc = _split_header_r2010(n.raw)
        r = B.Bits(n.raw, (ln + nmc) * 8)
        oc = r.BB(); n.type = r.RC() if oc == 0 else (r.RC() + 0x1F0 if oc == 1 else r.RS())
        n.data_bit = r.p
        n.handle_bit = (ln + nmc + sz) * 8 - hsize
    return n


STRING_COUNT = {1: 1, 2: 2, 3: 3, 44: 1}  # TEXT, ATTRIB, ATTDEF, MTEXT: strings in decode order (text, tag, prompt)
for _t in (20, 21, 22, 23, 24, 25, 26): STRING_COUNT[_t] = 1  # dimensions: user text


def set_strings(self, h, new):
    """Replace the strings of entity h (decode order). Inline versions: splice the TV fields; R2007+: rebuild the string stream."""
    import dwgmodel
    o = self._as_obj(h)
    dec = dwgmodel.ENT_DECODERS[o.type]
    e = dec(o)
    old = e.get('text') if o.type in (1, 44) else None
    n_expected = STRING_COUNT[o.type]
    if len(new) != n_expected:
        raise ValueError('entity type %d has %d strings' % (o.type, n_expected))
    bs = body_start(o)
    body = W.BitWriter()
    hs, _ = parse_handles_raw(o)
    if o.ver in ('AC1015', 'AC1018'):
        pos = list(dwgent.STRPOS)
        if len(pos) != n_expected:
            raise ValueError('string positions not recorded (%d)' % len(pos))
        cp = dwgmodel.CODEPAGES.get(self.model.codepage, 'cp1252')
        cur = bs
        for (p0, p1), s in zip(pos, new):
            body.copy_bits(o.raw, cur, p0)
            body.TV(s, cp)
            cur = p1
        body.copy_bits(o.raw, cur, o.handle_bit)
    else:
        exp = dwgent.expected_end(o)
        body.copy_bits(o.raw, bs, exp)
        strw = W.BitWriter()
        for s in new: strw.TU(s)
        body.bits.extend(strw.bits)
        size = len(strw)
        if size >= 0x8000:
            body.RS((size & 0x7FFF) | 0x8000); body.RS(size >> 15) if False else None
            raise NotImplementedError('string stream > 32767 bits')
        body.RS(size)
        body.B(1)
    self.new[h] = assemble(o, body, emit_handles(hs))


Editor.set_strings = set_strings
