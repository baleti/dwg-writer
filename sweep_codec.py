"""sweep_codec.py [files...]: codec round-trip statistics over the corpus (AC1015 + R2004 family). Run on host1 (h1run). Output TSV on stdout."""
import sys, os, glob, collections, time
import dwgload, dwgcodec

CORPUS = os.path.expanduser('~/dwg-research/corpus')
files = sys.argv[1:] or sorted(glob.glob(CORPUS + '/AC10*.dwg') + glob.glob(CORPUS + '/AC1018*.dwg'))
print('file\tver\ttype\tn\texact\tequiv\tdecfail\tbad\tfirst_error')
for f in files:
    buf = open(f, 'rb').read()
    if buf[:6] not in (b'AC1015', b'AC1018', b'AC1024', b'AC1027', b'AC1032'): continue
    t0 = time.time()
    try:
        d = dwgload.load(buf)
    except Exception as e:
        print('%s\t?\t-\t0\t0\t0\t0\t0\tload: %r' % (os.path.basename(f), e)); continue
    stat = collections.defaultdict(lambda: [0, 0, 0, 0, 0, ''])
    for h, o in d['objects'].items():
        if not dwgcodec.known(o.type): continue
        st = stat[o.type]; st[0] += 1
        try:
            dec = dwgcodec.decode(o, 30)
        except Exception as ex:
            st[3] += 1; st[5] = st[5] or ('%x: %s' % (h, ex)); continue
        try:
            raw = dwgcodec.encode(d['version'], dec, 30)
        except Exception as ex:
            st[4] += 1; st[5] = st[5] or ('enc %x: %r' % (h, ex)); continue
        if raw == o.raw: st[1] += 1
        else:
            try:
                n = dwgload.Obj(); n.handle = h; n.ver = d['version']; n.raw = raw
                import dwgedit; dwgedit._reparse(n)
                d2 = dwgcodec.decode(n, 30)
                same = {k: v for k, v in d2.items() if k != '_h'} == {k: v for k, v in dec.items() if k != '_h'}
            except Exception:
                same = False
            if same: st[2] += 1
            else: st[4] += 1; st[5] = st[5] or ('mismatch %x' % h)
    for t, st in sorted(stat.items()):
        print('%s\t%s\t%d\t%d\t%d\t%d\t%d\t%d\t%s' % (os.path.basename(f), d['version'], t, *st[:5], st[5]))
    sys.stderr.write('%s %.1fs\n' % (os.path.basename(f), time.time() - t0))
