# AutoCAD oracle (offline VM) - local only, never publish outputs
Ground truth for the DWG parser/writer/viewer: AutoCAD 2026 (also 2025, 2021 installed) in an OFFLINE Windows VM on host2. Outputs derived from client drawings stay on host2/host3 local disks.

## Use (from host3, light)
    tools/oracle/dwgq run FILE.dwg [--tasks dump,dxf,plot] [--summary] [--png DPI] [--timeout S] [--year 2026]
    tools/oracle/dwgq vm status|start|stop
Results go to ~/dwg-research/oracle-out/<stem>/ (git-ignored):
- dump.json   .NET dump (see below)          - drawing.dxf   DXFOUT ASCII R2018, 16 decimals
- plots/<Layout>.native.pdf  layout's own page setup (device swapped to DWG To PDF; paper size picked from the layout, falls back to A3 when the layout has no real paper)
- plots/<Layout>.fixed.pdf   A3 landscape, extents, scale to fit, no plot style table (same framing for every file; best for pixel diffs)  (+ .png with --png)
- plots/plot.log, *.log (accoreconsole transcripts), status.json (per task ok/seconds/exit; ok=false means timeout, killed)
- audit.log (task `audit`, for validating files written by our writer): AutoCAD AUDIT with fix=Y, read the transcript for 'errors found'/'fixed'; plus dump.log shows open failures.
Typical job: 2-10 s per task. The VM auto-starts if down (boot ~60 s). Reference tables (acad.lin, acadiso.lin, acad.pat, acadiso.pat, CTB/STB, PC3, SHX font list) are in oracle-out/_ref (Autodesk files, local only).
Known limit: an empty layout plots as model content in the fixed mode (AutoCAD fallback); compare layouts that have entities.

## dump.json layout (JSON, one object)
file, acad (host version), header{all Database system variables by property name (Ltscale, Pdmode, Insunits, Extmin, Extmax, Limmin, Lunits, Clayer, Textstyle, Dimstyle, ...), handseed, original_file_version_int (DwgVersion enum: 16=AC1009, 19=AC1012, 25=AC1018, 27=AC1021 ... measured on corpus), saved_as_version_int},
layers[] (all LayerTableRecord props), linetypes[] (dashes: length, shape/text/offset/scale/rotation), textstyles[] (font), dimstyles[] (all dim vars), ucs[], views[], viewports_table[], regapps[],
layouts[] (all Layout + PlotSettings props: paper size/units, media, plot style sheet, scale, plot type/window, rotation, origin, ...; viewport_handles),
named_objects{} (root dictionary keys, class, entries), object_counts{DXFNAME: n} and erased_counts for EVERY database object found by handle 1..handseed (validates an object map), objects[[handleHex, class]] (full mode),
blocks[] each: name, handle, layout flag/name, xref, anon, dynamic, origin, units, entity_counts{}, entities[] (full mode).
Entity record (short keys): h handle, t DXF type, layer, lt linetype, lts, lw lineweight (enum int, -1 bylayer, -2 byblock, -3 default), ci colour index (+rgb for true colour, cm for bylayer/byblock), vis, alpha, ps plot style, mat, ext [minx,miny,minz,maxx,maxy,maxz], xdata [[code,value]],
then per type: LINE a,b | CIRCLE c,r,n | ARC c,r,a0,a1,n | ELLIPSE | LWPOLYLINE v[[x,y,bulge,w0,w1]],closed,elev,cw | POLYLINE2D/3D v | SPLINE deg,cp,knots,wts,fit | TEXT/ATTDEF s,p,al,h,rot,wf,obl,style,hm,vm,tag | MTEXT contents,s,p,h,width,rot,att,style,dir | INSERT name,p,sc,rot,n,attrs[{tag,s,p,..}] | HATCH pattern,ptype,pscale,pangle,htype,assoc,solid,loops[{type,poly|curves}],area | DIMENSION dimstyle,text,meas,tp,block + type-specific points | LEADER/MLEADER | VIEWPORT number,c,w,h,on,vc,vt,vd,vh,twist,scale,std,locked,nonrect,clip,frozen[],vstyle | POINT/SOLID/3DFACE/XLINE/RAY/WIPEOUT/IMAGE/TABLE/3DSOLID basics; other types: reflected simple properties. A record with "err" failed to dump (rest of the file is unaffected).

## Infrastructure
- Channel: sshd over vsock via own relay (guest/vsock-relay.ps1, task at boot), host2 helpers ~/bin/acps (PowerShell stdin), acrun, acput, acget.
- Guest: Win11 22621 eval, user User blank password autologon, updates/telemetry/search/SysMain disabled, no NIC. AutoCAD 2021/2025/2026 with a local Autodesk network licence service (licence left untouched).
- WINDOWS EVALUATION LICENCE: the guest powers itself off about 1 h after boot ("license period expired", wlms). dwgq restarts it automatically. Not circumvented (a user decision if rearm is wanted).
- Plugin source: guest/dwgdump/{DwgDump.cs,DwgPlot.cs,DwgDump.csproj} built with the guest's dotnet SDK 8 (offline) to C:\work\bin\DwgDump.dll; commands DWGDUMP, DWGPLOT run inside accoreconsole (headless). Job runner guest/run-job.ps1 (C:\oracle).
- Console fallback (QMP): screendump/sendkey helpers were scratch scripts (see HANDOFF-c3-dwgvm.md).

## Parser-vs-oracle checkers (no VM needed once oracle-out/ is filled)
Run from ~/dwg-research with PYTHONPATH=. : tools/oracle/{countcmp,chk_viewports,chk_tables,chk_header,chk_dims,chk_hatch,chk_layouts,chk_textprops,chk_ellipse,chk_wipeout,chk_attribs}.py FILE.dwg (plus the older chk_oracle.py, chk_oracle_text.py in the repo root). One-file runs take seconds; loop over corpus/*.dwg with a 3 GB cap and write oracle-out/chk_<name>_all.txt. `tools/oracle/scoreboard.py` summarises those files. Findings and their classification (parser bug / oracle artefact) are at the tail of NEEDS-FROM-INDEX.md.
