"""Expand hatch line families into boundary-clipped segments (stdlib only)."""

import math


def _union(intervals):
    result = []
    for lo, hi in sorted(intervals):
        if result and lo <= result[-1][1]:
            result[-1] = (result[-1][0], max(hi, result[-1][1]))
        else:
            result.append((lo, hi))
    return result


def _intervals(polygons, level, style):
    crossings = []
    filled = []
    boundary = []
    for polygon in polygons:
        hits = []
        for i, (x1, y1) in enumerate(polygon):
            x2, y2 = polygon[(i + 1) % len(polygon)]
            if y1 == y2:
                if y1 == level:
                    boundary.append((min(x1, x2), max(x1, x2)))
                continue
            # Half-open edge ownership counts a shared vertex only once.
            if (y1 <= level < y2) or (y2 <= level < y1):
                hits.append(x1 + (level - y1) * (x2 - x1) / (y2 - y1))
        hits.sort()
        if style == 'normal':
            crossings.extend(hits)
        else:
            filled.extend(zip(hits[::2], hits[1::2]))
    if style == 'normal':
        crossings.sort()
        filled.extend(zip(crossings[::2], crossings[1::2]))
    return _union([(a, b) for a, b in filled + boundary if b > a])


def _dashed(intervals, dashes):
    if not dashes:
        return intervals
    period = sum(abs(d) for d in dashes)
    if not math.isfinite(period) or period == 0:
        raise ValueError('dash cycle must have a finite, positive length')
    marks = []
    phase = 0.0
    for dash in dashes:
        if dash >= 0:
            marks.append((phase, phase + dash, dash == 0))
        phase += abs(dash)
    result = []
    for lo, hi in intervals:
        for start, end, dot in marks:
            first = math.ceil((lo - end) / period)
            last = math.floor((hi - start) / period)
            for cycle in range(first, last + 1):
                a = max(lo, cycle * period + start)
                b = min(hi, cycle * period + end)
                if b > a or (dot and b == a):
                    result.append((a, b))
    return sorted(set(result))


def fill_segments(loops, plines, style='normal'):
    """Return segments ordered by family, integer line index, and dash position.

    Boundaries are included, including edges collinear with a pattern line.
    ``normal`` uses even-odd interiors; ``outer`` and ``ignore`` use the
    union of polygon interiors (nested polygons cannot change that union).
    A zero offset produces one line. A nonzero parallel offset describes
    infinitely many coincident lines and raises ValueError when in range.
    Dash lists containing only zeroes have no repeat distance and are rejected.
    """
    if style not in ('normal', 'outer', 'ignore'):
        raise ValueError('unknown hatch style: %r' % style)
    polygons = [list(loop) for loop in loops if len(loop) >= 3]
    if not polygons:
        return []
    vertices = [point for polygon in polygons for point in polygon]
    xmin = min(p[0] for p in vertices)
    xmax = max(p[0] for p in vertices)
    ymin = min(p[1] for p in vertices)
    ymax = max(p[1] for p in vertices)
    corners = [(xmin, ymin), (xmin, ymax), (xmax, ymin), (xmax, ymax)]
    segments = []
    for angle, (bx, by), (ox, oy), dashes in plines:
        dx, dy = math.cos(angle), math.sin(angle)

        def project(point):
            x, y = point[0] - bx, point[1] - by
            return (x * dx + y * dy, -x * dy + y * dx)

        projected = [[project(p) for p in polygon] for polygon in polygons]
        levels = [project(p)[1] for p in corners]
        low, high = min(levels), max(levels)
        step = -ox * dy + oy * dx
        advance = ox * dx + oy * dy
        if ox == 0 and oy == 0:
            indices = range(1) if low <= 0 <= high else range(0)
        elif abs(step) <= 8 * math.ulp(math.hypot(ox, oy)):
            if low <= 0 <= high:
                raise ValueError('family produces infinitely many coincident lines')
            indices = range(0)
        else:
            a, b = sorted((low / step, high / step))
            first, last = math.ceil(a), math.floor(b)
            if last - first + 1 > 200000:
                raise ValueError('family produces more than 200000 lines')
            indices = range(first, last + 1)
        for k in indices:
            shift = k * advance
            intervals = [(a - shift, b - shift)
                         for a, b in _intervals(projected, k * step, style)]
            origin_x, origin_y = bx + k * ox, by + k * oy
            for a, b in _dashed(intervals, dashes):
                segments.append(((origin_x + a * dx, origin_y + a * dy),
                                 (origin_x + b * dx, origin_y + b * dy)))
    return segments
