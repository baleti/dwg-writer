import os, unittest
import dwgdoc

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


@unittest.skipUnless(os.path.exists(os.path.join(HERE, 'templates', 'blank_2000.dwg')), 'local blank template missing')
class Purge(unittest.TestCase):
    def test_purge_layers(self):
        for v in ('2000', '2018'):
            d = dwgdoc.Doc(open(os.path.join(HERE, 'templates', 'blank_%s.dwg' % v), 'rb').read())
            d.add_layer('USED'); d.add_layer('EMPTY'); d.add_layer('Other')
            d.add_line((0, 0), (1, 1), layer='USED')
            gone = dwgdoc.Doc(d.save()).purge_layers()
            self.assertIn('empty', gone); self.assertIn('other', gone); self.assertNotIn('used', gone)
            e = dwgdoc.Doc(d.save()); e.purge_layers(); f = dwgdoc.Doc(e.save())
            self.assertIn('used', f.layers()); self.assertNotIn('empty', f.layers()); self.assertIn('0', f.layers())


if __name__ == '__main__': unittest.main()
