import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgdoc, dwgent, dwgcodec as C, dwgxform as X

F = os.path.expanduser('~/dwg-research/corpus/AC1032_26_71751c84.dwg')


@unittest.skipUnless(os.path.exists(F), 'corpus file missing')
class MLeader(unittest.TestCase):
    def setUp(self):
        self.d = dwgdoc.Doc(open(F, 'rb').read())

    def test_identity(self):
        for h in self.d.mleaders():
            x = self.d.get(h)
            self.assertEqual(x.get('key'), 'MULTILEADER')
            self.assertEqual(C.encode(self.d.ver, x), self.d.objs[h].raw)

    def test_add_move(self):
        d = self.d; hs = d.mleaders(); n = len(hs)
        h = d.add_mleader('Hello\\PWall', (100, 100), (140, 130), text_height=5.0)
        before = d.get(hs[0])['roots'][0]['conn']
        d.transform(hs[0], X.Transform.translate(10, 20))
        d2 = dwgdoc.Doc(d.save())
        self.assertEqual(len(d2.mleaders()), n + 1)
        e = dwgent.decode_multileader(d2.objs[h])
        self.assertTrue(e['full']); self.assertEqual(e['ctx']['text'], 'Hello\\PWall')
        self.assertEqual(e['roots'][0]['lines'][0]['pts'][0][:2], (100, 100)); self.assertEqual(e['roots'][0]['conn'][:2], (140, 130))
        c = d2.get(hs[0])['roots'][0]['conn']
        self.assertAlmostEqual(c[0], before[0] + 10); self.assertAlmostEqual(c[1], before[1] + 20)


if __name__ == '__main__':
    unittest.main()
