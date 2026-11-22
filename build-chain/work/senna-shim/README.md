# senna-shim —— senna-b 引导链诊断垫片（RAM only）

对应 `build-chain/boot-chain/DESIGN.md` 的 C.2：先用一个**只读探测 + 文本回写 + PSCI 复位**的
垫片，把「`fastboot boot` 在 RMX3706 上到底能不能跑起我们自己的 Image」以及若干未证参数
一次性测出来。**不写任何分区。**

## 为什么不再画屏（v0.4 的结论）

v0.2/v0.3 把探测结果画在 ABL 的 splash 帧缓冲（`0xb8000000`），实机连跑 4.5 分钟，
屏幕**始终停在 ABL 开机 logo**——但设备随后准点 `PSCI_SYSTEM_RESET` 回 Android，
说明代码执行到了最后一行，只有显示不可见。

根因：senna 面板是 DSI **command mode + DSC**
（`build-chain/artifacts/dts-roundtrip/from-binary.dts:16` 的 bootargs 里
`msm_drm.dsi_display0=qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd`）。
ABL 只把一帧推给面板自带 GRAM，之后没有持续扫描输出，所以往 splash 区写像素永远不会被读到。
→ 结论：XNU 要上屏必须先有 DPU + DSI + DSC 驱动，写 splash 一条路走不通。

v0.4 因此改为走 **ramoops 文本通道**：把结果写进 ramoops 控制台区，下一次 Linux 启动时
`/sys/fs/pstore/console-ramoops-0` 就能读到（本机 dmesg 实测
`ramoops: using 0x240000@0xa7a5c0000, ecc: 0`，两次重启地址相同）。

## 它要回答的问题（pstore 里的字段）

| 问题 | 字段 | 判读 |
|---|---|---|
| ABL 是否接受 `fastboot boot` 的 v4 容器 | 能否读到 `SENNA SHIM v0.4` | 读到 = 接受；`FAILED (remote: ...)` = 拒绝 |
| ABL 是否给 x0 传有效 DTB | `DTB` / `MAGIC` | magic=0xD00DFEED 才是有效 FDT |
| 当前异常级 / 是否 EL1 | `EL` | `0x...4` = EL1 |
| 架构定时器频率 | `CNTFRQ` | 期望 `0x0124F800`（19.2 MHz，DTB :7481-7487） |
| PSCI 版本 | `PSCI` | 期望 `0x00010000`（1.0，DTB :1197-1199） |
| GIC 版本 | `GICD_PIDR2` | bit[7:4]=3 → GICv3 |
| Redistributor 是否存在 | `GICR_TYPER0` / `_HI` | 非 0/全 F 即存在 |
| 系统寄存器 GIC 接口 | `ICC_SRE` / `ICC_CTLR` | SRE=1 → 可用 |
| ABL 有没有把 ramdisk 放到 `0x1000000` | `RD_1000000` | 非 0 → 有内容 |
| IMEM restart reason 可读性 | `IMEM_RR_146AA65C` | 用于判断能否当把手 |
| splash 区可读写性 | `FB_RW` | 1 = 读回一致（写进去了但看不见） |

## 组成

| 文件 | 作用 |
|---|---|
| `start.S` | arm64 Linux Image 头（`_head`）+ 入口（`daifset`、`spsel #1`、`vbar_el1`、清 bss）+ 16 个异常向量 |
| `shim.ld` | 链接脚本：`. = 0`、8×4K 二级栈、`_end` 供 Image 头使用 |
| `board.h` | senna 常量，**每条都带 DTB 行号出处**（见文件内注释） |
| `console.c/.h` | splash 帧缓冲上的 8×16 位图字（×3）；v0.4 仍保留，但页面不可见 |
| `senna.c` | 探测 → 组文本 →（`SENNA_RAMOOPS_WRITE=1`）写 ramoops → `wait_ms(SENNA_D0_HOLD_MS)` → `PSCI_SYSTEM_RESET` |
| `font.h` | 8×16 ASCII 字模（从 ios-sweet shim 复用） |
| `tools/mkbootimg_img.py` | 纯 Python 打 Android boot.img：`--version 4`（首选）/ `--version 2`（回退），并可 `--check-image` 校验 Image 头 |
| `build.sh` | 交叉编译 + 打包 + sha256 |

## ramoops 写入方式

`persistent_ram_buffer = { u32 sig=DBGC; u32 start; u32 size; u8 data[] }`，
结果文本紧跟在 12 字节头之后。DT 的 `ramoops_region`（`from-binary.dts:381-389`）**没有 reg**，
base 由 Linux 启动时分配（实测稳定在 `0xa7a5c0000`），所以 `ramoops_write()` 在
`base ± 2 MiB` 内每 4 KiB 页都盖一份同样的头+文本，让真正被保留的那页命中。
区域配置：`size=0x240000`、`console-size=0x40000`、`pmsg-size=0x200000`、**无 ECC**、无 record-size。

## v0.6spin（D0 保持构建）

只为一件事存在：判 U1——`fastboot boot` 之后，ABL 留下的 fastboot gadget 还在不在。

- `SENNA_RAMOOPS_WRITE` 置 0，ramoops 写入整段编译掉（D0 阶段不写任何内存）。
- 探测照跑，`draw_info()` 照画（仍然不可见，留着只为异常时红屏一致）。
- `wait_ms(120000)`：**2 分钟静置**，给主机侧 `build-chain/tools/usb_watch.py` 足够样本，然后 `PSCI_SYSTEM_RESET` 回 Android。
- 判读：`usb_watch.py` 返回 A（gadget 仍在，走路径 A 复用 EP1）/ B（消失，走路径 B 自己重建）/ C（有应答，直接抓）。
- 这是**一次性**构建；D0 结束后把 `SENNA_RAMOOPS_WRITE` 改回 1 再做 v0.7。

## 构建

本机没有 `clang`/`gcc`，正式构建走 GitHub Actions：

```bash
gh workflow run senna-shim -R awadmw/senna-b-port
gh run watch
gh run download <run-id> -n senna-shim-images -D build-chain/work/senna-shim/out
```

有交叉工具链的机器上等价于：

```bash
cd build-chain/work/senna-shim
CROSS=aarch64-linux-gnu- bash build.sh
```

产物：

- `out/senna-shim-v4.img` —— **首选**，与真机 stock `boot.img` 同为 v4 头。
- `out/senna-shim-v2.img` —— 回退（ios-sweet 用的容器），若 v4 被 ABL 拒绝再试。
- `out/shim.bin` —— 裸 Image，`--check-image` 会校验 branch/text_offset/image_size/flags/magic。

## 实机步骤

```bash
adb reboot bootloader
fastboot boot build-chain/work/senna-shim/out/senna-shim-v4.img
# 约 5 s 后设备自动重启回 Android
adb shell su -c "cat /sys/fs/pstore/console-ramoops-0"
```

时间线：探测（< 1 s）→ 写 ramoops → 3 s → `PSCI_SYSTEM_RESET` → 回 Android。
若发生异常：走 `SENNA SHIM PANIC` 红屏（不可见）→ `wfe` 停住，长按电源键恢复。

## 安全边界

- 只写 splash 帧缓冲（`0xb8000000`）+ ramoops 控制台区 + CPU 通用寄存器；
  **不写 IMEM、PMIC、UFS、分区表**。
- 结束用 PSCI `SYSTEM_RESET`（DTB 已证 PSCI 1.0）；若返回失败则停住 `wfe`。
- `fastboot boot` 不刷分区，断电即恢复原状。
