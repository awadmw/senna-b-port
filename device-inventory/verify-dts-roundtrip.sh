#!/usr/bin/env bash
# Independent dtc round-trip verification for the senna live DTS.
#
# Purpose (REMAINING.md B.1): device-inventory/senna-live.dts was produced by a
# local FDT parser, not by dtc. This script proves the text is valid dtc input
# and that compiling it reproduces the same device tree as the original binary,
# using the upstream device-tree-compiler instead of our own tooling.
#
# Usage: verify-dts-roundtrip.sh <original.dtb> <senna-live.dts> [outdir]
# Exit:  0 = round-trip identical, 1 = differ or tool failure.
set -uo pipefail

DTB=${1:-dtb/senna-live.dtb}
DTS=${2:-device-inventory/senna-live.dts}
OUT=${3:-dts-roundtrip}
REPORT="$OUT/report.txt"
mkdir -p "$OUT"
: > "$REPORT"
say() { printf '%s\n' "$*" | tee -a "$REPORT"; }
rc=0

if ! command -v dtc >/dev/null 2>&1; then
  say "FAIL: dtc not installed"
  exit 1
fi
say "dtc-version: $(dtc --version 2>&1 | head -1)"
say "host: $(uname -srm)"
say "input-dtb: $DTB ($(stat -c%s "$DTB" 2>/dev/null || echo '?') bytes)"
say "input-dts: $DTS ($(stat -c%s "$DTS" 2>/dev/null || echo '?') bytes)"
say "sha256-dtb: $(sha256sum "$DTB" | cut -d' ' -f1)"
say "sha256-dts: $(sha256sum "$DTS" | cut -d' ' -f1)"

# 1. Ground truth: what the real blob contains, rendered by dtc.
dtc -I dtb -O dts -o "$OUT/from-binary.dts" "$DTB" 2> "$OUT/from-binary.err"
rc1=$?
say "step1 dtc -I dtb -O dts (original) rc=$rc1"
[ $rc1 -ne 0 ] && { sed -n '1,20p' "$OUT/from-binary.err" | while read -r l; do say "  err: $l"; done; rc=1; }

# 2. Recompile the textual dump under test.
dtc -I dts -O dtb -o "$OUT/rebuilt.dtb" "$DTS" 2> "$OUT/recompile.err"
rc2=$?
say "step2 dtc -I dts -O dtb (senna-live.dts) rc=$rc2"
[ $rc2 -ne 0 ] && { sed -n '1,20p' "$OUT/recompile.err" | while read -r l; do say "  err: $l"; done; rc=1; }

# 3. Render the rebuilt blob the same way for comparison.
if [ $rc2 -eq 0 ]; then
  dtc -I dtb -O dts -o "$OUT/rebuilt.dts" "$OUT/rebuilt.dtb" 2> "$OUT/rebuilt.err"
  rc3=$?
  say "step3 dtc -I dtb -O dts (rebuilt) rc=$rc3"
  [ $rc3 -ne 0 ] && rc=1
  say "sha256-rebuilt-dtb: $(sha256sum "$OUT/rebuilt.dtb" | cut -d' ' -f1)"
  say "size-rebuilt-dtb: $(stat -c%s "$OUT/rebuilt.dtb")"
fi

# 4. Structural counts recorded independently of formatting.
if [ -f "$OUT/from-binary.dts" ] && [ -f "$OUT/rebuilt.dts" ]; then
  nodes_a=$(grep -c '{[[:space:]]*$' "$OUT/from-binary.dts")
  nodes_b=$(grep -c '{[[:space:]]*$' "$OUT/rebuilt.dts")
  props_a=$(grep -cE '^[[:space:]]+[^/=][^;]*;' "$OUT/from-binary.dts")
  props_b=$(grep -cE '^[[:space:]]+[^/=][^;]*;' "$OUT/rebuilt.dts")
  say "nodes: binary=$nodes_a rebuilt=$nodes_b"
  say "properties: binary=$props_a rebuilt=$props_b"
  [ "$nodes_a" != "$nodes_b" ] && { say "FAIL: node count differs"; rc=1; }
  [ "$props_a" != "$props_b" ] && { say "FAIL: property count differs"; rc=1; }

  # 5. Textual diff of two dtc renderings: any difference is a real data
  #    difference because both sides use the same formatter.
  if diff -u "$OUT/from-binary.dts" "$OUT/rebuilt.dts" > "$OUT/dts.diff" 2>&1; then
    say "diff: identical (0 lines)"
  else
    say "diff: $(wc -l < "$OUT/dts.diff") diff lines, see dts.diff"
    sed -n '1,60p' "$OUT/dts.diff" | while read -r l; do say "  $l"; done
    rc=1
  fi
fi

if [ $rc -eq 0 ]; then say "VERDICT: PASS - dtc round-trip is identical"; else say "VERDICT: FAIL"; fi
exit $rc
