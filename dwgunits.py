"""Pure dimension formatting, with lengths in inches for DIMLUNIT 3 and 4.

DIMZIN's low two bits select a feet/inches mode, not independent flags:
1 includes zero feet and inches; 2 includes zero feet but omits zero inches;
3 omits zero feet but includes zero inches; 0 omits both zero components.
A completely zero length always remains visible. Modes apply to both
engineering and architectural output. Architectural fractions retain an
explicit whole-inch zero when feet are shown.

Bits 4 and 8 suppress leading and trailing decimal zeros respectively,
including engineering inches; they never change fraction precision or
scientific mantissa digits. Engineering zero inches retain decimal precision
unless suppressed by the feet/inches mode or trailing-zero flag.
All rounding uses half away from zero, including the final display precision.
Inputs are interpreted through their decimal string representations to avoid
binary floating-point tie artifacts. Nonfinite values are not supported.

Reference: https://help.autodesk.com/cloudhelp/2019/ENU/AutoCAD-LT/files/
GUID-A1860981-FE1C-4947-927B-7CD6B8CEF8EE.htm
"""

from fractions import Fraction
from math import gcd


def _nearest(value):
    """Round a nonnegative Fraction to an integer, with ties upward."""
    whole, remainder = divmod(value.numerator, value.denominator)
    return whole + (2 * remainder >= value.denominator)


def _decimal(ticks, dec, zin):
    """Render nonnegative integer ticks at 10**dec ticks per unit."""
    if dec:
        digits = str(ticks).zfill(dec + 1)
        text = digits[:-dec] + "." + digits[-dec:]
        if zin & 8:
            text = text.rstrip("0").rstrip(".")
        if zin & 4 and text.startswith("0."):
            text = text[1:]
        return text
    return str(ticks)


def _fraction(ticks, denominator, include_zero=False):
    whole, numerator = divmod(ticks, denominator)
    if not numerator:
        return str(whole)
    divisor = gcd(numerator, denominator)
    fraction = f"{numerator // divisor}/{denominator // divisor}"
    return f"{whole} {fraction}" if whole or include_zero else fraction


def _feet_inches(feet, inches, inches_text, zin):
    mode = zin & 3
    show_feet = bool(feet) or mode in (1, 2)
    show_inches = bool(inches) or mode in (1, 3) or not show_feet
    parts = []
    if show_feet:
        parts.append(f"{feet}'")
    if show_inches:
        parts.append(inches_text + '"')
    return "-".join(parts)


def format_length(value, lunit=2, dec=4, zin=0, dsep='.', rnd=0.0,
                  prefix='', suffix='', lfac=1.0):
    """Format a scaled length using DIMLUNIT, DIMDEC and DIMZIN.

    DIMLFAC is applied before positive DIMRND increments. DIMLUNIT selects
    scientific (1), decimal (2), engineering (3), architectural (4), or
    fractional (5) output. For 4/5, dec is a denominator exponent in 0..8;
    otherwise it is a nonnegative number of decimal places. Affixes surround
    the signed number, and dsep must be a single decimal separator character.
    Invalid unit/precision/separator arguments raise ValueError.
    """
    if lunit not in (1, 2, 3, 4, 5):
        raise ValueError("lunit must be in 1..5")
    if not isinstance(dec, int) or dec < 0 or (lunit in (4, 5) and dec > 8):
        raise ValueError("invalid decimal or fractional precision")
    if not isinstance(dsep, str) or len(dsep) != 1:
        raise ValueError("dsep must be one character")
    scaled = Fraction(str(value)) * Fraction(str(lfac))
    negative = scaled < 0
    magnitude = abs(scaled)
    increment = Fraction(str(rnd))
    if increment > 0:
        magnitude = _nearest(magnitude / increment) * increment

    if lunit == 1:
        exponent = 0
        mantissa = magnitude
        if magnitude:
            exponent = (len(str(magnitude.numerator))
                        - len(str(magnitude.denominator)))
            power = Fraction(10) ** exponent
            if magnitude < power:
                exponent -= 1
                power /= 10
            mantissa = magnitude / power
        ticks = _nearest(mantissa * 10**dec)
        if ticks >= 10 ** (dec + 1):
            ticks //= 10
            exponent += 1
        text = _decimal(ticks, dec, 0) + f"E{exponent:+03d}"
    elif lunit in (2, 3):
        denominator = 10**dec
        ticks = _nearest(magnitude * denominator)
        if lunit == 2:
            text = _decimal(ticks, dec, zin)
        else:
            feet, inches = divmod(ticks, 12 * denominator)
            inch_text = _decimal(inches, dec, zin)
            text = _feet_inches(feet, inches, inch_text, zin)
    else:
        denominator = 2**dec
        ticks = _nearest(magnitude * denominator)
        if lunit == 5:
            text = _fraction(ticks, denominator)
        else:
            feet, inches = divmod(ticks, 12 * denominator)
            inch_text = _fraction(
                inches, denominator, include_zero=bool(feet) or (zin & 3) in (1, 2))
            text = _feet_inches(feet, inches, inch_text, zin)

    text = text.replace(".", dsep)
    if negative and ticks:
        text = "-" + text
    return prefix + text + suffix


def parse_dim_text(template, measurement_text):
    r"""Replace every <> placeholder, preserving literal codes such as \X.

    Empty text uses the measurement; exactly one space suppresses all text.
    """
    if template == "":
        return measurement_text
    if template == " ":
        return ""
    return template.replace("<>", measurement_text)
