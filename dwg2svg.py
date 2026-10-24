#!/usr/bin/env python3
"""dwg2svg.py FILE.dwg OUT_PREFIX [layout_index]: writes OUT_PREFIX_<layout>.svg for model space and each paper-space layout (viewports not yet applied)."""
import sys, math
import dwgscene
from xml.sax.saxutils import escape


def svg(prims, path, width=1400, bounds=None):
    xs = []; ys = []
    for p in prims:
        if p[0] == 'line':
            for x, y in p[1]: xs.append(x); ys.append(y)
        elif p[0] == 'text':
            xs.append(p[1][0]); ys.append(p[1][1])
        elif p[0] == 'hatch':
            for l in p[1]:
                for x, y in l: xs.append(x); ys.append(y)
    if not xs: return False
    xs.sort(); ys.sort()
    n = len(xs)
    # robust bounds: drop 0.5% outliers
    lo, hi = int(n * 0.005), max(int(n * 0.995) - 1, 0)
    x0, x1, y0, y1 = xs[lo], xs[hi], ys[lo], ys[hi]
    if bounds: x0, y0, x1, y1 = bounds
    w = max(x1 - x0, 1e-9); h = max(y1 - y0, 1e-9)
    sc = width / w
    H = h * sc
    def T(x, y): return ((x - x0) * sc, (y1 - y) * sc)
    o = ['<svg xmlns="http://www.w3.org/2000/svg" width="%d" height="%d" viewBox="0 0 %d %d"><rect width="100%%" height="100%%" fill="white"/>' % (width, H, width, H)]
    for p in prims:
        if p[0] == 'hatch':
            col = p[3] if isinstance(p[3], tuple) else dwgscene.ACI.get(p[3], (0, 0, 0))
            for l in p[1]:
                if len(l) > 2:
                    d = 'M' + ' L'.join('%.1f,%.1f' % T(*q) for q in l) + 'Z'
                    o.append('<path d="%s" fill="%s" fill-opacity="%s" stroke="none"/>' % (d, 'rgb%s' % (col,), '0.5' if p[4] else '0.15'))
    for p in prims:
        if p[0] == 'line' and len(p[1]) > 1:
            col = p[3] if isinstance(p[3], tuple) else dwgscene.ACI.get(p[3], (0, 0, 0))
            if col == (255, 255, 255): col = (0, 0, 0)
            d = 'M' + ' L'.join('%.1f,%.1f' % T(*q) for q in p[1])
            lw = p[4] if len(p) > 4 and p[4] else None
            sw = max(0.3, lw * 3.0) if lw else 0.6
            da = ''
            if len(p) > 5 and p[5]:
                dl = [max(x * sc, 0.5) for x in p[5]]
                if len(dl) % 2: dl = dl * 2
                da = ' stroke-dasharray="%s"' % ','.join('%.2f' % x for x in dl)
            o.append('<path d="%s" fill="none" stroke="rgb%s" stroke-width="%.2f"%s/>' % (d, (col,)[0].__str__(), sw, da))
        elif p[0] == 'text':
            col = p[6] if isinstance(p[6], tuple) else dwgscene.ACI.get(p[6], (0, 0, 0))
            if col == (255, 255, 255): col = (0, 0, 0)
            x, y = T(*p[1]); fs = max(p[2] * sc, 1.5)
            if fs > 400: continue
            import dwg2text
            t = dwg2text.strip_mtext(p[4]).replace('\n', ' ')
            o.append('<text x="%.1f" y="%.1f" font-size="%.1f" fill="rgb%s" transform="rotate(%.1f %.1f %.1f)" font-family="sans-serif">%s</text>' % (x, y, fs, col, -math.degrees(p[3]), x, y, escape(t[:200])))
    o.append('</svg>')
    open(path, 'w').write('\n'.join(o))
    return True


if __name__ == '__main__':
    sc = dwgscene.Scene(open(sys.argv[1], 'rb').read())
    pre = sys.argv[2]
    names = []
    for e in sc.m.layouts():
        names.append((e['name'], e['block_name']))
    done = []
    lays = sc.m.layouts()
    for i, lay in enumerate(lays):
        ln, bn = lay['name'], lay['block_name']
        prims = dwgscene.render_layout(sc, lay)
        ox, oy = lay.get('origin', (0.0, 0.0))
        bnd = None if ln.lower() == 'model' else (ox - 5, oy - 5, ox + lay['paper'][0] + 5, oy + lay['paper'][1] + 5)
        ok = svg(prims, '%s_%d.svg' % (pre, i), bounds=bnd)
        done.append((i, ln, bn, len(prims), ok))
    for d in done: print(d)
