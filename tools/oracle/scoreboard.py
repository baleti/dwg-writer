#!/usr/bin/env python3
"""scoreboard.py : summarise the oracle-out/chk_*_all.txt sweep files into one table (ok / bad per checker). Run the sweeps first (see README)."""
import sys, os, json, re, glob, collections, ast
root = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out')
rows = []
for f in sorted(glob.glob(os.path.join(root, 'chk_*_all.txt'))):
    name = os.path.basename(f)[4:-8]
    tot = collections.Counter(); files = 0; bad_files = 0
    for l in open(f, errors='replace'):
        if l.startswith('{'):
            try: d = json.loads(l)
            except ValueError:
                try: d = ast.literal_eval(l[:l.index('}') + 1])
                except (ValueError, SyntaxError): continue
            r = d.get('res', d); files += 1
            if name == 'tables': r = {'ok': 1 if len([k for k in r if k != 'layer_ok_checked']) == 0 else 0, 'bad': 0 if len([k for k in r if k != 'layer_ok_checked']) == 0 else 1}
            if name == 'viewports': r = {'ok': r.get('ok', 0), 'bad': r.get('bad', 0)}
            tot.update({k: v for k, v in r.items() if isinstance(v, int)})
            if r.get('bad') or r.get('missing'): bad_files += 1
    ok = tot.get('ok', 0) + tot.get('layouts', 0); bad = tot.get('bad', 0) + tot.get('missing', 0)
    rows.append((name, files, ok, bad, bad_files))
print('%-12s %6s %9s %7s %9s' % ('check', 'files', 'ok', 'bad', 'badfiles'))
for r in rows: print('%-12s %6d %9d %7d %9d' % r)
