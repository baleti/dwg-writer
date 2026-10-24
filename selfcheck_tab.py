import sys, collections, dwgload, dwgent, dwgtab
DEC = {49: dwgtab.decode_block_header, 51: dwgtab.decode_layer, 53: dwgtab.decode_style_full, 57: dwgtab.decode_ltype}
d = dwgload.load(open(sys.argv[1], 'rb').read())
ok = collections.Counter(); bad = collections.Counter(); exc = collections.Counter(); first = {}
for h, o in d['objects'].items():
    dec = DEC.get(o.type)
    if not dec: continue
    try:
        e = dec(o); end = dwgent.LAST_READER.p; exp = dwgent.expected_end(o)
        if end == exp or (o.ver in ('AC1015', 'AC1018') and 0 <= exp - end < 8): ok[o.type] += 1
        else: bad[o.type] += 1; first.setdefault(o.type, (h, end, exp))
    except Exception as ex:
        exc[o.type] += 1; first.setdefault(o.type, (h, repr(ex)[:50]))
for t in sorted(set(ok) | set(bad) | set(exc)): print(t, 'ok', ok[t], 'bad', bad[t], 'exc', exc[t], first.get(t, ''))
