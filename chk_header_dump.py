"""Header variables vs AutoCAD dump.json header (case-insensitive names): chk_header_dump.py FILE.dwg STEM"""
import sys, json, dwgmodel
f, stem = sys.argv[1:3]
h = json.load(open('oracle-out/%s/dump.json' % stem))['header']
mh = {k.upper(): v for k, v in dwgmodel.Model(open(f, 'rb').read()).header().items()}
INS = {n: i for i, n in enumerate('Undefined Inches Feet Miles Millimeters Centimeters Meters Kilometers Microinches Mils Yards Angstroms Nanometers Microns Decimeters Decameters Hectometers Gigameters AstronomicalUnits LightYears Parsecs USSurveyFeet USSurveyInch USSurveyYard USSurveyMile'.split())}
ok = bad = miss = 0; ex = []
for k, v in h.items():
    K = k.upper()
    if K not in mh: miss += 1; continue
    a = mh[K]
    if isinstance(v, dict) and 'h' in v:
        if isinstance(a, tuple): a = a[1]
        v = int(v['h'], 16)
    elif isinstance(v, dict) and 'method' in v:
        a = a[2] if False else {0xC0: 'ByLayer', 0xC1: 'ByBlock'}.get(a[1] >> 24, 'index') if isinstance(a, tuple) else a; v = v['method'] if v['method'] in ('ByLayer', 'ByBlock') else 'index'
    elif isinstance(v, str) and v.startswith(('ByBlock', 'ByLayer')) and isinstance(a, int):
        v = {'ByBlock': 65534, 'ByLayer': 65533}.get(v, v)
    elif k == 'TimeZone': continue
    if isinstance(v, list): v = tuple(v)
    if isinstance(a, tuple) and isinstance(v, tuple):
        eq = len(a) == len(v) and all(abs(x - y) <= 1e-6 * max(1, abs(y)) for x, y in zip(a, v))
        if eq: ok += 1
        else: bad += 1; ex.append((k, a, v)) if len(ex) < 30 else 0
        continue
    if K == 'INSUNITS' and isinstance(v, str): v = INS.get(v, v)
    try: eq = abs(float(a) - float(v)) < 1e-6 * max(1, abs(float(v)))
    except Exception: eq = str(a) == str(v)
    if eq: ok += 1
    else:
        bad += 1
        if len(ex) < 30: ex.append((k, a, v))
print(stem, 'equal', ok, 'differ', bad, 'not-read', miss, ex)
