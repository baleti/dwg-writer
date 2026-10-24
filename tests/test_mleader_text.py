import os, sys, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import dwgdoc, dwgent

F = os.path.expanduser('~/dwg-research/corpus/AC1032_26_71751c84.dwg')


@unittest.skipUnless(os.path.exists(F), 'corpus file missing')
class MLeaderText(unittest.TestCase):
    def test_replace_text(self):
        d = dwgdoc.Doc(open(F, 'rb').read())
        hs = d.mleaders()
        x = d.get(hs[0]); x['ctx']['text'] = 'Hello é WALLX'; d.put(x)
        self.assertEqual(d.replace_text('WALLX', 'WALL'), 1)
        d2 = dwgdoc.Doc(d.save())
        e = dwgent.decode_multileader(d2.objs[hs[0]])
        self.assertTrue(e['full']); self.assertEqual(e['ctx']['text'], 'Hello é WALL')
        self.assertEqual(dwgent.decode_multileader(d2.objs[hs[1]])['ctx']['text'], '')


if __name__ == '__main__':
    unittest.main()
