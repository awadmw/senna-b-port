# SENNA 引导链设计（C 段）：从 ABL 到 shim 到 XNU

> 状态：草案 v1（2026-11-20）。本文件是 C 段的唯一设计依据，任何实机动作前先在此登记「目标/做法/验收/失败日志」。
> 约束（用户 m00002 指令）：用户空间一字节不改；只用 `fastboot boot`，不刷任何分区；寄存器/内存/中断/固件地址必须有本机 DTB、官方 OTA 或高通公开 SM8475 源码出处；无证据就停下列清单，禁止套用其他机型数值。

## 1. 目的与范围

- 目的：在真我 GT Neo5（RMX3706 / senna-b / SM8475）上，用 `fastboot boot` 把一个自建的 boot.img 拉起来，最终把控制权交给 XNU（ios-sweet 的 16.7.16 用户空间）。
- 范围（本阶段 C.1–C.2）：只证明「引导链机制」与「senna 硬件常量正确」，不碰 iOS 用户空间、不改分区、不写 GPT。
- 明确不做：不做 `fastboot flash`；不改 bootloader / vendor_boot / dtbo / vbmeta；不动 `/persist`、`/modem`、`/recovery`。

## 2. 已验证事实（证据表）

### 2.1 平台/内存（来源：实机 live DTB）

| 项 | senna 值 | 出处 | 状态 |
| --- | --- | --- | --- |
| root model | `Qualcomm Technologies, Inc. Cape MTP, Senna B` | `build-chain/artifacts/dts-roundtrip/from-binary.dts` root 节点 | 证（DTB） |
| DRAM 段 | `0x80000000+0x6a000000`、`0xf1400000+0x0ec00000`、`0x8_00000000+0x39900000`、`0x9_00000000+0x18000000`、`0x8_40000000+0xc000000`，合计 12,655,263,744 | `from-binary.dts:21-25` `/memory` reg；`stage-01-platform-evidence/STAGE1-REPORT.md:66-72` | 证（DTB） |
| GICD | `0x17100000`，长度 `0x10000` | `from-binary.dts:1323-1331` `interrupt-controller@17100000` reg | 证（DTB） |
| GICR | `0x17180000`，长度 `0x200000`；`redistributor-stride = 0x40000`，`#redistributor-regions = 1`（8 核 × 0x40000） | 同上 `:1328-1330` | 证（DTB） |
| GICv3 ITS | `0x17140000+0x20000` | 同上 `:1334-1339` | 证（DTB） |
| CPU 数 | 8（`cpu@0/100/200/300/400/500/600/700`，`enable-method = "psci"`） | `from-binary.dts:492-`，`/cpus` | 证（DTB） |
| PSCI | `compatible = "arm,psci-1.0"`，`method = "smc"` | `from-binary.dts:1197-1199` | 证（DTB） |
| 架构 timer 频率 | `clock-frequency = 0x124f800` = 19,200,000 | `from-binary.dts:7481-7487` `timer@17420000`；`from-binary.dts:5883` `timer` 节点 | 证（DTB）+ 证（实机 dmesg：`arch_timer: cp15 and mmio timer(s) running at 19.20MHz (virt/virt)`） |
| 架构 timer PPI（EL1 可用） | secure-phys **13**、phys **14**、virt **11**、hyp **12**，全部 level-low（`0xff08`） | `from-binary.dts:5880-5886` `timer { compatible = "arm,armv8-timer" }` | 证（DTB）；实机 dmesg 输出 `GICv3:arch_timer(11)` 与 virt=11 一致 |
| timer frame 0 | `frame@17421000`，regs `0x17421000+0x1000` / `0x17422000+0x1000`，`interrupts = <0 8 4 0 6 4>` | `from-binary.dts:7490-` | 证（DTB）；这是 EL2/hyp 视角的 SPI 编号，**不是** EL1 下可用的 PPI 号 |
| UART 控制台 | GENI SE `0x99c000` + `0x4000`，`qcom,msm-geni-console`，`interrupts = <0 0x260 4>`（SPI 608），**引脚 GPIO26(TX)/GPIO27(RX)，function `qup7`**；`stdout-path = "/soc/qcom,qup_uart@99c000:115200n8"` | `from-binary.dts:2573-2584`（`qupv3_se7_2uart_pins`/`_active`）、`from-binary.dts:17` | `from-binary.dts:13812-13825` `qcom,qup_uart@99c000`；bootargs `console=ttyMSM0` | 证（DTB），但 SE 需要时钟/GPIO 初始化，ABL 之后是否仍可用**未证** |
| IMEM | 基址 `0x146aa000`，`restart_reason@65c` → **`0x146aa65c`** | `from-binary.dts:12935-12950` | 证（DTB）；与 sweet 常量数值相同属巧合，senna 有独立出处 |
| UFS host | `ufshc@1d84000`，`compatible = "qcom,ufshc"`，PHY `qcom,ufs-phy-qmp-v4-cape` | `from-binary.dts:12729`、`from-binary.dts:426`（alias `ufshc1`） | 证（DTB） |
| splash 区 | `splash_region` = `0xb8000000 + 0x2b00000`（45,088,768），label `cont_splash_region` | `from-binary.dts:412-416` | 证（DTB）；**帧缓冲基址/stride/像素格式本身未证**（见 §6） |
| 面板分辨率 | 1240 × 2772（DSC cmd 面板，`qcom,mdss_dsi_oplus_senna_bc_nt37705_..._1240_2772_...`） | `from-binary.dts:14186`、`:21564-21569` | 证（DTB 面板名） |
| 帧缓冲理论大小 | 1240 × 2772 × 4 = 13,749,120 字节；按 32 位对齐 stride 4960 | 由 DTB 分辨率推算 | 推算（未证） |

### 2.2 boot.img / vendor_boot（来源：官方 OTA）

| 项 | 值 | 出处 |
| --- | --- | --- |
| boot.img magic / 版本 | `ANDROID!`；`header_version = 4`（偏移 40） | `build-chain/ota-evidence/boot.img`，`:40` |
| kernel | 46,634,324 字节；头 `4D 5A 00 91` = arm64 Linux Image（code0 = 0x91005A4D） | 偏移 0x1000 |
| ramdisk | 1,698,305 字节；头 `02 21 4C 18` = LZ4 legacy magic `0x184C2102` | 偏移 `0x2c7b000` |
| header_size | 1584；page 4096；文件 0xC000000 | `:20` |
| vendor_boot | `VNDRBOOT`，header_version 4；`kernel_addr 0x8000`、`ramdisk_addr 0x1000000`、`tags_addr 0x100`、`dtb_size 0`、`vendor_ramdisk_size 19,416,683` | `build-chain/ota-evidence/vendor_boot.img` |
| vendor_boot cmdline | `video=vfb:640x400,bpp=32,memsize=3072000 msm_geni_serial.con_enabled=0 bootconfig buildvariant=user` | 同上 |
| vendor_boot 内嵌 FDT | 3 个，偏移 19,423,232 / 19,902,637 / 20,382,030（479,405 / 479,393 / 476,418 字节，ver 17） | 同上 |

**推论（有证据）**：本机 ABL 至少能解析 v4 boot image，且 kernel 位是 arm64 Linux Image——这与 ios-sweet `shim/start.S` 开头伪造的 arm64 Image 头（`b _start` … `ARM\x64`）一致。

### 2.3 `fastboot boot` 的支持性（当前结论：无静态证据）

| 镜像 | 大小 | 观察 |
| --- | --- | --- |
| `abl.img` | 221,184 | ELF32 ARM，entry `0x9fa00000`，唯一 LOAD 段 `0x1000→0x9fa00000` filesz 212,992，无 section 表，字节熵高（256 种字节值都出现）→ 加密/压缩；ASCII 字符串 338 条、0 条含 `fastboot` |
| `xbl.img` | 1,093,632 | ELF32，2,278 条 ASCII 字符串，0 条 `fastboot` |
| `uefi.img` | 3,153,920 | ELF64，11,849 条 ASCII 字符串，0 条 `fastboot`、0 条 `ANDROID!`；含 `DefaultBDSBootApp = "LinuxLoader"`、`PlatConfigFileName = "uefiplatLA.cfg"`、`Boot Device : UFS`、`UefiMemUseThreshold = 0x1900` |

结论：**镜像里读不出 fastboot 协议实现**（abl/xbl 被加密或压缩，uefi.img 是 Qualcomm EDK2 LinuxLoader 的配置/载荷）。因此 `fastboot boot` 是否可用必须实机验证，见 C.1。

## 3. 路线选择：复用 ios-sweet 的 shim（不做 edk2-msm）

| 方案 | 内容 | 优点 | 缺点 | 结论 |
| --- | --- | --- | --- | --- |
| A. clone edk2-msm 建 senna 设备包 | 走完整 UEFI → LinuxLoader → XNU | 与 Qualcomm 官方启动流程一致 | 需要大量固件/DXE 依赖、设备包从零写、sweet 上未验证过该路径；风险最高 | 不采用（本阶段） |
| B. 复用/移植 ios-sweet shim | ABL → `fastboot boot` shim → XNU | shim 本身就是一个 RAM-only boot.img，已在 sweet 实机跑通；不写分区；代码量约 40KB，全部可控 | 需替换 senna 常量并做帧缓冲/VTIMER 探测 | **采用** |

依据：ios-sweet README 记录 sweet 上已用同一机制跑起 16.7.16 用户空间（6/8 核、16K page、GICv3、UFS root、软件渲染），说明「ABL + fastboot boot + shim」这条链在骁龙 8 Gen 1 级别的机器上可行。senna 与 sweet 同为 SM8450 家族（SM8475 是 8+ Gen 1），差异集中在常量而非架构。

## 4. 引导链数据流

    ABL（原厂 bootloader，EL2/EL3 已配好 GIC、timer、MMU）
      └─ fastboot boot <shim-boot.img>        # 只进 RAM，不写分区
           └─ start.S: _start（arm64 Image 头，x0 = ABL 传入的 DTB 物理地址）
                ├─ daifset #0xf、spsel #1、设栈、vbar_el1、清 .bss
                └─ shim_main(x0)
                     ├─ console 初始化（senna：splash 帧缓冲 0xb8000000）
                     ├─ 打印/探测：CNTFRQ_EL0、PSCI 版本、GICD/GICR 可读性、DTB magic、ramdisk 位置
                     ├─ 定位 payload（ramdisk 内 "SWEETXNU" 结构）
                     ├─ 复制 XNU 各段 → ADT → boot_args（Video/deviceTreeP/CommandLine）
                     └─ 跳 entry_pa；XNU 接管（用户空间一字节不改）

回退路径：shim 不跳 XNU 时，延时后 `PSCI_SYSTEM_RESET` 回 Android；全程不写 flash。

## 5. 分阶段计划（每级先登记，判读日志后再进下一级）

### C.1 机制演练：`fastboot boot` 官方 stock boot.img（不涉及我们的代码）

- **目标**：证明本机 ABL 支持 `fastboot boot`，且 RAM 启动不会破坏分区。
- **做法**：
  1. 设备进 bootloader（关机后 电源+音量下），`fastboot devices` 应列出序列号；
  2. `fastboot getvar all` 存档（分区表/槽位/是否 unlocked）；
  3. `fastboot boot build-chain/ota-evidence/boot.img`；
  4. 观察：fastboot 侧输出、屏幕是否亮起并进入 Android（这是 RAM 里的官方 Android，不是刷机）；
  5. `fastboot reboot` 回正常系统。
- **验收**：fastboot 输出 `Sending 'boot.img' ... OKAY` + `Booting ... OKAY`；设备亮屏进 Android；`getvar all` 与步骤 2 存档一致；分区表未变。
- **失败日志（必须记录）**：fastboot 完整输出（含 `FAILED (remote: ...)` 文本）、屏幕照片、`fastboot getvar all` 前后 diff、设备序列号后 4 位、时间戳。若 `FAILED (remote: unknown command)` → 机制不可用，C 段改走 EDL/其它路线并停下汇报。

### C.2 senna 诊断 shim（无 XNU，探测 + 文本回读）

**状态：反馈通道判定完成（2026-11-22）——画屏证伪、ramoops/pstore 跨重启不持久、`/proc/kcore` 与 `/dev/mem` 均不可用 → 三条现成回读路线全部关闭。C.2 下一步是「重选输出通道」（见下文 C.2b），通道落地前不再做 shim 上机。**

- **目标**：用我们自己的 boot.img 在 senna 上跑起 shim，验证 §2.1 常量与 §6 未证项。
- **重大结论（2026-11-22，实机证伪）**：senna 的面板是 DSI **command mode** + DSC，bootargs 里写死 `msm_drm.dsi_display0=qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd`（`build-chain/artifacts/dts-roundtrip/from-binary.dts:16`）。ABL 只把一帧推给面板 GRAM，之后**没有持续扫描输出**，因此往 splash 区（`0xb8000000+0x2b00000`）写像素**永远不会显示**——除非先跑起 DPU+DSI+DSC 驱动。
  - 证据：v0.2/v0.3 跑满完整时长（v0.3 为 4.5 min）后自动 `PSCI_SYSTEM_RESET` 回 Android（uptime 从 0 重新计数），说明**代码执行链通**，但屏幕全程停在 ABL logo。
  - 对 C.3 的影响：XNU 要在 senna 上出画面，前置条件从「找到 FB 基址」升级为「**移植 DPU/DSI/DSC 驱动**」；在那之前，反馈通道只有 ramoops/pstore（本段正在打通）与 UART（SE 状态未证）。
- **当前反馈通道：ramoops → pstore**
  - senna 的 ramoops 由 Linux 启动时分配（DT 无 `reg`，`from-binary.dts:381-389`），实机 dmesg 稳定给出 `ramoops: using 0x240000@0xa7a5c0000, ecc: 0`（两次独立重启地址相同）。
  - 去掉 ECC 后 `persistent_ram_buffer` 的校验只剩 sig：`sig ^ (0 ^ PERSISTENT_RAM_SIG)` 必须为 0，即 DRAM 里 `sig = 0x43474244`（`fs/pstore/ram_core.c` `persistent_ram_post_init`）；头布局 `{u32 sig; u32 start; u32 size; u8 data[]}`。本机 `record_size` 为 0，console 区就落在区域基址（`0x240000 - 0x40000(console) - 0x200000(pmsg) = 0`）。
  - 内核用 `pgprot_noncached` 逐页 vmap 读取（`persistent_ram_vmap`），读的是真实 DRAM；所以只要 shim 把文本写进 DRAM 并清 cache 到 PoC，重启后 `/sys/fs/pstore/console-ramoops-0` 就会出现。
- **镜像版本与证据**（`build-chain/work/senna-shim/`，CI `.github/workflows/senna-shim.yml`）：
  - v0.3（屏显路线）：commit `3bbac9d`，CI run 44969357022；屏幕 4.5 min 内不可见 → 判伪。
  - v0.4（ramoops 首版）：commit `0b09995`，CI run 44970068008，`senna-shim-v4.img` sha256 `dd919a15c31d444e5854b8e3c6deee21b9eb1569c7f8f38c4d45b2700dcffbc6`；上机 `2026-11-22T01:10:31Z`，fastboot `Sending 84 KB OKAY` / `Booting OKAY`，30 s 回 adb、63 s `sys.boot_completed=1`，但 pstore 为空。
  - v0.5（加 `dc civac` 逐行清 cache + `dsb sy; isb`）：commit `20c95d3b4403`，CI run 44970517965，`senna-shim-v4.img` sha256 `a05c1136a35c4936b16103ec964400817d869d71330cf2b53cd49d29518ca47a`（v2 `eca04eddfa136184c1a214eac7a10323e92ecdb78a8b46dd9d5292abcd3935b3`）；上机 `2026-11-22T01:15:46Z`，fastboot 输出同上（`Total time: 0.789s`），之后 **adb 再未枚举**（USB 上只有 `CAPE-MTP _SN:78AD6B26`，VID_18D1&PID_4EE8，稳定 10 min 以上）→ 无法读 pstore，也无法判断是正常 reset 还是看门狗复位。
- **验收（已作废）**：~~shim 跑完后 `/sys/fs/pstore/console-ramoops-0` 出现 `SENNA SHIM v0.x` 文本~~——ramoops 已判定不持久（C.2b），此验收不再适用；改由 C.2b 选定通道的验收替代。
- **取证脚本**：`build-chain/tools/pstore-dump.sh`（设备侧读 pstore/last_kmsg）、`build-chain/tools/kcore-read.sh` + `build-chain/tools/kcore_phys.py`（绕开 pstore，直接从 `/proc/kcore` 线性映射 `PAGE_OFFSET+phys` 校验 `0xa7a5c0000` 是否被写入）。
- **失败日志**：fastboot 完整输出（注意 v0.5 那次真输出落在 `.fastboot.err`，`.fastboot.log` 为 0 字节）、设备回 Android 耗时、pstore 目录列表、adbd 是否恢复；卡死 → 长按电源 10 s 并记录。

### C.2b 输出通道重选（当前唯一阻塞点）

**目标**：给 shim（以及将来的 XNU）找一条「裸机写 → 主机读」的可靠通道。
**做法**：先把所有不依赖硬件的候选逐一证伪，再按成本排序；上机前每条通道都要有可离线复现的写入/读取脚本。
**验收**：主机能完整读回 shim 的 12 行 `TAG <hex>`，且同一通道在 XNU 阶段可复用（或明确记录不可复用）。

已证伪的候选（2026-11-22，均有实机证据）：

| 候选 | 判据 | 结论 |
| --- | --- | --- |
| splash 帧缓冲 | v0.2/v0.3 跑满 4.5 min 屏幕仍在 ABL logo；面板名带 `_dsc_cmd`（`from-binary.dts:16`） | 不可见（cmd-mode + DSC），需 DPU+DSI 驱动，代价最大 |
| ramoops/pstore | `build-chain/evidence/boot-attempts/20261122T022935Z-pmsg-persist.md`：`/dev/pmsg0` 写入 `write_ok`，重启后 `/sys/fs/pstore` total 0 | **不持久**（内核 console 与 pmsg 都写了，跨重启全丢） |
| `/proc/kcore` | `/proc/config.gz`：`CONFIG_PROC_KCORE is not set` | 不可用 |
| `/dev/mem` | `mknod /dev/mem c 1 1` 成功，但 `dd` 报 `No such device or address`；`/proc/config.gz`：`# CONFIG_DEVMEM is not set` | 不可用（内核没编 DEVMEM，与权限无关） |
| OPPO minidump | `ro.oplus.minidump.kernel.log.support=true`、`/sys/class/ramdump`、分区 `rawdump/logdump/logfs/xbl_ramdump_a`；但 `/data/persist_log/DCS/{de,en}/minidump` 与 `minidumpbackup` 均为空 | 只在崩溃时收集，且需内核先写 minidump 表；不能当常规输出 |

剩余候选（按成本/风险排序）：

1. **UART**：GENI SE `0x99c000`，GPIO26(TX)/GPIO27(RX)，115200n8，SPI 608（§2.1）。最省事最可靠；代价是需要接触主板测试点或专用调试线。
2. **裸机 USB device**：DWC3 `0xa600000`（`/sys/devices/platform/soc/a600000.ssusb`，驱动 `msm-dwc3`）+ QMP PHY（`88e8000.ssphy`）+ GCC 时钟/GDSC。不需额外硬件，成功后 shim 与 XNU 可共用一条控制台；代价是自写 USB 设备栈，且调试期本身「没有输出」，只能靠主机是否枚举来反馈。
3. **DPU+DSI+DSC 显示**：C.3 迟早要做（iOS 需要画面），但作为调试通道投入产出比最差，应排在串口/USB 之后。
4. **flash 草稿区**（`misc` 偏移 `0x800` 之后、`logfs` 等）：需要 shim 自带 UFS 栈（`ufshc@1d84000`），代价与 USB 相当，且属于分区写入，与 m00002 约束冲突 → 暂不考虑。

决策：**优先 UART**；若无法接触 UART 测试点，则启动「裸机 DWC3 控制台」子项目（C.2c）作为替代。通道落地前，C.2 的探测结果一律按「未读回」处理，不写进 §6 已证列。

**UART 通道的完整设计已单独成文：`build-chain/boot-chain/UART.md`（v1，2026-11-22，未上机）**——含 GENI SE 全部寄存器偏移（逐条标注 Linux v5.10 出处）、FIFO 模式发送序列、115200 分频算法、U1/U2/U3 三阶段验收与失败日志模板。

**失败日志**：候选证伪时记录判据命令与原始输出（如上表），不要只写结论。

### C.2c 裸机 DWC3 控制台（UART 不可接触后的替代路线）

**状态：设计稿 v1 完成（2026-11-22），未上机。完整设计见 `build-chain/boot-chain/USB-CONSOLE.md`。**

- **为什么是 USB**：它不是「理论上可用」，而是本机**刚刚用过**——ABL 的 fastboot 就跑在这套 DWC3 上（47,212 KB / 1.122 s）。
- **核心未知 U1（决定成本）**：ABL 跳转后 DWC3 是否仍留在「已枚举」状态。
  - 路径 A（继承，~200 行）：复用 ABL 已配好的 EP1 bulk IN，主机用 pyusb 直接读——**无需装驱动**。
  - 路径 B（重配 DWC3，~600 行）：PHY 沿用，重写 EP0 状态机直到重新枚举。
  - 路径 C（全量重建）：需要 GCC/GDSC/PMIC/eUSB2 repeater，**默认判为不可行**，只做评估。
- **D0 判据实验（零成本）**：`senna-shim-v0.6spin`（探测 → 不写 ramoops → 等 60 s → 复位）+ 主机侧 `build-chain/tools/usb_watch.py`。
  - 设备在场但 fastboot 不应答 → 路径 A；设备消失 → 路径 B；设备在场且应答 → ABL 未跳转，重测。
- **关键证据**：USB2 侧是 **eUSB2 PHY**（`hsphy@88e3000`，`qcom,usb-snps-eusb2-phy`，依赖外部 `usb-repeater`，`from-binary.dts:20953-20967`）；USB3/DP combo PHY（`ssphy@88e8000`）的**初始化序列与 13 项寄存器偏移表都直接写在 DTB 里**（`:20983-20984`），路径 B/C 不必从驱动反推。
- **验收**：D1 主机收到 `SENNA USB OK`；D2 收到 12 行 `TAG <hex>`（与 v0.4 的 payload 同格式）。
- **失败日志**：`evidence/boot-attempts/<UTC>-d0-usb-inherit.md` + `d0-usb-watch-<UTC>.csv`（含 `DSTS`/`DCTL`/`DEPCMD` 读回值）。
### C.3 XNU 接管（依赖 B 段剩余项）

- **目标**：shim 把 payload（XNU demo kernel + ADT）拉起，出现 XNU 早期日志（帧缓冲/串口二选一）。
- **前置（未完成，不得跳过）**：
  - `mkadt.py` 的 senna 版参数：dram-base/dram-size、GICD/GICR、UFS、timebase、VTIMER INTID、帧缓冲几何；
  - `xnu/senna/platform.sm8475.conf` 的 `RUNTIME_SUPPORT=not-implemented` 必须升级；
  - B 段：活动帧缓冲 stride/format 实测、CNTFRQ_EL0 与 GIC 中断实测、EDL 演练；
  - iOS 16.7.16 rootfs（userdata，用户已授权）与 `mkipsw` 道具链。
- **验收**：XNU 打印 `Boot args`/`AppleARMPE` 早期日志并停在可预期位置（不是静默重启）。
- **失败日志**：panic 文本（屏/串口）、`phys_base`/`mem_size`、payload sha256、ADT sha256。

## 6. 未证项与探测方法（有证据才写死，否则运行时探测）

| 项 | 现状 | 探测/替代方案 |
| --- | --- | --- |
| 帧缓冲基址 / stride / 像素格式 | **已降级为非阻塞**：面板是 DSI command mode + DSC，ABL 之后没有持续扫描输出，写 splash 区不可见（2026-11-22 实机证伪 v0.2/v0.3） | 不再靠画色块判 stride；要上屏必须先有 DPU+DSI+DSC 驱动（C.3 前置）。像素几何仍可留待 XNU 显示驱动阶段，用 DPU 寄存器读回 |
| VTIMER/PTIMER INTID（EL1 可用 PPI） | **已证**：phys 14、virt 11、secure-phys 13、hyp 12，level-low | `from-binary.dts:5882`（`arm,armv8-timer` interrupts），**不要**沿用 sweet 的 19/18 |
| `CNTFRQ_EL0` | **已证** 19,200,000（DTB `clock-frequency` + 实机 dmesg `arch_timer ... 19.20MHz`） | 无需再探测；XNU 侧按 19.2 MHz 配置 timebase |
| ramoops 物理地址与布局 | 地址 `0x240000@0xa7a5c0000` 稳定（`/sys/module/ramoops/parameters/mem_address=45002522624`），但**内容跨重启不保留** | 通道已关闭（C.2b）。若将来再次尝试，先解释「为什么内核自己每 boot 写 2 MB console 日志、重启后却一条都没有」 |
| 写入 DRAM 的可见性（cache） | v0.5 已加 `dc civac` 逐 64 B 行 + `dsb sy; isb`，pstore 仍为空 → 无法据此判断 MMU/cache 属性 | 随通道关闭而挂起；新通道（UART/USB）自带「写入即输出」，不再依赖 DRAM 跨 boot 保留 |
| PSHOLD 寄存器 | senna DTB 无 pshold 节点，**未证** | 不复用 sweet 的 `0x0c264000`；回退只用 `PSCI_SYSTEM_RESET`（PSCI 1.0 已证） |
| UART 控制台可用性 | 引脚 GPIO26/27、115200n8、SPI 608 已证（§2.1）；但 ABL 之后 SE 时钟/PHY 状态、以及物理测试点是否可接触**未证** | 作为 C.2b 首选通道：先在不改分区的前提下用 shim 直接配 GENI SE（`se-clk`/`m-ahb`/`s-ahb` + QUP wrapper）发一个字符，主机侧看是否收到 |
| ABL 是否把 x0 指向有效 DTB | 官方 kernel 需要它，故极可能为真 | C.2 打 DTB magic；无效则回退「扫描 `0x1000000` 起 32 MB 找 `SWEETXNU`」 |
| ramdisk 载入地址 | v4 头 `ramdisk_addr = 0x1000000` | 直接扫描该地址；命中 `SWEETXNU` 即定案 |

## 7. 回滚与安全

- 全程只用 `fastboot boot`（RAM 内），**不写任何分区**；`fastboot getvar all` 前后存档比对。
- 设备卡死：长按电源 10 s 强制重启；仍不行 → 电源+音量下进 bootloader，`fastboot reboot`。
- 不触碰 `/persist`、`/modem`、`/recovery`、bootloader 分区；不做 `fastboot flash`、不改 GPT。
- 用户空间（iOS rootfs）放到现成 userdata 分区是后续 C.3 的独立步骤，届时单独出方案 + 备份 + 用户确认。
- 每次实机动作前，本文件与 `HANDOFF.md` 都要写明「本次做什么、失败怎么退」。

## 8. 失败日志模板（每次实机动作复制一份到 `build-chain/evidence/boot-attempts/`）

    attempt: C.1-001
    date: 2026-11-2x HH:MM (UTC+8)
    image: build-chain/ota-evidence/boot.img
    image_sha256: <sha256>
    cmd: fastboot boot boot.img
    fastboot_stdout: |
      <完整输出>
    exit_code: 0
    screen: <照片文件名>
    getvar_before_after_diff: <none | 差异>
    post_reboot_android: ok | hang
    notes: <观察 / 猜测分开写>

## 9. 决策记录

- 2026-11-20：C 段路线定为复用 ios-sweet shim，不 clone edk2-msm（理由见 §3）；先做 C.1 机制演练，再做 C.2 诊断 shim；任何实机动作前需用户确认。
- 2026-11-20：boot.img 目标版本定为 v4（实机 OTA 已证 v4 可用），不再沿用 sweet 的 v2 假设；ramdisk 定位加 `0x1000000` 扫描回退，避免依赖 ABL 传 DTB。
- 2026-11-22：**画屏路线证伪**。senna 面板是 DSI command mode + DSC（`from-binary.dts:16` bootargs 面板名 `..._dsc_cmd`），ABL 之后没有持续扫描输出，写 splash 区不可见；v0.2/v0.3 代码确实执行到自动复位（uptime 归零、回 Android），屏幕却全程停在 ABL logo。→ C.2 反馈通道改为 ramoops/pstore；C.3 上屏前置升级为「DPU+DSI+DSC 驱动」。
- 2026-11-22：ramoops 通道选「直接写 `persistent_ram_buffer` 头」而不是伪造整块 ramoops 元数据。理由：本机 `ecc: 0`，校验只剩 `sig ^ PERSISTENT_RAM_SIG == 0`（`fs/pstore/ram_core.c:488-530`），只需 `{sig=0x43474244,start=0,size=len}` 三字段；内核用 `pgprot_noncached` 读真实 DRAM，绕开 cache 差异。
- 2026-11-22：v0.4（无 cache 清理）→ pstore 为空后，v0.5 **只加 `dc civac` + `dsb`，不动基址/扫描范围/文本格式**，保持单变量；若仍为空，下一步改成按 `SCTLR_EL1.M` 分支（MMU 关时不需要清理，说明问题在别处）。
- 2026-11-22：**ramoops 通道关闭**。终判依据：`/dev/pmsg0` 写入 `write_ok` + `sync`，`adb reboot` 后 `/sys/fs/pstore` total 0、marker 全无（`build-chain/evidence/boot-attempts/20261122T022935Z-pmsg-persist.md`）；同时 `init.oplus.debug.rc:816` 那句 `copy /sys/fs/pstore/console-ramoops-0 /data/debugging/last_kmsg.txt` 在每次启动都失败——说明**连 OPPO 自己都读不到这个文件**，不是 Android 删了它。
- 2026-11-22：**用户态直读物理内存的路线全部关闭**：`/proc/config.gz` 里 `CONFIG_PROC_KCORE is not set`、`# CONFIG_DEVMEM is not set`；`mknod /dev/mem c 1 1` 能建节点但 `dd` 报 `No such device or address`。以后不要再在 kcore/devmem 上花时间。
- 2026-11-22：**中断号以本机 DTB 为准**：`arm,armv8-timer` 给 PPI 13/14/11/12（`from-binary.dts:5882`），实机 dmesg 的 `GICv3:arch_timer(11)` 与 virt=11 对上；sweet 的 19/18 一律不采用。CNTFRQ 用 DTB `0x124f800` + dmesg `19.20MHz` 双证据定案。
- 2026-11-22：**输出通道优先 UART**，次选裸机 DWC3 控制台；显示驱动排最后（虽然 C.3 终局需要）；flash 草稿区因与「不刷分区」约束冲突而排除（详见 C.2b）。
- 2026-11-22：**UART 不可接触 → 定 C.2c 裸机 DWC3 控制台**。先做 D0 零成本观测再写代码：U1（ABL 是否留下已枚举 gadget）决定 200 行还是 600+ 行；路径 A 复用现成 fastboot 接口（主机已绑 WinUSB，免装驱动），不自己造 CDC-ACM。PHY 初始化序列直接取 DTB（`from-binary.dts:20984`）而不是从驱动反推。

## 10. 待办（按顺序）

1. [C.1] ~~`fastboot boot` 官方 boot.img~~ **通过（2026-11-22）**：`Sending 47212 KB OKAY [1.122s]` / `Booting OKAY [0.515s]`，9 s 回 adb、48 s `sys.boot_completed=1`；证据 `build-chain/evidence/boot-attempts/2026-11-22T01-00Z-c1-stock.md`。结论：senna ABL 支持 `fastboot boot`。
2. [C.2] ~~建 `build-chain/work/senna-shim/`，替换常量、加探测与自动重启~~ 完成（源码见该目录）。
3. [C.2] ~~交叉编译 + CI 出镜像~~ 完成（`.github/workflows/senna-shim.yml`，v4/v2 双镜像 + SHA256SUMS）。
4. [C.2] ~~画屏判读 FB/stride/format~~ **证伪并关闭**：cmd-mode 面板，ABL 后无扫描输出（§5 C.2 结论）。
5. [C.2] ~~pstore 回读~~ **通道关闭**：pmsg 终判不持久（`20261122T022935Z-pmsg-persist.md`）；kcore/devmem 也都不存在（`CONFIG_PROC_KCORE`/`CONFIG_DEVMEM` 均未开）。
6. [C.2b] **决策已完成（2026-11-22）**：UART 硬件不可接触（用户 m01641）→ 转 C.2c 裸机 DWC3 控制台。UART 设计 `build-chain/boot-chain/UART.md` 保留备查，不再推进。
6a. [C.2c] ~~设计稿~~ **v1 完成（2026-11-22）**：`build-chain/boot-chain/USB-CONSOLE.md`，含 DTB 证据表、DWC3 寄存器表（Linux v6.6 出处）、A/B/C 三条路径与 D0–D4 计划；主机侧观测器 `build-chain/tools/usb_watch.py` 已写并冒烟通过。
6b. [C.2c/D0] ~~出 `senna-shim-v0.6spin` 镜像~~ **已就绪（2026-11-22，CI run `44977828469`）**：`SENNA_RAMOOPS_WRITE=0` + `SENNA_D0_HOLD_MS=120000`，v4 sha256 `bb0a77605dcca97ccb33ed9824e36314c0abef0a6b5133ed0a4e56a294cb0caf`。**下一步**：与用户约 2 分钟窗口，先跑 `usb_watch.py --duration 150` 再 `fastboot boot`，判 U1（A 继承 / B 重建 / C 重测）。
7. [C.2] 通道打通后（A 或 B 路径任一成立）再上机回读 `TAG <hex>`，把 DTB magic、EL、GIC/PSCI/IMEM 等未证项一次性回填 §6。
8. [C.3] 与通道并行可做的离线工作：`mkadt.py` senna 参数落地、`xnu/senna/platform.sm8475.conf` 的 `RUNTIME_SUPPORT`、iOS 16.7.16 rootfs 与 `mkipsw` 道具链。
9. [B 剩余] CNTFRQ、GIC 中断已按 DTB + 实机 dmesg 回填（§2.1、§6）；仍待：EDL 演练、iOS 16.7.16 rootfs。