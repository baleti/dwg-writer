"""Tests for inline hatch pattern parsing, lookup, and expansion.

Findings
--------
(fixed in dwgpat) parse_pat() did not close the file it opened.
"""

import math
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import dwgpat


PATTERNS = """
; A comment before any pattern
17, 1, 2, 3, 4

*SIMPLE, comment
45, 0,0, 0,0.125

 ; A comment between patterns
* DaShEd , alternating strokes and gaps
 0, 0,0, 0,0.25, 0.125,-0.125 ; inline comment

* tWo , two line families
 0 , 1 , 2 , 0 , 0.5
; A comment between families

 90 , -1 , 3 , 0.25 , 0 , 0.5 , -0.25 , 0
1, 2, 3, 4
"""

SIMPLE = [(45.0, 0.0, 0.0, 0.0, 0.125, [])]
DASHED = [(0.0, 0.0, 0.0, 0.0, 0.25, [0.125, -0.125])]
TWO = [
    (0.0, 1.0, 2.0, 0.0, 0.5, []),
    (90.0, -1.0, 3.0, 0.25, 0.0, [0.5, -0.25, 0.0]),
]


class PatternFileTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.patfile = Path(directory.name) / "inline.pat"
        self.patfile.write_text(PATTERNS, encoding="latin1")
        # SEARCH captures DWG_PAT at import time, so patch both to isolate lookup.
        search = patch.object(dwgpat, "SEARCH", [])
        search.start()
        self.addCleanup(search.stop)
        environment = patch.dict(os.environ, {"DWG_PAT": ""})
        environment.start()
        self.addCleanup(environment.stop)

    def test_parse_structure_and_uppercase_names(self):
        result = dwgpat.parse_pat(self.patfile)
        self.assertIsInstance(result, dict)
        self.assertEqual(result, {"SIMPLE": SIMPLE, "DASHED": DASHED, "TWO": TWO})
        for families in result.values():
            self.assertIsInstance(families, list)
            for family in families:
                self.assertIsInstance(family, tuple)
                self.assertEqual(len(family), 6)
                for field in family[:5]:
                    self.assertIsInstance(field, float)
                self.assertIsInstance(family[5], list)
                for dash in family[5]:
                    self.assertIsInstance(dash, float)

    def test_comments_blanks_and_short_trailing_line_are_ignored(self):
        result = dwgpat.parse_pat(self.patfile)
        self.assertEqual(len(result), 3)
        self.assertEqual(result["SIMPLE"], SIMPLE)
        self.assertEqual(result["DASHED"], DASHED)
        self.assertEqual(result["TWO"], TWO)

    def test_comment_only_file_is_empty(self):
        self.patfile.write_text("\n ; only a comment\n \n", encoding="latin1")
        self.assertEqual(dwgpat.parse_pat(self.patfile), {})

    def test_parse_closes_input_file(self):
        with self.patfile.open(encoding="latin1") as handle:
            with patch("builtins.open", return_value=handle):
                dwgpat.parse_pat(self.patfile)
            self.assertTrue(handle.closed)

    def test_load_user_pattern_case_insensitively(self):
        for name in ("dashed", "DASHED", "DaShEd"):
            with self.subTest(name=name):
                self.assertEqual(dwgpat.load(name, self.patfile), DASHED)

    def test_user_pattern_overrides_builtin(self):
        self.patfile.write_text("*LiNe, custom\n30, 1,2, 3,4, 0.5,-0.5\n",
                                encoding="latin1")
        self.assertEqual(
            dwgpat.load("line", self.patfile),
            [(30.0, 1.0, 2.0, 3.0, 4.0, [0.5, -0.5])],
        )

    def test_missing_user_pattern_falls_back_to_builtin(self):
        self.assertEqual(dwgpat.load("aNsI31", self.patfile), SIMPLE)
        self.assertEqual(dwgpat.load("aNsI31", self.patfile),
                         dwgpat.BUILTIN["ANSI31"])

    def test_builtin_without_pattern_file(self):
        self.assertEqual(dwgpat.load("ansi31"), SIMPLE)
        self.assertEqual(dwgpat.load("solid"), [])

    def test_unknown_name_raises_key_error(self):
        for patfile in (None, self.patfile):
            with self.subTest(patfile=patfile):
                with self.assertRaises(KeyError):
                    dwgpat.load("not_an_inline_pattern", patfile)


class ExpansionTests(unittest.TestCase):
    def assertVectorAlmostEqual(self, actual, expected):
        self.assertIsInstance(actual, tuple)
        self.assertEqual(len(actual), 2)
        for value, wanted in zip(actual, expected):
            self.assertAlmostEqual(value, wanted)

    def test_degrees_are_converted_to_radians(self):
        lines = [(degrees, 0, 0, 0, 0, []) for degrees in (0, 45, 90, 180)]
        expanded = dwgpat.expand(lines)
        self.assertIsInstance(expanded, list)
        self.assertEqual(len(expanded), 4)
        for line, angle in zip(expanded, (0, math.pi / 4, math.pi / 2, math.pi)):
            self.assertIsInstance(line, tuple)
            self.assertEqual(len(line), 4)
            self.assertAlmostEqual(line[0], angle)
            self.assertVectorAlmostEqual(line[1], (0, 0))
            self.assertVectorAlmostEqual(line[2], (0, 0))
            self.assertEqual(line[3], [])

    def test_scale_multiplies_base_offset_and_signed_dashes(self):
        lines = [(0, 2, -3, 4, -5, [0.125, -0.25, 0])]
        angle, base, offset, dashes = dwgpat.expand(lines, scale=2.5)[0]
        self.assertEqual(angle, 0)
        self.assertVectorAlmostEqual(base, (5, -7.5))
        self.assertVectorAlmostEqual(offset, (10, -12.5))
        self.assertEqual(dashes, [0.3125, -0.625, 0])
        self.assertEqual(lines, [(0, 2, -3, 4, -5, [0.125, -0.25, 0])])

    def test_quarter_turn_with_ninety_degree_line(self):
        # Final angle pi: R(pi) * (0, 0.5) = (0, -0.5).
        angle, base, offset, dashes = dwgpat.expand(
            [(90, 0, 0, 0, 0.5, [])], angle_rad=math.pi / 2
        )[0]
        self.assertAlmostEqual(angle, math.pi)
        self.assertVectorAlmostEqual(base, (0, 0))
        self.assertVectorAlmostEqual(offset, (0, -0.5))
        self.assertEqual(dashes, [])

    def test_forty_five_degree_rotation_and_scale(self):
        # R(45) * (1, 2) * 2 = (-sqrt(2), 3*sqrt(2)).
        # Line angle 45 + rotation 45 = 90; R(90) * (3, 4) * 2 = (-8, 6).
        angle, base, offset, dashes = dwgpat.expand(
            [(45, 1, 2, 3, 4, [0.5, -0.25])],
            scale=2,
            angle_rad=math.pi / 4,
        )[0]
        self.assertAlmostEqual(angle, math.pi / 2)
        self.assertVectorAlmostEqual(base, (-math.sqrt(2), 3 * math.sqrt(2)))
        self.assertVectorAlmostEqual(offset, (-8, 6))
        self.assertEqual(dashes, [1, -0.5])

    def test_empty_lines(self):
        self.assertEqual(dwgpat.expand([]), [])
        self.assertEqual(dwgpat.expand([], scale=3, angle_rad=math.pi / 4), [])

    def test_zero_scale(self):
        angle, base, offset, dashes = dwgpat.expand(
            [(45, 1, -2, 3, -4, [0.125, -0.125, 0])],
            scale=0,
            angle_rad=math.pi / 2,
        )[0]
        self.assertAlmostEqual(angle, 3 * math.pi / 4)
        self.assertVectorAlmostEqual(base, (0, 0))
        self.assertVectorAlmostEqual(offset, (0, 0))
        self.assertEqual(dashes, [0, 0, 0])


if __name__ == "__main__":
    unittest.main()
