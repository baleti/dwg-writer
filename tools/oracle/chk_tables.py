#!/usr/bin/env python3
"""chk_tables.py FILE.dwg : symbol tables (layers, text styles, linetypes, dimstyles), parser vs AutoCAD dump, matched by name. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
res = collections.Counter(); first = {}
def close(a, b): return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
def note(kind, name, field, a, b):
    res[(kind, field)] += 1; first.setdefault((kind, field), (name, a, b))
def lw_code(s):  # "LineWeight009" -> 9 ; ByLayer etc ignored
    try: return int(s.replace('LineWeight', ''))
    except ValueError: return None
def tab(x): return x() if callable(x) else x
LT = {k.lower(): v for k, v in tab(m.ltypes).items()}
ours = {v['name']: v for v in tab(m.layer_table).values()}
names_o = {l['name'] for l in d['layers']}
for n in set(ours) ^ names_o: note('layer', n, 'name', n in ours, n in names_o)
for l in d['layers']:
    o = ours.get(l['name'])
    if not o: continue
    res['layer_ok_checked'] += 1
    if o['frozen'] != l['IsFrozen']: note('layer', l['name'], 'frozen', o['frozen'], l['IsFrozen'])
    if o['off'] != l['IsOff']: note('layer', l['name'], 'off', o['off'], l['IsOff'])
    if o['locked'] != l['IsLocked']: note('layer', l['name'], 'locked', o['locked'], l['IsLocked'])
    if o['plot'] != l['IsPlottable']: note('layer', l['name'], 'plot', o['plot'], l['IsPlottable'])
    if (o['ltype'] or '').lower() != l['LinetypeObjectId']['n'].lower(): note('layer', l['name'], 'ltype', o['ltype'], l['LinetypeObjectId']['n'])
    if l['Color']['method'] == 'ByAci' and abs(o['color']) != l['Color']['index']: note('layer', l['name'], 'color', o['color'], l['Color']['index'])
    lw = lw_code(l['LineWeight'])
    if lw is not None and o['lineweight_mm'] is not None and abs(o['lineweight_mm'] * 100 - lw) > 1: note('layer', l['name'], 'lweight', o['lineweight_mm'], lw)
ours_s = {k.lower(): v for k, v in tab(m.styles).items()}
for s in d['textstyles']:
    o = ours_s.get(s['name'].lower())
    if not o: note('style', s['name'], 'missing', None, None); continue
    if o['font'].lower() != s['FileName'].lower(): note('style', s['name'], 'font', o['font'], s['FileName'])
    if o['bigfont'].lower() != s['BigFontFileName'].lower(): note('style', s['name'], 'bigfont', o['bigfont'], s['BigFontFileName'])
    if not close(o['width_factor'], s['XScale']): note('style', s['name'], 'width', o['width_factor'], s['XScale'])
    if not close(o['oblique'], s['ObliquingAngle']): note('style', s['name'], 'oblique', o['oblique'], s['ObliquingAngle'])
    if not close(o['fixed_height'], s['TextSize']): note('style', s['name'], 'height', o['fixed_height'], s['TextSize'])
for t in d['linetypes']:
    o = LT.get(t['name'].lower())
    if not o: note('ltype', t['name'], 'missing', None, None); continue
    if len(o['dashes']) != t['num_dashes']: note('ltype', t['name'], 'ndash', len(o['dashes']), t['num_dashes'])
    elif not close(o['pattern_length'], t['pattern_length']): note('ltype', t['name'], 'length', o['pattern_length'], t['pattern_length'])
ours_d = {k.lower(): v for k, v in tab(m.dimstyles).items()}
for s in d['dimstyles']:
    o = ours_d.get(s['name'].lower())
    if not o: note('dimstyle', s['name'], 'missing', None, None); continue
    for var in ('DIMSCALE', 'DIMTXT', 'DIMASZ', 'DIMEXO', 'DIMDLI', 'DIMEXE', 'DIMTAD', 'DIMDEC', 'DIMLFAC', 'DIMGAP'):
        a = o.get(var); b = s.get(var.capitalize())
        if a is None or b is None: continue
        if not close(float(a), float(b)): note('dimstyle', s['name'], var, a, b)
print({'/'.join(k) if isinstance(k, tuple) else k: v for k, v in res.items()}, {'/'.join(k): v for k, v in first.items()})
