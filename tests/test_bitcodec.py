"""Round-trip tests for the current DWG bit reader and writer.

Findings
--------
No apparent bugs were found in the primitive operations tested here.
Integer readers return unsigned values: BS(-1) intentionally round-trips
as 65535 because the writer stores the low 16 bits. No values are skipped.
"""

import random
import struct
import unittest

from dwgbits import Bits
from dwgbitw import BitWriter


VALUES = {
    "B": (0, 1, 1, 0),
    "BB": (0, 1, 2, 3),
    "RC": (0, 1, 127, 128, 255),
    "RS": (0, 1, 255, 256, 32767, 32768, 65535),
    "RL": (0, 1, 255, 256, 65535, 65536, 2**31 - 1, 2**31, 2**32 - 1),
    "RD": (0.0, -0.0, 1.0, -1.0, 1e-9, 3.14159, 1e12),
    "BS": (0, 1, 255, 256, -1, 32767, 65535),
    "BL": (0, 1, 255, 256, 2**31 - 1, 2**32 - 1),
    "BD": (0.0, -0.0, 1.0, -1.0, 1e-9, 3.14159, 1e12),
}


class BitCodecTests(unittest.TestCase):
    def assert_round_trip(self, operations, offset=0):
        writer = BitWriter()
        prefix = [i % 2 for i in range(offset)]
        for value in prefix:
            writer.B(value)
        for op, value in operations:
            getattr(writer, op)(value)

        reader = Bits(writer.tobytes())
        self.assertEqual([reader.B() for _ in prefix], prefix)
        for index, (op, value) in enumerate(operations):
            with self.subTest(index=index, op=op, value=value, offset=offset):
                expected = value & 0xFFFF if op == "BS" else value
                actual = getattr(reader, op)()
                self.assertEqual(actual, expected)
                if op in ("RD", "BD"):
                    # Also distinguish positive and negative zero.
                    self.assertEqual(
                        struct.pack("<d", actual), struct.pack("<d", expected)
                    )
        self.assertEqual(reader.p, len(writer))

    def test_primitive_values(self):
        for op, values in VALUES.items():
            with self.subTest(op=op):
                self.assert_round_trip([(op, value) for value in values])

    def test_mixed_sequences_at_every_bit_offset(self):
        # Interleave types so both raw and compressed encodings cross bytes.
        operations = [
            (op, values[index])
            for index in range(max(map(len, VALUES.values())))
            for op, values in VALUES.items()
            if index < len(values)
        ]
        for offset in range(8):
            with self.subTest(offset=offset):
                self.assert_round_trip(operations, offset)

    def test_handles(self):
        handles = [
            (code, value)
            for code in (0, 2, 3, 4, 5)
            for value in (0, 1, 255, 256, 65535, 70000)
        ]
        for offset in range(8):
            writer = BitWriter()
            for _ in range(offset):
                writer.B(1)
            for code, value in handles:
                writer.H(code, value)
            reader = Bits(writer.tobytes(), pos=offset)
            for handle in handles:
                with self.subTest(offset=offset, handle=handle):
                    self.assertEqual(reader.H(), handle)
            self.assertEqual(reader.p, len(writer))

    def test_length_and_zero_padding(self):
        writer = BitWriter()
        self.assertEqual(len(writer), 0)
        self.assertEqual(writer.tobytes(), b"")
        sequence = [
            ("B", 1, 1),
            ("BB", 3, 2),
            ("RC", 255, 8),
            ("RS", 65535, 16),
            ("RL", 2**32 - 1, 32),
            ("RD", -1.0, 64),
            ("BS", 256, 2),
            ("BL", 255, 10),
            ("BD", 1.0, 2),
        ]
        total = 0
        for op, value, width in sequence:
            getattr(writer, op)(value)
            total += width
            self.assertEqual(len(writer), total)
        self.assertEqual(total, 137)

        # Cover all possible padding lengths, including an aligned stream.
        for extra in range(8):
            with self.subTest(extra=extra):
                bit_length = 137 + extra
                data = writer.tobytes()
                self.assertEqual(len(writer), bit_length)
                self.assertEqual(len(data), (bit_length + 7) // 8)
                padding = (-bit_length) % 8
                reader = Bits(data, pos=bit_length)
                self.assertEqual([reader.B() for _ in range(padding)], [0] * padding)
                self.assertEqual(reader.p, len(data) * 8)
                self.assertEqual(writer.tobytes(), data)
            writer.B(1)

    def test_reading_past_end(self):
        for op in VALUES:
            with self.subTest(op=op, data="empty"):
                with self.assertRaises(Exception):
                    getattr(Bits(b""), op)()
        for method, args in (("bit", ()), ("bits", (1,)), ("RC", ())):
            reader = Bits(b"\xff")
            self.assertEqual(reader.RC(), 255)
            with self.subTest(method=method):
                with self.assertRaises(Exception):
                    getattr(reader, method)(*args)
        with self.assertRaises(Exception):
            Bits(b"\xff", pos=7).bits(2)

    def test_seeded_random_mixed_sequences(self):
        rng = random.Random(1234)
        widths = {"B": 1, "BB": 2, "RC": 8, "RS": 16, "RL": 32,
                  "BS": 16, "BL": 32}
        names = tuple(VALUES)
        for sequence in range(2000):
            # Include every primitive, then vary the length and order.
            ops = list(names) + rng.choices(names, k=rng.randrange(24))
            rng.shuffle(ops)
            operations = []
            for op in ops:
                if rng.randrange(3) == 0:
                    value = rng.choice(VALUES[op])
                elif op in widths:
                    value = rng.getrandbits(widths[op])
                else:
                    value = rng.uniform(-1e12, 1e12)
                operations.append((op, value))
            with self.subTest(sequence=sequence):
                self.assert_round_trip(operations, offset=sequence % 8)


if __name__ == "__main__":
    unittest.main()
