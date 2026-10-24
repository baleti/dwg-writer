import math, unittest
import dwghatchfill as H
import dwgpat

SQ = [(0, 0), (10, 0), (10, 10), (0, 10)]


def length(segs):
    return sum(math.hypot(b[0] - a[0], b[1] - a[1]) for a, b in segs)


class HatchFillTests(unittest.TestCase):
    def test_horizontal_continuous(self):
        pl = dwgpat.expand([(0.0, 0.0, 0.0, 0.0, 1.0, [])])
        segs = H.fill_segments([SQ], pl)
        # lines y = 0..10 step 1: y=0 and y=10 lie on the boundary; interior ones y=1..9 must be present
        ys = sorted({round(a[1], 9) for a, b in segs})
        for y in range(1, 10): self.assertIn(float(y), ys)
        inner = [s for s in segs if 0 < s[0][1] < 10]
        self.assertEqual(len(inner), 9)
        for a, b in inner:
            self.assertAlmostEqual(abs(b[0] - a[0]), 10.0); self.assertAlmostEqual(a[1], b[1])

    def test_diagonal_total_length(self):
        pl = dwgpat.expand([(45.0, 0.0, 0.0, 0.0, 1.0, [])])
        segs = H.fill_segments([SQ], pl)
        # area / spacing = 100 / 1 = 100 total length (boundary-touching corner lines have zero length)
        self.assertAlmostEqual(length(segs), 100.0, delta=0.5)

    def test_island_even_odd(self):
        hole = [(2, 2), (8, 2), (8, 8), (2, 8)]
        pl = dwgpat.expand([(0.0, 0.0, 0.0, 0.0, 1.0, [])])
        normal = length(H.fill_segments([SQ, hole], pl, 'normal'))
        ignore = length(H.fill_segments([SQ, hole], pl, 'ignore'))
        outer = length(H.fill_segments([SQ, hole], pl, 'outer'))
        self.assertAlmostEqual(ignore, outer, delta=1e-6)
        self.assertAlmostEqual(outer - normal, 6.0 * 5, delta=1.01 * 6)   # about 5-7 lines of length 6 removed
        self.assertLess(normal, outer)

    def test_dashes(self):
        pl = dwgpat.expand([(0.0, 0.0, 0.0, 0.0, 5.0, [2.0, -1.0])])
        segs = [s for s in H.fill_segments([SQ], pl) if abs(s[0][1] - 5.0) < 1e-9]
        xs = sorted((round(a[0], 9), round(b[0], 9)) for a, b in segs)
        self.assertEqual(xs, [(0.0, 2.0), (3.0, 5.0), (6.0, 8.0), (9.0, 10.0)])

    def test_dot_and_zero_offset(self):
        pl = dwgpat.expand([(0.0, 5.0, 5.0, 0.0, 0.0, [0.0, -2.0])])
        segs = H.fill_segments([SQ], pl)
        self.assertTrue(all(s[0][1] == 5.0 for s in segs))
        self.assertEqual(sorted(s[0][0] for s in segs), [1.0, 3.0, 5.0, 7.0, 9.0])
        self.assertTrue(all(s[0] == s[1] for s in segs))

    def test_too_many_lines(self):
        pl = dwgpat.expand([(0.0, 0.0, 0.0, 0.0, 1e-6, [])])
        with self.assertRaises(ValueError):
            H.fill_segments([SQ], pl)

    def test_speed(self):
        import time
        big = [(0, 0), (100, 0), (100, 100), (0, 100)]
        pl = dwgpat.expand([(30.0, 0.0, 0.0, 0.0, 0.5, [])])
        t = time.time(); H.fill_segments([big], pl); self.assertLess(time.time() - t, 0.5)


if __name__ == '__main__':
    unittest.main()
