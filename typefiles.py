"""Heavy (host1): per file counts of not yet decoded entity types and class types: out/typefiles.tsv (file, name, count)"""
import glob, collections
import dwgmodel
rows = []
for p in sorted(glob.glob('corpus/AC10*.dwg')):
    v = p.split('/')[-1][:6]
    if v not in ('AC1015', 'AC1018', 'AC1024', 'AC1027', 'AC1032'): continue
    try:
        m = dwgmodel.Model(open(p, 'rb').read())
        cl = {c['num']: c['dxf'] for c in m.classes()} if v != 'AC1015' else {}
    except Exception as e:
        print('ERR', p, repr(e)[:80], flush=True); continue
    c = collections.Counter()
    for o in m.objs.values():
        if o.type in dwgmodel.ENT_DECODERS: continue
        if o.type >= 500: c[cl.get(o.type, 'type%d' % o.type)] += 1
        elif o.type in (8, 11, 16, 45, 46, 47, 33, 37, 38, 39, 43, 40, 41, 12, 13, 14, 29, 30, 20, 23, 24):
            c['FIXED%d' % o.type] += 1
    for k, n in c.items(): rows.append('%s\t%s\t%d' % (p.split('/')[-1], k, n))
open('out/typefiles.tsv', 'w').write('\n'.join(rows) + '\n')
print('done')
