"""chk_handles_dump.py FILE.dwg DUMP.json : entity handles of Model.entities() vs the per-block entity handles of AutoCAD's dump.json (for files without a drawing.dxf)."""
import sys, json, collections, dwgmodel
d = json.load(open(sys.argv[2]))
au = {}
for b in d['blocks']:
    for e in b.get('entities', []):
        if isinstance(e['h'], str): au[int(e['h'], 16)] = (b['name'], e['t'])  # MTEXT 'h' is the text height in the dump
SKIP = ('VERTEX2D', 'VERTEX3D', 'SEQEND', 'ATTRIB', 'VERTEX_MESH', 'VERTEX_PFACE', 'VERTEX_PFACE_FACE')
m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
ours = {}
for bn, e in m.entities():
    if e['kind'] not in SKIP + ('MTEXT', 'TEXT', 'ATTDEF'): ours[e['handle']] = (bn, e['kind'])
extra = [h for h in ours if h not in au]
missing = [h for h in au if h not in ours and au[h][1] not in ('VERTEX', 'SEQEND', 'ATTRIB', 'VIEWPORT')]
print('ours', len(ours), 'autocad', len(au), 'ours only', len(extra), 'autocad only', len(missing))
print(' ours-only kinds', collections.Counter(ours[h][1] for h in extra).most_common(8))
print(' autocad-only kinds', collections.Counter(au[h][1] for h in missing).most_common(8))
for h in sorted(extra)[:10]: print(' extra', hex(h), ours[h])
for h in sorted(missing)[:10]: print(' missing', hex(h), au[h])
