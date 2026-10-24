"""ACIS data of REGION / 3DSOLID / BODY entities (own code; formats found by experiment, see NOTES.md).
acis_data(o) -> ('sat', text) for R2000-R2007 objects (version 1: blocks of text, every byte above 32 stored as 159 - c) or ('sab', bytes) for R2010+."""
import dwgbits as B
import dwgent


def acis_data(o):
    r = dwgent.start_reader(o)
    dwgent.common_entity(r, o.ver)
    empty = r.B()  # 1: no ACIS data in the object (R2013+ keeps such solids in the AcDb:AcDsPrototype data store, not decoded)
    r.B()  # unknown (1 in R2000)
    if empty and o.ver in ('AC1027', 'AC1032'): return None, None
    ver = r.BS()
    if ver not in (1, 2): return None, None
    if ver == 1:
        chunks = []
        while True:
            n = r.BL()
            if not n: break
            raw = r.rcs(r.cnt(n, 8))
            chunks.append(bytes((159 - c) if c > 32 else c for c in raw))
        return 'sat', b''.join(chunks).decode('latin1')
    if ver == 2:
        n = (dwgent.expected_end(o) - r.p) // 8
        return 'sab', bytes(r.rcs(n))
    return None, None


def parse_sab(b):
    """SAB binary -> (header dict, records). A record is [name, fields...] with fields as ('p', idx) pointers, ('i', int), ('d', float), ('s', str), ('e', int) enums,
    ('b', bool), ('P', (x, y, z)) positions, ('V', (x, y, z)) vectors. Tags: 3/4 int, 6 double, 7/8/9 strings, 0xA/0xB bool, 0xC pointer, 0xD/0xE (sub)identifier,
    0x11 end of record, 0x12 ?, 0x13 position, 0x14 vector, 0x15 enum."""
    import struct
    if not b.startswith((b'ACIS BinaryFile', b'ASM BinaryFile')): raise ValueError('not SAB')
    ver, nrec, nent, flags = struct.unpack_from('<4i', b, 15)
    p = 15 + 16
    hdr = dict(version=ver, nrec=nrec, nent=nent, flags=flags)
    strs = []
    for _ in range(3):
        assert b[p] == 7; n = b[p + 1]; strs.append(b[p + 2:p + 2 + n].decode('latin1')); p += 2 + n
    hdr['product'] = strs
    units = []
    for _ in range(3):
        assert b[p] == 6; units.append(struct.unpack_from('<d', b, p + 1)[0]); p += 9
    hdr['units'] = units
    recs = []; cur = []; name = []
    n = len(b)
    while p < n:
        t = b[p]; p += 1
        if t == 0x0D or t == 0x0E:
            ln = b[p]; s = b[p + 1:p + 1 + ln].decode('latin1'); p += 1 + ln
            if t == 0x0D and cur == [] and not name: name = [s]
            else: name.append(s)
            if name in (['End', 'of', 'ACIS', 'data'], ['End', 'of', 'ASM', 'data']): break
            continue
        if not name and t != 0x11: pass
        if t == 0x11:
            recs.append(('-'.join(name), cur)); cur = []; name = []
            if recs[-1][0] in ('End-of-ACIS-data', 'End-of-ASM-data'): break
            continue
        if t in (3, 4): v = struct.unpack_from('<i', b, p)[0]; p += 4; cur.append(('i', v))
        elif t == 5: v = struct.unpack_from('<i', b, p)[0]; p += 4; cur.append(('i', v))
        elif t == 6: v = struct.unpack_from('<d', b, p)[0]; p += 8; cur.append(('d', v))
        elif t == 7: ln = b[p]; cur.append(('s', b[p + 1:p + 1 + ln].decode('latin1'))); p += 1 + ln
        elif t == 8: ln = struct.unpack_from('<H', b, p)[0]; cur.append(('s', b[p + 2:p + 2 + ln].decode('latin1'))); p += 2 + ln
        elif t == 9: ln = struct.unpack_from('<i', b, p)[0]; cur.append(('s', b[p + 4:p + 4 + ln].decode('latin1'))); p += 4 + ln
        elif t == 0x0A: cur.append(('b', True))
        elif t == 0x0B: cur.append(('b', False))
        elif t == 0x0C: v = struct.unpack_from('<i', b, p)[0]; p += 4; cur.append(('p', v))
        elif t in (0x13, 0x14): v = struct.unpack_from('<3d', b, p); p += 24; cur.append(('P' if t == 0x13 else 'V', v))
        elif t == 0x15: v = struct.unpack_from('<i', b, p)[0]; p += 4; cur.append(('e', v))
        elif t in (0x0F, 0x10): pass  # subtype brackets { } (ASM): the fields stay in the same record
        else: raise ValueError('SAB tag 0x%x at %d' % (t, p - 1))
    return hdr, recs


import math


def _vec_cross(a, b): return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _ptf(recs, i):
    """Position of a point record, or None."""
    if i is None or i < 0 or i >= len(recs): return None
    for t, v in recs[i][1]:
        if t == 'P': return v
    return None


def _ptr(f):
    return [v for t, v in f if t == 'p']


def curve_points(recs, ci, t0, t1, n_arc=720):
    """Sample curve record ci between parameters t0 and t1 (SAB v >= 20000 layout). Returns a list of points."""
    name, f = recs[ci]
    P = [v for t, v in f if t == 'P']; V = [v for t, v in f if t == 'V']; D = [v for t, v in f if t == 'd']
    if name == 'straight-curve':
        r, d = P[0], V[0]
        return [(r[0] + d[0] * t, r[1] + d[1] * t, r[2] + d[2] * t) for t in (t0, t1)]
    if name == 'ellipse-curve':
        c, nrm, maj = P[0], V[0], V[1]; ratio = D[0]
        mn = _vec_cross(nrm, maj); mn = tuple(x * ratio for x in mn)
        if t1 < t0: t0, t1 = t1, t0
        n = max(2, int(abs(t1 - t0) / (2 * math.pi) * n_arc) + 1)
        return [tuple(c[k] + maj[k] * math.cos(t0 + (t1 - t0) * i / n) + mn[k] * math.sin(t0 + (t1 - t0) * i / n) for k in range(3)) for i in range(n + 1)]
    return None


def _edge_points(recs, ep, ed):
    """Sampled points of one edge record (pointer list ep, doubles ed): curve between its parameters, or derived from the vertices (old files without parameters)."""
    vs, ve, curve = ep[2], ep[3], ep[5]
    pa = _ptf(recs, _ptr(recs[vs][1])[3]) if vs >= 0 else None
    pb = _ptf(recs, _ptr(recs[ve][1])[3]) if ve >= 0 else None
    if curve < 0: return [pa, pb]
    name, f = recs[curve]
    if len(ed) >= 2:
        return curve_points(recs, curve, ed[0], ed[1]) or [pa, pb]
    if name == 'straight-curve': return [pa, pb]
    if name == 'ellipse-curve':
        P = [v for t, v in f if t == 'P']; V = [v for t, v in f if t == 'V']; ratio = [v for t, v in f if t == 'd'][0]
        c, nrm, maj = P[0], V[0], V[1]
        mn = _vec_cross(nrm, maj); mn = tuple(x * ratio for x in mn)
        def ang(p):
            d = tuple(p[k] - c[k] for k in range(3))
            x = sum(d[k] * maj[k] for k in range(3)) / sum(m * m for m in maj)
            y = sum(d[k] * mn[k] for k in range(3)) / max(sum(m * m for m in mn), 1e-300)
            return math.atan2(y, x)
        if pa is None or pb is None: return [pa, pb]
        t0 = ang(pa); t1 = ang(pb)
        if t1 <= t0 + 1e-9: t1 += 2 * math.pi
        return curve_points(recs, curve, t0, t1)
    return [pa, pb]


def faces(recs):
    """Planar boundary loops of every face: [{'loops': [[(x, y, z), ...], ...], 'surface': name}] (curved edges other than lines and ellipses are
    reduced to their end points, flagged in 'approx')."""
    out = []
    for fi, (name, f) in enumerate(recs):
        if name != 'face': continue
        ps = _ptr(f)
        loop = ps[3] if len(ps) > 3 else -1   # [attr, hist, next face, loop, shell, subshell, surface]
        surf = ps[6] if len(ps) > 6 else -1
        loops = []; approx = False
        while loop is not None and loop >= 0:
            lf = recs[loop][1]; lp = _ptr(lf)
            ce0 = lp[3] if len(lp) > 3 else -1
            pts = []; ce = ce0; guard = 0
            while ce >= 0 and guard < 100000:
                guard += 1
                cf = recs[ce][1]; cp = _ptr(cf); bools = [v for t, v in cf if t == 'b']
                nxt = cp[2]; edge = cp[5]
                ef = recs[edge][1]; ep = _ptr(ef); ed = [v for t, v in ef if t == 'd']
                vs, ve, curve = ep[2], ep[3], ep[5]
                rev = bool(bools[0]) if bools else False
                seg = _edge_points(recs, ep, ed)
                if curve >= 0 and recs[curve][0] not in ('straight-curve', 'ellipse-curve'): approx = True
                ebrev = bool([v for t, v in ef if t == 'b'][0]) if [v for t, v in ef if t == 'b'] else False
                if ebrev: seg = seg[::-1]
                if rev: seg = seg[::-1]
                pts.extend(seg[:-1] if pts or True else seg)
                ce = nxt
                if ce == ce0: break
            loops.append([p for p in pts if p is not None])
            loop = lp[2] if len(lp) > 2 else -1
        out.append(dict(loops=loops, surface=recs[surf][0] if surf >= 0 else None, approx=approx))
    tf = body_transform(recs)
    if tf:
        for fc in out: fc['loops'] = [[tf(p) for p in lp] for lp in fc['loops']]
    return out


def body_transform(recs):
    """The body transform record as a function on points (rotation rows applied to row vectors, then scale, then translation; the reflect flag negates the
    result of the rotation) or None when absent or the identity. Verified on REGIONs with translation (3 files) and a 90 degree rotation against AutoCAD's bounding box."""
    for name, f in recs:
        if name != 'transform': continue
        vs = [v for t, v in f if t == 'V']; ds = [v for t, v in f if t == 'd']
        if len(vs) < 4 or not ds: return None
        R = vs[:3]; T = vs[3]; sc = ds[0]
        if R == [(1.0, 0.0, 0.0), (0.0, 1.0, 0.0), (0.0, 0.0, 1.0)] and sc == 1.0 and not any(T): return None
        return lambda p: tuple((p[0] * R[0][i] + p[1] * R[1][i] + p[2] * R[2][i]) * sc + T[i] for i in range(3))
    return None


def wire(recs):
    """All edges as polylines [(x, y, z), ...] (lines and ellipses exact, other curves reduced to their end points)."""
    out = []
    for name, f in recs:
        if name != 'edge': continue
        ep = _ptr(f); ed = [v for t, v in f if t == 'd']
        try:
            seg = [p for p in _edge_points(recs, ep, ed) if p is not None]
        except Exception:
            continue
        if len(seg) >= 2: out.append(seg)
    tf = body_transform(recs)
    return [[tf(p) for p in seg] for seg in out] if tf else out


def area3d(loop):
    """Unsigned area of a planar 3D loop (Newell vector area, relative to the first point)."""
    o = loop[0]; nx = ny = nz = 0.0
    for i in range(len(loop)):
        a = [loop[i][k] - o[k] for k in range(3)]; b = [loop[(i + 1) % len(loop)][k] - o[k] for k in range(3)]
        nx += a[1] * b[2] - a[2] * b[1]; ny += a[2] * b[0] - a[0] * b[2]; nz += a[0] * b[1] - a[1] * b[0]
    return (nx * nx + ny * ny + nz * nz) ** 0.5 / 2


def area(loop):
    a = 0.0
    ox, oy = loop[0][0], loop[0][1]  # relative to the first point: the coordinates can be 1e10 and the products would lose all digits
    for i in range(len(loop)):
        x0, y0 = loop[i][0] - ox, loop[i][1] - oy; x1, y1 = loop[(i + 1) % len(loop)][0] - ox, loop[(i + 1) % len(loop)][1] - oy
        a += x0 * y1 - x1 * y0
    return a / 2


_SENSE = {'forward': False, 'reversed': True, 'single': False, 'double': True, 'in': False, 'out': True, 'forward_v': False, 'reverse_v': True, 'F': False, 'T': True}
_SCHEMA = {'point': 'P', 'straight-curve': 'PV', 'ellipse-curve': 'PVVd', 'plane-surface': 'PVV', 'cone-surface': 'PVVd', 'sphere-surface': 'Pd', 'torus-surface': 'PVdd'}


def parse_sat(text):
    """SAT text -> (header, records) in the same record form as parse_sab (old style records without index and history fields get a dummy history pointer)."""
    lines = text.split('\n')
    head = lines[0].split()
    ver = int(head[0])
    hdr = dict(version=ver, nrec=int(head[1]), nent=int(head[2]), flags=int(head[3]) if len(head) > 3 else 0)
    # line 2: three length-prefixed strings; line 3: units
    rest = '\n'.join(lines[1:])
    toks = rest.split()
    i = 0; strs = []
    for _ in range(3):
        n = int(toks[i]); i += 1
        s = ' '.join(toks[i:i + 1])
        # strings contain spaces: re-scan from the original text
        break
    # simple scan of the original text: after line 1 read three (len, string) pairs
    pos = len(lines[0]) + 1
    for _ in range(3):
        while text[pos] in ' \n\r': pos += 1
        q = pos
        while text[q].isdigit(): q += 1
        n = int(text[pos:q]); pos = q + 1
        strs.append(text[pos:pos + n]); pos += n
    hdr['product'] = strs
    m = pos
    body = text[m:]
    # units: three numbers
    t = body.split(None, 3)
    hdr['units'] = [float(t[0]), float(t[1]), float(t[2])]
    body = t[3] if len(t) > 3 else ''
    recs = []
    p = 0; n = len(body)
    while p < n:
        e = body.find('#', p)
        if e < 0: break
        chunk = body[p:e]; p = e + 1
        # tokenise respecting '@len string'
        toks = []; k = 0; L = len(chunk)
        while k < L:
            if chunk[k] in ' \n\r\t': k += 1; continue
            if chunk[k] == '@':
                j = k + 1
                while j < L and chunk[j].isdigit(): j += 1
                ln = int(chunk[k + 1:j]); toks.append(('s', chunk[j + 1:j + 1 + ln])); k = j + 1 + ln; continue
            j = k
            while j < L and chunk[j] not in ' \n\r\t': j += 1
            toks.append(chunk[k:j]); k = j
        if not toks: continue
        if toks[0].lstrip('-').isdigit() and toks[0].startswith('-'): toks = toks[1:]   # explicit index "-N"
        elif toks[0].isdigit(): toks = toks[1:]
        name = toks[0]; f = toks[1:]
        if name == 'End-of-ACIS-data' or name == 'End': break
        new_style = ver >= 500 and len(f) >= 3 and isinstance(f[0], str) and f[0].startswith('$') and f[1].lstrip('-').isdigit() and not isinstance(f[1], tuple) and isinstance(f[2], str) and f[2].startswith('$')
        out = []
        for x in f:
            if isinstance(x, tuple): out.append(x); continue
            if x[0] == '$': out.append(('p', int(x[1:])))
            elif x in _SENSE: out.append(('b', _SENSE[x]))
            elif x == 'I': out.append(('x', 'I'))
            else:
                try: out.append(('n', float(x) if any(c in x for c in '.eE') else int(x)))
                except ValueError: out.append(('s', x))
        if not new_style and out and out[0][0] == 'p':
            out.insert(1, ('p', -1))   # old style: no id / history pointer
        # group numeric tokens per schema: the first numbers after the header fields
        k0 = 3 if new_style else 2
        sch = _SCHEMA.get(name, '')
        res = out[:k0]; idx = k0
        if name == 'edge':
            res += [('d', float(v)) if t == 'n' else (t, v) for t, v in out[k0:]]
        else:
            for c in sch:
                if c in 'PV':
                    if idx + 3 <= len(out) and all(out[idx + j][0] == 'n' for j in range(3)):
                        res.append((c, tuple(float(out[idx + j][1]) for j in range(3)))); idx += 3
                elif c == 'd' and idx < len(out) and out[idx][0] == 'n':
                    res.append(('d', float(out[idx][1]))); idx += 1
            res += out[idx:]
        recs.append((name, res))
    return hdr, recs


def parse(e):
    """Records of a REGION / 3DSOLID / BODY entity dict (from the model): (header, records) or None."""
    fmt, data = e.get('acis', (None, None))
    if not data: return None
    return parse_sab(data) if fmt == 'sab' else parse_sat(data)


def datastore_sab(buf, info, objs):
    """R2013+ solids flagged 'acis empty' keep their ASM binary file in section AcDb:AcDsPrototype_1b. Returns {handle: bytes}. Found by experiment (HANDOFF.md): the store holds one
    'ASM BinaryFile' per record in file order; a table of rows [u32 0x14, u32 1, u64 handle, u32 offset] lists the owning objects, and the handle-sorted rows of the solid/class objects
    pair one to one with the files in file order (2,458 rows and 2,458 files in the sample; consecutive offset differences equal the file sizes in 2,153 of 2,432 steps, the rest
    cross segment boundaries). Not verified against an AutoCAD export: no oracle for such a file."""
    import re, struct, dwgload
    if not info or 'AcDb:AcDsPrototype_1b' not in info.get('sections', {}): return {}
    sec = dwgload.section(buf, info, 'AcDb:AcDsPrototype_1b')
    ms = [m.start() for m in re.finditer(rb'(?:ASM|ACIS) BinaryFile', sec)]
    if not ms: return {}
    rows = {}
    for m in re.finditer(re.escape(struct.pack('<II', 0x14, 1)), sec):
        h, v = struct.unpack_from('<QI', sec, m.start() + 8)
        o = objs.get(h)
        if o is not None and (o.type in (37, 38, 39) or o.type >= 500): rows[h] = v
    hs = sorted(rows)
    if len(hs) != len(ms): return {}  # pairing is only trusted when the counts agree
    out = {}
    for i, h in enumerate(hs):
        end = ms[i + 1] if i + 1 < len(ms) else min(len(sec), ms[i] + (64 << 20))
        out[h] = bytes(sec[ms[i]:end])
    return out
