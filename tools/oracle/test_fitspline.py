#!/usr/bin/env python3
"""Synthetic regression tests; run with python3 tools/oracle/test_fitspline.py."""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(__file__))
from fitspline import fit_to_nurbs, bspline_basis, basis_d


FIT = np.array([
    (0.2, -0.4, 0.7),
    (1.3, 0.8, -0.2),
    (2.1, -0.6, 1.4),
    (3.7, 1.5, 0.3),
    (4.2, 0.2, 2.1),
])


def chord_parameters(fit):
    return np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(fit, axis=0), axis=1))]


def evaluate(ctrl, knots, u, derivative=0):
    if derivative == 0:
        weights = [bspline_basis(i, 3, u, knots) for i in range(len(ctrl))]
    else:
        weights = [basis_d(i, 3, u, knots, derivative) for i in range(len(ctrl))]
    return np.asarray(weights) @ ctrl


def assert_close(actual, expected, tolerance=1e-9):
    error = np.max(np.abs(np.asarray(actual) - np.asarray(expected)))
    assert error < tolerance, (actual, expected, error)


def test_interpolation_and_knots():
    ctrl, knots = fit_to_nurbs(FIT)
    t = chord_parameters(FIT)
    n = len(FIT)
    assert isinstance(ctrl, np.ndarray)
    assert ctrl.shape == (n + 2, 3)
    assert isinstance(knots, list)
    assert len(knots) == 2 * 4 + (n - 2) == n + 6
    assert knots[:4] == [0.0] * 4
    assert knots[-4:] == [t[-1]] * 4
    assert_close(knots[4:-4], t[1:-1])
    for u, point in zip(t, FIT):
        assert_close(evaluate(ctrl, knots, u), point)


def test_natural_ends():
    total = chord_parameters(FIT)[-1]
    # Exercise each endpoint independently with absent and explicit zero tangents.
    for tan0 in (None, (0.0, 0.0, 0.0)):
        for tan1 in (None, (0.0, 0.0, 0.0)):
            ctrl, knots = fit_to_nurbs(FIT, tan0, tan1)
            for u in (0.0, total - 1e-12):
                assert_close(evaluate(ctrl, knots, u, 2), np.zeros(3), 1e-6)


def test_given_tangents():
    tan0, tan1 = (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)
    ctrl, knots = fit_to_nurbs(FIT, tan0, tan1)
    total = chord_parameters(FIT)[-1]
    assert_close(evaluate(ctrl, knots, 0.0, 1), tan0)
    assert_close(evaluate(ctrl, knots, total - 1e-12, 1), tan1)
    assert_close(evaluate(ctrl, knots, total, 1), tan1)


def test_straight_line():
    origin = np.array((0.5, -1.0, 2.0))
    direction = np.array((1.0, 2.0, -1.0))
    fit = origin + np.arange(4)[:, None] * direction
    ctrl, _ = fit_to_nurbs(fit)
    distances = np.linalg.norm(np.cross(ctrl - origin, direction), axis=1)
    assert np.all(distances < 1e-9), distances


def test_planar_points():
    fit = FIT.copy()
    fit[:, 2] = 0.0
    ctrl, _ = fit_to_nurbs(fit)
    assert_close(ctrl[:, 2], np.zeros(len(ctrl)))


if __name__ == "__main__":
    test_interpolation_and_knots()
    test_natural_ends()
    test_given_tangents()
    test_straight_line()
    test_planar_points()
    print("OK")
