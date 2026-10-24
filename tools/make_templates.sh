#!/bin/sh
# Regenerate the local (git-ignored) blank templates templates/blank_<year>.dwg with the offline AutoCAD VM. No AutoCAD is needed at writer run time.
cd "$(dirname "$0")/.." && mkdir -p templates && python3 tools/oracle/dwgscr tools/blank5.scr templates/
