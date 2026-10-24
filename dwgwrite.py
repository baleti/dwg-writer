"""R2004-family container writer (AC1018/1024/1027/1032 layout, used here to re-emit a file from section plaintext).
Compression is literal-only (valid R2004 LZ stream). Checksum recipes found by experiment (NOTES.md)."""
import struct, zlib
import dwgfmt as F

M = 65521


def adler(data, seed=0):
    a = seed & 0xFFFF
    b = (seed >> 16) & 0xFFFF
    for x in data:
        a += x
        if a >= M: a -= M
        b += a
        if b >= M: b -= M
    return (b << 16) | a


def lz77_literal(data):
    """Valid R2004 stream consisting of one literal run followed by the 0x11 terminator."""
    n = len(data)
    L = n - 3
    out = bytearray()
    if 1 <= L <= 15:
        out.append(L)
    else:
        out.append(0)
        v = L - 15
        z = (v - 1) // 255
        out.extend(b'\0' * z)
        out.append(v - 255 * z)
    out.extend(data)
    out.extend(b'\x11\0\0')
    return bytes(out)


def _rlong(t):
    z = (t - 1) // 255
    return b'\0' * z + bytes([t - 255 * z])


def _lit_run(lits):
    n = len(lits)
    if 4 <= n <= 18:
        return bytes([n - 3]) + lits
    return b'\0' + _rlong(n - 18) + lits


def _match(cb, off, ln):
    if off <= 1024 and 3 <= cb <= 14:
        return bytes([((cb + 1) << 4) | (((off - 1) & 3) << 2) | ln, (off - 1) >> 2])
    if off <= 16384:
        v = off - 1
        tail = bytes([((v & 0x3F) << 2) | ln, v >> 6])
        return (bytes([0x20 | (cb - 2)]) if cb <= 33 else b'\x20' + _rlong(cb - 33)) + tail
    v = off - 0x4000
    tail = bytes([((v & 0x3F) << 2) | ln, v >> 6])
    return (bytes([0x10 | (cb - 2)]) if cb <= 17 else b'\x10' + _rlong(cb - 9)) + tail


def lz77_compress(data, chain=24, maxlen=0x7FFF, maxoff=16384, minlen=4):
    """Valid R2004 LZ stream: greedy hash-chain matcher (>= 4 byte matches, offsets <= 16384 (AutoCAD rejects streams using the 0x10/0x12 long-offset forms, found by experiment))."""
    n = len(data)
    if n < 4:
        raise ValueError('section too short to compress')
    out = bytearray()
    heads = {}
    i = 0
    lit0 = 0           # start of pending literals
    first = True
    pend = None        # (cb, off) awaiting its trailing literal count
    def flush_lits(upto):
        nonlocal first, pend
        lits = data[lit0:upto]
        if pend is not None:
            cb, off = pend; pend = None
            k = len(lits)
            if k <= 3:
                out.extend(_match(cb, off, k)); out.extend(lits)
                return
            out.extend(_match(cb, off, 0))
        if lits:
            out.extend(_lit_run(bytes(lits)))
    while i < n:
        best_l = 0; best_o = 0
        if i + 4 <= n:
            key = data[i:i + 4]
            cand = heads.get(key)
            if cand:
                for j in reversed(cand[-chain:]):
                    off = i - j
                    if off > maxoff: break
                    l = minlen
                    while i + l < n and data[j + l] == data[i + l] and l < maxlen: l += 1
                    if l > best_l or (l == best_l and off < best_o):
                        best_l, best_o = l, off
                        if l >= 258: break
        if best_l >= minlen and first and i - lit0 < 4:
            best_l = 0   # a stream begins with a literal run of >= 4 bytes
        if best_l >= minlen:
            flush_lits(i); first = False
            pend = (best_l, best_o)
            for k in range(i, min(i + best_l, n - 3)):
                heads.setdefault(data[k:k + 4], []).append(k)
            i += best_l; lit0 = i
        else:
            if i + 4 <= n: heads.setdefault(data[i:i + 4], []).append(i)
            i += 1
    flush_lits(n)
    out.extend(b'\x11\0\0')   # terminator; AutoCAD's own streams carry two zero bytes after it
    return bytes(out)


def align(n, a):
    return (n + a - 1) // a * a


def enc_header(h):
    s = 1
    out = bytearray()
    for i in range(0x6C):
        s = (s * 0x343FD + 0x269EC3) & 0xFFFFFFFF
        out.append(h[i] ^ ((s >> 16) & 0xFF))
    return bytes(out)


def sys_page(ptype, plain):
    comp = lz77_compress(plain)
    hdr = struct.pack('<IIIII', ptype, len(plain), len(comp), 2, 0)
    sc = adler(comp, adler(hdr, 0))
    hdr = struct.pack('<IIIII', ptype, len(plain), len(comp), 2, sc)
    return hdr + comp


def data_page(secnum, start, payload, addr):
    """payload = compressed (or raw) bytes; returns bytes padded to 0x20."""
    total = align(32 + len(payload), 0x20)
    f = [0x4163043B, secnum, len(payload), total, start, 0, 0, adler(payload, 0)]
    dec = bytearray(struct.pack('<8I', *f))
    f[6] = adler(bytes(dec), f[7])  # header checksum computed with field 6 == 0
    mask = 0x4164536B ^ addr
    hdr = struct.pack('<8I', *[x ^ mask for x in f])
    return (hdr + payload).ljust(total, b'\0')


def _fix_preview(data, old_base, new_base, hdr_extra=0):
    """The preview header stores absolute file offsets of its images: shift them by (new_base - old_base)."""
    d = bytearray(data)
    cnt = d[20]
    p = 21
    for _ in range(cnt):
        start, = struct.unpack_from('<I', d, p + 1)
        struct.pack_into('<I', d, p + 1, start - old_base + new_base)
        p += 9
    return bytes(d)


def rewrite_r2004(buf, plain=None, sm_size=None, pm_size_over=None):
    info = F.r2004_open(buf)
    plain = dict(plain or {})
    secs = info['sections']
    hdr0 = F.r2004_decrypt_header(buf)
    sm_id0, pm_id0 = struct.unpack_from('<I', hdr0, 0x5C)[0], struct.unpack_from('<I', hdr0, 0x50)[0]
    out = bytearray(buf[:0x100])  # file header and (to be replaced) encrypted header block
    smap = []   # section descriptors with pages
    todo = []   # (orig page id or None, section name, start, payload)
    for name, s in secs.items():
        data = plain.get(name)
        if data is None and not s['pages']:
            # section without pages in the original (AutoCAD writes e.g. AcDb:Template this way): keep it page-less
            smap.append(dict(name=name, size=s['size'], maxpage=s['maxpage'], compressed=s['compressed'], id=s['id'], encrypted=s['encrypted'], pages=[]))
            continue
        if data is None:
            data = F.r2004_section_data(buf, info, name) if s['size'] else b''
        desc = dict(name=name, size=len(data), maxpage=s['maxpage'], compressed=s['compressed'], id=s['id'], encrypted=s['encrypted'], pages=[])
        smap.append(desc)
        if name == '':
            continue
        if s['compressed'] == 1:
            # uncompressed section: one page holding the data padded to its max page size (multiple of 128)
            mp = s['maxpage'] if len(data) <= s['maxpage'] else align(len(data), 128)
            desc['maxpage'] = mp
            chunks = [(0, data.ljust(mp, b'\0'))]
        else:
            mp = s['maxpage']
            chunks = []
            for st in range(0, max(len(data), 1), mp):
                part = data[st:st + mp].ljust(mp, b'\0')   # AutoCAD pages always decompress to the full page size
                chunks.append((st, lz77_compress(part) if len(part) >= 4 else lz77_literal(part)))
        for k, (st, payload) in enumerate(chunks):
            oid = s['pages'][k][0] if k < len(s['pages']) else None
            todo.append([oid, name, st, payload, desc])
    used = {t[0] for t in todo if t[0] is not None} | {sm_id0, pm_id0}
    nxt = max(used) + 1
    for t in todo:
        if t[0] is None:
            t[0] = nxt; nxt += 1
    todo.sort(key=lambda t: t[0])
    gseq = _orig_page_sequence(buf)
    if any(e[0] == 'g' for e in gseq):
        return _rewrite_r2004_gaps(buf, info, secs, smap, todo, gseq, sm_id0, pm_id0, out)
    pages = []  # (id, size)
    addr = 0x100
    for pid, name, st, payload, desc in todo:
        if name == 'AcDb:Preview' and st == 0 and len(payload) > 30:
            payload = bytearray(payload)
            payload[:] = _fix_preview(bytes(payload), struct.unpack_from('<I', buf, 0x0D)[0], addr + 32, 32)
            struct.pack_into('<I', out, 0x0D, addr + 32)  # image seeker points at the preview data
        page = data_page(secs[name]['id'], st, bytes(payload), addr)
        out.extend(page)
        pages.append((pid, len(page)))
        desc['pages'].append((pid, len(payload), st))
        addr += len(page)
    sm_id, pm_id = sm_id0, pm_id0
    top = max(p for p, _ in pages) if pages else 0
    if sm_id <= top or pm_id <= top or sm_id == pm_id:     # the system pages carry the largest page ids
        sm_id, pm_id = top + 1, top + 2
    # section map plaintext
    sm = bytearray(struct.pack('<IIIII', len(smap), 2, 0x7400, 0, len(smap)))
    for d in smap:
        nm = d['name'].encode('latin1')[:63].ljust(64, b'\0')
        sm += struct.pack('<QIIIIII', d['size'], len(d['pages']), d['maxpage'], 1, d['compressed'], d['id'], d['encrypted']) + nm
        for num, psz, st in d['pages']:
            sm += struct.pack('<IIQ', num, psz, st)
    sm_page = sys_page(0x4163003B, bytes(sm))
    sm_addr = addr
    sm_on_disk = sm_size or align(len(sm_page), 0x20)
    out.extend(sm_page.ljust(sm_on_disk, b'\0'))
    pages.append((sm_id, sm_on_disk)); addr += sm_on_disk
    # page map: includes itself
    pm_addr = addr
    def pm_plain(pm_size):
        e = list(pages) + [(pm_id, pm_size)]
        return b''.join(struct.pack('<ii', i, s) for i, s in e)
    # size of the page-map page depends on its own listing only through the (fixed width) entry
    pm_page = sys_page(0x41630E3B, pm_plain(0))
    pm_size = pm_size_over or align(len(pm_page) + 20 + 0x6C, 0x20)  # the listed size also covers the trailing second header
    pm_page = sys_page(0x41630E3B, pm_plain(pm_size))
    out.extend(pm_page)
    addr += len(pm_page)
    end_alloc = pm_addr + pm_size
    # second header: 20-byte system header + copy of the encrypted block, placed at the very end
    h = bytearray(F.r2004_decrypt_header(buf))
    struct.pack_into('<I', h, 0x28, pm_id)                       # last section page id
    struct.pack_into('<q', h, 0x2C, end_alloc - 0x100)            # last section page end address (relative)
    sh_addr = addr + 20
    struct.pack_into('<q', h, 0x34, sh_addr)                     # second header address (absolute)
    struct.pack_into('<I', h, 0x40, len(pages) + 1)              # number of page map entries (incl. system pages)
    struct.pack_into('<I', h, 0x50, pm_id)
    struct.pack_into('<q', h, 0x54, pm_addr - 0x100)
    struct.pack_into('<I', h, 0x5C, sm_id)
    struct.pack_into('<I', h, 0x60, pm_id)
    struct.pack_into('<I', h, 0x64, 0)
    for off in (0x18, 0x1C, 0x20): struct.pack_into('<I', h, off, 0)     # gap tree (root and lowest/highest gap ids): the rewrite lists no gap pages
    struct.pack_into('<I', h, 0x68, 0)
    struct.pack_into('<I', h, 0x68, zlib.crc32(bytes(h)) & 0xFFFFFFFF)
    out[0x80:0xEC] = enc_header(bytes(h))
    out.extend(struct.pack('<IIIII', 0x41630E3B, 0, 0, 2, 0))
    out.extend(enc_header(bytes(h)))
    return bytes(out)


def _orig_page_sequence(buf):
    """page map of the original in file order: ('p', id, size) for pages, ('g', num, size, extra16) for gap entries (free regions)"""
    h = F.r2004_decrypt_header(buf)
    pm = F.r2004_system_page(buf, struct.unpack_from('<q', h, 0x54)[0] + 0x100)
    seq = []; p = 0
    while p + 8 <= len(pm):
        num, size = struct.unpack_from('<ii', pm, p); p += 8
        if num > 0: seq.append(('p', num, size))
        else: seq.append(('g', num, size, bytes(pm[p:p + 16]))); p += 16
    return seq


def _rewrite_r2004_gaps(buf, info, secs, smap, todo, gseq, sm_id0, pm_id0, out):
    """rewrite of a file whose page map carries gap (free space) entries: pages keep their original order and ids, the gap regions stay
    (zero filled, entries copied verbatim so the gap tree in the file header stays valid), the section and page map pages stay where they were."""
    payload_of = {t[0]: t for t in todo}                      # page id -> [id, name, start, payload, desc]
    # sizes first (addresses only feed the page header mask)
    own = {}
    for pid, t in payload_of.items():
        own[pid] = align(32 + len(t[3]), 0x20)
    for t in todo:
        t[4]['pages'].append((t[0], len(t[3]), t[2]))
    sm = bytearray(struct.pack('<IIIII', len(smap), 2, 0x7400, 0, len(smap)))
    for d in smap:
        nm = d['name'].encode('latin1')[:63].ljust(64, b'\0')
        sm += struct.pack('<QIIIIII', d['size'], len(d['pages']), d['maxpage'], 1, d['compressed'], d['id'], d['encrypted']) + nm
        for num, psz, st in sorted(d['pages'], key=lambda x: x[2]):
            sm += struct.pack('<IIQ', num, psz, st)
    sm_page = sys_page(0x4163003B, bytes(sm)); sm_size = align(len(sm_page), 0x20)
    seq = [e for e in gseq if e[0] == 'g' or e[1] in payload_of or e[1] in (sm_id0, pm_id0)]
    placed = {e[1] for e in seq if e[0] == 'p'}
    extra = [pid for pid in sorted(payload_of) if pid not in placed]
    last_extra = [('p', pid, 0) for pid in extra]
    seq = seq + last_extra
    sizes = {}
    for e in seq:
        if e[0] == 'p':
            sizes[e[1]] = sm_size if e[1] == sm_id0 else (None if e[1] == pm_id0 else own[e[1]])
    def pm_plain(pm_size, tail_extra):
        buf2 = b''
        last_real = [e for e in seq if e[0] == 'p'][-1][1]
        for e in seq:
            if e[0] == 'g': buf2 += struct.pack('<ii', e[1], e[2]) + e[3]
            else:
                sz = pm_size if e[1] == pm_id0 else sizes[e[1]]
                if e[1] == last_real: sz += tail_extra
                buf2 += struct.pack('<ii', e[1], sz)
        return buf2
    tail = align(20 + 0x6C, 0x20)
    pm_page = sys_page(0x41630E3B, pm_plain(0, tail)); pm_size = align(len(pm_page) + 32, 0x20)
    pm_page = sys_page(0x41630E3B, pm_plain(pm_size, tail))
    assert len(pm_page) <= pm_size
    sizes[pm_id0] = pm_size
    out = bytearray(out)
    addr = 0x100; pm_addr = sm_addr = None; last_real = None; last_end = None
    for e in seq:
        if e[0] == 'g':
            out.extend(b'\0' * e[2]); addr += e[2]; continue
        pid = e[1]
        if pid == sm_id0:
            out.extend(sm_page.ljust(sm_size, b'\0')); sm_addr = addr
        elif pid == pm_id0:
            out.extend(pm_page.ljust(pm_size, b'\0')); pm_addr = addr
        else:
            _, name, st, payload, desc = payload_of[pid]
            if name == 'AcDb:Preview' and st == 0 and len(payload) > 30:
                payload = bytearray(payload)
                payload[:] = _fix_preview(bytes(payload), struct.unpack_from('<I', buf, 0x0D)[0], addr + 32, 32)
                struct.pack_into('<I', out, 0x0D, addr + 32)
            out.extend(data_page(secs[name]['id'], st, bytes(payload), addr))
        addr += sizes[pid]; last_real = pid; last_end = addr
    # the last page's listed size also covers the trailing second header
    end_alloc = last_end + tail
    h = bytearray(F.r2004_decrypt_header(buf))
    struct.pack_into('<I', h, 0x28, last_real)
    struct.pack_into('<q', h, 0x2C, end_alloc - 0x100)
    sh_addr = last_end + 20
    struct.pack_into('<q', h, 0x34, sh_addr)
    struct.pack_into('<I', h, 0x40, sum(1 for e in seq if e[0] == 'p'))
    struct.pack_into('<q', h, 0x54, pm_addr - 0x100)
    struct.pack_into('<I', h, 0x68, 0)
    struct.pack_into('<I', h, 0x68, zlib.crc32(bytes(h)) & 0xFFFFFFFF)
    out[0x80:0xEC] = enc_header(bytes(h))
    out.extend(struct.pack('<IIIII', 0x41630E3B, 0, 0, 2, 0))
    out.extend(enc_header(bytes(h)))
    return bytes(out)


def rewrite_r2000(buf, raws_in_order, header_sec=None, handles_fn=None):
    """Re-emit an AC1015 file. raws_in_order: [(handle, raw bytes)] in the order they are to be written; header_sec: replacement for the
    header-variables section bytes (sentinel .. sentinel) or None; handles_fn(omap)->bytes builds the object map section."""
    import dwgedit
    h = F.read_r13_r2000(buf)
    loc = {n: (s, z) for n, s, z in h['locators']}
    out = bytearray(buf[:0x61])
    out += buf[0x61:0x61 + loc[5][1]]                       # locator 5: 123-byte aux block
    preview_start = 0x61 + loc[5][1]
    out += buf[preview_start:loc[0][0]]                     # preview image (image seeker target)
    s0 = header_sec if header_sec is not None else bytes(buf[loc[0][0]:loc[0][0] + loc[0][1]])
    new0 = (len(out), len(s0)); out += s0
    s1 = bytes(buf[loc[1][0]:loc[1][0] + loc[1][1]])
    new1 = (len(out), len(s1)); out += s1
    # 4 byte object stream marker between classes and the first object
    out += buf[loc[1][0] + loc[1][1]:loc[1][0] + loc[1][1] + 4]
    omap = {}
    for hnd, raw in raws_in_order:
        omap[hnd] = len(out)
        out += raw
    om = handles_fn(omap)
    new2 = (len(out), len(om)); out += om
    tail4 = loc[4][0] >= loc[2][0]                         # locator 4 normally is the 4 byte trailer; in some files it points at the marker after the classes
    gap_old = bytes(buf[loc[2][0] + loc[2][1]:loc[4][0] if tail4 else len(buf)])
    sent = bytes.fromhex('d47b21ce28939fbf53244009123caa01')
    k = gap_old.find(sent)                                   # some files carry a short block (locator 3) in front of the second header
    if k < 0 or k > 256 or len(gap_old) - k < 130:
        raise NotImplementedError('unexpected layout after the object map (no second header)')
    gap_start = len(out)
    gap = bytearray(gap_old)
    new4 = (gap_start + len(gap), 4) if tail4 else (new1[0] + new1[1], 4)
    # second header: bit stream whose locator fields are BL (2 bit code: 00 = 32 bit value, 01 = 8 bit value, 10 = zero), so a
    # changed value can change the field width; the header is re-packed and its size field and CRC recomputed
    hb = bytes(gap[k:])
    bitsarr = [(hb[i >> 3] >> (7 - (i & 7))) & 1 for i in range(len(hb) * 8)]

    def rd_bl(p):
        c = bitsarr[p] * 2 + bitsarr[p + 1]; p += 2
        if c == 0: w = 32
        elif c == 1: w = 8
        elif c == 2: return 0, p
        else: raise NotImplementedError('second header: BL code 3')
        v = 0
        for j in range(w):
            v |= bitsarr[p + j] << (8 * (j // 8) + 7 - (j % 8))
        return v, p + w

    def enc_bl(v):
        if v == 0: return [1, 0]
        if v < 256: bits = [0, 1]; w = 8
        else: bits = [0, 0]; w = 32
        for j in range(w):
            bits.append(((v >> (8 * (j // 8))) >> (7 - (j % 8))) & 1)
        return bits

    size_field = struct.unpack_from('<I', hb, 16)[0]
    crcpos = 6 + size_field
    newvals = {160: gap_start + k}
    starts = [160]; p = 350
    for i, v in enumerate((new0[0], new0[1], new1[0], new1[1], new2[0], new2[1])):
        newvals[p] = v; starts.append(p); _, p = rd_bl(p)
        if i % 2: p += 8                                     # RC locator number in front of each (seeker, size) pair
    pay = bitsarr[:crcpos * 8]
    pieces = []; last = 0
    for st in starts:
        _, en = rd_bl(st)
        pieces += pay[last:st] + enc_bl(newvals[st]); last = en
    pieces += pay[last:]
    while len(pieces) % 8: pieces.append(0)
    nb = bytearray(len(pieces) // 8)
    for i, bt in enumerate(pieces):
        if bt: nb[i >> 3] |= 0x80 >> (i & 7)
    delta = len(nb) - crcpos
    struct.pack_into('<I', nb, 16, size_field + delta)
    ncrc = len(nb)
    nb += struct.pack('<H', F.crc16(bytes(nb[16:ncrc]), 0xC0C1))
    g2 = bytes(gap[:k]) + bytes(nb) + hb[crcpos + 2:]
    gap_len = len(g2)
    new4 = (gap_start + gap_len, 4) if tail4 else (new1[0] + new1[1], 4)
    out += g2
    if tail4: out += buf[loc[4][0]:loc[4][0] + 4]
    # locator table
    n = struct.unpack_from('<I', buf, 0x15)[0]
    recs = {0: new0, 1: new1, 2: new2, 3: ((gap_start, loc[3][1]) if k and loc[3][1] else (0, 0)), 4: new4, 5: loc[5]}
    for i in range(n):
        num, = struct.unpack_from('<B', out, 0x19 + 9 * i)
        struct.pack_into('<II', out, 0x19 + 9 * i + 1, *recs[num])
    end = 0x19 + 9 * n
    struct.pack_into('<H', out, end, F.crc16(bytes(out[:end]), 0xC0C1))
    return bytes(out)
