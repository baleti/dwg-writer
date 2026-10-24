#!/usr/bin/env python3
"""chk_attribs.py FILE.dwg : INSERT attributes, parser (ATTRIB entities owned by the INSERT) vs AutoCAD 'attrs' per INSERT handle: multiset of (tag, value, height, layer, invisible). Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel, dwg2text
def norm(t): return ' '.join(dwg2text.strip_mtext(t).split()) if '\\' in t else ' '.join(t.split())
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
by = collections.defaultdict(collections.Counter)
for b, e in m.entities():
    if e['kind'] == 'ATTRIB': by[e['owner']][(e['tag'].upper(), norm(e['text']), round(e['height'], 4), e['layer'], bool((e.get('attflags') or 0) & 1))] += 1
res = collections.Counter(); first = {}
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] != 'INSERT' or not isinstance(e['h'], str) or not e.get('attrs'): continue
        want = collections.Counter((a['tag'].upper(), ' '.join(a['s'].split()), round(a['h'], 4), a['layer'], bool(a['invisible'])) for a in e['attrs'])
        got = by.get(int(e['h'], 16), collections.Counter())
        if want == got: res['ok'] += 1
        else: res['bad'] += 1; first.setdefault('x', (e['h'], list((want - got).items())[:2], list((got - want).items())[:2]))
print(json.dumps({'res': dict(res), 'first': first}, default=str))
