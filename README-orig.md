# dwg-research: own .dwg reader / editor (pure Python, no third-party binaries at runtime)

Status 2026-10-18 (end of day). Details and provenance of every format finding: NOTES.md. Hand-over state: HANDOFF.md. Scope: SCOPE.md.

## What works
| area | AC1015 (R2000) | AC1018 (R2004) | AC1024 (R2010) | AC1027 (R2013) | AC1032 (R2018) | AC1021 (R2007) | R12-R14 |
|---|---|---|---|---|---|---|---|
| container, object map, sections | yes | yes | yes | yes | yes | NO (see NOTES) | partial |
| tables, layouts, viewports, classes, header variables, DIMSTYLE | yes (layouts incl.) | yes | yes | yes | yes | - | - |
| entities (LINE ARC CIRCLE ELLIPSE SPLINE POINT SOLID 3DFACE LWPOLYLINE POLYLINE2D TEXT MTEXT ATTRIB ATTDEF INSERT HATCH DIMENSION* VIEWPORT RAY XLINE LEADER IMAGE WIPEOUT MINSERT(unvalidated) POLYLINE3D POLYFACE/MESH; text of MULTILEADER and Tangent proxy objects) | yes | yes | yes | yes | yes (MTEXT tail skipped) | - | - |
| rewrite container / edit / add / delete | yes | yes | yes | yes | yes | - | - |

Validation: all 1.4 million entities of the 33 R2004-family corpus files decode with exact end positions; TEXT/MTEXT/HATCH/LINE/ARC/CIRCLE/LWPOLYLINE/INSERT/POINT/SPLINE of one file per version match the AutoCAD oracle exactly (chk_oracle.py, chk_oracle_text.py); written files (modify, clone, set_strings, delete) open in AutoCAD itself for AC1015-AC1032. The independent corpus run (c6, 949 files) loads 49.3% weighted, the whole gap being AC1021.

Index API: `dwg2text.py FILE... --jsonl` (schema_version 1, status/exit codes, items, attributes, dimension text, proxy_text); see NEEDS-FROM-INDEX.md.

Corpus statistics (59 real files): AC1021 ~45%, AC1032 ~26%, AC1024 ~16%, AC1027 ~7%, AC1018/AC1015/older < 3%.

AC1021 (R2007) status 2026-10-19: container pieces, Classes and Header sections decode exactly (16 pages checked by their end sentinels); the first objects page of an AutoCAD-written file verifies 51 objects by CRC16 chain (lz21crc.py / exp/lzgrow.py); the literal chunk table and a few LZ forms are still being fixed with that CRC oracle (NOTES.md). Not usable for reading yet.

R13/R14 (AC1012/AC1014) status 2026-10-19: dwgr14.py reads layers, blocks (owner handles), LINE ARC CIRCLE POINT SOLID TEXT MTEXT INSERT ATTRIB ATTDEF; counts and text equal the AutoCAD dump on the 4 files checked (chk_r14.py, exp/chk_r14_blocks.py). dwg2text.py works on them with status partial / exit 3; layouts with viewports render (dwg2svg on AC1014_37 shows the title block and the viewport content); dimension text and summary info are missing.

```python
import dwgmodel, dwgscene
m = dwgmodel.Model(open('x.dwg','rb').read())
m.layers, m.blocks, m.layer_table(), m.ltypes(), m.styles(), m.classes(), m.layouts()
for block_name, e in m.entities():       # e: dict(kind=..., geometry..., layer=..., color=..., handle=..., owner=...)
    m.effective(e)                        # resolved colour / lineweight / linetype
sc = dwgscene.Scene(buf); prims = dwgscene.render_layout(sc, layout)   # 2D primitives in paper units, viewports applied
```
Editing (R2000 / R2004 family):
```python
import dwgedit
ed = dwgedit.Editor(buf)
ed.modify(handle, lambda e: ...)                 # LINE ARC CIRCLE LWPOLYLINE ELLIPSE POINT
ed.set_strings(handle, ['new text'])             # TEXT MTEXT ATTRIB ATTDEF DIMENSION user text
nh = ed.clone_entity(template_handle, mutate)    # new entity, new handle, owner block list + HANDSEED updated
ed.delete_entity(handle, block='*Model_Space')
open('out.dwg','wb').write(ed.save())
```
Unknown objects are carried over as raw bytes (byte-exact).

## Tools
- dwg2text.py FILE [--json]   text/metadata extraction (used for indexing); exit 2 for unsupported versions
- dwg2svg.py FILE PREFIX      one SVG per layout (rsvg-convert -w 1400 x.svg -o x.png to look at it)
- selfcheck.py FILE           oracle-free decoder validation (decoder must end exactly at the end of the object's main data)
- chk_*.py FILE DXF           comparisons with ODA File Converter DXF output (oracle only)
- dwgwrite.py / dwgedit.py    container writers and the editing layer
- sweep*.py, selfcheck_all.py, typehist.py, classhist.py   corpus-wide jobs: run on host1 (h1run)

## Validation summary
- 1.4 M objects in 33 R2004-family files decode exactly (end position check), < 100 failures.
- Rewritten / edited files are opened by AutoCAD itself (oracle VM, exp/wtest.py, exp/wtest2.py): modify, clone, set_strings and delete verified on AC1018, 1024, 1027, 1032 (AC1015 opens). Earlier ODA-only checks missed stream-format errors that AutoCAD rejects (NOTES.md).
- Real drawings (HVAC schematic, civil manhole details, building services risers) render plausibly incl. paper space viewports.
