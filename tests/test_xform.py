"""Pure math tests for Transform.

Findings
--------
* (fixed in dwgxform) vec() did not scale z; scale with a negative factor was flagged as a reflection although it is a rotation by pi.
"""

import math
import random
import unittest

from dwgxform import Transform


TOL = 1e-9


class TransformTests(unittest.TestCase):
    def assertPointClose(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, e in zip(actual, expected):
            self.assertAlmostEqual(a, e, delta=TOL)

    def assertAngleClose(self, transform, actual, expected):
        residual = transform.norm(actual - expected + math.pi) - math.pi
        self.assertAlmostEqual(residual, 0.0, delta=TOL)

    def test_translate(self):
        for dx, dy, dz in [(3.5, -7.25, 4.0), (-2.0, 5.0, -9.0),
                           (0.0, 0.0, 0.0)]:
            with self.subTest(offset=(dx, dy, dz)):
                t = Transform.translate(dx, dy, dz)
                self.assertPointClose(t.pt((1, 2)), (1 + dx, 2 + dy))
                self.assertPointClose(t.pt((1, 2, 3)), (1 + dx, 2 + dy, 3 + dz))
                self.assertPointClose(t.vec((1, 2)), (1, 2))
                self.assertPointClose(t.vec((1, 2, 3)), (1, 2, 3))
        self.assertPointClose(Transform.translate(3, 4).pt((1, 2, 5)), (4, 6, 5))

    def test_rotate_about_center(self):
        for center in [(0, 0), (3.25, -4.5), (-2, 7)]:
            with self.subTest(center=center):
                cx, cy = center
                t = Transform.rotate(center, math.pi / 2)
                self.assertPointClose(t.pt(center), center)
                result = t.pt((cx + 1, cy))
                self.assertPointClose(result, (cx, cy + 1))
                for value in result:
                    self.assertTrue(value == 0.0 or abs(value) >= 1e-12)
        t = Transform.rotate((0, 0), math.pi / 2)
        self.assertEqual(t.pt((1, 0)), (0.0, 1.0))
        self.assertEqual(t.pt((1, 0))[0], 0.0)
        self.assertEqual(t.vec((1, 0)), (0.0, 1.0))

    def test_z_cleanup(self):
        for value in [0.0, 1e-15, -1e-15, 0.999e-12, -0.999e-12]:
            with self.subTest(value=value):
                self.assertEqual(Transform._z(value), 0.0)
        for value in [1e-12, -1e-12, 2.0, -2.0]:
            with self.subTest(value=value):
                self.assertEqual(Transform._z(value), value)

    def test_scale_about_center(self):
        center = (3.0, -4.0)
        point = (5.0, 1.0)
        for f in [0.0, 0.25, 1.0, 3.5, -0.5, -2.0]:
            with self.subTest(factor=f):
                t = Transform.scale(center, f)
                self.assertPointClose(t.pt(center), center)
                self.assertPointClose(t.pt(point), (3 + 2 * f, -4 + 5 * f))
                self.assertAlmostEqual(
                    math.dist(t.pt(point), center),
                    abs(f) * math.dist(point, center), delta=TOL)
                self.assertAlmostEqual(t.s, abs(f), delta=TOL)
                self.assertFalse(t.refl)               # a negative factor is a point reflection (rotation by pi), not a mirror
                self.assertPointClose(t.pt((*point, 6)), (3 + 2 * f, -4 + 5 * f, 6 * f))

    def test_mirror_geometry(self):
        lines = [((0, 0), (2, 0)), ((0, 0), (0, 2)),
                 ((0, 3), (2, 5))]
        for p1, p2 in lines:
            with self.subTest(line=(p1, p2)):
                t = Transform.mirror(p1, p2)
                self.assertTrue(t.refl)
                direction = (p2[0] - p1[0], p2[1] - p1[1])
                for parameter in [-2.0, 0.0, 0.5, 1.0, 3.0]:
                    on_line = tuple(p1[i] + parameter * direction[i] for i in range(2))
                    self.assertPointClose(t.pt(on_line), on_line)
                point = (4.0, -2.0)
                reflected = t.pt(point)
                midpoint = tuple((point[i] + reflected[i]) / 2 for i in range(2))
                cross = ((midpoint[0] - p1[0]) * direction[1]
                         - (midpoint[1] - p1[1]) * direction[0])
                self.assertAlmostEqual(cross, 0.0, delta=TOL)
                dot = sum((reflected[i] - point[i]) * direction[i] for i in range(2))
                self.assertAlmostEqual(dot, 0.0, delta=TOL)
                self.assertPointClose(t.pt(t.pt(point)), point)
                self.assertPointClose(t.pt(t.pt((*point, 7))), (*point, 7))

    def test_angles(self):
        rotation = 2.3
        cases = [
            (Transform.translate(5, -7), lambda theta: theta),
            (Transform.rotate((3, 4), rotation), lambda theta: theta + rotation),
            (Transform.mirror((0, 0), (1, 0)), lambda theta: -theta),
            (Transform.mirror((0, 0), (1, 1)), lambda theta: math.pi / 2 - theta),
        ]
        for t, expected in cases:
            for theta in [-9 * math.pi, -2.1, 0.0, 0.7, math.pi, 8 * math.pi]:
                with self.subTest(transform=t.__dict__, theta=theta):
                    self.assertAngleClose(t, t.ang(theta), expected(theta))

    def test_norm(self):
        t = Transform()
        for angle, expected in [(0, 0), (2 * math.pi, 0), (-2 * math.pi, 0),
                                (-math.pi / 2, 3 * math.pi / 2),
                                (5 * math.pi, math.pi)]:
            with self.subTest(angle=angle):
                result = t.norm(angle)
                self.assertGreaterEqual(result, 0.0)
                self.assertLess(result, 2 * math.pi)
                self.assertAlmostEqual(result, expected, delta=TOL)

    def test_random_transform_invariants(self):
        rng = random.Random(7)
        kinds = ("rotate", "scale", "mirror", "translate")
        for case in range(500):
            # Cycle kinds to guarantee 125 random examples of each operation.
            kind = kinds[case % len(kinds)]
            center = (rng.uniform(-20, 20), rng.uniform(-20, 20))
            angle = rng.uniform(-4 * math.pi, 4 * math.pi)
            if kind == "rotate":
                t = Transform.rotate(center, angle)
            elif kind == "scale":
                t = Transform.scale(center, rng.uniform(0.1, 5))
            elif kind == "mirror":
                end = (center[0] + math.cos(angle), center[1] + math.sin(angle))
                t = Transform.mirror(center, end)
            else:
                t = Transform.translate(*center, rng.uniform(-20, 20))
            p = (rng.uniform(-20, 20), rng.uniform(-20, 20))
            theta = rng.uniform(-math.pi, math.pi)
            length = rng.uniform(0.5, 10)
            v = (length * math.cos(theta), length * math.sin(theta))
            # Exercise 3D too wherever vec and pt have consistent z behavior.
            if kind != "scale":
                p += (rng.uniform(-20, 20),)
                v += (rng.uniform(-10, 10),)
            q = tuple(a + b for a, b in zip(p, v))
            tp, tq = t.pt(p), t.pt(q)
            delta = tuple(b - a for a, b in zip(tp, tq))
            with self.subTest(case=case, kind=kind):
                self.assertPointClose(t.vec(v), delta)
                self.assertAngleClose(t, math.atan2(delta[1], delta[0]),
                                      t.ang(math.atan2(v[1], v[0])))

    def test_scale_3d_vector_difference(self):
        t = Transform.scale((0, 0), 2)
        p, v = (1, 2, 3), (4, 5, 6)
        q = tuple(a + b for a, b in zip(p, v))
        self.assertPointClose(t.vec(v), tuple(b - a for a, b in zip(t.pt(p), t.pt(q))))

    def test_negative_scale_direction_angle(self):
        t = Transform.scale((0, 0), -2)
        theta = 0.3
        endpoint = t.pt((math.cos(theta), math.sin(theta)))
        self.assertAngleClose(t, math.atan2(endpoint[1], endpoint[0]), t.ang(theta))


if __name__ == "__main__":
    unittest.main()
