#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""pstore_after_reboot.py - 重启后等 adb 回来，抓 pstore 判定 ramoops 是否持久。

背景：设备的 adbd 在重启后要等屏幕解锁才枚举，所以这里按秒轮询，直到设备回来
（或超时）。设备回来后：读 pstore 列表 + /sys/module/ramoops/parameters + 上一次启动
的 console-ramoops 前 4 KiB，写证据到 build-chain/evidence/boot-attempts/。

退出码：0 = pstore 有记录（持久）；1 = 仍为空（区域被清零/重分配）；2 = 等不到设备。
"""
import datetime as dt
import os
import subprocess
import sys
import time

NL = chr(10)
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ADB = "C:/Android/platform-tools/adb.exe"

PROBE = NL.join([
    "#!/system/bin/sh",
    "echo ==uptime==",
    "cat /proc/uptime",
    "echo ==bootreason==",
    "getprop sys.boot.reason",
    "echo ==memaddr==",
    "cat /sys/module/ramoops/parameters/mem_address",
    "cat /sys/module/ramoops/parameters/mem_size",
    "echo ==pstore==",
    "ls -la /sys/fs/pstore",
    "echo ==dump==",
    "for f in /sys/fs/pstore/console-ramoops-0 /sys/fs/pstore/console-ramoops /sys/fs/pstore/dmesg-ramoops-0; do",
    "  if [ -f $f ]; then",
    "    echo --- $f ---",
    "    dd if=$f bs=4096 count=1 2>/dev/null",
    "  fi",
    "done",
    "echo ==dmesg==",
    "dmesg | grep -i -E 'pstore|ramoops' | head -20",
    "echo DONE",
    "",
])


def adb(args, timeout=120):
    return subprocess.run([ADB] + args, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def online():
    out = adb(["devices"], timeout=30).stdout
    return any(l.split()[1] == "device" for l in out.splitlines()[1:] if len(l.split()) >= 2)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 2700
    start = time.time()
    while time.time() - start < limit:
        if online():
            bc = adb(["shell", "getprop sys.boot_completed"], timeout=30).stdout.strip()
            if bc == "1":
                break
        time.sleep(10)
    else:
        print("timeout waiting for device")
        return 2
    time.sleep(20)
    script = os.path.join(REPO, "build-chain", "work", "pstore_after.sh")
    open(script, "w", encoding="utf-8", newline=NL).write(PROBE)
    adb(["push", script, "/data/local/tmp/pstore_after.sh"], timeout=120)
    r = adb(["shell", "su -c 'sh /data/local/tmp/pstore_after.sh'"], timeout=180)
    text = (r.stdout or "") + (r.stderr or "")
    ok = ("console-ramoops-0" in text) or ("--- /sys/fs/pstore" in text)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(REPO, "build-chain", "evidence", "boot-attempts", stamp + "-pstore-after-reboot.md")
    md = ["# 重启后 pstore 判读 " + stamp, "", "```", text.strip(), "```", "",
          "- 结论：%s" % ("pstore 有记录 -> ramoops 跨重启持久" if ok else "pstore 仍为空 -> 区域被清零/重分配"), ""]
    open(path, "w", encoding="utf-8", newline=NL).write(NL.join(md))
    print(text[-3000:])
    print("wrote " + path)
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
