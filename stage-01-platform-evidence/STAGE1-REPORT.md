# 阶段 1：平台证据解析与 UEFI 源码核对

**结论：证据阶段通过；不代表 SM8475/senna-b 的 UEFI 或 XNU 已适配，也不代表可以实机启动。**

日期：2026-11-19。全程仅在电脑侧只读分析已有备份；未连接设备、未刷写、未清空、未解锁、未执行 `fastboot boot`，未生成启动镜像。

## 1. 目标、做法、验收与失败日志

- 目标：从本机 `dtbo_b`、`vendor_boot_b` 和实时合并 FDT 还原 senna-b 配置，并核对 ios-sweet、UniXNU、edk2-msm、darwin-xnu-build 的真实支持范围。
- 做法：验证阶段 0 输入哈希；解析 Android 镜像头和 FDT；导出全部 DTB 与可读文本；以实时 FDT 为最终硬件事实来源；用 GitHub 固定 commit、递归树和原始源码审计参考仓库。
- 验收：镜像边界和 FDT 长度一致；senna-b 对应条目有根属性和实时配置双重依据；本阶段采用的关键内存、寄存器、中断、面板与启动参数均可回到本机节点；参考数值与本机证据隔离；未知项明确保留。
- 失败时看：DTBO 魔数/表项边界、vendor_boot DTB 偏移、FDT `totalsize`、根 model/compatible、仓库 commit/tree/API 错误、网络下载日志。详见 `FAILURES.md`。

## 2. 输入与解析结果

阶段 0 的 `boot_b.img`、`dtbo_b.img`、`vendor_boot_b.img`、`vbmeta_b.img` 和实时 DTB 均与 `../stage-00-evidence/SHA256SUMS.txt` 一致。实时 DTB 为 1118143 字节，SHA-256：

`AB7B51E9564A168BA3AE93E22F70CEE32BA5CAF776A4438B3CF31B2A3CC77E57`

| 输入 | 本机解析结果 |
|---|---|
| `dtbo_b.img` | DTBO total_size=14188027，entry_size=32，16 项；全部提取并解析成功 |
| `boot_b.img` | Android boot v4，header_size=1584，kernel_size=46634324，ramdisk_size=1302512，signature_size=4096；未发现有效 FDT 候选 |
| `vendor_boot_b.img` | VNDRBOOT v4，page=4096，header_size=2128，vendor_ramdisk_size=19416683；DTB 区含 3 个串联 FDT，全部提取成功 |
| 实时合并 FDT | 作为 Android 启动后最终生效配置，保存为 `live-base-copy.dtb`；优先级高于通用 base 或单独 overlay |

vendor_boot 的关键布局：`dtb_size @2100 = 0x15e650`，`dtb_addr @2104 = 0x01f00000`，`dtb_offset = 19423232 (0x1286000)`。三个 FDT 长度 `0x750ad + 0x750a1 + 0x74502 = 0x15e650`，与头部完全相等。`dtb_addr` 只是 Android vendor_boot 打包字段，不能自动当作 UEFI FD 或 XNU 加载地址。

完整偏移、表项和哈希见 `image-headers.json`、`extraction-run.json`。`.dts.txt` 是本地解析器生成的可读转储，不宣称是 `dtc` 输出或可编译 DTS。

## 3. senna-b 对应 DTBO 条目

16 个条目的根 model 分组：00–02 Jennie-a；03 Jennie-b；04 Kunpeng；05–07 Lvzhou；08–09 Ovaltine；10 Ukee Senna A；**11 Cape Senna B**；12 Cape Senna C；13–14 Udon；15 Whiteswan。

**选定 `dtbo-entry-11.dtb` 作为 senna-b 对应 overlay：**

| 属性 | 值 |
|---|---|
| model | `Qualcomm Technologies, Inc. Cape MTP, Senna B` |
| compatible | `qcom,cape-mtp`, `qcom,cape`, `qcom,mtp` |
| 文件长度 | 1212016 字节 |
| SHA-256 | `D3169C92C8D9FC4DC49C94F18778A81391DE2CAF1AA9D9AE5BB0BBE4504F04CD` |
| DTBO dt_offset | `8846178 (0x86fb62)`；原始八字节 `0086fb6200000000` |
| id / rev / custom | `0 / 0 / [0,0,0]` |
| 节点数 | 3478 |

依据不是“文件名像 senna”：通用 base 根 model 是 Cape SoC，实时合并 FDT 已变为 Senna B，只有 entry 11 根 model 同为 Senna B；实时 cmdline 的项目号 22624、NT37705 面板和 synaptics-s3910 也在该条目中有对应节点。entry 10/12 分别是 Senna A/C，禁止混用。DTBO 的 id 全零，本报告不臆测 bootloader 的表项匹配算法。

vendor_boot 三个 base：00=`Cape LTE Only SoC`/`qcom,cape-v2`，01=`Cape SoC`/`qcom,cape`，02=`Ukee SoC`/`qcom,ukee`。base 01 是候选，但 overlay 可替换根属性，尚无独立 bootloader 选择日志，因此不声称已证明实际选择 01；后续平台事实以实时合并 FDT 为准。

## 4. 本机关键硬件证据

除特别注明外，本节均来自实时合并 FDT `live-base-copy.dtb`，原始 hex、be32、字符串和 reg 解码见 `hardware-evidence.json`，可读节点见 `hardware-nodes.txt`、`hardware-summary.txt`。中断先列 DT 原始三元组；对 GIC SPI，若后续驱动需要全局 INTID，才按 `INTID = SPI + 32` 派生并保留映射，绝不从其他机型复制。

### 4.1 CPU、PSCI、内存

| 节点/来源 | 本机值 |
|---|---|
| `/cpus/cpu@0` … `/cpus/cpu@700` | 8 个 CPU；reg/MPIDR affinity 为 `0,0x100,…,0x700`；`enable-method="psci"` |
| `/soc/psci` | `compatible="arm,psci-1.0"`，`method="smc"`；尚未实机验证移植运行 Exception Level 下可调用 |
| root `qcom,msm-id` | 原始 `00000213000100000000021c000100000000021200010000`，即 `[531,65536,540,65536,530,65536]` |
| root `qcom,board-id` | `[65544,0]` |

`/memory` 的 address/size cells 均为 2，五段原始范围如下；合计 12655263744 字节，只是 DT 宣告内存，不等于可随意覆盖的物理内存，必须再排除全部 reserved-memory 和固件占用。

| 起始地址 | 大小 |
|---|---|
| `0x0000000080000000` | `0x000000006a000000` |
| `0x00000000f1400000` | `0x000000000ec00000` |
| `0x0000000800000000` | `0x0000000039900000` |
| `0x0000000900000000` | `0x0000000180000000` |
| `0x0000000840000000` | `0x00000000c0000000` |

### 4.2 中断、定时器、UART、UFS

| 子系统 | FDT 节点与原始证据 |
|---|---|
| GICv3 | `/soc/interrupt-controller@17100000`：GICD `0x17100000+0x10000`，GICR `0x17180000+0x200000`，`#interrupt-cells=3`；ITS `0x17140000+0x20000` |
| PDC | `/soc/interrupt-controller@b220000`：`0x0b220000+0x30000`、`0x17400ff0+0x64`；不能误当 GICD |
| mem timer | `/soc/timer@17420000`：`arm,armv7-timer-mem`，`clock-frequency=0x0124f800=19200000`；frame0 `0x17421000+0x1000`、`0x17422000+0x1000`，interrupts `[0,8,4,0,6,4]`；多数其他 frame disabled |
| arch timer | 合并 FDT 未发现 `arm,generic-timer` 节点；虚拟定时器 IRQ 和运行频率未确认。mem timer 的 19.2 MHz 不得替代实机 `CNTFRQ_EL0` 读取 |
| console UART | `/soc/qcom,qup_uart@99c000`：`qcom,msm-geni-console`，`0x0099c000+0x4000`，interrupts `[0,608,4]`，status=`ok`；Android bootargs 为 `console=ttyMSM0,115200n8` |
| 另一 UART | `/soc/qcom,qup_uart@894000`：`0x00894000+0x4000`，interrupts-extended 原始 `[1,0,587,4,60,79,4]`；不是当前 console 证据 |
| UFS | `/soc/ufshc@1d84000`：`ufs_mem 0x01d84000+0x3000`，`ufs_ice 0x01d88000+0x8000`，`ufs_ice_hwkm 0x01d90000+0x9000`；interrupts `[0,265,4]`，status=`ok` |

派生映射仅作记录：UFS SPI 265 → GIC INTID 297；console SPI 608 → 640。时钟、复位、regulator、PHY、ICE 依赖和实际可访问性尚未形成可启动驱动闭环，不能因为 status=`ok` 就宣称 XNU UFS 已工作。

### 4.3 显示、触控与保留内存

| 项目 | 本机证据与限制 |
|---|---|
| MDP | `/soc/qcom,mdss_mdp@ae00000`：`0x0ae00000+0x84000`、`0x0ae80000+0x2008`、`0x0ae7f800+0x800`；interrupts `[0,83,4]` |
| 当前面板 | 实时 cmdline 选择 `qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd`；1240x2772，60/90/120/144 Hz timings，DSC，physical 70x156，vendor `TM_NT37705_DVT` |
| 触控 | `/soc/spi@990000/synaptics_tcm@0`，compatible `synaptics,s3910`；与 cmdline `synaptics-s3910` 对应 |
| splash 保留区 | `/reserved-memory/splash_region`，label=`cont_splash_region`，`0x00000000b8000000+0x02b00000` |
| 帧缓冲限制 | 上述保留区不证明当前 active framebuffer base、stride 或 pixel format；这些值仍为未知，禁止套用 sweet/yudi |
| 日志/崩溃保留区 | `uefi_log_region 0x808e4000+0x10000`、`xbl_dtlog_region 0x80600000+0x40000`；ramoops size=`0x240000`。完整保留区在 JSON/文本转储中 |

本阶段没有采用任何固件文件路径；后续若需要 firmware，必须另从本机 DTB、匹配官方 OTA 或 Qualcomm 公开 SM8475 源码逐项补证。

## 5. 参考源码结论与隔离清单

详见 `repository-audit.md`。固定 commit：ios-sweet `45263bee…`、UniXNU `519d802…`、edk2-msm `e195262…`、darwin-xnu-build `6639065…`。只有 edk2-msm 存在 SM8475 SoC 目录，且唯一设备是 Xiaomi yudi；四个仓库都没有 senna-b/RMX3706 直接支持证据。

以下值/流程明确隔离，不得进入 senna-b 构建配置：

1. edk2-msm 示例 `FD_BASE=0xCE000000`、`FD_SIZE=0x02000000`，以及 yudi 的 2880x1800 和其他机型参数。
2. ios-sweet 的 SM7150 平台常量、rootfs tweaks；其“修改 rootfs 才能启动”的路径违反本项目一字节不改约束。
3. UniXNU 其他 SoC/机型的 memory map、timer、GIC、UFS、显示或固件参数。
4. 本机 `dtb_addr=0x01f00000` 和 splash 保留区虽真实存在，但语义分别是 Android 打包地址和保留区，不得擅自提升为 UEFI/XNU 加载地址或活动帧缓冲参数。

## 6. 已完成 / 未完成

### 已完成

- 验证输入哈希，解析 boot、vendor_boot、DTBO 和实时 FDT；16 个 overlay、3 个 vendor base、1 个实时 FDT 全部保留。
- 精确关联 entry 11 / Senna B，保留原始二进制、文本、偏移、哈希和选择依据。
- 建立本机内存、PSCI、GIC、PDC、timer、UART、UFS、MDP、面板、触控和关键保留区证据表。
- 固定并审计四个参考仓库 commit，记录真实机型范围、构建 pin 和禁止复用参数。

### 未完成 / 下一阶段前必须保持的未知项

- 未证明 bootloader 对三个 vendor base 的实际选择算法；以实时合并 FDT 为当前权威来源。
- 未获得 active framebuffer base/stride/format，未读取目标启动环境的 arch timer CNTFRQ/IRQ，未验证 PSCI/UART 在移植运行级别的可用性。
- 未建立 senna-b UEFI 设备包，未编译 XNU，未制作 shim/boot 镜像，未执行 `fastboot boot`。
- 本机无可用 Git、WSL/dtc；文本转储不是 dtc 编译结果。参考仓库通过 API/raw 文件固定版本保存，不冒充完整 git checkout。
- 阶段 0 的匹配官方全量 OTA、EDL 救砖验证、原版 rootfs 获取与哈希核验仍未完成。

## 7. 阶段验收

通过项仅限于：镜像结构自洽、DTB 完整、senna-b overlay 关联、本机关键参数可追溯、参考 commit 与支持范围明确、未知值没有被猜测。验收脚本及结果见 `validate_stage1.py`、`validation-results.json`；全目录哈希见 `SHA256SUMS.txt`。

**下一阶段建议：先做最小引导链的主机侧设计与可复现构建环境，逐项关闭上述未知项；在设计、回滚方案和验收日志未齐备前，不生成或执行实机启动。**