"""chk_dxfhandles.py STEM : entity handles of Model.entities() vs the entity handles of AutoCAD's drawing.dxf (BLOCKS + ENTITIES sections)."""
import sys, collections, dwgmodel
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].strip()) for i in range(0, len(L) - 1, 2)]
sec = None; blk = None; ents = {}; ctype = None; hnd = None; want_name = False
for c, v in pairs:
    if c == '0' and v == 'SECTION': sec = None; want_name = True; continue
    if c == '2' and want_name: sec = v; want_name = False; continue
    if c == '0' and v == 'ENDSEC': sec = None; continue
    if sec not in ('BLOCKS', 'ENTITIES'): continue
    if c == '0':
        ctype = v; hnd = None
        if v == 'BLOCK': blk = None
    elif c == '2' and ctype == 'BLOCK' and blk is None: blk = v
    elif c == '5' and ctype and hnd is None and ctype not in ('BLOCK', 'ENDBLK'):
        hnd = int(v, 16); ents[hnd] = (blk if sec == 'BLOCKS' else '*SPACE', ctype)
SKIP = ('VERTEX2D', 'VERTEX3D', 'SEQEND', 'ATTRIB', 'VERTEX_MESH', 'VERTEX_PFACE', 'VERTEX_PFACE_FACE')
m = dwgmodel.Model(open('corpus/%s.dwg' % stem, 'rb').read())
ours = {}
for bn, e in m.entities():
    if e['kind'] not in SKIP: ours[e['handle']] = (bn, e['kind'])
extra = [h for h in ours if h not in ents]
missing = [h for h in ents if h not in ours and ents[h][1] not in ('VERTEX', 'SEQEND', 'ATTRIB', 'VIEWPORT')]
print(stem, 'ours', len(ours), 'dxf', len(ents), 'ours not in dxf', len(extra), 'dxf not in ours', len(missing))
print(' extra kinds', collections.Counter(ours[h][1] for h in extra).most_common(6))
print(' missing kinds', collections.Counter(ents[h][1] for h in missing).most_common(6))
if len(sys.argv) > 2:
    wrong = sum(1 for h in ours if h in ents and ents[h][0] != '*SPACE' and not (ours[h][0] or '').startswith('*') and ents[h][0] != ours[h][0])
    print(' same handle, other block name (named blocks only):', wrong)
if len(sys.argv) > 2 and sys.argv[2] == 'show':
    import dwgr14
    for h in sorted(extra)[:12]:
        o = m.objs[h]; e = [e for bn, e in m.entities() if e['handle'] == h][0] if False else None
        print(hex(h), ours[h], 'entmode', m._entmode(o), [(c, hex(v)) for c, v in dwgr14.decode_entity(o)['handles'][:4]])
if len(sys.argv) > 2 and sys.argv[2] == 'extras':
    for h in sorted(extra)[:20]:
        print(hex(h), ours[h])
