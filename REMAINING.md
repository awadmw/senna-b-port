# 剩余工作清单

> 状态：阶段 0/1 与设备采集已完成；构建链 run12 待判读。以下按依赖顺序排列，未完成项不得宣称已完成。

## A. 构建链收尾（当前）

1. **判读 run12**（`https://github.com/awadmw/ios-sweet/actions/runs/44469178619`）：确认 `kmutil create` 是否还在 split seg 之外的新错误上失败。
2. SWEET 绿色运行 + 下载 `kernelcache.sweet`，核验：非空、`kmutil inspect --show-kernel-uuid`、`file` 架构、SHA256、`build-metadata.json` 中 `machine_config=SWEET`。
3. `workflow_dispatch` 运行 **SENNA**，同样下载核验 `kernelcache.senna`，并确认 `runtime_support=not-implemented`。
4. 把本地 `BUILDING.md` 的最终版本同步到远程仓库（含 run1–run12 验收表与 kernel-only KC 的边界说明）。
5. 归档两份 KC、运行 JSON、关键日志片段，重算 `SHA256SUMS.txt`，更新 `PROGRESS.md`。

**明确边界**：这两份 KC 只是构建链产物，**不是能在 senna 上启动的镜像**。

## B. 平台证据补证（阶段 2 前置）

1. **vendor_boot base 的实际选择算法**：目前只能证明 base 01 与 live 一致，未证明 bootloader 如何挑。需要从 ABL/XBL 日志或 bootconfig 侧找证据。
2. **活动帧缓冲**：`cont_splash_region=0xb8000000+0x02b00000` 只是保留区，不等于 stride/format；需要 UEFI 侧实际读 MDP 寄存器或在启动时打印。
3. **arch timer 真实频率与 IRQ**：DT 只有 `arm,armv7-timer-mem` 19.2 MHz，必须在目标环境读 `CNTFRQ_EL0` 并用 GIC 实际中断验证，不能套 sweet 的虚拟定时器 IRQ。
4. **PSCI/UART 在 UEFI 阶段的可访问性**：需要实机串口输出才能确认，不能靠 DT 存在性推断。
5. **EDL 救砖验证**：仍未做过一次真实进入/退出 EDL 的演练（需用户确认窗口期）。
6. **官方全量 OTA + 原版 rootfs**：`RMX3706_11.A.45` 全量包、iOS 16.7.16 (20H392) rootfs 的获取、哈希与来源记录仍未完成。

## C. 引导链（阶段 3）

1. edk2-msm 上新建 **senna 设备包**（`Platform/Realme/senna` 或等价路径），只复用 `Platform/Qualcomm/sm8475` 的 SoC 层；**不得**直接搬 yudi 的 FD/内存映射参数。
2. 依 DEVICE.md 生成 senna 的内存映射、`DeviceConfigurationMap`、UART/GIC/timer 配置。
3. 产出可 `fastboot boot` 的 UEFI 镜像，先只验证“串口有输出 + 内存/SMBIOS 基本信息”，不加载任何 iOS 组件。
4. 准备回滚与验收：boot 失败后回 Android 的完整步骤；每步日志留存。

## D. 内核与用户空间（阶段 4，尚未开始）

1. 用 SENNA 编译目标替换 SWEET 板级实现，逐项补 senna 的 GIC/timer/UART/UFS/display/触控驱动配置（全部来自 DEVICE.md 的证据）。
2. 解决 `fastboot boot` 镜像格式：ios-sweet 用 `mkpayload.py` 生成 raw kernel payload；若走 KC 路线需要另做收集与加载方案。
3. rootfs 只读挂载 + 缺失接口用内核或注入库补，**保持“用户空间一字节不改”**。
4. 只有在完整方案与回滚经用户确认后，才讨论划分 darwin 分区。

## E. 合规与隔离

- 参考仓库许可证：ios-sweet MIT、darwin-xnu-build MIT、UniXNU BSD-2-Clause-Patent、edk2-msm BSD-2-Clause；引用处保留原始 commit 与来源。
- yudi / sweet 的所有机型参数继续隔离，不得出现在 senna 产物的默认值里。
- 禁用清单保持：`sweet-root-tweaks.py`（改 rootfs）、任何未审计的预编译 dtc/打包工具。
