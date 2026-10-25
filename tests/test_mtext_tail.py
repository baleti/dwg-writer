"""R2018 MTEXT repeats insertion point / x direction / width in a trailer: transforms must update it (found by the edit matrix: AutoCAD ignored the moved entity position)."""
import os, unittest, dwgdoc, dwgxform as X
from dwgcodec_ent import mtext_tail_2018

TPL = os.path.join(os.path.dirname(__file__), '..', 'templates', 'blank_2018.dwg')


class MtextTail(unittest.TestCase):
    def test_transform_reaches_trailer(self):
        if not os.path.exists(TPL): self.skipTest('no template')
        d = dwgdoc.Doc(open(TPL, 'rb').read()); h = d.add_mtext((10, 20), 'abc', 2.5, width=30)
        d = dwgdoc.Doc(d.save())
        d.transform(h, X.Transform.translate(100, 5)); d.transform(h, X.Transform.scale((0, 0), 2.0))
        d2 = dwgdoc.Doc(d.save()); o = d2.get(h)
        self.assertEqual(tuple(o['ins']), (220.0, 50.0, 0.0))
        self.assertEqual(o['tail'], mtext_tail_2018(o))


if __name__ == '__main__': unittest.main()
