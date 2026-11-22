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

两份产物均已本地校验（zip SHA-256 与 GitHub digest 逐字符一致）：

- SWEET：`kernelcache.sweet` 21,184,512 字节（`D1B13A15…`），`kernel.development.sweet` 18,388,744 字节（`DD31242D…`）；`kmutil inspect` → boot KC `08A074F3-DF8A-CCEF-63BE-53FEB9362B67` 含 `com.apple.kernel 628D9966-43C4-3A18-8F89-4FF3F4F4D86B`；`build-metadata.json` machine_config=SWEET。
- SENNA（2026-11-20 完成）：zip 67,563,990 字节 SHA-256 `AE380407D52993B7611310FB424F8468EC50CE7E65792FB408DA1CD6B1BDA332`；`kernelcache.senna` 21,184,512 字节（`3F04B42B716A7F1B29B6A2F73192EF3E14E015E761AA346DB4C8D7DE9ED8E294`），`kernel.development.senna` 18,388,744 字节（`1BE4BDD1603326F0280C079BC0EC723DDDCE3D53E6FC6AB5B73210092549919C`）；`kmutil inspect` → boot KC `BD57BEA7-2F30-1A64-7A68-88AA0EC28235` 含 `com.apple.kernel F84769AE-DEF9-3BB1-BAE4-0A9C0F66BC22`（Extension Information 为空）；`build-metadata.json` 为 machine_config=SENNA、soc=SM8475、runtime_support=not-implemented、dxb_commit=66390652…。SENNA 与 SWEET 大小相同但哈希不同 → 配置确实进入产物。

**边界（必须一起说）**：这是 `kmutil create -a arm64 -x` 的 **kernel-only boot kernel collection**，不是可引导 payload，不能直接 `fastboot boot`；SENNA 只是编译别名（SOC=SM8475、BASE_MACHINE_CONFIG=SWEET、runtime_support=not-implemented），未做任何 senna 硬件适配；rootfs 未改。

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
- `gh run download` 也不稳：本机两次出现目标文件长时间 0 字节、约 13 分钟无进展。artifact 走 `productionresultssa19.blob.core.windows.net`，单连接约 60 KB/s。实测可行做法：`gh auth token` → `curl -s -o NUL -D - -H "Authorization: token $tok" https://api.github.com/repos/awadmw/ios-sweet/actions/artifacts/<id>/zip` 取 302 `Location`，再 `curl -r start-end` 分段并发；**SAS URL 约 10 分钟过期**，过期连接会挂起，须重取 `Location` 只补缺失区间（注意 `-C -` 是从文件长度续传整个对象，不是补该段偏移，别用），最后按偏移拼接、用总尺寸 + SHA-256 双重校验。

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
- **显示是 DSI command mode + DSC**（bootargs 面板名 `..._nt37705_1240_2772_dsc_cmd`）：ABL 推一帧进面板 GRAM 后没有持续扫描输出 → 在 shim/XNU 里往 splash 区写像素**看不见**。带画面的判读必须先有 DPU+DSI+DSC 驱动；在那之前只能用 ramoops/pstore（或未验证的 UART）做反馈通道。
- **ramoops/pstore 通道已彻底关闭（2026-11-22 终判，不要再试）**：`0x240000@0xa7a5c0000`（ecc 0）地址本身稳定，但**跨重启不持久**——内核 `console [ramoops-1]` 每 boot 都在写、OPPO 的 `/system_ext/etc/init/init.oplus.debug.rc:816` 每 boot 都在拷 `console-ramoops-0`，可重启后 `/sys/fs/pstore` 恒为空；pmsg 写 marker 的对照实验同样归零（`build-chain/evidence/boot-attempts/20261122T022935Z-pmsg-persist.md`）。
- **`/dev/mem` 与 `/proc/kcore` 都不可用**：本机内核 `# CONFIG_DEVMEM is not set`、`CONFIG_PROC_KCORE is not set`；`mknod /dev/mem c 1 1` 能建节点但 `dd` 报 `No such device or address` → 用户态没有任何直读物理内存的途径。
- **OPPO minidump 不是常规通道**：`/data/persist_log/**/minidump*`、`rawdump`、`xbl_ramdump_a` 都只在崩溃时收集，正常 boot 后全空。
- **`fastboot boot` 后 adbd 可能长时间不枚举**（v0.5 实测：USB 上只有 MTP，10 min+ 无 adb）：此时设备其实是进了 Android 用户态，不是变砖；需用户解锁屏幕/重启把 adb 弄回来。

## 7. 未完成任务（按优先级）

**A. 构建链收尾 —— 已完成（2026-11-20）**
- A.1 ~~下载 SENNA 产物并校验~~：见第 4 节，zip 67,563,990 字节 / SHA-256 `AE380407…` 与 digest 一致，`kernelcache.senna`、`kernel.development.senna`、`kc-inspect.txt`、`build-metadata.json` 均已登记。
- A.2 ~~补进 BUILD-EVIDENCE.md 与 PROGRESS.md~~：已写入（BUILD-EVIDENCE 第 4 节改为“通过”）。
- A.3 ~~commit + push~~：见第 5 节提交记录。
- A.4 ~~本地 work 副本与远程对齐~~：`build-chain/work/ios-sweet` 的 5 个文件已按 `aea14cd` 覆盖（`xnu.yml`、`0019/0020/0026-stage-*.sh`、`xnu/senna/platform.sm8475.conf`）。
- 仍未做（A 段遗留）：`BUILDING.md` 终版同步到远程仓库；KC 归档清单 `SHA256SUMS.txt` 汇总。

**B. 证据补证**
- **B.1 dtc round-trip —— 已完成（2026-11-20，run 44673153305 success）**：结果 节点 4475=4475、属性 31220=31220、DTS diff 0 行、`VERDICT: PASS`；报告 `build-chain/evidence/dts-roundtrip/report.txt`，流程见 `build-chain/BUILD-EVIDENCE.md` 第 6 节。原始 DTB 走 release asset：release tag `dtb-evidence-v1`，asset `senna-live.dtb`（digest `7a290b13…3094`）。工具：`device-inventory/verify-dts-roundtrip.sh` + `.github/workflows/verify-dts.yml`（workflow_dispatch，ubuntu-24.04，apt 装 device-tree-compiler）。原始 DTB 不入库（`.gitignore` 有 `*.dtb`），以 release asset 提供：release tag `dtb-evidence-v1`，asset `senna-live.dtb`。计划步骤：`gh release create dtb-evidence-v1` 上传 `device-inventory/senna-live.dtb` → push → `gh workflow run verify-dts.yml` → 取 `dts-roundtrip` artifact 判读。
- **B.2/B.6 官方 OTA 交叉核对（已完成一半）**：`build-chain/ota-evidence/`。`RMX3706_13.1.0.115_CN01_rollback_4.0.zip`（7,585,057,674 字节）用 payload-dumper-go 抽 `dtbo`(=实机 `4F80DE98…`)、`vendor_boot`(=实机 `4AAB629E…`)、`uefi`（`F4CD52E1…`）、`boot`（`D9162A96…`，实机 `boot_b` 是 Magisk 补丁所以不同）。结论：DTBO 与 vendor_boot 来源已可追溯到官方全量包。**仍缺**：iOS 16.7.16 (20H392) rootfs。
- 仍缺：vendor_boot base 选择算法的 bootloader 侧证据；活动帧缓冲实际 stride/format；CNTFRQ_EL0 与 GIC 中断实测；EDL 演练。

**C. 引导链（主线；C.1 已通过，C.2 阻塞在「输出通道」上）**
- 设计：`build-chain/boot-chain/DESIGN.md`（v1 2026-11-20；2026-11-22 更新 §5 C.2、§6 未证项、§9 决策、§10 待办），路线 = 复用 ios-sweet shim，boot.img v4（v2 兜底）。
- **C.1 已通过（2026-11-22）**：`fastboot boot` 官方 stock 去填充镜像（`boot-trimmed.img` 48,345,088 B，sha256 `2698dbbe…be09`）→ `Sending 47212 KB OKAY [1.122s]` + `Booting OKAY [0.515s]`，9 s 回 adb、48 s 开机完成、槽位/解锁状态不变。→ **senna ABL 支持 `fastboot boot`**。证据 `build-chain/evidence/boot-attempts/2026-11-22T01-00Z-c1-stock.md`。
- **C.2 画屏路线证伪（2026-11-22，重大结论）**：面板是 DSI **command mode** + DSC（`from-binary.dts:16` bootargs 面板名 `..._dsc_cmd`），ABL 之后没有持续扫描输出，往 splash 区 `0xb8000000+0x2b00000` 写像素**永远不可见**。v0.2/v0.3 跑满全时长（v0.3 = 4.5 min）后自动 `PSCI_SYSTEM_RESET` 回 Android（uptime 归零）→ 代码执行链通，只是显示不可见。**对 C.3 的影响：XNU 上屏前置 = 移植 DPU+DSI+DSC 驱动**。
- **C.2 四条回读路线全部关闭（2026-11-22 终判）**：splash 帧缓冲（cmd-mode 不可见）、ramoops/pstore（跨重启不持久）、`/proc/kcore`（内核未编）、`/dev/mem`（内核未编）；OPPO minidump 只在崩溃时收集。→ **C.2 当前唯一阻塞点 = 输出通道**，通道未定前不再上机（上机也读不到）。
  - v0.4（commit `0b09995`，sha256 `dd919a15…fbc6`，ramoops 直写）：上机 `2026-11-22T01:10:31Z`，fastboot OK、30 s 回 adb，pstore 全空。
  - v0.5（commit `20c95d3b4403`，sha256 `a05c1136…a47a`，加 `dc civac`）：上机 `2026-11-22T01:15:46Z`，fastboot OK（`Total time: 0.789s`），之后 adbd 长时间不枚举（USB 只有 `CAPE-MTP _SN:78AD6B26`）。
  - 终判实验：`build-chain/tools/persist_test.py` 往 `/dev/pmsg0` 写 marker 再 `adb reboot`，重启后 pstore 连一条都没有（`build-chain/evidence/boot-attempts/20261122T022935Z-pmsg-persist.md`）→ 保留区不持久，**不是 shim 写错**。
- **C.2b 输出通道重选（当前唯一路径）**：候选排序 ① UART（`qcom,msm-geni-console` @`0x99c000`，SPI 608，GPIO26/27，function `qup7`）② 裸机 DWC3 USB 控制台（`a600000.ssusb` + QMP `88e8000.ssphy`）③ DPU+DSI+DSC（顺带解决 XNU 上屏，工程量最大）④ flash 草稿区（被「用户空间一字节不改」排除）。决策与验收见 `build-chain/boot-chain/DESIGN.md` §5 C.2b。
- **B 段顺带补齐的参数（都是本机出处，别再套 sweet）**：CNTFRQ = 19,200,000（`from-binary.dts:5883` + dmesg 19.20MHz）；架构 timer PPI = phys 14 / virt 11 / secure-phys 13 / hyp 12 全 level-low（`from-binary.dts:5882`）；GICv3 = 988 SPI + 16 PPI + GICR stride 0x40000 + ITS `0x17140000`（实机 dmesg）。
- C.3 前置未动：`mkadt.py` senna 参数（dram/GIC/UFS/timebase/VTIMER INTID/FB 几何）、`platform.sm8475.conf` 的 `RUNTIME_SUPPORT`、B 段剩余实测；**新增 DPU+DSI+DSC 显示驱动**。
- 任何实机动作前：给方案 + 回滚 + 用户确认；只 `fastboot boot`，不刷分区。
- 工具：`build-chain/tools/boot-attempt.ps1`（校验 sha256 → 探测设备 → 生成证据 → 仅 `-Confirm` 时 `fastboot boot`）；`build-chain/tools/persist_test.py`（pmsg 持久性终判）；`build-chain/tools/pstore-dump.sh`；`kcore-read.sh`/`kcore_phys.py`（已作废，内核没编 kcore）；`collect_readback.py`（pstore 空时转 kcore，已作废）。
**D. 内核/用户空间**
- 明确哪些 kext/用户态组件必须注入、哪些由内核补；rootfs 依然一字节不改（只读挂载或 overlay 方案需先论证）。
## 8. 下一会话第一件事

**现状（2026-11-22 终判）**：C.1 已通过（`fastboot boot` 可用）；C.2 的四条回读路线（splash 帧缓冲、ramoops/pstore、`/proc/kcore`、`/dev/mem`）全部关闭，OPPO minidump 只在崩溃时收集 → **当前唯一阻塞点 = 输出通道**。C.2b 方案已写入 `build-chain/boot-chain/DESIGN.md` §5，`PROGRESS.md` 已回填。

**第一件事：先决策，不要自己选**——UART 硬件能不能接触（拆后盖接 GPIO26/27，或已有 USB-TTL / 工程线 / 9008 线里带串口）？
- 能 → 走 **C.2b-UART**（成本最低、和 XNU 早期调试同一条路）。
- 不能 → 走 **C.2c 裸机 DWC3 控制台**（工程量大，但与 C.3 的 USB 驱动同源，不算白做）。

**UART 路线（先离线写清，再上机一次验证）**：
1. 写 `build-chain/boot-chain/UART.md`：GENI SE 在 `0x99c000`（窗口 `0x4000`）、SPI 608、引脚 GPIO26(TX)/GPIO27(RX)、function `qup7`、`115200n8`（出处 `from-binary.dts:17`、`:13812-13825`、`:2573-2584`）。只读 `GENI_S_STATUS`/`GENI_S_IRQ` 先判断 ABL 是否已把 SE 初始化过，再决定是否重配 `GENI_S_*`。
2. shim 侧加 `uart_putc()`，把 12 行 `TAG <hex>` 直接打到串口（不依赖 ramoops）；串口无输出时退回最原始的忙等轮询 TX FIFO。
3. 上机：`build-chain/tools/boot-attempt.ps1 -Image shim-v4 -Confirm`，PC 侧开串口记录（`mode COMx:115200,n,8,1` 或 PuTTY）。

**DWC3 路线（若 UART 不可行）**：先离线读 DTB `ssusb@a600000` + `dwc3-msm.ko` 的初始化序列与 QMP PHY `88e8000.ssphy`，只做 device-mode 枚举；**换自有 VID/PID**（不要复用 `18D1:4EE8`，会和 adb 抢），先写完代码再上机。

**不要再做的三件事**：读 pstore（跨重启不持久，已终判）、`/proc/kcore`+`/dev/mem`（内核没编）、画屏判读（面板是 DSI command mode + DSC，ABL 之后没有扫描输出）。

**通道打通之后**：把 12 项 `TAG` 值（DTB magic、CurrentEL、SCTLR、CNTFRQ、CNTPCT、GICD_PIDR2/TYPER、GICR_TYPER、ICC_SRE、PSCI 版本、IMEM restart reason、FB 读回）写回 `DESIGN.md` §6 与 `REMAINING.md`，然后进 C.3。

**边界不变**：只 `fastboot boot`，不刷分区、不动用户空间一字节；每次实机动作前先给「目标/做法/验收/失败日志」；执行器 `build-chain/tools/boot-attempt.ps1 -Image shim-v4 -Confirm`。
