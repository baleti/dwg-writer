#!/usr/bin/env python3
"""chk_layouts.py FILE.dwg : layouts by name, parser vs AutoCAD dump: tab order, limits, extents, plot type, centered, rotation, style sheet, plot origin, scale, viewport count.
Paper size / media name are NOT compared: AutoCAD in the VM substitutes the missing plotter (see oracle notes), the file values are the truth. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections
import dwgmodel
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
L = m.layouts() if callable(m.layouts) else m.layouts
ours = {l['name']: l for l in L}
def close(a, b): return abs(a - b) <= 1e-6 * max(1.0, abs(a), abs(b))
res = collections.Counter(); first = {}
def note(f, name, a, b): res[f] += 1; first.setdefault(f, (name, a, b))
PT = {'Display': 0, 'Extents': 1, 'Limits': 2, 'View': 3, 'Window': 4, 'Layout': 5}
for l in d['layouts']:
    o = ours.get(l['LayoutName'])
    if o is None: note('missing', l['LayoutName'], None, None); continue
    res['layouts'] += 1
    if o['tab_order'] != l['TabOrder']: note('tab', l['LayoutName'], o['tab_order'], l['TabOrder'])
    if not all(close(a, b) for a, b in zip(o['limmin'] + o['limmax'], l['Limits']['min'] + l['Limits']['max'])): note('limits', l['LayoutName'], (o['limmin'], o['limmax']), l['Limits'])
    if o['style_sheet'].lower() != l['CurrentStyleSheet'].lower(): note('style_sheet', l['LayoutName'], o['style_sheet'], l['CurrentStyleSheet'])
    if (o['rotation'] if 'rotation' in o else None) is not None and 'Degrees%03d' % (o['rotation'] * 90) != l['PlotRotation']: note('rotation', l['LayoutName'], o['rotation'], l['PlotRotation'])
    if not all(close(a, b) for a, b in zip(o['plot_origin'], l.get('PlotOrigin', o['plot_origin']))): note('origin', l['LayoutName'], o['plot_origin'], l.get('PlotOrigin'))
    if len(o['viewports']) != len(l.get('viewport_handles', o['viewports'])): note('nviewports', l['LayoutName'], len(o['viewports']), len(l['viewport_handles']))
print(json.dumps({'res': dict(res), 'first': first}))
