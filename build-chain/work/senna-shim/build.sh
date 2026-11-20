#!/usr/bin/env bash
#
# Build the senna-b diagnostic shim and wrap it into boot images.
#
# The shim is an arm64 Linux Image (header comes from start.S) so that
# Qualcomm ABL will accept it via "fastboot boot". Two containers are
# produced: v4 (what this device's stock boot.img uses) and v2 (fallback,
# what the ios-sweet shim used). Neither is flashed.
#
set -euo pipefail
cd "$(dirname "$0")"

CROSS="${CROSS:-aarch64-linux-gnu-}"
CC="${CROSS}gcc"
LD="${CROSS}ld"
OBJCOPY="${CROSS}objcopy"
OUT="${OUT:-out}"

CFLAGS=(-O2 -g -ffreestanding -fno-builtin -fno-stack-protector
	-fno-pic -fno-pie -mgeneral-regs-only -mstrict-align
	-Wall -Wextra -Werror -I.)

rm -rf "$OUT"
mkdir -p "$OUT"

"$CC" "${CFLAGS[@]}" -c start.S   -o "$OUT/start.o"
"$CC" "${CFLAGS[@]}" -c senna.c   -o "$OUT/senna.o"
"$CC" "${CFLAGS[@]}" -c console.c -o "$OUT/console.o"

"$LD" -T shim.ld -nostdlib -z max-page-size=4096 --no-warn-rwx-segments \
	-o "$OUT/shim.elf" \
	"$OUT/start.o" "$OUT/senna.o" "$OUT/console.o"
"$OBJCOPY" -O binary "$OUT/shim.elf" "$OUT/shim.bin"

echo "--- raw Image header check ---"
python3 tools/mkbootimg_img.py --pad-image "$OUT/shim.bin"
python3 tools/mkbootimg_img.py --check-image "$OUT/shim.bin"

echo "--- boot.img v4 ---"
python3 tools/mkbootimg_img.py --version 4 --kernel "$OUT/shim.bin" \
	--output "$OUT/senna-shim-v4.img" --os-version 0x18000177

echo "--- boot.img v2 (fallback) ---"
python3 tools/mkbootimg_img.py --version 2 --kernel "$OUT/shim.bin" \
	--output "$OUT/senna-shim-v2.img" --os-version 0x18000177 \
	--kernel-addr 0x8000 --ramdisk-addr 0x1000000 --tags-addr 0x100

ls -l "$OUT"
sha256sum "$OUT"/*.img | tee "$OUT/SHA256SUMS"
