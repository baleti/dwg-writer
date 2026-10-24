"""AutoCAD INSUNITS names and conversions using millimetres per unit."""

NAMES = {
    0: "Undefined",
    1: "Inches",
    2: "Feet",
    3: "Miles",
    4: "Millimeters",
    5: "Centimeters",
    6: "Meters",
    7: "Kilometers",
    8: "Microinches",
    9: "Mils",
    10: "Yards",
    11: "Angstroms",
    12: "Nanometers",
    13: "Microns",
    14: "Decimeters",
    15: "Decameters",
    16: "Hectometers",
    17: "Gigameters",
    18: "Astronomical units",
    19: "Light years",
    20: "Parsecs",
    21: "US Survey Feet",
    22: "US Survey Inch",
    23: "US Survey Yard",
    24: "US Survey Mile",
}

MM = {
    1: 25.4,
    2: 304.8,
    3: 1609344.0,
    4: 1.0,
    5: 10.0,
    6: 1000.0,
    7: 1e6,
    8: 25.4e-6,
    9: 0.0254,
    10: 914.4,
    11: 1e-7,
    12: 1e-6,
    13: 1e-3,
    14: 100.0,
    15: 1e4,
    16: 1e5,
    17: 1e12,
    18: 1.495978707e14,
    19: 9.4607304725808e18,
    20: 3.0856775814914e19,
    21: 304.8006096012192,
    22: 25.40005080010160,
    23: 914.4018288036576,
    24: 1609347.2188,
}


def name(code: int) -> str:
    """Return the unit name, or an unknown-code label."""
    return NAMES.get(code, "Unknown (%d)" % code)


def to_mm(value: float, code: int) -> float | None:
    """Convert to millimetres, returning None for undefined or unknown units."""
    factor = MM.get(code)
    if factor is None:
        return None
    return value * factor


def convert(value: float, src: int, dst: int) -> float | None:
    """Convert between units, returning None if either unit is unsupported."""
    src_factor = MM.get(src)
    dst_factor = MM.get(dst)
    if src_factor is None or dst_factor is None:
        return None
    return value * (src_factor / dst_factor)
