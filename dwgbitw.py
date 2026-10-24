"""Bit-stream writer: inverse of dwgbits.Bits."""
import struct


class BitWriter:
    def __init__(self):
        self.bits = []  # list of 0/1 (simple, fast enough for object sized data)

    def __len__(self):
        return len(self.bits)

    def put(self, v, n):
        for i in range(n - 1, -1, -1):
            self.bits.append((v >> i) & 1)

    def copy_bits(self, data, start, end):
        for i in range(start, end):
            self.bits.append((data[i >> 3] >> (7 - (i & 7))) & 1)

    def tobytes(self):
        b = self.bits
        out = bytearray((len(b) + 7) // 8)
        for i, v in enumerate(b):
            if v: out[i >> 3] |= 0x80 >> (i & 7)
        return bytes(out)

    # primitive types
    def B(self, v): self.bits.append(1 if v else 0)
    def BB(self, v): self.put(v, 2)
    def RC(self, v): self.put(v & 0xFF, 8)
    def RS(self, v): self.RC(v); self.RC(v >> 8)
    def RL(self, v): self.RS(v); self.RS(v >> 16)
    def RD(self, v):
        for c in struct.pack('<d', v): self.RC(c)

    def BS(self, v):
        if v == 0: self.BB(2)
        elif v == 256: self.BB(3)
        elif 0 < v < 256: self.BB(1); self.RC(v)
        else: self.BB(0); self.RS(v)

    def BL(self, v):
        if v == 0: self.BB(2)
        elif 0 < v < 256: self.BB(1); self.RC(v)
        else: self.BB(0); self.RL(v)

    def BD(self, v):
        if v == 0.0 and str(v)[0] != '-': self.BB(2)
        elif v == 1.0: self.BB(1)
        else: self.BB(0); self.RD(v)

    def DD(self, v, default):
        if v == default: self.BB(0); return
        bd = struct.pack('<d', default); bv = struct.pack('<d', v)
        if bd[4:] == bv[4:]:
            self.BB(1); [self.RC(c) for c in bv[:4]]; return
        if bd[6:] == bv[6:]:
            self.BB(2); [self.RC(c) for c in (bv[4], bv[5], bv[0], bv[1], bv[2], bv[3])]; return
        self.BB(3); self.RD(v)

    def BT(self, v):
        if v == 0.0: self.B(1)
        else: self.B(0); self.BD(v)

    def BE(self, v):
        if tuple(v) == (0.0, 0.0, 1.0): self.B(1)
        else: self.B(0); [self.BD(c) for c in v]

    def BD3(self, v): [self.BD(c) for c in v]
    def RD2(self, v): [self.RD(c) for c in v]

    def H(self, code, v):
        n = 0
        t = v
        while t: n += 1; t >>= 8
        self.put(code, 4); self.put(n, 4)
        for i in range(n - 1, -1, -1): self.RC(v >> (8 * i))

    def TV(self, s, enc='latin1'):
        if s == '':
            self.BS(0); return  # empty strings are stored with length 0 (no terminator)
        raw = s.encode(enc, 'replace') + b'\0'
        self.BS(len(raw))
        for c in raw: self.RC(c)

    def TU(self, s):
        raw = s.encode('utf-16le')
        self.BS(len(raw) // 2)  # character count without terminator (verified on string streams)
        for c in raw: self.RC(c)
