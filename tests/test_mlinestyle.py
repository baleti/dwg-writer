import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgdoc, dwgmodel

T = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'blank_%s.dwg')


class MlStyle(unittest.TestCase):
    def test_add_and_read(self):
        for v in ('2000', '2004', '2010', '2013', '2018'):
            if not os.path.exists(T % v): continue
            d = dwgdoc.Doc(open(T % v, 'rb').read())
            d.add_ltype('DASHED5', 'Dashed', [12.5, -6.25])
            d.add_mlinestyle('WALL3', [(1.5, 1, None), (0, 3, 'DASHED5'), (-1.5, 5, None)], description='three lines', flags=1)
            d.add_mline([(0, 0), (100, 0), (100, 60)], style='WALL3', offsets=[1.5, 0, -1.5])
            ms = dwgmodel.Model(d.save()).mlstyles()
            w = ms['WALL3']
            self.assertEqual([e['offset'] for e in w['elements']], [1.5, 0.0, -1.5])
            self.assertEqual([e['color'] for e in w['elements']], [1, 3, 5])
            self.assertEqual((w['flags'], w['description']), (1, 'three lines'))
            with self.assertRaises(ValueError): d.add_mlinestyle('WALL3', [(0.5, None, None)])


if __name__ == '__main__':
    unittest.main()
