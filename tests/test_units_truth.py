import os, unittest
import dwgunits as U

HERE = os.path.dirname(os.path.abspath(__file__))


class TruthTests(unittest.TestCase):
    def test_all_rows(self):
        rows = [l.rstrip('\n').split('|') for l in open(os.path.join(HERE, 'data', 'rtos_truth.txt')) if not l.startswith('#') and l.strip()]
        self.assertEqual(len(rows), 700)
        bad = []
        for z, u, d, v, exp in rows:
            got = U.format_length(float(v), int(u), int(d), zin=int(z))
            if got != exp: bad.append((int(z), int(u), int(d), v, exp, got))
        self.assertEqual(bad, [], '%d of %d rows differ, first: %s' % (len(bad), len(rows), bad[:5]))


if __name__ == '__main__':
    unittest.main()
