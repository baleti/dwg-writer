"""Reed-Solomon codec pieces of the AC1021 (R2007) container (own analysis: parity fitted against corpus files).
System header and system pages: GF poly 0x169, 16 parity bytes (roots alpha^239..254), 239 data bytes per codeword (see SYSTEM).
Page data: k = ceil(csz / 251) codewords of 255 bytes, byte i of codeword j stored at raw[i * k + j] (column interleave); a codeword is
251 data bytes + 4 parity bytes (last codeword zero padded). GF(256) polynomial 0x11d, generator roots alpha^251 .. alpha^254 (alpha = 2)."""

class Field:
    def __init__(self, poly, n, fcr):
        self.exp = [0] * 512; self.log = [0] * 256; self.n = n
        self.fcr = fcr
        x = 1
        for i in range(255):
            self.exp[i] = x; self.log[x] = i
            x <<= 1
            if x & 256: x ^= poly
        for i in range(255, 512): self.exp[i] = self.exp[i - 255]
        g = [1]
        for i in range(n):
            r = self.exp[(fcr + i) % 255]; ng = [0] * (len(g) + 1)
            for j, c in enumerate(g):
                ng[j] ^= c; ng[j + 1] ^= self.mul(c, r)
            g = ng
        self.g = g

    def mul(self, a, b): return 0 if a == 0 or b == 0 else self.exp[self.log[a] + self.log[b]]

    def parity(self, data):
        rem = [0] * self.n; g = self.g; mul = self.mul
        for d in data:
            fb = d ^ rem[0]
            rem = rem[1:] + [0]
            if fb:
                for i in range(self.n): rem[i] ^= mul(g[i + 1], fb)
        return bytes(rem)

    def syndromes(self, cw):
        """Evaluate a highest-power-first codeword at the generator roots."""
        if len(cw) != 255:
            raise ValueError('codeword must contain 255 bytes')
        exp, log = self.exp, self.log
        result = []
        for i in range(self.n):
            root = (self.fcr + i) % 255
            value = 0
            for byte in cw:
                value = (exp[log[value] + root] if value else 0) ^ byte
            result.append(value)
        return result

    def correct(self, cw):
        """Correct up to n//2 byte errors in a 255-byte codeword.

        Uncorrectable patterns raise ValueError. As with any bounded-distance
        decoder, damage beyond that limit can resemble another valid codeword.
        """
        cw = bytes(cw)
        synd = self.syndromes(cw)
        if not any(synd):
            return cw, 0
        n, mul, exp, log = self.n, self.mul, self.exp, self.log

        # Berlekamp-Massey: polynomials here have constant coefficient first.
        locator = [1] + [0] * n
        previous = locator[:]
        degree, shift, last = 0, 1, 1
        for step in range(n):
            discrepancy = synd[step]
            for i in range(1, degree + 1):
                discrepancy ^= mul(locator[i], synd[step - i])
            if not discrepancy:
                shift += 1
                continue
            saved = locator[:]
            scale = exp[(log[discrepancy] - log[last]) % 255]
            for i in range(n + 1 - shift):
                locator[i + shift] ^= mul(scale, previous[i])
            if 2 * degree <= step:
                degree = step + 1 - degree
                previous, last, shift = saved, discrepancy, 1
            else:
                shift += 1
        if degree == 0 or degree > n // 2:
            raise ValueError('uncorrectable')
        locator = locator[:degree + 1]

        def evaluate(poly, x):
            value = 0
            for coefficient in reversed(poly):
                value = mul(value, x) ^ coefficient
            return value

        # Chien search: position p has error location X = alpha**(254-p).
        errors = []
        for pos in range(255):
            power = 254 - pos
            inverse = exp[(-power) % 255]
            if evaluate(locator, inverse) == 0:
                errors.append((pos, power, inverse))
        if len(errors) != degree:
            raise ValueError('uncorrectable')

        # Forney: Omega = (S * locator) mod x**n. The first root offset
        # contributes X**(1-fcr) to each error magnitude.
        omega = [0] * n
        for i, coefficient in enumerate(locator):
            for j in range(n - i):
                omega[i + j] ^= mul(coefficient, synd[j])
        derivative = [locator[i] if i % 2 else 0
                      for i in range(1, len(locator))]
        corrected = bytearray(cw)
        for pos, power, inverse in errors:
            numerator = evaluate(omega, inverse)
            denominator = evaluate(derivative, inverse)
            if not numerator or not denominator:
                raise ValueError('uncorrectable')
            magnitude = exp[(log[numerator] - log[denominator]
                             + power * (1 - self.fcr)) % 255]
            corrected[pos] ^= magnitude
        if any(self.syndromes(corrected)):
            raise ValueError('uncorrectable')
        return bytes(corrected), degree


DATA = Field(0x11d, 4, 251)        # data pages: RS(255,251)
SYSTEM = Field(0x169, 16, 239)     # system header and system pages (page map, section map): RS(255,239), different field polynomial


def parity(data): return DATA.parity(data)


def encode_page(data):
    """data (compressed or stored bytes) -> interleaved RS(255,251) payload of k*255 bytes (no trailing padding)"""
    k = -(-len(data) // 251)
    data = bytes(data).ljust(k * 251, b'\0')
    out = bytearray(k * 255)
    for j in range(k):
        cw = data[j * 251:(j + 1) * 251]
        cw = cw + parity(cw)
        out[j::k] = cw
    return bytes(out)


def encode_system(data, k=None):
    """system header / system page payload: ceil(len/239) codewords RS(255,239), column interleaved like encode_page"""
    k = k or -(-len(data) // 239)
    data = bytes(data).ljust(k * 239, b'\0')
    out = bytearray(k * 255)
    for j in range(k):
        cw = data[j * 239:(j + 1) * 239]
        out[j::k] = cw + SYSTEM.parity(cw)
    return bytes(out)


def decode_page(raw, k, field=None):
    """Decode k interleaved codewords, retaining any encoder data padding."""
    field = DATA if field is None else field
    if not isinstance(k, int) or k < 0 or len(raw) != k * 255:
        raise ValueError('raw length must be k * 255 with nonnegative integer k')
    raw = bytes(raw)
    data = bytearray()
    total = 0
    for j in range(k):
        corrected, count = field.correct(raw[j::k])
        data.extend(corrected[:255 - field.n])
        total += count
    return bytes(data), total


def decode_system(raw, k):
    """Decode interleaved SYSTEM codewords, retaining encoder data padding."""
    return decode_page(raw, k, SYSTEM)
