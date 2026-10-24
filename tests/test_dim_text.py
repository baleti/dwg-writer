import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgdoc

T = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'blank_%s.dwg')


class DimText(unittest.TestCase):
    def test_replace(self):
        for v in ('2000', '2018'):
            if not os.path.exists(T % v): continue
            d = dwgdoc.Doc(open(T % v, 'rb').read())
            h = d.add_dim_linear((0, 0), (100, 0), (50, 20), text='Room OLD')
            self.assertEqual(d.replace_text('OLD', 'NEW'), 1)
            d2 = dwgdoc.Doc(d.save()); x = d2.get(h)
            self.assertEqual(x['user_text'], 'Room NEW')
            self.assertTrue(any('Room NEW' in (d2.get(e).get('text') or '') for e in d2.chain(x['dimblock'])))


if __name__ == '__main__':
    unittest.main()
