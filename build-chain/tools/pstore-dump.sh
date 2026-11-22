#!/system/bin/sh
for f in /sys/fs/pstore/console-ramoops-0 /sys/fs/pstore/console-ramoops /sys/fs/pstore/dmesg-ramoops-0 /data/debugging/last_kmsg.txt; do
  if [ -e "$f" ]; then
    echo "===== $f"
    ls -l "$f"
    cat "$f"
    echo "===== end $f"
  else
    echo "===== MISSING $f"
  fi
done
ls -la /sys/fs/pstore 2>&1
echo DONE
