"""fuzz_audit.py OUTDIR [seed] [per_version]: random edits (fuzz_edit.one) on local corpus files, then AutoCAD AUDIT of the edited file vs the untouched original
(needs the AutoCAD VM). Reports files where the edited drawing has more audit errors / fails to open. Own code."""
import os, sys, random
import fuzz_edit, wtest, dwgdoc


def main():
    out = sys.argv[1]; seed = int(sys.argv[2]) if len(sys.argv) > 2 else 1; per = int(sys.argv[3]) if len(sys.argv) > 3 else 3
    os.makedirs(out, exist_ok=True); rng = random.Random(seed)
    by = {}
    for f in sorted(os.listdir(fuzz_edit.CORPUS)):
        if f[:6] in fuzz_edit.SUPPORTED and os.path.getsize(fuzz_edit.CORPUS + f) < 1500000: by.setdefault(f[:6], []).append(f)
    bad = 0
    for v, fs in by.items():
        for f in rng.sample(fs, min(per, len(fs))):
            src = fuzz_edit.CORPUS + f
            try:
                want, got, log = fuzz_edit.one(src, rng, save_to=out + '/e_' + f)
            except Exception as e:
                print(f, 'EXC', repr(e)[:80], flush=True); bad += 1; continue
            a = wtest.audit(out + '/e_' + f, out + '/o_' + f[:-4]); b = wtest.audit(src, out + '/r_' + f[:-4])
            same = (a or 'OK') == (b or 'OK')
            bad += not same or want != got
            print(f, 'edited:', a or 'OK', '| original:', b or 'OK', '| count', want, got, ','.join(log), 'SAME' if same else 'DIFF', flush=True)
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
