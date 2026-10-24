"""Heavy: object type histogram over the corpus (run on host1). Output: out/typehist.tsv (version, type, count, files)."""
import glob, collections, dwgload
tot = collections.defaultdict(collections.Counter); files = collections.defaultdict(collections.Counter)
for p in sorted(glob.glob('corpus/AC10*.dwg')):
    v = p.split('/')[-1][:6]
    if v not in ('AC1018', 'AC1024', 'AC1027', 'AC1032'): continue
    try:
        d = dwgload.load(open(p, 'rb').read())
    except Exception as e:
        print('ERR', p, e); continue
    c = collections.Counter(o.type for o in d['objects'].values())
    for t, n in c.items():
        tot[v][t] += n; files[v][t] += 1
with open('out/typehist.tsv', 'w') as f:
    f.write('version\ttype\tcount\tfiles\n')
    for v in sorted(tot):
        for t, n in tot[v].most_common():
            f.write('%s\t%d\t%d\t%d\n' % (v, t, n, files[v][t]))
print('done')
