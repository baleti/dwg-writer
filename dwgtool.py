#!/usr/bin/env python3
"""dwgtool.py - small command line editor on dwgdoc (own code). Writes a new file, never modifies the input.
  dwgtool.py info IN.dwg
  dwgtool.py layers IN.dwg
  dwgtool.py new OUT.dwg SPEC.json [2000|2004|2010|2013|2018]   (drawing from a JSON description, see build())
  dwgtool.py attribs IN.dwg        (INSERTs with attributes: handle, block, {tag: value})
  dwgtool.py diff A.dwg B.dwg      (objects added / removed / changed by type; exit 1 when different)
  dwgtool.py edit IN.dwg OUT.dwg [--rename-layer OLD NEW]... [--layer-color NAME ACI]... [--layer-off NAME]... [--layer-freeze NAME]...
                                  [--move-layer NAME DX DY]... [--erase-layer NAME]... [--replace-text OLD NEW]...
                                [--layer-on N]... [--layer-thaw N]... [--layer-lock N]... [--layer-unlock N]... [--layer-noplot N]...
                                [--layer-lweight N HUNDREDTHS_MM]... [--change-layer FROM TO]... [--explode BLOCKNAME]... [--set-attrib BLOCK TAG VALUE]... [--purge-layers]
                                [--rename-layout OLD NEW]... [--layout-paper NAME W H]...
                                [--add-mleader TEXT TIPX TIPY LANDX LANDY LAYER]... (R2010+, clones an existing MULTILEADER for its style)
"""
import sys, collections
import dwgdoc, dwgxform


def ents(doc):
    for bn, bh in doc.blocks().items():
        if bn.startswith('*d') or bn.startswith('*u'): continue
        for h in doc.chain(bh):
            yield bn, h


def tup(v):
    return tuple(tup(x) for x in v) if isinstance(v, list) else v


def build(spec_path, out, year):
    """new: blank template + JSON spec {"layers": [{"name":..,"color":..}], "blocks": [{"name":..}], "entities": [{"type": "line", "p1": [0,0], "p2": [5,5], "layer": "A"}]};
    entity "type" X calls Doc.add_X with the remaining keys as keyword arguments (lists become tuples; positional parameter names as in WRITER.md)."""
    import json, os, inspect
    tpl = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'templates', 'blank_%s.dwg' % year)
    doc = dwgdoc.Doc(open(tpl, 'rb').read())
    spec = json.load(open(spec_path))
    for l in spec.get('layers', []): doc.add_layer(**{k: tup(v) for k, v in l.items()})
    for b in spec.get('blocks', []): doc.add_block(**{k: tup(v) for k, v in b.items()})
    for e in spec.get('entities', []):
        e = dict(e); fn = getattr(doc, 'add_' + e.pop('type'))
        fn(**{k: tup(v) for k, v in e.items()})
    open(out, 'wb').write(doc.save()); print('wrote', out, len(spec.get('entities', [])), 'entities')
    return 0


def main(a):
    if len(a) < 2: print(__doc__); return 2
    if a[0] == 'new' and len(a) >= 3: return build(a[2], a[1], a[3] if len(a) > 3 else '2018')
    cmd, src = a[0], a[1]
    doc = dwgdoc.Doc(open(src, 'rb').read())
    if cmd == 'info':
        print(doc.ver, 'objects', len(doc.objs), 'layers', len(doc.layers()), 'blocks', len(doc.blocks()), 'layouts', list(doc.layouts()))
        c = collections.Counter(doc.otype(h) for _, h in ents(doc)); print('entities by type', dict(c))
    elif cmd == 'attribs':
        for bn, h in ents(doc):
            if doc.otype(h) == 7 and doc.get(h)['has_attribs']:
                print('%x\t%s\t%s' % (h, doc.get(doc.get(h)['bheader'])['name'], doc.attributes(h)))
    elif cmd == 'diff':
        b = dwgdoc.Doc(open(a[2], 'rb').read())
        added = [h for h in b.objs if h not in doc.objs]; removed = [h for h in doc.objs if h not in b.objs]
        changed = [h for h in doc.objs if h in b.objs and doc.objs[h].raw != b.objs[h].raw]
        for name, hs, src in (('added', added, b), ('removed', removed, doc), ('changed', changed, b)):
            c = collections.Counter(src.otype(h) for h in hs)
            print('%-8s %6d  by type %s' % (name, len(hs), dict(sorted(c.items()))))
        return 0 if not (added or removed or changed) else 1
    elif cmd == 'layers':
        use = collections.Counter(doc.get(h)['layer'] for _, h in ents(doc))
        for n, h in sorted(doc.layers().items()):
            d = doc.get(h); print('%-40s flags=%#x color=%s entities=%d' % (d['name'], d['flags'], d['color'][0] or hex(d['color'][1] or 0), use.get(h, 0)))
    elif cmd == 'edit':
        out = a[2]; i = 3
        lay = lambda n: doc.layer_handle(n)
        while i < len(a):
            o = a[i]
            if o == '--rename-layer': doc.set_layer(a[i + 1], new_name=a[i + 2]); i += 3
            elif o == '--layer-color': doc.set_layer(a[i + 1], color=int(a[i + 2])); i += 3
            elif o == '--layer-off': doc.set_layer(a[i + 1], off=True); i += 2
            elif o == '--layer-freeze': doc.set_layer(a[i + 1], frozen=True); i += 2
            elif o == '--layer-on': doc.set_layer(a[i + 1], off=False); i += 2
            elif o == '--layer-thaw': doc.set_layer(a[i + 1], frozen=False); i += 2
            elif o == '--layer-lock': doc.set_layer(a[i + 1], locked=True); i += 2
            elif o == '--layer-unlock': doc.set_layer(a[i + 1], locked=False); i += 2
            elif o == '--layer-noplot': doc.set_layer(a[i + 1], plot=False); i += 2
            elif o == '--layer-lweight': doc.set_layer(a[i + 1], lineweight=int(a[i + 2])); i += 3
            elif o == '--change-layer':
                src, dst = lay(a[i + 1]), lay(a[i + 2]); n = 0
                for bn, h in list(ents(doc)):
                    if doc.get(h)['layer'] == src: doc.set_props(h, layer=dst); n += 1
                print(o, a[i + 1], '->', a[i + 2], n, 'entities'); i += 3
            elif o == '--purge-layers': print(o, doc.purge_layers()); i += 1
            elif o == '--set-attrib':
                bhh = doc.blocks().get(a[i + 1].lower()); n = 0
                for _, h in list(ents(doc)):
                    if bhh and doc.otype(h) == 7 and doc.get(h)['bheader'] == bhh and doc.set_attrib(h, a[i + 2], a[i + 3]): n += 1
                print(o, a[i + 1], a[i + 2], '=', a[i + 3], n, 'inserts'); i += 4
            elif o == '--explode':
                bn = a[i + 1].lower(); bhh = doc.blocks().get(bn); n = skipped = 0
                for _, h in list(ents(doc)):
                    if bhh is None or doc.otype(h) != 7 or doc.get(h)['bheader'] != bhh: continue
                    try: doc.explode(h); n += 1
                    except NotImplementedError: skipped += 1
                print(o, a[i + 1], n, 'exploded' + (', %d skipped (attributes / odd scale)' % skipped if skipped else '')); i += 2
            elif o == '--rename-layout': doc.rename_layout(a[i + 1], a[i + 2]); print(o, a[i + 1], '->', a[i + 2]); i += 3
            elif o == '--layout-paper': doc.set_layout(a[i + 1], paper=(float(a[i + 2]), float(a[i + 3]))); print(o, a[i + 1], a[i + 2], 'x', a[i + 3]); i += 4
            elif o == '--add-mleader':
                h = doc.add_mleader(a[i + 1], (float(a[i + 2]), float(a[i + 3])), (float(a[i + 4]), float(a[i + 5])), layer=a[i + 6], to_right=float(a[i + 4]) >= float(a[i + 2]))
                print(o, a[i + 1], hex(h)); i += 7
            elif o == '--replace-text': print(o, a[i + 1], '->', a[i + 2], doc.replace_text(a[i + 1], a[i + 2]), 'objects'); i += 3
            elif o in ('--move-layer', '--erase-layer'):
                lh = lay(a[i + 1]); n = 0; skipped = 0
                for bn, h in list(ents(doc)):
                    if doc.get(h)['layer'] != lh: continue
                    if o == '--erase-layer': doc.erase(h)
                    else:
                        try: doc.transform(h, dwgxform.Transform.translate(float(a[i + 2]), float(a[i + 3])))
                        except NotImplementedError: skipped += 1; continue      # e.g. ACIS solids
                    n += 1
                print(o, a[i + 1], n, 'entities' + (', %d not movable (skipped)' % skipped if skipped else ''))
                i += 2 if o == '--erase-layer' else 4
            else: print('unknown option', o); return 2
        open(out, 'wb').write(doc.save()); print('wrote', out)
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
