import math
import unittest

import dwgpat
from dwghatchfill import fill_segments


def square(a, b):
    return [(a, a), (b, a), (b, b), (a, b)]


def line(y=5, dashes=()):
    return [(0, (0, y), (0, 0), list(dashes))]


class ExtraHatchFillTests(unittest.TestCase):
    def test_nested_islands(self):
        self.assertEqual(fill_segments([square(0, 10), square(2, 8), square(4, 6)], line()),
                         [((0, 5), (2, 5)), ((4, 5), (6, 5)), ((8, 5), (10, 5))])

    def test_outer_nested(self):
        self.assertEqual(fill_segments([square(2, 8), square(0, 10)], line(), 'outer'),
                         [((0, 5), (10, 5))])

    def test_ignore_overlapping_union(self):
        self.assertEqual(fill_segments([square(0, 6), square(4, 10)], line(), 'ignore'),
                         [((0, 5), (10, 5))])

    def test_negative_dash_phase(self):
        self.assertEqual(fill_segments([square(-5, 5)], line(0, [2, -1])),
                         [((-5, 0), (-4, 0)), ((-3, 0), (-1, 0)),
                          ((0, 0), (2, 0)), ((3, 0), (5, 0))])

    def test_vertex_crossings(self):
        diamond = [(0, 0), (2, 2), (4, 0), (2, -2)]
        self.assertEqual(fill_segments([diamond], line(0)), [((0, 0), (4, 0))])

    def test_collinear_boundary(self):
        self.assertEqual(fill_segments([square(0, 10)], line(10)), [((0, 10), (10, 10))])

    def test_rotated_family(self):
        plines = dwgpat.expand([(0, 0, 0, 0, 2, [])], angle_rad=math.pi / 4)
        segments = fill_segments([square(-5, 5)], plines)
        self.assertTrue(segments)
        for a, b in segments:
            self.assertAlmostEqual(b[0] - a[0], b[1] - a[1])
            for x, y in (a, b):
                self.assertLessEqual(abs(x), 5 + 1e-10)
                self.assertLessEqual(abs(y), 5 + 1e-10)

    def test_zero_offset(self):
        self.assertEqual(fill_segments([square(0, 10)], line()), [((0, 5), (10, 5))])

    def test_along_line_offset_shifts_phase(self):
        segments = fill_segments([square(0, 4)], [(0, (0, 0), (1, 2), [1, -2])])
        self.assertEqual([s for s in segments if s[0][1] == 2], [((1, 2), (2, 2))])

    def test_negative_spacing_order(self):
        segments = fill_segments([square(0, 2)], [(0, (0, 0), (0, -1), [])])
        self.assertEqual([a[1] for a, b in segments], [2, 1, 0])

    def test_dots_backwards(self):
        self.assertEqual(fill_segments([square(-3, 3)], line(0, [0, -2])),
                         [((-2, 0), (-2, 0)), ((0, 0), (0, 0)), ((2, 0), (2, 0))])

    def test_degenerate_inputs(self):
        self.assertEqual(fill_segments([], line()), [])
        with self.assertRaises(ValueError):
            fill_segments([square(0, 2)], line(), 'invalid')
        with self.assertRaises(ValueError):
            fill_segments([square(0, 2)], [(0, (0, 1), (1, 0), [])])
