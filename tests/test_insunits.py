import unittest
import dwginsunits as U


class T(unittest.TestCase):
    def test_names(self):
        self.assertEqual(U.NAMES[4], 'Millimeters'); self.assertEqual(U.NAMES[21], 'US Survey Feet'); self.assertEqual(len(U.NAMES), 25)
        self.assertEqual(U.name(6), 'Meters'); self.assertEqual(U.name(99), 'Unknown (99)')

    def test_mm_table(self):
        self.assertNotIn(0, U.MM)
        self.assertEqual(U.MM[1], 25.4); self.assertEqual(U.MM[2], 304.8); self.assertEqual(U.MM[6], 1000)
        self.assertEqual(sorted(U.MM), list(range(1, 25)))

    def test_to_mm(self):
        self.assertEqual(U.to_mm(2, 6), 2000)
        self.assertIsNone(U.to_mm(1, 0)); self.assertIsNone(U.to_mm(1, 99))

    def test_convert(self):
        self.assertAlmostEqual(U.convert(1, 2, 1), 12.0)
        self.assertAlmostEqual(U.convert(1000, 4, 6), 1.0)
        self.assertIsNone(U.convert(1, 0, 4)); self.assertIsNone(U.convert(1, 4, 0))


if __name__ == '__main__':
    unittest.main()
