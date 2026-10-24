import math
import tempfile
import unittest
from pathlib import Path
from unittest.mock import mock_open, patch

import dwglin


class LinExtraTests(unittest.TestCase):
    def test_empty_and_comments(self):
        self.assertEqual(dwglin.parse_lin('\r\n\t; comment\n'), {})

    def test_description_commas(self):
        self.assertEqual(dwglin.parse_lin('*x, first, second ;ignored\nA,1'),
                         {'X': ('first, second', [1.0])})

    def test_numeric_forms(self):
        self.assertEqual(dwglin.parse_lin('*X,\n a ,\t.5, -.25,+1e-3,2.\t')['X'],
                         ('', [0.5, -0.25, 0.001, 2.0]))

    def test_quoted_punctuation(self):
        dash = dwglin.parse_lin('*X\nA,["a;,[b]",Standard]; ignored')['X'][1][0]
        self.assertEqual(dash, {'length': 0.0, 'text': 'a;,[b]',
                                'style': 'Standard'})

    def test_adjacent_complex_elements(self):
        dashes = dwglin.parse_lin('*X\nA,-2,["a",s],["b",s],0')['X'][1]
        self.assertEqual([d['length'] for d in dashes[:2]], [-2.0, 0.0])
        self.assertEqual(dashes[2], 0.0)

    def test_multiple_pattern_lines(self):
        dashes = dwglin.parse_lin('*X\nA,1,-2\n;comment\nA,["a",s],3')['X'][1]
        self.assertEqual(dashes, [1.0, -2.0,
                                 {'length': 0.0, 'text': 'a', 'style': 's'}, 3.0])

    def test_options_order_and_case(self):
        dash = dwglin.parse_lin(
            '*X\nA,0,[BOX,a.shx,y=.5,a=-180,x=2,s=.1]')['X'][1][0]
        self.assertEqual(dash, {'length': 0.0, 'shape_name': 'BOX',
                                'shxfile': 'a.shx', 'y': .5,
                                'rotation': -math.pi, 'absolute': True,
                                'x': 2.0, 'scale': .1})

    def test_integer_shape_and_omitted_options(self):
        dash = dwglin.parse_lin('*X\nA,[00130,a.shx]')['X'][1][0]
        self.assertEqual(dash, {'length': 0.0, 'shape': 130, 'shxfile': 'a.shx'})

    def test_malformed_patterns_have_line_numbers(self):
        for pattern in ('B,1', 'A,1,no', 'A,1,', 'A,,1', 'A,[BOX]',
                        'A,["x,s]', 'A,[BOX,s', 'A,1]',
                        'A,[BOX,s,Q=2]', 'A,[BOX,s,S=bad]', 'A,nan'):
            with self.subTest(pattern=pattern):
                with self.assertRaisesRegex(ValueError, r'line 3:'):
                    dwglin.parse_lin(';comment\n*X\n' + pattern)

    def test_header_required_and_empty_name(self):
        for text in (';comment\nA,1', '\n*,description'):
            with self.assertRaisesRegex(ValueError, r'line 2:'):
                dwglin.parse_lin(text)

    def test_duplicate_resets_all_dashes(self):
        self.assertEqual(dwglin.parse_lin('*X,old\nA,1\nA,2\n*x\nA,3'),
                         {'X': ('', [3.0])})

    def test_latin1_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'test.lin'
            path.write_bytes(b'*CAF\xc9,caf\xe9\r\nA,1')
            self.assertEqual(dwglin.parse_lin_file(path),
                             {'CAFÉ': ('café', [1.0])})

    def test_file_closed_on_parse_error(self):
        opener = mock_open(read_data='A,1')
        with patch('builtins.open', opener):
            with self.assertRaises(ValueError):
                dwglin.parse_lin_file('example.lin')
        opener.assert_called_once_with('example.lin', encoding='latin-1')
        opener.return_value.__exit__.assert_called_once()


if __name__ == '__main__':
    unittest.main()
