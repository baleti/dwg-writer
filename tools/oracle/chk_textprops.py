#!/usr/bin/env python3
"""chk_textprops.py FILE.dwg : TEXT / MTEXT properties, parser vs AutoCAD dump. Oracle 'h' is the height (not the handle), so entities are matched by (kind, position, string)
and only unique keys are compared. TEXT: height, rotation, width factor, oblique, style. MTEXT: contents, text height, width, attachment, style, extents size. Run with PYTHONPATH=~/dwg-research."""
import sys, os, json, collections, math
import dwgmodel, dwgscene
p = sys.argv[1]; stem = os.path.basename(p)[:-4]
d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
m = dwgmodel.Model(open(p, 'rb').read())
def close(a, b, t=1e-6): return abs(a - b) <= t * max(1.0, abs(a), abs(b))
ora = collections.defaultdict(list)
for b in d['blocks']:
    for e in b.get('entities', []):
        if e['t'] == 'TEXT':
            ap = e['al'] if e.get('al') and (e['al'][0] or e['al'][1]) else e['p']
            ora[('TEXT', e['s'], round(ap[0], 2), round(ap[1], 2))].append(e)
        elif e['t'] == 'MTEXT': ora[('MTEXT', e['contents'], round(e['p'][0], 2), round(e['p'][1], 2))].append(e)
res = collections.Counter(); first = {}
def note(f, a, b): res[f] += 1; first.setdefault(f, (a, b))
ATT = {1: 'TopLeft', 2: 'TopCenter', 3: 'TopRight', 4: 'MiddleLeft', 5: 'MiddleCenter', 6: 'MiddleRight', 7: 'BottomLeft', 8: 'BottomCenter', 9: 'BottomRight'}
for b, e in m.entities():
    if e['kind'] == 'TEXT':
        ip = e['align'] if e.get('align') else e['ins']
        w = dwgscene.ocs_to_wcs((ip[0], ip[1], e.get('elev', 0.0)), tuple(e.get('ext', (0, 0, 1))))
        k = ('TEXT', e['text'], round(w[0], 2), round(w[1], 2))
    elif e['kind'] == 'MTEXT': k = ('MTEXT', e['text'], round(e['ins'][0], 2), round(e['ins'][1], 2))
    else: continue
    c = ora.get(k)
    if not c or len(c) != 1: res['unmatched_or_dup'] += 1; continue
    o = c[0]; errs = []
    if e['kind'] == 'TEXT':
        if not close(e['height'], o['h']): errs.append('height')
        if not close(math.fmod(e['rot'], 2 * math.pi), math.fmod(o['rot'], 2 * math.pi), 1e-6) and not close(abs(e['rot'] - o['rot']), 2 * math.pi, 1e-6): errs.append('rot')
        if not close(e['widthf'], o['wf']): errs.append('widthf')
        if not close(e['oblique'], o['obl'], 1e-6): errs.append('oblique')
        if e['style'].lower() != o['style'].lower(): errs.append('style')
    else:
        if e['text_height'] and not close(e['text_height'], o['h']): errs.append('height')
        if not close(e['width'], o['width']): errs.append('width')
        if ATT.get(e['attachment']) != o['att']: errs.append('attach')
        if e['style'].lower() != o['style'].lower(): errs.append('style')
    for x in errs: note(x, e['kind'], e.get('handle'))
    res['ok' if not errs else 'bad'] += 1
print(json.dumps({'res': dict(res), 'first': first}, default=str))
