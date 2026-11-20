# 交接文档（新会话开工必读）

最后更新：2026-11-20。本文件用于把本会话完整移交给新会话，包含用户关键词、硬约束、已完成证据、当前卡点与下一步动作。

---

## 0. 新会话开场提示词（直接粘贴）

> 你继续「真我 GT Neo5 (RMX3706 / senna-b / SM8475) 移植 xnu-8796 与 iPhone X iOS 16.7.16 rootfs」项目。先读 `C:\Users\hjfdw\Documents\deepseek-harness\default-workspace\senna-b-port\HANDOFF.md`、`PROGRESS.md`、`DEVICE.md`、`REMAINING.md`、`build-chain/BUILD-EVIDENCE.md`，然后从「第 7 节 未完成任务」继续。全程中文；用户空间一字节不改；只用 `fastboot boot`，不刷分区；寄存器/内存/中断/固件地址必须有本机 DTB、官方 OTA 或高通公开 SM8475 源码出处，无证据就停下列清单，禁止套用其他机型数值。每阶段先给「目标/做法/验收/失败日志」，判读实机日志后才能继续，并输出「已完成/未完成/关键参数表」。

---

## 1. 用户关键词与硬约束（不得删改）

- 角色：资深 ARM64 移植执行 agent；**全程中文**。
- 目标：把 **xnu-8796** 与 **iPhone X 的 iOS 16.7.16 (20H392) 原版 rootfs** 移植到 **真我 GT Neo5 RMX3706 / senna-b（SM8475）**。
- **用户空间一字节不改**；缺失接口靠内核或注入库补。
- 所有寄存器、内存、中断、固件路径必须来自 **本机 DTB / `/proc/device-tree`、官方 OTA、高通公开 SM8475 源码**；**无证据就停下列清单**，**禁止套用其他机型数值**。
- 早期**只用 `fastboot boot`，不刷分区**；**划 darwin 分区前必须先给完整方案 + 回滚方案，并经用户确认**。
- **每阶段**先给：目标 / 做法 / 验收 / 失败日志；判读实机日志后才能继续；每阶段输出「已完成 / 未完成 / 关键参数表」。
- **解锁、清数据、刷写只给命令由用户执行**，不假设已完成。
- 参考项目：`ios-sweet`、`UniXNU`、`edk2-msm`、`blacktop/darwin-xnu-build`。
- 用户后续原话："不要写任何移植代码"（仅针对采集阶段，m00303）、"你先复盘一下本对话吧，然后把项目上传GitHub，接着告诉我还剩下哪些需要完成"（m02463）、"帮我部署git呗"（m02519）、"你接着完成剩余任务，然后记得上传。"（m02672）。
- 交付物偏好：可复现命令、证据文件、哈希、明确的"未完成"清单；**禁止把未验证的东西说成通过**。

## 2. 设备事实（已实测，均有出处）

| 项 | 值 |
| --- | --- |
| 设备 | ADB 序列号 `78ad6b26`，型号 RMX3706 / RE5860，代号 senna-b，SoC SM8475 |
| 系统 | Android 13，`RMX3706_13.1.0.115(CN01)`，OTA `RMX3706_11.A.45_0450_202308171956` |
| 内核 | `5.10.149-android12-9-o-g36dae0b389f6` |
| 槽位/锁 | 当前 `_b`，`orange` 状态，`unlocked`，`flash.locked=0`；有 su |
| 分区（示例） | `boot_b=/dev/block/sde43`(201326592)、`dtbo_b=/dev/block/sde47`(25165824)、`vendor_boot_b=/dev/block/sde54`(201326592)、`vbmeta_b=/dev/block/sde46`(65536)；全量 132 项见 `DEVICE.md` |
| 当前 DT | `senna-live.dtb` 1,118,143 字节，SHA-256 `7A290B13563A058464FA01287FA801687B76E55A85A80867DDA76AAC73743094`；阶段0 旧 DT `AB7B51E9…`（仅 hypervisor 动态节点差异） |
| PMIC/SPMI | `/soc/qcom,spmi@c42d000`，cnfg `0x0c42d000+0x4000`；PMK8350/PM8350/PM8350C/PM8350B/PMR735A/PMR735B/PM8450/PM8010I/PM8010J，USID 0/1/2/3/4/5/7/8/9 |
| 触控 | `synaptics-s3910`，`/soc/spi@990000`（qcom,spi-geni，MMIO `0x00990000+0x4000`），**SPI0 chip-select 0**（不是 I2C 地址） |
| 面板 | cmdline 选中 `qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd`，1240x2772、30bpp、DSC v1.1、slice 620x12、5 组 timing（sdc120/sdc90/sdc60/sdc144/oplus120） |
| UFS | Micron `MT256GAXAT4U31`，specification_version 0x0310（**UFS 3.1**），UniPro 1.8，M-PHY 4.1，manufacturer_id 0x012C |
| Wi-Fi/BT | 均为 **QCA6490**（`/soc/qcom,cnss-qca6490@b0000000`、`/soc/bt_qca6490`；PCI 0000:01:00.0 17cb:1103） |
| GIC/ITS | GICD `0x17100000+0x10000`，GICR `0x17180000+0x200000`，ITS `msi-controller@17140000` `0x17140000+0x20000` |
| reserved-memory | 55 项，完整 reg/size/no-map 见 `DEVICE.md` |

> 注意：阶段1 报告曾把 GICR 误写为 `0x171c0000`，已按原始 DT 更正为 `0x17180000`；以 DT 解码结果为准。

## 3. 已完成（可直接引用）

- **阶段0**：设备/固件/槽位/锁状态、分区与 DTB 证据、fastboot 回环验证。证据在 `stage-00-evidence/`。
- **阶段1**：平台证据解析 + 仓库审计，验收 54/54。报告 `stage-01-platform-evidence/STAGE1-REPORT.md`。
- **移植前采集（只读）**：`device-inventory/`（完整 `/proc/device-tree` 35,696 成员展开零错误、132 分区、55 reserved-memory、UFS 描述符、DTS 2,716,184 字节）；验收 26/26；说明 `device-inventory/COLLECTION.md`、失败记录 `FAILURES.md`。
- **`DEVICE.md`**：senna 移植参数表 + `ios-sweet`(SM7150) / UniXNU 对照的三类清单（可直接复用 / 需改地址 / 需新写）。**UniXNU 固定 main `519d80242a5028ee123447b01bc3b809baed565f` 里没有 SM8475 机型路径，不得虚构。**
- **复盘**：`RETROSPECTIVE.md`（阶段0→run12 逐 run 失败原因表）；剩余工作：`REMAINING.md`（A 构建链 / B 证据补证 / C 引导链 / D 内核用户空间 / E 合规隔离）。

## 4. 构建链现状（关键）

Fork：https://github.com/awadmw/ios-sweet （上游 `45263bee51df4a0f55cdf9c649af886399488ddb`），固定 DXB `663906528d1cd5ea8fde7de6f16de73db9511549`，xnu-8796.141.3，runner macos-15。

| 目标 | run | 结论 | 产物 |
| --- | --- | --- | --- |
| SWEET（SM7150 参考） | 44481202871（提交 `c1c360d`） | **success** 8m44s | `xnu-kernelcache-SWEET` id=14509386243，67,562,895 字节，digest `sha256:6084969434F242277F2FAACD051D2ADDFC7671402A1AAC7EBD44E76D06BDBF5B`；`xnu-buildtree-SWEET` id=14509246494 |
| SENNA（SM8475 编译别名） | 44489106397（提交 `aea14cd`） | **success** | `xnu-kernelcache-SENNA` id=14512706375，67,563,990 字节，digest `sha256:ae380407d52993b7611310fb424f8468ec50ce7e65792fb408da1cd6b1bda332`；`xnu-buildtree-SENNA` id=14512860694 |

SWEET 产物已本地校验：下载 zip 的 SHA-256 与 GitHub digest 一致；`kernelcache.sweet` 21,184,512 字节（`D1B13A15B78E54E3CC7E19E54725C633E989D5CCAE007B2B37A3AE669B8B6BC1`），`kernel.development.sweet` 18,388,744 字节（`DD31242D…`）；`kmutil inspect` → boot kernel collection `08A074F3-DF8A-CCEF-63BE-53FEB9362B67`，内含 `com.apple.kernel 628D9966-43C4-3A18-8F89-4FF3F4F4D86B`。

**边界（必须一起说）**：这是 `kmutil create -a arm64 -x` 的 **kernel-only boot kernel collection**，不是可引导 payload，不能直接 `fastboot boot`；机器配置是 SWEET（SM7150）参考，未做任何 senna 硬件适配；rootfs 未改。

### 已修掉的真实失败（别再重复踩）
1. runner `macos-14-arm64-us-default` 已退役 → 改 macos-15。
2. `KMErrorDomain Code=34`：kmutil 要求宿主同版本 KDK → 装 KDK 15.8.2 build 24H232（dortania KdpSupportPkg）。
3. `Code=71 AppleRTC 依赖 IOACPIFamily 找不到`：删掉 `-x` 导致扫描全 KDK → 恢复 `-x $(ipsw kernel kmutil inspect -x --filter ...)`。
4. `Code=31 AppleUSBTDM missing compatible arch`：`-a arm64` 要求全部 kext 有 plain-arm64 slice → 改回 `-a arm64e`。
5. `Code=31 kernel is not a compatible arch`：arm64e 集合收不了 plain-arm64 内核 → 改 **kernel-only**（`-a arm64 -x` 且不带 `-b`）。
6. `Missing split seg v2`：plain arm64 缺 `LDFLAGS_KERNEL_ONLY_SUBARCH_arm64` → 注入 `-Wl,-add_split_seg_info -Wl,-kernel`。
7. KC 文件名带 `.development` 后缀导致 `test -s` 失败 → 接受 `${output_path}.${KC_VARIANT}`。
8. SENNA 找不到 `sweet_bearssl/`、`sweet_libpthread/`、`hfs.h`：`0019/0020/0026-stage-*.sh` 里 `MACHINE_CONFIG==SWEET` 守卫 → 放宽为 `SWEET|SENNA`（`3c466f3`）。
9. SENNA 里 `-include sweet_hfs_compat.h`、`SWEET_AES_INC` 不生效：`*/conf/Makefile.template` 的 `ifeq ($(CURRENT_MACHINE_CONFIG),SWEET)` 守卫 → 改为 `ifneq ($(filter …,SWEET SENNA),)`（`19fb11b`、`aea14cd`）。

### 诊断方法（有效，别退回抓 47MB 日志）
- workflow 失败时上传 `build-failure-<CONFIG>` artifact（`fail-errors.log` + `fail-tail.log`），用 `gh run download <run> -R awadmw/ios-sweet -n build-failure-SENNA -D <dir>` 取回，秒级。
- `gh run view --log` 会 `stream error: stream ID 1; CANCEL`；blob URL 不支持 Range，47MB 拉不动。**不要再用 Chrome 抓 raw 日志。**

## 5. 主机环境

- 项目根：`C:\Users\hjfdw\Documents\deepseek-harness\default-workspace\senna-b-port`（约 889 MB，含大镜像与日志，`.gitignore` 已排除）。
- 工具：`C:\Program Files\Git\cmd\git.exe`（2.56.0）、`C:\Users\hjfdw\AppData\Local\Microsoft\WinGet\Packages\GitHub.cli_Microsoft.Winget.Source_8wekyb3d8bbwe\bin\gh.exe`（2.105.0，已 `gh auth` 登录 awadmw，scopes `repo, workflow, gist, read:org`）；adb 在 `C:\Android\platform-tools\adb.exe`（不在 PATH）。
- PowerShell 5.1 注意：**不能用 `>` 保存 adb 二进制**（会破坏字节），用 `.NET Process` 的 `StandardOutput.BaseStream.CopyTo(FileStream)`；`Start-Process -ArgumentList` 传数组会被空格断开，必须传单个带引号字符串。
- 上传仓库：https://github.com/awadmw/senna-b-port （Public，main）。已推送：`426d2be` → `b2ffac1` → `b68bb10`。
- 本地未提交：`build-chain/artifacts/`、`build-chain/remote/`、`build-chain/work/ios-sweet/.github/workflows/xnu.yml` 等（`.gitignore` 视情况再定）。

## 6. 已知限制

- **账号余额 ¥0.00**：`code_agent` 子代理调用失败（`Select an available model before sending a message`），长任务易被打断。充值后可用于纯执行类工作（下载/校验/文档）。
- 本机无 macOS，无法本地编译内核；一切构建只能在 GitHub Actions。
- 设备为唯一实机，任何 `fastboot boot` 前必须先有回滚说明与用户确认。

## 7. 未完成任务（按优先级）

**A. 构建链收尾（最快可完成）**
1. 下载 SENNA 产物并校验：`gh run download 44489106397 -R awadmw/ios-sweet -n xnu-kernelcache-SENNA -D build-chain\artifacts\kc-senna-artifact`（约 20 分钟，64 MB）。校验 zip SHA-256 必须等于 `ae380407d52993b7611310fb424f8468ec50ce7e65792fb408da1cd6b1bda332`；解包后记录 `kernelcache.senna` 大小/哈希与 `kmutil inspect` 输出。
2. 把 SENNA 结果补进 `build-chain/BUILD-EVIDENCE.md` 与 `PROGRESS.md`（替换现在的"进行中"表述），把证据 JSON/文本放进 `build-chain/evidence/`。
3. `git add` + `commit` + `push` 到 `senna-b-port`。
4. 把此前只在本地的 `xnu/senna/*`、workflow 变更与远程 `awadmw/ios-sweet` 对齐（远程已是 `aea14cd`）。

**B. 证据补证**
- 用 `dtc` 对 `device-inventory/senna-live.dts` 做 round-trip 校验（本机无 dtc，可用 Actions 或 WSL）。
- 官方 OTA `RMX3706_11.A.45_0450_202308171956` 的 payload 里提取 dtb/dtbo 与本机 DT 交叉比对（尚未做）。

**C. 引导链（主线，尚未开始）**
- 明确 senna 的最小引导路径：ABL/UEFI（edk2-msm）与 `fastboot boot` 的限制；`ios-sweet` 的 `tools/mkpayload.py` 生成 raw kernel payload 的流程。
- 需要补的：SM8475 的 UART、GIC/timer 中断号、内存 map 与 iOS 侧 KASLR/PE 状态位的本机出处。
- 任何实机动作前：给方案 + 回滚 + 用户确认；只 `fastboot boot`。

**D. 内核/用户空间**
- 明确哪些 kext/用户态组件必须注入、哪些由内核补；rootfs 依然一字节不改（只读挂载或 overlay 方案需先论证）。

**E. 合规与隔离**
- 保留"不做签名绕过、不碰分区表"的边界说明；所有实验可回滚。

## 8. 下一会话第一件事

按第 7 节 A.1 开始：下载并校验 SENNA 内核集合，然后把结果写进 `BUILD-EVIDENCE.md`/`PROGRESS.md` 并 push。