#!/bin/sh
# sweep-checks.sh NAME...  : run tools/oracle/chk_NAME.py (or countcmp) over corpus/*.dwg, 3 GB cap, output oracle-out/chk_NAME_all.txt
cd "$(dirname "$0")/../.."
for n in "$@"; do
  s=tools/oracle/chk_$n.py; [ -f "$s" ] || s=tools/oracle/$n.py
  for f in corpus/*.dwg; do echo "== $f"; PYTHONPATH=. systemd-run --user --scope -q -p MemoryMax=3G -p MemorySwapMax=0 nice -n 19 timeout 150 python3 "$s" "$f" 2>&1 | tail -1; done > oracle-out/chk_${n}_all.txt 2>&1
done
