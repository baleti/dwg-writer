# DWG parser accuracy against AutoCAD (aggregate numbers only)

Ground truth: AutoCAD 2026 in an offline VM dumps every corpus drawing (entities, tables, layouts, header); our own parser is compared per object with `tools/oracle/chk_*.py`. The corpus itself and the dumps are local-only and not published. Corpus: 59 drawings, AC1009 to AC1032. Numbers below are from the last sweeps (2026-10-19; ellipse, attributes and text properties re-run after the R13/R14 reader work: 56 of 59 files now readable); R13/R14 decoding is being extended, so those rows move.

| Check | Compared | Match | Note |
|---|---|---|---|
| LINE/CIRCLE/ARC/LWPOLYLINE/INSERT/POINT geometry, layer, colour, lineweight | 40 readable files | 36 files exact | rest: fit-point splines (derived control points), one anonymous-block INSERT |
| Fit-point spline to NURBS (recipe `fitspline.py`) | 11 splines | 11 (error < 1e-10) | chord-length knots, natural ends |
| TEXT/MTEXT/HATCH multiset | 76 comparisons | 69 exact | rest: fields re-evaluated by AutoCAD, annotative scale, diameter glyph |
| TEXT/MTEXT properties (height, rotation, style, width, attachment) | 20406 | 20397 | 56 files readable |
| DIMENSION (measurement, text position, user text, definition points) | 2922 | 2922 | 49 files |
| HATCH (pattern, scale, angle, loops, boundary) | 22649 | 22630 | 19 hatches in unreferenced anonymous blocks are skipped on purpose; all others match |
| ELLIPSE | 25197 | 25126 | 71 missing, all R13/R14 |
| WIPEOUT/IMAGE clip boundary | 4052 | 4052 | |
| INSERT attributes | 3158 | 3150 | one anonymous block (8 INSERTs in 2 files) |
| Symbol tables (layers, text styles, linetypes, dimstyles) | 40 files | 38 exact | 2 internal layers only |
| Header variables (~117 per file) | 57 files | 54 exact | plot-style name code page; text size in two files |
| Layouts (name, order, limits, style sheet, origin) | 148 | 148 | |
| Paper-space viewports (view, height, direction, twist) | 150 | 119 | the rest are the overall viewport AutoCAD recomputes (not drawn); one frozen-layer case |

Not yet readable by the parser: 19 of 59 files (AC1009, most AC1021). R13/R14 files load; DIMENSION is now exact in all 9, HATCH within 2 of 322; still missing VIEWPORT, ELLIPSE, LEADER, XLINE, some polylines (AutoCAD counts 2D polylines as LWPOLYLINE there), plus a small surplus of POINT/MTEXT/SOLID/INSERT in 3 files.

## Added 2026-10-21 (c8-dwgparser)
| Check | Compared | Match | Note |
|---|---|---|---|
| Entity counts per type (countcmp), 57 readable files incl. AC1021 | 57 files | 50 exact | rest: AutoCAD-created objects not stored in the file (TEXT/MTEXT/INSERT of unresolved xrefs and annotative evaluation), proxy entities, PDF underlay (now decoded) |
| Entity-level properties (visibility, linetype scale, linetype, colour method, transparency), chk_props | all handle-keyed entities | 0 differences | |
| INSUNITS / lineweight display / celweight (header tail R2007+) | 32 files | 32 | |
| INSUNITS (R2000) | 6 files | 6 | |
| Native fast path vs Python reference | 1.4M objects, 252 files of dwg2text | 0 differences | |
| AC1021 object CRC chain over the sampled corpus | 20,880 files | 20,880 | 15 container failures fixed afterwards |

## Added 2026-10-22 (c8-dwgparser)
| Check | Compared | Match | Note |
|---|---|---|---|
| R12 (AC1009) entities per block and type (chk_r12.py, tests/test_r12.py) | 2 dumped files, every block | all equal | TEXT equal except AutoCAD-recomputed width of fit text |
| R12 entity totals incl. viewports (chk_r12_corpus.py) | 15 files with AutoCAD counts | 15 | POLYLINE and LWPOLYLINE compared as one class |
| R12 linetypes / text styles / layers | 24 / 6 / 142 | all | ByBlock and ByLayer are not stored |
| R13/R14 polylines incl. 3D, polyface, mesh (chk_r14_counts.py) | 6 files | totals equal | AC1014_18 23 of 23 3D polylines equal by vertex data |
| R13/R14 entmode vs AutoCAD space (LINEs) | about 190,000 | all | model 2, paper 1, blocks 0 |
| R13/R14 per-type totals | 9 files | 5 equal, 4 with small differences | AEC dead blocks (AC1014_06/_49: LINE/POINT/INSERT/MTEXT surplus 0.03-6 percent), AC1014_37 HATCH 323 vs 322 |
| Viewport frozen layers (internal 'name @ scale' layers hidden) | AC1027_13, AC1032_27 | equal to AutoCAD (0 frozen) | AC1021_05 sets still unexplained |
| Viewport frozen layers vs AutoCAD DXF (chk_vpfrozen.py) | 212 viewports, 37 files | 212 | AC1021_05 included; the API figure of 53 was GetFrozenLayers, not the file list |
| R13/R14 entity handles vs AutoCAD drawing.dxf (chk_dxfhandles.py) | 9 files, about 290,000 entities | 0 extra, 0 missing | dead blocks and misaligned block headers fixed; AC1014_06/_49 surpluses gone |
| Entity handles vs AutoCAD drawing.dxf (chk_dxfhandles.py), R2000-R2018 | 46 files, about 1.3M entities | 0 extra / 0 missing in 42 files | AC1021_05 16 extra (dead annotation/dynamic-block objects), AC1027_13 2 extra, 1,732 proxy entities not read by design |
| R13/R14 effective linetype vs AutoCAD DXF (chk_ltype_dxf.py) | 4 files, 248,001 entities | 248,000 | miss is a DIMENSION entity |
| R13/R14 entity geometry per handle vs AutoCAD DXF (chk_geom_dxf.py) | 9 files, about 300,000 entities | all but 6 TEXT | the 6 are justified text whose position AutoCAD recomputes |
| R13/R14 text style per entity vs AutoCAD DXF (chk_style_dxf.py) | 7 files, 5,972 text entities | 5,923 | misses: long style names truncated in the R14 file |
| HATCH pattern / solid / path count per handle vs AutoCAD DXF (chk_hatch_dxf.py) | 22,378 hatches, 51 files (R13-R2018) | 22,378 | |
| TEXT/MTEXT height per handle vs AutoCAD DXF (chk_text_dxf.py) | 26,927 text entities | 26,927 | strings 25,547 equal, the rest DXF encoding conventions |
| ATTRIB/ATTDEF tag and value per handle vs AutoCAD DXF (chk_attrib_dxf.py) | 8,311 attributes | tags 8,309, values 8,287 | rest: AutoCAD-evaluated fields and one renamed tag |
| LWPOLYLINE vertices + bulges + closed per handle vs AutoCAD DXF (chk_lwpoly_dxf.py) | 44,148 polylines, 51 files | 44,148 | every file equal |
| ELLIPSE / SOLID / SPLINE per handle vs AutoCAD DXF (chk_curves_dxf.py) | 48,078 entities | 48,064 | 14 fit-point splines (control points computed by AutoCAD) |
| DIMENSION picture block / measurement / text override per handle vs AutoCAD DXF (chk_dim_dxf.py), R2000-R2018 | 3,152 dimensions | block 3,152, measurement 3,152, text 3,152 | fixed 526 wrong picture blocks |
| VIEWPORT centre / size / view centre / view height / twist per handle vs AutoCAD DXF (chk_vp_dxf.py) | 45 files | all drawn viewports equal | overall viewport (not drawn) recomputed by AutoCAD |
| LEADER vertex count, MULTILEADER text and text location per handle vs AutoCAD DXF (chk_mleader_dxf.py) | 414 entities | all equal | |
| Layer table (name, linetype, frozen/off, colour) vs AutoCAD DXF (chk_layers_dxf.py) | 4,093 layers, 25 files | names 4,083, linetype 4,086, frozen/off 4,090 | colour differences are true-colour layers |
| Layout names and paper size vs AutoCAD DXF (chk_layouts_dxf.py) | 148 layouts | names 148, paper 56 of 56 stored | 92 layouts store no paper size |
| MULTILEADER decode end position (exp/mlscan.py, host1), AC1024-AC1032 | 4,265 objects in 436 files + 409 objects of the 42 MB landscape drawing | 0 misaligned | the 150 block-attribute-label multileaders of that drawing were misaligned before |
| Per-viewport layer colour overrides vs AutoCAD DXF (chk_layovr_dxf.py) | 315 viewport blocks, 2 files | 315 equal | linetype/lineweight/transparency keys unverified |
| Layout plot option booleans vs AutoCAD (exp/plotflags.py) | 111 layouts | all bits that vary equal | PlotHidden and viewport borders never set in the sample |
| LINE/ARC/CIRCLE/POINT/LWPOLYLINE/SPLINE/INSERT geometry, layer, colour, lineweight per handle vs AutoCAD dump.json (chk_oracle.py, host1) | 33 real drawings, 340,719 entities | all equal | 52 entities of a block AutoCAD regenerates |
| TEXT/MTEXT and HATCH per entity vs AutoCAD dump.json (chk_oracle_text.py, host1) | 33 real drawings, 10,833 strings, 13,873 hatches | text 10,776, hatch 13,861 | text: evaluated fields, format codes; hatch: pattern name case |
| DIMSTYLE variables vs AutoCAD dump.json (chk_dimstyle_dump.py) | 33 real drawings, 15,414 values | all equal | variables after DIMATFIT/DIMFXLON (R2007+) not decoded |
| STYLE and LTYPE records vs AutoCAD dump.json (chk_tables_dump.py) | 4,660 values | 4,658 equal | shape-file style font, one last-used height |
| LAYER records vs AutoCAD dump.json (chk_layers_dump.py) | 10,512 values | all equal | lineweight codes map one to one |
| LAYOUT plot settings vs AutoCAD dump.json (chk_layouts_dump.py) | 1,090 values | all equal where settings are stored | 11 layouts without plot settings, 18 'none_device' spellings |
| Named views, UCS, VPORT vs AutoCAD dump.json (chk_views_dump.py) | 285 values | all equal | paper-space view flag not decoded |
| Object counts per class vs AutoCAD (chk_objcounts_dump.py) | 30 real drawings | equal after subtracting AutoCAD's erased objects | erased objects stay in the file with no known marker |
- MLINESTYLE (claude8, 2026-10-23): dwgtab.decode_mlstyle / Model.mlstyles() (name, flags, angles, elements with offset and colour) vs AutoCAD drawing.dxf (chk_mlstyle_dxf.py), 51 files R2000-R2018 with a style: 51 of 51 styles equal (flags, start/end angle, element count, offsets, colours).
- MLEADERSTYLE (claude8, 2026-10-23): dwgtab.decode_mleaderstyle / Model.mleaderstyles() (content type, orders, max points, angles, leader type, lineweight, landing/dogleg, arrow size, attachments, text height/frame, block scale/rotation, scale, annotative, break gap) vs AutoCAD drawing.dxf per handle (chk_mleaderstyle_dxf.py), AC1024-AC1032 files <= 6 MB: all decoded fields equal; 2 style handles (AC1024_21, AC1024_22) are objects AutoCAD creates in memory, absent from the file. Handles (line type, arrow, text style, block) not resolved.
- Complex linetype text (claude8, 2026-10-23): dwgtab.decode_ltype now sets dash['text'] for text elements (flag 2) from the 256/512-byte text area (code page / UTF-16). vs AutoCAD drawing.dxf LTYPE group 9 (chk_ltypetext_dxf.py, AC1018-AC1032 files <= 6 MB): 120 of 120 linetypes equal.
- ACIS body transform (claude8, 2026-10-23): dwgacis.body_transform applied in wire() and faces() (rotation rows on row vectors, scale, translation). REGION wire bounding boxes vs AutoCAD ext (campaign/solidchk.py): AC1032_26 rotated region exact (1e-15), AC1015_56 18 of 18 ok (5e-6); AC1024_21 10 REGIONs still differ by hundreds of units in a 5e10 georeferenced drawing (no transform record; lines and the arc both exceed AutoCAD's ext, cause unknown, open). The 25adb9e8da and other data-store solids could not be rechecked: source files not mounted.
- AC1024_21 REGIONs resolved (claude8): the 10 bounding-box differences are not a decoding error. Region 149FB: face loops signed areas 3,935,106 and -2,275,901 (outer arc loop, inner hole) give 1,659,205 against AutoCAD's Area 1,659,215 (0.0006 percent); AutoCAD's reported ext does not enclose its own loops, so ext is not a usable bbox oracle for these regions. Use Area/Perimeter instead.
- REGION area vs AutoCAD Area (claude8, dwgacis.area3d for vertical planes): AC1024_21 10 of 10, AC1015_56 5 of 5, AC1032_26 1 of 1 (relative 1e-3 or better).
- DIMSTYLE tail R2007+ (claude8, 2026-10-23): DIMLWD/DIMLWE (all versions), DIMTXTDIRECTION, DIMALTMZF/DIMALTMZS/DIMMZF/DIMMZS (R2010+) decoded after DIMFXLON; DIMLWD/DIMLWE equal AutoCAD's lineweight names (ByBlock 65534, ByLayer 65535, default 65533) in the 6 files checked with chk_dimstyle_dump.py (0 differences, 3,000+ values).
- Annotative flag (claude8, 2026-10-23): entities from Model.entities() carry e['annotative'] (True/False) from their AnnotativeData extended data (dwgent.annotative_flag; two 1070 integers inside braces, second = annotative). vs AutoCAD drawing.dxf xdata AnnotativeData per handle, AC1027_13: 750 of 760 equal, 0 differ, 10 handles not in our entity list (likely erased or unlisted blocks), 1 entity flagged by us only. The annotation scales of each entity (object context data) are not decoded yet.
