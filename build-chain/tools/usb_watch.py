#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""D0 观测器：判断 fastboot boot 之后 ABL 是否把 USB 留在已枚举状态。

背景见 build-chain/boot-chain/USB-CONSOLE.md §4/§6（U1、D0）。
本脚本只读主机侧状态，不发送任何 fastboot 命令去改变设备，也不碰设备端内存。

用法 A（**D0 推荐**，全程不碰 fastboot 协议，只看 Windows PnP 枚举）：
    python build-chain/tools/usb_watch.py --pnp-only --duration 150 --out build-chain/evidence/boot-attempts/d0-usb-watch.csv

用法 B（旧模式，会用 fastboot devices/getvar 轮询）：
    python build-chain/tools/usb_watch.py --duration 120 --out build-chain/evidence/boot-attempts/d0-usb-watch.csv

**警告（2026-11-22 实测）**：绝对不要在 `fastboot boot` 传输期间用模式 B 轮询。
fastboot 传输与 `fastboot devices`/`getvar` 并发会写坏 ABL 的 fastboot 栈，
之后所有命令都是 `AdbWriteEndpointSync failed: 信号灯超时时间已到 (121)`，
设备只能长按电源键重启恢复。D0 一律用 --pnp-only。

判读（脚本结束时会打印）：
    A 设备在场但 fastboot 不应答 -> ABL 留下的 gadget 还在总线上（走路径 A 继承）
    B 设备消失                  -> ABL 已拆 USB（走路径 B 重建）
    C 设备在场且 fastboot 应答   -> ABL 还没跳转（不可能，需重测）
"""

import argparse
import csv
import datetime as dt
import os
import shutil
import subprocess
import sys
import time

WIN_FASTBOOT = r"C:\Android\platform-tools\fastboot.exe"


def find_fastboot(explicit=None):
    if explicit:
        return explicit
    if os.path.exists(WIN_FASTBOOT):
        return WIN_FASTBOOT
    found = shutil.which("fastboot")
    return found or "fastboot"


def run(cmd, timeout):
    """跑一条命令，返回 (exit_code, stdout+stderr 文本, 是否超时)。"""
    try:
        p = subprocess.run(cmd, capture_output=True, timeout=timeout)
        out = (p.stdout or b"").decode("utf-8", "replace") + (p.stderr or b"").decode("utf-8", "replace")
        return p.returncode, out.strip(), False
    except subprocess.TimeoutExpired:
        return None, "", True
    except FileNotFoundError:
        return 127, "command not found: " + cmd[0], False


def pnp_snapshot():
    """Windows 上抓一份 VID_18D1 / 05C6 相关的 PnP 设备快照；其它平台返回空串。

    注意：senna 的 bootloader 枚举成 VID_18D1&PID_D00D（"Android Bootloader
    Interface"），不是老机型常见的 4EE0；Get-PnpDevice 有时看不到它（类不在
    USB 下），所以这里用 Win32_PnPEntity，实测可靠。
    """
    if os.name != "nt":
        return ""
    ps = (
        "Get-CimInstance Win32_PnPEntity -ErrorAction SilentlyContinue | "
        "Where-Object { $_.DeviceID -match 'VID_18D1|VID_05C6' } | "
        "ForEach-Object { $_.Status + '|' + $_.Name + '|' + $_.DeviceID }"
    )
    rc, out, _ = run(["powershell", "-NoProfile", "-Command", ps], timeout=20)
    return out.replace("\r", "").replace("\n", " ; ")


def main():
    ap = argparse.ArgumentParser(description="D0: watch USB/fastboot presence during shim run")
    ap.add_argument("--duration", type=int, default=120, help="观测秒数（默认 120）")
    ap.add_argument("--interval", type=float, default=1.0, help="轮询间隔秒（默认 1.0）")
    ap.add_argument("--out", default="", help="CSV 输出路径；留空则只打印")
    ap.add_argument("--fastboot", default=None, help="fastboot 可执行文件路径")
    ap.add_argument("--no-getvar", dest="getvar", action="store_false", help="设备在场时不要发 getvar 探测")
    ap.add_argument("--pnp-only", dest="pnp_only", action="store_true",
                    help="完全不用 fastboot 协议，只按 Windows PnP 枚举判在场（D0 必须用这个）")
    args = ap.parse_args()

    fb = find_fastboot(args.fastboot)
    rows = []
    seen_present = 0
    seen_answered = 0
    seen_android = 0
    t0 = time.time()
    print("fastboot =", fb)
    print("duration =", args.duration, "s, interval =", args.interval, "s")
    try:
        while time.time() - t0 < args.duration:
            ts = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
            if args.pnp_only:
                snap = pnp_snapshot()
                low = snap.lower()
                fb_dev = ("vid_18d1&pid_d00d" in low) or ("vid_18d1&pid_4ee0" in low)
                mtp_dev = "vid_18d1&pid_4ee8" in low or "vid_18d1&pid_4ee7" in low
                row = {
                    "utc": ts,
                    "elapsed_s": round(time.time() - t0, 1),
                    "pnp_4ee0_fastboot": fb_dev,
                    "pnp_android": mtp_dev,
                    "pnp": snap[:300],
                }
                if fb_dev:
                    seen_present += 1
                if mtp_dev:
                    seen_android += 1
                rows.append(row)
                print("{utc} fastboot_gadget={pnp_4ee0_fastboot} android={pnp_android}".format(**row))
                time.sleep(args.interval)
                continue
            rc, devs, to = run([fb, "devices"], timeout=8)
            ids = [ln.split()[0] for ln in devs.splitlines() if ln.strip() and "fastboot" in ln]
            present = len(ids) > 0
            answered, gv_rc, gv = False, None, ""
            if present and args.getvar:
                gv_rc, gv, gv_to = run([fb, "getvar", "product"], timeout=6)
                answered = (gv_rc == 0) and ("product:" in gv)
                if gv_to:
                    gv = "TIMEOUT"
            if present:
                seen_present += 1
            if answered:
                seen_answered += 1
            row = {
                "utc": ts,
                "elapsed_s": round(time.time() - t0, 1),
                "fastboot_rc": "" if rc is None else rc,
                "fastboot_timeout": to,
                "device_count": len(ids),
                "device_ids": " ".join(ids),
                "getvar_rc": "" if gv_rc is None else gv_rc,
                "getvar_answered": answered,
                "getvar_text": gv.replace("\n", " | ")[:200],
                "pnp": "" if not present else "",
            }
            if present and len(rows) % 10 == 0:
                row["pnp"] = pnp_snapshot()[:400]
            rows.append(row)
            print("{utc} dev={device_count} [{device_ids}] answered={getvar_answered} {getvar_text}".format(**row))
            time.sleep(args.interval)
    except KeyboardInterrupt:
        print("\n[interrupted]")

    if args.out:
        os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
        with open(args.out, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()) if rows else ["utc"])
            w.writeheader()
            w.writerows(rows)
        print("csv ->", os.path.abspath(args.out))

    total = len(rows)
    if total == 0:
        print("VERDICT: no samples")
        return 2
    if args.pnp_only:
        print("pnp-only: fastboot gadget seen %d/%d, android seen %d/%d" % (seen_present, total, seen_android, total))
        if seen_present == 0:
            print("VERDICT B: fastboot gadget never enumerated -> ABL tore USB down, go path B")
            return 1
        if seen_android == 0 and seen_present == total:
            print("VERDICT A: fastboot gadget stayed enumerated for all samples -> ABL gadget alive, go path A")
            return 0
        print("VERDICT MIXED: see CSV (gadget %d/%d, android %d/%d) -> decide by timeline" % (seen_present, total, seen_android, total))
        return 3
    if seen_present == 0:
        print("VERDICT B: no USB device seen at all (%d/%d samples) -> ABL tore USB down, go path B" % (seen_present, total))
        return 1
    if seen_answered == 0:
        print("VERDICT A: device present but fastboot never answers (%d/%d present, 0 answered) -> ABL gadget alive, go path A" % (seen_present, total))
        return 0
    print("VERDICT C: device present and fastboot answered %d/%d -> ABL still running or device back in fastboot, retest" % (seen_answered, total))
    return 3


if __name__ == "__main__":
    sys.exit(main())