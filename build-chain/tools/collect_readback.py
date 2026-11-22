#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""collect_readback.py - 等 adb 回来，然后一次性抓 ramoops/pstore 与物理内存取证。

背景：v0.4/v0.5 的 shim 把探测文本写进 ramoops（0xa7a5c0000+0x240000），但 v0.4
回读时 /sys/fs/pstore 是空的，v0.5 上机后 adbd 干脆没起来。这个脚本做三件事：

  1) 等 adb devices 出现设备（默认 1800 s）；
  2) 跑设备侧 pstore-dump.sh，收集 /sys/fs/pstore、last_kmsg 与 dmesg 的 ramoops 行；
  3) pstore 为空时，从 /proc/kcore 按线性映射 PAGE_OFFSET+phys 直接 dump 0xa7a5c0000，
     在二进制里搜 SENNA SHIM，绕开 pstore 校验回答「到底有没有写进 DRAM」。

结果写 build-chain/evidence/boot-attempts/<UTC>-pstore-readback.md；退出码 0 = 命中，1 = 未命中，2 = 没等到设备。

用法：python build-chain/tools/collect_readback.py --wait 1800 [--serial 78ad6b26]
"""
import argparse
import datetime as dt
import os
import struct
import subprocess
import sys
import time

NL = chr(10)
BS = chr(92)
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
ADB = "C:/Android/platform-tools/adb.exe"
RAMOOPS_BASE = 0x0A7A5C0000
PAGE_OFFSET = 0xFFFF000000000000
DEVICE_PSTORE_SH = os.path.join(REPO, "build-chain", "tools", "pstore-dump.sh")


def adb(args, serial=None, timeout=60):
    cmd = [ADB] + (["-s", serial] if serial else []) + args
    return subprocess.run(cmd, capture_output=True, text=True, timeout=timeout, encoding="utf-8", errors="replace")


def list_devices():
    out = adb(["devices"]).stdout
    found = []
    for line in out.splitlines()[1:]:
        parts = line.split()
        if len(parts) >= 2 and parts[1] == "device":
            found.append(parts[0])
    return found


def wait_for_device(serial, wait_s):
    deadline = time.time() + wait_s
    while time.time() < deadline:
        devs = list_devices()
        if serial and serial in devs:
            return serial
        if not serial and devs:
            return devs[0]
        time.sleep(5)
    return None


def shell(serial, cmd, timeout=120):
    return adb(["shell", cmd], serial=serial, timeout=timeout)


def grab_props(serial):
    keys = ["ro.build.display.id", "ro.boot.slot_suffix", "ro.boot.verifiedbootstate",
            "ro.boot.flash.locked", "sys.boot_completed", "sys.boot.reason"]
    out = []
    for k in keys:
        r = shell(serial, "getprop " + k)
        out.append("%s = %s" % (k, (r.stdout or "").strip()))
    r = shell(serial, "uptime")
    out.append("uptime = %s" % (r.stdout or "").strip())
    return out


def grab_dmesg(serial):
    r = shell(serial, "su -c 'dmesg | grep -i ramoops'")
    return ((r.stdout or "") + (r.stderr or "")).strip()


def grab_pstore(serial):
    md = ["### pstore（设备侧 pstore-dump.sh）", ""]
    if not os.path.exists(DEVICE_PSTORE_SH):
        md.append("（本地缺少 build-chain/tools/pstore-dump.sh）")
        return NL.join(md), ""
    adb(["push", DEVICE_PSTORE_SH, "/data/local/tmp/pstore.sh"], serial=serial, timeout=120)
    r = shell(serial, "su -c 'sh /data/local/tmp/pstore.sh'", timeout=180)
    text = (r.stdout or "") + (r.stderr or "")
    md.append("```")
    md.append(text.strip())
    md.append("```")
    return NL.join(md), text


KDUMP_SH = NL.join([
    "#!/system/bin/sh",
    "# usage: kdump.sh <skip> <count> <out>",
    "dd if=/proc/kcore bs=1 skip=\"$1\" count=\"$2\" of=\"$3\" 2>/dev/null",
    "chmod 644 \"$3\"",
    "echo dd done",
    "ls -l \"$3\"",
    "",
])


def parse_kcore_segments(path):
    blob = open(path, "rb").read()
    if blob[:4] != bytes([0x7F, 0x45, 0x4C, 0x46]):
        return None
    e_phoff = struct.unpack_from("<Q", blob, 0x20)[0]
    e_phentsize = struct.unpack_from("<H", blob, 0x36)[0]
    e_phnum = struct.unpack_from("<H", blob, 0x38)[0]
    segs = []
    for i in range(e_phnum):
        off = e_phoff + i * e_phentsize
        vals = struct.unpack_from("<IIQQQQQ", blob, off)
        p_type, p_offset, p_vaddr, p_filesz = vals[0], vals[2], vals[3], vals[5]
        if p_type == 1 and p_filesz:
            segs.append((p_vaddr, p_filesz, p_offset))
    return segs


def grab_kcore(serial, workdir):
    md = ["### /proc/kcore 直读物理 0xa7a5c0000", ""]
    script = os.path.join(workdir, "kdump.sh")
    open(script, "w", encoding="utf-8", newline=NL).write(KDUMP_SH)
    adb(["push", script, "/data/local/tmp/kdump.sh"], serial=serial, timeout=120)
    r = shell(serial, "su -c 'sh /data/local/tmp/kdump.sh 0 65536 /data/local/tmp/kc.hdr'")
    md.append("dump header: " + ((r.stdout or "").strip() or "(no output)"))
    hdr_local = os.path.join(workdir, "kc.hdr")
    adb(["pull", "/data/local/tmp/kc.hdr", hdr_local], serial=serial, timeout=120)
    if not os.path.exists(hdr_local):
        md.append("（拉取 kcore 头失败：/proc/kcore 可能不可读或被 SELinux 拦）")
        return NL.join(md), False
    segs = parse_kcore_segments(hdr_local)
    if not segs:
        md.append("（不是 ELF64，无法解析段表）")
        return NL.join(md), False
    md.append("段表：")
    md.append("```")
    for vaddr, filesz, offset in segs:
        md.append("vaddr=%#x size=%#x off=%#x" % (vaddr, filesz, offset))
    md.append("```")
    target = PAGE_OFFSET + RAMOOPS_BASE
    hit = None
    for vaddr, filesz, offset in segs:
        if vaddr <= target < vaddr + filesz:
            hit = offset + (target - vaddr)
            break
    if hit is None:
        md.append("（物理 %#x 不在任何 PT_LOAD 段内）" % RAMOOPS_BASE)
        return NL.join(md), False
    cmd = "su -c 'sh /data/local/tmp/kdump.sh %d 65536 /data/local/tmp/ramoops.bin'" % hit
    r = shell(serial, cmd)
    md.append("dump ramoops: " + ((r.stdout or "").strip() or "(no output)"))
    dump_local = os.path.join(workdir, "ramoops.bin")
    adb(["pull", "/data/local/tmp/ramoops.bin", dump_local], serial=serial, timeout=120)
    if not os.path.exists(dump_local):
        md.append("（拉取 ramoops 失败）")
        return NL.join(md), False
    blob = open(dump_local, "rb").read()
    ok = b"SENNA SHIM" in blob
    md.append("dump 大小 %d；含 SENNA SHIM：%s" % (len(blob), ok))
    idx = blob.find(b"SENNA SHIM")
    if idx >= 0:
        snippet = blob[idx:idx + 700].split(bytes([0]))[0]
        md.append("```")
        md.append(snippet.decode("ascii", "replace"))
        md.append("```")
    return NL.join(md), ok


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--wait", type=int, default=1800)
    ap.add_argument("--serial", default="")
    args = ap.parse_args()

    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    outdir = os.path.join(REPO, "build-chain", "evidence", "boot-attempts")
    os.makedirs(outdir, exist_ok=True)
    workdir = os.path.join(REPO, "build-chain", "work", "readback")
    os.makedirs(workdir, exist_ok=True)

    print("waiting up to %d s for adb..." % args.wait, flush=True)
    serial = wait_for_device(args.serial, args.wait)
    if not serial:
        print("no adb device within %d s" % args.wait)
        return 2
    print("device: " + serial, flush=True)

    parts = ["# pstore / kcore readback " + stamp, "",
             "- serial: " + serial,
             "- 生成时间（UTC）：" + stamp, ""]
    parts.append("### 设备状态")
    for p in grab_props(serial):
        parts.append("- " + p)
    parts.append("")
    parts.append("### 当前 boot 的 ramoops 行")
    parts.append("```")
    parts.append(grab_dmesg(serial) or "(空)")
    parts.append("```")

    pstore_md, pstore_text = grab_pstore(serial)
    parts.append(pstore_md)

    found = "SENNA SHIM" in pstore_text
    if not found:
        kcore_md, found = grab_kcore(serial, workdir)
        parts.append(kcore_md)

    parts.append("")
    parts.append("### 结论")
    parts.append("- pstore/kcore 命中 SENNA SHIM：**%s**" % ("是" if found else "否"))

    path = os.path.join(outdir, stamp + "-pstore-readback.md")
    open(path, "w", encoding="utf-8", newline=NL).write(NL.join(parts) + NL)
    print("wrote %s (found=%s)" % (path, found))
    return 0 if found else 1


if __name__ == "__main__":
    sys.exit(main())
