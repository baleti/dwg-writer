"""chk_generic2.py FILE: every entity-like object must survive decode_generic/encode_generic bit-exactly (own code)"""
import sys, collections
import dwgload, dwgcodec
buf = open(sys.argv[1], 'rb').read()
d = dwgload.load(buf)
st = collections.defaultdict(lambda: [0, 0, 0])
for h, o in d['objects'].items():
    if o.type in dwgcodec.TAB.OBJ or o.type >= 49 and o.type not in (77, 78, 34, 35, 36, 44, 45, 40, 41, 46, 47) or o.type in (42, 48): continue
    try:
        dec = dwgcodec.decode_generic(o)
    except Exception as e:
        st[o.type][2] += 1; continue
    st[o.type][0] += 1
    if dwgcodec.encode_generic(d['version'], dec) == o.raw: st[o.type][1] += 1
print(d['version'], 'types', len(st), 'bad:', {t: v for t, v in st.items() if v[0] != v[1]})
