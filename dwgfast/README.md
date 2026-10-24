# dwgfast: optional native fast path for the DWG reader

Own code (Rust, pyo3, abi3). Mirrors the Python reference module by module; every function has a Python fallback and the results are bit-identical
(`exp/fast_equiv.py` compares decoders object by object, `exp/fast_digest.py` compares object splitting and handle streams, `tests/test_fast.py` runs in the suite).

Build: `dwgfast/build.sh` (offline cargo, about 10 s) writes `dwgfast.abi3.so` next to the Python modules; without it everything runs in pure Python.
`DWG_NO_FAST=1` forces the Python path.

Native: R2004 LZ77 and R2007 LZ decompression, object splitting (R2004 family and AC1021), handle stream resolution, and the entity decoders
LINE ARC CIRCLE POINT SOLID TRACE 3DFACE ELLIPSE RAY XLINE LWPOLYLINE INSERT MINSERT POLYLINE2D/3D/PFACE/MESH VERTEX2D/3D/PFACE SEQEND SPLINE
(all versions) and TEXT ATTRIB ATTDEF MTEXT HATCH DIMENSION (R2007+; older versions keep the Python decoders because they record string positions for the editor).
Typical speed-up end to end: 3-8x.
