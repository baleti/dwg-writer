"""AC1021 (R2007) LZ decoder, grammar re-derived from the structure the CRC chain showed (own analysis, checked against object CRCs).
Opcode forms: hi 0 = A long match at the top of a block, literal run inside a match chain; hi 1 / 3..15 short forms; hi 2 = 2-byte-offset form.
Inside a chain of matches without literals a 0xF? byte is a marker that is dropped (the next byte is the opcode)."""
import lz2007


SKIPF = True


def decompress_py(D, usz, trace=None):
    n = len(D); i = 0; out = bytearray(); length = 0; start = True
    st = 'done'
    try:
        if D[0] >> 4 == 2:
            length = D[3] & 7; i = 4
        while i < n and len(out) < usz:
            if length:
                start = False
                out += lz2007.lit_copy(D[i:i + length]); i += length
                if trace is not None: trace.append(('lit', len(out) - length, length, i))
                length = 0
                if i >= n: break
            op = D[i]; i += 1
            first = not start; start = False
            while True:
                hi = op >> 4
                if hi == 0 and not first:  # literal run
                    length = (op & 15) + 8
                    if op & 15 == 15:
                        nn = D[i]; i += 1; length += nn
                        if nn == 0xFF:
                            while True:
                                w = D[i] | D[i + 1] << 8; i += 2; length += w
                                if w != 0xFFFF: break
                    break
                if hi == 0:
                    ln = (op & 15) + 0x13; off = D[i]; b2 = D[i + 1]; i += 2
                    ln += (b2 >> 3) & 0x10; off += ((b2 & 0x78) << 5) + 1; op = b2
                elif hi == 1:
                    ln = (op & 15) + 3; off = D[i]; b2 = D[i + 1]; i += 2; off += ((b2 & 0xF8) << 5) + 1; op = b2
                elif hi == 2:
                    off = D[i] | D[i + 1] << 8; i += 2; ln = op & 7
                    if op & 8 == 0:
                        op = D[i]; i += 1; ln += op & 0xF8
                    else:
                        off += 1; ln += D[i] << 3; i += 1; op = D[i]; i += 1; ln += ((op & 0xF8) << 8) + 0x100
                else:
                    ln = hi; off = op & 15; op = D[i]; i += 1; off += ((op & 0xF8) << 1) + 1
                if off > len(out): return bytes(out), 'bad offset %d at out %d stream %d' % (off, len(out), i)
                for _ in range(ln): out.append(out[-off])
                if trace is not None: trace.append(('m', len(out) - ln, ln, off, i))
                length = op & 7
                if len(out) >= usz: break
                if length: break
                if i >= n: break
                op = D[i]; i += 1; first = False
                if SKIPF and op >> 4 == 15: op &= 15; first = True
    except IndexError:
        st = 'truncated'
    return bytes(out), st


try:
    import os
    if os.environ.get('DWG_NO_FAST'): raise ImportError
    from dwgfast import lz2007_decompress as _fast

    def decompress(D, usz, trace=None):
        return decompress_py(D, usz, trace) if trace is not None else _fast(bytes(D), usz)
except ImportError:
    decompress = decompress_py
