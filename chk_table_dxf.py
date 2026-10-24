"""chk_table_dxf.py STEM : ACAD_TABLE cell texts (DXF group 302/1 inside the entity) vs the texts of the picture block (dwg2text 'tables'), per handle."""
import sys, re, collections, dwg2text
stem = sys.argv[1]
L = open('oracle-out/%s/drawing.dxf' % stem, errors='replace').read().split('\n')
pairs = [(L[i].strip(), L[i + 1].rstrip('\r')) for i in range(0, len(L) - 1, 2)]
tabs = {}; cur = None; sec = None; want = False
for c, v in pairs:
    if c == '0' and v.strip() == 'SECTION': want = True; continue
    if c == '2' and want: sec = v.strip(); want = False; continue
    if c == '0' and v.strip() == 'ENDSEC': sec = None
    if c == '0': cur = None; t = v.strip()
    if sec not in ('BLOCKS', 'ENTITIES'): continue
    if c == '0' and v.strip() == 'ACAD_TABLE': cur = {'txt': []}; pend = True
    elif cur is not None:
        if c == '5' and pend: tabs[int(v, 16)] = cur; pend = False
        elif c == '302': cur['txt'].append(v)
norm = lambda s: re.sub(r'\\[A-Za-z][^;]*;|[{}]|\\P', '', s).strip()
res = dwg2text.extract('corpus/%s.dwg' % stem)[0]
ours = {t['handle']: t['texts'] for t in res.get('tables', [])}
c = collections.Counter()
for h, d in tabs.items():
    c['tables'] += 1
    a = collections.Counter(norm(x) for x in d['txt'] if norm(x)); b = collections.Counter(norm(x) for x in ours.get(h, []) if norm(x))
    c['equal'] += a == b; c['dxf_cells'] += sum(a.values()); c['matched'] += sum((a & b).values())
print(stem, dict(c))
if '-v' in sys.argv:
    for h, d in tabs.items(): print(sorted(set(norm(x) for x in d['txt']) - set(norm(x) for x in ours.get(h, []))), sorted(set(norm(x) for x in ours.get(h, [])) - set(norm(x) for x in d['txt'])))
