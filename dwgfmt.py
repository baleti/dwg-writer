"""DWG container reader. Own code; layout found by experiment + general knowledge of public format descriptions (see NOTES.md)."""
import struct

VERSIONS = {b'AC1009': 'R11/12', b'AC1012': 'R13', b'AC1014': 'R14', b'AC1015': 'R2000',
            b'AC1018': 'R2004', b'AC1021': 'R2007', b'AC1024': 'R2010', b'AC1027': 'R2013', b'AC1032': 'R2018'}

# section start sentinels (found by experiment in corpus AC1015 files); end sentinel = bitwise complement of start
SENT_START = {0: bytes.fromhex('cf7b1f23fdde38a95f7c68b84e6d335f'),
              1: bytes.fromhex('8da1c4b8c4a9f8c5c0dcf45fe7cfb68a')}


_T = []
for _i in range(256):
    _c = _i
    for _ in range(8):
        _c = (_c >> 1) ^ 0xA001 if _c & 1 else _c >> 1
    _T.append(_c)


def crc16(data, seed=0):
    """Reflected CRC-16 poly 0xA001 (found by experiment: matches section CRCs with seed 0xC0C1 over size+data)."""
    for x in data:
        seed = (seed >> 8) ^ _T[(seed ^ x) & 255]
    return seed


def read_r13_r2000(buf):
    ver = bytes(buf[:6])
    maint, = struct.unpack_from('<B', buf, 0x0B)
    image_seeker, = struct.unpack_from('<I', buf, 0x0D)
    codepage, = struct.unpack_from('<H', buf, 0x13)
    n, = struct.unpack_from('<I', buf, 0x15)
    recs = []
    for i in range(n):
        num, seek, size = struct.unpack_from('<BII', buf, 0x19 + 9 * i)
        recs.append((num, seek, size))
    return dict(version=ver, maint=maint, image_seeker=image_seeker, codepage=codepage, locators=recs)


def section_r13_r2000(buf, loc):
    """Locators 0 (header vars) and 1 (classes): sentinel, RL size, data, RS crc, complement sentinel. Returns (data, crc_ok, sent_ok)."""
    _, seek, size = loc
    sz, = struct.unpack_from('<I', buf, seek + 16)
    data = bytes(buf[seek + 20:seek + 20 + sz])
    crc, = struct.unpack_from('<H', buf, seek + 20 + sz)
    end = bytes(buf[seek + 22 + sz:seek + 38 + sz])
    sent_ok = bytes(x ^ 0xFF for x in buf[seek:seek + 16]) == end
    return data, crc16(buf[seek + 16:seek + 20 + sz], 0xC0C1) == crc, sent_ok


def object_map_r13_r2000(buf, loc, reset_h=True, reset_o=True):
    """Locator 2. Chunks: RS size (big-endian, includes the 2 size bytes), then pairs of modular numbers
    (handle delta unsigned, file offset delta signed), then RS crc (big-endian, seed 0xC0C1 over size+pairs).
    Chunk of size 2 ends the map. Returns ({handle: offset}, all_crc_ok). [layout GEN, verified EXP]"""
    _, seek, size = loc
    pos, end = seek, seek + size
    out, ok = {}, True
    handle = off = 0
    while pos + 2 <= end:
        n = (buf[pos] << 8) | buf[pos + 1]
        if n <= 2:
            break
        p, stop = pos + 2, pos + n
        if reset_h: handle = 0
        if reset_o: off = 0
        while p < stop:
            v = 0; sh = 0
            while True:
                c = buf[p]; p += 1
                v |= (c & 0x7F) << sh; sh += 7
                if not c & 0x80: break
            handle += v
            v = 0; sh = 0
            while True:
                c = buf[p]; p += 1
                if not c & 0x80:
                    v |= (c & 0x3F) << sh
                    if c & 0x40: v = -v
                    break
                v |= (c & 0x7F) << sh; sh += 7
            off += v
            out[handle] = off
        crc = (buf[stop] << 8) | buf[stop + 1]
        ok &= crc16(buf[pos:stop], 0xC0C1) == crc
        pos = stop + 2
    return out, ok


if __name__ == '__main__':
    import sys
    for p in sys.argv[1:]:
        b = open(p, 'rb').read()
        v = bytes(b[:6])
        if v in (b'AC1012', b'AC1014', b'AC1015'):
            h = read_r13_r2000(b)
            print(p, VERSIONS[v], h)
            for num, seek, size in h['locators']:
                print(' ', num, hex(seek), size, b[seek:seek + 16].hex(), b[seek + size - 16:seek + size].hex() if seek + size <= len(b) else 'OOR')


# ---- R2004 family (AC1018, AC1024, AC1027, AC1032) ----
def r2004_decrypt_header(buf):
    """The 0x6C-byte block at 0x80 is XORed with a linear congruential byte stream (seed 1, mult 0x343FD, add 0x269EC3, byte = state>>16). [GEN, verified: decrypts to 'AcFssFcAJMB']"""
    s = 1
    out = bytearray()
    for i in range(0x6C):
        s = (s * 0x343FD + 0x269EC3) & 0xFFFFFFFF
        out.append(buf[0x80 + i] ^ ((s >> 16) & 0xFF))
    return bytes(out)


def _lz77_decompress_py(src, out_size):
    """DWG R2004 LZ77-style decompressor. Written from the opcode semantics as understood from public format descriptions; verified by output size and CRC/structure checks (NOTES.md)."""
    out = bytearray()
    i = 0

    def rlong():
        nonlocal i
        t = 0
        while src[i] == 0:
            t += 0xFF
            i += 1
        t += src[i]
        i += 1
        return t

    def lit_run(op):
        nonlocal i
        n = op & 0x0F
        n = (0x0F + rlong() if n == 0 else n) + 3
        out.extend(src[i:i + n])
        i += n

    op = src[i]; i += 1
    if op & 0xF0 == 0:
        lit_run(op)
        op = src[i]; i += 1
    while op != 0x11 and len(out) < out_size:
        if op >= 0x40:
            cb = ((op >> 4) & 0xF) - 1
            b2 = src[i]; i += 1
            off = (((op >> 2) & 3) | (b2 << 2)) + 1
            ln = op & 3
        elif op >= 0x21:
            cb = (op & 0x1F) + 2
            b1 = src[i]; b2 = src[i + 1]; i += 2
            off = ((b1 >> 2) | (b2 << 6)) + 1
            ln = b1 & 3
        elif op == 0x20:
            cb = rlong() + 0x1F + 2
            b1 = src[i]; b2 = src[i + 1]; i += 2
            off = ((b1 >> 2) | (b2 << 6)) + 1
            ln = b1 & 3
        elif op >= 0x10:  # far match: bit 3 of the opcode adds another 0x4000 to the offset (needed for pages whose output exceeds 32 KB)
            cb = (op & 7) + 2 if op & 7 else rlong() + 9
            b1 = src[i]; b2 = src[i + 1]; i += 2
            off = ((b1 >> 2) | (b2 << 6)) + 0x4000 + ((op & 8) << 11)
            ln = b1 & 3
        else:
            raise ValueError('bad opcode %#x at %d' % (op, i - 1))
        if off > len(out):
            raise ValueError('lz77 bad offset op=%#x i=%d out=%d off=%d cb=%d ln=%d' % (op, i, len(out), off, cb, ln))
        for _ in range(cb):
            out.append(out[-off])
        if ln:
            out.extend(src[i:i + ln]); i += ln
            op = src[i]; i += 1
        else:
            op = src[i]; i += 1
            if op & 0xF0 == 0:
                lit_run(op)
                op = src[i]; i += 1
    _lz77_decompress_py.last_i = i
    return bytes(out)


try:
    import os
    if os.environ.get('DWG_NO_FAST'): raise ImportError
    from dwgfast import lz77_decompress as _lz77_fast  # native fast path (dwgfast/), bit-identical to the Python reference

    def lz77_decompress(src, out_size):
        out, i = _lz77_fast(src, out_size)
        lz77_decompress.last_i = i
        return out
except ImportError:
    lz77_decompress = _lz77_decompress_py


def r2004_system_page(buf, addr):
    t, ds, cs, ct, sc = struct.unpack_from('<IIIII', buf, addr)
    if t not in (0x41630e3b, 0x4163003b):
        raise ValueError('bad system page type %#x at %#x' % (t, addr))
    data = bytes(buf[addr + 20:addr + 20 + cs])
    return lz77_decompress(data, ds) if ct == 2 else data


def r2004_open(buf):
    """Returns dict(pages={id: (addr, size)}, sections={name: dict(size, maxpage, compressed, id, encrypted, pages=[(num, size, start)])})."""
    h = r2004_decrypt_header(buf)
    pm_addr = struct.unpack_from('<q', h, 0x54)[0] + 0x100
    sm_id, = struct.unpack_from('<I', h, 0x5C)
    pm = r2004_system_page(buf, pm_addr)
    pages = {}
    p, addr = 0, 0x100
    while p + 8 <= len(pm):
        num, size = struct.unpack_from('<ii', pm, p)
        p += 8
        if num > 0:
            pages[num] = (addr, size)
        else:
            p += 16
        addr += size
    sa, ss = pages[sm_id]
    sm = r2004_system_page(buf, sa)
    ndesc, = struct.unpack_from('<I', sm, 0)
    p = 20
    sections = {}
    for _ in range(ndesc):
        size, npg, maxd, _u, comp, sid, enc = struct.unpack_from('<QIIIIII', sm, p)
        name = sm[p + 32:p + 96].split(b'\0')[0].decode('latin1')
        p += 96
        pl = []
        for _ in range(npg):
            num, psz, start = struct.unpack_from('<IIQ', sm, p)
            p += 16
            pl.append((num, psz, start))
        sections[name] = dict(size=size, maxpage=maxd, compressed=comp, id=sid, encrypted=enc, pages=pl)
    return dict(header=h, pages=pages, sections=sections)


def r2004_section_data(buf, info, name):
    """Assemble a named section: for each page the 32-byte header is XORed with 0x4164536B ^ page address; data decompressed when compressed==2."""
    sec = info['sections'][name]
    out = bytearray()
    for num, psz, start in sec['pages']:
        addr, _ = info['pages'][num]
        mask = 0x4164536B ^ addr
        hdr = struct.unpack_from('<8I', buf, addr)
        t, sn, cs, ds, off, sc, dc, _u = (x ^ mask for x in hdr)
        if t != 0x4163043B:
            raise ValueError('bad data page type %#x in %s' % (t, name))
        raw = bytes(buf[addr + 32:addr + 32 + cs])
        page = lz77_decompress(raw, sec["maxpage"]) if sec["compressed"] == 2 else raw
        if len(out) < start:
            out.extend(b'\0' * (start - len(out)))
        out[start:start + len(page)] = page
    return bytes(out[:sec['size']]) if sec['size'] else bytes(out)
