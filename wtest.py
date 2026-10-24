"""wtest.py [OUTDIR] [versions...]: writer regression suite. Builds scenario drawings from the blank templates (templates/blank_<year>.dwg,
made by tools/oracle/dwgscr) and checks each with AutoCAD AUDIT through tools/oracle/dwgq (offline VM). Exit 1 on any failure."""
import sys, os, subprocess, tempfile
import dwgdoc

HERE = os.path.dirname(os.path.abspath(__file__))
DWGQ = os.path.expanduser('~/dwg-research/tools/oracle/dwgq')


def basic(d):
    d.add_layer('A-WALL', color=3); d.add_layer('A-DOOR', color=1, lineweight=50)
    d.add_line((0, 0), (1000, 0), layer='A-WALL'); d.add_circle((500, 250), 100, layer='A-DOOR'); d.add_arc((0, 0), 300, 0.0, 1.57)
    d.add_lwpolyline([(0, 0), (100, 0), (100, 100)], closed=True); d.add_text((50, 50), 'Hello', 25.0); d.add_point((1, 1))
    d.add_ellipse((200, 200, 0), (100, 0, 0), 0.5); d.add_solid([(0, 0), (10, 0), (0, 10), (10, 10)])


def blocks(d):
    d.add_layer('A-DOOR', color=1); d.add_block('DOOR1')
    d.add_line((0, 0), (900, 0), block='DOOR1'); d.add_attdef('DOOR1', 'MARK', 'mark', 'D01', (450, -150), 100.0)
    d.add_insert('DOOR1', (1000, 2000), rot=0.5, attribs={'MARK': 'D-17'}); d.add_insert('DOOR1', (3000, 2000), scale=2)


def more(d):
    d.add_mtext((10, 20), 'Hello\\Pline2', 5.0, width=100); d.add_spline(ctrl=[(0, 0), (10, 20), (20, -10), (30, 0)]); d.add_spline(fit=[(0, 50), (10, 70), (20, 40)])
    d.add_xline((0, 0), (1, 1)); d.add_ray((0, 0), (1, 0)); d.add_3dface([(0, 0, 0), (10, 0, 0), (10, 10, 5), (0, 10, 5)])
    d.add_polyline2d([(0, 0), (10, 5), (20, 0)]); d.add_polyline3d([(0, 0, 0), (10, 5, 3), (20, 0, 6)]); d.add_trace([(0, 0), (5, 0), (0, 2), (5, 2)]); d.add_leader([(0, 0), (10, 10), (20, 10)])
    d.add_mline([(0, 100), (50, 100), (50, 150)]); d.add_mline([(100, 100), (140, 100), (140, 140), (100, 140)], closed=True, justification=1)
    d.add_hatch([[(0, 0), (100, 0), (100, 100), (0, 100)]]); d.add_hatch([[(200, 0), (300, 0), (300, 100)]], pattern='ANSI31', scale=2.0)

    d.add_block('EXP', base=(1, 1, 0)); d.add_line((1, 1), (3, 1), block='EXP'); d.add_circle((2, 2), 0.5, block='EXP'); d.add_lwpolyline([(0, 0), (4, 0), (4, 2)], block='EXP')
    d.explode(d.add_insert('EXP', (300, 300), scale=(2.0, 2.0, 2.0), rot=0.7)); d.add_insert('EXP', (400, 300))


def dims(d):
    d.add_dimstyle('ARCH-50', DIMSCALE=50.0, DIMTXT=2.5, DIMASZ=2.0, DIMDEC=0, DIMGAP=1.0)
    d.add_dim_aligned((0, 0), (5000, 0), (2500, 800), dimstyle='ARCH-50'); d.add_dim_linear((0, 0), (3000, 2000), (3500, 1000), rot=1.5707963, dimstyle='ARCH-50')
    d.add_dim_radius((150, 50), (100, 50)); d.add_dim_diameter((200, 0), (240, 0))
    d.add_dim_ordinate((0, 0), (3000, 1000), (3000, 2000), True, dimstyle='ARCH-50'); d.add_dim_ordinate((0, 0), (3000, 1000), (4500, 1000), False, dimstyle='ARCH-50')
    d.add_dim_angular2((0, 0), (1000, 0), (0, 0), (700, 700), (600, 300), dimstyle='ARCH-50')
    d.add_dim_angular((0, 0), (1000, 0), (700, 700), (600, 300), dimstyle='ARCH-50')


def layouts(d):
    d.add_layer('VP', color=5); d.add_circle((5000, 3000), 1500)
    lh = d.add_layout('A3 Plan', paper=(420, 297))
    d.add_viewport(lh, (210, 148.5), (420, 297), paper_viewport=True)
    d.add_viewport(lh, (210, 148.5), (380, 260), view_center=(5000, 3000), scale=1 / 50.0, layer='VP')


def styles(d):
    d.add_style('Arial-100', 'arial.ttf', width=0.9, oblique=0.2); d.add_ltype('DASHED5', 'Dashed', [12.5, -6.25]); d.add_layer('A-DASH', ltype='DASHED5'); d.add_ltype('GASLINE', 'Gas', [12.5, dict(length=-2.5, text='GAS', x=-1.0, y=-0.5), -2.5]); d.add_line((0, 5), (300, 5), ltype='GASLINE')
    d.add_xrecord(None, 'MYKEY', [(1, 'hello'), (70, 7), (40, 2.5), (10, (1.0, 2.0, 3.0)), (90, 123456), (290, 1), (300, 'text300')])
    h = d.add_line((0, 0), (500, 0), layer='A-DASH'); d.add_xdata(h, 'MYAPP', [(1000, 'hello'), (1070, 7), (1040, 2.5), (1010, (1.0, 2.0, 3.0))])


def retext(d):
    d.add_text((0, 0), 'Hello world', 3.0); d.add_mtext((0, 10), 'Hello\\Pline2', 3.0, width=50); d.add_block('B9'); d.add_attdef('B9', 'T', 'p', 'Hello', (0, 0), 3.0); d.add_insert('B9', (50, 50), attribs={'T': 'Hello 7'})
    assert d.replace_text('Hello', 'Bye') == 4


def shapes(d):
    d.add_style('LTSHP', 'ltypeshp.shx', shapefile=True); d.add_ltype('TRACKS', 'Tracks', [10, dict(length=-5, shape=130, style='LTSHP', scale=1.0), -5]); d.add_line((0, 0), (300, 0), ltype='TRACKS')


def edits(d):
    basic(d)
    ls = d.entities('*Model_Space')
    import dwgxform as X
    d.transform(ls[0], X.Transform.rotate((0, 0), 0.5)); d.set_props(ls[1], color=3, lweight=50); d.copy_entity(ls[1], X.Transform.translate(10, 10)); d.erase(ls[2])
    d.set_layer('A-WALL', new_name='WALLS', color=2)
    d.add_block('B1'); d.add_line((0, 0), (5, 5), block='B1'); d.rename_block('B1', 'B-REN')
    d.add_layer('GONE'); g = d.add_line((0, 0), (9, 9), layer='GONE'); d.delete_layer('GONE', force=True)
    assert d.get(g)['layer'] == d.layer_handle('0')
    d.add_layer('PURGEME'); d.add_layer('PURGE2'); assert 'purgeme' in d.purge_layers()


def xforms(d):
    import dwgxform as X
    hs = [d.add_line((0, 0), (100, 0)), d.add_circle((50, 50), 20), d.add_arc((0, 0), 30, 0.2, 2.0), d.add_lwpolyline([(0, 0), (10, 0), (10, 10)], bulges=[0.5, 0, 0]),
          d.add_text((5, 5), 'T', 3.0), d.add_mtext((5, 5), 'M', 3.0, width=30), d.add_ellipse((0, 0, 0), (10, 0, 0), 0.5, 0.0, 3.0),
          d.add_hatch([[(0, 0), (10, 0), (10, 10)]], pattern='ANSI31', scale=2.0), d.add_spline(ctrl=[(0, 0), (5, 9), (9, 0), (12, 5)]),
          d.add_dim_aligned((0, 0), (100, 0), (50, 20)), d.add_dim_radius((50, 50), (70, 50)), d.add_solid([(0, 0), (1, 0), (0, 1), (1, 1)]),
          d.add_polyline2d([(0, 0), (5, 5), (9, 0)])]
    for i, h in enumerate(hs):
        for t in (X.Transform.rotate((10, 10), 0.7), X.Transform.scale((0, 0), 2.0), X.Transform.mirror((0, 0), (1, 1))):
            c = d.copy_entity(h, t)


def mlstyle(d):
    d.add_ltype('DASHED5', 'Dashed', [12.5, -6.25]); d.add_mlinestyle('WALL3', [(1.5, 1, None), (0, 3, 'DASHED5'), (-1.5, 5, None)], description='three lines', flags=1)
    d.add_mline([(0, 0), (100, 0), (100, 60)], style='WALL3', offsets=[1.5, 0, -1.5]); d.add_mline([(0, -20), (100, -20)])


SCEN = dict(mlstyle=mlstyle, xforms=xforms, basic=basic, blocks=blocks, more=more, dims=dims, layouts=layouts, styles=styles, shapes=shapes, retext=retext, edits=edits)


def audit(path, out):
    r = subprocess.run([DWGQ, 'run', path, '--tasks', 'audit', '--summary', '--out', out], capture_output=True, text=True)
    try:
        log = open(out + '/audit.log', 'rb').read().decode('utf-16le', 'ignore').replace('\r', '')
    except OSError:
        return 'no audit log'
    if 'Total errors found 0 fixed 0' in log: return None
    for l in log.split('\n'):
        if 'Total errors' in l or 'not valid' in l or 'ERROR' in l: return l.strip()
    return 'unknown failure'


def main():
    outdir = sys.argv[1] if len(sys.argv) > 1 else tempfile.mkdtemp(prefix='wtest_')
    vers = sys.argv[2:] or ['2000', '2004', '2010', '2013', '2018']
    os.makedirs(outdir, exist_ok=True)
    bad = 0
    for v in vers:
        tpl = open(os.path.join(HERE, 'templates', 'blank_%s.dwg' % v), 'rb').read()
        for name, fn in SCEN.items():
            d = dwgdoc.Doc(tpl); fn(d)
            p = os.path.join(outdir, '%s_%s.dwg' % (name, v)); open(p, 'wb').write(d.save())
            err = audit(p, os.path.join(outdir, 'o_%s_%s' % (name, v)))
            print('%-8s %s %s' % (name, v, 'OK' if err is None else 'FAIL ' + err)); sys.stdout.flush()
            bad += err is not None
    sys.exit(1 if bad else 0)


if __name__ == '__main__':
    main()
