#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ramoops_persist_test.py - 判定 ramoops 区（0xa7a5c0000+0x240000）跨重启是否持久。

目的：v0.4/v0.5 的 shim 往 ramoops 写了文本，但 /sys/fs/pstore 一直为空。
两种可能：(A) 区域每次启动被重新分配/清零 -> 通道不可用；(B) shim 写入没落盘。
内核自己也在用这个 console 区打日志，所以只要「正常重启一次，pstore 里应出现
console-ramoops-0（内容是上一次启动的内核日志）」。本脚本就是做这个判定：

  1) 记录重启前：pstore 列表、/sys/module/ramoops/parameters/mem_address、uptime；
  2) adb reboot，等设备回来并 sys.boot_completed=1；
  3) 记录重启后同样的信息 + 抓 console-ramoops 的前 4 KiB 文本；
  4) 写证据 build-chain/evidence/boot-attempts/<UTC>-ramoops-persist.md。

退出码：0 = 重启后出现 pstore 记录（通道可用）；1 = 仍为空（区域被清零/重分配）。
"""
import datetime as dt
import os
import subprocess
import sys
import time

NL = chr(10)
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ADB = "C:/Android/platform-tools/adb.exe"

DEV_PROBE = NL.join([
    "#!/system/bin/sh",
    "echo ==uptime==",
    "cat /proc/uptime",
    "echo ==memaddr==",
    "cat /sys/module/ramoops/parameters/mem_address",
    "cat /sys/module/ramoops/parameters/mem_size",
    "echo ==bootreason==",
    "getprop sys.boot.reason",
    "getprop ro.boot.bootreason",
    "echo ==pstore==",
    "ls -la /sys/fs/pstore",
    "echo ==dump==",
    "for f in /sys/fs/pstore/console-ramoops-0 /sys/fs/pstore/console-ramoops /sys/fs/pstore/dmesg-ramoops-0; do",
    "  if [ -f $f ]; then",
    "    echo --- $f ---",
    "    dd if=$f bs=4096 count=1 2>/dev/null",
    "  fi",
    "done",
    "echo DONE",
    "",
])


def adb(args, timeout=120):
    return subprocess.run([ADB] + args, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def device_online():
    out = adb(["devices"], timeout=30).stdout
    return any(l.split()[1] == "device" for l in out.splitlines()[1:] if len(l.split()) >= 2)


def wait_boot(timeout_s=300):
    deadline = time.time() + timeout_s
    while time.time() < deadline:
        if device_online():
            r = adb(["shell", "getprop sys.boot_completed"], timeout=30)
            if (r.stdout or "").strip() == "1":
                return True
        time.sleep(3)
    return False


def probe():
    script = os.path.join(REPO, "build-chain", "work", "ramoops_probe.sh")
    open(script, "w", encoding="utf-8", newline=NL).write(DEV_PROBE)
    adb(["push", script, "/data/local/tmp/ramoops_probe.sh"], timeout=120)
    r = adb(["shell", "su -c 'sh /data/local/tmp/ramoops_probe.sh'"], timeout=180)
    return (r.stdout or "") + (r.stderr or "")


def main():
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    before = probe()
    print("=== before ===")
    print(before[-1200:])
    adb(["reboot"], timeout=60)
    print("rebooted, waiting...")
    time.sleep(10)
    if not wait_boot(300):
        print("device did not come back / boot_completed within 300 s")
        return 3
    time.sleep(15)
    after = probe()
    print("=== after ===")
    print(after[-2500:])
    persisted = "console-ramoops-0" in after or "console-ramoops" in after or "dmesg-ramoops-0" in after
    outdir = os.path.join(REPO, "build-chain", "evidence", "boot-attempts")
    path = os.path.join(outdir, stamp + "-ramoops-persist.md")
    md = [
        "# ramoops 持久性测试 " + stamp,
        "",
        "目的：判定 ramoops 区在正常重启后是否还能读到上一次启动的 console 记录。",
        "",
        "## 重启前",
        "```",
        before.strip(),
        "```",
        "",
        "## 重启后",
        "```",
        after.strip(),
        "```",
        "",
        "## 结论",
        "- 重启后 pstore 出现记录：**%s**" % ("是" if persisted else "否"),
        "",
    ]
    open(path, "w", encoding="utf-8", newline=NL).write(NL.join(md) + NL)
    print("wrote " + path)
    return 0 if persisted else 1


if __name__ == "__main__":
    sys.exit(main())
