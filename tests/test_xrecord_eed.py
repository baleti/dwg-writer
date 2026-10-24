"""Source-only tests for XRECORD streams and EED payloads.

Findings
--------
(fixed in dwgdoc) wide XRECORD/EED strings counted Python characters, not UTF-16 code units.
Byte-kind values are intentionally encoded as truth values (0 or 1), so
round trips use 0 and 1; a separate layout check covers normalization.

RESULT notes: dwgdoc imports without fake modules; no DWG files are used.
"""

import random
import unittest
from types import SimpleNamespace

import dwgdoc


VERSIONS = ('AC1015', 'AC1018', 'AC1024', 'AC1027', 'AC1032')
# Independent transcription of the documented group-code ranges.
RANGES = {
    'str': ((0, 9), (100, 102), (300, 309), (410, 419), (430, 439), (470, 479)),
    'pt': ((10, 39), (210, 239)),
    'dbl': ((40, 59), (140, 149), (460, 469)),
    'short': ((60, 79), (170, 179), (270, 289), (370, 389), (400, 409)),
    'long': ((90, 99), (420, 429), (440, 449)),
    'byte': ((290, 299),),
    'bin': ((310, 319),),
    'handle': ((320, 329),),
}
ONE = bytes.fromhex('000000000000f03f')
NEG_TWO = bytes.fromhex('00000000000000c0')
HALF = bytes.fromhex('000000000000e03f')
POINT = ONE + NEG_TWO + HALF


def samples(ver):
    strings = ['ASCII', '', 'é']
    if ver in dwgdoc.C.WIDE:
        strings.append('中文')
    return ([(1, value) for value in strings] + [
        (10, (1.0, -2.0, 0.5)), (40, 0.5), (40, -2.0),
        (70, -32768), (70, 32767), (90, -(2**31)), (90, 2**31 - 1),
        (290, 0), (290, 1), (310, b''), (310, bytes(range(255))),
        (320, 0), (320, 2**63),
    ])


class XRecordTests(unittest.TestCase):
    def test_kind_boundaries_and_neighbors(self):
        expected = {code: kind for kind, ranges in RANGES.items()
                    for first, last in ranges for code in range(first, last + 1)}
        for kind, ranges in RANGES.items():
            for first, last in ranges:
                for code in (first - 1, first, last, last + 1):
                    with self.subTest(kind=kind, bounds=(first, last), code=code):
                        if code in expected:
                            self.assertEqual(dwgdoc._xr_kind(code), expected[code])
                        else:
                            with self.assertRaises(ValueError):
                                dwgdoc._xr_kind(code)

    def test_round_trip_each_kind(self):
        for ver in VERSIONS:
            stub = SimpleNamespace(ver=ver)
            for item in samples(ver):
                with self.subTest(ver=ver, code=item[0], value=item[1]):
                    self.assertEqual(dwgdoc._xr_unpack(stub, dwgdoc._xr_pack(stub, [item])), [item])
            self.assertEqual(dwgdoc._xr_pack(stub, []), b'')
            self.assertEqual(dwgdoc._xr_unpack(stub, b''), [])

    def test_300_random_mixed_streams(self):
        rng = random.Random(11)
        for index in range(300):
            ver = VERSIONS[index % len(VERSIONS)]
            stub = SimpleNamespace(ver=ver)
            items = samples(ver)
            items += rng.choices(items, k=rng.randrange(40))
            # Exercise alternate group codes as well as arbitrary ordering.
            items = [(rng.choice([c for lo, hi in RANGES[dwgdoc._xr_kind(code)]
                                  for c in range(lo, hi + 1)]), value)
                     for code, value in items]
            rng.shuffle(items)
            with self.subTest(stream=index, ver=ver):
                self.assertEqual(dwgdoc._xr_unpack(stub, dwgdoc._xr_pack(stub, items)), items)

    def test_exact_layouts(self):
        numeric = [(10, (1.0, -2.0, 0.5)), (40, 0.5), (70, -32768),
                   (90, -(2**31)), (290, 1), (310, b'\x00\xff'), (320, 2**63)]
        expected = (b'\x0a\x00' + POINT + b'\x28\x00' + HALF +
                    bytes.fromhex('46000080 5a0000000080 220101 36010200ff 40010000000000000080'))
        for ver in VERSIONS:
            stub = SimpleNamespace(ver=ver)
            with self.subTest(ver=ver):
                self.assertEqual(dwgdoc._xr_pack(stub, numeric), expected)
                self.assertEqual(dwgdoc._xr_unpack(stub, expected), numeric)
                if ver in dwgdoc.C.WIDE:
                    strings = [(1, 'Aé中'), (300, '')]
                    encoded = bytes.fromhex('010003004100e9002d4e 2c010000')
                else:
                    strings = [(1, 'Aé'), (300, '')]
                    encoded = bytes.fromhex('010002001e41e9 2c0100001e')
                self.assertEqual(dwgdoc._xr_pack(stub, strings), encoded)
                self.assertEqual(dwgdoc._xr_unpack(stub, encoded), strings)
                self.assertEqual(dwgdoc._xr_pack(stub, [(290, 255)]), b'\x22\x01\x01')

    def test_non_bmp_wide_round_trip(self):
        for ver in VERSIONS:
            if ver in dwgdoc.C.WIDE:
                stub = SimpleNamespace(ver=ver)
                items = [(1, '\U0001f600')]
                self.assertEqual(dwgdoc._xr_unpack(stub, dwgdoc._xr_pack(stub, items)), items)


class EEDTests(unittest.TestCase):
    def test_exact_string_layouts(self):
        for ver in VERSIONS:
            for code in (1000, 1001, 1003):
                cases = [('', b'\x00\x00'), ('Aé中', bytes.fromhex('03004100e9002d4e'))] if ver in dwgdoc.C.WIDE else [
                    ('', b'\x00\x00\x1e'), ('Aé', b'\x02\x00\x1eA\xe9')]
                for value, payload in cases:
                    with self.subTest(ver=ver, code=code, value=value):
                        self.assertEqual(dwgdoc._eed_bytes(SimpleNamespace(ver=ver), [(code, value)]),
                                         bytes([code - 1000]) + payload)

    def test_exact_non_string_layouts(self):
        cases = [
            (1002, '{', b'\x02\x00'), (1002, '}', b'\x02\x01'),
            (1004, b'', b'\x04\x00'),
            (1004, b'\x00\xff', b'\x04\x02\x00\xff'),
            (1004, bytes(range(255)), b'\x04\xff' + bytes(range(255))),
            (1005, 0, b'\x05' + b'\x00' * 8),
            (1005, 2**63, b'\x05\x80' + b'\x00' * 7),
            (1005, 0x0102030405060708, bytes.fromhex('050102030405060708')),
            (1070, -32768, bytes.fromhex('460080')),
            (1070, 32767, bytes.fromhex('46ff7f')),
            (1071, -(2**31), bytes.fromhex('4700000080')),
            (1071, 2**31 - 1, bytes.fromhex('47ffffff7f')),
        ]
        cases += [(code, (1.0, -2.0, 0.5), bytes([code - 1000]) + POINT)
                  for code in range(1010, 1014)]
        cases += [(code, 0.5, bytes([code - 1000]) + HALF)
                  for code in range(1040, 1043)]
        for ver in VERSIONS:
            stub = SimpleNamespace(ver=ver)
            for code, value, expected in cases:
                with self.subTest(ver=ver, code=code, value=value):
                    self.assertEqual(dwgdoc._eed_bytes(stub, [(code, value)]), expected)
            self.assertEqual(dwgdoc._eed_bytes(stub, [(c, v) for c, v, _ in cases]),
                             b''.join(expected for _, _, expected in cases))
            self.assertEqual(dwgdoc._eed_bytes(stub, []), b'')

    def test_unsupported_codes(self):
        for ver in VERSIONS:
            for code in (-1, 999, 1006, 1009, 1014, 1039, 1043, 1069, 1072):
                with self.subTest(ver=ver, code=code):
                    with self.assertRaises(ValueError):
                        dwgdoc._eed_bytes(SimpleNamespace(ver=ver), [(code, 0)])


if __name__ == '__main__':
    unittest.main()
