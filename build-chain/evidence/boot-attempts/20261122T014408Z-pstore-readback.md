# pstore / kcore readback 20261122T014408Z

- serial: 78ad6b26
- 生成时间（UTC）：20261122T014408Z

### 设备状态
- ro.build.display.id = RMX3706_13.1.0.115(CN01)
- ro.boot.slot_suffix = _b
- ro.boot.verifiedbootstate = orange
- ro.boot.flash.locked = 0
- sys.boot_completed = 1
- sys.boot.reason = bootloader
- uptime = 00:38:26 up 27 min,  0 users,  load average: 4.59, 4.63, 3.95

### 当前 boot 的 ramoops 行
```
(空)
```
### pstore（设备侧 pstore-dump.sh）

```
===== MISSING /sys/fs/pstore/console-ramoops-0
===== MISSING /sys/fs/pstore/console-ramoops
===== MISSING /sys/fs/pstore/dmesg-ramoops-0
===== MISSING /data/debugging/last_kmsg.txt
total 0
dr-xr-x---  2 system log  0 1970-01-29 08:47 .
drwxr-xr-x 10 root   root 0 1970-01-01 08:00 ..
DONE
```
### /proc/kcore 直读物理 0xa7a5c0000

dump header: dd done
（拉取 kcore 头失败：/proc/kcore 可能不可读或被 SELinux 拦）

### 结论
- pstore/kcore 命中 SENNA SHIM：**否**
