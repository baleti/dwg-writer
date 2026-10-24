"""AC1021 (R2007) container: system header, page map, section map and the compressed sections (own code; the LZ variant is lz2007b).
open_r21(buf) -> dict(sections={name: [pages]}, ...); section_data(buf, info, name) -> bytes (all pages concatenated, trimmed to the page sizes)."""
import struct
import r21
import lz2007b


def _rs_bytes(buf, pos, size, per, kfix=None):
    k = kfix or size // 255
    raw = buf[pos:pos + 255 * k]
    return b''.join(raw[j::k][:per] for j in range(k))


def _section_map(buf, q, pm):
    pid, usz = q[24], q[25]
    if pid not in pm['pages']: return None
    pos, sz = pm['pages'][pid]
    best = None
    for k in range(1, sz // 255 + 1):  # the interleave factor of the system pages is not derivable from the size: trial; the exact output size is the check
        o, st = lz2007b.decompress(_rs_bytes(buf, pos, sz, 239, k), usz)
        if len(o) >= usz and (st == 'done' or len(o) == usz):  # trailing junk after the exact size is not an error; a match may overshoot by a few bytes
            if best is None or len(o) < best[0]: best = (len(o), o[:usz])  # smallest overshoot wins
    return best[1] if best is not None else None


def open_r21(buf):
    q = r21.system_header(buf)
    pm = r21.page_map(buf, q)
    if pm is None: raise ValueError('AC1021 page map unreadable')
    o = _section_map(buf, q, pm)
    if o is None: raise ValueError('AC1021 section map unreadable')
    p = 0; secs = {}
    while p + 64 <= len(o):
        ds, mx, enc, h, nl, unk, encd, npg = struct.unpack_from('<8Q', o, p); p += 64
        if nl == 0 and npg == 0:
            if secs: break
            continue  # a leading empty record (seen in a small file): skip it
        name = o[p:p + nl].decode('utf-16le', 'replace').rstrip('\0'); p += nl
        pages = []
        for _ in range(npg):
            pages.append(struct.unpack_from('<7Q', o, p)); p += 56
        secs[name] = dict(size=ds, max=mx, encoded=encd, pages=pages)
    return dict(kind='r21', sys=q, pagemap=pm, sections=secs)


def page_data(buf, info, ent, raw=False):
    """One page entry (offset, size, id, usz, csz, ...) -> its decompressed bytes."""
    off, size, pid, usz, csz = ent[:5]
    pos, psz = info['pagemap']['pages'][pid]
    if raw: return bytes(buf[pos:pos + usz]), 'raw'  # encoded=1 sections (AppInfo, SummaryInfo, Preview...) are plain, without interleave
    b = _rs_bytes(buf, pos, psz, 251)[:csz]
    if csz == usz: return b, 'stored'  # incompressible pages are stored raw (compressed size equals the page size)
    o, st = lz2007b.decompress(b, usz)
    return o[:usz], st


def section_data(buf, info, name):
    s = info['sections'][name]
    out = bytearray(); bad = []
    for ent in s['pages']:
        o, st = page_data(buf, info, ent, s['encoded'] == 1)
        if len(o) != ent[3]: bad.append((ent[2], st))
        out += o.ljust(ent[3], b'\0')
    return bytes(out), bad
