# C.2c 裸机 DWC3 控制台设计 v1

> 状态：设计稿（2026-11-22），**未上机**。
> 归属：C 段「输出通道」子项目。上位文档 `DESIGN.md`（路线选择）、`UART.md`（已放弃的 UART 路线，保留备查）。
> 前置结论：画屏（cmd-mode 面板）、ramoops/pstore、`/proc/kcore`、`/dev/mem` 四条通道全部关闭（见 `PROGRESS.md` 2026-11-22 各节）。

## 1. 目的与范围

**目标**：在 `fastboot boot` 之后、Android 内核尚未启动的裸机 shim 里，建立一条「设备 → 主机」的**单向**输出通道，把 12 项探测值（DTB magic、EL/MPIDR、SCTLR、CNTFRQ、GIC、PSCI、IMEM、FB 等）送到 PC 上。

**非目标（明确不做，防蔓延）**：
- 不做 ADB / fastboot 协议应答，不做双向交互，不做大吞吐。
- 不改用户空间任何一个字节，不刷任何分区（边界同 m00002）。
- 不碰 EUD（`qcom,msm-eud`，见 §3）——语义未证且 `qcom,secure-eud-en`，只作为 D4 的最后备选记录。
- 不为了这条通道去改 Android 内核配置（`CONFIG_PROC_KCORE` 等）。

## 2. 为什么是 USB

| 通道 | 结论 | 依据 |
|---|---|---|
| 画屏 | 关闭 | 面板 `..._dsc_cmd`（`from-binary.dts:16`），ABL 只推一帧进 GRAM，之后无扫描输出 |
| ramoops → pstore | 关闭 | pmsg 终判不持久（`evidence/boot-attempts/20261122T022935Z-pmsg-persist.md`） |
| `/proc/kcore` / `/dev/mem` | 不可用 | `CONFIG_PROC_KCORE` 未开、`/dev/mem` 不存在 |
| UART | 需要硬件接触 | 用户 m01641 决策：不可接触 |
| **USB** | **本机唯一已被证明可用的外设** | `fastboot boot` 47,212 KB 传输 1.122 s 完成（`2026-11-22T01-00Z-c1-stock.md`） |

关键判断：USB 不是「理论上可用」，而是**刚刚用过**——ABL 的 fastboot 就是跑在这套 DWC3 上的。所以问题不是「能不能驱动 USB」，而是「ABL 把 USB 交给我们时，它处于什么状态」。

## 3. 已证事实（全部有本机 DTB 行号）

| 项 | 值 | 出处（`build-chain/artifacts/dts-roundtrip/from-binary.dts`） |
|---|---|---|
| USB 控制器 | `ssusb@a600000`，`reg = <0xa600000 0x100000>` | `:20889-20895` |
| compatible | `qcom,dwc-usb3-msm`（外层）/ `snps,dwc3`（内层） | `:20890`、`:20919` |
| DWC3 核 | `dwc3@a600000`，`reg = <0xa600000 0xd93c>` | `:20918-20920` |
| 角色/速率 | `dr_mode = "otg"`、`maximum-speed = "super-speed-plus"` | `:20939-20940` |
| DWC3 中断 | SPI **133**（`<0 0x85 4>`，level-high） | `:20925` |
| wrapper 中断 | pwr_event SPI **130**（PDC）、ss_phy SPI **17**、dp_hs_phy SPI **14**、dm_hs_phy SPI **15** | `:20901-20902` |
| 时钟 | `core_clk`/`iface_clk`/`bus_aggr_clk`/`utmi_clk`/`sleep_clk`（GCC） | `:20897-20898` |
| 核时钟频率 | `core-clk-rate = 0xbebc200`(200 MHz)；disconnected `0x7f28155`(133.3 MHz)；hs `0x3f940ab`(66.7 MHz) | `:20906-20908` |
| USB2 PHY | `hsphy@88e3000`，`qcom,usb-snps-eusb2-phy`（**eUSB2**，非 QUSB2） | `:20953-20955` |
| USB2 PHY 寄存器 | `0x88e3000+0x154`；EUD enable `0x88e2000`；EUD detect `0xc276000` | `:20955-20956` |
| USB2 依赖 | `usb-repeater = <0x59b>`（外部 repeater，在 companion/PMIC 侧） | `:20966` |
| USB3/DP PHY | `ssphy@88e8000`，`qcom,usb-ssphy-qmp-dp-combo`，`0x88e8000+0x3000` | `:20969-20972` |
| **PHY 初始化表** | `qcom,qmp-phy-init-seq` **164 组 (addr,val)** 直接写在 DTB 里 | `:20984` |
| **PHY 寄存器偏移表** | `qcom,qmp-phy-reg-offset` 13 项：`0x1c14 0x1f08 0x1f14 0x1c40 0x1c00 0x1c44 0xffff 0x08 0x04 0x1c 0x00 0x10 0x1e00` | `:20983` |
| EUD | `qcom,msm-eud@88e0000`，`0x88e0000+0x2000`，SPI **11**，`qcom,secure-eud-en` | `:12884-12896` |
| 别名 | `usb0 = /soc/ssusb@a600000`、`usb_qmp_dp_phy = /soc/ssphy@88e8000` | `:40125`、`:40127` |

**重要副产品**：QMP PHY 的初始化序列和寄存器偏移表都在 DTB 里，不需要从驱动反推——`phy-qcom-qmp-combo.c` 只是把 DTB 的序列表按偏移写进 PHY。这显著降低了「路径 C」的成本估计。

### 3.1 DWC3 寄存器与结构（出处：Linux v6.6 `drivers/usb/dwc3/core.h`）

| 名称 | 偏移 | 说明 |
|---|---|---|
| `GCTL` | `0xc110` | 全局控制；`PRTCAPDIR` bits13:12（device=2）、`CORESOFTRESET` bit11、`DSBLCLKGTNG` bit0 |
| `GHWPARAMS0..9` | `0xc140`…`0xc6e0` | 硬件能力（端点数量、PHY 接口类型、FIFO 深度） |
| `GUSB2PHYCFG(0)` | `0xc200` | USB2 PHY 配置；`PHYSOFTRST` bit31、`SUSPHY` bit6、`ULPI_UTMI` bit4 |
| `GUSB3PIPECTL(0)` | `0xc2c0` | PIPE 控制；`PHYSOFTRST` bit31、`SUSPHY` bit17、`DEP1P2P3` bits21:19 |
| `GTXFIFOSIZ(n)` | `0xc300+n*4` | TX FIFO 深度/起始地址 |
| `GEVNTADRLO/HI(n)` | `0xc400+n*0x10` / `+4` | 事件缓冲物理地址（低/高 32 位） |
| `GEVNTSIZ(n)` | `+8` | 事件缓冲大小（`INTMASK` bit31、`SIZE` bits15:0） |
| `GEVNTCOUNT(n)` | `+0xc` | 已产生事件数（低 2 位恒 0）；`EHB` bit31 写 1 清中断 |
| `DCFG` | `0xc700` | `DEVADDR` bits9:3、`SPEED` bits2:0（SS=4、HS=0）、`LPM_CAP` bit22 |
| `DCTL` | `0xc704` | `RUN_STOP` bit31、`CSFTRST` bit30、`ULSTCHNGREQ` bits8:5 |
| `DEVTEN` | `0xc708` | 设备事件使能（`USBRSTEN` bit1、`DISCONNEVTEN` bit0、`CONNECTDONEEN` bit2、`CMDCMPLTEN` bit10） |
| `DSTS` | `0xc70c` | `USBLNKST` bits21:18、`DEVCTRLHLT` bit22、`CONNECTSPD` bits2:0 |
| `DALEPENA` | `0xc720` | 端点使能位图 |
| `DEP_BASE(n)` | `0xc800 + n*0x10` | `PAR2`+0、`PAR1`+4、`PAR0`+8、`CMD`+0xc |

端点命令（`DEPCMD`）：`CMDACT` bit10、`CMDIOC` bit8、`STATUS` bits15:12；命令码 `SETEPCONFIG=0x01`、`GETEPSTATE=0x03`、`SETSTALL=0x04`、`CLEARSTALL=0x05`、`STARTTRANSFER=0x06`、`ENDTRANSFER=0x08`、`DEPSTARTCFG=0x09`。设备命令（`DGCMD`，`0xc714`）：`XMIT_FUNCTION=0x03`、`SELECTED_FIFO_FLUSH=0x09`。

结构与常量：
- 事件缓冲 `DWC3_EVENT_BUFFERS_SIZE = 4096` 字节，事件 4 字节（`union dwc3_event`），共 1024 项；环回写靠 `GEVNTCOUNT` 递减 + `EHB`。
- TRB 16 字节：`bpl`(4) `bph`(4) `size`(4) `ctrl`(4)；`size[23:0]`=长度、`size[27:24]`=PCM1、`size[31:28]`=TRBSTS；`ctrl`：`TRBCTL(n)=n<<4`、`IOC=bit11`、`ISP_IMI=bit10`、`CHN=bit2`、`LST=bit1`、`HWO=bit0`。
- 端点事件：`XFERCOMPLETE=0x01`、`XFERINPROGRESS=0x02`、`XFERNOTREADY=0x03`、`RXTXFIFOEVT=0x04`、`EPCMDCMPLT=0x07`；EP0 的 SETUP 包以 `XFERNOTREADY` + `event_info=bRequest` 的形式到达。

## 4. 三个决定成本的未知

| # | 未知 | 为什么重要 | 怎么判 |
|---|---|---|---|
| U1 | ABL 跳转后 DWC3 是否仍在**已枚举**状态 | 决定路径 A（便宜）还是 B/C（昂贵） | **D0 主机侧观测**，零成本 |
| U2 | eUSB2 PHY + 外部 repeater 是否还能被裸机重配 | 若 ABL 已拆 PHY，裸机要碰 PMIC/companion，很可能不可行 | 路径 C 的可行性评估 |
| U3 | USB 的 GDSC/时钟/电源域在 ABL 退出后是否仍开 | 同上；`USB3_GDSC-supply` 由 RPMh 控制 | 只能通过「能不能重新枚举」间接判 |

## 5. 路线分叉

### 路径 A：继承（首选，成本最低）
前提：U1 = 「设备仍在总线上、仍是 ABL 的 fastboot gadget」。
做法：不碰 PHY/时钟/电源，只复用已配置的 EP1 bulk IN：
1. 读 `DSTS.CONNECTSPD` 决定 maxpacket（SS=1024，HS=512）。
2. 往 EP1 IN 挂一个 TRB（`bpl/bph` 指向 RAM 里的字符串，`size`=长度，`ctrl = IOC|LST|TRBCTL(2)`，`HWO=0`）。
3. 触发 `DEPCMD(STARTTRANSFER)`，轮询 `DEPCMD.CMDACT`，等 `XFERCOMPLETE`。
4. 主机侧用 pyusb 打开 fastboot 那个已绑定的 WinUSB 设备，直接 `read(0x81)`。
代码量估计 ~200 行，复用现有 `senna.c` 的 `wait_ms`/`pause`。

### 路径 B：重配 DWC3，PHY 沿用
前提：U1 = 「USB 已断开、但 PHY 仍上电（`GUSB2PHYCFG.PHYSOFTRST=0` 且 `GUSB3PIPECTL.PHYSOFTRST=0` 读回正常）」。
做法：`DCTL.CSFTRST` 软复位 → 设 `GCTL.PRTCAPDIR=2` → 配 `GUSB2PHYCFG`/`GUSB3PIPECTL` → 建事件缓冲 → `DCFG` 设初速（HS）→ `DEVTEN` 开 `USBRST/DISCONN/CONNECTDONE/CMDCMPLT` → `DCTL.RUN_STOP=1` → 处理 EP0 标准请求（GET_DESCRIPTOR / SET_ADDRESS / SET_CONFIGURATION）→ 之后同路径 A 发数据。
代码量估计 ~600 行；描述符可用 CDC-ACM（Windows 自动 `usbser.sys`）或 vendor bulk（需 Zadig 换 WinUSB，动主机驱动，需用户同意）。

### 路径 C：全量重建（高风险，默认不做）
需要 GCC 时钟树、`USB3_GDSC`、eUSB2 repeater（PMIC 侧）、QMP PHY 上电序列。裸机没有 RPMh/regulator 框架，**判为大概率不可行**。只有在 A/B 都失败、且用户明确要求继续时才评估。

## 6. 分阶段计划

### D0 主机侧观测（**不改任何 shim 逻辑**，只判 U1）
- 镜像：`senna-shim-v0.6spin` —— 探测 → 不写 ramoops → `SENNA_D0_HOLD_MS=120000`（2 分钟静置）→ `PSCI_SYSTEM_RESET`（相对 v0.5 只改「不写 ramoops」+ 静置时长）。
- 主机侧：`python build-chain/tools/usb_watch.py --pnp-only --duration 150 --out build-chain/evidence/boot-attempts/d0-usb-watch.csv`。
  **必须带 `--pnp-only`**：只读 `Get-CimInstance Win32_PnPEntity` 里 `VID_18D1`/`VID_05C6` 的在场情况，**不发任何 fastboot 命令**（见下面的 D0 事故记录）。
- 在场判定：senna bootloader 枚举为 `USB\VID_18D1&PID_D00D`（FriendlyName = `Android Bootloader Interface`），**不是**老机型的 `18D1:4EE0`；回到 Android 后是 `18D1:4EE8`（MTP）。`Get-PnpDevice` 有时看不到这个设备（类不在 USB 下），必须用 `Win32_PnPEntity`。
- 验收（三选一）：(a) 2 分钟内 `18D1:D00D` 一直在场（shim 里也没变成别的 PID）→ **路径 A**；(b) 引导后该设备从总线消失、始终不回来 → **路径 B**；(c) 在场且切到 `4EE8` → 设备已经回 Android，超时太短，需重测。
- 失败日志：`evidence/boot-attempts/<UTC>-shim-v4.md`（含 fastboot 输出）+ `d0-usb-watch.csv`。

#### D0 事故记录（2026-11-22，已 wedge 一次设备）

第一次执行时把 `usb_watch.py`（旧版，会每 1 s 跑 `fastboot devices` + `getvar`）和
`fastboot boot` 并发跑，bulk 传输直接失败：
`Sending 'boot.img' (84 KB) FAILED (AdbWriteEndpointSync failed: 信号灯超时时间已到 (121))`。
更麻烦的是 **ABL 的 fastboot 栈被写坏后不自愈**：kill 掉观测器、单独重跑 `fastboot boot`
仍然 121，`getvar product` / `reboot-bootloader` 也全是 121（`fastboot devices` 仍能列出设备，
因为那只是本地 WinUSB 枚举）。恢复只能长按电源键 ~15 s 强制重启。

**结论**：D0 期间主机侧**只允许** `--pnp-only` 观测；`fastboot boot` 传输窗口内不得有任何
其它 fastboot 进程。这也是 `boot-attempt.ps1` 的 `-Confirm` 提示语改掉的原因。

### D1 路径 A 最小发送
- 目标：设备发 `SENNA USB OK`，主机收到完全相同字符串。
- 做法：§5 路径 A 四步；长度补齐到 maxpacket 整数倍（末尾 0x00 填充，主机侧剥离）。
- 验收：主机文件里字符串逐字节一致；否则按失败日志记录 `DSTS`/`DEPCMD` 读回。

### D2 路径 A 全量 TAG
- 目标：12 行 `TAG 16HEX`（内容同 `senna.c` 的 `payload_build()`）。
- 做法：把 v0.4 的 payload 搬到 USB 发送侧，一次发完（<900 字节），主机落盘 `evidence/boot-attempts/<UTC>-tags.txt`。
- 验收：文件 12 行齐全、`END` 结尾；随后 C.2 的 §6 未证项一次性回填。

### D3 路径 B 重新枚举
- 目标：主机看到 `SENNA SHIM` 设备重新枚举（描述符 `iProduct` 可辨识）。
- 做法：§5 路径 B；先只做 EP0 标准请求，能枚举到「未知设备」即算通过，再补 bulk IN。
- 失败日志：`DSTS`/`DCTL`/`GUSB2PHYCFG`/`GUSB3PIPECTL` 读回值 + 主机端 `Get-PnpDevice` 快照。

### D4 路径 C 评估（可以不写代码）
- 目标：给出「C 路线可行/不可行」的结论与证据，避免无限投入。
- 做法：查 `dwc3-qcom.c`/`phy-qcom-snps-eusb2.c`/`phy-qcom-qmp-combo.c` 的电源与 repeater 依赖，逐项标注「裸机是否具备」。
- 停止判据：若需要 RPMh/GDSC/PMIC 通路才能重新枚举 → **停**，向用户汇报并请求决策，不再加码。

## 7. 主机侧工具（离线可写）

| 文件 | 作用 | 状态 |
|---|---|---|
| `build-chain/tools/usb_watch.py` | D0 观测：`--pnp-only` 纯 PnP 轮询（默认）；旧 fastboot 轮询模式**禁止与 boot 并发** | 已可用（2026-11-22 冒烟） |
| `build-chain/tools/usb_console.py` | D1/D2：pyusb 打开 VID/PID，读 EP1 IN，写文件 | 待写（D1 前） |
| `build-chain/tools/boot-attempt.ps1` | 已有执行器，加 `shim-v6spin` 基线即可 | 已有 |

备选：若 pyusb/libwinusb 不可用，才考虑 Zadig 换 WinUSB 驱动——**会动主机驱动，需用户明确同意**，默认不做。

## 8. 风险与失败模式

| 风险 | 影响 | 缓解 |
|---|---|---|
| ABL 的 fastboot gadget 端点号不是 EP1 | 路径 A 需先读 `DALEPENA` 与端点事件确认 | D1 先读 `DALEPENA`/`GTXFIFOSIZ` 再发 |
| 主机侧驱动未绑定 / 设备管理器显示未知设备 | 收不到数据 | D0 的 CSV 里记录驱动名与状态 |
| 端点 NAK（主机未读） | 数据延迟，不丢 | 重试 + `wait_ms` 轮询 `XFERCOMPLETE` |
| shim 未开 MMU/cache | 无所谓（当前无 D-cache） | 若后续开 cache，复用 v0.5 的 `flush_range` |
| 写错 `DCTL`/`ULSTCHNGREQ` 导致 DWC3 挂死 | 设备停在 shim，需硬重启 | 只 `fastboot boot`，不变砖；超时 60 s 后 `PSCI_SYSTEM_RESET` |
| eUSB2 repeater 未初始化 | HS 无法建链 | 路径 A 不碰；路径 B 先验证 HS 是否还能用 |

## 9. 决策记录

1. **先做 D0 观测再写 USB 代码**：U1 决定 200 行还是 600+ 行，且 D0 零成本（只需一个 60 s 空转镜像）。
2. **路径 A 用「现成的 fastboot 接口」而不是自建 CDC-ACM**：ABL 已经把设备枚举好了，主机也已经绑好 WinUSB 驱动；自建枚举要重写描述符与 EP0 状态机，收益为零。
3. **不做 EUD**：`qcom,secure-eud-en` 且 EUD 语义（嵌入式 USB 调试器）未在本机验证，安全性不明。
4. **PHY 初始化表从 DTB 取而不是从驱动反推**：DTB 是实机产物，比驱动默认值更权威（`from-binary.dts:20984`）。

## 10. 待办

1. [D0] ~~写 `usb_watch.py`；出 `senna-shim-v0.6spin` 镜像~~ 完成（CI run `44977828469`，v4 sha256 `bb0a7760…c0caf`）；观测器已加 `--pnp-only` 并通过冒烟。
2. [D0] 等用户电源键重启后重跑：先起 `--pnp-only` 观测器，再 `fastboot boot`（不并发 fastboot）。
3. [D1/D2] 按 U1 结果二选一实现。
4. [C.3] USB 通道打通后，`TAG` 回填 `DESIGN.md` §6，再进 XNU 接管。