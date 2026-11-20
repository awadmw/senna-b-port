# senna-shim —— senna-b 引导链诊断垫片（RAM only）

对应 `build-chain/boot-chain/DESIGN.md` 的 C.2：先用一个**只读探测 + 画屏 + PSCI 复位**的
垫片，把「`fastboot boot` 在 RMX3706 上到底能不能跑起我们自己的 Image」以及若干未证参数
一次性测出来。**不写任何分区。**

## 它要回答的问题

| 问题 | 屏幕上的字段 | 判读 |
|---|---|---|
| ABL 是否接受 `fastboot boot` 的 v4 容器 | 是否出现信息页 | 出现 = 接受；`FAILED (remote: ...)` = 拒绝，改 v2/路线 |
| ABL 是否给 x0 传有效 DTB | `DTB x0 / magic` | magic=0xD00DFEED 才是有效 FDT |
| 当前异常级 / 是否 EL1 | `EL currentel` | 期望 `0x...4`（EL1） |
| 架构定时器频率 | `TIMER cntfrq` | 期望 `0x0124F800`（19.2 MHz，来自 DTB） |
| PSCI 版本 | `PSCI version` | 期望 `0x00010000`（1.0） |
| GIC 版本 | `GICD pidr2` | bit[7:4]=3 → GICv3 |
| Redistributor 是否存在 | `GICR0 typer lo/hi` | 非 0/全 F 即存在 |
| 系统寄存器 GIC 接口是否可用 | `ICC sre / ctlr` | sre=1 → 可用 |
| ABL 有没有把 ramdisk 放到 `0x1000000` | `RAMDISK @0x1000000` | 非 0 → 有内容（真机 OTA 已证 vendor_boot ramdisk_addr=0x1000000） |
| `fbcon`/splash 的 base/stride/像素格式 | 4 组配色页 + 底部彩条 | 见下方判读表 |

## 组成

| 文件 | 作用 |
|---|---|
| `start.S` | arm64 Linux Image 头（`_head`）+ 入口（`daifset`、`spsel #1`、`vbar_el1`、清 bss）+ 16 个异常向量 |
| `shim.ld` | 链接脚本：`. = 0`、8×4K 二级栈、`_end` 供 Image 头使用 |
| `board.h` | senna 常量，**每条都带 DTB 行号出处**（见文件内注释） |
| `console.c/.h` | 在 splash 帧缓冲上画 8×16 位图字（×3），运行期可切 stride / R-B 交换 |
| `senna.c` | 探测 + 画 4 组 FB 候选 + 30s 倒计时 + `PSCI_SYSTEM_RESET`；异常走同一套画屏 |
| `font.h` | 8×16 ASCII 字模（从 ios-sweet shim 复用） |
| `tools/mkbootimg_img.py` | 纯 Python 打 Android boot.img：`--version 4`（首选）/ `--version 2`（回退），并可 `--check-image` 校验 Image 头 |
| `build.sh` | 交叉编译 + 打包 + sha256 |

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

- `out/senna-shim-v4.img` —— **首选**，与真机 stock `boot.img` 同为 v4 头（kernel 46,634,324 / os_version 0x18000177 已由官方 OTA 实测）。
- `out/senna-shim-v2.img` —— 回退（ios-sweet 用的容器），若 v4 被 ABL 拒绝再试。
- `out/shim.bin` —— 裸 Image，`--check-image` 会校验 branch/text_offset/image_size/flags/magic。

## 实机步骤（需要设备在手 + 用户确认）

```bash
adb devices                      # 确认在线
adb reboot bootloader
fastboot devices
fastboot boot build-chain/work/senna-shim/out/senna-shim-v4.img
```

屏幕时间线（每次上电只跑一轮）：

1. `0–12 s`：信息页（PROBE 表）。
2. `12–40 s`：4 组帧缓冲候选，每组 7 s，页面底色不同 + 底部红/绿/蓝/白彩条。
3. `40–70 s`：信息页 + 30 s 倒计时，随后 `PSCI_SYSTEM_RESET` 自动重启。
4. 若发生异常：红底 `SENNA SHIM PANIC` 页显示 slot/ESR/FAR/ELR/SPSR 与 x0–x7，然后 `wfe` 停住。

## FB 判读表（拍照对照）

| 现象 | 结论 |
|---|---|
| 第 1 组（stride 4960，RGBA）文字清晰、彩条 R/G/B 顺序正确 | FB = base 0xb8000000，stride 4960，a8r8g8b8 |
| 第 2 组（同 stride，R-B 交换）反而正确 | FB 为 BGRA（`swap_rb=1`） |
| 第 3 组（stride 5120）清晰 | stride 5120（1240 行不紧凑，可能为对齐填充） |
| 第 4 组（stride 4992）清晰 | stride 4992 |
| 各组都呈对角斜纹 | stride 候选都不对 → 需要从 ABL/vendor 侧再取证 |
| 各组都不改底色，屏上仍是 Android/充电 logo | 写入没有落到面板：base 不对，或 ABL 已关闭显示电源 |
| 文字出现但颜色整体偏色 | 记下是哪一组 + 彩条实际颜色，回填 DESIGN.md |

## 安全边界

- 只写 splash 帧缓冲（`0xb8000000`，DTB 已证）+ CPU 通用寄存器；**不写 IMEM、PMIC、UFS、分区表**。
- 结束用 PSCI `SYSTEM_RESET`（DTB 已证 PSCI 1.0）；若返回失败则停住 `wfe`，长按电源键即可恢复。
- `fastboot boot` 不刷分区，断电即恢复原状；stock boot.img 仍可用同一命令再引导回去。
