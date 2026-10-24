#!/bin/sh
# Build the optional native extension and copy it next to the Python modules (dwgfast.abi3.so, git-ignored). Without it everything runs in pure Python.
# Usage: dwgfast/build.sh   (cargo, offline crates cache; small: about 10 s; run niced)
set -e
cd "$(dirname "$0")"
nice -n 19 cargo build --release --offline
cp target/release/libdwgfast.so ../dwgfast.abi3.so.tmp && mv -f ../dwgfast.abi3.so.tmp ../dwgfast.abi3.so  # atomic: running processes keep the old mapping
echo "built ../dwgfast.abi3.so"
