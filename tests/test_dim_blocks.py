"""Synthetic characterisation tests; font metrics are deliberately fixed."""
import math
import sys
import types
import unittest
from unittest.mock import patch

import dwgdim


class FakeDocument:
    def __init__(self, existing_defpoints=False, **style):
        self.style = dict(DIMSCALE=1, DIMASZ=2, DIMEXO=1, DIMEXE=3,
                          DIMTXT=2, DIMGAP=1, DIMDEC=2, DIMLFAC=1,
                          DIMTAD=1, DIMCEN=0.5)
        self.style.update(style)
        self.objects = {'style': self.style}
        self.layer_table = {'defpoints': 'layer'} if existing_defpoints else {}
        self.calls = []

    def dimstyles(self):
        return {'standard': 'style'}

    def get(self, handle):
        return self.objects[handle]

    def add_block(self, name):
        self.calls.append(('add_block', (name,), {}))
        self.objects['block'] = {'handle': 'block', 'name': name}
        return 'block'

    def put(self, obj):
        self.calls.append(('put', (dict(obj),), {}))
        self.objects[obj['handle']] = obj

    def layers(self):
        return self.layer_table

    def add_layer(self, name, **kwargs):
        self.calls.append(('add_layer', (name,), kwargs))
        self.layer_table[name.lower()] = 'layer'

    def _record(self, name, args, kwargs):
        self.calls.append((name, args, kwargs))

    def add_line(self, *args, **kwargs):
        self._record('add_line', args, kwargs)

    def add_solid(self, *args, **kwargs):
        self._record('add_solid', args, kwargs)

    def add_mtext(self, *args, **kwargs):
        self._record('add_mtext', args, kwargs)

    def add_arc(self, *args, **kwargs):
        self._record('add_arc', args, kwargs)

    def add_point(self, *args, **kwargs):
        self._record('add_point', args, kwargs)


class DimensionBlockTests(unittest.TestCase):
    def setUp(self):
        # This source-only checkout omits dwgfont. Width 2 * factor 2 = 4
        # isolates builder geometry from external font files and metrics.
        font = types.ModuleType('dwgfont')
        font.text_width = lambda body, height: 2.0
        font.style_factor = lambda style: 2.0
        patcher = patch.dict(sys.modules, {'dwgfont': font})
        patcher.start()
        self.addCleanup(patcher.stop)
        self.doc = FakeDocument()

    def dimension(self, **changes):
        d = dict(type=22, pt13=(0, 0, 9), pt14=(20, 0, 8),
                 pt10=(20, 5, 7), measurement=20, user_text='', dim_rot=0)
        d.update(changes)
        return d

    def linear(self, **changes):
        d = self.dimension(**changes)
        return d, dwgdim.build_linear_block(self.doc, d, 'StAnDaRd')

    def assertPoint(self, actual, expected):
        self.assertEqual(len(actual), len(expected))
        for a, b in zip(actual, expected):
            self.assertAlmostEqual(a, b)

    def assertLine(self, actual, start, end):
        self.assertEqual(actual[0], 'L')
        self.assertPoint(actual[1], start)
        self.assertPoint(actual[2], end)

    def assertKinds(self, ents, kinds):
        self.assertEqual(''.join(e[0] for e in ents), kinds)

    def test_horizontal_geometry_and_definition_points(self):
        d, ents = self.linear()
        self.assertKinds(ents, 'LLLSSTPPP')
        self.assertLine(ents[0], (0, 1), (0, 8))
        self.assertLine(ents[1], (20, 1), (20, 8))
        self.assertLine(ents[2], (0, 5), (20, 5))
        self.assertEqual(ents[5], ('T', (10, 6), r'\A1;20.00', 2, 8, 0))
        self.assertEqual(ents[6:], [('P', (0, 0)), ('P', (20, 0)), ('P', (20, 5))])
        self.assertEqual(d['text_mid'], (10, 6))

    def test_horizontal_arrow_vertices(self):
        _, ents = self.linear()
        for entity, expected in zip(ents[3:5], [
                [(2, 5 + 1 / 3), (2, 5 - 1 / 3), (0, 5), (0, 5)],
                [(18, 5 + 1 / 3), (18, 5 - 1 / 3), (20, 5), (20, 5)]]):
            self.assertEqual(entity[0], 'S')
            self.assertEqual(len(entity[1]), 4)
            for actual, point in zip(entity[1], expected):
                self.assertPoint(actual, point)

    def test_vertical_geometry(self):
        d, ents = self.linear(pt14=(0, 20), pt10=(-5, 20))
        self.assertKinds(ents, 'LLLSSTPPP')
        self.assertLine(ents[0], (-1, 0), (-8, 0))
        self.assertLine(ents[1], (-1, 20), (-8, 20))
        self.assertLine(ents[2], (-5, 0), (-5, 20))
        self.assertPoint(d['text_mid'], (-6, 10))
        self.assertAlmostEqual(ents[5][5], math.pi / 2)

    def test_rotated_type_21_projects_first_point(self):
        d, ents = self.linear(type=21, dim_rot=math.pi / 4,
                              pt14=(10, 0), pt10=(8, 2))
        h = math.sqrt(0.5)
        self.assertKinds(ents, 'LLLSSTPPP')
        self.assertLine(ents[0], (-h, h), (3 - 3*h, -3 + 3*h))
        self.assertLine(ents[1], (10 - h, h), (8 - 3*h, 2 + 3*h))
        self.assertLine(ents[2], (3, -3), (8, 2))
        self.assertPoint(d['text_mid'], (5.5 - h, -0.5 + h))
        self.assertEqual(ents[5][5], math.pi / 4)

    def test_negative_offset_side(self):
        d, ents = self.linear(pt10=(20, -5))
        self.assertLine(ents[0], (0, -1), (0, -8))
        self.assertLine(ents[1], (20, -1), (20, -8))
        self.assertLine(ents[2], (0, -5), (20, -5))
        self.assertEqual(d['text_mid'], (10, -6))

    def test_centered_text_splits_long_dimension_line(self):
        self.doc.style['DIMTAD'] = 0
        d, ents = self.linear()
        self.assertKinds(ents, 'LLLLSSTPPP')
        self.assertLine(ents[2], (0, 5), (7, 5))
        self.assertLine(ents[3], (20, 5), (13, 5))
        self.assertEqual(ents[6], ('T', (10, 5), r'\A1;20.00', 2, 5, 0))
        self.assertEqual(d['text_mid'], (10, 5))

    def test_centered_text_at_exact_fit_keeps_one_line(self):
        self.doc.style['DIMTAD'] = 0
        _, ents = self.linear(pt14=(10, 0), pt10=(10, 5))
        # Threshold is 2 * arrow size + 2 * (width / 2 + gap) = 10.
        self.assertKinds(ents, 'LLLSSTPPP')
        self.assertLine(ents[2], (0, 5), (10, 5))

    def test_scale_two_scales_style_geometry(self):
        self.doc.style['DIMSCALE'] = 2
        d, ents = self.linear()
        self.assertLine(ents[0], (0, 2), (0, 11))
        self.assertEqual(ents[5], ('T', (10, 7), r'\A1;20.00', 4, 8, 0))
        self.assertEqual(d['text_mid'], (10, 7))

    def test_linear_user_text_and_zero_length_factor(self):
        self.doc.style['DIMLFAC'] = 0
        _, ents = self.linear(user_text='[<>] / <>', measurement=3.125)
        self.assertEqual(ents[5][2], r'\A1;[3.12] / 3.12')

    def test_fmt_precision_sign_and_factor(self):
        for args, expected in [((12, 2), '12.00'), ((1.25, 1), '1.2'),
                               ((1.75, 1), '1.8'), ((-0.001, 2), '-0.00'),
                               ((2.5, 3, 2), '5.000'), ((4, 0, 0), '0')]:
            with self.subTest(args=args):
                self.assertEqual(dwgdim._fmt(*args), expected)

    def radial(self, **changes):
        d = self.dimension(type=25, pt10=(0, 0), pt15=(10, 0), measurement=10)
        d.update(changes)
        return d, dwgdim.build_radial_block(self.doc, d, 'STANDARD')

    def test_radius_geometry_center_marks_and_text(self):
        d, ents = self.radial()
        self.assertKinds(ents, 'SLLLTPP')
        self.assertLine(ents[1], (8, 0), (13, 0))
        self.assertLine(ents[2], (-0.5, 0), (0.5, 0))
        self.assertLine(ents[3], (0, -0.5), (0, 0.5))
        self.assertEqual(ents[4], ('T', (16, 0), r'\A1;R10.00', 2, 5, 0))
        self.assertEqual(ents[5:], [('P', (10, 0)), ('P', (0, 0))])
        self.assertEqual(d['text_mid'], (16, 0))

    def test_diameter_far_line_starts_outside_chord(self):
        d, ents = self.radial(type=26, pt10=(-10, 0), measurement=20)
        self.assertKinds(ents, 'SLSLTPP')
        self.assertLine(ents[1], (8, 0), (13, 0))
        self.assertLine(ents[3], (-12, 0), (8, 0))
        self.assertEqual(ents[2][1][2:], [(-10, 0), (-10, 0)])
        self.assertEqual(ents[4][2], r'\A1;%%c20.00')
        self.assertEqual(ents[-1], ('P', (-10, 0)))

    def test_radial_override_replaces_without_automatic_prefix(self):
        self.doc.style['DIMLFAC'] = 2
        _, ents = self.radial(user_text='radius <>')
        self.assertEqual(ents[4][2], r'\A1;radius 20.00')

    def test_zero_radius_uses_positive_x_direction(self):
        d, ents = self.radial(pt15=(0, 0), measurement=0)
        self.assertKinds(ents, 'SLLLTPP')
        self.assertLine(ents[1], (-2, 0), (3, 0))
        self.assertEqual(d['text_mid'], (6, 0))

    def angular(self, **changes):
        d = self.dimension(type=23, pt15=(0, 0), pt13=(2, 0),
                           pt14=(0, 2), pt10=(10, 0))
        d.update(changes)
        return d, dwgdim.build_angular_block(self.doc, d, 'standard')

    def test_angular_quarter_circle(self):
        d, ents = self.angular()
        self.assertKinds(ents, 'LLASSTPPPP')
        self.assertLine(ents[0], (3, 0), (13, 0))
        self.assertLine(ents[1], (0, 3), (0, 13))
        self.assertEqual(ents[2], ('A', (0, 0), 10, 0, math.pi / 2))
        self.assertAlmostEqual(d['measurement'], math.pi / 2)
        pos = 11 / math.sqrt(2) + 1.5
        self.assertPoint(d['text_mid'], (pos, pos))
        self.assertPoint(ents[5][1], (pos, pos))
        self.assertEqual(ents[5][2:], (r'\A1;90.00\U+00B0', 2, 5, 0))
        self.assertEqual(ents[6:], [('P', (2, 0)), ('P', (0, 2)),
                                    ('P', (10, 0)), ('P', (0, 0))])

    def test_angular_omits_extensions_when_legs_reach_past_arc(self):
        _, ents = self.angular(pt13=(12, 0), pt14=(0, 20))
        self.assertKinds(ents, 'ASSTPPPP')

    def test_angular_wraparound_and_override(self):
        self.doc.style['DIMLFAC'] = 7  # Angular formatting ignores this.
        d, ents = self.angular(pt13=(0, 2), pt14=(2, 0), user_text='angle <>')
        self.assertAlmostEqual(d['measurement'], 3 * math.pi / 2)
        self.assertEqual(ents[2], ('A', (0, 0), 10, math.pi / 2, 2 * math.pi))
        self.assertEqual(ents[5][2], r'\A1;angle 270.00\U+00B0')

    def ordinate(self, **changes):
        d = self.dimension(type=20, pt10=(10, 10), pt13=(3, 4), pt14=(9, 12))
        d.update(changes)
        return d, dwgdim.build_ordinate_block(self.doc, d, 'standard')

    def test_ordinate_default_y_uses_absolute_offset(self):
        d, ents = self.ordinate()
        self.assertKinds(ents, 'LTPPP')
        self.assertLine(ents[0], (4, 4), (9, 4))
        self.assertEqual(d['measurement'], 6)
        self.assertEqual(ents[1], ('T', (12, 4), r'\A1;6.00', 2, 5, 0))
        self.assertEqual(d['text_mid'], (12, 4))
        self.assertEqual(ents[2:], [('P', (3, 4)), ('P', (10, 10)), ('P', (9, 12))])

    def test_ordinate_x_flag_and_upward_leader(self):
        d, ents = self.ordinate(oflags=65)
        self.assertKinds(ents, 'LTPPP')
        self.assertLine(ents[0], (3, 5), (3, 12))
        self.assertEqual(d['measurement'], 7)
        self.assertEqual(ents[1], ('T', (3, 14), r'\A1;7.00', 2, 5, math.pi / 2))
        self.assertEqual(d['text_mid'], (3, 14))

    def test_ordinate_negative_leader_directions(self):
        for flags, start, end, pos in [(64, (3, 3), (3, 0), (3, -2)),
                                       (0, (2, 4), (0, 4), (-3, 4))]:
            with self.subTest(flags=flags):
                d, ents = self.ordinate(oflags=flags, pt14=(0, 0))
                self.assertLine(ents[0], start, end)
                self.assertEqual(d['text_mid'], pos)

    def test_ordinate_override_and_length_factor(self):
        self.doc.style['DIMLFAC'] = 2
        d, ents = self.ordinate(user_text='offset <>')
        self.assertEqual(d['measurement'], 6)
        self.assertEqual(ents[1][2], r'\A1;offset 12.00')

    def test_zero_dimscale_matches_one_for_all_builders(self):
        for build in (self.linear, self.radial, self.angular, self.ordinate):
            with self.subTest(builder=build.__name__):
                self.doc.style['DIMSCALE'] = 1
                expected_d, expected = build()
                self.doc.style['DIMSCALE'] = 0
                actual_d, actual = build()
                self.assertEqual(actual, expected)
                self.assertEqual(actual_d, expected_d)


class MakeBlockTests(unittest.TestCase):
    def test_emits_all_entity_types_with_document_arguments(self):
        doc = FakeDocument()
        vertices = [(1, 1), (2, 1), (2, 2), (2, 2)]
        ents = [('L', (1, 2), (3, 4)), ('S', vertices),
                ('T', (5, 6), 'label', 2, 8, 0.25),
                ('A', (7, 8), 9, -math.pi / 2, 5 * math.pi), ('P', (9, 10))]
        self.assertEqual(dwgdim.make_block(doc, ents, layer='Dimensions'), 'block')
        common = dict(block='block', layer='Dimensions', color=0)
        self.assertEqual(doc.calls, [
            ('add_block', ('*D',), {}),
            ('put', ({'handle': 'block', 'name': '*D', 'anonymous': 1},), {}),
            ('add_layer', ('Defpoints',), {'plot': False}),
            ('add_line', ((1, 2), (3, 4)), dict(common, lweight=-2)),
            ('add_solid', (vertices,), common),
            ('add_mtext', ((5, 6, 0.0), 'label', 2), dict(common, attachment=8, rot=0.25)),
            ('add_arc', ((7, 8), 9, 3 * math.pi / 2, math.pi), dict(common, lweight=-2)),
            ('add_point', ((9, 10),), dict(block='block', layer='Defpoints', color=0)),
        ])

    def test_existing_defpoints_and_default_layer(self):
        doc = FakeDocument(existing_defpoints=True)
        dwgdim.make_block(doc, [('L', (0, 0), (1, 1))])
        self.assertEqual([call[0] for call in doc.calls], ['add_block', 'put', 'add_line'])
        self.assertEqual(doc.calls[-1][2], dict(block='block', layer='0', color=0, lweight=-2))

    def test_empty_block_still_creates_anonymous_block_and_layer(self):
        doc = FakeDocument()
        self.assertEqual(dwgdim.make_block(doc, []), 'block')
        self.assertEqual(doc.get('block')['anonymous'], 1)
        self.assertEqual([call[0] for call in doc.calls], ['add_block', 'put', 'add_layer'])


if __name__ == '__main__':
    unittest.main()
