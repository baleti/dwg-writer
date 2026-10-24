"""Complex linetype text elements (LTYPE group 9) vs AutoCAD drawing.dxf, AC1018-AC1032 files <= 6 MB: chk_ltypetext_dxf.py"""
import re, glob, os, dwgmodel, dwgtab
tot = ok = 0
for d in sorted(glob.glob('oracle-out/*/drawing.dxf')):
    stem = d.split('/')[1]; f = 'corpus/%s.dwg' % stem
    if not os.path.exists(f) or not re.match(r'AC10(18|21|24|27|32)', stem) or os.path.getsize(f) > 6e6: continue
    s = open(d, encoding='utf-8', errors='replace').read()
    truth = {}
    for blk in s.split('\n  0\nLTYPE\n')[1:]:
        L = blk.split('\n  0\n')[0].split('\n'); pr = [(L[i].strip(), L[i + 1]) for i in range(0, len(L) - 1, 2)]
        name = next((v for c, v in pr if c == '2'), None); txt = [v for c, v in pr if c == '9']
        if txt: truth[name] = txt
    if not truth: continue
    m = dwgmodel.Model(open(f, 'rb').read()); mine = {}
    for h, o in m.objs.items():
        if o.type == 57:
            try: x = dwgtab.decode_ltype(o)
            except Exception: continue
            mine[x['name']] = [e['text'] for e in x['dashes'] if 'text' in e]
    for n, t in truth.items():
        tot += 1
        if mine.get(n) == t: ok += 1
        else: print(stem, repr(n)[:30], t, mine.get(n))
print('equal', ok, 'of', tot)
