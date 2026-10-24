#!/usr/bin/env python3
"""worker_edit_doc.py FILE : same edit test as the campaign's worker_edit.py but through dwgdoc.Doc: move one model-space LINE by (1.5,-2.25) (Transform.translate),
erase another LINE, replace the string of one TEXT; save, re-parse with dwgmodel, check only these changes happened (other entity records equal except prev/next links).
One json line."""
import sys, os, json
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import dwgdoc, dwgmodel, dwgxform as X


def main(path):
    buf = open(path, 'rb').read(); R = {'magic': bytes(buf[:6]).decode('latin1')}
    m1 = dwgmodel.Model(buf)
    before = {e['handle']: e for b, e in m1.entities()}
    ents = list(m1.entities())
    lines = [e['handle'] for b, e in ents if e['kind'] == 'LINE' and b and b.lower() == '*model_space']
    texts = [e['handle'] for b, e in ents if e['kind'] == 'TEXT' and e.get('text')]
    doc = dwgdoc.Doc(buf); todo = {}
    if len(lines) >= 2:
        hm, hd = lines[len(lines) // 3], lines[2 * len(lines) // 3]
        if hm == hd: hd = lines[-1]
        doc.transform(hm, X.Transform.translate(1.5, -2.25)); doc.erase(hd); todo['moved'] = hm; todo['deleted'] = hd
    if texts:
        ht = texts[len(texts) // 2]; d = doc.get(ht); d['text'] = 'XEDIT'; doc.put(d); todo['text'] = ht
    out = doc.save()
    m2 = dwgmodel.Model(out); after = {e['handle']: e for b, e in m2.entities()}
    bad = []
    if 'moved' in todo:
        a, b = before[todo['moved']], after.get(todo['moved'])
        if b is None or any(abs(x - y - dd) > 1e-9 for x, y, dd in zip(b['p1'][:2], a['p1'][:2], (1.5, -2.25))): bad.append('moved')
        if todo['deleted'] in after: bad.append('not_deleted')
    if 'text' in todo and (after.get(todo['text']) or {}).get('text') != 'XEDIT': bad.append('text')
    touched = set(todo.values()); LINKS = ('prev', 'next', 'prev_h', 'next_h'); keys = {}; diff = 0
    core = lambda e: {k: v for k, v in e.items() if k not in LINKS}
    for h in before:
        if h in touched: continue
        if h not in after: diff += 1; keys['<missing>'] = keys.get('<missing>', 0) + 1; continue
        a0, b0 = core(before[h]), core(after[h])
        if a0 != b0:
            diff += 1
            for k in set(a0) | set(b0):
                if a0.get(k) != b0.get(k): keys[k] = keys.get(k, 0) + 1
    if diff: bad.append('others_changed:%d' % diff)
    extra = sum(1 for h in after if h not in before)
    if extra: bad.append('extra:%d' % extra)
    if sorted(m2.layers.values()) != sorted(m1.layers.values()): bad.append('layers')
    R.update(bad=bad, diff_keys=dict(sorted(keys.items(), key=lambda kv: -kv[1])[:6]), skipped=not todo, ok_all=not bad and bool(todo))
    return R


if __name__ == '__main__':
    print(json.dumps(main(sys.argv[1])))
