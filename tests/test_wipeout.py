import os, sys, unittest, math
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgdoc, dwgent, dwgcodec as C, dwgxform as X

F = os.path.expanduser('~/dwg-research/corpus/AC1027_13_048c555f.dwg')


@unittest.skipUnless(os.path.exists(F), 'corpus file missing')
class Wipeout(unittest.TestCase):
    def setUp(self):
        self.d = dwgdoc.Doc(open(F, 'rb').read())

    def test_identity(self):
        ws = self.d.wipeouts(); self.assertGreater(len(ws), 5)
        for h in ws:
            self.assertEqual(C.encode(self.d.ver, self.d.get(h)), self.d.objs[h].raw)

    def test_add_and_transform(self):
        d = self.d; a = d.add_wipeout([(1, 1), (4, 1), (4, 3)], layer='0')
        b = d.copy_entity(a, X.Transform.translate(10, 0))
        d2 = dwgdoc.Doc(d.save())
        e = dwgent.decode_wipeout(d2.objs[b])
        self.assertEqual(e['clip_type'], 2); self.assertEqual(len(e['clip']), 3)
        self.assertAlmostEqual(e['pt0'][0], 11.0); self.assertAlmostEqual(e['uvec'][0], 3.0); self.assertAlmostEqual(e['vvec'][1], 2.0)
        with self.assertRaises(ValueError): d.add_wipeout([(0, 0), (1, 1)])


class WipeoutScratch(unittest.TestCase):
    def test_blank_drawings(self):
        base = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'blank_%s.dwg')
        for v in ('2010', '2013', '2018'):
            if not os.path.exists(base % v): continue
            d = dwgdoc.Doc(open(base % v, 'rb').read()); n0 = len(d.clsmap)
            a = d.add_wipeout([(3, 3), (7, 3), (7, 7), (3, 7)]); d.copy_entity(a, X.Transform.translate(10, 0))
            d2 = dwgdoc.Doc(d.save())
            self.assertEqual(len(d2.clsmap), n0 + 1); self.assertEqual(len(d2.wipeouts()), 2)
            self.assertEqual(sorted(c['dxf'] for c in d2._classes()).count('WIPEOUT'), 1)
            c = [c for c in d2._classes() if c['dxf'] == 'WIPEOUT'][0]
            self.assertTrue(c['item'] == 0x1F2)


if __name__ == '__main__':
    unittest.main()
