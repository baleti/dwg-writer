"""chk_layvp_dump.py : layout viewport handle lists of Model.layouts() vs AutoCAD's dump.json viewport_handles (files up to 8 MB)."""
import json, glob, os, dwgmodel, collections
c = collections.Counter(); ex = []
for f in sorted(glob.glob('oracle-out/*/dump.json')):
    st = f.split('/')[1]; p = 'corpus/%s.dwg' % st
    if not os.path.exists(p) or os.path.getsize(p) > 8e6: continue
    try:
        d = json.load(open(f)); m = dwgmodel.Model(open(p, 'rb').read()); ours = {l['name']: l for l in m.layouts()}
    except Exception:
        continue
    for l in d['layouts']:
        o = ours.get(l['LayoutName'])
        if not o: continue
        a = set(int(x, 16) for x in l.get('viewport_handles', [])); b = set(o['viewports'])
        c['layouts'] += 1; c['equal'] += a == b; c['ours_extra'] += bool(b - a); c['ours_missing'] += bool(a - b)
        if a != b and len(ex) < 8: ex.append((st, l['LayoutName'], sorted(a), sorted(b)))
print(dict(c)); [print(x) for x in ex]
