# Edit matrix (aggregate only; real drawings stay in ~/dwg-edit-tests, never committed)
Runner: `edit_matrix.py run OUTDIR [--files id,id] [--ops a,b] [--limit N]` / `report OUTDIR`; sample picker `edit_sample.py 100 1` (-> ~/dwg-edit-tests/src + sample.tsv, 100 files: AC1015 8, AC1018 12, AC1021 15, AC1024 22, AC1027 18, AC1032 25; AC1021 cannot be saved so it is skipped).
Method: oracle (dwgq audit+dump) of the original, ONE batch file with one op on one entity per DXF type (distinct entities), oracle of the edited file, per-handle expectation check + "untouched entities identical" (children of edited dimension blocks excluded); on batch failure every op is re-run alone (bisect).

## Status 2026-10-25 (sweep run3 stopped after 2 of 85 files; partial AC1015 numbers: 162 PASS, 4 UNSUPPORTED, 1 FAIL_CHECK scale2, 1 FAIL_AUDIT batch, 1 FAIL_OPEN move DIMENSION)
Fixed: (1) R2018 MTEXT trailer repeated ins/xdir/width, so AutoCAD ignored moves (2f737dc, test_mtext_tail); (2) copy of an associative HATCH made AUDIT stall (copy is now non-associative, 816da3e).
Open: AC1015_5220c155cc batch FAIL_AUDIT (1 error), `move DIMENSION` no audit log (suspect AUDIT hang/crash), scale2 FAIL_CHECK; see results.jsonl in the run dir.
Gaps: AC1021 (46% of the catalogue) cannot be saved; R12-R14 not writable; mirror expectation for text types is anchor point only (MIRRTEXT 0).

## Next steps
1. `python3 edit_matrix.py run ~/dwg-edit-tests/run4` (35-60 min), then `report`, classify failures, minimise to synthetic repros, fix, add regression tests. On host2 dwgq calls `ssh host2`; adapt (DWGQ in edit_matrix.py, or ssh to itself) if the VM is local.
2. Link tests (user request): xref attach/overlay/detach/reload, path types, nested, circular, missing, clip, VISRETAIN overrides; IMAGEDEF; UNDERLAYDEFINITION (PDF/DGN/DWF); OLE; data links; hyperlinks. Block header already has is_xref/xref_path/overlaid (dwgcodec_tab). Plan: AutoCAD specimens via `dwgscr ~/dwg-edit-tests/links/xr1.scr OUTDIR` (script fixed, not yet run to completion; needs an own variant of dwgscr that uploads extra files for multi-file jobs), parse them, add writer API (add_xref / set_xref_path / detach), verify AutoCAD resolves the link in the dump.
3. More ops: text edits, per-type geometry edits, block defs and attribs, table edits (layers, styles), layouts/viewports, xdata, edit chains, save-as, boundary values, random sequences.
4. Add a dated line to ~/demo-state/SCOREBOARD.md once a full sweep exists.
