#!/usr/bin/env python3
"""fitspline.py : derive AutoCAD-style cubic control points from SPLINE fit points (scenario 2), to be checked against the oracle's cp/knots.
Model found from the oracle: chord-length parameter t_i, clamped knot vector [0]*4 + interior knots t_1..t_{n-2} + [T]*4 (n fit pts -> n+2 control points),
end conditions given by start/end tangents (tan0/tan1) if non-zero, else natural (S''=0). Usage: PYTHONPATH=. fitspline.py FILE.dwg"""
import sys, os, json
import numpy as np

def bspline_basis(i, p, u, knots):
    if p == 0:
        return 1.0 if (knots[i] <= u < knots[i + 1]) or (u == knots[-1] and knots[i] < knots[i + 1] == knots[-1]) else 0.0
    a = b = 0.0
    d1 = knots[i + p] - knots[i]
    if d1 > 0: a = (u - knots[i]) / d1 * bspline_basis(i, p - 1, u, knots)
    d2 = knots[i + p + 1] - knots[i + 1]
    if d2 > 0: b = (knots[i + p + 1] - u) / d2 * bspline_basis(i + 1, p - 1, u, knots)
    return a + b

def basis_d(i, p, u, knots, k):
    """k-th derivative (k=1,2) of basis i."""
    if k == 0: return bspline_basis(i, p, u, knots)
    a = b = 0.0
    d1 = knots[i + p] - knots[i]
    if d1 > 0: a = p / d1 * basis_d(i, p - 1, u, knots, k - 1)
    d2 = knots[i + p + 1] - knots[i + 1]
    if d2 > 0: b = p / d2 * basis_d(i + 1, p - 1, u, knots, k - 1)
    return a - b

def fit_to_nurbs(fit, tan0=None, tan1=None):
    P = np.array([f[:3] for f in fit], float); n = len(P)
    t = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    T = t[-1]
    knots = [0.0] * 4 + list(t[1:-1]) + [T] * 4
    m = n + 2
    A = np.zeros((m, m)); B = np.zeros((m, 3))
    for r, u in enumerate(t):
        for c in range(m): A[r, c] = bspline_basis(c, 3, u, knots)
        B[r] = P[r]
    for c in range(m): A[n, c] = basis_d(c, 3, 0.0, knots, 1) if tan0 and any(tan0) else basis_d(c, 3, 0.0, knots, 2)
    for c in range(m): A[n + 1, c] = basis_d(c, 3, T - 1e-12, knots, 1) if tan1 and any(tan1) else basis_d(c, 3, T - 1e-12, knots, 2)
    if tan0 and any(tan0): B[n] = np.array(tan0)
    if tan1 and any(tan1): B[n + 1] = np.array(tan1)
    return np.linalg.solve(A, B), knots

if __name__ == '__main__':
    import dwgmodel
    p = sys.argv[1]; stem = os.path.basename(p)[:-4]
    d = json.load(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../oracle-out', stem, 'dump.json')))
    m = dwgmodel.Model(open(p, 'rb').read())
    mine = {e['handle']: e for b, e in m.entities() if e['kind'] == 'SPLINE' and e['scenario'] == 2 and not e['ctrl'] and not e['closed'] and e['degree'] == 3}
    n = bad = 0; worst = 0.0
    for b in d['blocks']:
        for e in b.get('entities', []):
            if e['t'] != 'SPLINE' or not isinstance(e['h'], str): continue
            o = mine.get(int(e['h'], 16))
            if not o or len(o['fit']) < 3 or len(e['cp']) != len(o['fit']) + 2: continue
            cp, kn = fit_to_nurbs(o['fit'], o['tan0'], o['tan1'])
            err = np.abs(cp - np.array(e['cp'])).max() / max(1.0, np.abs(np.array(e['cp'])).max())
            n += 1; worst = max(worst, float(err)); bad += int(err > 1e-6)
    print(json.dumps({'checked': n, 'bad': bad, 'worst_rel_err': worst}))
