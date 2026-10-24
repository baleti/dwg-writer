"""Parse AutoCAD .lin text into linetype descriptions and dash lists."""

import math
import re


def _strip_comment(line):
    quoted = False
    for i, char in enumerate(line):
        if char == '"':
            quoted = not quoted
        elif char == ';' and not quoted:
            return line[:i].strip()
    return line.strip()


def _fields(text):
    """Split commas outside quotes and brackets, checking delimiters."""
    fields = []
    start = 0
    depth = 0
    quoted = False
    for i, char in enumerate(text):
        if char == '"':
            quoted = not quoted
        elif not quoted:
            if char == '[':
                depth += 1
                if depth > 1:
                    raise ValueError('nested brackets')
            elif char == ']':
                depth -= 1
                if depth < 0:
                    raise ValueError('unexpected closing bracket')
            elif char == ',' and depth == 0:
                fields.append(text[start:i].strip())
                start = i + 1
    if quoted or depth:
        raise ValueError('unclosed quote or bracket')
    fields.append(text[start:].strip())
    if any(not field for field in fields):
        raise ValueError('empty element')
    return fields


def _number(text):
    # Restrict float() to the decimal notation used in .lin files.
    if not re.fullmatch(r'[+-]?(?:[0-9]+(?:\.[0-9]*)?|\.[0-9]+)'
                        r'(?:[eE][+-]?[0-9]+)?', text):
        raise ValueError('invalid number: ' + text)
    value = float(text)
    if not math.isfinite(value):
        raise ValueError('number out of range: ' + text)
    return value


def _complex(token, length):
    if not token.endswith(']'):
        raise ValueError('invalid complex element')
    fields = _fields(token[1:-1])
    if len(fields) < 2:
        raise ValueError('complex element needs a style or shape file')
    first, style = fields[:2]
    result = {'length': length}
    if first.startswith('"'):
        if not first.endswith('"') or '"' in first[1:-1]:
            raise ValueError('invalid quoted text')
        result.update(text=first[1:-1], style=style)
    elif re.fullmatch(r'[+-]?[0-9]+', first):
        result.update(shape=int(first), shxfile=style)
    else:
        if any(char in first for char in '"[]'):
            raise ValueError('invalid shape name')
        result.update(shape_name=first, shxfile=style)
    for option in fields[2:]:
        key, separator, value = option.partition('=')
        key = key.strip().upper()
        if not separator or key not in ('S', 'R', 'A', 'X', 'Y'):
            raise ValueError('invalid complex option: ' + option)
        value = _number(value.strip())
        if key in ('R', 'A'):
            result['rotation'] = math.radians(value)
            if key == 'A':
                result['absolute'] = True
            else:
                result.pop('absolute', None)
        else:
            result[{'S': 'scale', 'X': 'x', 'Y': 'y'}[key]] = value
    return result


def parse_lin(text):
    """Return {UPPERCASE_NAME: (description, dashes)} from .lin text.

    Repeated pattern lines append to the current definition. A repeated
    header replaces the previous definition. Errors include the source line.
    Shape names/files are preserved for resolution by the caller.
    """
    result = {}
    current = None
    for lineno, raw in enumerate(text.splitlines(), 1):
        line = _strip_comment(raw)
        if not line:
            continue
        try:
            if line.startswith('*'):
                name, _, description = line[1:].partition(',')
                current = name.strip().upper()
                if not current:
                    raise ValueError('empty linetype name')
                result[current] = (description.strip(), [])
                continue
            if current is None:
                raise ValueError('pattern without a header')
            fields = _fields(line)
            if len(fields) < 2 or fields[0].upper() != 'A':
                raise ValueError('pattern must start with A,')
            dashes = result[current][1]
            # A length is consumed only by the next complex element on this
            # pattern line, never by a second adjacent complex element.
            pending = False
            for token in fields[1:]:
                if token.startswith('['):
                    length = dashes.pop() if pending else 0.0
                    dashes.append(_complex(token, length))
                    pending = False
                else:
                    dashes.append(_number(token))
                    pending = True
        except ValueError as exc:
            raise ValueError('line %d: %s' % (lineno, exc)) from exc
    return result


def parse_lin_file(path):
    """Read a Latin-1 .lin file and return its parsed definitions."""
    with open(path, encoding='latin-1') as stream:
        return parse_lin(stream.read())
