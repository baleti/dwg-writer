"""Characterisation tests for the standalone geometry helpers."""
import math
import unittest

from dwgscene import (Mat, arc_points, bspline_points, bulge_points,
                      clip_polyline, fit_to_nurbs, ocs_axes, ocs_to_wcs)


class GeometryTests(unittest.TestCase):
    def assertPointAlmostEqual(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertAlmostEqual(a, e)

    def assertPointsAlmostEqual(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertPointAlmostEqual(a, e)

    def test_ocs_default_axes(self):
        self.assertPointsAlmostEqual(ocs_axes((0, 0, 1)),
                                     [(1, 0, 0), (0, 1, 0), (0, 0, 1)])

    def test_ocs_default_normal_preserves_point_and_dimension(self):
        for point in [(2, 3), (2, 3, 4)]:
            self.assertIs(ocs_to_wcs(point, (0, 0, 1)), point)

    def test_ocs_tilted_normal(self):
        self.assertPointsAlmostEqual(ocs_axes((0, 3, 4)),
                                     [(-1, 0, 0), (0, -.8, .6), (0, .6, .8)])
        self.assertPointAlmostEqual(ocs_to_wcs((2, 3, 4), (0, 3, 4)),
                                    (-2, 0, 5))
        self.assertPointAlmostEqual(ocs_to_wcs((2, 3), (0, 3, 4)),
                                    (-2, -2.4, 1.8))

    def test_ocs_axis_switch_at_normalized_threshold(self):
        # The strict threshold is tested on unit normals, after normalization.
        x = 1 / 128
        z = math.sqrt(1 - x * x)
        self.assertPointAlmostEqual(ocs_axes((x, 0, z))[0], (z, 0, -x))
        x = 1 / 64
        z = math.sqrt(1 - x * x)
        self.assertPointAlmostEqual(ocs_axes((x, 0, z))[0], (0, 1, 0))
        self.assertPointAlmostEqual(ocs_axes((0, x, z))[0], (-1, 0, 0))

    def test_ocs_axes_are_orthonormal(self):
        for normal in [(0, 0, 7), (1, 2, 3), (.001, -.002, 1), (0, 0, -2)]:
            with self.subTest(normal=normal):
                axes = ocs_axes(normal)
                for i in range(3):
                    for j in range(3):
                        self.assertAlmostEqual(sum(a * b for a, b in zip(axes[i], axes[j])),
                                               1 if i == j else 0)

    def test_mat_identity(self):
        self.assertPointAlmostEqual(Mat().apply(3, -4), (3, -4))
        self.assertAlmostEqual(Mat().det(), 1)

    def test_mat_translation(self):
        self.assertPointAlmostEqual(Mat(tx=5, ty=-2).apply(3, 4), (8, 2))

    def test_mat_rotation(self):
        angle = math.pi / 2
        c, s = math.cos(angle), math.sin(angle)
        mat = Mat(c, -s, s, c)
        self.assertPointAlmostEqual(mat.apply(2, 3), (-3, 2))
        self.assertAlmostEqual(mat.rot(), angle)
        self.assertAlmostEqual(mat.scale_x(), 1)

    def test_mat_scale(self):
        mat = Mat(a=2, d=-3)
        self.assertPointAlmostEqual(mat.apply(4, 5), (8, -15))
        self.assertAlmostEqual(mat.det(), -6)
        self.assertAlmostEqual(mat.scale_x(), 2)

    def test_mat_general_affine(self):
        self.assertPointAlmostEqual(Mat(2, 3, 4, 5, 6, 7).apply(8, 9), (49, 84))

    def test_mat_composition_applies_right_operand_first(self):
        translate = Mat(tx=5, ty=7)
        scale = Mat(a=2, d=3)
        self.assertPointAlmostEqual(translate.mul(scale).apply(1, 2), (7, 13))
        self.assertPointAlmostEqual(scale.mul(translate).apply(1, 2), (12, 27))
        left, right = Mat(2, 3, 4, 5, 6, 7), Mat(7, 6, 5, 4, 3, 2)
        self.assertPointAlmostEqual(left.mul(right).apply(2, -1),
                                    left.apply(*right.apply(2, -1)))

    def test_arc_quarter_and_endpoints(self):
        pts = arc_points(2, -3, 4, 0, math.pi / 2)
        self.assertEqual(len(pts), 18)
        self.assertPointAlmostEqual(pts[0], (6, -3))
        self.assertPointAlmostEqual(pts[-1], (2, 1))
        for i, p in enumerate(pts):
            angle = math.pi * i / 34
            self.assertPointAlmostEqual(p, (2 + 4 * math.cos(angle), -3 + 4 * math.sin(angle)))

    def test_arc_equal_angles_make_full_circle(self):
        pts = arc_points(0, 0, 2, 0, 0)
        self.assertEqual(len(pts), 66)
        self.assertPointAlmostEqual(pts[0], (2, 0))
        self.assertPointAlmostEqual(pts[-1], (2, 0))
        for x, y in pts:
            self.assertAlmostEqual(x * x + y * y, 4)

    def test_arc_clockwise_direction(self):
        pts = arc_points(0, 0, 1, 0, -math.pi / 2, ccw=False)
        self.assertEqual(len(pts), 18)
        self.assertLess(pts[1][1], 0)
        self.assertPointAlmostEqual(pts[-1], (0, -1))
        # A positive end angle wraps around in the clockwise direction.
        wrapped = arc_points(0, 0, 1, 0, math.pi / 2, ccw=False)
        self.assertEqual(len(wrapped), 50)
        self.assertLess(wrapped[1][1], 0)
        self.assertPointAlmostEqual(wrapped[-1], (0, 1))

    def test_arc_step_is_ignored(self):
        expected = arc_points(0, 0, 1, 0, math.pi / 2)
        for step in [.001, 10]:
            self.assertPointsAlmostEqual(arc_points(0, 0, 1, 0, math.pi / 2, step=step), expected)

    def test_arc_short_sweep_has_eight_segments(self):
        pts = arc_points(0, 0, 1, 0, .01)
        self.assertEqual(len(pts), 9)
        self.assertPointAlmostEqual(pts[-1], (math.cos(.01), math.sin(.01)))

    def test_bulge_zero_returns_only_end(self):
        for bulge in [0, 1e-13]:
            self.assertPointsAlmostEqual(bulge_points((0, 0), (2, 0), bulge), [(2, 0)])

    def test_bulge_positive_semicircle(self):
        pts = bulge_points((0, 0), (2, 0), 1)
        self.assertEqual(len(pts), 33)
        for i, (x, y) in enumerate(pts, 1):
            self.assertPointAlmostEqual((x, y), (1 - math.cos(math.pi * i / 33),
                                                -math.sin(math.pi * i / 33)))
        self.assertLess(pts[0][1], 0)
        self.assertPointAlmostEqual(pts[-1], (2, 0))

    def test_bulge_negative_semicircle_is_on_other_side(self):
        pts = bulge_points((0, 0), (2, 0), -1)
        self.assertEqual(len(pts), 33)
        for i, p in enumerate(pts, 1):
            self.assertPointAlmostEqual(p, (1 - math.cos(math.pi * i / 33),
                                            math.sin(math.pi * i / 33)))

    def test_bulge_n_is_ignored_and_endpoint_is_original(self):
        end = (2, 0)
        expected = bulge_points((0, 0), end, 1)
        for n in [2, 100]:
            pts = bulge_points((0, 0), end, 1, n=n)
            self.assertPointsAlmostEqual(pts, expected)
            self.assertIs(pts[-1], end)

    def test_bulge_coincident_points(self):
        self.assertPointsAlmostEqual(bulge_points((1, 2), (1, 2), 1), [(1, 2)])

    def test_straight_line_fit_and_sampling(self):
        fit = [(0, 1, 0), (2, 5, 0), (4, 9, 0)]
        result = fit_to_nurbs(fit)
        self.assertIsNotNone(result)
        knots, ctrl = result
        self.assertEqual(len(ctrl), 5)
        self.assertPointAlmostEqual(knots, [0] * 4 + [math.sqrt(20)] + [2 * math.sqrt(20)] * 4)
        pts = bspline_points(3, knots, ctrl, n=10)
        self.assertEqual(len(pts), 11)
        for x, y in pts:
            self.assertAlmostEqual(y, 2 * x + 1)
        self.assertPointAlmostEqual(pts[0], fit[0][:2])
        self.assertPointAlmostEqual(pts[5], fit[1][:2])
        self.assertPointAlmostEqual(pts[-1], fit[-1][:2])

    def test_degenerate_fit_returns_none(self):
        for fit in [[], [(1, 2, 3)], [(1, 2, 3), (1, 2, 3)]]:
            self.assertIsNone(fit_to_nurbs(fit))

    def test_quadratic_bezier_midpoint_and_endpoints(self):
        pts = bspline_points(2, [0, 0, 0, 1, 1, 1], [(0, 0), (2, 4), (4, 0)], n=2)
        self.assertPointsAlmostEqual(pts, [(0, 0), (2, 2), (4, 0)])

    def test_rational_quadratic_weights(self):
        pts = bspline_points(2, [0, 0, 0, 1, 1, 1], [(1, 0), (1, 1), (0, 1)],
                             weights=[1, math.sqrt(.5), 1], n=2)
        self.assertPointsAlmostEqual(pts, [(1, 0), (math.sqrt(.5), math.sqrt(.5)), (0, 1)])

    def test_bspline_n_counts_intervals_and_zero_uses_default(self):
        for n, count in [(1, 2), (7, 8), (None, 25), (0, 25)]:
            pts = bspline_points(2, [0, 0, 0, 1, 1, 1], [(0, 0), (2, 4), (4, 0)], n=n)
            self.assertEqual(len(pts), count)
            self.assertPointAlmostEqual(pts[0], (0, 0))
            self.assertPointAlmostEqual(pts[-1], (4, 0))

    def assertClipped(self, pts, expected):
        actual = clip_polyline(pts, 0, 0, 10, 10)
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertPointsAlmostEqual(a, e)

    def test_clip_fully_inside(self):
        self.assertClipped([(1, 2), (3, 4), (8, 9)], [[(1, 2), (3, 4), (8, 9)]])

    def test_clip_fully_outside(self):
        self.assertClipped([(-3, 1), (-2, 5), (-1, 9)], [])

    def test_clip_crossing_one_edge(self):
        self.assertClipped([(-2, 2), (2, 6)], [[(0, 4), (2, 6)]])
        self.assertClipped([(2, 6), (-2, 2)], [[(2, 6), (0, 4)]])

    def test_clip_crossing_two_edges(self):
        self.assertClipped([(-5, 2), (15, 6)], [[(0, 3), (10, 5)]])
        self.assertClipped([(2, -5), (6, 15)], [[(3, 0), (5, 10)]])

    def test_clip_empty_and_single_point(self):
        self.assertClipped([], [])
        self.assertClipped([(5, 5)], [])

    def test_clip_zero_length_segments(self):
        self.assertClipped([(5, 5), (5, 5)], [[(5, 5), (5, 5)]])
        self.assertClipped([(-1, 5), (-1, 5)], [])

    def test_clip_boundary_and_corner_touch(self):
        self.assertClipped([(0, -1), (0, 11)], [[(0, 0), (0, 10)]])
        self.assertClipped([(-1, 1), (1, -1)], [[(0, 0), (0, 0)]])

    def test_clip_polyline_reenters_window(self):
        self.assertClipped([(2, 2), (12, 2), (12, 8), (2, 8)],
                           [[(2, 2), (10, 2)], [(10, 8), (2, 8)]])

    def test_clip_immediate_reentry_splits_at_exit(self):
        self.assertClipped([(2, 2), (12, 2), (2, 2)],
                           [[(2, 2), (10, 2)], [(10, 2), (2, 2)]])


if __name__ == '__main__':
    unittest.main()
