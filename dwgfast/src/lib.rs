//! dwgfast: native fast path for the DWG reader (own code, mirrors the Python reference in dwgfmt.py / lz2007b.py / dwgbits.py / dwgent.py).
use pyo3::exceptions::PyValueError;
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyList, PyTuple};

mod bits;
mod ent;
use bits::Rd;

fn bad(msg: String) -> PyErr {
    PyValueError::new_err(msg)
}

/// R2004 LZ77 decompressor (dwgfmt.lz77_decompress).
#[pyfunction]
fn lz77_decompress<'py>(py: Python<'py>, src: &[u8], out_size: usize) -> PyResult<(Bound<'py, PyBytes>, usize)> {
    let mut out: Vec<u8> = Vec::with_capacity(out_size + 64);
    let mut i = 0usize;
    macro_rules! get {
        ($k:expr) => {{
            let k = $k;
            if k >= src.len() {
                return Err(pyo3::exceptions::PyIndexError::new_err("lz77: read past the end of the source"));
            }
            src[k]
        }};
    }
    let rlong = |i: &mut usize| -> PyResult<usize> {
        let mut t = 0usize;
        loop {
            if *i >= src.len() {
                return Err(pyo3::exceptions::PyIndexError::new_err("lz77: read past the end of the source"));
            }
            if src[*i] == 0 {
                t += 0xFF;
                *i += 1;
            } else {
                break;
            }
        }
        t += src[*i] as usize;
        *i += 1;
        Ok(t)
    };
    let lit_run = |op: u8, i: &mut usize, out: &mut Vec<u8>| -> PyResult<()> {
        let n = (op & 0x0F) as usize;
        let n = (if n == 0 { 0x0F + rlong(i)? } else { n }) + 3;
        let end = (*i + n).min(src.len());
        out.extend_from_slice(&src[*i..end]);
        *i += n;
        Ok(())
    };
    let mut op = get!(i);
    i += 1;
    if op & 0xF0 == 0 {
        lit_run(op, &mut i, &mut out)?;
        op = get!(i);
        i += 1;
    }
    while op != 0x11 && out.len() < out_size {
        let (cb, off, ln);
        if op >= 0x40 {
            cb = (((op >> 4) & 0xF) as usize) - 1;
            let b2 = get!(i) as usize;
            i += 1;
            off = ((((op >> 2) & 3) as usize) | (b2 << 2)) + 1;
            ln = (op & 3) as usize;
        } else if op >= 0x21 {
            cb = ((op & 0x1F) as usize) + 2;
            let b1 = get!(i) as usize;
            let b2 = get!(i + 1) as usize;
            i += 2;
            off = ((b1 >> 2) | (b2 << 6)) + 1;
            ln = b1 & 3;
        } else if op == 0x20 {
            cb = rlong(&mut i)? + 0x1F + 2;
            let b1 = get!(i) as usize;
            let b2 = get!(i + 1) as usize;
            i += 2;
            off = ((b1 >> 2) | (b2 << 6)) + 1;
            ln = b1 & 3;
        } else if op >= 0x10 {
            cb = if op & 7 != 0 { ((op & 7) as usize) + 2 } else { rlong(&mut i)? + 9 };
            let b1 = get!(i) as usize;
            let b2 = get!(i + 1) as usize;
            i += 2;
            off = ((b1 >> 2) | (b2 << 6)) + 0x4000 + (((op & 8) as usize) << 11);
            ln = b1 & 3;
        } else {
            return Err(bad(format!("bad opcode {:#x} at {}", op, i - 1)));
        }
        if off > out.len() {
            return Err(bad(format!("lz77 bad offset op={:#x} i={} out={} off={} cb={} ln={}", op, i, out.len(), off, cb, ln)));
        }
        for _ in 0..cb {
            let b = out[out.len() - off];
            out.push(b);
        }
        if ln != 0 {
            let end = (i + ln).min(src.len());
            out.extend_from_slice(&src[i..end]);
            i += ln;
            op = get!(i);
            i += 1;
        } else {
            op = get!(i);
            i += 1;
            if op & 0xF0 == 0 {
                lit_run(op, &mut i, &mut out)?;
                op = get!(i);
                i += 1;
            }
        }
    }
    Ok((PyBytes::new_bound(py, &out), i))
}

/// Chunk sizes (source order) of an R2007 literal run of n bytes (lz2007.CHUNKS); the chunks are written in reverse order.
fn chunks(n: usize) -> Vec<usize> {
    match n {
        1 => vec![1],
        2 => vec![1, 1],
        3 => vec![1, 1, 1],
        4 => vec![4],
        5 => vec![4, 1],
        6 => vec![1, 4, 1],
        7 => vec![1, 4, 1, 1],
        8 => vec![8],
        9 => vec![8, 1],
        10 => vec![1, 8, 1],
        11 => vec![1, 8, 1, 1],
        12 => vec![8, 4],
        13 => vec![8, 4, 1],
        14 => vec![1, 8, 4, 1],
        15 => vec![1, 8, 4, 1, 1],
        16 => vec![8, 8],
        17 => vec![8, 1, 8],
        18 => vec![1, 8, 8, 1],
        19 => vec![8, 8, 1, 1, 1],
        20 => vec![8, 8, 4],
        21 => vec![8, 8, 4, 1],
        22 => vec![8, 8, 4, 1, 1],
        23 => vec![8, 8, 4, 1, 1, 1],
        25 => vec![8, 8, 1, 8],
        26 => vec![8, 8, 1, 8, 1],
        27 => vec![8, 8, 1, 8, 1, 1],
        31 => vec![1, 1, 8, 8, 8, 4, 1],
        _ => {
            let mut ch = vec![8; n / 8];
            let mut r = n % 8;
            if r >= 4 {
                ch.push(4);
                r -= 4;
            }
            for _ in 0..r {
                ch.push(1);
            }
            ch
        }
    }
}

fn lit_copy(raw: &[u8], out: &mut Vec<u8>) {
    let n = raw.len();
    let mut p = 0usize;
    if n >= 32 {
        while n - p >= 32 {
            let b = &raw[p..p + 32];
            out.extend_from_slice(&b[24..32]);
            out.extend_from_slice(&b[16..24]);
            out.extend_from_slice(&b[8..16]);
            out.extend_from_slice(&b[0..8]);
            p += 32;
        }
        if p < n {
            lit_copy(&raw[p..], out);
        }
        return;
    }
    let ch = chunks(n);
    let mut parts: Vec<&[u8]> = Vec::with_capacity(ch.len());
    for c in ch {
        parts.push(&raw[p..(p + c).min(n)]);
        p += c;
    }
    for part in parts.into_iter().rev() {
        out.extend_from_slice(part);
    }
}

/// AC1021 LZ decoder (lz2007b.decompress): returns (bytes, status) with status 'done', 'truncated' or an error text.
#[pyfunction]
fn lz2007_decompress<'py>(py: Python<'py>, d: &[u8], usz: usize) -> PyResult<(Bound<'py, PyBytes>, String)> {
    let n = d.len();
    let mut i = 0usize;
    let mut out: Vec<u8> = Vec::with_capacity(usz + 64);
    let mut length = 0usize;
    let mut start = true;
    let mut st = String::from("done");
    // run the grammar; any out-of-range read ends with 'truncated' like the Python IndexError handler
    let res: Result<(), String> = (|| -> Result<(), String> {
        macro_rules! g {
            ($k:expr) => {{
                let k = $k;
                if k >= n {
                    return Err(String::from("truncated"));
                }
                d[k]
            }};
        }
        if n == 0 {
            return Err(String::from("truncated"));
        }
        if d[0] >> 4 == 2 {
            length = (g!(3) & 7) as usize;
            i = 4;
        }
        while i < n && out.len() < usz {
            if length != 0 {
                start = false;
                let end = (i + length).min(n);
                lit_copy(&d[i..end], &mut out);
                i += length;
                length = 0;
                if i >= n {
                    break;
                }
            }
            let mut op = g!(i);
            i += 1;
            let mut first = !start;
            start = false;
            loop {
                let hi = op >> 4;
                if hi == 0 && !first {
                    length = ((op & 15) as usize) + 8;
                    if op & 15 == 15 {
                        let nn = g!(i) as usize;
                        i += 1;
                        length += nn;
                        if nn == 0xFF {
                            loop {
                                let w = (g!(i) as usize) | ((g!(i + 1) as usize) << 8);
                                i += 2;
                                length += w;
                                if w != 0xFFFF {
                                    break;
                                }
                            }
                        }
                    }
                    break;
                }
                let (mut ln, mut off): (usize, usize);
                if hi == 0 {
                    ln = ((op & 15) as usize) + 0x13;
                    off = g!(i) as usize;
                    let b2 = g!(i + 1);
                    i += 2;
                    ln += ((b2 >> 3) & 0x10) as usize;
                    off += (((b2 & 0x78) as usize) << 5) + 1;
                    op = b2;
                } else if hi == 1 {
                    ln = ((op & 15) as usize) + 3;
                    off = g!(i) as usize;
                    let b2 = g!(i + 1);
                    i += 2;
                    off += (((b2 & 0xF8) as usize) << 5) + 1;
                    op = b2;
                } else if hi == 2 {
                    off = (g!(i) as usize) | ((g!(i + 1) as usize) << 8);
                    i += 2;
                    ln = (op & 7) as usize;
                    if op & 8 == 0 {
                        op = g!(i);
                        i += 1;
                        ln += (op & 0xF8) as usize;
                    } else {
                        off += 1;
                        ln += (g!(i) as usize) << 3;
                        i += 1;
                        op = g!(i);
                        i += 1;
                        ln += (((op & 0xF8) as usize) << 8) + 0x100;
                    }
                } else {
                    ln = hi as usize;
                    off = (op & 15) as usize;
                    op = g!(i);
                    i += 1;
                    off += (((op & 0xF8) as usize) << 1) + 1;
                }
                if off > out.len() {
                    return Err(format!("bad offset {} at out {} stream {}", off, out.len(), i));
                }
                for _ in 0..ln {
                    // Python out[-off]: off == 0 reads out[0] (IndexError on an empty buffer)
                    if out.is_empty() {
                        return Err(String::from("truncated"));
                    }
                    let b = if off == 0 { out[0] } else { out[out.len() - off] };
                    out.push(b);
                }
                length = (op & 7) as usize;
                if out.len() >= usz {
                    break;
                }
                if length != 0 {
                    break;
                }
                if i >= n {
                    break;
                }
                op = g!(i);
                i += 1;
                first = false;
                if op >> 4 == 15 {
                    op &= 15;
                    first = true;
                }
            }
        }
        Ok(())
    })();
    if let Err(e) = res {
        st = e;
    }
    Ok((PyBytes::new_bound(py, &out), st))
}

/// decode_entity(type, raw, data_bit, handle_bit, ver) -> (dict, end_bit) or None (no native decoder for this type).
#[pyfunction]
fn decode_entity<'py>(py: Python<'py>, otype: u32, raw: &[u8], data_bit: usize, handle_bit: usize, ver: u32) -> PyResult<Option<(Bound<'py, pyo3::types::PyDict>, usize)>> {
    let c = ent::Ctx { raw, data_bit, handle_bit, ver };
    ent::decode(py, otype, &c)
}

/// resolve_handles(raw, handle_bit, own) -> [(code, absolute handle)] (dwgmodel.resolve_handles: handle stream with relative codes resolved).
#[pyfunction]
fn resolve_handles<'py>(py: Python<'py>, raw: &[u8], handle_bit: usize, own: u128) -> PyResult<Bound<'py, PyList>> {
    let out = PyList::empty_bound(py);
    let mut hr = Rd::new(raw, handle_bit);
    let limit = (raw.len() * 8).saturating_sub(20);
    while hr.p < limit {
        match hr.h() {
            Ok((c, v)) => {
                let a: i128 = match c {
                    6 => own as i128 + 1,
                    8 => own as i128 - 1,
                    10 => own as i128 + v as i128,
                    12 => own as i128 - v as i128,
                    _ => v as i128,
                };
                out.append(PyTuple::new_bound(py, [c.to_object(py), a.to_object(py)]))?;
            }
            Err(bits::Er::Idx) => break,
            Err(e) => return Err(ent::to_pyerr(e)),
        }
    }
    Ok(out)
}

/// split_objects(od, offsets, ver) -> [(start, end, type, data_bit, handle_bit)] (dwgload.load object splitting: size field, type, bit positions).
#[pyfunction]
fn split_objects<'py>(py: Python<'py>, od: &[u8], offs: Vec<usize>, ver: u32) -> PyResult<Bound<'py, PyList>> {
    let out = PyList::empty_bound(py);
    for off in offs {
        let (start, end, ty, db, hb): (usize, usize, u32, usize, i64);
        if ver == 18 || ver == 21 {
            if off + 1 >= od.len() {
                return Err(ent::to_pyerr(bits::Er::Idx));
            }
            let w1 = od[off] as usize | ((od[off + 1] as usize) << 8);
            let (sz, hdr);
            if w1 & 0x8000 != 0 {
                if off + 3 >= od.len() {
                    return Err(ent::to_pyerr(bits::Er::Idx));
                }
                sz = (w1 & 0x7FFF) | ((od[off + 2] as usize | ((od[off + 3] as usize) << 8)) << 15);
                hdr = 32usize;
            } else {
                sz = w1;
                hdr = 16usize;
            }
            let e = (off + sz + hdr / 8 + 2).min(od.len());
            let raw = &od[off..e];
            let mut r = Rd::new(raw, hdr);
            let t = r.bs().map_err(ent::to_pyerr)?;
            let bitsize = r.rl().map_err(ent::to_pyerr)? as i64;
            start = off;
            end = e;
            ty = t;
            db = r.p;
            hb = hdr as i64 + bitsize;
        } else {
            let mut r = Rd::new(od, off * 8);
            let mut sz = (r.bits(8).map_err(ent::to_pyerr)? | (r.bits(8).map_err(ent::to_pyerr)? << 8)) as usize;
            let mut n = 2usize;
            if sz & 0x8000 != 0 {
                let hi = (r.bits(8).map_err(ent::to_pyerr)? | (r.bits(8).map_err(ent::to_pyerr)? << 8)) as usize;
                sz = (sz & 0x7FFF) | (hi << 15);
                n = 4;
            }
            let (mut v, mut sh, mut nmc) = (0u128, 0u32, 0usize);
            loop {
                let c = r.bits(8).map_err(ent::to_pyerr)? as u128;
                if sh < 120 {
                    v |= (c & 0x7F) << sh;
                }
                sh += 7;
                nmc += 1;
                if c & 0x80 == 0 {
                    break;
                }
            }
            let e = off + n + nmc + sz;
            let e2 = (e + 2).min(od.len());
            let raw = &od[off..e2];
            let mut r2 = Rd::new(raw, 0);
            // skip the size field and MC again (same layout)
            let mut tmp = (r2.bits(8).map_err(ent::to_pyerr)? | (r2.bits(8).map_err(ent::to_pyerr)? << 8)) as usize;
            if tmp & 0x8000 != 0 {
                r2.bits(16).map_err(ent::to_pyerr)?;
                tmp = 0;
            }
            let _ = tmp;
            loop {
                let c = r2.bits(8).map_err(ent::to_pyerr)?;
                if c & 0x80 == 0 {
                    break;
                }
            }
            let oc = r2.bb().map_err(ent::to_pyerr)?;
            let t = if oc == 0 {
                r2.rc().map_err(ent::to_pyerr)?
            } else if oc == 1 {
                r2.rc().map_err(ent::to_pyerr)? + 0x1F0
            } else {
                r2.rs().map_err(ent::to_pyerr)?
            };
            start = off;
            end = e2;
            ty = t;
            db = r2.p;
            hb = ((n + nmc + sz) * 8) as i64 - v as i64;
        }
        out.append((start, end, ty, db, hb))?;
    }
    Ok(out)
}

/// Candidate bit offsets of TV strings (BS length 2..120 + that many bytes) that can pass the text test of Model.proxy_texts; mode 0 = no byte test,
/// 1 = GB2312 (ASCII printable or lead A1..F7 + trail A1..FE), 2 = single-byte code page (ASCII letters, digits and -_.:/ +()%# only).
#[pyfunction]
fn tv_candidates(raw: &[u8], p0: usize, x: usize, mode: u8) -> Vec<usize> {
    let n = raw.len() * 8;
    let bit = |i: usize| -> u32 { ((raw[i >> 3] >> (7 - (i & 7))) & 1) as u32 };
    let bits = |i: usize, k: usize| -> u32 { let mut v = 0; for j in 0..k { v = v << 1 | bit(i + j); } v };
    let mut out = Vec::new();
    let mut p = p0;
    while p + 16 < x {
        if p + 18 > n { break; }
        let code = bits(p, 2);
        let (l, s) = match code {
            1 => (bits(p + 2, 8) as usize, p + 10),
            0 => {
                let lo = bits(p + 2, 8) as usize;
                let hi = bits(p + 10, 8);
                if hi != 0 { p += 1; continue; }
                (lo, p + 18)
            }
            _ => { p += 1; continue; }
        };
        if !(2..=120).contains(&l) || p + 8 * l >= x || s + 8 * l > n { p += 1; continue; }
        let mut b: Vec<u8> = (0..l).map(|k| bits(s + 8 * k, 8) as u8).collect();
        while b.last() == Some(&0) { b.pop(); }
        let ok = match mode {
            0 => b.len() >= 2 || b.is_empty() || true,
            1 => {
                let mut i = 0; let mut good = b.len() >= 2;
                while good && i < b.len() {
                    let c = b[i];
                    if (32..127).contains(&c) { i += 1; }
                    else if (0xA1..=0xF7).contains(&c) && i + 1 < b.len() && (0xA1..=0xFE).contains(&b[i + 1]) { i += 2; }
                    else { good = false; }
                }
                good
            }
            _ => b.len() >= 3 && b.iter().all(|&c| c.is_ascii_alphanumeric() || b"-_.:/ +()%#".contains(&c)),
        };
        if ok { out.push(p); }
        p += 1;
    }
    out
}

#[pymodule]
fn dwgfast(m: &Bound<'_, PyModule>) -> PyResult<()> {
    m.add_function(wrap_pyfunction!(decode_entity, m)?)?;
    m.add_function(wrap_pyfunction!(split_objects, m)?)?;
    m.add_function(wrap_pyfunction!(resolve_handles, m)?)?;
    m.add_function(wrap_pyfunction!(tv_candidates, m)?)?;
    m.add_function(wrap_pyfunction!(lz77_decompress, m)?)?;
    m.add_function(wrap_pyfunction!(lz2007_decompress, m)?)?;
    Ok(())
}
