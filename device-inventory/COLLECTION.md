# senna-b 只读采集清单

本清单对应 `collect-device.sh` 与 `collect-ufs.sh`。命令只读取 Android 属性、sysfs、procfs、DT 和内核日志；不需要刷写、解锁、清数据或修改分区。实际采集使用 ADB 序列号 `78ad6b26`。

## 0. 连接与 root 检查

```sh
adb devices -l
adb -s 78ad6b26 shell id
adb -s 78ad6b26 shell su -c id
adb -s 78ad6b26 shell uname -a
```

只有 `su -c id` 返回 `uid=0` 才继续 root 部分。不要把本机已解锁状态当成其他设备的既定状态。

## 1. 型号、系统版本和 BL 状态

```sh
adb -s 78ad6b26 shell 'for p in \
ro.product.model ro.product.device ro.product.name ro.product.brand \
ro.product.manufacturer ro.product.board ro.product.hardware \
ro.build.fingerprint ro.vendor.build.fingerprint ro.build.display.id \
ro.build.version.release ro.build.version.sdk ro.build.version.security_patch \
ro.build.version.ota ro.boot.slot_suffix ro.boot.verifiedbootstate \
ro.boot.vbmeta.device_state ro.boot.flash.locked; do \
printf "%s=[" "$p"; getprop "$p"; echo "]"; done'
adb -s 78ad6b26 shell getprop > getprop.txt
adb -s 78ad6b26 shell su -c 'cat /proc/cmdline; cat /proc/version'
```

这一步不重启设备。fastboot 查询属于另一项会重启的操作，不是获取这些 Android 属性的必要步骤。

## 2. 完整设备树、DTB 与 DTS

手机侧枚举：

```sh
adb -s 78ad6b26 shell su -c 'find /proc/device-tree -type d | sort'
adb -s 78ad6b26 shell su -c 'for f in model compatible qcom,msm-id qcom,board-id; do echo "--- $f"; od -An -tx1 -v "/proc/device-tree/$f"; done'
```

完整归档命令（产生 tar 字节流到 stdout，不写手机文件）：

```sh
adb -s 78ad6b26 exec-out su -c 'tar -cf - -C /proc/device-tree .'
```

当前合并 DTB 的读取命令：

```sh
adb -s 78ad6b26 exec-out su -c 'cat /sys/firmware/fdt'
```

**Windows PowerShell 5.1 不得用 `>` 保存上述二进制输出，否则可能按文本重编码。** 本次使用 .NET `Process.StandardOutput.BaseStream.CopyTo(FileStream)` 保存原始字节。`cmd.exe` 的二进制重定向也应先校验 DTB magic 和哈希再使用。

得到 DTB 后，在安装了 dtc 的 Linux/macOS 环境复核：

```sh
dtc -I dtb -O dts -o senna-live.dts senna-live.dtb
dtc -I dts -O dtb -o /tmp/senna-live-roundtrip.dtb senna-live.dts
sha256sum senna-live.dtb senna-live.dts
```

本机已有实时 DT，所以“官方 OTA payload 提取”不是本次完成 DTS 的必要条件；若后续改用 OTA，必须另行保存 OTA 来源、版本、payload 哈希和镜像提取日志，不能把其他版本 DTB 混入本表。

## 3. by-name 全分区与大小

在 root shell 执行：

```sh
for base in /dev/block/by-name /dev/block/platform/*/by-name; do
  [ -d "$base" ] || continue
  for n in "$base"/*; do
    [ -e "$n" ] || [ -L "$n" ] || continue
    dev=$(readlink -f "$n")
    [ -b "$dev" ] || continue
    size=$(blockdev --getsize64 "$dev" 2>/dev/null)
    if [ -z "$size" ]; then
      sectors=$(cat "/sys/class/block/${dev##*/}/size" 2>/dev/null)
      [ -n "$sectors" ] && size=$((sectors * 512))
    fi
    printf '%s\t%s\t%s\t%s\n' "${n##*/}" "$dev" "$size" "$n"
  done
done | sort -u
```

这里只读取块设备大小，不读取分区内容，更不能对返回的节点使用 `dd of=`。

## 4. DT 中的关键硬件

```sh
adb -s 78ad6b26 shell su -c 'find /proc/device-tree -type d \( \
-iname "*spmi*" -o -iname "*pmic*" -o -iname "*pm[0-9]*" \
-o -iname "*synaptics*" -o -iname "*s3910*" -o -iname "*nt37705*" \
-o -iname "*ufshc*" -o -iname "*wlan*" -o -iname "*wifi*" \
-o -iname "*bluetooth*" -o -iname "*wcn*" \) -print'
```

对输出的每个目录读取 `compatible/reg/reg-names/status/label`。字符串属性用 `cat`，`reg` 等二进制属性用：

```sh
od -An -tx1 -v /proc/device-tree/节点路径/reg
```

`reg` 必须按父节点 `#address-cells/#size-cells` 解码。例如 SPMI PMIC 的第一个 cell 是 USID；触控节点在 SPI 下时，`reg=<0>` 是 chip-select 0，不是 I2C 地址。

reserved-memory 全量：

```sh
adb -s 78ad6b26 shell su -c 'for d in /proc/device-tree/reserved-memory/*; do
  [ -d "$d" ] || continue
  echo "--- $d"
  for f in compatible label reg size alignment alloc-ranges; do
    [ ! -f "$d/$f" ] || { echo "[$f]"; od -An -tx1 -v "$d/$f"; }
  done
  [ ! -f "$d/no-map" ] || echo no-map
  [ ! -f "$d/reusable" ] || echo reusable
done'
```

## 5. UFS、Wi-Fi/BT、触控 sysfs 与内核日志

```sh
adb -s 78ad6b26 shell su -c 'for d in /sys/class/scsi_device/*/device /sys/block/sd*/device; do
  [ -d "$d" ] || continue
  echo "--- $d"
  for f in vendor model rev type state; do [ ! -r "$d/$f" ] || { printf "%s=" "$f"; cat "$d/$f"; }; done
done'

adb -s 78ad6b26 shell su -c 'base=/sys/devices/platform/soc/1d84000.ufshc
for d in "$base/device_descriptor" "$base/interconnect_descriptor"; do
  for f in "$d"/*; do [ ! -f "$f" ] || { echo "### $f"; cat "$f"; }; done
done'

adb -s 78ad6b26 shell su -c 'for d in /sys/bus/pci/devices/*; do
  echo "--- $d"
  for f in vendor device subsystem_vendor subsystem_device class modalias; do
    [ ! -r "$d/$f" ] || { printf "%s=" "$f"; cat "$d/$f"; }
  done
done'

adb -s 78ad6b26 shell su -c 'cat /proc/bus/input/devices; dmesg' > dmesg-and-input.txt
```

UFS `rev` 是产品/固件 revision；规范版本必须读 `specification_version`，UniPro/M-PHY 必须读 interconnect descriptor。内核环形日志可能已丢失早期启动行，缺失时回到 DT 与 sysfs，不得猜测。

## 6. 一键脚本与本次结果

- `collect-device.sh`：属性、分区、DT 目标节点、reserved-memory、UFS SCSI、PCI/SDIO、input 和完整 dmesg。
- `collect-ufs.sh`：UFS device/interconnect descriptor 补采。
- `inventory-shell.txt`、`device-tree.tar`、`senna-live.dtb`：本次原始证据。
- `senna-live.dts`：本地解析器生成的 DTS；标准 dtc 复核仍是待办。
- `partitions.tsv`：132 个唯一 by-name 分区及精确字节数。

所有脚本均只读；实际执行没有重启手机，也没有在手机创建文件。