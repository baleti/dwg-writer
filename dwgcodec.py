"""Symmetric object codec (own code): one function per object type that both reads and writes the object's bit streams, so that
encode(decode(raw)) == raw can be tested on AutoCAD-written files and new objects are built with the very same code path.

A codec function takes (rw, d): rw is an RW stream wrapper, d a dict. When rw.reading every primitive `d[k] = rw.X(d.get(k))` stores the
value read; when writing it emits d[k]. Handle references (handle stream) go through rw.href(value, code)."""
import struct
import dwgbits as B
import dwgbitw as W
import dwgfmt as F

WIDE = ('AC1021', 'AC1024', 'AC1027', 'AC1032')       # strings live in a separate string stream
R2010 = ('AC1024', 'AC1027', 'AC1032')
R2013 = ('AC1027', 'AC1032')
CODEPAGES = None


def _cp(codepage):
    global CODEPAGES
    if CODEPAGES is None:
        import dwgmodel
        CODEPAGES = dwgmodel.CODEPAGES
    return CODEPAGES.get(codepage, 'cp1252')


class RW:
    def __init__(self, ver, codepage=30, reading=True):
        self.ver = ver
        self.reading = reading
        self.wide = ver in WIDE
        self.cp = _cp(codepage)
        self.handle = 0
        self.hlist = []          # reading: (code, value) as stored; writing: hints from a previous read (same order)
        self.hidx = 0
        self.eed_raw = None
        self.nonul = False

    # ---- construction
    @classmethod
    def for_read(cls, o, codepage=30):
        self = cls(o.ver, codepage, True)
        self.handle = o.handle
        self.m = B.Bits(o.raw, o.data_bit)
        self.h = B.Bits(o.raw, o.handle_bit)
        self.hend = (len(o.raw) - 2) * 8
        self.s = None
        if self.wide:
            end = o.handle_bit
            if B.Bits(o.raw, end - 1).bit():
                p = end - 1 - 16
                size = B.Bits(o.raw, p).RS()
                if size & 0x8000:
                    p -= 16
                    size = (size & 0x7FFF) | (B.Bits(o.raw, p).RS() << 15)
                self.s = B.Bits(o.raw, p - size)
                self.s_end = p
                self.main_end = p - size
            else:
                self.main_end = end - 1
        else:
            self.main_end = o.handle_bit
        return self

    @classmethod
    def for_write(cls, ver, handle, codepage=30, hints=None):
        self = cls(ver, codepage, False)
        self.handle = handle
        self.m = W.BitWriter()
        self.h = W.BitWriter()
        self.s = W.BitWriter() if self.wide else None
        self.nstr = 0
        self.hlist = list(hints or [])
        return self

    # ---- primitives
    def _p(name):
        def f(self, v=None):
            if self.reading:
                return getattr(self.m, name)()
            getattr(self.m, name)(v)
            return v
        f.__name__ = name
        return f
    B = _p('B'); BB = _p('BB'); BS = _p('BS'); BL = _p('BL'); BD = _p('BD'); RC = _p('RC'); RS = _p('RS'); RL = _p('RL'); RD = _p('RD')
    BT = _p('BT'); BE = _p('BE'); BD3 = _p('BD3'); RD2 = _p('RD2')
    del _p

    def DD(self, v, default):
        if self.reading:
            return self.m.DD(default)
        self.m.DD(v, default)
        return v

    def BLL(self, v=None):
        if self.reading:
            return self.m.BLL()
        n = 0
        t = v
        while t: n += 1; t >>= 8
        self.m.put(n, 3)
        for i in range(n): self.m.RC((v >> (8 * i)) & 0xFF)
        return v

    def H(self, v=None):
        """handle stored in the main stream (code, value) pair; the object's own handle uses code 0"""
        if self.reading:
            return self.m.H()
        self.m.H(v[0], v[1])
        return v

    def raw_bits(self, n, bits=None):
        if self.reading:
            return [self.m.bit() for _ in range(n)]
        self.m.bits.extend(bits)
        return bits

    # text
    def T(self, v=None):
        if self.reading:
            if self.wide:
                if self.s is None: raise ValueError('no string stream')
                return self.s.TU()
            raw = self.m.BS()
            b = bytes(self.m.RC() for _ in range(raw))
            if b.endswith(b'\0'): b = b[:-1]
            elif b: self.nonul = True                  # some writers store inline strings without the terminating NUL
            return b.decode(self.cp, 'surrogateescape')
        if self.wide:
            self.s.TU(v)
            self.nstr += 1
            return v
        if v == '':
            self.m.BS(0)
        else:
            b = v.encode(self.cp, 'surrogateescape') + (b'' if getattr(self, 'nonul', False) else b'\0')
            self.m.BS(len(b))
            for c in b: self.m.RC(c)
        return v

    def TV_inline(self, v=None):
        """text that stays in the main stream in every version (e.g. dimension-less fixed strings)"""
        return self.T(v)

    # handle stream
    def href(self, v=None, code=5):
        """absolute handle; code used when writing (a hint from the original read is reused when it resolves to the same handle)"""
        if self.reading:
            c, val = self.h.H()
            self.hlist.append((c, val))
            return abs_handle(c, val, self.handle)
        i = self.hidx; self.hidx += 1
        if i < len(self.hlist):
            c, val = self.hlist[i]
            if abs_handle(c, val, self.handle) == v:
                self.h.H(c, val); return v
        self.h.H(code, v)
        return v

    def more_handles(self):
        return self.hend - self.h.p >= 8


def abs_handle(c, v, own):
    if c in (2, 3, 4, 5): return v
    if c == 6: return own + 1
    if c == 8: return own - 1
    if c == 10: return own + v
    if c == 12: return own - v
    return v      # code 0 (own handle) / unknown


# ---------------------------------------------------------------- framing
def split_stream_lengths(raw):
    pass


def finish(rw, otype, handle):
    """Assemble the raw object bytes from the written streams (inverse of dwgload)."""
    ver = rw.ver
    main = list(rw.m.bits)
    if rw.wide and getattr(rw, 'raw_tail', False):
        pass                                   # opaque tail already contains string stream + size + flag
    elif rw.wide:
        if rw.nstr:
            sbits = rw.s.bits
            size = len(sbits)
            main.extend(sbits)
            w = W.BitWriter()
            if size >= 0x8000:
                w.RS(size >> 15); w.RS((size & 0x7FFF) | 0x8000)
            else:
                w.RS(size)
            main.extend(w.bits)
            main.append(1)
        else:
            main.append(0)
    hbits = rw.h.bits
    if ver in ('AC1015', 'AC1018'):
        # prefix: BS type, RL bitsize (bits from after the size field up to the handle stream)
        pre = W.BitWriter(); pre.BS(otype); pre.RL(0)
        body = pre.bits + main
        bitsize = len(body)
        pre2 = W.BitWriter(); pre2.BS(otype); pre2.RL(bitsize)
        body[:len(pre2.bits)] = pre2.bits
        bits = body + list(hbits)
        while len(bits) % 8: bits.append(1)
        w = W.BitWriter(); w.bits = bits
        data = w.tobytes()
        out = _ms(len(data)) + data
        return out + struct.pack('<H', F.crc16(out, 0xC0C1))
    pre = W.BitWriter()
    if otype < 0x1F0 and otype < 256:
        pre.BB(0); pre.RC(otype)
    elif 0x1F0 <= otype < 0x2F0:
        pre.BB(1); pre.RC(otype - 0x1F0)
    else:
        pre.BB(2); pre.RS(otype)
    bits = pre.bits + main
    hs_start = len(bits)
    bits = bits + list(hbits)
    while len(bits) % 8: bits.append(1)
    hsize = len(bits) - hs_start
    w = W.BitWriter(); w.bits = bits
    data = w.tobytes()
    out = _ms(len(data)) + _mc_u(hsize) + data
    return out + struct.pack('<H', F.crc16(out, 0xC0C1))


def _ms(v):
    if v < 0x8000: return struct.pack('<H', v)
    return struct.pack('<HH', (v & 0x7FFF) | 0x8000, v >> 15)


def _mc_u(v):
    out = bytearray()
    while True:
        c = v & 0x7F; v >>= 7
        if v: out.append(c | 0x80)
        else: out.append(c); break
    return bytes(out)


# ---------------------------------------------------------------- common blocks
def eed(rw, d):
    """extended entity data: list of (app handle code/value, bytes) kept verbatim"""
    if rw.reading:
        lst = []
        while True:
            n = rw.m.BS()
            if n == 0: break
            app = rw.m.H()
            lst.append((app, bytes(rw.m.RC() for _ in range(n))))
        d['eed'] = lst
    else:
        for app, data in d.get('eed', []):
            rw.m.BS(len(data)); rw.m.H(app[0], app[1])
            for c in data: rw.m.RC(c)
        rw.m.BS(0)


def cmc(rw, v):
    """entity colour: (index, rgb|None, alpha|None, bookhandle flag)"""
    if rw.reading:
        idx = rw.m.BS()
        rgb = alpha = None
        if rw.ver != 'AC1015':
            if idx & 0x8000: rgb = rw.m.BL()
            if idx & 0x2000: alpha = rw.m.BL()
        return (idx, rgb, alpha)
    idx, rgb, alpha = v
    rw.m.BS(idx)
    if rw.ver != 'AC1015':
        if idx & 0x8000: rw.m.BL(rgb)
        if idx & 0x2000: rw.m.BL(alpha)
    return v


def entity_head(rw, d):
    """Everything between the object's handle and the entity specific data. Returns nothing; fills/consumes d."""
    rd = rw.reading
    ver = rw.ver
    eed(rw, d)
    # graphic data (proxy preview); kept raw
    if rd:
        g = rw.m.B()
        d['graphic'] = None
        if g:
            sz = rw.m.BLL() if ver in R2010 else rw.m.RL()
            d['graphic'] = [rw.m.bit() for _ in range(sz * 8)]
    else:
        g = d.get('graphic')
        rw.m.B(1 if g else 0)
        if g:
            n = len(g) // 8
            if ver in R2010:
                rw.BLL(n)
            else:
                rw.m.RL(n)
            rw.m.bits.extend(g)
    d['entmode'] = rw.BB(d.get('entmode', 0))
    d['nreactors'] = rw.BL(d.get('nreactors', 0))
    d['xdic_missing'] = rw.B(d.get('xdic_missing', 1))      # AC1015: "no links" flag
    if ver in R2013: d['has_binary'] = rw.B(d.get('has_binary', 0))
    d['color'] = cmc(rw, d.get('color', (256, None, None)))
    d['ltscale'] = rw.BD(d.get('ltscale', 1.0))
    d['ltflags'] = rw.BB(d.get('ltflags', 0))
    d['plotflags'] = rw.BB(d.get('plotflags', 0))
    if ver in WIDE:
        d['matflags'] = rw.BB(d.get('matflags', 0))
        d['shadow'] = rw.RC(d.get('shadow', 0))
        if ver in R2010:
            d['vs_full'] = rw.B(d.get('vs_full', 0)); d['vs_face'] = rw.B(d.get('vs_face', 0)); d['vs_edge'] = rw.B(d.get('vs_edge', 0))
    d['invis'] = rw.BS(d.get('invis', 0))
    d['lweight'] = rw.RC(d.get('lweight', 29))


def entity_handles(rw, d):
    """common handle stream head: owner (entmode 0), reactors, xdic, [links], layer, linetype, material, plotstyle, visual styles"""
    ver = rw.ver
    if d['entmode'] == 0: d['owner'] = rw.href(d.get('owner'), 4)
    d['reactors'] = [rw.href(x, 4) for x in (d.get('reactors') or [None] * d['nreactors'])]
    if ver == 'AC1015' or not d['xdic_missing']: d['xdic'] = rw.href(d.get('xdic', 0), 3)
    if ver == 'AC1015' and not d['xdic_missing']:
        d['prev'] = rw.href(d.get('prev'), 4); d['next'] = rw.href(d.get('next'), 4)
    d['layer'] = rw.href(d.get('layer'), 5)
    if d['ltflags'] == 3: d['ltype'] = rw.href(d.get('ltype'), 5)
    if ver in WIDE and d['matflags'] == 3: d['material'] = rw.href(d.get('material'), 5)
    if d['plotflags'] == 3: d['plotstyle'] = rw.href(d.get('plotstyle'), 5)
    if ver in R2010:
        if d['vs_full']: d['vs_full_h'] = rw.href(d.get('vs_full_h'), 5)
        if d['vs_face']: d['vs_face_h'] = rw.href(d.get('vs_face_h'), 5)
        if d['vs_edge']: d['vs_edge_h'] = rw.href(d.get('vs_edge_h'), 5)


def object_head(rw, d):
    """non-entity objects (tables, dictionaries...): EED, reactor count, xdic flag"""
    eed(rw, d)
    d['nreactors'] = rw.BL(d.get('nreactors', 0))
    if rw.ver != 'AC1015':
        d['xdic_missing'] = rw.B(d.get('xdic_missing', 1))
        if rw.ver in R2013: d['has_binary'] = rw.B(d.get('has_binary', 0))


def object_handles(rw, d):
    d['owner'] = rw.href(d.get('owner'), 4)
    d['reactors'] = [rw.href(x, 4) for x in (d.get('reactors') or [None] * d['nreactors'])]
    if rw.ver == 'AC1015' or not d.get('xdic_missing', 1):
        d['xdic'] = rw.href(d.get('xdic', 0), 3)


# ---------------------------------------------------------------- entity codecs
def c_line(rw, d):
    rd = rw.reading
    if rd:
        z0 = rw.B()
        x1 = rw.RD(); x2 = rw.DD(None, x1); y1 = rw.RD(); y2 = rw.DD(None, y1)
        z1 = z2 = 0.0
        if not z0: z1 = rw.RD(); z2 = rw.DD(None, z1)
        d['p1'] = (x1, y1, z1); d['p2'] = (x2, y2, z2)
    else:
        (x1, y1, z1), (x2, y2, z2) = d['p1'], d['p2']
        z0 = (z1 == 0.0 and z2 == 0.0)
        rw.B(z0); rw.RD(x1); rw.DD(x2, x1); rw.RD(y1); rw.DD(y2, y1)
        if not z0: rw.RD(z1); rw.DD(z2, z1)
    d['thickness'] = rw.BT(d.get('thickness', 0.0))
    d['ext'] = rw.BE(d.get('ext', (0.0, 0.0, 1.0)))


def c_circle(rw, d):
    d['center'] = rw.BD3(d.get('center')); d['radius'] = rw.BD(d.get('radius'))
    d['thickness'] = rw.BT(d.get('thickness', 0.0)); d['ext'] = rw.BE(d.get('ext', (0.0, 0.0, 1.0)))


def c_arc(rw, d):
    c_circle(rw, d)
    d['a0'] = rw.BD(d.get('a0')); d['a1'] = rw.BD(d.get('a1'))


def c_point(rw, d):
    d['p'] = rw.BD3(d.get('p')); d['thickness'] = rw.BT(d.get('thickness', 0.0)); d['ext'] = rw.BE(d.get('ext', (0.0, 0.0, 1.0)))
    d['xangle'] = rw.BD(d.get('xangle', 0.0))


ENT = {19: c_line, 18: c_circle, 17: c_arc, 27: c_point}
HND = {}          # type -> function(rw, d) reading/writing the entity specific handles (after the common handle head)


def register(otype, main, handles=None):
    ENT[otype] = main
    if handles: HND[otype] = handles


# ---------------------------------------------------------------- object level API
def decode_generic(o, codepage=30):
    """entity of a type without a codec: common head decoded, the type specific bits (incl. R2007+ string area) and handles kept verbatim"""
    rw = RW.for_read(o, codepage)
    d = {'type': o.type, 'handle': o.handle, 'generic': True}
    rw.m.H()
    entity_head(rw, d)
    p0 = rw.m.p
    d['rest'] = [B.Bits(o.raw, i).bit() for i in range(p0, o.handle_bit)]
    entity_handles(rw, d)
    d['_extra_h'] = []
    while rw.more_handles():
        d['_extra_h'].append(rw.h.H())
    d['_h'] = list(rw.hlist)
    return d


def encode_generic(ver, d, codepage=30):
    rw = RW.for_write(ver, d['handle'], codepage, d.get('_h'))
    rw.raw_tail = True
    rw.m.H(0, d['handle'])
    entity_head(rw, d)
    rw.m.bits.extend(d['rest'])
    entity_handles(rw, d)
    for c, v in d.get('_extra_h', []): rw.h.H(c, v)
    return finish(rw, d['type'], d['handle'])


CLASS_ENT = {}        # class name -> main codec of a class based entity (MULTILEADER ...); handles are kept verbatim (_extra_h)


def codec_key(o, cls=None):
    return cls if (o.type >= 500 and cls) else o.type


def decode(o, codepage=30, strict=True, cls=None):
    key = codec_key(o, cls)
    if key in OBJTYPES():
        d = TAB.decode(o, codepage, strict, key)
        d['key'] = key
        return d
    if o.type >= 500 and key in CLASS_ENT:
        rw = RW.for_read(o, codepage)
        d = {'type': o.type, 'handle': o.handle, 'key': key}
        rw.m.H(); entity_head(rw, d)
        CLASS_ENT[key](rw, d)
        if strict and rw.m.p != rw.main_end:
            raise ValueError('decoder ended at %d, expected %d' % (rw.m.p, rw.main_end))
        entity_handles(rw, d)
        d['_extra_h'] = []
        while rw.more_handles(): d['_extra_h'].append(rw.h.H())
        d['_h'] = list(rw.hlist)
        return d
    if o.type not in ENT: return decode_generic(o, codepage)
    """Decode a dwgload.Obj with a known entity codec -> dict (including '_h': stored handle codes for exact re-encoding)."""
    fn = ENT[o.type]
    rw = RW.for_read(o, codepage)
    d = {'type': o.type, 'handle': o.handle}
    rw.m.H()       # own handle
    entity_head(rw, d)
    fn(rw, d)
    if strict and rw.m.p != rw.main_end:
        raise ValueError('decoder ended at %d, expected %d' % (rw.m.p, rw.main_end))
    entity_handles(rw, d)
    if o.type in HND: HND[o.type](rw, d)
    d['_extra_h'] = []
    while rw.more_handles():
        d['_extra_h'].append(rw.h.H())
    d['_h'] = list(rw.hlist)
    if rw.nonul: d['_nonul'] = True
    return d


def encode(ver, d, codepage=30):
    if d.get('generic'): return encode_generic(ver, d, codepage)
    if d.get('key', d['type']) in OBJTYPES(): return TAB.encode(ver, d, codepage, d.get('key', d['type']))
    if d.get('key') in CLASS_ENT:
        rw = RW.for_write(ver, d['handle'], codepage, d.get('_h'))
        rw.m.H(0, d['handle']); entity_head(rw, d)
        CLASS_ENT[d['key']](rw, d)
        entity_handles(rw, d)
        for c, v in d.get('_extra_h', []): rw.h.H(c, v)
        return finish(rw, d['type'], d['handle'])
    rw = RW.for_write(ver, d['handle'], codepage, d.get('_h'))
    rw.nonul = d.get('_nonul', False)
    rw.m.H(0, d['handle'])
    entity_head(rw, d)
    ENT[d['type']](rw, d)
    entity_handles(rw, d)
    if d['type'] in HND: HND[d['type']](rw, d)
    for c, v in d.get('_extra_h', []): rw.h.H(c, v)
    return finish(rw, d['type'], d['handle'])

import dwgcodec_ent  # noqa: E402,F401  (registers the entity codecs)
import dwgcodec_tab as TAB  # noqa: E402


def OBJTYPES():
    return TAB.OBJ


def known(t, cls=None):
    return t in ENT or t in TAB.OBJ or (cls in TAB.OBJ or (t >= 500 and cls in CLASS_ENT) if cls else False)
