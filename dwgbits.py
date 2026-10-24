"""Bit-stream reader for DWG object data (R13-R2000 coding). Own code; code tables from general knowledge, verified by experiment (see NOTES.md)."""
import struct
_unpack_d = struct.Struct('<d').unpack


class Bits:
    def __init__(self, data, pos=0):
        self.d = data
        self.p = pos  # bit position
        self.n = len(data) * 8

    def bit(self):
        i = self.p
        self.p = i + 1
        return (self.d[i >> 3] >> (7 - (i & 7))) & 1

    def bits(self, n):
        i = self.p; end = i + n
        if n <= 0: return 0
        if end > self.n: raise IndexError('read past the end of the object')
        a = i >> 3; b = (end + 7) >> 3
        v = int.from_bytes(self.d[a:b], 'big')
        self.p = end
        return (v >> (b * 8 - end)) & ((1 << n) - 1)

    def cnt(self, n, unit_bits=1):
        """Validate a count read from the stream before it drives a loop: n elements of at least unit_bits bits must still fit."""
        if n is None or n < 0 or n * unit_bits > len(self.d) * 8 - self.p:
            raise ValueError('implausible count %r' % (n,))
        return n

    def rcs(self, n):
        """n raw bytes."""
        self.cnt(n, 8)
        return bytes(self._raw(n)) if n else b''

    def _raw(self, n):
        """n whole bytes at the current bit position (aligned: a slice; unaligned: one shifted integer)."""
        i = self.p; end = i + 8 * n
        d = self.d
        if end > self.n: raise IndexError('read past the end of the object')
        a = i >> 3
        self.p = end
        if not i & 7: return d[a:a + n]
        b = (end + 7) >> 3
        return ((int.from_bytes(d[a:b], 'big') >> (b * 8 - end)) & ((1 << (8 * n)) - 1)).to_bytes(n, 'big')

    def RC(self):
        i = self.p
        d = self.d
        a = i >> 3
        if i + 8 > self.n: raise IndexError('read past the end of the object')
        self.p = i + 8
        s = i & 7
        if not s: return d[a]
        return ((d[a] << 8 | d[a + 1]) >> (8 - s)) & 0xFF

    def RS(self):
        return int.from_bytes(self._raw(2), 'little')

    def RL(self):
        return int.from_bytes(self._raw(4), 'little')

    def RD(self):
        return _unpack_d(self._raw(8))[0]

    def B(self):
        return self.bit()

    def BB(self):
        i = self.p
        if i + 2 > self.n: raise IndexError('read past the end of the object')
        self.p = i + 2
        d = self.d; a = i >> 3; s = i & 7
        if s < 7: return (d[a] >> (6 - s)) & 3
        return ((d[a] << 8 | d[a + 1]) >> 7) & 3

    def BS(self):
        c = self.BB()
        if c == 0: return self.RS()
        if c == 1: return self.RC()
        if c == 2: return 0
        return 256

    def BL(self):
        c = self.BB()
        if c == 0: return self.RL()
        if c == 1: return self.RC()
        if c == 2: return 0
        return None

    def BD(self):
        c = self.BB()
        if c == 0: return self.RD()
        if c == 1: return 1.0
        if c == 2: return 0.0
        return None

    def H(self):
        """Handle reference: (code, handle value)."""
        code = self.bits(4)
        n = self.bits(4)
        return code, int.from_bytes(self._raw(n), 'big') if n else 0


def _dd(self, default):
    c = self.BB()
    if c == 0: return default
    if c == 3: return self.RD()
    b = struct.pack('<d', default)
    if c == 1:
        nb = bytes(self._raw(4)) + b[4:]
    else:
        x = bytes(self._raw(6))
        nb = x[2:6] + x[0:2] + b[6:]
    return struct.unpack('<d', nb)[0]


def _bt(self):  # bit thickness
    return 0.0 if self.B() else self.BD()


def _be(self):  # bit extrusion
    return (0.0, 0.0, 1.0) if self.B() else (self.BD(), self.BD(), self.BD())


Bits.DD = _dd
Bits.BT = _bt
Bits.BE = _be
Bits.BD3 = lambda self: (self.BD(), self.BD(), self.BD())
Bits.RD2 = lambda self: (self.RD(), self.RD())


def _tv(self):  # R2000 text: BS length + bytes
    n = self.BS()
    return bytes(self._raw(n)).rstrip(b'\0').decode('latin1')


Bits.TV = _tv


def _tu(self):  # R2007+ text: BS length + UTF-16LE
    n = self.BS()
    return bytes(self._raw(2 * n)).decode('utf-16le', 'replace').rstrip('\0')


Bits.TU = _tu


def _bll(self):
    n = self.bits(3)
    return int.from_bytes(self._raw(n), 'little') if n else 0


Bits.BLL = _bll
