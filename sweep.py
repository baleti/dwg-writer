"""Corpus sweep (HEAVY: run on host1 via h1run). For each corpus file: container load, object count, LINE decode error rate. Usage: sweep.py > out/sweep.tsv"""
import glob, sys, time, collections
import dwgload, dwgent
print('file\tver\tobjects\tmap_ok\tlines\tline_err\tsecs')
for p in sorted(glob.glob('corpus/AC10*.dwg')):
    t = time.time()
    try:
        d = dwgload.load(open(p, 'rb').read())
    except Exception as e:
        print('%s\t%s\tERR %r\t\t\t\t%.1f' % (p[7:], p[7:13], e, time.time() - t)); sys.stdout.flush(); continue
    n = err = 0
    for o in d['objects'].values():
        if o.type == 19:
            n += 1
            try: dwgent.decode_line(o)
            except Exception: err += 1
    print('%s\t%s\t%d\t%s\t%d\t%d\t%.1f' % (p[7:], d['version'], len(d['objects']), d.get('omap_ok'), n, err, time.time() - t)); sys.stdout.flush()
