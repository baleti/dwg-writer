"""Hatch pattern definitions (.pat files) and their expansion into the line list stored in a HATCH entity (own code).
A .pat file is read at run time from a path the user supplies (e.g. the one of the local AutoCAD installation); nothing is embedded
except the trivial built-ins below."""
import math, os

BUILTIN = {
    'SOLID': [],
    'ANSI31': [(45.0, 0.0, 0.0, 0.0, 0.125, [])],
    'ANSI37': [(45.0, 0.0, 0.0, 0.0, 0.125, []), (135.0, 0.0, 0.0, 0.0, 0.125, [])],
    'LINE': [(0.0, 0.0, 0.0, 0.0, 0.125, [])],
    'NET': [(0.0, 0.0, 0.0, 0.0, 0.125, []), (90.0, 0.0, 0.0, 0.0, 0.125, [])],
}

SEARCH = [os.environ.get('DWG_PAT', ''), os.path.expanduser('~/dwg-research/oracle-out/_ref/acad.pat'), os.path.expanduser('~/dwg-research/oracle-out/_ref/acadiso.pat')]


def parse_pat(path):
    """{NAME: [(angle_deg, x0, y0, dx, dy, [dashes])]}"""
    out = {}
    cur = None
    with open(path, encoding='latin1') as fh:
        lines = fh.readlines()
    for line in lines:
        line = line.split(';')[0].strip()
        if not line: continue
        if line.startswith('*'):
            cur = line[1:].split(',')[0].strip().upper()
            out[cur] = []
            continue
        if cur is None: continue
        v = [float(x) for x in line.split(',') if x.strip()]
        if len(v) < 5: continue
        out[cur].append((v[0], v[1], v[2], v[3], v[4], v[5:]))
    return out


def load(name, patfile=None):
    name = name.upper()
    if name in BUILTIN and patfile is None and not any(p and os.path.exists(p) for p in SEARCH):
        return BUILTIN[name]
    for p in ([patfile] if patfile else SEARCH):
        if p and os.path.exists(p):
            t = parse_pat(p)
            if name in t: return t[name]
    if name in BUILTIN: return BUILTIN[name]
    raise KeyError('hatch pattern not found: ' + name)


def expand(lines, scale=1.0, angle_rad=0.0):
    """HATCH entity pattern lines: (angle rad, base (x, y), offset (dx, dy), dashes)"""
    out = []
    ca, sa = math.cos(angle_rad), math.sin(angle_rad)
    for ang, x0, y0, dx, dy, dashes in lines:
        a = math.radians(ang) + angle_rad
        cb, sb = math.cos(a), math.sin(a)
        base = ((x0 * ca - y0 * sa) * scale, (x0 * sa + y0 * ca) * scale)
        off = ((dx * cb - dy * sb) * scale, (dx * sb + dy * cb) * scale)
        out.append((a, base, off, [d * scale for d in dashes]))
    return out
