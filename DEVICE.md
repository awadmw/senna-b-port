# senna 移植参数表（DEVICE.md）

> 状态：移植前只读信息采集完成；本文不包含移植代码，也不代表已具备可启动的 UEFI/XNU。
> 采集设备：ADB `78ad6b26`；全程未重启、未解锁、未清数据、未刷写、未在手机创建或修改文件。

## 1. 证据范围与结论边界

- 当前合并 DTB：[`device-inventory/senna-live.dtb`](<device-inventory/senna-live.dtb>)，1118143 字节，SHA-256 `7A290B13563A058464FA01287FA801687B76E55A85A80867DDA76AAC73743094`。
- 完整 `/proc/device-tree`：[`device-inventory/device-tree.tar`](<device-inventory/device-tree.tar>)，35,696 个 tar 成员；已完整展开 31,221 个文件和 4,475 个目录，零错误，见 [`device-tree-extraction.json`](<device-inventory/device-tree-extraction.json>)。
- DTS 文本：[`device-inventory/senna-live.dts`](<device-inventory/senna-live.dts>)。由本地 FDT 解析器生成，尚未用 `dtc` 二次编译验证。
- 本机已有实时 DT，因此本次没有从官方 OTA `payload.bin` 重复提取；匹配全量 OTA 仍未提供。
- 当前 DT 与阶段0 DT 只有 `/hypervisor` 下动态 resource-manager-rpc 节点一增一删，硬件属性无差异；见 [`dt-generation-diff.json`](<device-inventory/dt-generation-diff.json>)。
- `dmesg` 环形缓冲只保留约 189 秒以后，早期启动日志已被 Wi-Fi 日志冲刷；硬件结论以 DT、sysfs 和尚存日志交叉确认，不拿缺失日志补猜。

## 2. 准确型号、系统与启动状态

| 项目 | 实测值 | 来源 |
|---|---|---|
| 销售型号 | `RMX3706` | `getprop ro.product.model` |
| Android 设备代号 | `RE5860` | `getprop ro.product.device` |
| 产品名 | `RMX3706` | `getprop ro.product.name` |
| 品牌 | `realme` | `getprop ro.product.brand` |
| 制造商 | `realme` | `getprop ro.product.manufacturer` |
| 主板属性 | `taro` | `getprop ro.product.board` |
| 硬件属性 | `（空）` | `getprop ro.product.hardware` |
| Android 版本 | `13` | `getprop ro.build.version.release` |
| SDK | `33` | `getprop ro.build.version.sdk` |
| 系统显示版本 | `RMX3706_13.1.0.115(CN01)` | `getprop ro.build.display.id` |
| OTA 版本 | `RMX3706_11.A.45_0450_202308171956` | `getprop ro.build.version.ota` |
| 安全补丁 | `2023-07-05` | `getprop ro.build.version.security_patch` |
| 当前槽位 | `_b` | `getprop ro.boot.slot_suffix` |
| AVB 设备状态 | `unlocked` | `getprop ro.boot.vbmeta.device_state` |
| verifiedbootstate | `orange` | `getprop ro.boot.verifiedbootstate` |
| flash.locked | `0` | `getprop ro.boot.flash.locked` |
| DT 整机标识 | `Qualcomm Technologies, Inc. Cape MTP, Senna B` | 当前 DT `/model` |
| 项目号 | `22624` | 当前 `/chosen/bootargs` 的 `oplusboot.prjname` |
| Build fingerprint | `realme/RMX3706/RE5860:13/SKQ1.221119.001/T.12aa1e6-252_210:user/release-keys` | `getprop ro.build.fingerprint` |

**命名规则：** `RMX3706` 是销售型号，`RE5860` 是 Android `ro.product.device`，`senna-b` 是 DT/启动参数对应的平台代号；三者不能互相替换。`unlocked/orange/flash.locked=0` 是当前 Android 侧证据；阶段0 的部分 fastboot getvar 不受 bootloader 支持，不能补写成 fastboot 已返回这些值。

## 3. SoC、内存与核心控制器

- `qcom,msm-id`：`[531, 65536, 540, 65536, 530, 65536]`；`qcom,board-id`：`[65544, 0]`。
- CPU：8 个节点；`enable-method=psci`。PSCI：`{'compatible': ['arm,psci-1.0'], 'method': ['smc']}`。
- 内存五段合计 `12,655,263,744` 字节；可用内存必须继续扣除后文 55 项 reserved-memory。

| 项目 | 当前 DT 参数 |
|---|---|
| `/memory` | `0x0000000080000000 + 0x6a000000`<br>`0x00000000f1400000 + 0xec00000`<br>`0x0000000800000000 + 0x39900000`<br>`0x0000000900000000 + 0x180000000`<br>`0x0000000840000000 + 0xc0000000` |
| GICv3 | `/soc/interrupt-controller@17100000`；GICD `0x17100000+0x10000`；GICR `0x17180000+0x200000`；`#interrupt-cells=3` |
| GIC ITS | `/soc/interrupt-controller@17100000/msi-controller@17140000`；`0x0000000017140000 + 0x20000` |
| PDC | `/soc/interrupt-controller@b220000`；`0x000000000b220000 + 0x30000`<br>`0x00000000174000f0 + 0x64`；names=['pdc-interrupt-base', 'apss-shared-spi-cfg'] |
| MMIO timer | `/soc/timer@17420000`；`clock-frequency=19200000` Hz；该值不能直接当作 arch timer 的 CNTFRQ |
| UART console | `/soc/qcom,qup_uart@99c000`；`0x000000000099c000 + 0x4000`；`interrupts=[0, 608, 4]`；`console=ttyMSM0,115200n8` |

## 4. PMIC 与 SPMI

主控制器 `/soc/qcom,spmi@c42d000`，`compatible=qcom,spmi-pmic-arb`，`#address-cells=2`、`#size-cells=0`。第二控制器 `/soc/qcom,spmi@c432000` 在当前合并 DT 中没有直接设备节点。

| SPMI 寄存器名 | 地址 + 大小 |
|---|---|
| `cnfg` | `0x0c42d000 + 0x4000` |
| `core` | `0x0c400000 + 0x3000` |
| `chnls` | `0x0c500000 + 0x400000` |
| `obsrvr` | `0x0c440000 + 0x80000` |
| `intr` | `0x0c4c0000 + 0x10000` |

| DT 节点 | USID（reg 第一 cell） | reg 原始值 |
|---|---:|---|
| `qcom,pmk8350@0` | `0` | `[0, 0]` |
| `qcom,pm8350@1` | `1` | `[1, 0]` |
| `qcom,pm8350c@2` | `2` | `[2, 0]` |
| `qcom,pm8350b@3` | `3` | `[3, 0]` |
| `qcom,pmr735a@4` | `4` | `[4, 0]` |
| `qcom,pmr735b@5` | `5` | `[5, 0]` |
| `qcom,pm8450@7` | `7` | `[7, 0]` |
| `qcom,pm8010i@8` | `8` | `[8, 0]` |
| `qcom,pm8010j@9` | `9` | `[9, 0]` |

确认到的 PMIC 名称为 **PMK8350、PM8350、PM8350C、PM8350B、PMR735A、PMR735B、PM8450、PM8010I、PM8010J**。这些名称来自 DT 节点，不替代芯片丝印。`qcom,pm8010@8/@9` 与同 USID 的 `pm8010i/j` 是重复兼容节点，不能计作额外两颗 PMIC。

## 5. 触摸控制器

| 项目 | 实测值 |
|---|---|
| 控制器 | `synaptics-s3910` |
| DT 节点 | `/soc/spi@990000/synaptics_tcm@0` |
| 总线与地址 | **SPI0，chip-select 0**；`reg=<0>`；不是 I2C 地址 |
| 父控制器 | `qcom,spi-geni`，MMIO `0x00990000 + 0x4000` |
| 状态 | `okay` |
| input sysfs | `/devices/platform/soc/990000.spi/spi_master/spi0/spi0.0/input/input5` |

## 6. 屏幕面板与 DSI

唯一采用启动参数选中的节点：`/soc/qcom,mdss_mdp@ae00000/qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd`。DT 中其他候选面板没有混入本表。

| 项目 | 当前选中面板参数 |
|---|---|
| 面板名称 | `senna ab575 tm nt37705 dsc cmd mode panel` |
| 厂商标识 | `TM_NT37705_DVT` |
| 制造标识 | `TM1240` |
| 模式 | `dsi_cmd_mode` |
| 流量模式 | `non_burst_sync_event` |
| lane map | `lane_map_0123` |
| 颜色顺序 | `rgb_swap_rgb` |
| DSI / PHY / VC / stream | `ctrl=0` / `phy=0` / `VC=0` / `stream=0` |
| DSI bpp | `30`；不要与 DSC 的 8 bpp 混淆 |
| 物理尺寸 | `70 × 156` mm |
| MDP | `/soc/qcom,mdss_mdp@ae00000`：`0x0ae00000+0x84000`、`0x0ae80000+0x2008`、`0x0ae7f800+0x800`，SPI 83 |

五组 DT timing（clock 单位 Hz，transfer 单位 µs）：

| timing | fps | 宽 | 高 | clock | HFP | HBP | HPW | VFP | VBP | VPW | DSC bpc | DSC bpp | slice W | slice H | transfer |
|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|
| fhd_oplus_120 | 120 | 1240 | 2772 | 998400000 | 64 | 50 | 8 | 2 | 8 | 2 | 10 | 8 | 620 | 12 | 6000 |
| fhd_sdc_120 | 120 | 1240 | 2772 | 998400000 | 64 | 50 | 8 | 2 | 8 | 2 | 10 | 8 | 620 | 12 | 6000 |
| fhd_sdc_144 | 144 | 1240 | 2772 | 1148000000 | 64 | 48 | 8 | 2 | 8 | 2 | 10 | 8 | 620 | 12 | 5000 |
| fhd_sdc_60 | 60 | 1240 | 2772 | 998400000 | 64 | 48 | 8 | 2 | 8 | 2 | 10 | 8 | 620 | 12 | 6000 |
| fhd_sdc_90 | 90 | 1240 | 2772 | 998400000 | 64 | 49 | 8 | 2 | 8 | 2 | 10 | 8 | 620 | 12 | 9000 |

公共 DSC 参数：`dsc-version=0x11`、`scr-version=1`、`slice-per-pkt=2`、`encoders=2`、`lm-split=[620,620]`、`display-topology=[1,1,1,2,2,1]`。五组 timing 是支持集合，**当前实际刷新率和实时 DSI 链路状态本次未确定**。完整 81 个面板属性及所有命令字节哈希见 [`inventory-facts.json`](<device-inventory/inventory-facts.json>)。

## 7. UFS

| 项目 | 实测值 | 来源 |
|---|---|---|
| 控制器 | `/soc/ufshc@1d84000`；`0x0000000001d84000 + 0x3000`<br>`0x0000000001d88000 + 0x8000`<br>`0x0000000001d90000 + 0x9000`；names=['ufs_mem', 'ufs_ice', 'ufs_ice_hwkm']；SPI 265 | 当前 DT |
| SCSI 厂商 | `MICRON` | 所有已列 LUN 的 sysfs `vendor` |
| 产品型号 | `MT256GAXAT4U31` | sysfs `model` / 产品字符串 |
| 产品/固件 revision | `0107` | sysfs `rev`；不是 UFS 规范版本 |
| manufacturer_id | `0x012C` | UFS device descriptor |
| device_version | `0x0011` | UFS device descriptor，保留原始值 |
| UFS 规范版本 | `0x0310` → **UFS 3.1** | device descriptor BCD |
| UniPro / M-PHY | `0x0180` / `0x0410` → **1.8 / 4.1** | interconnect descriptor BCD |
| LUN / queue depth | `0x06` / `0x20` | device descriptor |

原始描述符输出见 [`ufs-descriptors.txt`](<device-inventory/ufs-descriptors.txt>)。没有从 `MT256GAXAT4U31` 的字符串反推未读出的容量、制程或功耗参数。

## 8. Wi-Fi 与蓝牙

| 功能 | 本机证据 | 结论 |
|---|---|---|
| Wi-Fi | DT `/soc/qcom,cnss-qca6490@b0000000`：`compatible=qcom,cnss-qca6490`；PCI `0000:01:00.0` vendor/device=`0x17cb:0x1103`，subsystem=`0x17cb:0x0108`，class=`0x028000` | Wi-Fi 功能为 **QCA6490**；PCI ID 不用于反推另一型号 |
| 蓝牙 | DT `/soc/bt_qca6490`：`compatible=qcom,qca6490`；现有驱动日志也含 qca6490 | 蓝牙功能为 **QCA6490** |

`qcom,cnss-qca6490@b0000000` 的 `reg=0xb0000000+0x10000` 名为 `smmu_iova_ipa`，**不是 PCI MMIO 地址**。本报告不据此断言芯片封装数量或未采集的固件版本。

## 9. reserved-memory 全量布局

共 55 项。地址均保留 64 位形式；无 `reg` 的节点列出其 `size/alignment/alloc-ranges`，不得把动态分配池猜成固定地址。

| 节点 | compatible / label | reg 地址 + 大小 | size / alignment / alloc-ranges | 标志 |
|---|---|---|---|---|
| `reserved-memory/hyp_region@80000000` | — | `0x0000000080000000+0x600000` | — | no-map |
| `reserved-memory/xbl_dtlog_region@80600000` | — | `0x0000000080600000+0x40000` | — | no-map |
| `reserved-memory/xbl_ramdump_region@80640000` | — | `0x0000000080640000+0x1c0000` | — | no-map |
| `reserved-memory/aop_image_region@80800000` | — | `0x0000000080800000+0x60000` | — | no-map |
| `reserved-memory/aop_cmd_db_region@80860000` | qcom,cmd-db | `0x0000000080860000+0x20000` | — | no-map |
| `reserved-memory/aop_config_region@80880000` | — | `0x0000000080880000+0x20000` | — | no-map |
| `reserved-memory/tme_crash_dump_region@808a0000` | — | `0x00000000808a0000+0x40000` | — | no-map |
| `reserved-memory/tme_log_region@808e0000` | — | `0x00000000808e0000+0x4000` | — | no-map |
| `reserved-memory/uefi_log_region@808e4000` | — | `0x00000000808e4000+0x10000` | — | no-map |
| `reserved-memory/smem_region@80900000` | — | `0x0000000080900000+0x200000` | — | no-map |
| `reserved-memory/cpucp_fw_region@80b00000` | — | `0x0000000080b00000+0x100000` | — | no-map |
| `reserved-memory/cdsp_secure_heap_region@80c00000` | — | `0x0000000080c00000+0x100000` | — | no-map |
| `reserved-memory/video_region@85700000` | — | `0x000000009fd00000+0x700000` | — | no-map |
| `reserved-memory/adsp_region@85e00000` | — | `0x0000000085700000+0x2800000` | — | no-map |
| `reserved-memory/slpi_region@88000000` | — | `0x0000000088000000+0x1900000` | — | no-map |
| `reserved-memory/cdsp_region@89900000` | — | `0x0000000089900000+0x2000000` | — | no-map |
| `reserved-memory/ipa_fw_region@8b900000` | — | `0x000000008b900000+0x10000` | — | no-map |
| `reserved-memory/ipa_gsi_region@8b910000` | — | `0x000000008b910000+0xa000` | — | no-map |
| `reserved-memory/gpu_microcode_region@8b91a000` | — | `0x000000008b91a000+0x2000` | — | no-map |
| `reserved-memory/spss_region_region@8ba00000` | — | `0x000000008ba00000+0x180000` | — | no-map |
| `reserved-memory/spu_tz_shared_mem@8bb80000` | — | `0x000000008bb80000+0x60000` | — | no-map |
| `reserved-memory/spu_modem_shared_mem@8bbe0000` | — | `0x000000008bbe0000+0x20000` | — | no-map |
| `reserved-memory/mpss_region@8bc00000` | — | `0x000000008bc00000+0x13200000` | — | no-map |
| `reserved-memory/cvp_region@9ee00000` | — | `0x000000009ee00000+0x700000` | — | no-map |
| `reserved-memory/camera_region@9f500000` | — | `0x000000009f500000+0x800000` | — | no-map |
| `reserved-memory/xbl_sc_region@a6e00000` | — | `0x00000000a6e00000+0x40000` | — | no-map |
| `reserved-memory/global_sync_region@a6f00000` | — | `0x00000000a6f00000+0x100000` | — | no-map |
| `reserved-memory/qheebsp_reserved_region@e0000000` | — | `0x00000000e0000000+0x0` | — | no-map |
| `reserved-memory/cpusys_vm_region@e0600000` | — | `0x00000000e0600000+0x400000` | — | no-map |
| `reserved-memory/hyp_reserved_region@e0a00000` | — | `0x00000000e0a00000+0x100000` | — | no-map |
| `reserved-memory/trust_ui_vm_region@e0b00000` | — | `0x00000000e0b00000+0x4af3000` | — | no-map |
| `reserved-memory/trust_ui_vm_qrtr@e55f3000` | — | `0x00000000e55f3000+0x9000` | — | no-map |
| `reserved-memory/trust_ui_vm_vblk0_ring@e55fc000` | — | `0x00000000e55fc000+0x4000` | — | no-map |
| `reserved-memory/trust_ui_vm_swiotlb@e5600000` | — | `0x00000000e5600000+0x100000` | — | no-map |
| `reserved-memory/tz_stat_region@e8800000` | — | `0x00000000e8800000+0x100000` | — | no-map |
| `reserved-memory/tags_region@e8900000` | — | `0x00000000e8900000+0x1200000` | — | no-map |
| `reserved-memory/qtee_region@e9b00000` | — | `0x00000000e9b00000+0x500000` | — | no-map |
| `reserved-memory/sp_region` | shared-dma-pool | — | `size=['0x0', '0x1000000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/linux,cma` | shared-dma-pool | — | `size=['0x0', '0x2000000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/va_md_mem_region` | shared-dma-pool | — | `size=['0x0', '0x1000000']`<br>`alloc-ranges=['0x1', '0x0', '0xfffffffe', '0xffffffff']` | reusable |
| `reserved-memory/user_contig_region` | shared-dma-pool | — | `size=['0x0', '0x1000000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/qseecom_region` | shared-dma-pool | — | `size=['0x0', '0x4800000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/non_secure_display_region` | shared-dma-pool | — | `size=['0x0', '0xa400000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/demura_heap_region` | shared-dma-pool | — | `size=['0x0', '0x2800000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x1', '0x0', '0xfffffffe', '0xffffffff']` | reusable |
| `reserved-memory/qseecom_ta_region` | shared-dma-pool | — | `size=['0x0', '0x1000000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/cnss_wlan_region` | shared-dma-pool | — | `size=['0x0', '0x2000000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/audio_cma_region` | shared-dma-pool | — | `size=['0x0', '0x1c00000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/adsp_heap_region` | shared-dma-pool | — | `size=['0x0', '0xc00000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/sdsp_region` | shared-dma-pool | — | `size=['0x0', '0x800000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/cdsp_eva_region` | shared-dma-pool | — | `size=['0x0', '0x400000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x0', '0x0', '0x0', '0xffffffff']` | reusable |
| `reserved-memory/ramoops_region` | ramoops | — | `size=['0x0', '0x240000']`<br>`alloc-ranges=['0x0', '0x0', '0xffffffff', '0xffffffff']` | — |
| `reserved-memory/mem_dump_region` | shared-dma-pool | — | `size=['0x0', '0x3000000']`<br>`alignment=['0x0', '0x400000']`<br>`alloc-ranges=['0x1', '0x0', '0xfffffffe', '0xffffffff']` | reusable |
| `reserved-memory/device_info_mem@0xA4F00000` | label=dump_device_info_mem | `0x00000000a4f00000+0x8000` | — | — |
| `reserved-memory/botloader_mem@0xA7605000` | label=bootloader_log_mem | `0x00000000a7605000+0x8000` | — | — |
| `reserved-memory/splash_region` | label=cont_splash_region | `0x00000000b8000000+0x2b00000` | — | — |

## 10. 全量 by-name 分区表

共 132 个唯一名称；大小由 root 下 `blockdev --getsize64` 读取，失败时才用 sysfs sectors×512。未读取或修改分区内容。

| 分区名 | 块设备 | 大小（字节） | 大小（MiB） | by-name 路径 |
|---|---|---:|---:|---|
| `ALIGN_TO_128K_1` | `/dev/block/sdd1` | 106496 | 0.102 | `/dev/block/by-name/ALIGN_TO_128K_1` |
| `ALIGN_TO_128K_2` | `/dev/block/sdf1` | 106496 | 0.102 | `/dev/block/by-name/ALIGN_TO_128K_2` |
| `DRIVER` | `/dev/block/sdf14` | 33554432 | 32.000 | `/dev/block/by-name/DRIVER` |
| `abl_a` | `/dev/block/sde10` | 1048576 | 1.000 | `/dev/block/by-name/abl_a` |
| `abl_b` | `/dev/block/sde40` | 1048576 | 1.000 | `/dev/block/by-name/abl_b` |
| `aop_a` | `/dev/block/sde2` | 524288 | 0.500 | `/dev/block/by-name/aop_a` |
| `aop_b` | `/dev/block/sde32` | 524288 | 0.500 | `/dev/block/by-name/aop_b` |
| `aop_config_a` | `/dev/block/sde3` | 524288 | 0.500 | `/dev/block/by-name/aop_config_a` |
| `aop_config_b` | `/dev/block/sde33` | 524288 | 0.500 | `/dev/block/by-name/aop_config_b` |
| `apdp` | `/dev/block/sdb5` | 262144 | 0.250 | `/dev/block/by-name/apdp` |
| `apdp_full` | `/dev/block/sde78` | 262144 | 0.250 | `/dev/block/by-name/apdp_full` |
| `apdpb` | `/dev/block/sdc5` | 262144 | 0.250 | `/dev/block/by-name/apdpb` |
| `bluetooth_a` | `/dev/block/sde7` | 4194304 | 4.000 | `/dev/block/by-name/bluetooth_a` |
| `bluetooth_b` | `/dev/block/sde37` | 4194304 | 4.000 | `/dev/block/by-name/bluetooth_b` |
| `boot_a` | `/dev/block/sde13` | 201326592 | 192.000 | `/dev/block/by-name/boot_a` |
| `boot_b` | `/dev/block/sde43` | 201326592 | 192.000 | `/dev/block/by-name/boot_b` |
| `cdt` | `/dev/block/sdd2` | 131072 | 0.125 | `/dev/block/by-name/cdt` |
| `connsec` | `/dev/block/sde72` | 131072 | 0.125 | `/dev/block/by-name/connsec` |
| `cpucp_a` | `/dev/block/sde22` | 1048576 | 1.000 | `/dev/block/by-name/cpucp_a` |
| `cpucp_b` | `/dev/block/sde52` | 1048576 | 1.000 | `/dev/block/by-name/cpucp_b` |
| `ddr` | `/dev/block/sdd3` | 1048576 | 1.000 | `/dev/block/by-name/ddr` |
| `devcfg_a` | `/dev/block/sde14` | 131072 | 0.125 | `/dev/block/by-name/devcfg_a` |
| `devcfg_b` | `/dev/block/sde44` | 131072 | 0.125 | `/dev/block/by-name/devcfg_b` |
| `devinfo` | `/dev/block/sde60` | 4096 | 0.004 | `/dev/block/by-name/devinfo` |
| `dinfo` | `/dev/block/sdd6` | 16384 | 0.016 | `/dev/block/by-name/dinfo` |
| `dip` | `/dev/block/sde61` | 1048576 | 1.000 | `/dev/block/by-name/dip` |
| `dsp_a` | `/dev/block/sde11` | 67108864 | 64.000 | `/dev/block/by-name/dsp_a` |
| `dsp_b` | `/dev/block/sde41` | 67108864 | 64.000 | `/dev/block/by-name/dsp_b` |
| `dtbo_a` | `/dev/block/sde17` | 25165824 | 24.000 | `/dev/block/by-name/dtbo_a` |
| `dtbo_b` | `/dev/block/sde47` | 25165824 | 24.000 | `/dev/block/by-name/dtbo_b` |
| `engineering_cdt_a` | `/dev/block/sdd4` | 1048576 | 1.000 | `/dev/block/by-name/engineering_cdt_a` |
| `engineering_cdt_b` | `/dev/block/sdd7` | 1048576 | 1.000 | `/dev/block/by-name/engineering_cdt_b` |
| `featenabler_a` | `/dev/block/sde23` | 131072 | 0.125 | `/dev/block/by-name/featenabler_a` |
| `featenabler_b` | `/dev/block/sde53` | 131072 | 0.125 | `/dev/block/by-name/featenabler_b` |
| `frp` | `/dev/block/sda5` | 524288 | 0.500 | `/dev/block/by-name/frp` |
| `fsc` | `/dev/block/sdf7` | 131072 | 0.125 | `/dev/block/by-name/fsc` |
| `fsg` | `/dev/block/sdf6` | 3145728 | 3.000 | `/dev/block/by-name/fsg` |
| `hyp_a` | `/dev/block/sde5` | 8388608 | 8.000 | `/dev/block/by-name/hyp_a` |
| `hyp_b` | `/dev/block/sde35` | 8388608 | 8.000 | `/dev/block/by-name/hyp_b` |
| `imagefv_a` | `/dev/block/sde19` | 2097152 | 2.000 | `/dev/block/by-name/imagefv_a` |
| `imagefv_b` | `/dev/block/sde49` | 2097152 | 2.000 | `/dev/block/by-name/imagefv_b` |
| `keymaster_a` | `/dev/block/sde12` | 524288 | 0.500 | `/dev/block/by-name/keymaster_a` |
| `keymaster_b` | `/dev/block/sde42` | 524288 | 0.500 | `/dev/block/by-name/keymaster_b` |
| `keystore` | `/dev/block/sda4` | 524288 | 0.500 | `/dev/block/by-name/keystore` |
| `last_parti` | `/dev/block/sdf17` | 58437632 | 55.730 | `/dev/block/by-name/last_parti` |
| `limits` | `/dev/block/sde62` | 4096 | 0.004 | `/dev/block/by-name/limits` |
| `limits-cdsp` | `/dev/block/sde63` | 4096 | 0.004 | `/dev/block/by-name/limits-cdsp` |
| `logdump` | `/dev/block/sde66` | 536870912 | 512.000 | `/dev/block/by-name/logdump` |
| `logfs` | `/dev/block/sde65` | 8388608 | 8.000 | `/dev/block/by-name/logfs` |
| `mdcompress` | `/dev/block/sde71` | 20971520 | 20.000 | `/dev/block/by-name/mdcompress` |
| `mdm1oemnvbktmp` | `/dev/block/sdf8` | 2097152 | 2.000 | `/dev/block/by-name/mdm1oemnvbktmp` |
| `mdtp_a` | `/dev/block/sde9` | 33554432 | 32.000 | `/dev/block/by-name/mdtp_a` |
| `mdtp_b` | `/dev/block/sde39` | 33554432 | 32.000 | `/dev/block/by-name/mdtp_b` |
| `mdtpsecapp_a` | `/dev/block/sde8` | 4194304 | 4.000 | `/dev/block/by-name/mdtpsecapp_a` |
| `mdtpsecapp_b` | `/dev/block/sde38` | 4194304 | 4.000 | `/dev/block/by-name/mdtpsecapp_b` |
| `metadata` | `/dev/block/sda11` | 16777216 | 16.000 | `/dev/block/by-name/metadata` |
| `misc` | `/dev/block/sda3` | 1048576 | 1.000 | `/dev/block/by-name/misc` |
| `modem_a` | `/dev/block/sde6` | 314572800 | 300.000 | `/dev/block/by-name/modem_a` |
| `modem_b` | `/dev/block/sde36` | 314572800 | 300.000 | `/dev/block/by-name/modem_b` |
| `modemst1` | `/dev/block/sdf4` | 3145728 | 3.000 | `/dev/block/by-name/modemst1` |
| `modemst2` | `/dev/block/sdf5` | 3145728 | 3.000 | `/dev/block/by-name/modemst2` |
| `multiimgoem_a` | `/dev/block/sdb4` | 32768 | 0.031 | `/dev/block/by-name/multiimgoem_a` |
| `multiimgoem_b` | `/dev/block/sdc4` | 32768 | 0.031 | `/dev/block/by-name/multiimgoem_b` |
| `multiimgqti_a` | `/dev/block/sdb3` | 32768 | 0.031 | `/dev/block/by-name/multiimgqti_a` |
| `multiimgqti_b` | `/dev/block/sdc3` | 32768 | 0.031 | `/dev/block/by-name/multiimgqti_b` |
| `ocdt` | `/dev/block/sdd5` | 131072 | 0.125 | `/dev/block/by-name/ocdt` |
| `oplus_sec_a` | `/dev/block/sde27` | 10485760 | 10.000 | `/dev/block/by-name/oplus_sec_a` |
| `oplus_sec_b` | `/dev/block/sde56` | 10485760 | 10.000 | `/dev/block/by-name/oplus_sec_b` |
| `oplusdycnvbk` | `/dev/block/sdf2` | 20971520 | 20.000 | `/dev/block/by-name/oplusdycnvbk` |
| `oplusreserve1` | `/dev/block/sdf9` | 8388608 | 8.000 | `/dev/block/by-name/oplusreserve1` |
| `oplusreserve2` | `/dev/block/sdf10` | 268435456 | 256.000 | `/dev/block/by-name/oplusreserve2` |
| `oplusreserve3` | `/dev/block/sdf11` | 67108864 | 64.000 | `/dev/block/by-name/oplusreserve3` |
| `oplusreserve4` | `/dev/block/sdf12` | 33554432 | 32.000 | `/dev/block/by-name/oplusreserve4` |
| `oplusreserve5` | `/dev/block/sdf13` | 67108864 | 64.000 | `/dev/block/by-name/oplusreserve5` |
| `oplusstanvbk_a` | `/dev/block/sdf3` | 20971520 | 20.000 | `/dev/block/by-name/oplusstanvbk_a` |
| `oplusstanvbk_b` | `/dev/block/sdf15` | 20971520 | 20.000 | `/dev/block/by-name/oplusstanvbk_b` |
| `param` | `/dev/block/sdf16` | 1048576 | 1.000 | `/dev/block/by-name/param` |
| `persist` | `/dev/block/sda2` | 33554432 | 32.000 | `/dev/block/by-name/persist` |
| `qmcs` | `/dev/block/sde25` | 31457280 | 30.000 | `/dev/block/by-name/qmcs` |
| `qupfw_a` | `/dev/block/sde15` | 81920 | 0.078 | `/dev/block/by-name/qupfw_a` |
| `qupfw_b` | `/dev/block/sde45` | 81920 | 0.078 | `/dev/block/by-name/qupfw_b` |
| `qweslicstore_a` | `/dev/block/sde26` | 262144 | 0.250 | `/dev/block/by-name/qweslicstore_a` |
| `qweslicstore_b` | `/dev/block/sde55` | 262144 | 0.250 | `/dev/block/by-name/qweslicstore_b` |
| `rawdump` | `/dev/block/sda12` | 268435456 | 256.000 | `/dev/block/by-name/rawdump` |
| `recovery_a` | `/dev/block/sde28` | 104857600 | 100.000 | `/dev/block/by-name/recovery_a` |
| `recovery_b` | `/dev/block/sde57` | 104857600 | 100.000 | `/dev/block/by-name/recovery_b` |
| `rtice` | `/dev/block/sde75` | 524288 | 0.500 | `/dev/block/by-name/rtice` |
| `sda` | `/dev/block/sda` | 251951841280 | 240280.000 | `/dev/block/by-name/sda` |
| `sdb` | `/dev/block/sdb` | 8388608 | 8.000 | `/dev/block/by-name/sdb` |
| `sdc` | `/dev/block/sdc` | 8388608 | 8.000 | `/dev/block/by-name/sdc` |
| `sdd` | `/dev/block/sdd` | 33554432 | 32.000 | `/dev/block/by-name/sdd` |
| `sde` | `/dev/block/sde` | 3296722944 | 3144.000 | `/dev/block/by-name/sde` |
| `sdf` | `/dev/block/sdf` | 612368384 | 584.000 | `/dev/block/by-name/sdf` |
| `secdata` | `/dev/block/sde69` | 28672 | 0.027 | `/dev/block/by-name/secdata` |
| `shrm_a` | `/dev/block/sde20` | 131072 | 0.125 | `/dev/block/by-name/shrm_a` |
| `shrm_b` | `/dev/block/sde50` | 131072 | 0.125 | `/dev/block/by-name/shrm_b` |
| `splash_a` | `/dev/block/sde29` | 34226176 | 32.641 | `/dev/block/by-name/splash_a` |
| `splash_b` | `/dev/block/sde58` | 34226176 | 32.641 | `/dev/block/by-name/splash_b` |
| `splash_odm` | `/dev/block/sda13` | 34226176 | 32.641 | `/dev/block/by-name/splash_odm` |
| `spunvm` | `/dev/block/sde74` | 33554432 | 32.000 | `/dev/block/by-name/spunvm` |
| `ssd` | `/dev/block/sda1` | 8192 | 0.008 | `/dev/block/by-name/ssd` |
| `storsec` | `/dev/block/sde67` | 131072 | 0.125 | `/dev/block/by-name/storsec` |
| `super` | `/dev/block/sda6` | 14495514624 | 13824.000 | `/dev/block/by-name/super` |
| `toolsfv` | `/dev/block/sde64` | 1048576 | 1.000 | `/dev/block/by-name/toolsfv` |
| `tz_a` | `/dev/block/sde4` | 4194304 | 4.000 | `/dev/block/by-name/tz_a` |
| `tz_b` | `/dev/block/sde34` | 4194304 | 4.000 | `/dev/block/by-name/tz_b` |
| `tzsc` | `/dev/block/sde73` | 131072 | 0.125 | `/dev/block/by-name/tzsc` |
| `uefi_a` | `/dev/block/sde1` | 5242880 | 5.000 | `/dev/block/by-name/uefi_a` |
| `uefi_b` | `/dev/block/sde31` | 5242880 | 5.000 | `/dev/block/by-name/uefi_b` |
| `uefisecapp_a` | `/dev/block/sde18` | 2097152 | 2.000 | `/dev/block/by-name/uefisecapp_a` |
| `uefisecapp_b` | `/dev/block/sde48` | 2097152 | 2.000 | `/dev/block/by-name/uefisecapp_b` |
| `uefivarstore` | `/dev/block/sde68` | 524288 | 0.500 | `/dev/block/by-name/uefivarstore` |
| `userdata` | `/dev/block/sda14` | 237100920832 | 226117.059 | `/dev/block/by-name/userdata` |
| `vbmeta_a` | `/dev/block/sde16` | 65536 | 0.062 | `/dev/block/by-name/vbmeta_a` |
| `vbmeta_b` | `/dev/block/sde46` | 65536 | 0.062 | `/dev/block/by-name/vbmeta_b` |
| `vbmeta_system_a` | `/dev/block/sda7` | 65536 | 0.062 | `/dev/block/by-name/vbmeta_system_a` |
| `vbmeta_system_b` | `/dev/block/sda8` | 65536 | 0.062 | `/dev/block/by-name/vbmeta_system_b` |
| `vbmeta_vendor_a` | `/dev/block/sda9` | 65536 | 0.062 | `/dev/block/by-name/vbmeta_vendor_a` |
| `vbmeta_vendor_b` | `/dev/block/sda10` | 65536 | 0.062 | `/dev/block/by-name/vbmeta_vendor_b` |
| `vendor_boot_a` | `/dev/block/sde24` | 201326592 | 192.000 | `/dev/block/by-name/vendor_boot_a` |
| `vendor_boot_b` | `/dev/block/sde54` | 201326592 | 192.000 | `/dev/block/by-name/vendor_boot_b` |
| `vm-bootsys_a` | `/dev/block/sde21` | 274878464 | 262.145 | `/dev/block/by-name/vm-bootsys_a` |
| `vm-bootsys_b` | `/dev/block/sde51` | 274878464 | 262.145 | `/dev/block/by-name/vm-bootsys_b` |
| `vm-data` | `/dev/block/sde70` | 34226176 | 32.641 | `/dev/block/by-name/vm-data` |
| `xbl_a` | `/dev/block/sdb1` | 6291456 | 6.000 | `/dev/block/by-name/xbl_a` |
| `xbl_b` | `/dev/block/sdc1` | 6291456 | 6.000 | `/dev/block/by-name/xbl_b` |
| `xbl_config_a` | `/dev/block/sdb2` | 217088 | 0.207 | `/dev/block/by-name/xbl_config_a` |
| `xbl_config_b` | `/dev/block/sdc2` | 217088 | 0.207 | `/dev/block/by-name/xbl_config_b` |
| `xbl_ramdump_a` | `/dev/block/sde30` | 2097152 | 2.000 | `/dev/block/by-name/xbl_ramdump_a` |
| `xbl_ramdump_b` | `/dev/block/sde59` | 2097152 | 2.000 | `/dev/block/by-name/xbl_ramdump_b` |
| `xbl_sc_logs` | `/dev/block/sde77` | 131072 | 0.125 | `/dev/block/by-name/xbl_sc_logs` |
| `xbl_sc_test_mode` | `/dev/block/sde76` | 65536 | 0.062 | `/dev/block/by-name/xbl_sc_test_mode` |

## 11. 对照 ios-sweet 与 UniXNU 的复用分类

参考固定版本：ios-sweet `45263bee51df4a0f55cdf9c649af886399488ddb`（SM7150/sweet）；UniXNU `519d80242a5028ee123447b01bc3b809baed565f`。

**先纠正对照前提：上述 UniXNU main commit 没有 SM8475/cape/taro/senna/RMX3706 设备路径，因此不存在可诚实列出的“UniXNU 的 SM8475 机型参数”。若指其他分支或 fork，必须另给 commit 后再审计。**

### 11.1 可直接复用（仅通用方法/框架，仍须构建与实机验证）

- ios-sweet 的 xnu-8796 构建链方法：darwin-xnu-build 固定 `663906528d1cd5ea8fde7de6f16de73db9511549`、macOS 13.5、Xcode 15/iig、`DEVELOPMENT` 配置。可复用的是工具链固定方法，不是 sweet 整机镜像。
- 架构通用算法/协议实现可作为候选：ARM64 PSCI 调用框架、GICv3 驱动框架、UFS/SCSI 协议层、FDT 解析与启动参数传递。SoC glue、地址、时钟、复位、PHY 不在此类。
- UniXNU 的通用移植文档、代码组织方式和 BSD-2-Clause-Patent 许可文本可参考；没有可据该 commit 直接复用的 SM8475 机型参数。
- **不可复用：** `tools/sweet-root-tweaks.py` 会修改 rootfs，违反本项目“用户空间一字节不改”，明确禁用。

### 11.2 需改地址/本机参数

| 子系统 | 不能照搬的内容 | senna-b 必须使用的证据 |
|---|---|---|
| 内存 | sweet/其他机型的 DRAM base、大小、保留区 | 本文 5 段 `/memory` 与 55 项 reserved-memory |
| GICv3/ITS/PDC | 所有 MMIO、redistributor、IRQ 配置 | GICD `0x17100000`、GICR `0x17180000`、ITS `0x17140000`；以当前 DT 原始 reg 为准 |
| Timer/UART | MMIO frame、IRQ、console base | timer `0x17420000`；UART `0x0099c000`、SPI 608 |
| UFS | HC/ICE/HWKM、IRQ、PHY/clock/reset/interconnect | `0x01d84000/0x01d88000/0x01d90000`、SPI 265；描述符仅识别设备，不替代初始化代码 |
| SPMI/PMIC | arbiter 五组寄存器、USID、regulator/clock 资源 | `0x0c42d000` 总线及本机 PMIC 表 |
| 显示 | MDP/DSI/PHY、DSC、timing、reset/TE/backlight | 当前 NT37705 节点与五组 timing |
| 触控 | I2C 地址和 sweet 触控流程 | 本机是 SPI0 CS0 的 Synaptics S3910 |
| Wi-Fi/BT | sweet 的 WLAN/BT 平台 glue | QCA6490、PCI `17cb:1103`、CNSS/MHI/IOMMU 本机节点 |

### 11.3 需新写或新适配

- senna-b 专用 UEFI DSC/FDF、MemoryMap、DeviceConfigurationMap、启动 shim 设备配置；当前没有现成 senna-b 设备包。
- SM8475/senna-b 的时钟、复位、pinctrl、regulator、互连和 PMIC 初始化序列；不能只改一个 base address。
- UFS host glue 与 PHY 初始化，并单独决定 ICE/HWKM 支持策略；描述符读取成功不代表 XNU 可读写 UFS。
- NT37705 的 DSI command-mode + DSC 初始化、命令包、动态刷新、背光/TE/reset，以及 Pixelworks Iris 相关依赖的启用或隔离策略。
- S3910 的 GENI SPI 传输、供电/复位/中断和固件加载流程；不能从 I2C 触控驱动小改得到。
- QCA6490 的 PCIe/CNSS/MHI、固件、IOMMU 与电源管理适配；Wi-Fi/BT 不能视为通用 PCIe 网卡即插即用。
- UniXNU 若后续提供确切 SM8475 分支，仍需逐项重新分类；当前不能预写为已有实现。

## 12. 未确定项与下一步采集

- 标准 `dtc -I dtb -O dts` 复核；官方全量 OTA/payload 与哈希；bootloader 实际 base DTB 选择算法。
- 当前活动帧缓冲 base/stride/format、实际刷新率/DSI 链路状态、目标启动环境 CNTFRQ 和 arch-timer IRQ。
- PSCI、UART、 clocks/resets/regulators 在非 Android 环境的可访问性，需要后续受控启动实验，不能由本次只读采集推断。
- 本报告只做信息采集与参数归档，未进入移植实现。
