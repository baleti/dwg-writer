"""Object store for R2000 (AC1015). Every object keeps its raw bytes (offset, size, bytes) so unknown objects round-trip byte-exact."""
import struct
import dwgfmt as F
import dwgbits as B


class Obj:
    __slots__ = ('handle', 'offset', 'size', 'type', 'bitsize', 'raw')

    def __init__(self, handle, offset, size, type_, bitsize, raw):
        self.handle, self.offset, self.size, self.type, self.bitsize, self.raw = handle, offset, size, type_, bitsize, raw


def load_r2000(buf):
    hdr = F.read_r13_r2000(buf)
    hv, hv_crc, _ = F.section_r13_r2000(buf, hdr['locators'][0])
    cl, cl_crc, _ = F.section_r13_r2000(buf, hdr['locators'][1])
    omap, omap_ok = F.object_map_r13_r2000(buf, hdr['locators'][2])
    objs = {}
    for h, off in omap.items():
        size, = struct.unpack_from('<H', buf, off)
        hb = 2
        if size & 0x8000:  # MS: second word holds the high bits
            size = (size & 0x7FFF) | (struct.unpack_from('<H', buf, off + 2)[0] << 15); hb = 4
        raw = bytes(buf[off:off + size + hb + 2])  # size field + data + crc
        r = B.Bits(buf, (off + hb) * 8)
        objs[h] = Obj(h, off, size, r.BS(), r.RL(), raw)
    return dict(header=hdr, hdrvars=hv, classes=cl, objects=objs, omap_ok=omap_ok)


if __name__ == '__main__':
    import sys, collections
    for p in sys.argv[1:]:
        d = load_r2000(open(p, 'rb').read())
        c = collections.Counter(o.type for o in d['objects'].values())
        print(p, len(d['objects']), c.most_common(12))


def common_entity_r2000(r):
    """Common entity header after the object handle: returns dict; leaves r at start of entity-specific data. [GEN layout]"""
    e = {}
    eed = []
    while True:
        n = r.BS()
        if n == 0: break
        app = r.H()
        data = bytes(r.RC() for _ in range(n))
        eed.append((app, data))
    e['eed'] = eed
    if r.B():
        sz = r.RL()
        r.p += sz * 8
    e['entmode'] = r.BB()
    e['nreactors'] = r.BL()
    e['nolinks'] = r.B()
    e['color'] = r.BS()
    e['ltscale'] = r.BD()
    e['ltflags'] = r.BB()
    e['plotflags'] = r.BB()
    e['invis'] = r.BS()
    e['lweight'] = r.RC()
    return e


def decode_entity_r2000(o, buf):
    r = B.Bits(o.raw, 16)  # after size field (2 bytes)
    r.BS(); r.RL(); r.H()
    e = common_entity_r2000(r)
    t = o.type
    if t == 19:
        z0 = r.B(); x1 = r.RD(); x2 = r.DD(x1); y1 = r.RD(); y2 = r.DD(y1)
        z1 = z2 = 0.0
        if not z0: z1 = r.RD(); z2 = r.DD(z1)
        e.update(kind='LINE', p1=(x1, y1, z1), p2=(x2, y2, z2), thickness=r.BT(), ext=r.BE())
    elif t in (17, 18):
        c = r.BD3(); rad = r.BD(); th = r.BT(); ex = r.BE()
        e.update(kind='ARC' if t == 17 else 'CIRCLE', center=c, radius=rad, thickness=th, ext=ex)
        if t == 17: e.update(a0=r.BD(), a1=r.BD())
    elif t == 1:
        fl = r.RC()
        elev = 0.0 if fl & 1 else r.RD()
        ins = r.RD2()
        al = ins if fl & 2 else (r.DD(ins[0]), r.DD(ins[1]))
        ex = r.BE(); th = r.BT()
        obl = 0.0 if fl & 4 else r.RD()
        rot = 0.0 if fl & 8 else r.RD()
        h = r.RD()
        wf = 1.0 if fl & 0x10 else r.RD()
        txt = r.TV()
        gen = 0 if fl & 0x20 else r.BS()
        ha = 0 if fl & 0x40 else r.BS()
        va = 0 if fl & 0x80 else r.BS()
        e.update(kind='TEXT', elev=elev, ins=ins, align=al, ext=ex, thickness=th, oblique=obl, rot=rot, height=h, widthf=wf, text=txt, gen=gen, halign=ha, valign=va)
    elif t == 77:
        fl = r.BS()
        cw = r.BD() if fl & 4 else 0.0
        el = r.BD() if fl & 8 else 0.0
        th = r.BD() if fl & 2 else 0.0
        nm = r.BD3() if fl & 1 else (0.0, 0.0, 1.0)
        n = r.BL()
        nb = r.BL() if fl & 16 else 0
        nw = r.BL() if fl & 32 else 0
        pts = []
        for i in range(n):
            if i == 0: pts.append(r.RD2())
            else: pts.append((r.DD(pts[-1][0]), r.DD(pts[-1][1])))
        bul = [r.BD() for _ in range(nb)]
        wid = [(r.BD(), r.BD()) for _ in range(nw)]
        e.update(kind='LWPOLYLINE', flags=fl, closed=bool(fl & 512), constwidth=cw, elev=el, thickness=th, ext=nm, pts=pts, bulges=bul, widths=wid)
    return e


def decode_object_r2000(o):
    """Non-entity objects (tables, dictionaries...). Returns dict with kind and decoded fields where supported."""
    r = B.Bits(o.raw, 16)
    r.BS(); r.RL(); r.H()
    eed = []
    while True:
        n = r.BS()
        if n == 0: break
        eed.append((r.H(), bytes(r.RC() for _ in range(n))))
    nre = r.BL()
    e = dict(eed=eed, nreactors=nre)
    t = o.type
    if t == 51:  # LAYER
        name = r.TV(); r.B(); r.BS(); r.B()
        fl = r.BS(); col = r.BS()
        e.update(kind='LAYER', name=name, frozen=bool(fl & 1), locked=bool(fl & 4), color=col, flags=fl)
    return e


def parse_classes_r2000(data):
    r = B.Bits(data)
    out = []
    end = len(data) * 8 - 8
    while r.p < end:
        try:
            num = r.BS(); ver = r.BS(); app = r.TV(); cpp = r.TV(); dxf = r.TV(); zombie = r.B(); iid = r.BS()
        except IndexError:
            break
        out.append(dict(num=num, version=ver, app=app, cpp=cpp, dxf=dxf, zombie=zombie, item=iid))
    return out


def handle_stream_r2000(o):
    """Handle references of an object: stream starts at bit 16+bitsize of raw (size field = 16 bits). [EXP]"""
    hr = B.Bits(o.raw, 16 + o.bitsize)
    hs = []
    try:
        while hr.p < len(o.raw) * 8 - 20:
            hs.append(hr.H())
    except IndexError:
        pass
    return hs


def abs_handle(code, val, own):
    """Resolve relative handle codes (6 = own+1, 8 = own-1, 10 = own+val, 12 = own-val); 2-5 absolute."""
    if code in (2, 3, 4, 5): return val
    if code == 6: return own + 1
    if code == 8: return own - 1
    if code == 10: return own + val
    if code == 12: return own - val
    return val


def entity_layer_r2000(o):
    for c, v in handle_stream_r2000(o):
        if c == 5: return v
