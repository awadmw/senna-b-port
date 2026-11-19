# 本对话复盘（阶段 0 → 构建链 run12）

> 记录时间：2026-11-19。所有结论都来自本机证据或实际运行日志；没有一条来自“看起来合理”的推测。

## 1. 总目标与硬约束

把 **xnu-8796** 与 **iPhone X / iOS 16.7.16 (20H392) 原版 rootfs** 移植到 **真我 GT Neo5 RMX3706（senna-b，SM8475）**。

用户定下的约束，全程未破：

| 约束 | 执行情况 |
|---|---|
| 用户空间一字节不改 | 未下载/挂载/修改任何 iOS rootfs；明确禁用 ios-sweet 的 `tools/sweet-root-tweaks.py` |
| 参数必须有证据 | 寄存器/内存/中断/固件路径全部来自本机 DTB、本机 sysfs、官方 OTA 元数据或上游源码；无证据处一律列为“未知” |
| 禁止套用他机型数值 | edk2 yudi（Xiaomi Pad 6 Max 14）的 `FD_BASE=0xCE000000` 等参数被明确隔离，不得用于 senna |
| 早期只用 `fastboot boot`，不刷分区 | 全程未执行 `fastboot flash`；未划分 darwin 分区 |
| 每阶段给目标/做法/验收/失败日志 | 阶段 0、阶段 1、采集、构建链各自有报告与失败记录 |
| 只由用户执行解锁/清数据/刷写 | 未替用户执行任何破坏性操作 |

## 2. 阶段 0：设备与可恢复性基线

实测（ADB `78ad6b26`）：

- 机型 `RMX3706` / `RE5860`，Android 13 `RMX3706_13.1.0.115(CN01)`
- OTA 基线 `RMX3706_11.A.45_0450_202308171956`
- 内核 `5.10.149-android12-9-o-g36dae0b389f6`
- 当前槽 `_b`、`orange` 状态、`unlocked`、`flash.locked=0`、`su` 可读 root
- 分区：`boot_b=/dev/block/sde43`、`dtbo_b=sde47`、`vendor_boot_b=sde54`、`vbmeta_b=sde46`
- cmdline 含项目号 `22624`、`console=ttyMSM0,115200n8`、面板 `qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd`、触控 `synaptics-s3910`

**关键教训**：PowerShell 的 `>` 会破坏二进制（首次导出得到 65 字节垃圾）。必须用 `.NET Process` 的 `StandardOutput.BaseStream.CopyTo(FileStream)`。另外 `su` 引号写错也会静默产生截断文件。

## 3. 阶段 1：镜像与 FDT 证据（只读）

本机没有 git/dtc/WSL，因此自己写了 FDT 解析器（`android_fdt_tool.py`），而不是下载不明预编译工具。

实际踩到的坑，全部已修正并记录：

1. `DTBO_MAGIC` 是 `0xD7B7AB1E`（一开始写成 `0x1EABB7D7`，直接 `bad DTBO magic`）。
2. 本机 DTBO 的 64 位 offset 原始字序是 **low-u32 在前**，不是标准大端直读。16 项全部用 `off=(hi<<32)|lo` 通过边界、`D00DFEED`、`FDT totalsize` 三重校验后才采用。
3. DTBO `entry_size=32`，`custom` 只有 3 个 u32（按 4 个读会越到下一条目）。
4. `vendor_boot` 早期把 `dtb_size` 读成 0，是结构偏移错误，不是“没有 DTB”；后来由 `header_size`、ramdisk 对齐、三个 FDT 大小之和 `0x15e650` 精确交叉验证。

结果：

- `dtbo_b`：16 个 overlay 全部提取成 DTB + 文本。
- 逐条解析根属性后确定 **senna-b = `dtbo-entry-11.dtb`**（`Cape MTP, Senna B`，1212016 字节，`D3169C92…04CD`）。10 是 Senna A、12 是 Senna C，不能混用。
- `vendor_boot` 有 3 个 base DTB（Cape LTE Only / Cape / Ukee）。
- 四仓库固定 commit 审计：ios-sweet `45263bee…`、UniXNU `519d8024…`、edk2-msm `e1952621…`、darwin-xnu-build `66390652…`。
  - **重要纠正**：UniXNU 固定 main 里**没有任何 SM8475 设备路径**；edk2-msm 唯一的 SM8475 机型是 yudi。用户原先“UniXNU 的 SM8475 机型”这一对照前提不成立，已如实说明。
- 硬件表：内存 5 段合计 12655263744 字节；PSCI `arm,psci-1.0`/`smc`；GICD `0x17100000+0x10000`；ITS `0x17140000+0x20000`；UART `0x0099c000`、SPI 608；UFS `0x01d84000`、SPI 265；timer `0x17420000`、19.2 MHz。
- 自动验收 **54/54 通过**。

**一处人工转录错误**：阶段 1 报告曾把 GICR 写成 `0x171c0000`，原始 DT 是 `…1718000000200000…`，正确值是 **`0x17180000+0x200000`**。后来所有文档都从原始 DT 直接生成，不再手抄。

## 4. 移植前设备采集（只读，DEVICE.md）

- 采集脚本 `collect-device.sh` / `collect-ufs.sh`，未在手机写文件、未重启。
- 完整 DT：`tar` 42592256 字节、31221 文件；普通展开因超长路径 `FileNotFoundError`，改用 Windows `\\?\` 扩展路径后 **complete=true**。部分展开不能称“完整”，这点专门纠正过。
- 132 项分区、55 项 reserved-memory 全量结构化。
- PMIC：PMK8350/PM8350/PM8350C/PM8350B/PMR735A/PMR735B/PM8450/PM8010I/PM8010J，USID 依次 0/1/2/3/4/5/7/8/9，主 SPMI `c42d000`。
- 触控：`synaptics-s3910`，挂在 **SPI0 chip-select 0**（不是 I2C 地址）。
- 面板：NT37705，1240×2772，DSC，5 组 timing（60/90/120/144 + oplus120），完整 81 个属性入库。
- UFS：Micron `MT256GAXAT4U31`，`specification_version=0x0310`（UFS 3.1）、UniPro `1.8`、M-PHY `4.1`。**`rev=0107` 不是 UFS 版本**，一开始就区分开了。
- Wi-Fi/BT：`qca6490`，由 DT `qcom,cnss-qca6490` / `qcom,qca6490` 与驱动日志双向确认；不拿 PCI device id 反推型号。
- 当前 DT 与阶段 0 DT 逐属性对比：唯一差异是 hypervisor 下的动态 RPC 节点，**硬件无差异**，两代证据都保留。
- 验收 **26/26 通过**；阶段 1 回归 **54/54**。

## 5. 构建链：从“能编译”到“真出 kernelcache”

Fork：`awadmw/ios-sweet`，上游锁 `45263bee…`，DXB 锁 `66390652…`。

逐步排错（每一步都是真实日志，不是猜）：

| run | 结果 | 精确原因 |
|---|---|---|
| 1 | 失败 | GitHub 不再支持 `macos-14-arm64-us-default` |
| 2 | 绿（≠验收） | 内核编译成功，但 `bash build.sh` 没传 `-k`，`kmutil_create_count=0`，**没有 KC** |
| 5 | Code 34 | `kmutil` 要求宿主构建号 24H232 的 KDK |
| 6 | Code 34 | 去掉 `ipsw` 后原路径仍触发宿主 KDK 检查 |
| 7 | Code 34 | 显式 `--kdk 13.5` 仍不够，宿主 KDK 缺失是独立条件 |
| 8 | Code 71 | 装了宿主 KDK，但删掉 `-x` 导致全 KDK 扫描，`AppleRTC` 缺 `IOACPIFamily` |
| 9 | Code 31 | `-a arm64` 的 KC 收不了只有 arm64e slice 的 `AppleUSBTDM` |
| 10 | Code 31 | 改回 `-a arm64e`，KC 收不了 plain-arm64 的 kernel |
| 11 | Code 31 | 纯内核 arm64 KC：`Missing split seg v2` |
| 12 | 进行中 | 补 `-Wl,-add_split_seg_info -Wl,-kernel` |

关键判断与理由：

- **为什么最后做 kernel-only KC**：上游 ios-sweet 的真实启动链是 `tools/mkpayload.py` 处理 plain-arm64 raw kernel，明确“no kmutil, no iBoot”。所以 CI 里按用户要求另做 **kernel-only kernelcache**，并在文档里写清它**不是**可启动 payload，也不代表 senna 驱动已就位。这样既不伪装成功，也满足“真实 KC artifact”的验收要求。
- **为什么 SENNA 是 compile-only alias**：`XNU_BOARD_CONFIG=SWEET` 只是借 SWEET 的板级实现把编译、链接、`kmutil` 走通；不写任何未证实的 senna 地址，`RUNTIME_SUPPORT=not-implemented` 写进产物元数据。
- **为什么空补丁是两行注释**：GitHub 网页不接受零字节文件；本地 workflow 会拒绝任何非注释内容，等价于“无 diff 补丁”。

## 6. 工程教训

- GitHub raw 日志入口是 `/commit/<sha>/checks/<job>/logs`；`/job/<id>/logs` 是 404。菜单项要先聚焦再 Tab/Enter。
- Chrome 窗口尺寸会变，GUI 坐标每次按最新截图归一化，不要沿用旧值。
- 本机**没有 git / gh / token**；远程改动靠已登录网页 + 公开 API（curl）留证。
- `dmesg` 环形缓冲被 Wi-Fi 日志冲刷，早启动行不全；结论要靠 DTS + sysfs + 现有日志交叉证明，不能只靠 dmesg。

## 7. 当前状态

- 阶段 0、阶段 1、设备采集：**已完成并通过验收**。
- 构建链：SWEET 内核多次真实编译成功；**尚无验收合格的 kernelcache**；run12 正在跑。
- 未连接/未操作实机（构建阶段）；未接触 rootfs。
