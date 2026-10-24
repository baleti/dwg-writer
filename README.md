# dwg-writer

Write and edit AutoCAD .dwg files without AutoCAD (experimental).

- Writes R2004-family DWG containers with an LZ77 compressor and edits existing drawings (layouts, layers, wipeouts, images, hatches).
- Interoperability goal: every written or modified file opens in AutoCAD without audit or recovery errors. Round-trip tests are in progress.

## How it was built

Independent implementation. The format was worked out from public format descriptions (read, not copied) and by experiment, and every decoded value is checked against output of AutoCAD 2026 running in an offline virtual machine. No code, tables or constants from other DWG libraries (LibreDWG, Open Design Alliance, or others) are used. The test drawings are not redistributed.

Status: experimental.

## License

MIT, see [LICENSE](LICENSE). AutoCAD and DWG are trademarks of Autodesk, Inc. This project is independent and is not affiliated with, endorsed by or sponsored by Autodesk.
