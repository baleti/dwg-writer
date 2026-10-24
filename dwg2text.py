#!/usr/bin/env python3
"""dwg2text.py FILE.dwg [FILE ...] [--json] [--jsonl] [--text-only] : text/metadata extraction for indexing (own parser, no external tools).

Stable extraction API (schema_version 1). One JSON object per file (--json: pretty, --jsonl: one line per file, for batches):
  file, schema_version, version (AC10xx), status ('ok' | 'partial' | 'unsupported' | 'error'), errors [str], codepage, size, seconds,
  summary {title, subject, author, keywords, comments, last_saved_by, revision, hyperlink_base}, app [str], header {INSUNITS, LTSCALE, ...},
  layers [str], blocks [str], layouts [{name, paper, size_mm, viewports}], entity_counts {KIND: n},
  text {block_name: [str]}                        TEXT and MTEXT (MTEXT formatting stripped), grouped by owner block,
  attributes [{kind, tag, value, layer, block, insert}]  ATTRIB (instance values; insert = name of the inserted block) and ATTDEF (defaults; block = defining block),
  tables [{handle, block, layer, x, y, texts}]     ACAD_TABLE entities with the texts of their picture block (cell order as drawn),
  xrefs [{name, path, overlay, loaded}]            external references (block records flagged as xref),
  images [{path, count}]                           raster image files referenced by IMAGE entities,
  underlays [{kind, block, layer, path, sheet, x, y, scale}]   PDF/DGN/DWF underlay references (file path as stored),
  dimension_text [{block, text}]                  explicit dimension texts (not the default '<>' ones),
  proxy_text [{handle, cls, layer, text}]         strings recovered from custom proxy objects (Tangent TCH_* ...; no graphics exist for them),
  items [{kind, block, layer, text, x, y}]        flat list of every text-bearing entity (stable order), x/y in the block's coordinates.
Exit codes: 0 ok, 1 usage, 2 unsupported version (AC1021 until its container works, R12), 3 also for AC1012/AC1014 (partial entity coverage), 3 partial (some stage failed, output still printed),
4 unreadable file. Several files: exit code is the maximum."""
import sys, re, json, collections, struct, gc
from dwgtextfmt import strip_mtext


def summary_info(buf, info, ver, codepage):
    import dwgload
    import dwgmodel
    if 'AcDb:SummaryInfo' not in info['sections'] or not info['sections']['AcDb:SummaryInfo']['size']:
        return {}
    d = dwgload.section(buf, info, 'AcDb:SummaryInfo')
    p = 0
    out = {}
    names = ['title', 'subject', 'author', 'keywords', 'comments', 'last_saved_by', 'revision', 'hyperlink_base']
    try:
        for n in names:
            ln, = struct.unpack_from('<H', d, p); p += 2
            if ver == 'AC1018':
                raw = d[p:p + ln]; p += ln
                out[n] = dwgmodel.decode_tv(raw.rstrip(b'\0').decode('latin1'), codepage)
            else:
                raw = d[p:p + 2 * ln]; p += 2 * ln
                out[n] = raw.decode('utf-16le', 'replace').rstrip('\0')
    except struct.error:
        pass
    return {k: v for k, v in out.items() if v}


def app_info(buf, info):
    import dwgload
    if 'AcDb:AppInfo' not in info['sections'] or not info['sections']['AcDb:AppInfo']['size']:
        return []
    d = dwgload.section(buf, info, 'AcDb:AppInfo')
    strs = re.findall(rb'(?:[\x20-\x7e]\x00){4,}', d)
    return [s.decode('utf-16le') for s in strs][:12]



SUPPORTED = ('AC1009', 'AC1012', 'AC1014', 'AC1015', 'AC1018', 'AC1021', 'AC1024', 'AC1027', 'AC1032')


TEXT_ONLY = False
TEXT_TYPES = {1, 2, 3, 44, 7, 8} | set(range(20, 27))  # TEXT ATTRIB ATTDEF MTEXT INSERT MINSERT DIMENSIONs (the picture blocks carry no text of their own here)


def extract(path):
    import dwgmodel
    import time
    t0 = time.time()
    res = collections.OrderedDict(file=path, schema_version=1, status='ok', errors=[])
    try:
        buf = open(path, 'rb').read()
    except OSError as ex:
        res.update(status='error', errors=['read: %s' % ex]); return res, 4
    ver = bytes(buf[:6]).decode('latin1', 'replace')
    res['version'] = ver; res['size'] = len(buf)
    if ver not in SUPPORTED:
        res.update(status='unsupported', errors=['version %s not supported' % ver]); return res, 2
    try:
        m = dwgmodel.Model(buf)
    except Exception as ex:
        res.update(status='error', errors=['load: %r' % ex]); return res, 4
    res['codepage'] = m.codepage
    def stage(name, fn, default):
        try:
            return fn()
        except Exception as ex:
            res['errors'].append('%s: %r' % (name, ex)); res['status'] = 'partial'; return default
    if ver in ('AC1009', 'AC1012', 'AC1014'):
        res['summary'] = {}; res['app'] = []
        res['errors'].append('R12/R13/R14 reader is partial: no MLINE, header variables (R12: LTSCALE, TEXTSIZE, PDMODE only), plot settings or object properties'); res['status'] = 'partial'
    elif ver != 'AC1015':
        res['summary'] = stage('summary', lambda: summary_info(buf, m._info, ver, m.codepage), {})
        res['app'] = stage('app', lambda: app_info(buf, m._info), [])
    else:
        res['summary'] = {}; res['app'] = []
    def hdr():
        h = m.header()
        keep = ('INSUNITS', 'LTSCALE', 'PSLTSCALE', 'TEXTSIZE', 'DIMSCALE', 'DWGCODEPAGE', 'CLAYER_NAME', 'TEXTSTYLE_NAME', 'DIMSTYLE_NAME', 'CANNOSCALE', 'MSLTSCALE', 'CMLEADERSTYLE', 'CTABLESTYLE', 'LIGHTINGUNITS', 'MEASUREMENT')
        return {k: h[k] for k in keep if k in h and h[k] is not None}
    res['header'] = stage('header', hdr, {})
    if 'INSUNITS' in res['header']:
        import dwginsunits
        res['header']['INSUNITS_NAME'] = dwginsunits.name(res['header']['INSUNITS'])
    res['layers'] = sorted(set(n for h, n in m.layers.items() if h not in getattr(m, 'internal_layers', ())))
    res['blocks'] = sorted(set(n.split('~')[0] for n in m.blocks.values() if not n.startswith('*')))
    def lay():
        out = []
        for e in m.layouts():
            nm = dwgmodel.decode_tv(e['name'], m.codepage) if ver == 'AC1018' and e['name'] and not e['name'].isascii() and False else e['name']
            out.append(dict(name=nm, paper=e.get('paper_size'), size_mm=[round(x, 1) for x in e['paper']], viewports=len(e['viewports'])))
        return out
    res['layouts'] = stage('layouts', lay, [])
    counts = collections.Counter(); texts = collections.OrderedDict(); attrs = []; dims = []; items = []
    underlays = []; full_texts = {}; table_ents = []
    def ents():
        ins_name = {}
        for blk, e in m.entities(TEXT_TYPES if TEXT_ONLY else None):
            if e['kind'] == 'INSERT': ins_name[e['handle']] = (e.get('block_true_name') or e.get('block_ref') or '').split('~')[0]
        for blk, e in m.entities(TEXT_TYPES if TEXT_ONLY else None):
            k = e['kind']; counts[k] += 1
            if k == 'ACAD_TABLE' and e.get('block_ref'): table_ents.append((blk, e))
            if k.endswith('UNDERLAY'):
                ds = e.get('definition_strings') or ['', '']
                underlays.append(dict(kind=k, block=blk.split('~')[0] if blk else '?', layer=e.get('layer'), path=ds[0] if ds else '', sheet=ds[1] if len(ds) > 1 else '', x=e['ins'][0], y=e['ins'][1], scale=e['scale'][0]))
            bn = blk.split('~')[0] if blk else '?'
            lay_ = e.get('layer')
            pos = e.get('ins') or e.get('align') or e.get('text_mid') or (0, 0, 0)
            if k in ('TEXT', 'MTEXT'):
                t = e['text'] if k == 'TEXT' else strip_mtext(e['text'])
                if t.strip():
                    texts.setdefault(bn, []).append(t.strip()); full_texts.setdefault(blk, []).append(t.strip())
                    items.append(dict(kind=k, block=bn, layer=lay_, text=t.strip(), x=round(pos[0], 3), y=round(pos[1], 3)))
            elif k in ('ATTRIB', 'ATTDEF'):
                t = (e.get('text') or '').strip()
                if t or e.get('tag'):
                    attrs.append(dict(block=bn if k == 'ATTDEF' else None, insert=ins_name.get(e.get('owner')) if k == 'ATTRIB' else None, kind=k, tag=e.get('tag'), value=t, layer=lay_))
                    items.append(dict(kind=k, block=bn, layer=lay_, text=t, tag=e.get('tag'), x=round(pos[0], 3), y=round(pos[1], 3)))
            elif k in ('MULTILEADER', 'ACAD_TABLE'):
                for t in e.get('strings', []):
                    t = strip_mtext(t).strip()
                    if t:
                        it = dict(kind=k, block=bn, layer=lay_, text=t)
                        if e.get('text_loc'): it.update(x=round(e['text_loc'][0], 3), y=round(e['text_loc'][1], 3))
                        items.append(it); texts.setdefault(bn, []).append(t)
            elif k.startswith('DIM'):
                t = (e.get('user_text') or '').strip()
                if t and t != '<>':
                    dims.append(dict(block=bn, text=strip_mtext(t)))
                    items.append(dict(kind=k, block=bn, layer=lay_, text=strip_mtext(t), x=round(pos[0], 3), y=round(pos[1], 3)))
    stage('entities', ents, None)
    def ptx():
        out = []
        for h, cls, lay_, t in m.proxy_texts():
            out.append(dict(handle=h, cls=cls, layer=lay_, text=t))
            items.append(dict(kind='PROXY_TEXT', block='?', layer=lay_, text=t, cls=cls))
        return out
    res['proxy_text'] = stage('proxy_text', ptx, [])
    def tbl():
        out = []
        for h, cls, t in m.object_strings(('TABLECONTENT',)):
            t = strip_mtext(t).strip()
            if t: out.append(dict(handle=h, cls=cls, text=t)); items.append(dict(kind='TABLE_CELL', block='?', layer=None, text=t))
        return out
    res['table_text'] = stage('table_text', tbl, [])
    res['entity_counts'] = dict(counts.most_common())
    res['text'] = texts
    res['attributes'] = attrs
    res['underlays'] = underlays
    res['tables'] = [dict(handle=e['handle'], block=(b or '?').split('~')[0], layer=e.get('layer'), x=round(e['ins'][0], 3), y=round(e['ins'][1], 3), texts=[t for t in full_texts.get(e['block_ref'], [])]) for b, e in table_ents]
    def xr():
        import dwgtab
        out = []
        for h, o in m.objs.items():
            if o.type == 49:
                d = dwgtab.decode_block_header(o)
                if d['is_xref']:
                    out.append(dict(name=m.blocks.get(h) or d['name'], path=decode_tv_(d['xref_path']), overlay=d['overlaid'], loaded=d['loaded']))
        return out
    decode_tv_ = lambda t: dwgmodel.decode_tv(t, m.codepage) if isinstance(t, str) else t
    res['xrefs'] = stage('xrefs', xr, []) if ver not in ('AC1009', 'AC1012', 'AC1014') else []
    def imgs():
        seen = {}
        for blk, e in m.entities(frozenset()):  # IMAGE is class based (type >= 500): no built-in decoder needed
            if e['kind'] == 'IMAGE' and e.get('image_path'): seen[e['image_path']] = seen.get(e['image_path'], 0) + 1
        return [dict(path=p_, count=n_) for p_, n_ in seen.items()]
    res['images'] = stage('images', imgs, [])
    res['dimension_text'] = dims
    res['items'] = items
    res['seconds'] = round(time.time() - t0, 2)
    return res, (3 if res['status'] == 'partial' else 0)


def print_text(res):
    print('# %s  %s  codepage %s  %s bytes' % (res['file'], res.get('version'), res.get('codepage'), res.get('size')))
    for k, v in res.get('summary', {}).items(): print('%s: %s' % (k, v))
    print('layers: ' + ', '.join(res.get('layers', [])))
    print('blocks: ' + ', '.join(res.get('blocks', [])))
    for lay in res.get('layouts', []): print('layout: %s | %s | viewports %d' % (lay['name'], lay['paper'], lay['viewports']))
    print('entities: ' + ', '.join('%s %d' % kv for kv in res.get('entity_counts', {}).items()))
    for blk, ts in res.get('text', {}).items():
        print('--- text in %s' % blk)
        for t in ts: print(t)
    if res.get('attributes'):
        print('--- attributes')
        for a in res['attributes']: print('%s=%s' % (a['tag'], a['value']))
    if res.get('dimension_text'):
        print('--- dimension text')
        for d in res['dimension_text']: print(d['text'])
    for e in res.get('errors', []): print('! ' + e, file=sys.stderr)


def main(argv):
    files = [a for a in argv if not a.startswith('--')]
    if not files:
        print(__doc__, file=sys.stderr); return 1
    global TEXT_ONLY
    TEXT_ONLY = '--text-only' in argv  # skip geometry decoders: entity_counts then only covers text-bearing kinds (about 2x faster, much less memory)
    mode = 'jsonl' if '--jsonl' in argv else ('json' if '--json' in argv else 'text')
    worst = 0
    gc.disable()  # object-heavy parsing: cyclic GC passes dominate otherwise
    for p in files:
        gc.collect()
        try:
            res, code = extract(p)
        except Exception as ex:  # never let one file kill a batch
            res, code = collections.OrderedDict(file=p, schema_version=1, status='error', errors=['internal: %r' % ex]), 4
        worst = max(worst, code)
        if mode == 'jsonl': print(json.dumps(res, ensure_ascii=False, separators=(',', ':')))
        elif mode == 'json': print(json.dumps(res, ensure_ascii=False, indent=1))
        else: print_text(res)
        sys.stdout.flush()
    return worst


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))
