echo '=== UFS DESCRIPTOR SYSFS ==='
base=/sys/devices/platform/soc/1d84000.ufshc
for d in "$base/device_descriptor" "$base/interconnect_descriptor"; do
  echo "--- $d ---"
  if [ -d "$d" ]; then
    for f in "$d"/*; do
      if [ -f "$f" ]; then echo "### $f"; cat "$f" 2>&1; fi
    done
  else
    echo 'NOT FOUND'
  fi
done
echo '=== UFS HOST/CONTROLLER SYSFS CANDIDATES ==='
for d in /sys/class/ufs_host /sys/class/scsi_host /sys/kernel/debug/ufs /sys/kernel/debug/ufshcd0 "$base"; do
  [ -e "$d" ] || continue
  echo "--- $d ---"
  find "$d" -maxdepth 3 -type f 2>/dev/null | grep -E 'descriptor|device_desc|geometry|version|manufacturer|spec|unipro|mphy|m_phy|gear|lane|host|ufs' | head -200
done
echo '=== UFS KERNEL LOG MATCHES ==='
dmesg | grep -iE 'ufshcd|ufs-|ufs |uni.?pro|m-?phy|MT256|MICRON' | head -800