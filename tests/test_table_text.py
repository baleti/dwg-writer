import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgdoc, dwgfmt as F

SRC = os.path.expanduser('~/dwg-research/corpus/AC1032_24_41ea1a99.dwg')


def utf16_bits(s):
    return ''.join(format(c, '08b') for c in s.encode('utf-16le'))


def has(o, s):
    return utf16_bits(s) in ''.join(format(b, '08b') for b in o.raw)


@unittest.skipUnless(os.path.exists(SRC), 'corpus file missing')
class TableText(unittest.TestCase):
    def test_table_cells(self):
        d = dwgdoc.Doc(open(SRC, 'rb').read())
        self.assertGreaterEqual(d.replace_text('28/02/2025', '01/03/2026'), 1)
        d2 = dwgdoc.Doc(d.save())
        for h, o in d2.objs.items():
            if d2.clsmap.get(o.type) in ('TABLECONTENT', 'ACAD_TABLE', 'CADS_RC_DRAWINGSHEETREVISION'):
                self.assertFalse(has(o, '28/02/2025'), hex(h))
        self.assertTrue(any(has(o, '01/03/2026') for o in d2.objs.values() if d2.clsmap.get(o.type) == 'TABLECONTENT'))
        self.assertEqual(len(d2.objs), len(d.objs))


if __name__ == '__main__':
    unittest.main()
