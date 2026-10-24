"""Heavy (host1): selfcheck over all corpus files of R2004 family; out/selfcheck.tsv rows: version type ok bad exc"""
import glob, collections, dwgload, dwgent, dwgmodel, dwgtab
DECODERS = dict(dwgmodel.ENT_DECODERS)
DECODERS.update({49: dwgtab.decode_block_header, 51: dwgtab.decode_layer, 53: dwgtab.decode_style_full, 57: dwgtab.decode_ltype, 82: dwgent.decode_layout})
tot = collections.defaultdict(lambda: [0, 0, 0]); firstbad = {}
for p in sorted(glob.glob('corpus/AC10*.dwg')):
    v = p.split('/')[-1][:6]
    if v not in ('AC1018', 'AC1024', 'AC1027', 'AC1032'): continue
    try: d = dwgload.load(open(p, 'rb').read())
    except Exception as e: print('ERR', p, e); continue
    for h, o in d['objects'].items():
        dec = DECODERS.get(o.type)
        if not dec: continue
        k = (v, o.type)
        try:
            dec(o)
            end = dwgent.LAST_READER.p; exp = dwgent.expected_end(o)
            if end == exp or (v == 'AC1018' and 0 <= exp - end < 8): tot[k][0] += 1
            else:
                tot[k][1] += 1; firstbad.setdefault(k, (p.split('/')[-1][:14], h, end, exp))
        except Exception as ex:
            tot[k][2] += 1; firstbad.setdefault(k, (p.split('/')[-1][:14], h, repr(ex)[:50]))
with open('out/selfcheck.tsv', 'w') as f:
    f.write('version\ttype\tok\tbad\texc\tfirst_problem\n')
    for k in sorted(tot):
        f.write('%s\t%d\t%d\t%d\t%d\t%s\n' % (k[0], k[1], *tot[k], firstbad.get(k, '')))
print('done')
