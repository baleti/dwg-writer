"""Native fast path (dwgfast) against the Python reference. Skipped when the extension is not built."""
import os, random, unittest
try:
    import dwgfast
except ImportError:
    dwgfast = None
import dwgfmt, lz2007b
from dwgwrite import lz77_compress, lz77_literal


@unittest.skipIf(dwgfast is None, 'dwgfast not built')
class FastTests(unittest.TestCase):
    def test_lz77_roundtrip_equal(self):
        rnd = random.Random(7)
        for n in (8, 40, 300, 5000, 70000):
            data = bytes(rnd.choice(b'abcab\0\0\x01') for _ in range(n))
            for enc in (lz77_compress, lz77_literal):
                z = enc(data)
                a = dwgfmt._lz77_decompress_py(z, len(data))
                b, i = dwgfast.lz77_decompress(z, len(data))
                self.assertEqual(a, b)
                self.assertEqual(b, data)
                self.assertEqual(i, dwgfmt._lz77_decompress_py.last_i)

    def test_lz77_errors_match(self):
        for bad in (b'\x00', b'\x01\x02', bytes([0x40, 0x01, 0x00]), b'\x13' + bytes(30)):
            ra = rb = None
            try: dwgfmt._lz77_decompress_py(bad, 100)
            except Exception as ex: ra = type(ex).__name__
            try: dwgfast.lz77_decompress(bad, 100)
            except Exception as ex: rb = type(ex).__name__
            self.assertEqual(ra, rb, bad)

    def test_lz2007_random_streams_equal(self):
        rnd = random.Random(11)
        for _ in range(300):
            n = rnd.randrange(1, 120)
            data = bytes(rnd.randrange(256) for _ in range(n))
            a = lz2007b.decompress_py(data, 400)
            b = dwgfast.lz2007_decompress(data, 400)
            self.assertEqual(a[0], b[0]); self.assertEqual(a[1], b[1])

    def test_entities_equal_on_corpus_file(self):
        p = os.path.join(os.path.dirname(__file__), '..', 'corpus', 'AC1024_02_c9e40a32.dwg')
        if not os.path.exists(p): self.skipTest('corpus file missing')
        import dwgload, dwgent, dwgmodel
        d = dwgload.load(open(p, 'rb').read())
        n = 0
        for o in d['objects'].values():
            dec = dwgmodel.ENT_DECODERS.get(o.type)
            py = dwgent.PY_DECODERS.get(getattr(dec, '__name__', ''))
            if py is None: continue
            try: a = repr(py(o)); ea = dwgent.LAST_READER.p
            except Exception as ex: a = type(ex).__name__; ea = None
            try: b = repr(dec(o)); eb = dwgent.LAST_READER.p
            except Exception as ex: b = type(ex).__name__; eb = None
            self.assertEqual(a, b); self.assertEqual(ea, eb); n += 1
        self.assertGreater(n, 0)


if __name__ == '__main__':
    unittest.main()
