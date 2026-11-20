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

### C.2 senna 诊断 shim（无 XNU，纯探测 + 画屏）

**状态：源码与镜像已就绪（2026-11-20），未上机。**

- **目标**：用我们自己的 boot.img 在 senna 上跑起 shim，验证 §2.1 常量与 §6 未证项。
- **已有产物**（`build-chain/work/senna-shim/`，CI run 44677167822）：
  - `senna-shim-v4.img` 86,016 B（header v4，os_version `0x18000177`，sha256 `c0b8762d…fb23`）；`senna-shim-v2.img`（kernel_addr `0x8000`、ramdisk_addr `0x1000000`、tags `0x100`，sha256 `71c5ab9c…2dbda`）——v4 失败时换 v2 重试；
  - raw Image 已按 arm64 头 `image_size`（`0x14000`）补齐，入口 `_head` 的 `b _start` 由 `--check-image` 校验；
  - 源码：`start.S`/`shim.ld`（复用 sweet）、`board.h`（常量带 DTB 行号）、`console.c/h`、`senna.c`（探测 + 画屏 + panic 页 + PSCI 复位）、`tools/mkbootimg_img.py`（v4/v2 打包 + 头校验）。
- **实机时间线**（shim v0.2 固定）：0-20 s 信息页（PSCI 版本、CNTFRQ、MPIDR/Aff、CurrentEL、GICD/GICR TYPER、DTB magic、ramdisk、IMEM restart reason；20 s 便于拍全）→ 20-60 s 四组帧缓冲候选各 10 s（组号 + RED/GREEN/BLUE/WHITE 四色条，用于判 stride 与 R/B 交换）→ 60-80 s 倒计时 → `PSCI_SYSTEM_RESET` 回 Android；任何异常进红底 PANIC 页（slot/ESR/FAR/ELR/SPSR/SP/x0-x7）并停住。屏幕标题行含 `v0.2`，用于区分镜像版本。
- **验收**：屏上出现信息页；四组中恰有一组几何与颜色正确（记录组号 → stride/format）；CNTFRQ = 19,200,000、GICv3、DTB magic = `0xd00dfeed`、ramdisk 命中任一项即算补证；70 s 后自动重启回 Android；`fastboot getvar all` 无变化。
- **失败日志**：屏不亮 → fastboot 输出 + 照片 + 试过的镜像版本；屏花 → 记录组号与候选表；卡死 → 长按电源 10 s，记录卡死前屏幕。

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
| 帧缓冲基址 / stride / 像素格式 | 只有 splash 区 `0xb8000000+0x2b00000` 与面板 1240×2772；stride/格式未证 | C.2 依次试 `base=0xb8000000` × `stride∈{4960, 5120, 4992}` × `format∈{RGBA8888, BGRA8888}`，每组画编号色块；能看见且方向正确即定案 |
| VTIMER/PTIMER INTID（EL1 可用 PPI） | sweet 用 19/18，senna 无出处 | C.2 逐候选 {19,18,27,26,30,29,14,11} 使能 + `cntv_tval_el0=1ms`，看 `icc_iar1_el1` 是否命中；命中即记录 |
| `CNTFRQ_EL0` | DTB 给 19,200,000 | C.2 直接读寄存器，与 DTB 对照 |
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

## 10. 待办（按顺序）

1. [C.1] 用户确认 + 设备进 bootloader + `fastboot boot` 官方 boot.img，记录 §8 日志。**阻塞：设备未连接（`adb devices`/`fastboot devices` 空）。**
2. [C.2] ~~建 `build-chain/work/senna-shim/`，替换常量、加 FB/VTIMER 探测与自动重启~~ 完成（源码见该目录）。
3. [C.2] ~~交叉编译 + CI 出镜像~~ 完成（run 44677167822，v4/v2 双镜像）。
4. [C.2] 实机：`fastboot boot` senna-shim（先 v4，失败换 v2），拍屏判读四组候选 → 回填 §6 与 `REMAINING.md`。**阻塞：设备 + 用户确认。**
5. [C.3] `mkadt.py` senna 参数落地（每个值在本文件 §2 有出处）。
6. [B 剩余] 帧缓冲 stride/format、CNTFRQ、GIC 中断实测结果回填本文件与 `REMAINING.md`。
