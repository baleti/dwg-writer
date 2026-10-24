import unittest

from dwgunits import format_length as fmt, parse_dim_text


class ExtraUnitsTests(unittest.TestCase):
    def test_increment_ties(self):
        self.assertEqual(fmt(1.25, dec=2, rnd=.5), "1.50")
        self.assertEqual(fmt(-1.25, dec=2, rnd=.5), "-1.50")

    def test_scaling_before_rounding(self):
        self.assertEqual(fmt(1.25, dec=1, lfac=2, rnd=1), "3.0")
        self.assertEqual(fmt(1.25, dec=1, lfac=-2, rnd=1), "-3.0")

    def test_decimal_ties(self):
        self.assertEqual(fmt(1.005, dec=2), "1.01")
        self.assertEqual(fmt(-1.005, dec=2), "-1.01")

    def test_scientific(self):
        self.assertEqual(fmt(.00123456, 1, 3), "1.235E-03")
        self.assertEqual(fmt(-99.99, 1, 2), "-1.00E+02")
        self.assertEqual(fmt(0, 1, 2), "0.00E+00")

    def test_fraction_reduction(self):
        self.assertEqual(fmt(3.5, 5, 4), "3 1/2")
        self.assertEqual(fmt(.75, 5, 8), "3/4")
        self.assertEqual(fmt(3.5, 4, 4), '3 1/2"')

    def test_architectural_carry(self):
        self.assertEqual(fmt(11 + 15 / 16, 4, 4, rnd=.125), "1'")
        self.assertEqual(fmt(11.5, 4, 0), "1'")

    def test_engineering_carry(self):
        self.assertEqual(fmt(11.999, 3, 2), "1'")
        self.assertEqual(fmt(-11.999, 3, 2), "-1'")

    def test_negative_zero(self):
        for unit in (2, 3, 4, 5):
            with self.subTest(unit=unit):
                self.assertNotIn("-", fmt(-.001, unit, 2))
        self.assertEqual(fmt(-.1, 1, 2, rnd=1), "0.00E+00")
        self.assertEqual(fmt(-0.0, 2, 2, zin=12), "0")

    def test_feet_inches_modes(self):
        for unit in (3, 4):
            for mode, expected in enumerate(("2'", "2'-0\"", "2'", "2'-0\"")):
                with self.subTest(unit=unit, mode=mode):
                    self.assertEqual(fmt(24, unit, 0, zin=mode), expected)
            self.assertEqual(fmt(3, unit, 0, zin=1), "0'-3\"")
            self.assertEqual(fmt(3, unit, 0, zin=2), "0'-3\"")
            self.assertEqual(fmt(3, unit, 0, zin=3), '3"')
            self.assertEqual(fmt(0, unit, 0, zin=0), '0"')

    def test_engineering_decimal_flags(self):
        self.assertEqual(fmt(.5, 3, 4, zin=13), "0'-.5\"")
        self.assertEqual(fmt(12.5, 3, 4, zin=12), "1'-.5\"")

    def test_separator_and_affixes(self):
        self.assertEqual(fmt(-15.5, 3, 2, dsep=",", prefix="[", suffix="]"),
                         "[-1'-3,50\"]")
        self.assertEqual(fmt(12.5, 1, 2, dsep=","), "1,25E+01")

    def test_zero_scale_and_disabled_increment(self):
        self.assertEqual(fmt(5, lfac=0, dec=0), "0")
        self.assertEqual(fmt(1.25, dec=2, rnd=-1), "1.25")

    def test_overrides(self):
        self.assertEqual(parse_dim_text(r"<>\X<> mm", "3.5"), r"3.5\X3.5 mm")
        self.assertEqual(parse_dim_text("  ", "3.5"), "  ")
        self.assertEqual(parse_dim_text(" ", "3.5"), "")
        self.assertEqual(parse_dim_text("", "3.5"), "3.5")

    def test_invalid_arguments(self):
        for options in ({"lunit": 6}, {"dec": -1}, {"lunit": 4, "dec": 9},
                        {"dsep": ".."}):
            with self.subTest(options=options), self.assertRaises(ValueError):
                fmt(1, **options)


if __name__ == "__main__":
    unittest.main()
