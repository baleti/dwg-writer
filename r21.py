"""AC1021 (R2007) container reader (experimental)."""
import struct
import lz21
import lz2007b


def system_header(buf):
    blk = buf[0x80:0x80 + 0x3d8]
    data = bytearray()
    for k in range(3):
        data += blk[k:0x2fd:3][:239]
    cl, _ = struct.unpack_from('<ii', data, 24)
    o, st = lz2007b.decompress(bytes(data[32:32 + cl]), 272)
    return struct.unpack_from('<34Q', o, 0)


def rs_data(buf, off, k, csz):
    raw = buf[off:off + 255 * k]
    d = bytearray()
    for j in range(k):
        d += raw[j::k][:239]
    return bytes(d[:csz])


def find_stream(buf, off, csz, usz, kmin=None, khint=None):
    """Find interleave factor k by trial (unknown rule for k): returns (k, plaintext)."""
    best = None
    ks = ([khint] if khint else []) + list(range(max(1, kmin or -(-csz // 239)), 700))
    for k in ks:
        try:
            o, st = lz2007b.decompress(rs_data(buf, off, k, csz), usz)
        except Exception:
            continue
        if st == 'done' and len(o) >= usz:
            if len(o) == usz: return k, o
            if best is None or len(o) < best[1]: best = (k, len(o), o[:usz])  # an overshooting parse is rarely right: keep the closest, prefer an exact size
    return (best[0], best[2]) if best else (None, None)


def page_map(buf, q):
    span = q[9] - q[7]  # the page map page is followed by the next system page: its size gives the interleave factor
    k, o = find_stream(buf, q[7] + 0x480, q[10], q[11], khint=span // 255 if 0 < span < 1 << 24 else None)
    if o is None:
        return None
    e = struct.unpack_from('<%dq' % (len(o) // 8), o, 0)
    pages = {}
    pos = 0x480
    for sz, i in zip(e[0::2], e[1::2]):
        if i > 0:
            pages[i] = (pos, sz)
        pos += sz
    return dict(k=k, pages=pages, entries=list(zip(e[0::2], e[1::2])))
