"""Characterisation of ACIS parsing and geometry using only invented data."""

import math
import struct
import unittest

import dwgacis as acis


def sat(records, version=400):
    return (f'{version} 1 1\n'
            '9 Toy Model 3 1.0 5 today\n'
            '1 0.01 0.001\n' + records)


def sab_header():
    return (b'ACIS BinaryFile' + struct.pack('<4i', 22000, 1, 1, 0)
            + b'\x07\x03Toy\x07\x031.0\x07\x05today'
            + b''.join(b'\x06' + struct.pack('<d', x)
                       for x in (1, 0.01, 0.001)))


def pointers(*indices):
    return [('p', index) for index in indices]


def square_records(curve_name='straight-curve', edge_reverse=False,
                   coedge_reverse=False):
    """Four vertices, edges and coedges, one circular loop and one face."""
    corners = [(0, 0, 0), (2, 0, 0), (2, 2, 0), (0, 2, 0)]
    recs = [('point', [('P', p)]) for p in corners]  # 0..3
    recs += [('vertex', pointers(-1, -1, -1, i)) for i in range(4)]
    for i, p in enumerate(corners):  # curves 8..11
        q = corners[(i + 1) % 4]
        recs.append((curve_name, [('P', p),
                                 ('V', tuple(q[k] - p[k] for k in range(3)))]))
    for i in range(4):  # edges 12..15; no parameters: use vertices
        recs.append(('edge', pointers(-1, -1, 4 + i, 4 + (i + 1) % 4,
                                      -1, 8 + i) + [('b', edge_reverse)]))
    for i in range(4):  # coedges 16..19
        recs.append(('coedge', pointers(-1, -1, 16 + (i + 1) % 4,
                                        -1, -1, 12 + i)
                     + [('b', coedge_reverse)]))
    recs += [('loop', pointers(-1, -1, -1, 16)),  # 20
             ('plane-surface', [('P', (0, 0, 0)), ('V', (0, 0, 1)),
                                ('V', (1, 0, 0))]),
             ('face', pointers(-1, -1, -1, 20, -1, -1, 21))]
    return recs, corners


class ParseTests(unittest.TestCase):
    def test_sat_header_and_old_point(self):
        header, recs = acis.parse_sat(sat('point $-1 2 3 4 #'))
        self.assertEqual(header, dict(version=400, nrec=1, nent=1, flags=0,
                                      product=['Toy Model', '1.0', 'today'],
                                      units=[1.0, 0.01, 0.001]))
        self.assertEqual(recs, [('point', [('p', -1), ('p', -1),
                                          ('P', (2.0, 3.0, 4.0))])])

    def test_sat_new_style_index_and_history(self):
        text = sat('-7 point $-1 42 $-1 2 3 4 #', version=700)
        text = text.replace('700 1 1\n', '700 1 1 9\n')
        header, recs = acis.parse_sat(text)
        self.assertEqual(header['flags'], 9)
        self.assertEqual(recs, [('point', [('p', -1), ('n', 42), ('p', -1),
                                          ('P', (2.0, 3.0, 4.0))])])

    def test_sat_geometry_schemas(self):
        _, recs = acis.parse_sat(sat(
            'plane-surface $-1 1 2 3 0 0 1 1 0 0 #\n'
            'straight-curve $-1 2 3 4 1 0 0 #\n'
            'ellipse-curve $-1 0 0 0 0 0 1 2 0 0 0.5 #'))
        self.assertEqual(recs, [
            ('plane-surface', pointers(-1, -1) +
             [('P', (1., 2., 3.)), ('V', (0., 0., 1.)), ('V', (1., 0., 0.))]),
            ('straight-curve', pointers(-1, -1) +
             [('P', (2., 3., 4.)), ('V', (1., 0., 0.))]),
            ('ellipse-curve', pointers(-1, -1) +
             [('P', (0., 0., 0.)), ('V', (0., 0., 1.)),
              ('V', (2., 0., 0.)), ('d', 0.5)])])

    def test_sat_edge_numbers_senses_and_strings(self):
        _, recs = acis.parse_sat(sat(
            'edge $-1 $2 $3 $4 $5 0 2.5 forward reversed I @7 two xyz #'))
        self.assertEqual(recs, [('edge', pointers(-1, -1, 2, 3, 4, 5) +
                                [('d', 0.0), ('d', 2.5), ('b', False),
                                 ('b', True), ('x', 'I'), ('s', 'two xyz')])])

    def test_sat_terminator_and_unterminated_record(self):
        for tail in ('End-of-ACIS-data # point $-1 9 9 9 #',
                     'point $-1 9 9 9'):
            with self.subTest(tail=tail):
                _, recs = acis.parse_sat(sat('point $-1 1 2 3 # ' + tail))
                self.assertEqual(len(recs), 1)

    def test_sab_header_and_all_supported_field_types(self):
        fields = b''.join(bytes([tag]) + struct.pack('<i', value)
                          for tag, value in [(3, -2), (4, 3), (5, 4)])
        fields += b'\x06' + struct.pack('<d', 1.25)
        fields += b'\x07\x02hi\x08\x02\x00ok\x09\x01\x00\x00\x00\xe9'
        fields += b'\x0a\x0b\x0c' + struct.pack('<i', -1)
        fields += b'\x13' + struct.pack('<3d', 1, 2, 3)
        fields += b'\x14' + struct.pack('<3d', 0, 0, 1)
        fields += b'\x15' + struct.pack('<i', 7)
        header, recs = acis.parse_sab(sab_header() + b'\x0d\x03toy\x0e\x06record'
                                     + fields + b'\x11')
        self.assertEqual(header, dict(version=22000, nrec=1, nent=1, flags=0,
                                      product=['Toy', '1.0', 'today'],
                                      units=[1.0, 0.01, 0.001]))
        self.assertEqual(recs, [('toy-record', [
            ('i', -2), ('i', 3), ('i', 4), ('d', 1.25),
            ('s', 'hi'), ('s', 'ok'), ('s', '\xe9'), ('b', True), ('b', False),
            ('p', -1), ('P', (1., 2., 3.)), ('V', (0., 0., 1.)), ('e', 7)])])

    def test_sab_terminator_ignores_trailing_bytes(self):
        end = b'\x0d\x03End\x0e\x02of\x0e\x04ACIS\x0e\x04data'
        _, recs = acis.parse_sab(sab_header() + b'\x0d\x04body\x11' + end + b'\xff')
        self.assertEqual(recs, [('body', [])])

    def test_sab_rejects_bad_magic_and_unknown_tag(self):
        with self.assertRaisesRegex(ValueError, 'not SAB'):
            acis.parse_sab(b'invented')
        with self.assertRaisesRegex(ValueError, 'SAB tag 0xff at'):
            acis.parse_sab(sab_header() + b'\xff')

    def test_parse_trivial_entity_dictionary(self):
        self.assertIsNone(acis.parse({}))
        self.assertIsNone(acis.parse({'acis': ('sat', '')}))
        for fmt, data, parser in [('sat', sat('point $-1 1 2 3 #'), acis.parse_sat),
                                  ('sab', sab_header(), acis.parse_sab)]:
            with self.subTest(fmt=fmt):
                self.assertEqual(acis.parse({'acis': (fmt, data)}), parser(data))


class GeometryTests(unittest.TestCase):
    def test_cross_product_order_and_parallel_vectors(self):
        self.assertEqual(acis._vec_cross((1, 2, 3), (4, 5, 6)), (-3, 6, -3))
        self.assertEqual(acis._vec_cross((4, 5, 6), (1, 2, 3)), (3, -6, 3))
        self.assertEqual(acis._vec_cross((1, 2, 3), (2, 4, 6)), (0, 0, 0))

    def test_straight_curve_preserves_parameter_order(self):
        recs = [('straight-curve', [('P', (1, 2, 3)), ('V', (2, -1, 0))])]
        self.assertEqual(acis.curve_points(recs, 0, 2, -1, n_arc=99),
                         [(5, 0, 3), (-1, 3, 3)])

    def test_full_ellipse_sampling_count_axes_and_closure(self):
        # n_arc=3 gives four segments (five points), including both endpoints.
        for ratio in (1.0, 0.5):
            with self.subTest(ratio=ratio):
                recs = [('ellipse-curve', [('P', (1, 2, 3)), ('V', (0, 0, 1)),
                                           ('V', (2, 0, 0)), ('d', ratio)])]
                pts = acis.curve_points(recs, 0, 0, 2 * math.pi, n_arc=3)
                expected = [(3, 2, 3), (1, 2 + 2 * ratio, 3), (-1, 2, 3),
                            (1, 2 - 2 * ratio, 3), (3, 2, 3)]
                self.assertEqual(len(pts), 5)
                for actual, want in zip(pts, expected):
                    for a, b in zip(actual, want):
                        self.assertAlmostEqual(a, b)
                self.assertEqual(acis.curve_points(recs, 0, 2 * math.pi, 0, 3), pts)

    def test_zero_length_ellipse_has_three_samples(self):
        recs = [('ellipse-curve', [('P', (0, 0, 0)), ('V', (0, 0, 1)),
                                   ('V', (1, 0, 0)), ('d', 1)])]
        self.assertEqual(acis.curve_points(recs, 0, 0, 0, n_arc=1), [(1, 0, 0)] * 3)

    def test_unknown_curve_returns_none(self):
        self.assertIsNone(acis.curve_points([('invented-curve', [])], 0, 0, 1))

    def test_square_area_and_orientation(self):
        square = [(0, 0), (2, 0), (2, 2), (0, 2)]
        self.assertEqual(acis.area(square), 4)
        self.assertEqual(acis.area(square[::-1]), -4)
        self.assertEqual(acis.area(square + [square[0]]), 4)

    def test_triangle_area_ignores_z(self):
        self.assertEqual(acis.area([(1, 1, 7), (5, 1, -3), (1, 4, 9)]), 6)

    def test_area_degenerate_and_empty_loops(self):
        for loop in ([(1, 1)], [(1, 1), (2, 2)], [(0, 0), (1, 1), (2, 2)]):
            with self.subTest(loop=loop):
                self.assertEqual(acis.area(loop), 0)
        with self.assertRaises(IndexError):
            acis.area([])

    def test_area_large_translation(self):
        self.assertEqual(acis.area([(1e10, 1e10), (1e10 + 2, 1e10),
                                    (1e10 + 2, 1e10 + 2), (1e10, 1e10 + 2)]), 4)

    def test_faces_square_loop_and_surface(self):
        recs, corners = square_records()
        self.assertEqual(acis.faces(recs), [dict(loops=[corners],
                                                surface='plane-surface', approx=False)])

    def test_faces_reversal_flags_combine(self):
        for edge_rev, coedge_rev in [(True, False), (False, True), (True, True)]:
            with self.subTest(edge=edge_rev, coedge=coedge_rev):
                recs, corners = square_records(edge_reverse=edge_rev,
                                                coedge_reverse=coedge_rev)
                expected = corners[1:] + corners[:1] if edge_rev != coedge_rev else corners
                self.assertEqual(acis.faces(recs)[0]['loops'], [expected])

    def test_faces_unknown_curve_marks_approximation(self):
        recs, corners = square_records(curve_name='invented-curve')
        self.assertEqual(acis.faces(recs), [dict(loops=[corners],
                                                surface='plane-surface', approx=True)])

    def test_faces_empty_and_missing_loop(self):
        self.assertEqual(acis.faces([]), [])
        self.assertEqual(acis.faces([('face', [])]),
                         [dict(loops=[], surface=None, approx=False)])

    def test_wire_vertex_fallback_ignores_edge_sense(self):
        for name in ('straight-curve', 'invented-curve'):
            with self.subTest(curve=name):
                recs, corners = square_records(curve_name=name, edge_reverse=True)
                self.assertEqual(acis.wire(recs),
                                 [[corners[i], corners[(i + 1) % 4]] for i in range(4)])

    def test_wire_parameterised_edge_and_bad_edges(self):
        recs = [('straight-curve', [('P', (1, 2, 3)), ('V', (2, 0, 0))]),
                ('edge', pointers(-1, -1, -1, -1, -1, 0) + [('d', 0), ('d', 2)]),
                ('edge', []),  # malformed edge is silently omitted
                ('edge', pointers(-1, -1, -1, -1, -1, -1))]  # no endpoints
        self.assertEqual(acis.wire(recs), [[(1, 2, 3), (5, 2, 3)]])
        self.assertEqual(acis.wire([]), [])


if __name__ == '__main__':
    unittest.main()
