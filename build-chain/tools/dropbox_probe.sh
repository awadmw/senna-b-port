#!/system/bin/sh
# dropbox_probe.sh - 检查 pstore 是否被 Android 的 BootReceiver/PstoreManager 搬进 dropbox
# 背景：/sys/fs/pstore 为空不代表 ramoops 没写成功——Android 12+ 的 PstoreManager
# 会在启动时把 pstore 记录收进 /data/system/dropbox（SYSTEM_LAST_KMSG 等）并删掉原文件。
echo ==pstore==
ls -la /sys/fs/pstore
echo ==dropbox-list==
ls -la /data/system/dropbox 2>&1 | head -40
echo ==dropbox-count==
ls /data/system/dropbox 2>/dev/null | wc -l
echo ==dropbox-kmsg-files==
ls -la /data/system/dropbox 2>/dev/null | grep -i -E "kmsg|restart|kernel|boot" | head -20
echo ==dropbox-grep-senna==
grep -l -i "SENNA SHIM" /data/system/dropbox/* 2>/dev/null | head -10
echo ==dropbox-grep-ramoops==
grep -l -i "ramoops" /data/system/dropbox/* 2>/dev/null | head -10
echo ==tombstones==
ls -la /data/tombstones 2>&1 | head -10
echo ==logcat-senna==
logcat -b all -d 2>/dev/null | grep -i -E "senna shim|ramoops" | head -20
echo ==dmesg-pstore==
dmesg | grep -i -E "pstore|ramoops" | head -20
echo DONE
