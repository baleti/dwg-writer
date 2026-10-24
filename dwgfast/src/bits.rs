//! DWG bit reader (mirror of dwgbits.Bits). Errors: Idx = IndexError (read past the end), Val = ValueError.
pub enum Er {
    Idx,
    Val(String),
}
pub type R<T> = Result<T, Er>;

pub struct Rd<'a> {
    pub d: &'a [u8],
    pub p: usize,
    pub n: usize,
}

impl<'a> Rd<'a> {
    pub fn new(d: &'a [u8], p: usize) -> Self {
        Rd { d, p, n: d.len() * 8 }
    }
    #[inline]
    pub fn bit(&mut self) -> R<u32> {
        let i = self.p;
        if (i >> 3) >= self.d.len() {
            return Err(Er::Idx);
        }
        self.p = i + 1;
        Ok(((self.d[i >> 3] >> (7 - (i & 7))) & 1) as u32)
    }
    /// n <= 64 bits as an unsigned integer
    #[inline]
    pub fn bits(&mut self, n: usize) -> R<u64> {
        if n == 0 {
            return Ok(0);
        }
        let i = self.p;
        let end = i + n;
        if end > self.n {
            return Err(Er::Idx);
        }
        let mut v: u128 = 0;
        let a = i >> 3;
        let b = (end + 7) >> 3;
        for k in a..b {
            v = (v << 8) | self.d[k] as u128;
        }
        self.p = end;
        let v = v >> (b * 8 - end);
        Ok((v & ((1u128 << n) - 1)) as u64)
    }
    pub fn cnt(&self, n: Option<u32>, unit: usize) -> R<usize> {
        match n {
            Some(n) if (n as usize).saturating_mul(unit) <= self.n.saturating_sub(self.p) => Ok(n as usize),
            _ => Err(Er::Val(String::from("implausible count"))),
        }
    }
    /// n whole bytes at the current bit position
    pub fn raw(&mut self, n: usize) -> R<Vec<u8>> {
        let i = self.p;
        let end = i + 8 * n;
        if end > self.n {
            return Err(Er::Idx);
        }
        let a = i >> 3;
        self.p = end;
        if i & 7 == 0 {
            return Ok(self.d[a..a + n].to_vec());
        }
        let s = i & 7;
        let mut out = Vec::with_capacity(n);
        for k in 0..n {
            let w = ((self.d[a + k] as u16) << 8) | self.d[a + k + 1] as u16;
            out.push(((w >> (8 - s)) & 0xFF) as u8);
        }
        Ok(out)
    }
    #[inline]
    pub fn rc(&mut self) -> R<u32> {
        let i = self.p;
        if i + 8 > self.n {
            return Err(Er::Idx);
        }
        self.p = i + 8;
        let a = i >> 3;
        let s = i & 7;
        if s == 0 {
            return Ok(self.d[a] as u32);
        }
        Ok((((self.d[a] as u32) << 8 | self.d[a + 1] as u32) >> (8 - s)) & 0xFF)
    }
    pub fn rs(&mut self) -> R<u32> {
        let b = self.raw(2)?;
        Ok(b[0] as u32 | (b[1] as u32) << 8)
    }
    pub fn rl(&mut self) -> R<u32> {
        let b = self.raw(4)?;
        Ok(u32::from_le_bytes([b[0], b[1], b[2], b[3]]))
    }
    pub fn rd(&mut self) -> R<f64> {
        let b = self.raw(8)?;
        Ok(f64::from_le_bytes([b[0], b[1], b[2], b[3], b[4], b[5], b[6], b[7]]))
    }
    #[inline]
    pub fn bb(&mut self) -> R<u32> {
        let i = self.p;
        if i + 2 > self.n {
            return Err(Er::Idx);
        }
        self.p = i + 2;
        let a = i >> 3;
        let s = i & 7;
        if s < 7 {
            return Ok(((self.d[a] >> (6 - s)) & 3) as u32);
        }
        Ok(((((self.d[a] as u32) << 8 | self.d[a + 1] as u32) >> 7) & 3) as u32)
    }
    pub fn bs(&mut self) -> R<u32> {
        match self.bb()? {
            0 => self.rs(),
            1 => self.rc(),
            2 => Ok(0),
            _ => Ok(256),
        }
    }
    pub fn bl(&mut self) -> R<Option<u32>> {
        match self.bb()? {
            0 => Ok(Some(self.rl()?)),
            1 => Ok(Some(self.rc()?)),
            2 => Ok(Some(0)),
            _ => Ok(None),
        }
    }
    pub fn bd(&mut self) -> R<Option<f64>> {
        match self.bb()? {
            0 => Ok(Some(self.rd()?)),
            1 => Ok(Some(1.0)),
            2 => Ok(Some(0.0)),
            _ => Ok(None),
        }
    }
    pub fn h(&mut self) -> R<(u32, u128)> {
        let code = self.bits(4)? as u32;
        let n = self.bits(4)? as usize;
        let mut v: u128 = 0;
        if n > 0 {
            for b in self.raw(n)? {
                v = (v << 8) | b as u128;
            }
        }
        Ok((code, v))
    }
    pub fn dd(&mut self, default: f64) -> R<f64> {
        let c = self.bb()?;
        if c == 0 {
            return Ok(default);
        }
        if c == 3 {
            return self.rd();
        }
        let b = default.to_le_bytes();
        let nb: [u8; 8];
        if c == 1 {
            let x = self.raw(4)?;
            nb = [x[0], x[1], x[2], x[3], b[4], b[5], b[6], b[7]];
        } else {
            let x = self.raw(6)?;
            nb = [x[2], x[3], x[4], x[5], x[0], x[1], b[6], b[7]];
        }
        Ok(f64::from_le_bytes(nb))
    }
    pub fn bt(&mut self) -> R<Option<f64>> {
        if self.bit()? == 1 {
            Ok(Some(0.0))
        } else {
            self.bd()
        }
    }
    pub fn bd3(&mut self) -> R<(Option<f64>, Option<f64>, Option<f64>)> {
        let a = self.bd()?;
        let b = self.bd()?;
        let c = self.bd()?;
        Ok((a, b, c))
    }
    pub fn be(&mut self) -> R<(Option<f64>, Option<f64>, Option<f64>)> {
        if self.bit()? == 1 {
            Ok((Some(0.0), Some(0.0), Some(1.0)))
        } else {
            self.bd3()
        }
    }
    pub fn rd2(&mut self) -> R<(f64, f64)> {
        let a = self.rd()?;
        let b = self.rd()?;
        Ok((a, b))
    }
    pub fn bll(&mut self) -> R<u128> {
        let n = self.bits(3)? as usize;
        if n == 0 {
            return Ok(0);
        }
        let mut v: u128 = 0;
        for (k, b) in self.raw(n)?.iter().enumerate() {
            v |= (*b as u128) << (8 * k);
        }
        Ok(v)
    }
    /// R2007+ text: BS length + UTF-16LE
    pub fn tu(&mut self) -> R<String> {
        let n = self.bs()? as usize;
        let b = self.raw(2 * n)?;
        let u: Vec<u16> = b.chunks(2).map(|c| c[0] as u16 | (c[1] as u16) << 8).collect();
        let s = String::from_utf16_lossy(&u);
        Ok(s.trim_end_matches('\0').to_string())
    }
    /// R2000 text: BS length + single bytes (latin1)
    pub fn tv(&mut self) -> R<String> {
        let n = self.bs()? as usize;
        let b = self.raw(n)?;
        let mut e = b.len();
        while e > 0 && b[e - 1] == 0 {
            e -= 1;
        }
        Ok(b[..e].iter().map(|&c| c as char).collect())
    }
}
