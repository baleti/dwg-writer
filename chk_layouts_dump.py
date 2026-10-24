"""chk_layouts_dump.py FILE.dwg DUMP.json : LAYOUT plot settings of Model.layouts() vs dump.json by layout name (names, tab order, media, printer, style sheet, paper, margins, origin, window; rotation and plot type code pairs)."""
import sys, json, collections, dwgmodel
d = json.load(open(sys.argv[2])); m = dwgmodel.Model(open(sys.argv[1], 'rb').read())
ours = {l['name']: l for l in m.layouts()}
ok = collections.Counter(); bad = collections.Counter(); ex = {}; pairs = collections.Counter()
def cmp(k, a, b, tol=1e-4):
    g = (abs(a - b) <= tol * max(1, abs(b))) if isinstance(b, (int, float)) and not isinstance(b, bool) else str(a).lower() == str(b).lower()
    (ok if g else bad)[k] += 1
    if not g: ex.setdefault(k, (a, b))
for s in d['layouts']:
    o = ours.get(s['LayoutName'])
    if o is None: bad['missing'] += 1; continue
    cmp('tab', o['tab_order'], s['TabOrder'])
    if 'paper_size' not in o: ok['nosettings'] += 1; continue
    cmp('media', o['paper_size'], s['CanonicalMediaName']); cmp('printer', o['printer'], s['PlotConfigurationName']); cmp('style', o['style_sheet'], s['CurrentStyleSheet'])
    cmp('origin_x', o['plot_origin'][0], s['PlotOrigin'][0], 1e-3); cmp('origin_y', o['plot_origin'][1], s['PlotOrigin'][1], 1e-3)
    mn, mx = s['PlotPaperMargins']['min'], s['PlotPaperMargins']['max']
    cmp('margin_l', o['margins'][0], mn[0], 1e-3); cmp('margin_b', o['margins'][1], mn[1], 1e-3); cmp('margin_r', o['margins'][2], mx[0], 1e-3); cmp('margin_t', o['margins'][3], mx[1], 1e-3)
    cmp('paper_w', o['paper'][0], s['PlotPaperSize'][0], 1e-3); cmp('paper_h', o['paper'][1], s['PlotPaperSize'][1], 1e-3)
    pairs[('rot', o['rotation'], s['PlotRotation'])] += 1; pairs[('type', o['plot_type'], s['PlotType'])] += 1
    pairs[('units', o['paper_units'], s['PlotPaperUnits'])] += 1
print('ok', sum(ok.values()), 'bad', dict(bad)); print('first', ex); print('pairs', dict(pairs))
