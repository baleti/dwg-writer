"""Unit tests for lz2007b (R2007 LZ) and dwgacis (SAT parser, planar face loops) on synthetic data. Run: python3 -m unittest tests.test_acis_lz"""
import sys, os, unittest
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import lz2007b, dwgacis, dwgbits, dwgbitw


class LZ(unittest.TestCase):
    def test_literal_run(self):
        data = bytes(range(1, 9))
        out, st = lz2007b.decompress(b'\x00' + data, 8)
        self.assertEqual(st, 'done'); self.assertEqual(out, data)

    def test_literal_run_then_match(self):
        data = bytes(range(1, 9))
        # after a literal run the next opcode is read in the "top" state: hi nibble 3 = match of length 3, offset (op & 15) + ((b1 & 0xF8) << 1) + 1, b1 & 7 literals
        stream = b'\x00' + data + bytes([0x32, 0x00])   # offset 2+1 = 3, length 3, no literals
        out, st = lz2007b.decompress(stream, 11)
        self.assertEqual(out, data + data[-3:])

    def test_overlapping_match(self):
        data = bytes([9, 8, 7, 6, 5, 4, 3, 2])
        stream = b'\x00' + data + bytes([0x40, 0x00])   # length 4, offset 1: repeats the last byte
        out, st = lz2007b.decompress(stream, 12)
        self.assertEqual(out, data + bytes([2]) * 4)


SAT = """400 0 1 0
7 Unknown 13 ACIS 4.0.2 NT 24 Sun Mar 02 12:47:39 1997
-1 9.9999999999999995e-007 1e-010
body $-1 $1 $-1 $-1 #
lump $-1 $-1 $2 $0 #
shell $-1 $-1 $-1 $3 $-1 $1 #
face $-1 $-1 $4 $2 $-1 $5 forward single #
loop $-1 $-1 $6 $3 #
plane-surface $-1 0 0 0 0 0 1 1 0 0 forward_v I I I I #
coedge $-1 $7 $9 $-1 $14 forward $4 $-1 #
coedge $-1 $8 $6 $-1 $15 forward $4 $-1 #
coedge $-1 $9 $7 $-1 $16 forward $4 $-1 #
coedge $-1 $6 $8 $-1 $17 forward $4 $-1 #
point $-1 0 0 0 #
point $-1 2 0 0 #
point $-1 2 2 0 #
point $-1 0 2 0 #
edge $-1 $18 $19 $6 $22 forward #
edge $-1 $19 $20 $7 $23 forward #
edge $-1 $20 $21 $8 $24 forward #
edge $-1 $21 $18 $9 $25 forward #
vertex $-1 $14 $10 #
vertex $-1 $15 $11 #
vertex $-1 $16 $12 #
vertex $-1 $17 $13 #
straight-curve $-1 0 0 0 1 0 0 I I #
straight-curve $-1 2 0 0 0 1 0 I I #
straight-curve $-1 2 2 0 -1 0 0 I I #
straight-curve $-1 0 2 0 0 -1 0 I I #
End-of-ACIS-data
"""


class Acis(unittest.TestCase):
    def test_parse_and_area(self):
        hdr, recs = dwgacis.parse_sat(SAT)
        self.assertEqual(hdr['version'], 400)
        names = [n for n, _ in recs]
        self.assertEqual(names.count('edge'), 4); self.assertEqual(names.count('point'), 4)
        w = dwgacis.wire(recs)
        self.assertEqual(len(w), 4)

    def test_face_loop_area(self):
        hdr, recs = dwgacis.parse_sat(SAT)
        fs = dwgacis.faces(recs)
        self.assertEqual(len(fs), 1)
        self.assertAlmostEqual(abs(dwgacis.area(fs[0]['loops'][0])), 4.0)

    def test_area_helper(self):
        sq = [(0, 0, 0), (4, 0, 0), (4, 3, 0), (0, 3, 0)]
        self.assertAlmostEqual(dwgacis.area(sq), 12.0)
        far = [(x + 5e10, y + 2e10, 0) for x, y, _ in sq]
        self.assertAlmostEqual(dwgacis.area(far), 12.0, places=3)   # shifted to the first point: no loss of digits


class Bits(unittest.TestCase):
    def test_roundtrip(self):
        w = dwgbitw.BitWriter()
        w.BS(0); w.BS(7); w.BS(300); w.BL(5); w.BL(70000); w.BD(0.0); w.BD(1.0); w.BD(3.25); w.H(5, 0x1234); w.B(1)
        r = dwgbits.Bits(w.tobytes() + b'\0\0')
        self.assertEqual([r.BS(), r.BS(), r.BS(), r.BL(), r.BL()], [0, 7, 300, 5, 70000])
        self.assertEqual([r.BD(), r.BD(), r.BD()], [0.0, 1.0, 3.25])
        self.assertEqual(r.H(), (5, 0x1234)); self.assertEqual(r.B(), 1)


if __name__ == '__main__':
    unittest.main()
