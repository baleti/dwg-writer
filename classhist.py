"""Heavy (host1): histogram of class-based object types by DXF class name; out/classhist.tsv (name, count, files)."""
import glob, collections
import dwgmodel
tot = collections.Counter(); files = collections.Counter()
for p in sorted(glob.glob('corpus/AC10*.dwg')):
    v = p.split('/')[-1][:6]
    if v not in ('AC1018', 'AC1024', 'AC1027', 'AC1032'): continue
    try:
        m = dwgmodel.Model(open(p, 'rb').read())
        cl = {c['num']: c['dxf'] for c in m.classes()}
        c = collections.Counter(cl.get(o.type, 'type%d' % o.type) for o in m.objs.values() if o.type >= 500)
        # also fixed types without decoder
        c2 = collections.Counter('FIXED%d' % o.type for o in m.objs.values() if o.type < 500 and o.type not in dwgmodel.ENT_DECODERS and o.type not in (4, 5, 42, 48, 49, 50, 51, 52, 53, 56, 57, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 79, 80, 82))
    except Exception as e:
        print('ERR', p, repr(e)[:80], flush=True); continue
    for k, n in (c + c2).items():
        tot[k] += n; files[k] += 1
with open('out/classhist.tsv', 'w') as f:
    for k, n in tot.most_common():
        f.write('%s\t%d\t%d\n' % (k, n, files[k]))
print('done')
