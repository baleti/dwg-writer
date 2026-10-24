"""AC1021 (R2007) LZ variant, found by experiment (see NOTES.md "AC1021 LZ"): opcode forms, literal copy permutations, a search for the
ambiguous high-nibble-0 opcodes (literal run vs long match). Experimental."""
import sys
sys.setrecursionlimit(100000)

# chunk sizes (source order) of the literal copy for a run of n bytes; the chunks are written to the output in reverse order
CHUNKS = {1: [1], 2: [1, 1], 3: [1, 1, 1], 4: [4], 5: [4, 1], 6: [1, 4, 1], 7: [1, 4, 1, 1], 8: [8], 9: [8, 1], 10: [1, 8, 1], 11: [1, 8, 1, 1], 12: [8, 4],
          13: [8, 4, 1], 14: [1, 8, 4, 1], 15: [1, 8, 4, 1, 1], 16: [8, 8], 17: [8, 1, 8], 18: [1, 8, 8, 1], 19: [8, 8, 1, 1, 1], 20: [8, 8, 4],
          21: [8, 8, 4, 1], 22: [8, 8, 4, 1, 1], 23: [8, 8, 4, 1, 1, 1], 25: [8, 8, 1, 8], 26: [8, 8, 1, 8, 1], 27: [8, 8, 1, 8, 1, 1], 31: [1, 1, 8, 8, 8, 4, 1]}  # 9, 26 and the 2/3 entries: CRC verified on AutoCAD-written AC1021 pages


STRICT_F = True  # True: hi-15 opcodes are always the A form (an invalid offset then ends the parse)
REM = {}  # overrides for the remainder after 32-byte blocks (chunk lists), keyed by remainder length


def lit_copy(raw, over=None):
    n = len(raw)
    if n >= 32:
        out = bytearray(); p = 0
        while n - p >= 32:
            b = raw[p:p + 32]; out += b[24:32] + b[16:24] + b[8:16] + b[0:8]; p += 32
        return bytes(out) + (lit_copy(raw[p:], REM) if p < n else b'')
    ch = (over or {}).get(n) or CHUNKS.get(n)
    if ch is None:  # n >= 24 (remainders after 32-byte blocks): 8-byte chunks, then a 4-byte chunk, then single bytes (confirmed for 29)
        ch = [8] * (n // 8); r = n % 8
        if r >= 4: ch.append(4); r -= 4
        ch += [1] * r
    parts = []; p = 0
    for c in ch: parts.append(raw[p:p + c]); p += c
    return b''.join(reversed(parts))


def parse(D, usz):
    try:
        return _parse(D, usz)
    except IndexError:
        return [], len(D), 'truncated'


def _parse(D, usz):
    """Deterministic parse of an R2007 LZ stream into segments: ('lit', pos, k) | ('copy', ln, off). Returns (segments, consumed, status).
    Grammar (found by experiment): opcode high nibble 0 after a literal-free state = literal run of (op&15)+8 bytes (+next byte if nibble 15);
    after a match that carried literals it is a long match; 1, 2, 3..15 as in NOTES.md; the first byte 0x2? is the preamble [20 00 00 xx]."""
    n = len(D); i = 0; segs = []; outlen = 0; litlen = 0
    if D[0] >> 4 == 2:
        litlen = D[3] & 7; i = 4
        segs.append(('lit', i, litlen)); outlen += litlen; i += litlen; litlen = 0
    while outlen < usz and i < n:
        op = D[i]; i += 1; hi = op >> 4
        if hi == 0 and litlen == 0:
            k = (op & 15) + 8
            if op & 15 == 15: k += D[i]; i += 1
            segs.append(('lit', i, k)); outlen += k; i += k; litlen = -1; continue  # a literal run is never followed by another one: the next hi-0 opcode is a match
        if hi == 0:
            ln = (op & 15) + 0x13; off = D[i]; b2 = D[i + 1]; i += 2
            ln += (b2 >> 3) & 0x10; off += ((b2 & 0x78) << 5) + 1; litlen = b2 & 7
        elif hi == 1:
            ln = (op & 15) + 3; off = D[i]; b2 = D[i + 1]; i += 2; off += ((b2 & 0xF8) << 5) + 1; litlen = b2 & 7
        elif hi == 15:  # EXP (AutoCAD-written specimens): the A form when its offset is valid, else the hi-2 form
            ln = (op & 15) + 0x13; off = D[i]; b2 = D[i + 1]; ln += (b2 >> 3) & 0x10; off += ((b2 & 0x78) << 5) + 1
            if off > outlen and not STRICT_F:
                off = D[i] + 1; ln = (op & 7) + (b2 >> 3)
            i += 2; litlen = b2 & 7
        elif hi == 2:
            off = D[i] + 1; b2 = D[i + 1]; i += 2; ln = (op & 7) + (b2 >> 3); litlen = b2 & 7
        else:
            ln = hi; off = op & 15; b2 = D[i]; i += 1; off += ((b2 & 0xF8) << 1) + 1; litlen = b2 & 7
        if off > outlen: return segs, i, 'bad offset'
        segs.append(('copy', ln, off)); outlen += ln
        if litlen:
            segs.append(('lit', i, litlen)); outlen += litlen; i += litlen
    return segs, i, 'done' if outlen >= usz else 'short'


def build(D, segs):
    out = bytearray()
    for s in segs:
        if s[0] == 'lit': out += lit_copy(D[s[1]:s[1] + s[2]])
        else:
            for _ in range(s[1]): out.append(out[-s[2]])
    return out


def decompress(D, usz):
    segs, i, st = parse(D, usz)
    return bytes(build(D, segs)[:usz]), st
