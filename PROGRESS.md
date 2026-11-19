# RMX3706 / senna-b XNU 移植进度

## 阶段 0：本机证据与可恢复性基线——通过（仅限已验证范围）

### 已完成
- ADB 设备序列号 78ad6b26，型号 RMX3706，Android 设备名 RE5860。
- 固件 RMX3706_13.1.0.115(CN01)；OTA RMX3706_11.A.45_0450_202308171956。
- Android 内核 5.10.149-android12-9-o-g36dae0b389f6；当前槽位 _b。
- verifiedbootstate=orange，vbmeta.device_state=unlocked，flash.locked=0。
- root 只读备份 boot_b、dtbo_b、vendor_boot_b、vbmeta_b；保存实时基础 DTB、cmdline、iomem、分区和属性。
- fastboot devices 已识别 78ad6b26；fastboot reboot 成功；设备已返回 Android，sys.boot_completed=1，槽位仍 _b、orange。
- bootloader getvar product 返回 taro；current-slot 返回 unknown command；unlocked、version-bootloader、is-userspace 返回 GetVar Variable Not found。

### 未完成／限制
- 未执行 fastboot boot，内存启动能力尚未验证。
- 未提供匹配官方全量 OTA；未验证 EDL 或其他深度救砖路径。
- 未刷写、未清空、未解锁、未修改任何设备分区。
- fastboot product=taro 只是平台标识，不是 senna-b UEFI/DTB 已适配证明。
- live base DTB compatible=qcom,cape-mtp/qcom,cape/qcom,mtp；不得直接当整机配置，需解析 DTBO/vendor_boot。

### 关键参数表
| 项目 | 值 | 来源 |
|---|---|---|
| boot_b | /dev/block/sde43，201326592 字节 | 本机 by-name、备份头 ANDROID! |
| dtbo_b | /dev/block/sde47，25165824 字节 | 本机 by-name、DTBO 表头 |
| vendor_boot_b | /dev/block/sde54，201326592 字节 | 本机 by-name、VNDRBOOT v4 |
| vbmeta_b | /dev/block/sde46，65536 字节 | 本机 by-name、AVB0 |
| live base DTB | 1118143 字节 | /sys/firmware/fdt，FDT 魔数 D0 0D FE ED |
| DTB SHA-256 | AB7B51E9564A168BA3AE93E22F70CEE32BA5CAF776A4438B3CF31B2A3CC77E57 | 主机计算 |
| 显示面板 compatible | qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd | 本机 /proc/cmdline |
| 触控标识 | synaptics-s3910 | 本机 /proc/cmdline |
| 项目号 | 22624 | 本机 /proc/cmdline oplusboot.prjname |

证据目录：stage-00-evidence。哈希见 stage-00-evidence/SHA256SUMS.txt；fastboot 原始输出见 fastboot-getvar.txt 和 fastboot-reboot.txt。

## 阶段 1：平台证据解析与 UEFI 源码核对——证据阶段通过

### 已完成
- 阶段 0 输入哈希全部一致；解析 16 个 DTBO overlay、3 个 vendor_boot base 和实时合并 FDT，保留二进制、文本、偏移和 SHA-256。
- senna-b 对应 `dtbo-entry-11.dtb`，model=`Qualcomm Technologies, Inc. Cape MTP, Senna B`，SHA-256=`D3169C92C8D9FC4DC49C94F18778A81391DE2CAF1AA9D9AE5BB0BBE4504F04CD`。
- 建立本机内存、8 CPU/PSCI、GICv3/PDC、timer、UART、UFS、MDP、NT37705 面板、synaptics-s3910 和保留区证据表。
- 固定审计 ios-sweet `45263bee51df4a0f55cdf9c649af886399488ddb`、UniXNU `519d80242a5028ee123447b01bc3b809baed565f`、edk2-msm `e1952621f419f8db60ed28271264e1b5184c571d`、darwin-xnu-build `663906528d1cd5ea8fde7de6f16de73db9511549`。
- 自动验收 54/54 通过；范围仅是主机侧证据完整性，不是启动功能测试。

### 未完成／限制
- 未证明 bootloader 的 vendor base 选择算法；最终硬件事实以实时合并 FDT 为准。
- active framebuffer base/stride/format、目标运行环境 arch timer CNTFRQ/IRQ、PSCI/UART 可访问性仍未知。
- 未建立 senna-b UEFI 设备包，未编译 XNU，未制作 shim/boot 镜像，未执行 fastboot boot；本阶段未连接或修改设备。
- edk2-msm 只有 SM8475 SoC 目录和 yudi 设备参考，没有 senna-b 直接支持；其他机型参数全部隔离。
- 匹配官方全量 OTA、EDL 救砖验证、原版 rootfs 获取与哈希核验仍未完成。

### 关键参数表
| 项目 | 值 | 来源 |
|---|---|---|
| senna-b overlay | DTBO entry 11，1212016 字节 | entry 11 与实时合并 FDT 根 model 一致 |
| 内存 | 5 段，合计 12655263744 字节；须排除 reserved-memory | live `/memory` |
| GICv3 | GICD 0x17100000+0x10000；GICR 0x17180000+0x200000 | live `/soc/interrupt-controller@17100000` |
| console | 0x0099c000+0x4000，SPI 608，115200n8 | live UART 节点和 bootargs |
| UFS | 0x01d84000+0x3000，SPI 265 | live `/soc/ufshc@1d84000` |
| 面板 | NT37705，1240x2772，DSC，60/90/120/144 Hz timings | live cmdline 和面板节点 |
| splash 保留区 | 0xb8000000+0x02b00000；不等于活动帧缓冲参数 | live `/reserved-memory/splash_region` |

完整报告：`stage-01-platform-evidence/STAGE1-REPORT.md`；原始值：`hardware-evidence.json`；仓库审计：`repository-audit.md`；失败记录：`FAILURES.md`；验收：`validation-results.json`；哈希：`SHA256SUMS.txt`。

下一阶段尚未开始。须先确定最小引导链设计、可复现构建环境、未知参数补证和回滚/验收日志，再决定是否生成任何启动镜像。

## 移植前设备信息采集（只读）

- 用户要求先采集、不写移植代码；已在 ADB `78ad6b26` 上执行只读脚本，未重启、未刷写、未在手机创建或修改文件。
- 已导出完整 `/proc/device-tree`：35,696 tar 成员；31,221 文件、4,475 目录完整展开，零错误。当前 `senna-live.dtb` 为 1,118,143 字节，SHA-256 `7A290B13563A058464FA01287FA801687B76E55A85A80867DDA76AAC73743094`；已生成本地解析器 DTS，标准 dtc 复核待办。
- 已形成 `DEVICE.md`：准确型号/系统/BL、5 段内存、GIC/Timer/UART、9 个 USID 的 PMIC、S3910 SPI0 CS0、NT37705 五组 DSI/DSC timing、Micron MT256GAXAT4U31 UFS 3.1（UniPro 1.8/M-PHY 4.1）、QCA6490 Wi-Fi/BT、55 项 reserved-memory、132 个 by-name 分区及三类复用清单。
- UniXNU 固定 main `519d80242a5028ee123447b01bc3b809baed565f` 没有 SM8475 机型路径，报告明确禁止虚构对照对象。
- 采集自动验收 26/26；阶段1回归验收 54/54。阶段1人工转录的 GICR `0x171c0000` 已按原始 DT 更正为 `0x17180000+0x200000`。
- 交付：`DEVICE.md`、`device-inventory/COLLECTION.md`、`device-inventory/validation-results.json`、`device-inventory/SHA256SUMS.txt`。未开始移植实现或实机启动。
