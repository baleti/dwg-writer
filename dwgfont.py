"""Text width estimates from a local TrueType font (Liberation Sans is metric compatible with Arial); falls back to 0.6 em per character."""
import os
CANDS = ['/usr/share/fonts/liberation/LiberationSans-Regular.ttf', '/usr/share/fonts/TTF/Arial.TTF', '/usr/share/fonts/TTF/arial.ttf', '/usr/share/fonts/TTF/DejaVuSans.ttf']
_f = None


def _font():
    global _f
    if _f is None:
        _f = False
        try:
            from PIL import ImageFont
            for p in [os.environ.get('DWG_FONT', '')] + CANDS:
                if p and os.path.exists(p):
                    _f = ImageFont.truetype(p, 1000); break
        except Exception:
            pass
    return _f


def text_width(text, height, widthf=1.0):
    f = _font()
    if f:
        return f.getlength(text) / 1000.0 * height * widthf
    return len(text) * height * 0.6 * widthf


def style_factor(fontname):
    """AutoCAD text height is the CAP height of a TrueType font (Arial cap height 0.716 em), so widths scale by 1/0.716 (measured: 'Centered' at height 10 is 57.5 wide
    in AutoCAD, 41.1 by em metrics). Same factor assumed for SHX fonts (unmeasured)."""
    return 1.0 / 0.716
