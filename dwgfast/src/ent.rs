//! Entity decoders mirroring dwgent.py (same dict layout). Unsupported types return None so the Python decoder runs.
use crate::bits::{Er, Rd, R};
use pyo3::exceptions::{PyIndexError, PyValueError};
use pyo3::prelude::*;
use pyo3::types::{PyBytes, PyDict, PyList, PyTuple};

/// R2007+ string stream reader (dwgent.string_stream): None when the object has no string stream.
fn string_stream<'a>(raw: &'a [u8], handle_bit: usize) -> R<Option<Rd<'a>>> {
    let end = handle_bit;
    if end == 0 {
        return Err(Er::Idx);
    }
    let mut r = Rd::new(raw, end - 1);
    if r.bit()? == 0 {
        return Ok(None);
    }
    if end < 17 {
        return Err(Er::Idx);
    }
    let mut p = end - 1 - 16;
    let mut size = Rd::new(raw, p).rs()? as usize;
    if size & 0x8000 != 0 {
        if p < 16 {
            return Err(Er::Idx);
        }
        p -= 16;
        let hi = Rd::new(raw, p).rs()? as usize;
        size = (size & 0x7FFF) | (hi << 15);
    }
    if size > p {
        return Err(Er::Val(String::from("string stream start before the object")));
    }
    Ok(Some(Rd::new(raw, p - size)))
}

pub fn to_pyerr(e: Er) -> PyErr {
    match e {
        Er::Idx => PyIndexError::new_err("read past the end of the object"),
        Er::Val(s) => PyValueError::new_err(s),
    }
}

type F3 = (Option<f64>, Option<f64>, Option<f64>);

fn t3<'py>(py: Python<'py>, v: F3) -> Bound<'py, PyTuple> {
    PyTuple::new_bound(py, [v.0.to_object(py), v.1.to_object(py), v.2.to_object(py)])
}
fn t3f<'py>(py: Python<'py>, a: f64, b: f64, c: f64) -> Bound<'py, PyTuple> {
    PyTuple::new_bound(py, [a, b, c])
}
fn t2f<'py>(py: Python<'py>, a: f64, b: f64) -> Bound<'py, PyTuple> {
    PyTuple::new_bound(py, [a, b])
}

pub struct Ctx<'a> {
    pub raw: &'a [u8],
    pub data_bit: usize,
    pub handle_bit: usize,
    pub ver: u32,
}

impl<'a> Ctx<'a> {
    fn wide(&self) -> bool {
        self.ver >= 21
    }
    pub fn start(&self) -> R<Rd<'a>> {
        let mut r = Rd::new(self.raw, self.data_bit);
        r.h()?;
        Ok(r)
    }
    pub fn expected_end(&self) -> R<usize> {
        if self.ver < 21 {
            return Ok(self.handle_bit);
        }
        let end = self.handle_bit;
        let mut b = Rd::new(self.raw, end - 1);
        if b.bit()? == 1 {
            let mut p = end - 1 - 16;
            let mut size = Rd::new(self.raw, p).rs()? as usize;
            if size & 0x8000 != 0 {
                p -= 16;
                size = (size & 0x7FFF) | ((Rd::new(self.raw, p).rs()? as usize) << 15);
            }
            return Ok(p - size);
        }
        Ok(end - 1)
    }
}

fn cmc<'py>(py: Python<'py>, r: &mut Rd, ver: u32) -> R<Bound<'py, PyTuple>> {
    let mut idx = r.bs()?;
    let mut rgb: Option<u32> = None;
    let mut alpha: Option<u32> = None;
    if ver != 15 {
        if idx & 0x8000 != 0 && idx & 0x4000 == 0 {
            rgb = r.bl()?;
        }
        if idx & 0x2000 != 0 {
            alpha = r.bl()?;
        }
        idx &= 0x1FFF;
    }
    Ok(PyTuple::new_bound(py, [idx.to_object(py), rgb.to_object(py), alpha.to_object(py)]))
}

/// Common entity header (dwgent.common_entity): fills `e`.
pub fn common_entity<'py>(py: Python<'py>, r: &mut Rd, ver: u32, e: &Bound<'py, PyDict>) -> PyResult<()> {
    let eed = PyList::empty_bound(py);
    loop {
        let n = r.bs().map_err(to_pyerr)?;
        if n == 0 {
            break;
        }
        let (c, v) = r.h().map_err(to_pyerr)?;
        r.cnt(Some(n), 8).map_err(to_pyerr)?;
        let data = r.raw(n as usize).map_err(to_pyerr)?;
        eed.append(PyTuple::new_bound(py, [PyTuple::new_bound(py, [c.to_object(py), v.to_object(py)]).to_object(py), PyBytes::new_bound(py, &data).to_object(py)]))?;
    }
    e.set_item("eed", eed)?;
    if r.bit().map_err(to_pyerr)? == 1 {
        let sz: u128 = if ver >= 24 { r.bll().map_err(to_pyerr)? } else { r.rl().map_err(to_pyerr)? as u128 };
        r.p = r.p.wrapping_add((sz as usize).wrapping_mul(8));
    }
    e.set_item("entmode", r.bb().map_err(to_pyerr)?)?;
    e.set_item("nreactors", r.bl().map_err(to_pyerr)?)?;
    e.set_item("xdicmissing", r.bit().map_err(to_pyerr)?)?;
    if ver == 27 || ver == 32 {
        e.set_item("hasbinary", r.bit().map_err(to_pyerr)?)?;
    }
    e.set_item("color", cmc(py, r, ver).map_err(to_pyerr_py)?)?;
    e.set_item("ltscale", r.bd().map_err(to_pyerr)?)?;
    e.set_item("ltflags", r.bb().map_err(to_pyerr)?)?;
    e.set_item("plotflags", r.bb().map_err(to_pyerr)?)?;
    if ver >= 21 {
        e.set_item("material", r.bb().map_err(to_pyerr)?)?;
        e.set_item("shadow", r.rc().map_err(to_pyerr)?)?;
        if ver != 21 {
            r.bit().map_err(to_pyerr)?;
            r.bit().map_err(to_pyerr)?;
            r.bit().map_err(to_pyerr)?;
        }
    }
    e.set_item("invis", r.bs().map_err(to_pyerr)?)?;
    e.set_item("lweight", r.rc().map_err(to_pyerr)?)?;
    Ok(())
}

fn to_pyerr_py(e: Er) -> PyErr {
    to_pyerr(e)
}

macro_rules! q {
    ($x:expr) => {
        $x.map_err(to_pyerr)?
    };
}

fn nz(v: Option<f64>) -> PyResult<f64> {
    v.ok_or_else(|| PyValueError::new_err("implausible BD"))
}

/// Decode one entity. Returns (dict, end_bit) or None when the type has no native decoder.
pub fn decode<'py>(py: Python<'py>, otype: u32, c: &Ctx) -> PyResult<Option<(Bound<'py, PyDict>, usize)>> {
    let supported = matches!(otype, 19 | 17 | 18 | 27 | 31 | 32 | 28 | 35 | 40 | 41 | 77 | 7 | 8 | 15 | 10 | 6 | 11 | 16 | 12 | 13 | 14 | 29 | 30 | 36) || (c.ver >= 21 && matches!(otype, 1 | 2 | 3 | 44 | 78 | 20..=26));
    if !supported {
        return Ok(None);
    }
    let ver = c.ver;
    if otype == 36 {
        return decode_spline(py, c).map(Some);
    }
    let mut r = q!(c.start());
    let e = PyDict::new_bound(py);
    common_entity(py, &mut r, ver, &e)?;
    match otype {
        19 => {
            let z0 = q!(r.bit());
            let x1 = q!(r.rd());
            let x2 = q!(r.dd(x1));
            let y1 = q!(r.rd());
            let y2 = q!(r.dd(y1));
            let (mut z1, mut z2) = (0.0, 0.0);
            if z0 == 0 {
                z1 = q!(r.rd());
                z2 = q!(r.dd(z1));
            }
            e.set_item("kind", "LINE")?;
            e.set_item("p1", t3f(py, x1, y1, z1))?;
            e.set_item("p2", t3f(py, x2, y2, z2))?;
            e.set_item("thickness", q!(r.bt()))?;
            e.set_item("ext", t3(py, q!(r.be())))?;
        }
        17 | 18 => {
            let ce = q!(r.bd3());
            let rad = q!(r.bd());
            let th = q!(r.bt());
            let ex = q!(r.be());
            e.set_item("kind", if otype == 18 { "CIRCLE" } else { "ARC" })?;
            e.set_item("center", t3(py, ce))?;
            e.set_item("radius", rad)?;
            e.set_item("thickness", th)?;
            e.set_item("ext", t3(py, ex))?;
            if otype == 17 {
                e.set_item("a0", q!(r.bd()))?;
                e.set_item("a1", q!(r.bd()))?;
            }
        }
        27 => {
            e.set_item("kind", "POINT")?;
            e.set_item("p", t3(py, q!(r.bd3())))?;
            e.set_item("thickness", q!(r.bt()))?;
            e.set_item("ext", t3(py, q!(r.be())))?;
            e.set_item("xangle", q!(r.bd()))?;
        }
        31 | 32 => {
            let th = q!(r.bt());
            let el = q!(r.bd());
            let mut pts = Vec::new();
            for _ in 0..4 {
                let (a, b) = q!(r.rd2());
                pts.push(t2f(py, a, b));
            }
            e.set_item("kind", if otype == 31 { "SOLID" } else { "TRACE" })?;
            e.set_item("thickness", th)?;
            e.set_item("elev", el)?;
            e.set_item("pts", PyList::new_bound(py, pts))?;
            e.set_item("ext", t3(py, q!(r.be())))?;
        }
        28 => {
            let noflags = q!(r.bit());
            let zzero = q!(r.bit());
            let (x, y) = q!(r.rd2());
            let z = if zzero == 1 { 0.0 } else { q!(r.rd()) };
            let mut pts = vec![(x, y, z)];
            for _ in 0..3 {
                let l = *pts.last().unwrap();
                let x = q!(r.dd(l.0));
                let y = q!(r.dd(l.1));
                let z = q!(r.dd(l.2));
                pts.push((x, y, z));
            }
            let inv = if noflags == 1 { 0 } else { q!(r.bs()) };
            e.set_item("kind", "3DFACE")?;
            e.set_item("pts", PyList::new_bound(py, pts.iter().map(|p| t3f(py, p.0, p.1, p.2)).collect::<Vec<_>>()))?;
            e.set_item("invisible", inv)?;
        }
        35 => {
            e.set_item("kind", "ELLIPSE")?;
            e.set_item("center", t3(py, q!(r.bd3())))?;
            e.set_item("major", t3(py, q!(r.bd3())))?;
            e.set_item("ext", t3(py, q!(r.bd3())))?;
            e.set_item("ratio", q!(r.bd()))?;
            e.set_item("a0", q!(r.bd()))?;
            e.set_item("a1", q!(r.bd()))?;
        }
        40 | 41 => {
            e.set_item("kind", if otype == 40 { "RAY" } else { "XLINE" })?;
            e.set_item("p", t3(py, q!(r.bd3())))?;
            e.set_item("v", t3(py, q!(r.bd3())))?;
        }
        77 => {
            let fl = q!(r.bs());
            let cw = if fl & 4 != 0 { q!(r.bd()) } else { Some(0.0) };
            let el = if fl & 8 != 0 { q!(r.bd()) } else { Some(0.0) };
            let th = if fl & 2 != 0 { q!(r.bd()) } else { Some(0.0) };
            let nm: F3 = if fl & 1 != 0 { q!(r.bd3()) } else { (Some(0.0), Some(0.0), Some(1.0)) };
            let n = q!(r.bl());
            let nb = if fl & 16 != 0 { q!(r.bl()) } else { Some(0) };
            let nids = if fl & 1024 != 0 { q!(r.bl()) } else { Some(0) };
            let nw = if fl & 32 != 0 { q!(r.bl()) } else { Some(0) };
            let n = q!(r.cnt(n, 2));
            let mut pts: Vec<(f64, f64)> = Vec::with_capacity(n);
            for i in 0..n {
                if i == 0 {
                    pts.push(q!(r.rd2()));
                } else {
                    let l = pts[i - 1];
                    let x = q!(r.dd(l.0));
                    let y = q!(r.dd(l.1));
                    pts.push((x, y));
                }
            }
            let nb = q!(r.cnt(nb, 2));
            let mut bul: Vec<Option<f64>> = Vec::with_capacity(nb);
            for _ in 0..nb {
                bul.push(q!(r.bd()));
            }
            let nids = q!(r.cnt(nids, 2));
            for _ in 0..nids {
                q!(r.bl());
            }
            let nw = q!(r.cnt(nw, 4));
            let mut wid: Vec<(Option<f64>, Option<f64>)> = Vec::with_capacity(nw);
            for _ in 0..nw {
                let a = q!(r.bd());
                let b = q!(r.bd());
                wid.push((a, b));
            }
            e.set_item("kind", "LWPOLYLINE")?;
            e.set_item("flags", fl)?;
            e.set_item("closed", fl & 512 != 0)?;
            e.set_item("constwidth", cw)?;
            e.set_item("elev", el)?;
            e.set_item("thickness", th)?;
            e.set_item("ext", t3(py, nm))?;
            e.set_item("pts", PyList::new_bound(py, pts.iter().map(|p| t2f(py, p.0, p.1)).collect::<Vec<_>>()))?;
            e.set_item("bulges", PyList::new_bound(py, bul.iter().map(|b| b.to_object(py)).collect::<Vec<_>>()))?;
            e.set_item("widths", PyList::new_bound(py, wid.iter().map(|w| PyTuple::new_bound(py, [w.0.to_object(py), w.1.to_object(py)])).collect::<Vec<_>>()))?;
        }
        7 | 8 => {
            let ip = q!(r.bd3());
            let sf = q!(r.bb());
            let (sx, sy, sz);
            if sf == 0 {
                sx = q!(r.rd());
                sy = q!(r.dd(sx));
                sz = q!(r.dd(sx));
            } else if sf == 1 {
                sx = 1.0;
                sy = q!(r.dd(1.0));
                sz = q!(r.dd(1.0));
            } else if sf == 2 {
                sx = q!(r.rd());
                sy = sx;
                sz = sx;
            } else {
                sx = 1.0;
                sy = 1.0;
                sz = 1.0;
            }
            let rot = q!(r.bd());
            let ex = q!(r.bd3());
            let ha = q!(r.bit());
            if ha == 1 && ver != 15 {
                q!(r.bl());
            }
            e.set_item("kind", if otype == 7 { "INSERT" } else { "MINSERT" })?;
            e.set_item("ins", t3(py, ip))?;
            e.set_item("scale", t3f(py, sx, sy, sz))?;
            e.set_item("rot", rot)?;
            e.set_item("ext", t3(py, ex))?;
            e.set_item("hasattribs", ha)?;
            if otype == 8 {
                e.set_item("cols", q!(r.bs()))?;
                e.set_item("rows", q!(r.bs()))?;
                e.set_item("col_spacing", q!(r.bd()))?;
                e.set_item("row_spacing", q!(r.bd()))?;
            }
        }
        15 => {
            let fl = q!(r.bs());
            let curve = q!(r.bs());
            let sw = q!(r.bd());
            let ew = q!(r.bd());
            let th = q!(r.bt());
            let el = q!(r.bd());
            let ex = q!(r.be());
            let nowned: Option<u32> = if ver != 15 { q!(r.bl()) } else { Some(0) };
            e.set_item("kind", "POLYLINE2D")?;
            e.set_item("flags", fl)?;
            e.set_item("closed", fl & 1 != 0)?;
            e.set_item("curve", curve)?;
            e.set_item("start_width", sw)?;
            e.set_item("end_width", ew)?;
            e.set_item("thickness", th)?;
            e.set_item("elev", el)?;
            e.set_item("ext", t3(py, ex))?;
            e.set_item("nvert", nowned)?;
        }
        10 => {
            let fl = q!(r.rc());
            let p = q!(r.bd3());
            let sw = q!(r.bd());
            let swf = nz(sw)?;
            let ew = if swf < 0.0 { Some(-swf) } else { q!(r.bd()) };
            let bulge = q!(r.bd());
            let vid: Option<u32> = if ver >= 24 { q!(r.bl()) } else { Some(0) };
            let tan = q!(r.bd());
            e.set_item("kind", "VERTEX2D")?;
            e.set_item("flags", fl)?;
            e.set_item("p", t3(py, p))?;
            e.set_item("start_width", swf.abs())?;
            e.set_item("end_width", ew)?;
            e.set_item("bulge", bulge)?;
            e.set_item("vid", vid)?;
            e.set_item("tangent", tan)?;
        }
        6 => {
            e.set_item("kind", "SEQEND")?;
        }
        11 => {
            e.set_item("kind", "VERTEX3D")?;
            e.set_item("flags", q!(r.rc()))?;
            e.set_item("p", t3(py, q!(r.bd3())))?;
        }
        16 => {
            let fl1 = q!(r.rc());
            let fl2 = q!(r.rc());
            let nowned: Option<u32> = if ver != 15 { q!(r.bl()) } else { Some(0) };
            e.set_item("kind", "POLYLINE3D")?;
            e.set_item("flags", fl1)?;
            e.set_item("flags2", fl2)?;
            e.set_item("closed", fl2 & 1 != 0)?;
            e.set_item("nvert", nowned)?;
        }
        12 | 13 => {
            e.set_item("kind", if otype == 13 { "VERTEX_PFACE" } else { "VERTEX_MESH" })?;
            e.set_item("flags", q!(r.rc()))?;
            e.set_item("p", t3(py, q!(r.bd3())))?;
        }
        14 => {
            let mut idx: Vec<i64> = Vec::new();
            for _ in 0..4 {
                let i = q!(r.bs()) as i64;
                idx.push(if i > 32767 { i - 65536 } else { i });
            }
            e.set_item("kind", "VERTEX_PFACE_FACE")?;
            e.set_item("idx", PyList::new_bound(py, idx))?;
        }
        29 => {
            let nv = q!(r.bs());
            let nf = q!(r.bs());
            let nowned: Option<u32> = if ver != 15 { q!(r.bl()) } else { Some(0) };
            e.set_item("kind", "POLYLINE_PFACE")?;
            e.set_item("nverts", nv)?;
            e.set_item("nfaces", nf)?;
            e.set_item("nvert", nowned)?;
        }
        30 => {
            let fl = q!(r.bs());
            let curve = q!(r.bs());
            let m = q!(r.bs());
            let n = q!(r.bs());
            q!(r.bs());
            q!(r.bs());
            let nowned: Option<u32> = if ver != 15 { q!(r.bl()) } else { Some(0) };
            e.set_item("kind", "POLYLINE_MESH")?;
            e.set_item("flags", fl)?;
            e.set_item("curve", curve)?;
            e.set_item("m", m)?;
            e.set_item("n", n)?;
            e.set_item("m_closed", fl & 1 != 0)?;
            e.set_item("n_closed", fl & 32 != 0)?;
            e.set_item("nvert", nowned)?;
        }
        1 | 2 | 3 => {
            let mut ss = q!(string_stream(c.raw, c.handle_bit));
            let fl = q!(r.rc());
            let elev = if fl & 1 != 0 { 0.0 } else { q!(r.rd()) };
            let ins = q!(r.rd2());
            let al = if fl & 2 != 0 { ins } else { (q!(r.dd(ins.0)), q!(r.dd(ins.1))) };
            let ex = q!(r.be());
            let th = q!(r.bt());
            let obl = if fl & 4 != 0 { 0.0 } else { q!(r.rd()) };
            let rot = if fl & 8 != 0 { 0.0 } else { q!(r.rd()) };
            let h = q!(r.rd());
            let wf = if fl & 0x10 != 0 { 1.0 } else { q!(r.rd()) };
            let txt = match ss.as_mut() { Some(sr) => q!(sr.tu()), None => q!(r.tu()) };
            let gen = if fl & 0x20 != 0 { 0 } else { q!(r.bs()) };
            let ha = if fl & 0x40 != 0 { 0 } else { q!(r.bs()) };
            let va = if fl & 0x80 != 0 { 0 } else { q!(r.bs()) };
            e.set_item("elev", elev)?;
            e.set_item("ins", t2f(py, ins.0, ins.1))?;
            e.set_item("align", t2f(py, al.0, al.1))?;
            e.set_item("ext", t3(py, ex))?;
            e.set_item("thickness", th)?;
            e.set_item("oblique", obl)?;
            e.set_item("rot", rot)?;
            e.set_item("height", h)?;
            e.set_item("widthf", wf)?;
            e.set_item("text", txt)?;
            e.set_item("gen", gen)?;
            e.set_item("halign", ha)?;
            e.set_item("valign", va)?;
            if otype == 1 {
                e.set_item("kind", "TEXT")?;
            } else {
                if ver >= 24 {
                    e.set_item("version", q!(r.rc()))?;
                }
                if ver == 32 {
                    let at = q!(r.rc());
                    e.set_item("attr_type", at)?;
                    if at > 1 {
                        return Ok(None); // multiline attribute (R2018): Python decoder
                    }
                }
                let mut rd = |r: &mut Rd| -> R<String> { match ss.as_mut() { Some(sr) => sr.tu(), None => r.tu() } };
                let tag = q!(rd(&mut r));
                let flen = q!(r.bs());
                let flags = q!(r.rc());
                if ver >= 21 {
                    e.set_item("lock_position", q!(r.bit()))?;
                }
                if otype == 3 && ver >= 24 {
                    q!(r.rc());
                }
                let prompt: Option<String> = if otype == 3 { Some(q!(rd(&mut r))) } else { None };
                e.set_item("kind", if otype == 2 { "ATTRIB" } else { "ATTDEF" })?;
                e.set_item("tag", tag)?;
                e.set_item("field_length", flen)?;
                e.set_item("attflags", flags)?;
                e.set_item("prompt", prompt)?;
            }
        }
        78 => {
            let mut ss = q!(string_stream(c.raw, c.handle_bit));
            let grad = PyDict::new_bound(py);
            grad.set_item("is_gradient", q!(r.bl()))?;
            q!(r.bl());
            grad.set_item("angle", q!(r.bd()))?;
            grad.set_item("shift", q!(r.bd()))?;
            grad.set_item("single_color", q!(r.bl()))?;
            grad.set_item("tint", q!(r.bd()))?;
            let ncol = q!(r.bl());
            let ncol = q!(r.cnt(ncol, 8));
            let cols = PyList::empty_bound(py);
            for _ in 0..ncol {
                let v = q!(r.bd());
                let a = q!(r.bs());
                let b = q!(r.bl());
                let cc = q!(r.rc());
                cols.append(PyTuple::new_bound(py, [v.to_object(py), PyTuple::new_bound(py, [a.to_object(py), b.to_object(py), cc.to_object(py)]).to_object(py)]))?;
            }
            grad.set_item("colors", cols)?;
            let gname = match ss.as_mut() { Some(sr) => q!(sr.tu()), None => q!(r.tu()) };
            grad.set_item("name", gname)?;
            let elev = q!(r.bd());
            let ext = q!(r.bd3());
            let pname = match ss.as_mut() { Some(sr) => q!(sr.tu()), None => q!(r.tu()) };
            let solid = q!(r.bit());
            let assoc = q!(r.bit());
            let npaths = q!(r.bl());
            let npaths = q!(r.cnt(npaths, 2));
            let paths = PyList::empty_bound(py);
            let mut any_pixel = false;
            for _ in 0..npaths {
                let fl = q!(r.bl()).ok_or_else(|| PyValueError::new_err("hatch flags"))?;
                let segs = PyList::empty_bound(py);
                let path = PyDict::new_bound(py);
                if fl & 2 != 0 {
                    let bulges = q!(r.bit());
                    let closed = q!(r.bit());
                    let n = q!(r.bl());
                    let n = q!(r.cnt(n, 128));
                    for _ in 0..n {
                        let p = q!(r.rd2());
                        let b: Option<f64> = if bulges == 1 { q!(r.bd()) } else { Some(0.0) };
                        segs.append(PyTuple::new_bound(py, ["P".to_object(py), t2f(py, p.0, p.1).to_object(py), b.to_object(py)]))?;
                    }
                    path.set_item("flags", fl)?;
                    path.set_item("closed", closed == 1)?;
                    path.set_item("segs", segs)?;
                } else {
                    let n = q!(r.bl());
                    let n = q!(r.cnt(n, 8));
                    for _ in 0..n {
                        let t = q!(r.rc());
                        if t == 1 {
                            let a = q!(r.rd2());
                            let b = q!(r.rd2());
                            segs.append(PyTuple::new_bound(py, ["L".to_object(py), t2f(py, a.0, a.1).to_object(py), t2f(py, b.0, b.1).to_object(py)]))?;
                        } else if t == 2 {
                            let a = q!(r.rd2());
                            let (b1, b2, b3) = (q!(r.bd()), q!(r.bd()), q!(r.bd()));
                            let f = q!(r.bit());
                            segs.append(PyTuple::new_bound(py, ["A".to_object(py), t2f(py, a.0, a.1).to_object(py), b1.to_object(py), b2.to_object(py), b3.to_object(py), f.to_object(py)]))?;
                        } else if t == 3 {
                            let a = q!(r.rd2());
                            let b = q!(r.rd2());
                            let (b1, b2, b3) = (q!(r.bd()), q!(r.bd()), q!(r.bd()));
                            let f = q!(r.bit());
                            segs.append(PyTuple::new_bound(py, ["E".to_object(py), t2f(py, a.0, a.1).to_object(py), t2f(py, b.0, b.1).to_object(py), b1.to_object(py), b2.to_object(py), b3.to_object(py), f.to_object(py)]))?;
                        } else if t == 4 {
                            let deg = q!(r.bl());
                            let rat = q!(r.bit());
                            let per = q!(r.bit());
                            let nk = q!(r.bl());
                            let nc = q!(r.bl());
                            let nk = q!(r.cnt(nk, 2));
                            let mut kn: Vec<Option<f64>> = Vec::with_capacity(nk);
                            for _ in 0..nk {
                                kn.push(q!(r.bd()));
                            }
                            let nc = q!(r.cnt(nc, 128));
                            let cp = PyList::empty_bound(py);
                            for _ in 0..nc {
                                let pt = q!(r.rd2());
                                let w: Option<f64> = if rat == 1 { q!(r.bd()) } else { Some(1.0) };
                                cp.append(PyTuple::new_bound(py, [t2f(py, pt.0, pt.1).to_object(py), w.to_object(py)]))?;
                            }
                            let mut fit: PyObject = py.None();
                            if ver >= 24 {
                                let nf = q!(r.bl());
                                if nf.map_or(false, |n| n != 0) {
                                    let nf = q!(r.cnt(nf, 128));
                                    let mut pts = Vec::with_capacity(nf);
                                    for _ in 0..nf {
                                        let p = q!(r.rd2());
                                        pts.push(t2f(py, p.0, p.1));
                                    }
                                    let t0 = q!(r.rd2());
                                    let t1 = q!(r.rd2());
                                    fit = PyTuple::new_bound(py, [PyList::new_bound(py, pts).to_object(py), t2f(py, t0.0, t0.1).to_object(py), t2f(py, t1.0, t1.1).to_object(py)]).to_object(py);
                                }
                            }
                            segs.append(PyTuple::new_bound(py, ["S".to_object(py), deg.to_object(py), (rat == 1).to_object(py), (per == 1).to_object(py), PyList::new_bound(py, kn.iter().map(|k| k.to_object(py)).collect::<Vec<_>>()).to_object(py), cp.to_object(py), fit]))?;
                        } else {
                            return Err(PyValueError::new_err(format!("hatch seg type {}", t)));
                        }
                    }
                    path.set_item("flags", fl)?;
                    path.set_item("segs", segs)?;
                }
                path.set_item("nboundary", q!(r.bl()))?;
                if fl & 4 != 0 {
                    any_pixel = true;
                }
                paths.append(path)?;
            }
            let style = q!(r.bs());
            let ptype = q!(r.bs());
            let mut pattern: PyObject = py.None();
            let (mut angle, mut scale, mut double) = (Some(0.0f64), Some(0.0f64), 0u32);
            if solid == 0 {
                angle = q!(r.bd());
                scale = q!(r.bd());
                double = q!(r.bit());
                let nl = q!(r.bs());
                let nl = q!(r.cnt(Some(nl), 8));
                let pl = PyList::empty_bound(py);
                for _ in 0..nl {
                    let a = q!(r.bd());
                    let p0 = (q!(r.bd()), q!(r.bd()));
                    let off = (q!(r.bd()), q!(r.bd()));
                    let nd = q!(r.bs());
                    let nd = q!(r.cnt(Some(nd), 2));
                    let mut ds: Vec<Option<f64>> = Vec::with_capacity(nd);
                    for _ in 0..nd {
                        ds.push(q!(r.bd()));
                    }
                    pl.append(PyTuple::new_bound(py, [a.to_object(py), PyTuple::new_bound(py, [p0.0.to_object(py), p0.1.to_object(py)]).to_object(py), PyTuple::new_bound(py, [off.0.to_object(py), off.1.to_object(py)]).to_object(py), PyList::new_bound(py, ds.iter().map(|d| d.to_object(py)).collect::<Vec<_>>()).to_object(py)]))?;
                }
                pattern = pl.to_object(py);
            }
            let pixel: Option<Option<f64>> = if any_pixel { Some(q!(r.bd())) } else { None };
            let nseeds = q!(r.bl());
            let nseeds = q!(r.cnt(nseeds, 128));
            let mut seeds = Vec::with_capacity(nseeds);
            for _ in 0..nseeds {
                let p = q!(r.rd2());
                seeds.push(t2f(py, p.0, p.1));
            }
            e.set_item("kind", "HATCH")?;
            e.set_item("gradient", grad)?;
            e.set_item("elev", elev)?;
            e.set_item("ext", t3(py, ext))?;
            e.set_item("pattern_name", pname)?;
            e.set_item("solid", solid)?;
            e.set_item("assoc", assoc)?;
            e.set_item("paths", paths)?;
            e.set_item("style", style)?;
            e.set_item("pattern_type", ptype)?;
            e.set_item("pattern_angle", angle)?;
            e.set_item("pattern_scale", scale)?;
            e.set_item("pattern_double", double)?;
            e.set_item("pattern_lines", pattern)?;
            e.set_item("pixel", pixel.map(|x| x.to_object(py)))?;
            e.set_item("seeds", PyList::new_bound(py, seeds))?;
        }
        20..=26 => {
            let mut ss = q!(string_stream(c.raw, c.handle_bit));
            if ver >= 24 {
                e.set_item("dim_version", q!(r.rc()))?;
            }
            let ext = q!(r.bd3());
            let tm = q!(r.rd2());
            let el = q!(r.bd());
            let df = q!(r.rc());
            let ut = match ss.as_mut() { Some(sr) => q!(sr.tu()), None => q!(r.tu()) };
            e.set_item("ext", t3(py, ext))?;
            e.set_item("text_mid", t2f(py, tm.0, tm.1))?;
            e.set_item("elevation", el)?;
            e.set_item("dflags", df)?;
            e.set_item("user_text", ut)?;
            e.set_item("text_rot", q!(r.bd()))?;
            e.set_item("horiz_dir", q!(r.bd()))?;
            e.set_item("ins_scale", t3(py, q!(r.bd3())))?;
            e.set_item("ins_rot", q!(r.bd()))?;
            e.set_item("attach", q!(r.bs()))?;
            e.set_item("ls_style", q!(r.bs()))?;
            e.set_item("ls_factor", q!(r.bd()))?;
            e.set_item("measurement", q!(r.bd()))?;
            e.set_item("unknown_b", q!(r.bit()))?;
            e.set_item("flip1", q!(r.bit()))?;
            e.set_item("flip2", q!(r.bit()))?;
            let cp = q!(r.rd2());
            e.set_item("clone_pt", t2f(py, cp.0, cp.1))?;
            match otype {
                21 => {
                    e.set_item("pt13", t3(py, q!(r.bd3())))?;
                    e.set_item("pt14", t3(py, q!(r.bd3())))?;
                    e.set_item("pt10", t3(py, q!(r.bd3())))?;
                    e.set_item("ext_rot", q!(r.bd()))?;
                    e.set_item("dim_rot", q!(r.bd()))?;
                }
                22 => {
                    e.set_item("pt13", t3(py, q!(r.bd3())))?;
                    e.set_item("pt14", t3(py, q!(r.bd3())))?;
                    e.set_item("pt10", t3(py, q!(r.bd3())))?;
                    e.set_item("ext_rot", q!(r.bd()))?;
                }
                23 => {
                    e.set_item("pt10", t3(py, q!(r.bd3())))?;
                    e.set_item("pt13", t3(py, q!(r.bd3())))?;
                    e.set_item("pt14", t3(py, q!(r.bd3())))?;
                    e.set_item("pt15", t3(py, q!(r.bd3())))?;
                }
                24 => {
                    let p16 = q!(r.rd2());
                    e.set_item("pt16", t2f(py, p16.0, p16.1))?;
                    e.set_item("pt13", t3(py, q!(r.bd3())))?;
                    e.set_item("pt14", t3(py, q!(r.bd3())))?;
                    e.set_item("pt15", t3(py, q!(r.bd3())))?;
                    e.set_item("pt10", t3(py, q!(r.bd3())))?;
                }
                25 | 26 => {
                    e.set_item("pt10", t3(py, q!(r.bd3())))?;
                    e.set_item("pt15", t3(py, q!(r.bd3())))?;
                    e.set_item("leader_len", q!(r.bd()))?;
                }
                _ => {
                    e.set_item("pt10", t3(py, q!(r.bd3())))?;
                    e.set_item("pt13", t3(py, q!(r.bd3())))?;
                    e.set_item("pt14", t3(py, q!(r.bd3())))?;
                    e.set_item("oflags", q!(r.rc()))?;
                }
            }
            e.set_item("kind", match otype { 20 => "DIM_ORDINATE", 21 => "DIM_LINEAR", 22 => "DIM_ALIGNED", 23 => "DIM_ANG3PT", 24 => "DIM_ANG2LN", 25 => "DIM_RADIUS", _ => "DIM_DIAMETER" })?;
        }
        44 => {
            let ins = q!(r.bd3());
            let ex = q!(r.bd3());
            let xd = q!(r.bd3());
            let w = q!(r.bd());
            let h = q!(r.bd());
            let th = q!(r.bd());
            let att = q!(r.bs());
            let dd = q!(r.bs());
            let eh = q!(r.bd());
            let ew = q!(r.bd());
            let mut ss = q!(string_stream(c.raw, c.handle_bit));
            let txt = match ss.as_mut() { Some(sr) => q!(sr.tu()), None => q!(r.tu()) };
            let ls_style = q!(r.bs());
            let ls_factor = q!(r.bd());
            q!(r.bit());
            let mut bg_scale: Option<Option<f64>> = None;
            let mut bg_col: Option<Bound<'py, PyTuple>> = None;
            let mut bg_trans: Option<Option<u32>> = None;
            let bg = q!(r.bl()).ok_or_else(|| PyValueError::new_err("mtext bg"))?;
            if bg & 1 != 0 {
                bg_scale = Some(q!(r.bd()));
                let a = q!(r.bs());
                let b = q!(r.bl());
                let cc = q!(r.rc());
                bg_col = Some(PyTuple::new_bound(py, [a.to_object(py), b.to_object(py), cc.to_object(py)]));
                bg_trans = Some(q!(r.bl()));
            }
            if ver == 32 {
                r.p = q!(c.expected_end());
            }
            e.set_item("kind", "MTEXT")?;
            e.set_item("ins", t3(py, ins))?;
            e.set_item("ext", t3(py, ex))?;
            e.set_item("xdir", t3(py, xd))?;
            e.set_item("width", w)?;
            e.set_item("height", h)?;
            e.set_item("text_height", th)?;
            e.set_item("attachment", att)?;
            e.set_item("drawdir", dd)?;
            e.set_item("ext_h", eh)?;
            e.set_item("ext_w", ew)?;
            e.set_item("text", txt)?;
            e.set_item("ls_style", ls_style)?;
            e.set_item("ls_factor", ls_factor)?;
            e.set_item("bgflags", bg)?;
            e.set_item("bg_scale", bg_scale.map(|x| x.to_object(py)))?;
            e.set_item("bg_color", bg_col)?;
            e.set_item("bg_transparency", bg_trans.map(|x| x.to_object(py)))?;
        }
        _ => return Ok(None),
    }
    let _ = c.wide();
    Ok(Some((e, r.p)))
}

fn spline_layout<'py>(py: Python<'py>, c: &Ctx, scenario: u32) -> PyResult<(Bound<'py, PyDict>, usize)> {
    let ver = c.ver;
    let mut r = q!(c.start());
    let e = PyDict::new_bound(py);
    common_entity(py, &mut r, ver, &e)?;
    q!(r.bl());
    if ver == 27 || ver == 32 {
        q!(r.bl());
        q!(r.bl());
    }
    let degree = q!(r.bl());
    let mut ctrl: Vec<Bound<'py, PyTuple>> = Vec::new();
    let mut fit: Vec<Bound<'py, PyTuple>> = Vec::new();
    let mut knots: Vec<Option<f64>> = Vec::new();
    let mut weights: Vec<Option<f64>> = Vec::new();
    let (mut rational, mut closed, mut periodic) = (false, false, false);
    let (mut tan0, mut tan1): (Option<F3>, Option<F3>) = (None, None);
    if scenario == 1 {
        rational = q!(r.bit()) == 1;
        closed = q!(r.bit()) == 1;
        periodic = q!(r.bit()) == 1;
        q!(r.bd());
        q!(r.bd());
        let nk = q!(r.bl());
        let nc = q!(r.bl());
        let weighted = q!(r.bit()) == 1;
        let nk = q!(r.cnt(nk, 2));
        for _ in 0..nk {
            knots.push(q!(r.bd()));
        }
        let nc = q!(r.cnt(nc, 6));
        for _ in 0..nc {
            ctrl.push(t3(py, q!(r.bd3())));
            if weighted {
                weights.push(q!(r.bd()));
            }
        }
    } else if scenario == 2 {
        q!(r.bd());
        tan0 = Some(q!(r.bd3()));
        tan1 = Some(q!(r.bd3()));
        let nf = q!(r.bl());
        let nf = q!(r.cnt(nf, 6));
        for _ in 0..nf {
            fit.push(t3(py, q!(r.bd3())));
        }
    } else {
        return Err(PyValueError::new_err("scenario"));
    }
    e.set_item("kind", "SPLINE")?;
    e.set_item("scenario", scenario)?;
    e.set_item("degree", degree)?;
    e.set_item("rational", rational)?;
    e.set_item("closed", closed)?;
    e.set_item("periodic", periodic)?;
    e.set_item("knots", PyList::new_bound(py, knots.iter().map(|b| b.to_object(py)).collect::<Vec<_>>()))?;
    e.set_item("ctrl", PyList::new_bound(py, ctrl))?;
    e.set_item("weights", PyList::new_bound(py, weights.iter().map(|b| b.to_object(py)).collect::<Vec<_>>()))?;
    e.set_item("fit", PyList::new_bound(py, fit))?;
    e.set_item("tan0", tan0.map(|t| t3(py, t)))?;
    e.set_item("tan1", tan1.map(|t| t3(py, t)))?;
    Ok((e, r.p))
}

fn decode_spline<'py>(py: Python<'py>, c: &Ctx) -> PyResult<(Bound<'py, PyDict>, usize)> {
    let ver = c.ver;
    let mut r0 = q!(c.start());
    let scratch = PyDict::new_bound(py);
    common_entity(py, &mut r0, ver, &scratch)?;
    let scenario0 = q!(r0.bl());
    let mut sflags = 0u32;
    if ver == 27 || ver == 32 {
        sflags = q!(r0.bl()).ok_or_else(|| PyValueError::new_err("spline flags"))?;
    }
    let sc0 = scenario0.unwrap_or(99);
    let order: [u32; 2] = if sflags & 1 != 0 { [2, 1] } else { [sc0, if sc0 == 1 || sc0 == 2 { 3 - sc0 } else { 1 }] };
    let exp_end = q!(c.expected_end());
    let mut first: Option<(Bound<'py, PyDict>, usize)> = None;
    for sc in order {
        match spline_layout(py, c, sc) {
            Ok((e, end)) => {
                if first.is_none() {
                    first = Some((e.clone(), end));
                }
                if end == exp_end {
                    return Ok((e, end));
                }
            }
            Err(err) => {
                if err.is_instance_of::<PyValueError>(py) || err.is_instance_of::<PyIndexError>(py) {
                    continue;
                }
                return Err(err);
            }
        }
    }
    first.ok_or_else(|| PyValueError::new_err("spline layout"))
}
