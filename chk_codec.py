"""chk_codec.py FILE [TYPE...]: encode(decode(object)) must equal the stored bytes. Per-type counts (own code)."""
import sys, collections
import dwgload, dwgcodec, dwgmodel

def same_value(ver, raw, dec, o, cp):
    """the re-encoded object decodes to the same dictionary (the original merely uses a different but equivalent bit coding)"""
    try:
        n = dwgload.Obj(); n.handle = o.handle; n.ver = ver; n.raw = raw
        import dwgedit
        dwgedit._reparse(n)
        d2 = dwgcodec.decode(n, cp, True, dec.get('key') if isinstance(dec.get('key'), str) else None)
    except Exception:
        return False
    return {k: v for k, v in d2.items() if k != '_h'} == {k: v for k, v in dec.items() if k != '_h'}


def CLASSMAP(buf):
    import dwgfmt as F, dwgmodel, dwgobj as O
    ver = buf[:6].decode()
    cl = O.parse_classes_r2000(O.load_r2000(buf)['classes']) if ver == 'AC1015' else dwgmodel.parse_classes(F.r2004_section_data(buf, F.r2004_open(buf), 'AcDb:Classes'), ver)
    return {c['num']: c['dxf'] for c in cl}


def run(path, types=None, show=3):
    buf = open(path, 'rb').read()
    d = dwgload.load(buf)
    cp = 30
    clsmap = CLASSMAP(buf)
    stat = collections.defaultdict(lambda: [0, 0, 0, 0, 0])   # n, exact, equivalent, decode fail, mismatch
    shown = collections.Counter()
    for h, o in d['objects'].items():
        if not dwgcodec.known(o.type, clsmap.get(o.type)) or (types and o.type not in types): continue
        st = stat[o.type]; st[0] += 1
        try:
            dec = dwgcodec.decode(o, cp, True, clsmap.get(o.type))
        except Exception as ex:
            st[3] += 1
            if shown[o.type, 'f'] < show: shown[o.type, 'f'] += 1; print('  decode fail type %d handle %x: %s' % (o.type, h, ex))
            continue
        try:
            raw = dwgcodec.encode(d['version'], dec, cp)
        except Exception as ex:
            st[4] += 1
            if shown[o.type, 'e'] < show: shown[o.type, 'e'] += 1; print('  encode fail type %d handle %x: %r' % (o.type, h, ex))
            continue
        if raw == o.raw: st[1] += 1
        elif same_value(d['version'], raw, dec, o, cp):
            st[2] += 1
        else:
            st[4] += 1
            if shown[o.type, 'm'] < show:
                shown[o.type, 'm'] += 1
                i = next((i for i in range(min(len(raw), len(o.raw))) if raw[i] != o.raw[i]), None)
                print('  mismatch type %d handle %x: len %d vs %d first diff byte %s' % (o.type, h, len(raw), len(o.raw), i))
    tot = [sum(st[i] for st in stat.values()) for i in range(5)]
    print('%s total n=%d exact=%d equiv=%d decfail=%d bad=%d' % (d['version'], *tot))
    for t, st in sorted(stat.items()):
        if QUIET and st[3] == 0 and st[4] == 0: continue
        print('%s type %3d: n=%6d exact=%6d equiv=%6d decfail=%4d bad=%4d' % (d['version'], t, *st))

QUIET = '-q' in sys.argv

if __name__ == '__main__':
    run(sys.argv[1], set(int(x) for x in sys.argv[2:] if x != '-q'))
