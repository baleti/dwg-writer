"""Version-independent loader: returns objects with raw bytes, type, handle and bit positions of data / handle streams.
Supports AC1015 and the R2004 family (AC1018/1024/1027/1032). AC1021 (R2007) not yet."""
import struct
import dwgfmt as F
import dwgbits as B
try:
    import os as _os
    if _os.environ.get('DWG_NO_FAST'): raise ImportError
    from dwgfast import split_objects as _split_native  # native fast path (dwgfast/)
except ImportError:
    _split_native = None
_VNUM = {'AC1018': 18, 'AC1021': 21, 'AC1024': 24, 'AC1027': 27, 'AC1032': 32}


class Obj:
    __slots__ = ('handle', 'type', 'raw', 'data_bit', 'handle_bit', 'ver', 'codepage')

    def __repr__(self):
        return 'Obj(%d type=%d len=%d)' % (self.handle, self.type, len(self.raw))


def _split_r2010(buf, off):
    r = B.Bits(buf, off * 8)
    sz = r.bits(8) | (r.bits(8) << 8)
    n = 2
    if sz & 0x8000:
        sz = (sz & 0x7FFF) | ((r.bits(8) | (r.bits(8) << 8)) << 15)
        n = 4
    v = sh = 0
    nmc = 0
    while True:
        c = r.bits(8); v |= (c & 0x7F) << sh; sh += 7; nmc += 1
        if not c & 0x80: break
    return r, sz, n, (v, nmc)


def section(buf, info, name):
    """Decompressed section bytes of an R2004-family or AC1021 file (info from F.r2004_open / dwgr21.open_r21)."""
    if info.get('kind') == 'r21':
        import dwgr21
        return dwgr21.section_data(buf, info, name)[0]
    return F.r2004_section_data(buf, info, name)


def load(buf):
    ver = bytes(buf[:6]).decode('latin1')
    if ver == 'AC1015':
        import dwgobj as O
        d = O.load_r2000(buf)
        objs = {}
        for h, oo in d['objects'].items():
            o = Obj(); o.handle = h; o.ver = ver; o.raw = oo.raw; o.type = oo.type
            hdr = 32 if (o.raw[0] | (o.raw[1] << 8)) & 0x8000 else 16
            r = B.Bits(o.raw, hdr); r.BS(); r.RL()
            o.data_bit = r.p
            o.handle_bit = hdr + oo.bitsize
            objs[h] = o
        return dict(version=ver, objects=objs, omap_ok=d['omap_ok'])
    if ver not in ('AC1018', 'AC1021', 'AC1024', 'AC1027', 'AC1032'):
        raise NotImplementedError(ver)
    if ver == 'AC1021':
        import dwgr21
        info = dwgr21.open_r21(buf)
    else:
        info = F.r2004_open(buf)
    hs = section(buf, info, 'AcDb:Handles')
    od = section(buf, info, 'AcDb:AcDbObjects')
    omap, ok = F.object_map_r13_r2000(hs, (0, 0, len(hs)))
    objs = {}
    if _split_native is not None:
        hl = list(omap)
        for h, (s_, e_, t_, db_, hb_) in zip(hl, _split_native(od, [omap[h] for h in hl], _VNUM[ver])):
            o = Obj(); o.handle = h; o.ver = ver; o.raw = bytes(od[s_:e_]); o.type = t_; o.data_bit = db_; o.handle_bit = hb_
            objs[h] = o
        return dict(version=ver, objects=objs, info=info, omap_ok=ok)
    for h, off in omap.items():
        o = Obj(); o.handle = h; o.ver = ver
        if ver in ('AC1018', 'AC1021'):
            w1 = od[off] | (od[off + 1] << 8)
            if w1 & 0x8000:  # MS: second word holds the high bits of the size
                sz = (w1 & 0x7FFF) | ((od[off + 2] | (od[off + 3] << 8)) << 15); hdr = 32
            else:
                sz = w1; hdr = 16
            o.raw = bytes(od[off:off + sz + hdr // 8 + 2])
            r = B.Bits(o.raw, hdr)
            o.type = r.BS(); bitsize = r.RL()
            o.data_bit = r.p
            o.handle_bit = hdr + bitsize
        else:
            r, sz, n, (hsize, nmc) = _split_r2010(od, off)
            end = off + n + nmc + sz  # EXP: the size field counts the bytes after the MC; CRC16 (seed 0xC0C1 over everything before it) follows
            o.raw = bytes(od[off:end + 2])
            r = B.Bits(o.raw, 0)
            r2, _, n2, _hs = _split_r2010(o.raw, 0)
            oc = r2.BB()
            o.type = r2.RC() if oc == 0 else (r2.RC() + 0x1F0 if oc == 1 else r2.RS())
            o.data_bit = r2.p
            o.handle_bit = (n + nmc + sz) * 8 - hsize
        objs[h] = o
    return dict(version=ver, objects=objs, info=info, omap_ok=ok)


if __name__ == '__main__':
    import sys, collections
    for p in sys.argv[1:]:
        d = load(open(p, 'rb').read())
        c = collections.Counter(o.type for o in d['objects'].values())
        print(p, d['version'], len(d['objects']), c.most_common(8))
