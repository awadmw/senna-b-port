# C.2b-UART：用 GENI 串口做 shim 反馈通道（设计 v1，2026-11-22）

状态：**离线设计完成，未上机**。全部寄存器偏移与序列来自 Linux v5.10 源码（`torvalds/linux` tag `v5.10`：
`drivers/tty/serial/qcom_geni_serial.c`、`drivers/soc/qcom/qcom-geni-se.c`、`include/linux/qcom-geni-se.h`），
地址/引脚来自本机 DTB 反编译产物 `build-chain/artifacts/dts-roundtrip/from-binary.dts`。**没有套用任何其他机型数值。**

## 1. 目的与范围

C.2 的画屏、ramoops/pstore、`/proc/kcore`、`/dev/mem` 四条回读路线全部关闭（见 `DESIGN.md` §5/§9）后，
本文件定义「shim 用 UART 打日志」这一条通道的完整方案：寄存器序列、未知项探测法、分阶段验收、失败判读。
范围只到「shim 能把 12 行 `TAG` 打到串口」为止；XNU 侧串口不在此文范围。

## 2. 已证事实

| 项 | 值 | 出处 | 状态 |
| --- | --- | --- | --- |
| 串口节点 | `qcom,qup_uart@99c000`，`compatible = "qcom,msm-geni-console"`，`reg = <0x99c000 0x4000>` | `from-binary.dts:13812-13825` | 证 |
| 中断 | `interrupts = <0x00 0x260 0x04>` → **SPI 608**，level-high | 同上 `:13816` | 证 |
| 时钟 | `clocks = <0x24 0x64 0x24 0x86 0x24 0x87>` → `GCC_QUPV3_WRAP0_S7_CLK`(100) / `GCC_QUPV3_WRAP_0_M_AHB_CLK`(134) / `GCC_QUPV3_WRAP_0_S_AHB_CLK`(135) | 同上 `:13817-13818`；ID 名以 `include/dt-bindings/clock/qcom,gcc-sm8450.h`（v6.6）为准 | 证（ID 名，编号经 mainline 表核对一致） |
| 引脚 | `qupv3_se7_2uart_active`：`pins = "gpio26","gpio27"`、`function = "qup7"` | `from-binary.dts:2573-2584` | 证 |
| 控制台声明 | `stdout-path = "/soc/qcom,qup_uart@99c000:115200n8"` | `from-binary.dts:17` | 证 |
| 内核实际状态 | cmdline 有 `msm_geni_serial.con_enabled=0`；`/dev/ttyMSM*` 不存在；`/proc/consoles` 只有 `ramoops-1` | 实机 `/proc/consoles`、cmdline | 证（内核没接管） |
| 引脚复用基址 | `pinctrl@f000000`（`from-binary.dts` 节点），TLMM 具体 cfg 寄存器偏移**未查证** | 同上 | 部分证 |

## 3. 三个未知（先探测，不要假设）

1. **SE 有没有时钟/上电**：ABL 是唯一可能初始化过它的一方（`stdout-path` 指向它）。判据：读
   `0x99c000 + 0x68`（`GENI_FW_REVISION_RO`，`qcom-geni-se.h:69`）与 `0x99c000 + 0xe24`（`SE_HW_PARAM_0`）。
   两者都是 0 或全 `F` → SE 没有时钟（或访问被 NoC 拦），必须先解决 GCC 侧。
2. **引脚当前复用状态**：若 ABL 已把 GPIO26/27 设成 qup7，则不用碰 TLMM；否则要写 TLMM（偏移待查，**不许猜**）。
3. **115200 对应的 clk_div**：驱动算法见 §5.3；实机应直接读回 `GENI_SER_M_CLK_CFG`（`0x48`）判断 ABL 配的采样率和分频。

## 4. 分阶段计划

### U1：只读探测（零写，先上机一次）

- 目标：确认 SE 是否可用，拿到 `FW_REVISION_RO`/`STATUS`/`HW_PARAM_0`/`SER_M_CLK_CFG` 四个值。
- 做法：shim 里只做 32 位 load（`ldr w`，`Device-nGnRnE` 映射），每个读之前设一个计数上限的忙等，读到可疑值立刻停；
  结果仍按老办法写进 `TAG` 行（此时还没有输出通道，所以这轮的价值是**排除法**：如果读 SE 寄存器直接把设备挂死，
  说明 SE 没时钟且访问会卡总线，UART 路线作废，转 C.2c DWC3）。
- 验收：设备能自动 `PSCI_SYSTEM_RESET` 回 Android（说明读没卡死），且 4 个值不像 0/全 F。
- 失败日志：`FAILED U1: hang after read 0x99c000+0x68`（若挂死，改写 DESIGN §9 决策）。

### U2：最小 TX（单个字符 'A' + CRLF）

- 前置：U1 通过。
- 做法：按 §5.1 + §5.2 顺序初始化（FIFO 模式，非 DMA），只发 `"SENNA UART OK\r\n"`，然后等 `M_CMD_DONE` 50 ms，
  最多重试 3 次，再 `PSCI_SYSTEM_RESET`。
- 验收：PC 串口（115200 8N1）收到该串；同时设备正常回 Android。
- 失败日志：记录 `SE_GENI_STATUS`(0x40)、`SE_GENI_M_IRQ_STATUS`(0x610)、`SE_GENI_TX_FIFO_STATUS`(0x800) 的读回值，
  以及是否发出过 `UART_START_TX`。

### U3：TAG 输出（正式通道）

- 做法：`probe_all()` 的 12 项结果 + `RAMOOPS_BASE` 换成 `uart_printf` 逐行输出，每行 `TAG <name> <hex>\r\n`；
  发完等 TX 完成再 reset。
- 验收：PC 端 12 行全部收到，值与 DTB/预期一致（例：`CNTFRQ` 应为 `0x124f800`）。
- 之后：按 `HANDOFF.md` §8 回填 `DESIGN.md` §6 与 `REMAINING.md`。

## 5. 寄存器与序列（全部来自 Linux v5.10）

基址 `SE = 0x99c000`（窗口 0x4000，DTB `:13814`）。

### 5.1 QUP 顶层（`qcom-geni-se.c` `geni_se_io_init`/`geni_se_irq_clear`/初始化）

| 偏移 | 名字 | 写什么 | 出处 |
| --- | --- | --- | --- |
| `0x24` | `GENI_OUTPUT_CTRL` | `0x7f`（`DEFAULT_IO_OUTPUT_CTRL_MSK = GENMASK(6,0)`） | `qcom-geni-se.c:107,143,222` |
| `0x28` | `GENI_CGC_CTRL` | 读-改-写，置 `DEFAULT_CGC_EN` | `:108,213-215` |
| `0x20` | `GENI_FORCE_DEFAULT_REG` | `BIT(0)`（`FORCE_DEFAULT`） | `:100-101,223` |
| `0xe18` | `SE_GSI_EVENT_EN` | `0` | `:138,206,228` |
| `0xe1c` | `SE_IRQ_EN` | 置 `GENI_M_IRQ_EN|GENI_S_IRQ_EN|DMA_TX/RX_IRQ_EN` | `:197-200` |
| `0x258` | `SE_GENI_DMA_MODE_EN` | 清 `BIT(0)`（强制 FIFO 模式） | `:202-204`、`qcom-geni-se.h:120` |
| `0x610`/`0x618` | M_IRQ_STATUS / M_IRQ_CLEAR | 清 `0xffffffff` | `:229` |
| `0x640`/`0x648` | S_IRQ_STATUS / S_IRQ_CLEAR | 清 `0xffffffff` | `:230` |
| `0x804`/`0x810`/`0x814` | RX 水位 | `rx_wm=2`、`rx_rfr = rx_fifo_depth-2` | `:253-254`、`qcom_geni_serial.c:93,927` |

### 5.2 UART 协议层与 FIFO 发送

| 偏移 | 名字 | 写什么 | 出处 |
| --- | --- | --- | --- |
| `0x268` | `SE_UART_TX_WORD_LEN` | 8 | `qcom_geni_serial.c:27` |
| `0x26c` | `SE_UART_TX_STOP_BIT_LEN` | 1 | `:28` |
| `0x25c` | `SE_UART_TX_TRANS_CFG` | 无校验时为 0（`UART_TX_PAR_EN` 不置） | `:26,1030-1032` |
| `0x294` | `SE_UART_RX_STALE_CNT` | `10*16=160`（`DEFAULT_BITS_PER_CHAR*STALE_TIMEOUT`） | `:60-61,890,904` |
| `0x700` | `SE_GENI_TX_FIFOn` | 每次写一个 32 位字（**小端打包 4 字节**，`BYTES_PER_FIFO_WORD=4`） | `qcom-geni-se.h:83`、`qcom_geni_serial.c:107,408-411` |
| `0x80c` | `SE_GENI_TX_WATERMARK_REG` | `DEF_TX_WM = 2` | `:91,389,433` |
| `0x270` | `SE_UART_TX_TRANS_LEN` | 本次要发的字节数（`\n` 会多算 1 个 `\r`） | `:29,309,429-434` |
| `0x600` | `SE_GENI_M_CMD0` | `UART_START_TX(0x1) << M_OPCODE_SHFT(27)` = `0x08000000` | `:78,310-311`、`qcom-geni-se.h:124` |
| `0x610` | `SE_GENI_M_IRQ_STATUS` | 轮询 `M_TX_FIFO_WATERMARK_EN(BIT30)`、`M_CMD_DONE_EN(BIT0)` | `qcom-geni-se.h:143,166` |
| `0x610` | `SE_GENI_STATUS` | BIT0 `M_GENI_CMD_ACTIVE`，用于判忙 | `:104` |
| `0x604` | `SE_GENI_M_CMD_CTRL_REG` | 出错时写 `M_GENI_CMD_ABORT` | `:322` |

发送一个字节的最小顺序（`poll_put_char` 原样翻译，`qcom_geni_serial.c:386-396`）：

```
w(TX_WATERMARK, DEF_TX_WM);
w(TX_TRANS_LEN, 1);
w(M_CMD0, UART_START_TX << 27);
poll(M_IRQ_STATUS & M_TX_FIFO_WATERMARK_EN);   // 上限 ~10ms
w(TX_FIFOn, byte);                              // 4 字节一个字，不足补 0
w(M_IRQ_CLEAR, M_TX_FIFO_WATERMARK_EN);
poll(M_IRQ_STATUS & M_CMD_DONE_EN);            // 1ms 粒度轮询
w(M_IRQ_CLEAR, M_CMD_DONE_EN);
```

### 5.3 波特率与时钟

- 驱动：`sampling_rate = 32`（QUP >= 2.5 版减半为 16），`clk_rate = get_clk_div_rate(baud, sampling_rate, &clk_div)`，
  `ser_clk_cfg = SER_CLK_EN | (clk_div << 4)` 写 `GENI_SER_M_CLK_CFG(0x48)`（`qcom_geni_serial.c:1000-1013`、`CLK_DIV_SHFT=4`）。
- 也就是说 **SE 的输入时钟必须由 GCC 提供**（§2 的 `GCC_QUPV3_WRAP0_S7_CLK`），我们只写分频。
  这是 U1 必须先探测的原因：裸机无法像内核那样走 `dev_pm_opp_set_rate`。
- 若 U1 读到 `SER_M_CLK_CFG` 非 0 且 `FW_REVISION_RO` 合理，则**沿用 ABL 的分频**，不重算。

## 6. 风险与回滚

- 读/写未上电的 SE 可能让 AXI 事务超时并挂死 CPU：**每次上机前记录「挂死也不变砖」**——只 `fastboot boot`，重启即回 `boot_b`。
- 不做任何 flash 写；不改用户空间；不改分区。
- 回滚：重启（长按电源）；若卡 fastboot，重跑 `fastboot boot boot-trimmed.img` 或断电重启。

## 7. 失败日志模板

```
[ ] U1: FW_REVISION_RO=0x____ STATUS=0x____ HW_PARAM_0=0x____ SER_M_CLK_CFG=0x____
[ ] U1: 是否挂死（设备是否自动回 Android / 手动重启）
[ ] U2: PC 端是否收到 "SENNA UART OK"（串口号、波特率、收到字节）
[ ] U2: TX 后 M_IRQ_STATUS=0x____ TX_FIFO_STATUS=0x____
[ ] U3: 收到行数 __/12，缺失行号 ____
```

## 8. 待办

1. 用户确认 UART 硬件可接触（拆机接 GPIO26/27 + GND）或已有 USB-TTL。
2. 写 `build-chain/work/senna-shim/uart.c`（U1 只读版）+ 上机；CI 走 `.github/workflows/senna-shim.yml`。
3. U1 通过后写 U2/U3。
4. TLMM 引脚复用寄存器偏移：只在 U2 失败且确认引脚未复用时才去查（`pinctrl@f000000`），**不许猜偏移**。
