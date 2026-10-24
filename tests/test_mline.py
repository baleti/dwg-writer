import os, unittest
import dwgdoc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(os.path.exists(os.path.join(HERE, 'templates', 'blank_2000.dwg')), 'local blank template missing')
class Mline(unittest.TestCase):
    def test_roundtrip(self):
        for v in ('2000', '2018'):
            d = dwgdoc.Doc(open(os.path.join(HERE, 'templates', 'blank_%s.dwg' % v), 'rb').read())
            h = d.add_mline([(0, 0), (10, 0), (10, 10)])
            x = dwgdoc.Doc(d.save()).get(h)
            self.assertEqual(x['nlines'], 2)
            self.assertAlmostEqual(x['vertices'][1]['elements'][1][0][0], -2 ** 0.5)
            self.assertEqual(len(x['vertices']), 3)


if __name__ == '__main__': unittest.main()
