"""wtest_offline.py: VM-free writer regression. Builds every wtest scenario for every blank template, re-reads the file with our own parser and
compares the model-space entity count; also checks that the container round trips (save of an unchanged template re-opens). Exit 1 on failure.
This does NOT replace wtest.py (AutoCAD AUDIT); use it when the AutoCAD VM is down."""
import os, sys
import dwgdoc, wtest

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    vers = sys.argv[1:] or ['2000', '2004', '2010', '2013', '2018']
    bad = 0
    for v in vers:
        tpl = open(os.path.join(HERE, 'templates', 'blank_%s.dwg' % v), 'rb').read()
        for name, fn in wtest.SCEN.items():
            try:
                d = dwgdoc.Doc(tpl); fn(d); want = len(d.entities('*Model_Space'))
                got = len(dwgdoc.Doc(d.save()).entities('*Model_Space'))
                ok = want == got
            except Exception as e:
                ok = False; got = repr(e)[:80]
            print('%-8s %s %s' % (name, v, 'OK' if ok else 'FAIL %s' % (got,))); bad += not ok
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
