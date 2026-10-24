# DWG writer / editor (own code) - quick guide
Needs `templates/blank_<year>.dwg` (tools/make_templates.sh, one-time, local). Versions: AC1015 (R2000), AC1018, AC1024, AC1027, AC1032. All output verified with AutoCAD AUDIT (wtest.py).

```python
import dwgdoc, dwgxform as X
doc = dwgdoc.Doc(open('templates/blank_2018.dwg','rb').read())      # or any existing drawing: edits keep untouched objects byte-exact
doc.add_layer('A-WALL', color=3, lineweight=50); doc.add_style('Arial-100','arial.ttf'); doc.add_ltype('DASHED','Dashed',[12.5,-6.25])
doc.add_line((0,0),(1000,0),layer='A-WALL'); doc.add_circle/arc/point/lwpolyline/ellipse/text/mtext/solid/spline/hatch/leader/xline/ray/3dface/polyline2d(...)
doc.add_dimstyle('ARCH-50', DIMSCALE=50, DIMTXT=2.5); doc.add_dim_aligned/linear/radius/diameter/angular(...)
doc.add_block('DOOR'); doc.add_attdef('DOOR','MARK','prompt','D01',(0,0),100); doc.add_insert('DOOR',(0,0),attribs={'MARK':'D-17'})
lh = doc.add_layout('A3 Plan', paper=(420,297)); doc.add_viewport(lh,(210,148.5),(420,297),paper_viewport=True); doc.add_viewport(lh,(210,148.5),(380,260),view_center=(5000,3000),scale=1/50)
doc.add_xdata(h,'APP',[(1000,'x'),(1070,7)]); doc.add_xrecord(None,'KEY',[(1,'text'),(70,7)])
ls = doc.entities('*Model_Space'); doc.set_props(ls[0],color=3,layer='A-WALL'); doc.transform(ls[0],X.Transform.rotate((0,0),0.5)); doc.copy_entity(ls[1],X.Transform.mirror((0,0),(1,1))); doc.erase(ls[2])
doc.set_layer('A-WALL', new_name='WALLS'); doc.rename_block('DOOR','DOOR-A'); doc.delete_layer('OLD', force=True)
open('out.dwg','wb').write(doc.save())
```
CLI: `dwgtool.py info|layers|edit`. Tests: `python3 wtest.py OUTDIR` (AutoCAD VM), `chk_codec.py FILE -q` (codec round trip), `sweep_codec.py` (corpus, host1).
Internals: dwgcodec*.py symmetric per-object codecs; dwgwrite.py AutoCAD-strict container (see PROGRESS-WRITE.md for the rules found by experiment).

## Additions (2026-10-20)
- `doc.replace_text('old', 'new')` (TEXT, MTEXT, ATTDEF and INSERT attribute values, all blocks/layouts); CLI `dwgtool.py edit IN OUT --replace-text OLD NEW`.
- Shape linetypes: `doc.add_style('LTSHP', 'ltypeshp.shx', shapefile=True); doc.add_ltype('TRACKS', 'x', [10, dict(length=-5, shape=130, style='LTSHP'), -5])` (AUDIT clean and shapes drawn in the AutoCAD plot, R2000 and R2018).
- Older AC1015 files (BL-coded second header) can be edited; HANDSEED is located exactly (R2004 family via the header decoder).
- VM-free checks: `wtest_offline.py` (scenario build + re-read), `fuzz_edit.py SEED` (random edits on the local corpus), `worker_edit_doc.py FILE` (move/erase/retext + exact diff of all other entities).

## Additions (2026-10-21)
- `doc.add_trace(pts)` (TRACE, same layout as SOLID), `doc.add_polyline3d(pts, closed=False)` (POLYLINE3D + VERTEX3D); both AUDIT-verified in AutoCAD (wtest `more` scenario, 4 versions).
- `dwgtool.py new OUT.dwg SPEC.json [year]` builds a drawing from JSON (layers, blocks, entities: "type" X calls add_X with the other keys as kwargs); AUDIT OK 2000 and 2018.
- `doc.add_mline(pts, closed=False, justification=0, style=None|'NAME', offsets=(0.5,-0.5))` (MLINE, STANDARD-style geometry; AUDIT OK 2000-2018), `doc.purge_layers()` / `dwgtool edit --purge-layers` (drops layers no entity or viewport freeze list uses).
- `doc.erase(h)` removes the owned vertices and SEQEND of a polyline together with it.
- `dwgtool.py edit`: `--layer-on/--layer-thaw/--layer-lock/--layer-unlock/--layer-noplot N`, `--layer-lweight N HUNDREDTHS_MM`, `--change-layer FROM TO`.
- AC1021 (R2007) files open read-only in `Doc`; `save()` raises NotImplementedError (container writer blocked on unknown header checksums; Reed-Solomon encoders are in dwgrs21.py and exact against the corpus).

## Additions (2026-10-23)
- `doc.replace_text` now also edits MULTILEADER text, DIMENSION override text (and the text in its anonymous dimension block), ACAD_TABLE / TABLECONTENT / revision-schedule objects (R2010+, byte level; text inside prefix-less binary records only for same-length replacements). AUDIT edited == original on 23 real files AC1018-AC1032.
- `doc.add_mlinestyle(name, [(offset, aci|None, linetype|None), ...], description='', flags=0)`; flag bits measured: 1 miters, 2 fill, 16 start square cap, 32 start round cap, 64 start inner arcs. `add_mline(style='NAME', offsets=[...])` uses it.
- MULTILEADER (R2010+): `doc.mleaders()`, `doc.add_mleader(text, tip, landing, text_height=None, to_right=True, template=None, layer=None)` (clones a MULTILEADER of the same drawing for style and arrowhead; pass a plotting layer, the template's layer may not plot), `doc.set_mleader(h, text=, tip=, landing=, text_height=, to_right=)`; `doc.transform` moves, rotates and scales MULTILEADERs (no mirror). Plot-checked in AutoCAD. CLI: `dwgtool edit --add-mleader TEXT TIPX TIPY LANDX LANDY LAYER`.
- Layouts: `doc.rename_layout(old, new)`, `doc.set_layout(name, paper=(w, h), margins=, printer=, style_sheet=, plot_type=, rotation=)`, `doc.set_viewport(h, scale=, view_center=, view_height=, center=, size=, twist=, frozen=[layer names])`. CLI: `dwgtool edit --rename-layout OLD NEW --layout-paper NAME W H`.
- Testing: `fuzz_edit.py` ops now include add_mleader, replace_text, add_mlinestyle; `wtest.py` has an `mlstyle` scenario.
- WIPEOUT / IMAGE codec (60/60 corpus objects byte-exact). `doc.wipeouts()`, `doc.add_wipeout(points, template=None, layer=None)`; `doc.transform` handles WIPEOUT/IMAGE (mirror ok).
- `doc.add_class(dxf, cpp, app, proxy, item, counts)` (R2010+ only) adds a class record; `add_wipeout` uses it in drawings without any WIPEOUT. Finding: the class record's instance count must be the real number of objects of that class (> 0), otherwise AutoCAD shows the entities as ACAD_PROXY_ENTITY. The writer fills it at save. AUDIT 0, plot shows masks (blank 2010 and 2018).
- Not supported: add_class for AC1018/AC1015, ACIS transform, IMAGE/SHAPE/TOLERANCE creation, AC1021 save.
