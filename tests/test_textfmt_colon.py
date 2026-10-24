import unittest
from dwgtextfmt import strip_mtext


class ColonCodes(unittest.TestCase):
    def test_codes_after_colon(self):
        self.assertEqual(strip_mtext(r'EMAIL:\Pwww.x.com'), 'EMAIL:\nwww.x.com')
        self.assertEqual(strip_mtext(r'General Notes:\P1.\C7; Do not'), 'General Notes:\n1. Do not')

    def test_paths_kept(self):
        self.assertEqual(strip_mtext(r'C:\Users\x\a.dwg'), r'C:\Users\x\a.dwg')
        self.assertEqual(strip_mtext(r'File W:\Projects\x\y.dwg done'), r'File W:\Projects\x\y.dwg done')
