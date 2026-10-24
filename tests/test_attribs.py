import os, unittest
import dwgdoc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(os.path.exists(os.path.join(HERE, 'templates', 'blank_2000.dwg')), 'local blank template missing')
class Attribs(unittest.TestCase):
    def test_set_attrib_both_families(self):
        for v in ('2000', '2018'):
            d = dwgdoc.Doc(open(os.path.join(HERE, 'templates', 'blank_%s.dwg' % v), 'rb').read())
            d.add_block('B9'); d.add_attdef('B9', 'T', 'p', 'Hello', (0, 0), 3.0)
            a = d.add_insert('B9', (5, 5), attribs={'T': 'one'}); b = d.add_insert('B9', (9, 9), attribs={'T': 'two'})
            self.assertTrue(d.set_attrib(b, 't', 'NEW')); self.assertFalse(d.set_attrib(b, 'missing', 'x'))
            e = dwgdoc.Doc(d.save())
            self.assertEqual(e.attributes(a), {'T': 'one'}); self.assertEqual(e.attributes(b), {'T': 'NEW'})


if __name__ == '__main__': unittest.main()
