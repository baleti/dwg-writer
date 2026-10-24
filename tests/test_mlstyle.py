import glob, os, unittest, dwgmodel

CORPUS = os.path.expanduser('~/dwg-research/corpus')


class MlStyle(unittest.TestCase):
    def test_standard_style(self):
        fs = [f for v in ('AC1015', 'AC1018', 'AC1024', 'AC1032') for f in sorted(glob.glob(os.path.join(CORPUS, v + '*.dwg')))[:1]]
        if not fs: self.skipTest('no local corpus')
        for f in fs:
            st = dwgmodel.Model(open(f, 'rb').read()).mlstyles()
            s = next((v for k, v in st.items() if k.upper().endswith('STANDARD')), None)
            self.assertIsNotNone(s, f)
            self.assertEqual([(e['offset'], e['color']) for e in s['elements']], [(0.5, 256), (-0.5, 256)], f)


class MLeaderStyle(unittest.TestCase):
    def test_standard(self):
        fs = sorted(glob.glob(os.path.join(CORPUS, 'AC1024*.dwg')))[:3]
        if not fs: self.skipTest('no local corpus')
        for f in fs:
            st = dwgmodel.Model(open(f, 'rb').read()).mleaderstyles()
            self.assertTrue(st, f)
            for d in st.values():
                self.assertGreater(d['text_height'], 0, f)
                self.assertIn(d['leader_type'], (0, 1, 2), f)


class AnnotativeFlag(unittest.TestCase):
    def test_eed_block(self):
        import dwgent
        raw = 'AnnotativeData'.encode('utf-16le')
        wide = b'\x00\x0e\x00' + raw + b'\x02\x00F\x01\x00F\x01\x00\x02\x01'
        self.assertTrue(dwgent.annotative_flag([((5, 94), wide)]))
        off = b'\x00\x0e\x00' + raw + b'\x02\x00F\x01\x00F\x00\x00\x02\x01'
        self.assertFalse(dwgent.annotative_flag([((5, 94), off)]))
        self.assertIsNone(dwgent.annotative_flag([((5, 1), b'\x00\x04\x00abcd')]))
