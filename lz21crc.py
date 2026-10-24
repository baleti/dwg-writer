"""AC1021 data page decoder: R2007 LZ with the object CRC16 chain as oracle (own code; grammar found by experiment, see NOTES.md).
solve_page(stream, usz, first_obj=4, skip=0, maxnodes=3000000) -> (plaintext, info)
Grammar: hi-nibble-0 opcode = literal run after a match without literals, otherwise the A long match; hi 1/2/3..14 as in lz2007; hi 15 is the A form or a
general match of length 15 (both tried, the CRC chain decides); a hi-2 match may have length 0 (literal-only op)."""
import struct, sys
import dwgfmt as F
import lz2007

sys.setrecursionlimit(1000000)


def solve_page(b, usz, first_obj=4, skip=0, maxnodes=3000000, alts=()):
    n = len(b)
    out = bytearray(); state = {'q': first_obj, 'skipped': []}; nodes = [0]; best = [0, 0, None, None, 0, []]; plog = []

    def crc_ok():
        while True:
            qq = state['q']
            if len(out) < qq + 2: return True
            sz_ = out[qq] | out[qq + 1] << 8
            hdr = 2
            if sz_ & 0x8000:  # MS form: second word holds the high bits (objects larger than 32 KB)
                if len(out) < qq + 4: return True
                sz_ = (sz_ & 0x7FFF) | ((out[qq + 2] | out[qq + 3] << 8) << 15); hdr = 4
            end = qq + hdr + sz_
            if len(out) < end + 2: return True
            if F.crc16(bytes(out[qq:end]), 0xC0C1) != struct.unpack_from('<H', out, end)[0]:
                if len(state['skipped']) >= skip: return False
                state['skipped'].append(qq)
            state['q'] = end + 2

    def forms(op, i, st):
        hi = op >> 4; b1 = b[i] if i < n else 0; b2 = b[i + 1] if i + 1 < n else 0
        A = (((op & 15) + 19 + ((b2 >> 3) & 0x10)), b1 + ((b2 & 0x78) << 5) + 1, b2 & 7, i + 2)
        r = []
        if hi == 0:
            if st == 0 or 'litany' in alts:
                kk = (op & 15) + 8; j = i
                if op & 15 == 15: kk += b1; j = i + 1
                r.append(('lit', kk, j))
            if st != 0 or 'a_or_lit' in alts: r.append(('m',) + A)
        elif hi == 1:
            hv = [a_ for a_ in alts if isinstance(a_, tuple) and a_[0] == 'hi1']
            if hv and b2 & 0x80:  # candidate formula for hi-1 ops with bit 7 set: ('hi1', mask, shift, add)
                _, mk, sh, ad = hv[0]
                r.append(('m', (op & 15) + 3 + ad, b1 + (((b2 >> 3) & mk) << sh) + 1, b2 & 7, i + 2))
            else:
                r.append(('m', (op & 15) + 3, b1 + ((b2 & 0xF8) << 5) + 1, b2 & 7, i + 2))
            if 'h1A' in alts and b2 & 0x80: r.append(('m', (op & 15) + 19, b1 + ((b2 & 0x78) << 5) + 1, b2 & 7, i + 2))
        elif hi == 2: r.append(('m', (op & 7) + (b2 >> 3), b1 + 1, b2 & 7, i + 2))
        elif hi == 15:
            mk15 = [a_ for a_ in alts if isinstance(a_, tuple) and a_[0] == 'f15rule']
            if mk15:  # candidate rule: A form only when (b2 & mask) <= limit, else the general length-15 match
                _, mask, lim = mk15[0]
                if (b2 & mask) <= lim: r.append(('m',) + A)
                else: r.append(('m', 15, (op & 15) + ((b1 & 0xF8) << 1) + 1, b1 & 7, i + 1))
            else:
                r.append(('m',) + A); r.append(('m', 15, (op & 15) + ((b1 & 0xF8) << 1) + 1, b1 & 7, i + 1))
            if 'm15lit' in alts:
                for L_ in range(0, 8):
                    if L_ != (b1 & 7): r.append(('m', 15, (op & 15) + ((b1 & 0xF8) << 1) + 1, L_, i + 1))
            if 'm15x' in alts: r.append(('m', 15 + b2, (op & 15) + ((b1 & 0xF8) << 1) + 1, b1 & 7, i + 2))
        else: r.append(('m', hi, (op & 15) + ((b1 & 0xF8) << 1) + 1, b1 & 7, i + 1))
        return r

    def dfs(i, st):
        nodes[0] += 1
        if nodes[0] > maxnodes: return False
        if len(out) > best[0]:
            best[0] = len(out); best[1] = i; best[2] = bytes(out); best[3] = list(plog); best[4] = state['q']; best[5] = list(state['skipped'])
        if len(out) >= usz: return True
        if i >= n: return False
        for fi, fm in enumerate(forms(b[i], i + 1, st)):
            sl = len(out); sq = state['q']; sk = len(state['skipped'])
            if fm[0] == 'lit':
                _, kk, j = fm
                if j + kk > n: continue
                out.extend(lz2007.lit_copy(b[j:j + kk]))
                if crc_ok():
                    plog.append((i, fi, 'lit', sl, fm))
                    if dfs(j + kk, 1): return True
                    plog.pop()
            else:
                _, ln, off, ll, j = fm
                if off > len(out) or ln < 0 or j + ll > n: continue
                for _x in range(ln): out.append(out[-off])
                if ll: out.extend(lz2007.lit_copy(b[j:j + ll]))
                if crc_ok():
                    plog.append((i, fi, 'm', sl, fm))
                    if dfs(j + ll, 2 if ll else 0): return True
                    plog.pop()
            del out[sl:]; state['q'] = sq; del state['skipped'][sk:]
        return False

    ok = dfs(0, 0)
    info = dict(path=best[3], ok=ok, nodes=nodes[0], best_out=best[0], best_stream=best[1], skipped=best[5], verified_to=best[4])
    return (bytes(out) if ok else best[2] or b''), info
