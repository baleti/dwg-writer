#!/usr/bin/env python3
"""usage: counts.py oracle-out/<stem>/dump.json [--space model|paper|blocks|all]
Prints entity counts per DXF type (JSON) from the AutoCAD dump, for diffing against our parser."""
import json,sys,collections
d=json.load(open(sys.argv[1])); sp=sys.argv[3] if len(sys.argv)>3 else 'all'
c=collections.Counter()
for b in d['blocks']:
    kind='model' if b['name']=='*Model_Space' else 'paper' if b['layout'] else 'blocks'
    if sp in('all',kind):
        for k,v in b['entity_counts'].items(): c[k]+=v
for k,v in sorted(c.items()): print(f'{k}\t{v}')
