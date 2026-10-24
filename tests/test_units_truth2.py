"""3840 further AutoCAD 2026 rtos results (zin 0..13 subset, lunit 1..5, dec 0/1/3/6, 16 values) the formatter was NOT fitted to."""
import os, unittest
import dwgunits as U

HERE = os.path.dirname(os.path.abspath(__file__))


class Truth2Tests(unittest.TestCase):
    def test_all_rows(self):
        rows = [l.split('|') for l in open(os.path.join(HERE, 'data', 'rtos_truth2.txt')) if l.startswith('R|')]
        self.assertEqual(len(rows), 3840)
        bad = [(r[1:5], r[5], U.format_length(float(r[4]), int(r[2]), int(r[3]), zin=int(r[1]))) for r in rows
               if U.format_length(float(r[4]), int(r[2]), int(r[3]), zin=int(r[1])) != r[5]]
        self.assertEqual(bad, [], bad[:5])


if __name__ == '__main__':
    unittest.main()
