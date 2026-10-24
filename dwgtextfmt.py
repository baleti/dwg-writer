"""Pure, standard-library helpers for DWG text formatting."""

import re


def strip_mtext(s: str) -> str:
    """MTEXT formatting removed; field codes %<...>% are kept verbatim (a path such as W:\\Projects inside a field is not an escape sequence)."""
    fields = []
    def protect(value):
        fields.append(value); return '\x00%d\x00' % (len(fields) - 1)
    def keep(m):
        return protect(m.group(0))
    s = re.sub(r'%<.*?>%', keep, s, flags=re.S)
    s = re.sub(r'(?<![A-Za-z0-9])[A-Za-z]:(?:\\(?![ACcFfHhQqTtWwp][^;\\\s]*;)[^\s\\;{}]+)+', keep, s)  # cached field results such as W:\Projects\x are literal paths, not escapes
    s = s.replace('\\P', '\n').replace('\\~', ' ')
    s = re.sub(r'\\A\d;?', '', s)  # vertical alignment, the semicolon is optional (\A1{...})
    s = re.sub(r'\\[ACcFfHhQqTtWwpP][^;\\]*;', '', s)
    s = re.sub(r'\\[LlOoKk]', '', s)
    s = re.sub(r'\\S([^;^/#\\]*)[/^#]([^;]*);', r'\1/\2', s)
    s = re.sub(r'\\U\+([0-9A-Fa-f]{4})', lambda m: chr(int(m.group(1), 16)), s)
    s = s.replace('%%c', '\u2205').replace('%%d', '\u00b0').replace('%%p', '\u00b1').replace('%%C', '\u2205').replace('%%D', '\u00b0').replace('%%P', '\u00b1')  # %%c: AutoCAD shows U+2205
    s = s.replace('\\\\', '\\')
    # Restore escaped braces only after dropping formatting braces.
    s = re.sub(r'\\([{}])', lambda m: protect(m.group(1)), s)
    s = re.sub(r'[{}]', '', s)
    return re.sub(r'\x00(\d+)\x00', lambda m: fields[int(m.group(1))], s)

