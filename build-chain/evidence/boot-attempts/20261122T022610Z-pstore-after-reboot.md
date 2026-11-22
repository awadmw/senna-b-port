# 重启后 pstore 判读 20261122T022610Z

```
==uptime==
2408.85 17918.73
==bootreason==
reboot,shell
==memaddr==
45002522624
2359296
==pstore==
total 0
dr-xr-x---  2 system log  0 1970-01-29 09:16 .
drwxr-xr-x 10 root   root 0 1970-01-01 08:00 ..
==dump==
==dmesg==
DONE
```

- 结论：pstore 仍为空 -> 区域被清零/重分配
