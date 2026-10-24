import glob, os, unittest, dwgdoc

CORPUS = os.path.expanduser('~/dwg-research/corpus')


class Ac1021Read(unittest.TestCase):
    def test_open_read_only(self):
        fs = sorted(glob.glob(os.path.join(CORPUS, 'AC1021*.dwg')))[:2]
        if not fs: self.skipTest('no local corpus')
        for f in fs:
            d = dwgdoc.Doc(open(f, 'rb').read())
            self.assertEqual(d.ver, 'AC1021')
            self.assertGreater(len(d.entities('*Model_Space')), 0)
            with self.assertRaises(NotImplementedError): d.save()


if __name__ == '__main__': unittest.main()
