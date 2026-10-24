"""Round-trip and R2004 wire-format regression tests.

Findings
--------
No opcode-walker disagreement with dwgfmt was found in the seeded corpus.
Inline literals belong to the short-form opcode's low two bits, or the
first offset byte's low two bits for the medium and far forms (after any
length extension). The decoder consumes 0x11 but leaves its two padding
bytes unread; the walker checks and consumes all three terminator bytes.
lz77_literal has no explicit short-input guard, but its literal-run grammar
requires at least four bytes; smaller inputs are outside these round trips.
"""

import random
import unittest

from dwgfmt import lz77_decompress
from dwgwrite import lz77_compress, lz77_literal


TERMINATOR = b'\x11\x00\x00'


def walk_stream(stream):
    """Parse independently of the codec helpers; return output, matches, end.

    Unlike the production decoder, termination is driven only by the stream,
    not by a caller-provided output length. Bounds and backreferences are
    checked before use, including overlapping matches.
    """
    cursor = 0
    output = bytearray()
    matches = []

    def take(count):
        nonlocal cursor
        end = cursor + count
        if end > len(stream):
            raise ValueError('truncated stream')
        value = stream[cursor:end]
        cursor = end
        return value

    def byte():
        return take(1)[0]

    def extended(base):
        value = byte()
        while value == 0:
            base += 255
            value = byte()
        return base + value

    literal_allowed = True
    while True:
        opcode = byte()
        if opcode == 0x11:
            if take(2) != b'\0\0':
                raise ValueError('bad terminator padding')
            return bytes(output), matches, cursor
        if opcode < 0x10:
            if not literal_allowed:
                raise ValueError('unexpected literal run')
            length = opcode + 3 if opcode else extended(18)
            output.extend(take(length))
            literal_allowed = False
            continue
        if opcode >= 0x40:
            length = (opcode >> 4) - 1
            distance = 1 + ((opcode & 12) >> 2) + 4 * byte()
            inline = opcode & 3
        else:
            if opcode >= 0x20:
                length = (opcode & 31) + 2 if opcode & 31 else extended(33)
                base = 1
            else:
                length = (opcode & 7) + 2 if opcode & 7 else extended(9)
                base = 16384 + (16384 if opcode & 8 else 0)
            low, high = take(2)
            distance = base + (low >> 2) + 64 * high
            inline = low & 3
        if not 1 <= distance <= len(output):
            raise ValueError('invalid backreference')
        matches.append((distance, length))
        # Repeat the referenced suffix to handle overlapping matches without
        # duplicating the decoder's byte-at-a-time copying loop.
        suffix = bytes(output[-distance:])
        output.extend((suffix * ((length + distance - 1) // distance))[:length])
        output.extend(take(inline))
        literal_allowed = inline == 0


def random_bytes(rng, size):
    return bytes(rng.getrandbits(8) for _ in range(size))


def round_trip_cases():
    for size in range(4, 65):
        yield 'edge-%d' % size, bytes(range(size))
    yield 'zeros-70000', bytes(70000)
    for period in range(1, 41):
        pattern = bytes(range(period))
        yield 'period-%d' % period, (pattern * (2048 // period + 2))[:2048 + period]
    rng = random.Random(5)
    for size in (4, 18, 19, 64, 255, 258, 273, 274, 1024, 16384, 32768, 65536, 70000):
        yield 'random-%d' % size, random_bytes(rng, size)
    yield 'text', (b'Layer 12: Line from (10, 20) to (30, 40).\n' * 900)
    block = random_bytes(rng, 1024)
    yield 'long-near-match', block * 8
    # The duplicate block starts over 16 KiB away, outside the match window.
    yield 'long-distant-match', block + random_bytes(rng, 17000) + block
    for tail in range(4):
        yield 'inline-tail-%d' % tail, b'abcd' * 100 + b'XYZ'[:tail]


class LZTests(unittest.TestCase):
    def test_round_trips_terminators_and_determinism(self):
        for name, data in round_trip_cases():
            for encoder in (lz77_compress, lz77_literal):
                with self.subTest(case=name, encoder=encoder.__name__):
                    stream = encoder(data)
                    self.assertEqual(lz77_decompress(stream, len(data)), data)
                    self.assertTrue(stream.endswith(TERMINATOR))
                    self.assertEqual(encoder(data), stream)

    def test_short_compressor_inputs_rejected(self):
        for size in range(4):
            with self.subTest(size=size):
                with self.assertRaises(ValueError):
                    lz77_compress(bytes(size))

    def test_compression_sizes(self):
        self.assertLess(len(lz77_compress(bytes(70000))), 1000)
        rng = random.Random(5)
        # Tiny inputs necessarily exceed 2% overhead from framing alone.
        for size in (1024, 4096, 16384, 32768, 65536, 70000):
            data = random_bytes(rng, size)
            for encoder in (lz77_compress, lz77_literal):
                with self.subTest(size=size, encoder=encoder.__name__):
                    self.assertLessEqual(100 * len(encoder(data)), 102 * size)

    def test_structured_streams(self):
        rng = random.Random(5)
        seen_matches = []
        for case in range(300):
            data = bytearray(random_bytes(rng, rng.randint(4, 40)))
            for _ in range(rng.randint(5, 15)):
                kind = rng.randrange(4)
                if kind == 0:
                    data.extend(random_bytes(rng, rng.randint(1, 300)))
                elif kind == 1:
                    pattern = random_bytes(rng, rng.randint(1, 40))
                    data.extend(pattern * rng.randint(2, 80))
                elif kind == 2:
                    start = rng.randrange(len(data))
                    data.extend(bytes(data[start:start + rng.randint(4, 700)]))
                else:
                    data.extend(bytes([rng.randrange(256)]) * rng.randint(4, 1200))
            with self.subTest(case=case):
                stream = lz77_compress(bytes(data))
                decoded = lz77_decompress(stream, len(data))
                self.assertEqual(decoded, bytes(data))
                walked, matches, consumed = walk_stream(stream)
                self.assertEqual(walked, decoded)
                self.assertEqual(consumed, len(stream))
                self.assertEqual(lz77_decompress.last_i, consumed - 2)
                self.assertTrue(stream.endswith(TERMINATOR))
                self.assertTrue(all(offset <= 16384 for offset, _ in matches))
                seen_matches.extend(matches)
        self.assertTrue(seen_matches, 'offset assertions must not be vacuous')
        self.assertGreater(max(length for _, length in seen_matches), 258)

    def test_walker_match_forms(self):
        # Hand-authored streams exercise branches the default compressor
        # intentionally avoids, and every possible inline literal count.
        for inline in range(4):
            for opcode in (bytes([0x40 | inline, 0]),
                           bytes([0x22, inline, 0]),
                           bytes([0x20, 1, inline, 0])):
                stream = b'\x01abcd' + opcode + b'XYZ'[:inline] + TERMINATOR
                with self.subTest(opcode=opcode, inline=inline):
                    walked, _, consumed = walk_stream(stream)
                    self.assertEqual(lz77_decompress(stream, len(walked)), walked)
                    self.assertEqual(consumed, len(stream))
        for opcode, offset, length in ((b'\x12\0\0', 16384, 4),
                                       (b'\x10\x01\0\0', 16384, 10),
                                       (b'\x1a\0\0', 32768, 4)):
            prefix = bytes(range(256)) * (offset // 256)
            stream = lz77_literal(prefix)[:-3] + opcode + TERMINATOR
            expected = prefix + prefix[:length]
            walked, matches, consumed = walk_stream(stream)
            self.assertEqual(walked, expected)
            self.assertEqual(lz77_decompress(stream, len(expected)), expected)
            self.assertEqual(matches, [(offset, length)])
            self.assertEqual(consumed, len(stream))


if __name__ == '__main__':
    unittest.main()
