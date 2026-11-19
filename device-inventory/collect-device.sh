#!/system/bin/sh
# Read-only inventory. No phone files are created or modified.
echo '=== COLLECTION META ==='
date
id
uname -a
echo '=== GETPROP FULL ==='
getprop
echo '=== REQUESTED IDENTITY / VERSION / BOOT STATE ==='
for key in ro.product.model ro.product.device ro.product.name ro.product.brand ro.product.manufacturer ro.product.board ro.product.hardware ro.product.vendor.model ro.product.vendor.device ro.product.bootimage.model ro.product.bootimage.device ro.build.fingerprint ro.vendor.build.fingerprint ro.build.display.id ro.build.version.release ro.build.version.sdk ro.build.version.security_patch ro.build.version.full ro.oplus.version ro.build.version.ota ro.boot.slot_suffix ro.boot.slot ro.boot.verifiedbootstate ro.boot.vbmeta.device_state ro.boot.flash.locked ro.boot.veritymode ro.boot.hypervisor.state ro.boot.bootloader ro.boot.baseband ro.boot.project_name ro.boot.prjname ro.boot.operator ro.boot.carrier; do printf '%s=[' "$key"; getprop "$key"; echo ']'; done
echo '=== KERNEL / CMDLINE / MEMORY ==='
cat /proc/version
cat /proc/cmdline
cat /proc/iomem
cat /proc/meminfo
echo '=== PARTITION BY-NAME SIZES ==='
for base in /dev/block/by-name /dev/block/platform/*/by-name; do
  [ -d "$base" ] || continue
  for n in "$base"/*; do
    [ -e "$n" ] || [ -L "$n" ] || continue
    dev=$(readlink -f "$n")
    [ -b "$dev" ] || continue
    size=$(blockdev --getsize64 "$dev" 2>/dev/null)
    if [ -z "$size" ]; then sectors=$(cat "/sys/class/block/${dev##*/}/size" 2>/dev/null); [ -n "$sectors" ] && size=$((sectors * 512)); fi
    printf '%s\t%s\t%s\t%s\n' "${n##*/}" "$dev" "$size" "$n"
  done
done | sort -u
echo '=== PROC PARTITIONS ==='
cat /proc/partitions
echo '=== BLOCK SYSFS ==='
ls -l /dev/block
ls -l /sys/class/block
echo '=== DT ROOT IDENTITY ==='
for f in model compatible serial-number qcom,msm-id qcom,board-id; do if [ -f "/proc/device-tree/$f" ]; then echo "--- /proc/device-tree/$f"; od -An -tx1 -v "/proc/device-tree/$f"; fi; done
echo '=== DT TARGET NODE PATHS ==='
find /proc/device-tree -type d \( -iname '*spmi*' -o -iname '*pmic*' -o -iname '*pm[0-9]*' -o -iname '*synaptics*' -o -iname '*s3910*' -o -iname '*nt37705*' -o -iname '*ufshc*' -o -iname '*wlan*' -o -iname '*wifi*' -o -iname '*bluetooth*' -o -iname '*wcn*' \) -print
echo '=== DT TARGET NODE COMPATIBLE / REG / STATUS ==='
find /proc/device-tree -type d \( -iname '*spmi*' -o -iname '*pmic*' -o -iname '*pm[0-9]*' -o -iname '*synaptics*' -o -iname '*s3910*' -o -iname '*nt37705*' -o -iname '*ufshc*' -o -iname '*wlan*' -o -iname '*wifi*' -o -iname '*bluetooth*' -o -iname '*wcn*' \) -print | while read d; do
  echo "--- $d"
  for f in compatible reg reg-names status label; do if [ -f "$d/$f" ]; then echo "[$f]"; if [ "$f" = compatible ] || [ "$f" = status ] || [ "$f" = label ] || [ "$f" = reg-names ]; then cat "$d/$f"; echo; else od -An -tx1 -v "$d/$f"; fi; fi; done
done
echo '=== RESERVED MEMORY REGISTERS ==='
if [ -d /proc/device-tree/reserved-memory ]; then
  for d in /proc/device-tree/reserved-memory/*; do
    [ -d "$d" ] || continue
    echo "--- $d"
    for f in compatible label reg size alignment alloc-ranges; do if [ -f "$d/$f" ]; then echo "[$f]"; if [ "$f" = compatible ] || [ "$f" = label ]; then cat "$d/$f"; echo; else od -An -tx1 -v "$d/$f"; fi; fi; done
    [ ! -f "$d/no-map" ] || echo '[no-map present]'
    [ ! -f "$d/reusable" ] || echo '[reusable present]'
  done
fi
echo '=== UFS SCSI IDENTITY ==='
for d in /sys/class/scsi_device/*/device /sys/block/sd*/device; do
  [ -d "$d" ] || continue
  echo "--- $d"
  for f in vendor model rev type state; do [ ! -r "$d/$f" ] || { printf '%s=' "$f"; cat "$d/$f"; }; done
done
echo '=== UFS SYSFS PATH INVENTORY ==='
for d in /sys/bus/platform/devices/*ufs* /sys/devices/platform/soc/*ufs*; do [ -d "$d" ] || continue; echo "--- $d"; find "$d" -maxdepth 4 -type f -o -type l; done
echo '=== PCI / SDIO IDENTITY ==='
for d in /sys/bus/pci/devices/*; do [ -d "$d" ] || continue; echo "--- $d"; for f in vendor device subsystem_vendor subsystem_device class modalias; do [ ! -r "$d/$f" ] || { printf '%s=' "$f"; cat "$d/$f"; }; done; done
for d in /sys/bus/sdio/devices/*; do [ -d "$d" ] || continue; echo "--- $d"; for f in vendor device class modalias; do [ ! -r "$d/$f" ] || { printf '%s=' "$f"; cat "$d/$f"; }; done; done
echo '=== WIFI / BT SYSFS ==='
ls -l /sys/class/net
ls -l /sys/class/bluetooth
for d in /sys/class/net/wlan*; do [ -d "$d" ] || continue; echo "--- $d"; cat "$d/address"; cat "$d/uevent"; done
echo '=== INPUT DEVICES ==='
cat /proc/bus/input/devices
echo '=== DMESG FULL ==='
dmesg
echo '=== COLLECTION COMPLETE ==='