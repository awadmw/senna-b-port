#!/usr/bin/env python3
"""Pack an arm64 Linux Image into an Android boot.img (v2 or v4 header).

Only what the senna-b diagnostic shim needs: kernel + optional ramdisk +
optional dtb (v2 only), no AVB signature, no vendor_boot.

Header layouts follow AOSP system/tools/mkbootimg (bootimg.h).
"""
import argparse
import struct
import sys

PAGE = 4096
V4_HDR_SIZE = 1584
V2_HDR_SIZE = 1648


def align(n, a):
    return (n + a - 1) // a * a


def pad_image(path):
    """Pad the raw Image up to its own image_size.

    objcopy leaves the stack/BSS reservation out of the file (it is not a
    loaded section), while the arm64 header advertises _end - _text.
    Linux boot loaders read the file length, so make both agree.
    """
    data = bytearray(open(path, "rb").read())
    if len(data) < 64:
        sys.exit("image too small: %d bytes" % len(data))
    image_size = struct.unpack_from("<Q", data, 16)[0]
    if image_size < len(data):
        sys.exit("image_size (%d) < file size (%d)" % (image_size, len(data)))
    if image_size > len(data):
        orig = len(data)
        data += b"\x00" * (image_size - orig)
        with open(path, "wb") as f:
            f.write(bytes(data))
        print("  padded %s from %d to image_size %d"
              % (path, orig, image_size))
    else:
        print("  %s already matches image_size %d" % (path, image_size))


def check_image(path):
    data = open(path, "rb").read()
    if len(data) < 64:
        sys.exit("image too small: %d bytes" % len(data))
    code0 = struct.unpack_from("<I", data, 0)[0]
    code1 = struct.unpack_from("<I", data, 4)[0]
    text_offset = struct.unpack_from("<Q", data, 8)[0]
    image_size = struct.unpack_from("<Q", data, 16)[0]
    flags = struct.unpack_from("<Q", data, 24)[0]
    magic = data[56:60]
    rows = [
        ("code0 (branch)", "0x%08x" % code0),
        ("code1", "0x%08x" % code1),
        ("text_offset", "0x%x" % text_offset),
        ("image_size", "%d" % image_size),
        ("flags", "0x%x" % flags),
        ("magic", repr(magic)),
        ("file size", "%d" % len(data)),
    ]
    for k, v in rows:
        print("  %-16s %s" % (k, v))
    errs = []
    if (code0 & 0xfc000000) != 0x14000000:
        errs.append("code0 is not an unconditional branch")
    if magic != b"ARM\x64":
        errs.append("magic is not ARM64")
    if text_offset != 0:
        errs.append("text_offset must be 0 for a position-independent image")
    if not (4096 <= image_size <= 16 * 1024 * 1024):
        errs.append("image_size out of range")
    if image_size > len(data):
        errs.append("image_size larger than the file")
    if flags & 0xa != 0xa:
        errs.append("flags should be 0xa (LE, 4K pages, place anywhere)")
    if errs:
        for e in errs:
            print("  FAIL %s" % e)
        sys.exit("bad Image header")
    print("  OK: valid arm64 Image header")


def pack_v4(args, kernel, ramdisk):
    hdr = bytearray(V4_HDR_SIZE)
    hdr[0:8] = b"ANDROID!"
    struct.pack_into("<I", hdr, 8, len(kernel))
    struct.pack_into("<I", hdr, 12, len(ramdisk))
    struct.pack_into("<I", hdr, 16, args.os_version)
    struct.pack_into("<I", hdr, 20, V4_HDR_SIZE)
    struct.pack_into("<I", hdr, 40, 4)
    cmd = args.cmdline.encode()[:1536]
    hdr[44:44 + len(cmd)] = cmd
    struct.pack_into("<I", hdr, 1580, 0)	# signature_size

    out = bytearray()
    out += hdr
    out += b"\x00" * (align(len(out), PAGE) - len(out))
    kernel_off = len(out)
    out += kernel
    out += b"\x00" * (align(len(out), PAGE) - len(out))
    ramdisk_off = len(out)
    out += ramdisk
    out += b"\x00" * (align(len(out), PAGE) - len(out))
    return bytes(out), kernel_off, ramdisk_off


def pack_v2(args, kernel, ramdisk, dtb):
    hdr = bytearray(V2_HDR_SIZE)
    hdr[0:8] = b"ANDROID!"
    off = 8
    for v in (len(kernel), args.kernel_addr, len(ramdisk), args.ramdisk_addr,
              0, 0, args.tags_addr, PAGE, 2, args.os_version):
        struct.pack_into("<I", hdr, off, v)
        off += 4
    name = b"senna-shim"
    hdr[off:off + len(name)] = name
    off += 16
    cmd = args.cmdline.encode()[:512]
    hdr[off:off + len(cmd)] = cmd
    off += 512 + 32		# cmdline + id[8]
    off += 1024		# extra_cmdline
    struct.pack_into("<I", hdr, off, len(dtb))
    struct.pack_into("<Q", hdr, off + 4, args.dtb_addr)

    out = bytearray()
    out += hdr
    out += b"\x00" * (PAGE - len(out))
    kernel_off = len(out)
    out += kernel
    out += b"\x00" * (align(len(out), PAGE) - len(out))
    ramdisk_off = len(out)
    out += ramdisk
    out += b"\x00" * (align(len(out), PAGE) - len(out))
    dtb_off = len(out)
    out += dtb
    out += b"\x00" * (align(len(out), PAGE) - len(out))
    return bytes(out), kernel_off, ramdisk_off, dtb_off


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--check-image")
    ap.add_argument("--pad-image")
    ap.add_argument("--version", type=int, choices=(2, 4))
    ap.add_argument("--kernel")
    ap.add_argument("--ramdisk", default=None)
    ap.add_argument("--dtb", default=None, help="v2 only; embedded device tree")
    ap.add_argument("--output")
    ap.add_argument("--cmdline", default="console=null")
    ap.add_argument("--os-version", type=lambda s: int(s, 0), default=0)
    ap.add_argument("--kernel-addr", type=lambda s: int(s, 0), default=0x8000)
    ap.add_argument("--ramdisk-addr", type=lambda s: int(s, 0), default=0x1000000)
    ap.add_argument("--tags-addr", type=lambda s: int(s, 0), default=0x100)
    ap.add_argument("--dtb-addr", type=lambda s: int(s, 0), default=0x1f00000)
    args = ap.parse_args()

    if args.pad_image:
        pad_image(args.pad_image)
        return
    if args.check_image:
        check_image(args.check_image)
        return
    if not (args.version and args.kernel and args.output):
        ap.error("--version, --kernel and --output are required")

    kernel = open(args.kernel, "rb").read()
    ramdisk = open(args.ramdisk, "rb").read() if args.ramdisk else b""
    dtb = open(args.dtb, "rb").read() if args.dtb else b""
    if args.dtb and args.version != 2:
        sys.exit("--dtb is only supported for a v2 header (v4 keeps the DTB in vendor_boot)")

    if args.version == 4:
        data, koff, roff = pack_v4(args, kernel, ramdisk)
        doff = 0
    else:
        data, koff, roff, doff = pack_v2(args, kernel, ramdisk, dtb)

    with open(args.output, "wb") as f:
        f.write(data)

    print("  output           %s (%d bytes)" % (args.output, len(data)))
    print("  header_version   %d" % args.version)
    print("  kernel           %d bytes @ file 0x%x" % (len(kernel), koff))
    print("  ramdisk          %d bytes @ file 0x%x" % (len(ramdisk), roff))
    if args.version == 2:
        print("  dtb              %d bytes @ file 0x%x" % (len(dtb), doff))
        print("  load addr        kernel 0x%x ramdisk 0x%x tags 0x%x"
              % (args.kernel_addr, args.ramdisk_addr, args.tags_addr))
    print("  os_version       0x%08x" % args.os_version)
    print("  cmdline          %r" % args.cmdline)


if __name__ == "__main__":
    main()
