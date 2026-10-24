import math, os, unittest
import dwgdoc

TPL = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'templates', 'blank_2018.dwg')


@unittest.skipUnless(os.path.exists(TPL), 'local blank template missing')
class Explode(unittest.TestCase):
    def test_explode_scaled_rotated_insert(self):
        d = dwgdoc.Doc(open(TPL, 'rb').read())
        d.add_block('B1', base=(1, 1, 0))
        d.add_line((1, 1), (3, 1), block='B1'); d.add_circle((2, 2), 0.5, block='B1')
        ih = d.add_insert('B1', (10, 20), scale=(2.0, 2.0, 2.0), rot=math.pi / 2)
        d.explode(ih)
        e = dwgdoc.Doc(d.save()); ms = e.entities('*Model_Space')
        self.assertFalse([h for h in ms if e.objs[h].type == 7])
        ln = [e.get(h) for h in ms if e.objs[h].type == 19][0]
        for got, want in zip(ln['p2'], (10, 24, 0)): self.assertAlmostEqual(got, want)
        ci = [e.get(h) for h in ms if e.objs[h].type == 18][0]
        for got, want in zip(ci['center'], (8, 22, 0)): self.assertAlmostEqual(got, want)
        self.assertAlmostEqual(ci['radius'], 1.0)

    def test_attribs_refused(self):
        d = dwgdoc.Doc(open(TPL, 'rb').read())
        d.add_block('B2'); d.add_attdef('B2', 'TAG', 'p', 'v', (0, 0), 1.0)
        ih = d.add_insert('B2', (0, 0), attribs={'TAG': 'x'})
        with self.assertRaises(NotImplementedError): d.explode(ih)


if __name__ == '__main__': unittest.main()
