"""selfcheck.py file.dwg : for every decodable entity, does the decoder end exactly where the main data ends? (oracle-free validation)"""
import sys, collections, dwgload, dwgent, dwgmodel
d = dwgload.load(open(sys.argv[1], 'rb').read())
ok = collections.Counter(); bad = collections.Counter(); exc = collections.Counter(); first = {}
import dwgfmt as F
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
clsmap = {c['num']: c['dxf'] for c in m.classes()}
for h, o in d['objects'].items():
    dec = dwgmodel.ENT_DECODERS.get(o.type)
    if not dec and o.type >= 500: dec = dwgmodel.CLASS_DECODERS.get(clsmap.get(o.type))
    if not dec: continue
    try:
        e = dec(o)
        end = dwgent.LAST_READER.p
        exp = dwgent.expected_end(o)
        # text-like decoders consume the string area separately; accept end <= expected within padding bits
        if end == exp or (exp - end) in range(0, 8) and exp - end >= 0 and o.ver in ('AC1015', 'AC1018'):
            ok[o.type] += 1
        else:
            bad[o.type] += 1; first.setdefault(o.type, (h, end, exp))
    except Exception as ex:
        exc[o.type] += 1; first.setdefault(o.type, (h, repr(ex)[:60]))
for t in sorted(set(ok) | set(bad) | set(exc)):
    print(t, 'ok', ok[t], 'bad', bad[t], 'exc', exc[t], first.get(t, ''))
