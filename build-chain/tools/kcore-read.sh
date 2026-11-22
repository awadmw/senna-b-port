#!/system/bin/sh
# Dump a slice of /proc/kcore so the PC side can locate physical memory.
# usage: kcore-read.sh <skip_bytes> <count_bytes> <outfile>
skip="$1"; count="$2"; out="$3"
if [ -z "$skip" ] || [ -z "$count" ]; then echo "usage: kcore-read.sh skip count outfile"; exit 2; fi
dd if=/proc/kcore bs=1 skip="$skip" count="$count" of="${out:-/data/local/tmp/kcore.bin}" 2>/dev/null
echo "wrote ${out:-/data/local/tmp/kcore.bin}"
ls -l "${out:-/data/local/tmp/kcore.bin}"
