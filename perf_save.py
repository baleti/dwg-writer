import sys, time, dwgdoc
f = sys.argv[1]; t0 = time.time()
doc = dwgdoc.Doc(open(f, 'rb').read()); t1 = time.time()
doc.add_line((0, 0), (10, 10)); out = doc.save(); t2 = time.time()
open(sys.argv[2], 'wb').write(out)
print(f.split('/')[-1], 'load %.1fs save %.1fs in %d out %d' % (t1 - t0, t2 - t1, len(open(f, 'rb').read()), len(out)))
