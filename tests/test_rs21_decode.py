import random, unittest
import dwgrs21 as R


class Rs21Decode(unittest.TestCase):
    def test_clean_roundtrip(self):
        rng = random.Random(1)
        data = bytes(rng.randrange(256) for _ in range(251 * 5))
        raw = R.encode_page(data)
        out, n = R.decode_page(raw, 5)
        self.assertEqual(out, data); self.assertEqual(n, 0)

    def test_corrects_up_to_two_data_errors(self):
        rng = random.Random(2)
        data = bytes(rng.randrange(256) for _ in range(251 * 4))
        raw = bytearray(R.encode_page(data))
        # two errors in codeword 1 (column 1 of the interleave)
        for pos in (7, 200):
            raw[pos * 4 + 1] ^= 0x5a
        out, n = R.decode_page(bytes(raw), 4)
        self.assertEqual(out, data); self.assertEqual(n, 2)

    def test_error_in_parity_bytes(self):
        data = bytes(range(251))
        raw = bytearray(R.encode_page(data)); raw[254] ^= 1
        out, n = R.decode_page(bytes(raw), 1)
        self.assertEqual(out, data); self.assertEqual(n, 1)

    def test_too_many_errors(self):
        rng = random.Random(3)
        data = bytes(rng.randrange(256) for _ in range(251))
        raw = bytearray(R.encode_page(data))
        r = random.Random(1)      # 6 random byte errors: beyond t=2; detected for this pattern (some 6-error patterns are within 2 bytes of another codeword and would be miscorrected)
        for pos in r.sample(range(255), 6):
            raw[pos] ^= r.randrange(1, 256)
        with self.assertRaises(ValueError):
            R.decode_page(bytes(raw), 1)

    def test_system_corrects_eight(self):
        rng = random.Random(4)
        data = bytes(rng.randrange(256) for _ in range(239 * 3))
        raw = bytearray(R.encode_system(data, 3))
        for pos in (1, 20, 33, 90, 120, 180, 230, 254):
            raw[pos * 3 + 2] ^= (pos | 1)
        out, n = R.decode_system(bytes(raw), 3)
        self.assertEqual(out, data); self.assertEqual(n, 8)

    def test_syndromes_zero_for_codeword(self):
        cw = bytes(range(251)); cw = cw + R.DATA.parity(cw)
        self.assertEqual(R.DATA.syndromes(cw), [0, 0, 0, 0])


if __name__ == '__main__':
    unittest.main()
