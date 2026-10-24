import unittest
import dwgunits as U


class UnitsTests(unittest.TestCase):
    def test_decimal(self):
        self.assertEqual(U.format_length(12.3456789, 2, 4), '12.3457')
        self.assertEqual(U.format_length(12.5, 2, 2), '12.50')
        self.assertEqual(U.format_length(-0.001, 2, 2), '0.00')
        self.assertEqual(U.format_length(0.0, 2, 0), '0')

    def test_zin_decimal(self):
        self.assertEqual(U.format_length(0.5, 2, 4, zin=4), '.5000')
        self.assertEqual(U.format_length(1.5, 2, 4, zin=8), '1.5')
        self.assertEqual(U.format_length(2.0, 2, 4, zin=8), '2')
        self.assertEqual(U.format_length(0.25, 2, 4, zin=12), '.25')

    def test_sep_prefix_suffix_lfac_rnd(self):
        self.assertEqual(U.format_length(12.5, 2, 2, dsep=','), '12,50')
        self.assertEqual(U.format_length(12.5, 2, 1, prefix='R', suffix=' mm'), 'R12.5 mm')
        self.assertEqual(U.format_length(100.0, 2, 1, lfac=0.5), '50.0')
        self.assertEqual(U.format_length(12.3, 2, 2, rnd=0.5), '12.50')
        self.assertEqual(U.format_length(2.5, 2, 0, rnd=1.0), '3')

    def test_scientific(self):
        self.assertEqual(U.format_length(12.3456, 1, 2), '1.23E+01')

    def test_architectural(self):
        self.assertEqual(U.format_length(15.5, 4, 2), "1'-3 1/2\"")
        self.assertEqual(U.format_length(3.5, 4, 4, zin=0), '3 1/2"')
        self.assertEqual(U.format_length(0.0, 4, 2, zin=1), "0'-0\"")
        self.assertEqual(U.format_length(24.0, 4, 2), "2'")
        self.assertEqual(U.format_length(11.99, 4, 4), "1'")

    def test_engineering_fractional(self):
        self.assertEqual(U.format_length(15.5, 3, 4), "1'-3.5000\"")
        self.assertEqual(U.format_length(15.5, 5, 2), '15 1/2')
        self.assertEqual(U.format_length(-15.5, 5, 2), '-15 1/2')

    def test_dim_text(self):
        self.assertEqual(U.parse_dim_text('<>', '12.5'), '12.5')
        self.assertEqual(U.parse_dim_text('', '12.5'), '12.5')
        self.assertEqual(U.parse_dim_text(' ', '12.5'), '')
        self.assertEqual(U.parse_dim_text('~<> mm', '12.5'), '~12.5 mm')
        self.assertEqual(U.parse_dim_text('EQ', '12.5'), 'EQ')


if __name__ == '__main__':
    unittest.main()
