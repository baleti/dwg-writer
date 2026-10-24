import unittest
from dwgtextfmt import strip_mtext


class StripMtext(unittest.TestCase):
    def test_paragraph_and_nbsp(self):
        self.assertEqual(strip_mtext('a\\Pb\\~c'), 'a\nb c')

    def test_alignment_code(self):
        self.assertEqual(strip_mtext('\\A1;900'), '900')
        self.assertEqual(strip_mtext('\\A1{abc}'), 'abc')

    def test_font_height_colour(self):
        self.assertEqual(strip_mtext('\\fArial|b0|i0;Hello \\H2.5;big \\C1;red'), 'Hello big red')

    def test_toggles(self):
        self.assertEqual(strip_mtext('\\Lunder\\l \\Oover\\o \\Kstrike\\k'), 'under over strike')

    def test_stack(self):
        self.assertEqual(strip_mtext('\\S1/2;'), '1/2')
        self.assertEqual(strip_mtext('\\S1^2;'), '1/2')

    def test_unicode_escape(self):
        self.assertEqual(strip_mtext('45\\U+00B0'), '45\u00b0')

    def test_percent_codes(self):
        self.assertEqual(strip_mtext('%%c20 %%D90 %%p5 %%C1'), '\u220520 \u00b090 \u00b15 \u22051')

    def test_braces_and_backslash(self):
        self.assertEqual(strip_mtext('{a}\\{b\\}\\\\c'), 'a{b}\\c')

    def test_field_kept(self):
        s = '%<\\AcVar Filename \\f "%tc1">%'
        self.assertEqual(strip_mtext(s), s)

    def test_cached_path_kept(self):
        self.assertEqual(strip_mtext('W:\\Projects\\x\\y.dwg'), 'W:\\Projects\\x\\y.dwg')

    def test_dwg2text_reexports(self):
        import dwg2text, dwgtextfmt
        self.assertIs(dwg2text.strip_mtext, dwgtextfmt.strip_mtext)


if __name__ == '__main__':
    unittest.main()
