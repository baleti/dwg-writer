"""Experimental R2007 (AC1021) LZ decompressor. Structure found by experiment on the 0x110-byte system header of the corpus files (NOTES.md):
 - opcode high nibble 0: literal run of (low nibble + 8) bytes (low nibble 15: + extension bytes)
 - high nibble >= 3: match length = high nibble, offset = low nibble + ((next byte & 0xFC) << 1) + 1, next byte & 7 = literal bytes that follow
 - high nibble 2 (first opcode 0x20): 2-byte offset, length 0, literal count in following byte & 7 (forms 1 and 2 beyond that not yet understood)
 - literal runs are copied byte-reversed."""


RULE = 2


def copy_lit(raw):
    if RULE == 1:
        return raw[::-1]
    # rule 2: split from the front into 8-byte, 4-byte then single-byte chunks, emit chunks in reverse order, chunks kept as is
    n = len(raw); chunks = []; p = 0
    while n - p >= 8: chunks.append(raw[p:p + 8]); p += 8
    if n - p >= 4: chunks.append(raw[p:p + 4]); p += 4
    while p < n: chunks.append(raw[p:p + 1]); p += 1
    return b''.join(chunks[::-1])


class Unsupported(Exception):
    pass


def decompress(src, out_size, verbose=False):
    out = bytearray()
    i = 0
    n = len(src)

    def rd():
        nonlocal i
        b = src[i]; i += 1
        return b

    def lits(k):
        nonlocal i
        out.extend(copy_lit(src[i:i + k])); i += k

    if src[0] >> 4 == 2:  # stream header: 0x2X, two skipped bytes, literal count in low 3 bits of the next byte
        i = 3
        lit0 = rd() & 7
        if lit0: lits(lit0)
    while i < n and len(out) < out_size:
        op = rd()
        hi = op >> 4
        if hi == 0:
            k = (op & 0xF) + 8
            if op & 0xF == 0xF:
                x = rd(); k += x
                if x == 0xFF:
                    while True:
                        y = rd() | (rd() << 8); k += y
                        if y != 0xFFFF: break
            if verbose: print('lit', k)
            lits(k)
            continue
        if hi == 1:
            ln = (op & 15) + 3; b1 = rd(); b2 = rd()
            off = b1 + ((b2 & 0xF8) << 5) + 1; lit = b2 & 7
        elif hi == 2:
            ln = op & 15; b1 = rd(); b2 = rd()
            off = b1 + ((b2 & 0xF8) << 1) + 1; lit = b2 & 7  # EXP: length = low nibble (fits exact output size); offset formula guessed like the default form
        elif hi >= 3:
            ln = hi; off = op & 15; nx = rd(); off += ((nx & 0xF8) << 1) + 1; lit = nx & 7
        else:
            raise Unsupported('form %#x at %d' % (op, i - 1))
        if verbose: print('match', ln, off, 'lit', lit)
        if ln:
            if off > len(out): raise ValueError('bad offset %d > %d at %d' % (off, len(out), i))
            for _ in range(ln): out.append(out[-off])
        if lit: lits(lit)
    return bytes(out)


def rs_stream(buf, off, size, csz):
    """First csz data bytes of an R2007 RS-encoded page of on-disk `size`: k = size // 256 codewords of 255 bytes, byte-interleaved,
    239 data bytes + 16 parity each (parity not checked). [EXP]"""
    k = size // 256
    raw = buf[off:off + 255 * k]
    d = bytearray()
    for j in range(k):
        d += raw[j::k][:239]
    return bytes(d[:csz])
