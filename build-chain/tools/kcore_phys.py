#!/usr/bin/env python3
"""Locate physical memory inside /proc/kcore.

The kernel exposes physical memory through the linear map, so a physical
address P shows up at virtual address PAGE_OFFSET + P.  /proc/kcore is an
ELF core file whose PT_LOAD segments describe those virtual ranges; this
helper turns "I want phys 0x... " into the dd skip/count the phone has to
run (toybox dd cannot seek by ELF offset on its own).

usage:
  python kcore_phys.py <headers.bin> <phys_addr> [length]

headers.bin is the first 64 KiB of /proc/kcore (dd if=/proc/kcore bs=1024 count=64).
"""
import struct
import sys

PAGE_OFFSET = 0xFFFF000000000000


def segments(blob):
    if blob[:4] != b"\x7fELF":
        raise SystemExit("not an ELF file")
    is64 = blob[4] == 2
    if not is64:
        raise SystemExit("expecting ELF64")
    e_phoff = struct.unpack_from("<Q", blob, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", blob, 0x36)[0]
    e_phnum = struct.unpack_from("<H", blob, 0x38)[0]
    out = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        p_type, p_flags, p_offset, p_vaddr, p_paddr, p_filesz, p_memsz = struct.unpack_from(
            "<IIQQQQQ", blob, off
        )
        if p_type == 1 and p_filesz:
            out.append((p_vaddr, p_filesz, p_offset))
    return out


def main():
    blob = open(sys.argv[1], "rb").read()
    phys = int(sys.argv[2], 0)
    length = int(sys.argv[3], 0) if len(sys.argv) > 3 else 4096
    segs = segments(blob)
    print("PT_LOAD segments:")
    for vaddr, filesz, offset in segs:
        print("  vaddr=%#x size=%#x off=%#x" % (vaddr, filesz, offset))
    target = PAGE_OFFSET + phys
    for vaddr, filesz, offset in segs:
        if vaddr <= target < vaddr + filesz:
            skip = offset + (target - vaddr)
            print("phys %#x -> va %#x fileoff %#x" % (phys, target, skip))
            print("dd if=/proc/kcore bs=1 skip=%d count=%d of=/data/local/tmp/kcore.bin" % (skip, length))
            return
    raise SystemExit("phys %#x not covered by any PT_LOAD" % phys)


if __name__ == "__main__":
    main()
