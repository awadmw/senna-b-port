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
| 架构 timer 频率 | `clock-frequency = 0x124f800` = 19,200,000 | `from-binary.dts:7481-7487` `timer@17420000` | 证（DTB），运行时再用 `CNTFRQ_EL0` 交叉校验 |
| timer frame 0 | `frame@17421000`，regs `0x17421000+0x1000` / `0x17422000+0x1000`，`interrupts = <0 8 4 0 6 4>` | `from-binary.dts:7490-` | 证（DTB）；这是 EL2/hyp 视角的 SPI 编号，**不是** EL1 下可用的 PPI 号 |
| UART 控制台 | GENI SE `0x99c000` + `0x4000`，`qcom,msm-geni-console`，`interrupts = <0 0x260 4>`（SPI 608） | `from-binary.dts:13812-13825` `qcom,qup_uart@99c000`；bootargs `console=ttyMSM0` | 证（DTB），但 SE 需要时钟/GPIO 初始化，ABL 之后是否仍可用**未证** |
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

**状态：实机验证进行中（2026-11-22）。v0.1–v0.3 的「画屏」路线已判定不可行，改为经 ramoops/pstore 回读文本；v0.5 上机后 adbd 未恢复，取证被阻塞。**

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
- **验收**：shim 跑完后 `/sys/fs/pstore/console-ramoops-0` 出现 `SENNA SHIM v0.x` 文本，且 12 行 `TAG <hex>` 可解析；设备自动回到 Android；`fastboot getvar all` 无变化。
- **取证脚本**：`build-chain/tools/pstore-dump.sh`（设备侧读 pstore/last_kmsg）、`build-chain/tools/kcore-read.sh` + `build-chain/tools/kcore_phys.py`（绕开 pstore，直接从 `/proc/kcore` 线性映射 `PAGE_OFFSET+phys` 校验 `0xa7a5c0000` 是否被写入）。
- **失败日志**：fastboot 完整输出（注意 v0.5 那次真输出落在 `.fastboot.err`，`.fastboot.log` 为 0 字节）、设备回 Android 耗时、pstore 目录列表、adbd 是否恢复；卡死 → 长按电源 10 s 并记录。

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
| VTIMER/PTIMER INTID（EL1 可用 PPI） | sweet 用 19/18，senna 无出处 | C.2 v0.4/v0.5 已把候选逐个使能后的 `ICC_IAR1_EL1` 命中值写进 ramoops 文本；待 pstore 可读后回填 |
| `CNTFRQ_EL0` | DTB 给 19,200,000 | C.2 直接读寄存器写进 ramoops，与 DTB 对照（待回读） |
| ramoops 物理地址与布局 | 实机 dmesg 两次独立重启均为 `0x240000@0xa7a5c0000, ecc: 0`；DT 无 `reg`（`from-binary.dts:381-389`）→ 由内核启动时分配 | 地址确定性已证（同一地址跨重启）；但地址随内核分配策略可能变，shim 侧仍按「已知基址优先 + 扫描」处理，并在读到 pstore 后核对 |
| 写入 DRAM 的可见性（cache） | ABL 交给 shim 时 MMU 是否开启、映射是否 cacheable **未证**；v0.4 写入未清 cache → pstore 为空 | v0.5 加 `dc civac` 逐 64 B 行清理 + `dsb sy; isb`；若 v0.5 的 pstore 有内容即证「MMU 开着且 cacheable」 |
| PSHOLD 寄存器 | senna DTB 无 pshold 节点，**未证** | 不复用 sweet 的 `0x0c264000`；回退只用 `PSCI_SYSTEM_RESET`（PSCI 1.0 已证） |
| UART 控制台可用性 | GENI `0x99c000` 有节点，但 SE 时钟/GPIO 状态未知 | 本阶段不用 UART；若将来需要，先证 ABL 是否留下已初始化的 SE |
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

## 10. 待办（按顺序）

1. [C.1] ~~`fastboot boot` 官方 boot.img~~ **通过（2026-11-22）**：`Sending 47212 KB OKAY [1.122s]` / `Booting OKAY [0.515s]`，9 s 回 adb、48 s `sys.boot_completed=1`；证据 `build-chain/evidence/boot-attempts/2026-11-22T01-00Z-c1-stock.md`。结论：senna ABL 支持 `fastboot boot`。
2. [C.2] ~~建 `build-chain/work/senna-shim/`，替换常量、加探测与自动重启~~ 完成（源码见该目录）。
3. [C.2] ~~交叉编译 + CI 出镜像~~ 完成（`.github/workflows/senna-shim.yml`，v4/v2 双镜像 + SHA256SUMS）。
4. [C.2] ~~画屏判读 FB/stride/format~~ **证伪并关闭**：cmd-mode 面板，ABL 后无扫描输出（§5 C.2 结论）。
5. [C.2] **当前阻塞点**：v0.5 上机后 adbd 未恢复，pstore 读不到 → 需用户确认手机屏幕/解锁并让 adb 回来；随后跑 `build-chain/tools/pstore-dump.sh`，或先用 `kcore-read.sh`+`kcore_phys.py` 直读 `0xa7a5c0000` 判「数据是否进 DRAM」。
6. [C.2] 回读成功 → 把 `TAG <hex>` 12 行解析结果回填 §6 与 `REMAINING.md`（DTB magic、EL、CNTFRQ、GIC、PSCI、IMEM、splash 等）。
7. [C.3] `mkadt.py` senna 参数落地（每个值在本文件 §2 有出处），并在 C.2 回读补齐未证项之后。
8. [B 剩余] CNTFRQ、GIC 中断实测结果回填本文件与 `REMAINING.md`；EDL 演练、iOS 16.7.16 rootfs 另排。
