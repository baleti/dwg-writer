"""Heavy (host1): run the text extraction on every supported corpus file; out/sweep_text.tsv: file version secs ok entities texts layouts error"""
import glob, time, io, contextlib, traceback, json
import dwg2text
rows = []
for p in sorted(glob.glob('corpus/AC10*.dwg')):
    v = p.split('/')[-1][:6]
    if v not in ('AC1015', 'AC1018', 'AC1024', 'AC1027', 'AC1032'): continue
    t = time.time(); err = ''
    n = nt = nl = 0
    try:
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            dwg2text.main(p, True)
        d = json.loads(buf.getvalue())
        n = sum(d['entity_counts'].values()); nt = sum(len(x) for x in d['text'].values()); nl = len(d.get('layouts', []))
    except Exception as e:
        err = repr(e)[:100]
    rows.append('%s\t%s\t%.1f\t%s\t%d\t%d\t%d\t%s' % (p.split('/')[-1], v, time.time() - t, 'ok' if not err else 'ERR', n, nt, nl, err))
    print(rows[-1], flush=True)
open('out/sweep_text.tsv', 'w').write('file\tversion\tsecs\tok\tentities\ttexts\tlayouts\terror\n' + '\n'.join(rows) + '\n')
