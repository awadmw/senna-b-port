#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""persist_test.py - 用 pmsg 判定 ramoops 保留区跨重启是否持久。

为什么用 pmsg：shim 是裸机写内存，看不出「写没写进去」；而 /dev/pmsg0 是内核驱动
用 noncached 映射写的，一定能落 DRAM。所以：给 /dev/pmsg0 写一条带标记的消息 ->
正常重启 -> 若 /sys/fs/pstore 出现 pmsg-ramoops-0 且含该标记，说明区域跨重启持久
（那 shim 的问题在写路径）；若仍为空，说明这块保留区每次启动都被重新分配/清零，
ramoops 作为 shim->Android 的通道不可用，必须换通道。

用法：python persist_test.py [等待秒数，默认 3600]
退出码：0 持久（pstore 有文件）；1 不持久（仍为空）；2 等不到设备。
"""
import datetime as dt
import os
import subprocess
import sys
import time

NL = chr(10)
REPO = os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", ".."))
ADB = "C:/Android/platform-tools/adb.exe"
MARKER = "SENNA-PMSG-PERSIST-" + dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")

DO_WRITE = NL.join([
    "#!/system/bin/sh",
    "echo ==uptime==",
    "cat /proc/uptime",
    "echo ==pstore-before==",
    "ls -la /sys/fs/pstore",
    "echo ==pmsg-node==",
    "ls -l /dev/pmsg0",
    "echo ==write==",
    "echo '" + MARKER + "' > /dev/pmsg0 && echo write_ok || echo write_fail",
    "sync",
    "echo DONE",
    "",
])

DO_READ = NL.join([
    "#!/system/bin/sh",
    "echo ==uptime==",
    "cat /proc/uptime",
    "echo ==bootreason==",
    "getprop sys.boot.reason",
    "echo ==pstore==",
    "ls -la /sys/fs/pstore",
    "echo ==dump-all==",
    "for f in /sys/fs/pstore/*; do",
    "  if [ -f $f ]; then",
    "    echo --- $f ---",
    "    dd if=$f bs=4096 count=1 2>/dev/null",
    "  fi",
    "done",
    "echo ==marker-grep==",
    "grep -l '" + MARKER + "' /sys/fs/pstore/* 2>/dev/null",
    "echo ==dropbox-grep==",
    "grep -l '" + MARKER + "' /data/system/dropbox/* 2>/dev/null | head -5",
    "echo ==dmesg==",
    "dmesg | grep -i -E 'pstore|ramoops|pmsg' | head -20",
    "echo DONE",
    "",
])


def adb(args, timeout=120):
    return subprocess.run([ADB] + args, capture_output=True, text=True, timeout=timeout,
                          encoding="utf-8", errors="replace")


def run_device(name, body):
    path = os.path.join(REPO, "build-chain", "work", name)
    open(path, "w", encoding="utf-8", newline=NL).write(body)
    adb(["push", path, "/data/local/tmp/" + name], timeout=120)
    r = adb(["shell", "su -c 'sh /data/local/tmp/" + name + "'"], timeout=180)
    return (r.stdout or "") + (r.stderr or "")


def online():
    out = adb(["devices"], timeout=30).stdout
    return any(l.split()[1] == "device" for l in out.splitlines()[1:] if len(l.split()) >= 2)


def main():
    limit = int(sys.argv[1]) if len(sys.argv) > 1 else 3600
    print("marker: " + MARKER)
    before = run_device("pmsg_write.sh", DO_WRITE)
    print(before.strip())
    if "write_ok" not in before:
        print("pmsg write failed")
        return 3
    adb(["reboot"], timeout=60)
    print("rebooted at " + dt.datetime.now().isoformat(timespec="seconds"))
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
    after = run_device("pmsg_read.sh", DO_READ)
    print(after.strip())
    persisted = ("pmsg-ramoops-0" in after) or ("console-ramoops" in after) or (MARKER in after)
    stamp = dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = os.path.join(REPO, "build-chain", "evidence", "boot-attempts", stamp + "-pmsg-persist.md")
    md = ["# pmsg 持久性测试 " + stamp, "", "- marker: `" + MARKER + "`", "", "## 重启前", "```",
          before.strip(), "```", "", "## 重启后", "```", after.strip(), "```", "",
          "- 结论：%s" % ("ramoops 跨重启持久（shim 写入路径要查）" if persisted
                          else "ramoops 不持久（保留区每次启动被清零/重分配，通道不可用）"), ""]
    open(path, "w", encoding="utf-8", newline=NL).write(NL.join(md))
    print("wrote " + path)
    return 0 if persisted else 1


if __name__ == "__main__":
    sys.exit(main())
