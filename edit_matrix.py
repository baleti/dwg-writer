"""edit_matrix.py: automated edit matrix [entity type x operation x DWG version x real file] against the AutoCAD oracle (offline VM, via dwgq).
  edit_matrix.py run OUTDIR [--sample ~/dwg-edit-tests/sample.tsv] [--ops noop,move,...] [--seed N] [--limit N] [--files id,id]
  edit_matrix.py report OUTDIR      (aggregate pass rates -> stdout; EDIT-MATRIX.md is written by `report --md`)
Per file: oracle dump+audit of the original (cached), then ONE batch edit file with one operation on one entity of each type (distinct entities),
oracle dump+audit of the edited file, per-handle comparison against the expectation of the operation. If the batch fails to open / audits worse, every
operation is re-run alone (bisect) so the failure is attributed to a cell. Results: OUTDIR/results.jsonl (aggregate only; ids, never paths or client names).
Real drawings stay in ~/dwg-edit-tests (git-excluded), nothing is published."""
import os, sys, shutil, json, math, random, hashlib, subprocess, traceback, time, collections, argparse
import dwgdoc, dwgxform as X

HERE = os.path.dirname(os.path.abspath(__file__))
DWGQ = os.path.expanduser('~/dwg-research/tools/oracle/dwgq')
SRC = os.path.expanduser('~/dwg-edit-tests/src/')
ORIG = os.path.expanduser('~/dwg-edit-tests/o/')
TOP = ('*model_space', '*paper_space')


# ---------------------------------------------------------------- oracle
def oracle(path, out, tasks='audit,dump'):
    """run dwgq; returns (audit_text, dump dict or None). Cached when out/done.flag and out/input.sha match."""
    sha = hashlib.sha1(open(path, 'rb').read()).hexdigest()
    shaf = out + '/input.sha'
    if not (os.path.exists(out + '/dump.json') and os.path.exists(shaf) and open(shaf).read() == sha):
        os.makedirs(out, exist_ok=True)
        for _ in range(3):
            subprocess.run([DWGQ, 'run', path, '--tasks', tasks, '--out', out], capture_output=True, text=True, timeout=900)
            if os.path.exists(out + '/audit.log') or os.path.exists(out + '/dump.log'): break
            time.sleep(10)
        open(shaf, 'w').write(sha)
    return audit_text(out), load_dump(out)


def audit_text(out):
    try:
        log = open(out + '/audit.log', 'rb').read().decode('utf-16le', 'ignore').replace('\r', '')
    except OSError:
        return 'no audit log'
    if 'Total errors found 0 fixed 0' in log: return None
    for l in log.split('\n'):
        if 'Total errors' in l or 'not valid' in l or 'ERROR' in l: return l.strip()[:200]
    return 'unknown failure'


def _pairs(pairs):
    """the oracle writes 'h' twice for TEXT/MTEXT/VIEWPORT (handle, then height): keep the handle as 'h', the later value as 'h2'"""
    d = {}
    for k, v in pairs:
        if k in d and k == 'h': k = 'h2'
        d[k] = v
    return d


def load_dump(out):
    try:
        d = json.load(open(out + '/dump.json', encoding='utf-8-sig'), object_pairs_hook=_pairs)
    except (OSError, ValueError):
        return None
    ents = {}; per_block = {}
    for b in d.get('blocks', []):
        top = b['name'].lower() in TOP or b['name'].lower().startswith('*paper_space')
        for e in b.get('entities', []):
            e['_blk'] = b['name']; e['_top'] = top; ents[e['h']] = e
    d['ents'] = ents
    return d


# ---------------------------------------------------------------- expectations
def bbox_tf(ext, f):
    xs, ys = [], []
    for x in (ext[0], ext[3]):
        for y in (ext[1], ext[4]):
            a, b = f(x, y); xs.append(a); ys.append(b)
    return [min(xs), min(ys), ext[2], max(xs), max(ys), ext[5]]


def close(a, b, tol=1e-6):
    return all(abs(p - q) <= tol * max(1.0, abs(p), abs(q)) + 1e-6 for p, q in zip(a, b))


def mk_tf(kind):
    """returns (apply(doc,h) transform, python mapping for xy)"""
    if kind == 'move': return X.Transform.translate(1234.5, -321.25), lambda x, y: (x + 1234.5, y - 321.25), lambda z: z
    if kind == 'rot90': return X.Transform.rotate((0, 0), math.pi / 2), lambda x, y: (-y, x), lambda z: z
    if kind == 'rot180': return X.Transform.rotate((0, 0), math.pi), lambda x, y: (-x, -y), lambda z: z
    if kind == 'scale2': return X.Transform.scale((0, 0), 2.0), lambda x, y: (2 * x, 2 * y), lambda z: 2 * z
    if kind == 'mirrorx': return X.Transform.mirror((0, 0), (1, 0)), lambda x, y: (x, -y), lambda z: z
    if kind == 'mirrory': return X.Transform.mirror((0, 0), (0, 1)), lambda x, y: (-x, y), lambda z: z
    raise KeyError(kind)


TEXTY = ('TEXT', 'MTEXT', 'INSERT', 'DIMENSION', 'ATTDEF', 'ATTRIB', 'MULTILEADER', 'MLEADER', 'ACAD_TABLE', 'TABLE')


def chk_tf(kind):
    t, f, fz = mk_tf(kind)
    def check(old, new, ctx):
        if new is None: return 'entity missing after edit'
        if kind.startswith('mirror') and old['t'] in TEXTY:
            if old.get('p') and new.get('p'):       # text is not mirrored (MIRRTEXT 0): check the anchor point only
                w = f(old['p'][0], old['p'][1])
                return None if close(list(w), new['p'][:2]) else 'p %s want %s' % (_r(new['p']), _r(w))
            return None
        if not old.get('ext') or not new.get('ext'): return None if old.get('ext') == new.get('ext') else 'ext presence changed'
        want = bbox_tf(old['ext'], f)
        if not close(want[:2] + want[3:5], new['ext'][:2] + new['ext'][3:5]): return 'ext %s want %s' % (_r(new['ext']), _r(want))
        return None
    return check


def _r(v): return [round(x, 4) for x in v]


def chk_props(**kw):
    def check(old, new, ctx):
        if new is None: return 'entity missing after edit'
        for k, v in kw.items():
            if new.get(k) != v: return '%s=%r want %r' % (k, new.get(k), v)
        return None
    return check


# ---------------------------------------------------------------- operations: name -> dict(apply(doc,h,ctx), check(old,new,ctx), types or None)
def ap_tf(kind):
    def f(doc, h, ctx): doc.transform(h, mk_tf(kind)[0])
    return f


def ap_props(**kw):
    def f(doc, h, ctx): doc.set_props(h, **kw)
    return f


OPS = {}
for k in ('move', 'rot90', 'rot180', 'scale2', 'mirrorx', 'mirrory'):
    OPS[k] = dict(apply=ap_tf(k), check=chk_tf(k))
OPS['color'] = dict(apply=ap_props(color=3), check=chk_props(ci=3))
OPS['lweight'] = dict(apply=ap_props(lweight=50), check=chk_props(lw=50))
OPS['ltscale'] = dict(apply=ap_props(ltscale=2.5), check=chk_props(lts=2.5))
OPS['layer'] = dict(apply=lambda doc, h, ctx: doc.set_props(h, layer=ctx['newlayer']), check=lambda old, new, ctx: None if new and new.get('layer') == ctx['newlayer'] else 'layer %r' % (new and new.get('layer')))
OPS['erase'] = dict(apply=lambda doc, h, ctx: doc.erase(h), check=lambda old, new, ctx: None if new is None else 'still present')
OPS['copy'] = dict(apply=lambda doc, h, ctx: ctx['copies'].append((h, doc.copy_entity(h, X.Transform.translate(777.0, 111.0)))), check=None)
OPS['noop'] = dict(apply=lambda doc, h, ctx: None, check=lambda old, new, ctx: None if new == old else 'record changed')
OP_ORDER = ['noop', 'move', 'rot90', 'rot180', 'scale2', 'mirrorx', 'mirrory', 'color', 'lweight', 'ltscale', 'layer', 'copy', 'erase']


def pick_targets(dump, rng, ops, per_type=1):
    """returns [(op, dxf type, handle hex)] with distinct entities: for every type present on top-level spaces one entity per op"""
    by = collections.defaultdict(list)
    for h, e in dump['ents'].items():
        if e['_top'] and 't' in e and not e.get('err'): by[e['t']].append(h)
    plan = []
    for t, hs in sorted(by.items()):
        rng.shuffle(hs); i = 0
        for op in ops:
            if op == 'noop': continue
            if i >= len(hs): break
            plan.append((op, t, hs[i])); i += 1
    return plan


# ---------------------------------------------------------------- one file
def apply_plan(path, plan, ctx_extra, save_to):
    doc = dwgdoc.Doc(open(path, 'rb').read())
    ctx = dict(copies=[], **ctx_extra)
    res = {}
    # a 'layer' op needs a target layer
    if any(p[0] == 'layer' for p in plan) and ctx['newlayer'] not in [l.lower() if False else l for l in doc.layers()]:
        try: doc.add_layer(ctx['newlayer'], color=5)
        except Exception as e: res[('layer', '*')] = 'APPLY_FAIL add_layer ' + repr(e)[:100]
    for op, t, hx in plan:
        h = int(hx, 16)
        try:
            OPS[op]['apply'](doc, h, ctx); res[(op, t, hx)] = 'ok'
        except NotImplementedError as e:
            res[(op, t, hx)] = 'UNSUPPORTED ' + str(e)[:100]
        except Exception as e:
            res[(op, t, hx)] = 'APPLY_FAIL ' + ''.join(traceback.format_exception_only(type(e), e)).strip()[:150]
    data = doc.save()
    open(save_to, 'wb').write(data)
    return res, ctx


def evaluate(orig, new, plan, applied, ctx):
    """orig/new dumps -> {(op,type,h): (status, msg)}"""
    out = {}
    touched = set(p[2] for p in plan if applied.get(p, '').startswith('ok'))
    # the writer regenerates the anonymous block of an edited dimension: its children legitimately change
    dimblocks = set(orig['ents'][p[2]].get('block') for p in plan if p[1] == 'DIMENSION' and p[2] in orig['ents'] and applied.get(p, '').startswith('ok'))
    for p in plan:
        op, t, hx = p
        if not applied.get(p, '').startswith('ok'):
            out[p] = ('UNSUPPORTED' if applied.get(p, '').startswith('UNSUP') else 'APPLY_FAIL', applied.get(p, '')); continue
        old = orig['ents'].get(hx); nw = new['ents'].get(hx) if new else None
        chk = OPS[op]['check']
        if op == 'copy': continue
        msg = chk(old, nw, ctx)
        out[p] = ('PASS', '') if msg is None else ('FAIL_CHECK', msg)
    # untouched entities must be unchanged
    diff = 0; ex = []
    for h, e in orig['ents'].items():
        if h in touched or e['_blk'] in dimblocks: continue
        n = new['ents'].get(h)
        if n != e:
            diff += 1
            if len(ex) < 3: ex.append((h, e['t'], [k for k in set(e) | set(n or {}) if (n or {}).get(k) != e.get(k)][:4]))
    out[('untouched', '*', '*')] = ('PASS', '') if not diff else ('FAIL_UNTOUCHED', '%d changed e.g. %s' % (diff, ex))
    # copies: the new handle must exist with the same type and the bbox shifted
    for src, nh in ctx['copies']:
        sx = '%X' % src; nx = '%X' % nh; o = orig['ents'].get(sx); n = new['ents'].get(nx) if new else None
        key = ('copy', o['t'] if o else '?', sx)
        if n is None: out[key] = ('FAIL_CHECK', 'copy %s not in dump' % nx)
        elif n['t'] != o['t']: out[key] = ('FAIL_CHECK', 'copy type %s' % n['t'])
        elif o.get('ext') and n.get('ext') and not close(bbox_tf(o['ext'], lambda x, y: (x + 777.0, y + 111.0))[:2], n['ext'][:2]): out[key] = ('FAIL_CHECK', 'copy ext %s' % _r(n['ext']))
        else: out[key] = ('PASS', '')
    return out


def run_file(fid, args, rng, log):
    path = SRC + fid; ver = fid[:6]
    odir = ORIG + fid[:-4]
    a0, d0 = oracle(path, odir)
    if d0 is None:
        log(dict(file=fid, ver=ver, op='*', t='*', status='ORACLE_ORIG_FAIL', msg=str(a0))); return
    ops = [o for o in args.ops if o in OPS]
    ctx_extra = dict(newlayer='ZZ_EDIT_TEST')
    out_dir = args.out + '/' + fid[:-4]; os.makedirs(out_dir, exist_ok=True)
    plan = pick_targets(d0, rng, ops)
    # batch
    rounds = [('batch', plan)]
    for name, pl in rounds:
        ed = out_dir + '/%s.dwg' % name
        try:
            applied, ctx = apply_plan(path, pl, ctx_extra, ed)
        except Exception as e:
            log(dict(file=fid, ver=ver, op='*', t='*', status='SAVE_FAIL', msg=''.join(traceback.format_exception_only(type(e), e)).strip()[:200])); continue
        a1, d1 = oracle(ed, out_dir + '/o_' + name)
        if d1 is None or (a1 and a1 != a0):
            log(dict(file=fid, ver=ver, op='batch', t='*', status='FAIL_OPEN' if d1 is None else 'FAIL_AUDIT', msg=str(a1)))
            if args.bisect: bisect(fid, path, pl, ctx_extra, out_dir, d0, a0, log, ver)
            continue
        res = evaluate(d0, d1, pl, applied, ctx)
        for (op, t, hx), (st, msg) in res.items():
            log(dict(file=fid, ver=ver, op=op, t=t, status=st, msg=msg))
        if a1 != a0:
            log(dict(file=fid, ver=ver, op='batch', t='*', status='AUDIT_DIFF', msg=str(a1)))
    if os.path.exists(out_dir + '/batch.dwg') and not args.keep:
        pass


def bisect(fid, path, pl, ctx_extra, out_dir, d0, a0, log, ver):
    """re-run each planned op alone to attribute a batch failure"""
    for i, p in enumerate(pl):
        ed = out_dir + '/b%d.dwg' % i
        try:
            applied, ctx = apply_plan(path, [p], ctx_extra, ed)
        except Exception as e:
            log(dict(file=fid, ver=ver, op=p[0], t=p[1], status='SAVE_FAIL', msg=repr(e)[:150])); continue
        if not applied[p].startswith('ok'):
            log(dict(file=fid, ver=ver, op=p[0], t=p[1], status='UNSUPPORTED' if applied[p].startswith('UNSUP') else 'APPLY_FAIL', msg=applied[p])); continue
        a1, d1 = oracle(ed, out_dir + '/o_b%d' % i)
        if d1 is None: log(dict(file=fid, ver=ver, op=p[0], t=p[1], status='FAIL_OPEN', msg=str(a1)))
        elif a1 != a0: log(dict(file=fid, ver=ver, op=p[0], t=p[1], status='FAIL_AUDIT', msg=str(a1)))
        else:
            res = evaluate(d0, d1, [p], applied, ctx)
            for (op, t, hx), (st, msg) in res.items(): log(dict(file=fid, ver=ver, op=op, t=t, status=st, msg=msg))
        try: os.remove(ed)
        except OSError: pass
        shutil.rmtree(out_dir + '/o_b%d' % i, ignore_errors=True)       # dumps are large: only the batch dump is kept


def cmd_run(args):
    os.makedirs(args.out, exist_ok=True); os.makedirs(ORIG, exist_ok=True)
    rows = [l.split('\t') for l in open(args.sample).read().splitlines() if l]
    files = [r[0] for r in rows if r[0][:6] in ('AC1015', 'AC1018', 'AC1024', 'AC1027', 'AC1032')]
    if args.files: files = [f for f in files if f[:-4] in args.files.split(',')]
    if args.limit: files = files[:args.limit]
    rf = open(args.out + '/results.jsonl', 'a')
    def log(rec):
        rf.write(json.dumps(rec) + '\n'); rf.flush()
        if rec['status'] not in ('PASS', 'UNSUPPORTED'): print(rec['file'], rec['op'], rec['t'], rec['status'], rec['msg'][:150], flush=True)
    for i, f in enumerate(files):
        rng = random.Random(args.seed * 1000 + i)
        t0 = time.time()
        try:
            run_file(f, args, rng, log)
        except Exception as e:
            log(dict(file=f, ver=f[:6], op='*', t='*', status='RUNNER_EXC', msg=traceback.format_exc()[-300:]))
        print('[%d/%d] %s %.0fs' % (i + 1, len(files), f, time.time() - t0), flush=True)


def cmd_report(args):
    rows = [json.loads(l) for l in open(args.out + '/results.jsonl')]
    tab = collections.defaultdict(collections.Counter)
    for r in rows: tab[(r['op'], r['t'], r['ver'])][r['status']] += 1
    by = collections.defaultdict(collections.Counter)
    for (op, t, ver), c in tab.items():
        for k, v in c.items(): by[(op, ver)][k] += v
    for k in sorted(by): print(k, dict(by[k]))
    tot = collections.Counter(r['status'] for r in rows); print('TOTAL', dict(tot))


def main():
    ap = argparse.ArgumentParser(); sub = ap.add_subparsers(dest='cmd')
    r = sub.add_parser('run'); r.add_argument('out'); r.add_argument('--sample', default=os.path.expanduser('~/dwg-edit-tests/sample.tsv'))
    r.add_argument('--ops', default=','.join(OP_ORDER), type=lambda s: s.split(',')); r.add_argument('--seed', type=int, default=1)
    r.add_argument('--limit', type=int); r.add_argument('--files'); r.add_argument('--bisect', action='store_true', default=True); r.add_argument('--keep', action='store_true')
    p = sub.add_parser('report'); p.add_argument('out')
    a = ap.parse_args()
    {'run': cmd_run, 'report': cmd_report}[a.cmd](a)


if __name__ == '__main__':
    main()
