# RMX3706 / senna-b XNU 移植进度

## 阶段 0：本机证据与可恢复性基线——通过（仅限已验证范围）

### 已完成
- ADB 设备序列号 78ad6b26，型号 RMX3706，Android 设备名 RE5860。
- 固件 RMX3706_13.1.0.115(CN01)；OTA RMX3706_11.A.45_0450_202308171956。
- Android 内核 5.10.149-android12-9-o-g36dae0b389f6；当前槽位 _b。
- verifiedbootstate=orange，vbmeta.device_state=unlocked，flash.locked=0。
- root 只读备份 boot_b、dtbo_b、vendor_boot_b、vbmeta_b；保存实时基础 DTB、cmdline、iomem、分区和属性。
- fastboot devices 已识别 78ad6b26；fastboot reboot 成功；设备已返回 Android，sys.boot_completed=1，槽位仍 _b、orange。
- bootloader getvar product 返回 taro；current-slot 返回 unknown command；unlocked、version-bootloader、is-userspace 返回 GetVar Variable Not found。

### 未完成／限制
- 未执行 fastboot boot，内存启动能力尚未验证。
- 未提供匹配官方全量 OTA；未验证 EDL 或其他深度救砖路径。
- 未刷写、未清空、未解锁、未修改任何设备分区。
- fastboot product=taro 只是平台标识，不是 senna-b UEFI/DTB 已适配证明。
- live base DTB compatible=qcom,cape-mtp/qcom,cape/qcom,mtp；不得直接当整机配置，需解析 DTBO/vendor_boot。

### 关键参数表
| 项目 | 值 | 来源 |
|---|---|---|
| boot_b | /dev/block/sde43，201326592 字节 | 本机 by-name、备份头 ANDROID! |
| dtbo_b | /dev/block/sde47，25165824 字节 | 本机 by-name、DTBO 表头 |
| vendor_boot_b | /dev/block/sde54，201326592 字节 | 本机 by-name、VNDRBOOT v4 |
| vbmeta_b | /dev/block/sde46，65536 字节 | 本机 by-name、AVB0 |
| live base DTB | 1118143 字节 | /sys/firmware/fdt，FDT 魔数 D0 0D FE ED |
| DTB SHA-256 | AB7B51E9564A168BA3AE93E22F70CEE32BA5CAF776A4438B3CF31B2A3CC77E57 | 主机计算 |
| 显示面板 compatible | qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd | 本机 /proc/cmdline |
| 触控标识 | synaptics-s3910 | 本机 /proc/cmdline |
| 项目号 | 22624 | 本机 /proc/cmdline oplusboot.prjname |

证据目录：stage-00-evidence。哈希见 stage-00-evidence/SHA256SUMS.txt；fastboot 原始输出见 fastboot-getvar.txt 和 fastboot-reboot.txt。

## 阶段 1：平台证据解析与 UEFI 源码核对——证据阶段通过

### 已完成
- 阶段 0 输入哈希全部一致；解析 16 个 DTBO overlay、3 个 vendor_boot base 和实时合并 FDT，保留二进制、文本、偏移和 SHA-256。
- senna-b 对应 `dtbo-entry-11.dtb`，model=`Qualcomm Technologies, Inc. Cape MTP, Senna B`，SHA-256=`D3169C92C8D9FC4DC49C94F18778A81391DE2CAF1AA9D9AE5BB0BBE4504F04CD`。
- 建立本机内存、8 CPU/PSCI、GICv3/PDC、timer、UART、UFS、MDP、NT37705 面板、synaptics-s3910 和保留区证据表。
- 固定审计 ios-sweet `45263bee51df4a0f55cdf9c649af886399488ddb`、UniXNU `519d80242a5028ee123447b01bc3b809baed565f`、edk2-msm `e1952621f419f8db60ed28271264e1b5184c571d`、darwin-xnu-build `663906528d1cd5ea8fde7de6f16de73db9511549`。
- 自动验收 54/54 通过；范围仅是主机侧证据完整性，不是启动功能测试。

### 未完成／限制
- 未证明 bootloader 的 vendor base 选择算法；最终硬件事实以实时合并 FDT 为准。
- active framebuffer base/stride/format、目标运行环境 arch timer CNTFRQ/IRQ、PSCI/UART 可访问性仍未知。
- 未建立 senna-b UEFI 设备包，未编译 XNU，未制作 shim/boot 镜像，未执行 fastboot boot；本阶段未连接或修改设备。
- edk2-msm 只有 SM8475 SoC 目录和 yudi 设备参考，没有 senna-b 直接支持；其他机型参数全部隔离。
- 匹配官方全量 OTA、EDL 救砖验证、原版 rootfs 获取与哈希核验仍未完成。

### 关键参数表
| 项目 | 值 | 来源 |
|---|---|---|
| senna-b overlay | DTBO entry 11，1212016 字节 | entry 11 与实时合并 FDT 根 model 一致 |
| 内存 | 5 段，合计 12655263744 字节；须排除 reserved-memory | live `/memory` |
| GICv3 | GICD 0x17100000+0x10000；GICR 0x17180000+0x200000 | live `/soc/interrupt-controller@17100000` |
| console | 0x0099c000+0x4000，SPI 608，115200n8 | live UART 节点和 bootargs |
| UFS | 0x01d84000+0x3000，SPI 265 | live `/soc/ufshc@1d84000` |
| 面板 | NT37705，1240x2772，DSC，60/90/120/144 Hz timings | live cmdline 和面板节点 |
| splash 保留区 | 0xb8000000+0x02b00000；不等于活动帧缓冲参数 | live `/reserved-memory/splash_region` |

完整报告：`stage-01-platform-evidence/STAGE1-REPORT.md`；原始值：`hardware-evidence.json`；仓库审计：`repository-audit.md`；失败记录：`FAILURES.md`；验收：`validation-results.json`；哈希：`SHA256SUMS.txt`。

下一阶段尚未开始。须先确定最小引导链设计、可复现构建环境、未知参数补证和回滚/验收日志，再决定是否生成任何启动镜像。

## 移植前设备信息采集（只读）

- 用户要求先采集、不写移植代码；已在 ADB `78ad6b26` 上执行只读脚本，未重启、未刷写、未在手机创建或修改文件。
- 已导出完整 `/proc/device-tree`：35,696 tar 成员；31,221 文件、4,475 目录完整展开，零错误。当前 `senna-live.dtb` 为 1,118,143 字节，SHA-256 `7A290B13563A058464FA01287FA801687B76E55A85A80867DDA76AAC73743094`；已生成本地解析器 DTS，标准 dtc 复核待办。
- 已形成 `DEVICE.md`：准确型号/系统/BL、5 段内存、GIC/Timer/UART、9 个 USID 的 PMIC、S3910 SPI0 CS0、NT37705 五组 DSI/DSC timing、Micron MT256GAXAT4U31 UFS 3.1（UniPro 1.8/M-PHY 4.1）、QCA6490 Wi-Fi/BT、55 项 reserved-memory、132 个 by-name 分区及三类复用清单。
- UniXNU 固定 main `519d80242a5028ee123447b01bc3b809baed565f` 没有 SM8475 机型路径，报告明确禁止虚构对照对象。
- 采集自动验收 26/26；阶段1回归验收 54/54。阶段1人工转录的 GICR `0x171c0000` 已按原始 DT 更正为 `0x17180000+0x200000`。
- 交付：`DEVICE.md`、`device-inventory/COLLECTION.md`、`device-inventory/validation-results.json`、`device-inventory/SHA256SUMS.txt`。未开始移植实现或实机启动。

## 2026-11-19 仓库托管与本地工具链

- 本机安装 Git 2.56.0（git-for-windows，`C:\Program Files\Git`）与 GitHub CLI 2.105.0（winget 用户范围），`gh auth login` 设备码流程完成；账号 awadmw，token scopes `repo, workflow, gist, read:org`；`gh auth setup-git` 已写入 `credential.https://github.com.helper`。
- 远程仓库：https://github.com/awadmw/senna-b-port （Public，默认分支 main）。首个 commit `426d2be`，远程共 279 个文件 / 16 个目录。
- 入库内容：`README.md`、`DEVICE.md`、`PROGRESS.md`、`REMAINING.md`、`RETROSPECTIVE.md`、`BUILDING.md`、stage-00/stage-01 证据与校验脚本、device-inventory 文本证据与解析器、build-chain 工作流与日志证据摘要。
- 明确排除（`.gitignore`）：`*.img *.bin *.tar *.dtb *.dts.txt *.log *.zip *.pyc *.exe *.dmg`、`device-inventory/device-tree/`（31,221 个文件的展开目录）、`build-chain/dxb|upstream|xnu-upstream` 第三方快照、`_github-staging/` 暂存区。原始整分区镜像与 45 MB 级 Actions 原始日志仍仅存本机。
- 边界：仓库只承载证据与流程记录，不含可启动镜像，不含任何 rootfs 修改。
## 2026-11-19 构建链：SWEET 基线产出真实 kernelcache

- Fork：https://github.com/awadmw/ios-sweet （上游 `45263bee51df4a0f55cdf9c649af886399488ddb`），固定 DXB `663906528d1cd5ea8fde7de6f16de73db9511549`。
- 失败序列（逐次真实日志）：run1 runner 不受支持 → run5/6/7/8/9/10/11 逐步定位到 `kmutil` 宿主 KDK、显式 kext 集、arm64/arm64e 架构、kernel-only 集合和 `Missing split seg v2`（plain arm64 缺 `LDFLAGS_KERNEL_ONLY_SUBARCH_arm64`）；run12–run16 定位到 KC 输出名带 `.<variant>` 后缀。
- run `44481202871`（提交 `c1c360d`）**success**，8m44s，产出 `xnu-kernelcache-SWEET`（67,562,895 字节，digest `sha256:6084969434F242277F2FAACD051D2ADDFC7671402A1AAC7EBD44E76D06BDBF5B`）与 `xnu-buildtree-SWEET`。
- 本地校验：下载 zip 的 SHA-256 与 GitHub digest 逐字符一致；解包得 `kernelcache.sweet` 21,184,512 字节（`D1B13A15…`）与 `kernel.development.sweet` 18,388,744 字节（`DD31242D…`）；`kmutil inspect` 显示 boot kernel collection `08A074F3-DF8A-CCEF-63BE-53FEB9362B67`，内含 `com.apple.kernel` `628D9966-43C4-3A18-8F89-4FF3F4F4D86B`。
- 边界：这是 **kernel-only boot kernel collection**，不是可引导 payload，不能直接 fastboot；机器配置为上游 SWEET（SM7150 参考），与 senna/SM8475 硬件无关。
- 详见 `build-chain/BUILD-EVIDENCE.md`，原始证据摘要见 `build-chain/evidence/kc-sweet/`。

## 2026-11-19 构建链：SENNA 编译别名

- `xnu/senna/platform.sm8475.conf`：`MACHINE_CONFIG=SENNA`、`SOC=SM8475`、`BASE_MACHINE_CONFIG=SWEET`、`XNU_BOARD_CONFIG=SWEET`、`RUNTIME_SUPPORT=not-implemented`；`xnu/senna/0001-empty.patch` 为纯注释、无 diff，CI 会拒绝任何非注释行。
- 已修真实阻塞：(1) 提交 `3c466f3` 把 `0019/0020/0026-stage-*.sh` 暂存脚本的 `MACHINE_CONFIG==SWEET` 守卫放宽到 `SWEET|SENNA`（否则 bearssl/libpthread/hfs 源码不落地）；(2) 提交 `19fb11b`/`aea14cd` 在 prepare-senna 阶段把 `*/conf/Makefile.template` 里 `ifeq ($(CURRENT_MACHINE_CONFIG),SWEET)` 守卫放宽到 `SWEET SENNA`（否则 `-include sweet_hfs_compat.h` 与 `SWEET_AES_INC` 不生效）。
- 失败证据：`build-chain/evidence/run19-senna-kc-guard-errors.txt`、`build-chain/evidence/run20-senna-bearssl-inc-errors.txt`。
- 状态：SENNA 运行仍在迭代，通过前不宣称已产出 senna kernelcache。
## 2026-11-20 构建链收尾：SENNA kernelcache 产出并通过本地校验（A 段完成）

- run `44489106397`（head `aea14cdc9f45289803caa76c02673a71c64253e3`）**success**，08:37–08:47Z，全部步骤通过；artifact `xnu-kernelcache-SENNA` id=14512706375，67,563,990 字节，digest `sha256:ae380407d52993b7611310fb424f8468ec50ce7e65792fb408da1cd6b1bda332`；`xnu-buildtree-SENNA` id=14512860694，23,196,244 字节。
- 本地校验：`build-chain/artifacts/kc-senna-artifact/xnu-kernelcache-SENNA.zip` = 67,563,990 字节，SHA-256 `AE380407D52993B7611310FB424F8468EC50CE7E65792FB408DA1CD6B1BDA332`，与 GitHub digest 逐字符一致；解包得 `kernelcache.senna` 21,184,512 字节（`3F04B42B…`）、`kernel.development.senna` 18,388,744 字节（`1BE4BDD1…`）；`kmutil inspect` 显示 boot KC `BD57BEA7-2F30-1A64-7A68-88AA0EC28235` 含 `com.apple.kernel F84769AE-DEF9-3BB1-BAE4-0A9C0F66BC22`；`build-metadata.json` 为 machine_config=SENNA、soc=SM8475、runtime_support=not-implemented。
- 与 SWEET 的产物大小相同但 SHA-256 不同，说明 SENNA 配置确实进入产物，不是重复打包。
- 本地 work 副本 `build-chain/work/ios-sweet` 已按远程 `aea14cd` 更新 5 个文件（`xnu.yml`、`0019/0020/0026-stage-*.sh`、`xnu/senna/platform.sm8475.conf`），与 fork HEAD 对齐。
- 下载踩坑（写进 HANDOFF）：`gh run download` 在本机会长时间 0 字节假死；artifact 走 Azure blob，单连接约 60 KB/s，SAS URL 约 10 分钟过期；必须用 `curl -r` 分段 + 过期后重取 302 只补缺失区间 + 按偏移拼接，最后用尺寸与 digest 双重校验。

## 2026-11-20 官方 OTA 交叉核对（B.6 第一半完成）

- 本机已有官方全量包 `downloads/RMX3706_13.1.0.115_CN01_rollback_4.0.zip`（7,585,057,674 字节，payload 7,585,052,078 字节，full payload，45 分区）与 `RMX3706_14.0.0.903_CN01_rollback.zip`（7,898,448,731 字节）。
- 用 `payload-dumper-go` 2.1.0 抽取 `dtbo/vendor_boot/uefi/boot` 到 `build-chain/ota-evidence/`：`dtbo.img` SHA-256 `4F80DE98…` = 实机 `dtbo_b.img`；`vendor_boot.img` `4AAB629E…` = 实机 `vendor_boot_b.img`（均逐字节一致）。
- `boot.img`（`D9162A96…`）与实机 `boot_b.img`（`5B470B39…`）**不一致**：实机 boot 在偏移 47,679,313 含 `MAGISK`、47,673,873 含 `androidboot`，是 Magisk 补丁镜像；本项目不使用 boot_b 作为证据。
- `uefi.img` 3,153,920 字节 `F4CD52E1…`，仅作阶段 3 对照，不刷写。
- 结论：DTBO（含 senna-b overlay entry 11）与 vendor_boot base DTB 的来源已从“只读采集推断”升级为“官方全量包逐字节一致”。

### 本阶段未完成／边界

- SENNA KC 仍是 **kernel-only boot kernel collection**，不是可 `fastboot boot` 的镜像；`runtime_support=not-implemented` 不变。
- B.1 dtc round-trip：见下文「2026-11-20 B.1 dtc round-trip 通过」，已完成。
- iOS 16.7.16 (20H392) rootfs 仍未获取/未做哈希登记；EDL 演练仍未做。

## 2026-11-20 B.1 dtc round-trip 通过（B 段可做部分完成）

- 原始 DTB 走 release asset：release `dtb-evidence-v1`（https://github.com/awadmw/senna-b-port/releases/tag/dtb-evidence-v1），asset `senna-live.dtb` 1,118,143 字节，GitHub 计算 digest `sha256:7a290b13563a058464fa01287fa801687b76e55a85a80867dda76aac73743094`，与实机 DTB 一致；DTB 仍不入库（`.gitignore` 有 `*.dtb`）。
- workflow `verify-dts.yml` run **44673153305**（head `2cb4118619f018dde2a17ea2408e38c5288e19c8`）`conclusion=success`；ubuntu-24.04 + DTC 1.7.0。
- 判读（报告 `build-chain/evidence/dts-roundtrip/report.txt`）：节点数 二进制 4475 = 重建 4475；属性数 31220 = 31220；两次 dtc 渲染的 DTS `diff` **0 行**；`VERDICT: PASS - dtc round-trip is identical`。重建 DTB 1,116,869 字节（`0dd5478c…`），与原 1,118,143 字节的差异只是字符串表/对齐，非语义。
- 边界：证明 `device-inventory/senna-live.dts` 与实机 DTB 语义等价，不证明节点在实机可访问（时钟/regulator/PHY 依赖仍未闭环）。


## 2026-11-20 C 段设计完成（DESIGN.md v1）+ 引导链静态证据

### 已完成

- 新增 `build-chain/boot-chain/DESIGN.md`（v1，165 行）：证据表（每条带 `from-binary.dts` 行号）、boot.img/vendor_boot v4 头解析、`fastboot boot` 支持性无静态证据的结论、路线比较（shim vs edk2-msm，选 shim）、C.1/C.2/C.3 三级计划（每级目标/做法/验收/失败日志）、未证项探测方法、回滚、失败日志模板、待办。
- 路线决策：复用 ios-sweet 的 shim（ABL → `fastboot boot` shim → XNU），不 clone edk2-msm；boot.img 目标版本 **v4**（实机 OTA 已证 v4 可解析），ramdisk 定位加 `0x1000000` 扫描回退，避免依赖 ABL 传 DTB。
- 静态证据新增（本机 DTB，dtc 反编译件行号）：
  - IMEM 基址 `0x146aa000` + `restart_reason@65c` → `0x146aa65c`（`from-binary.dts:12935-12950`）；与 sweet 数值相同但有 senna 独立出处。
  - 控制台 GENI SE `0x99c000+0x4000`，`qcom,msm-geni-console`，SPI 608（`from-binary.dts:13812-13825`）。
  - UFS host `0x1d84000`，`compatible = "qcom,ufshc"`，PHY `qcom,ufs-phy-qmp-v4-cape`（`from-binary.dts:12729`、`:426`）。
  - PSCI 1.0 / smc（`:1197-1199`）；8 核（`:492-`）；GICv3 `0x17100000+0x10000`、GICR `0x17180000+0x200000`、stride `0x40000`（`:1323-1330`）。
  - 架构 timer `0x124f800` = 19,200,000（`:7481-7487`）；splash 区 `0xb8000000+0x2b00000`（`:412-416`）；面板 1240×2772（`:14186`、`:21564-21569`）。
- bootloader 镜像不可读结论：`abl.img` 熵高（加密/压缩）、`uefi.img` 是 EDK2 LinuxLoader 配置（`DefaultBDSBootApp = "LinuxLoader"`），三者合计 0 条 `fastboot` 字符串 → `fastboot boot` 必须实机验证。
- `HANDOFF.md` 第 8 节已改写为「设计已完成、路线已定、下一步 C.1 需用户确认」。

### 未完成

- C.1 机制演练（`fastboot boot` 官方 stock `boot.img`）：需设备进 bootloader + 用户在场确认。
- C.2 senna 诊断 shim：`build-chain/work/senna-shim/` 尚未创建；常量替换、FB/VTIMER 探测、CI 构建均未开始。
- C.3 XNU 接管：依赖 `mkadt.py` senna 参数、`platform.sm8475.conf` 的 `RUNTIME_SUPPORT`、B 段剩余实测项。
- B 剩余：帧缓冲 stride/format 实测、CNTFRQ_EL0 与 GIC 中断实测、EDL 演练、iOS 16.7.16 rootfs。

### 关键参数表（senna，均有出处）

| 参数 | 值 | 出处 | 状态 |
| --- | --- | --- | --- |
| GICD | `0x17100000+0x10000` | `from-binary.dts:1323-1330` | 证 |
| GICR | `0x17180000+0x200000`，stride `0x40000` | 同上 | 证 |
| PSCI | 1.0 / smc，8 核 | `from-binary.dts:1197-1199`、`:492-` | 证 |
| timer 频率 | 19,200,000（`0x124f800`） | `from-binary.dts:7481-7487` | 证（待 `CNTFRQ_EL0` 复核） |
| 控制台 UART | GENI `0x99c000`，SPI 608 | `from-binary.dts:13812-13825` | 证（可用性未证） |
| IMEM restart reason | `0x146aa65c` | `from-binary.dts:12935-12950` | 证 |
| UFS | `0x1d84000` | `from-binary.dts:12729` | 证 |
| splash 区 | `0xb8000000+0x2b00000` | `from-binary.dts:412-416` | 证（FB base/stride/format 未证） |
| boot.img | v4，kernel 46,634,324（arm64 Image）、ramdisk 1,698,305（LZ4） | `ota-evidence/boot.img` | 证 |
| vendor_boot | v4，`ramdisk_addr 0x1000000`、`tags_addr 0x100` | `ota-evidence/vendor_boot.img` | 证 |

## 2026-11-20 C.2 senna 诊断 shim：源码 + CI 镜像就绪（未上机）

### 已完成
- 源码树 `build-chain/work/senna-shim/`：`start.S`（arm64 Image 头 + 16 向量，复用 ios-sweet）、`shim.ld`、`board.h`（senna 常量，逐条带 DTB 行号）、`console.c/h`（splash 上 8×16 字模 ×3 放大，运行期可切 stride/R-B）、`senna.c`（探测 + 4 组帧缓冲候选 + panic 页 + 30 s 倒计时 + `PSCI_SYSTEM_RESET`）、`font.h`、`tools/mkbootimg_img.py`（v4/v2 打包 + `--pad-image`/`--check-image`）、`build.sh`、`README.md`。
- CI `.github/workflows/senna-shim.yml`（workflow_dispatch + push 触发，ubuntu-24.04，装 `gcc-aarch64-linux-gnu`，构建后附 `readelf -h/-S` 与入口 `objdump` 便于离线核对）。
- run **44677167822**（v0.1）与 **44678828635**（v0.2，信息页 20 s / 每组 10 s / 倒计时 20 s，标题含 `v0.2`）均全绿：`out/shim.bin` 81,920 B、`out/shim.elf` 39,792 B、`out/senna-shim-v4.img` 86,016 B、`out/senna-shim-v2.img` 86,016 B。
- 修补一处真实失败：`objcopy` 不输出栈/BSS 预留区，导致 arm64 头 `image_size 0x14000` > 文件长度 12,433 → `bad Image header`；加 `--pad-image` 按 `image_size` 补齐后通过。
- 入口离线证据（CI run 44678271929 的 `Disassemble entry point` 步骤）：`readelf` Entry point `0x0`、`.text` @0x0、`.rodata` @0x2660、`.bss` @0x30a0；`objdump` 反汇编 `0: 14000200 b 800 <_start>`，即 arm64 头 code0 无条件跳到 `_start`（0x800），与 `--check-image` 的校验一致。

### 未完成
- ~~C.1 机制演练 + C.2 上机~~ 已由下一节（2026-11-22）完成：C.1 通过，C.2 画屏证伪后改走 ramoops。
- C.3：未开始。

### 关键参数表（镜像与入口）

| 项 | 实测值 | 出处 | 状态 |
| --- | --- | --- | --- |
| v4 镜像 | magic `ANDROID!`、header_size 1584、header_version 4、kernel 81,920 @0x1000、ramdisk_size 0、os_version `0x18000177` | `out/senna-shim-v4.img` | 证 |
| v4 sha256 | `7483023e9843f9e17ae9128e72664f2aadf27c1e16c9b6b408fa9a140087f907` | 同上 | 证 |
| v2 镜像 | kernel_addr `0x8000`、ramdisk_addr `0x1000000`、tags `0x100`、page 4096、header_version 2、dtb_size 0 | `out/senna-shim-v2.img` | 证 |
| v2 sha256 | `1f7f4dafa764df746cb6205d489405f8fe5a6688a2c41d0f80baa12cfb92ed12` | 同上 | 证 |
| 入口 | arm64 头 code0 `0x14000200`（`b _start`）、`image_size 0x14000`、flags `0xa`、magic `ARMd` | `--check-image` + `objdump` | 证 |
| FB 候选 | stride 4960/R-B 正常、4960/R-B 交换、5120、4992；各 7 s | `senna.c cands[]` | 待实机判读 |
| 探测项 | PSCI 版本、`CNTFRQ_EL0`、GICD/GICR TYPER、DTB magic、`0x1000000` ramdisk、IMEM restart reason | `senna.c probe_all()` | 待实机判读 |

### 环境与推送
- 本机无 clang/gcc，交叉编译只能走 GitHub Actions；`C:\Android\platform-tools` 有 adb/fastboot。
- 本机 DNS 把 `github.com` 污染成 `20.6.7.17`，`git push` 连不上（`api.github.com` 正常）→ 新增 `build-chain/tools/push_via_api.py`：用 `gh auth token` 走 Git Data API 建 blob/tree/commit 并更新 `main`，把 remote sha 记到 `.git/remote_main_sha`，之后 `git push` 恢复即可停用。
- 实机执行器 `build-chain/tools/boot-attempt.ps1`：校验镜像 sha256（内置 v4/v2 基线）→ 探测 fastboot 设备 → 写 `build-chain/evidence/boot-attempts/<UTC>-<image>.md` 计划 → 仅 `-Confirm` 且设备在线时执行 `fastboot boot` 并落盘输出；无 `-Confirm` 只生成计划，不做任何引导。用法见脚本头注释（用 `powershell -File`，本机无 `pwsh`）。
- 坑：Windows PowerShell 5.1 按 ANSI 解析无 BOM 的 `.ps1`，含中文会报“字符串缺少终止符”→ `.ps1` 必须存成 UTF-8 带 BOM。

## 2026-11-22 C.1 通过 + C.2 上机：画屏证伪 → 改走 ramoops/pstore

### 已完成
- **C.1 机制演练通过**：`fastboot boot boot-trimmed.img` 输出 `Sending 'boot.img' (47212 KB) OKAY [1.122s]` / `Booting OKAY [0.515s]` / `Finished. Total time: 1.657s`；9 s 后 adb 回归，48 s 后 `sys.boot_completed=1`，`ro.boot.slot_suffix=_b`、`verifiedbootstate=orange` 不变。→ **senna ABL 支持 `fastboot boot`**（此前 uefi.img 静态扫描 0 命中 fastboot 命令，只能实机判定）。
- **stock 镜像去填充**：`ota-evidence/boot.img` 是 192 MiB 整分区 dump，AVBf footer @`0xbffffc0` 给出 `original_image_size=48345088`；去填充后 `boot-trimmed.img` 48,345,088 B，sha256 `2698dbbe0d4c638c9b0cde4c401a6b15f865a26049c89eb22518aca61eb9be09`（`*.img` 不入库）。
- **画屏路线证伪（关键结论）**：面板是 DSI command mode + DSC（bootargs `msm_drm.dsi_display0=qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd`，`from-binary.dts:16`）；ABL 推一帧进面板 GRAM 后没有持续扫描输出，写 splash 区永远不可见。v0.2/v0.3 跑满全时长（v0.3 = 4.5 min）后自动 `PSCI_SYSTEM_RESET` 回 Android（uptime 归零），说明**代码执行链通、只是显示不可见**。→ C.3 上屏前置升级为「DPU+DSI+DSC 驱动」。
- **ramoops 通道判定**：实机 dmesg 两次独立重启都是 `ramoops: using 0x240000@0xa7a5c0000, ecc: 0`（地址确定）；DT `ramoops_region` 无 `reg`（`from-binary.dts:381-389`），由内核启动时分配。`ecc: 0` → 校验只剩 sig：DRAM 里必须是 `0x43474244`（`fs/pstore/ram_core.c` `persistent_ram_post_init`）；本机 `record_size=0`，console 区落在区域基址。
- **shim v0.4**（commit `0b09995`，CI run 44970068008）：探测结果编成 12 行 `TAG <hex>` 文本，在 base±2 MiB 内每 4 KiB 页写 `{sig=0x43474244,start=0,size}` + 文本，3 s 后 `PSCI_SYSTEM_RESET`。上机 `2026-11-22T01:10:31Z`：fastboot `Sending 84 KB OKAY`/`Booting OKAY`，30 s 回 adb、63 s 开机完成，但 **pstore 全空**（`console-ramoops-0`/`console-ramoops`/`dmesg-ramoops-0`/`last_kmsg.txt` 全 MISSING）。
- **shim v0.5**（commit `20c95d3b4403`，CI run 44970517965）：只加 `dc civac` 逐 64 B 行清理 + `dsb sy; isb`（假设 ABL 交给 shim 时 MMU 开着且映射 cacheable，PSCI reset 会丢未回写的数据），其余不动。上机 `2026-11-22T01:15:46Z`：fastboot 同上（`Total time: 0.789s`），之后 **adb 再未枚举**；USB 上稳定出现 `CAPE-MTP _SN:78AD6B26`（VID_18D1&PID_4EE8，10 min 以上）→ 系统进了 Android 用户态但 adbd 没起来，pstore 取不到。
- **取证工具**：`build-chain/tools/pstore-dump.sh`（设备侧读 pstore/last_kmsg）、`build-chain/tools/kcore-read.sh` + `build-chain/tools/kcore_phys.py`（解析 `/proc/kcore` ELF64 PT_LOAD，按 `PAGE_OFFSET 0xFFFF000000000000 + phys` 算出 dd 偏移，直接验证物理 `0xa7a5c0000` 是否被写入，绕开 pstore 校验）。
- 文档：`build-chain/boot-chain/DESIGN.md` §5 C.2 重写（cmd-mode 结论 + ramoops 通道 + v0.3/v0.4/v0.5 证据）、§6 未证项表按新事实改写、§9 新增 3 条决策、§10 待办重排。

### 未完成
- **v0.5 结果未知**：无法判断是「跑完正常 reset」还是「看门狗复位」；pstore 未读、`0xa7a5c0000` 是否真的写进 DRAM 未验证。v0.4 是 30 s 内 adb 回来，v0.5 明显不同 → 可疑。
- 12 项探测值（DTB magic、CurrentEL、CNTFRQ、GIC TYPER、PSCI 版本、IMEM restart reason、splash 读回等）全部还没有回读。
- C.3 未开始，且新增前置：XNU 上屏需要 DPU+DSI+DSC。
- B 剩余：EDL 演练、iOS 16.7.16 rootfs 未动。

### 关键参数表（ramoops 与 v0.4/v0.5）

| 项 | 实测值 | 出处 | 状态 |
| --- | --- | --- | --- |
| ramoops 区 | `0x240000@0xa7a5c0000`，`ecc: 0` | 实机 dmesg（两次重启一致） | 证 |
| ramoops 布局 | size 0x240000、console 0x40000、pmsg 0x200000、record_size 0 | `from-binary.dts:381-389` + dmesg | 证 |
| 头结构 | `{u32 sig; u32 start; u32 size; u8 data[]}`，sig 必须 `0x43474244` | `fs/pstore/ram_core.c:33-38`、`:488-530` | 证 |
| 读取路径 | `pgprot_noncached` 逐页 vmap，直接读 DRAM | `fs/pstore/ram_core.c:399-437` | 证 |
| v0.4 sha256 | `dd919a15c31d444e5854b8e3c6deee21b9eb1569c7f8f38c4d45b2700dcffbc6` | CI 44970068008 | 证 |
| v0.5 sha256 | `a05c1136a35c4936b16103ec964400817d869d71330cf2b53cd49d29518ca47a` | CI 44970517965 | 证 |
| v0.5 v2 等价镜像 | `eca04eddfa136184c1a214eac7a10323e92ecdb78a8b46dd9d5292abcd3935b3` | 同上 | 证 |
| splash 区 | `0xb8000000+0x2b00000`，`/proc/iomem` 里是 reserved | `from-binary.dts:412-416`、实机 iomem | 证（但 cmd-mode 下写它不可见） |

### 证据与工具索引
- `build-chain/evidence/boot-attempts/2026-11-22T01-00Z-c1-stock.md`（C.1 全部原样日志）+ `c1-after-boot.png`
- `build-chain/evidence/boot-attempts/20261122T011031Z-shim-v4.md`（v0.4）
- `build-chain/evidence/boot-attempts/20261122T011546Z-shim-v4.md`（v0.5；真输出在 `.fastboot.err`）
- `build-chain/work/k_ram.c` / `k_ram_core.c` / `k_pstore_ram.h`（v5.10 pstore 源码，判 sig 语义用）

### 环境坑（新增）
- `edit`/覆盖写 `.ps1` 会丢 UTF-8 BOM → PS 5.1 按 ANSI 解析，中文报 `Unexpected token`；修法：python 用 `encoding='utf-8-sig'` 读写。
- 在 run_code 的 JS 模板字符串里直接写 PowerShell 的反引号换行转义（反引号加 r 再加反引号加 n）会把模板截断，导致 `Expected ',', got 'ident'`；改用字符串数组拼 `[Environment]::NewLine`。
- `gh run download` 没有 `--clobber`，重复下载前要先删目标目录。
- `gh api repos/torvalds/linux/contents/drivers/pstore/...` 恒 404：pstore 在 `fs/pstore`，且这类取文件用 `raw.githubusercontent.com` 更稳。
## 2026-11-22（续）ramoops 终判「不持久」→ 通道关闭；输出通道重选（C.2b）；参数表补证

### 已完成
- **ramoops 终判：跨重启不持久 → 通道关闭**。新增 `build-chain/tools/persist_test.py`：先 `echo '<marker>' > /dev/pmsg0` + `sync`，`adb reboot`，等 `sys.boot_completed=1` 后再查 pstore。证据 `build-chain/evidence/boot-attempts/20261122T022935Z-pmsg-persist.md`：marker `SENNA-PMSG-PERSIST-20261122T022722Z`、重启前 `write_ok`、重启后 `/sys/fs/pstore` **total 0**、`dump-all`/`marker-grep`/`dropbox-grep` 全空 → 退出码 1（不持久）。
- **旁证（不是 Android 删的）**：新 boot 的 dmesg 里 `[5.754536] init: Command 'copy /sys/fs/pstore/console-ramoops-0 /data/debugging/last_kmsg.txt' ... failed: Could not read input file ... No such file or directory`（`/system_ext/etc/init/init.oplus.debug.rc:816`）→ OPPO 自己每 boot 都在等这个文件，它从未出现过。
- **用户态直读物理内存全部关闭**：`/proc/config.gz` 里 `CONFIG_PROC_KCORE is not set`、`# CONFIG_DEVMEM is not set`；`mknod /dev/mem c 1 1` 能建节点，但 `dd if=/dev/mem` 报 `No such device or address` → kcore/devmem 两条路永久作废。
- **OPPO minidump 查完：不能当常规通道**。属性 `ro.oplus.minidump.kernel.log.support=true`、`persist.vendor.ssr.enable_ramdumps=1`、`init.svc.vendor.ss_ramdump=running`(pid 2700)；分区 `logdump 512 MiB`、`rawdump 256 MiB`、`logfs 8 MiB`、`xbl_ramdump_a 2 MiB`；但 `/data/persist_log/DCS/{de,en}/minidump` 与 `minidumpbackup`（`sdf10`）都是空的 → 只在崩溃时收集，且需内核先写 minidump 表。
- **参数表补证（本机 DTB + 实机 dmesg，无套用）**：
  - CNTFRQ = **19,200,000**（`from-binary.dts:5883` `clock-frequency = <0x124f800>`；dmesg `arch_timer: cp15 and mmio timer(s) running at 19.20MHz (virt/virt)`）。
  - 架构 timer PPI：**secure-phys 13 / phys 14 / virt 11 / hyp 12**，全 level-low（`from-binary.dts:5882`）；dmesg `GICv3:arch_timer(11)` 与 virt=11 对上。sweet 的 19/18 不采用。
  - GICv3：**988 SPIs、16 PPIs、0 Extended SPIs、无 Range Selector**；GICR stride `0x40000`（CPU0 `0x17180000`、CPU1 `0x171c0000`…）；ITS `0x17140000`（dmesg `Devices Table too large, reduce ids 32->19`）。
  - 内存：`/proc/iomem` 见 `800000000-8398fffff`、`840000000-a7fffffff`（9 GiB）、`a0400000-a6dfffff`、`a7000000-e05fffff`、`f1400000-ffffffff`；`MemTotal 11,488,152 kB`；ramoops `0xa7a5c0000` 落在 `840000000-a7fffffff` 内 → 地址合法。
  - UART：`0x99c000`、SPI 608、**GPIO26(TX)/GPIO27(RX)、function `qup7`**（`from-binary.dts:2573-2584`、`:17`）；实机 `/dev/ttyMSM*` 不存在（`con_enabled=0`），只有 `/dev/ttyHS0`（蓝牙）。
  - USB：`a600000.ssusb`（`msm-dwc3`、模块 `dwc3-msm.ko`、QMP PHY `88e8000.ssphy`、EUD `88e0000.qcom,msm-eud`），UDC `a600000.dwc3`。
  - 显示：无 `/sys/class/graphics`；DRM `card0-DSI-1`/`-DSI-2`/`-DP-1`/`-Virtual-1` + `sde-crtc-0..5`；DSI PHY `ae94400`/`ae96400`，`dsi0_phy_pll_out_dsiclk` 166.4 MHz。
- **C.2b 输出通道重选写入 `build-chain/boot-chain/DESIGN.md`**：已证伪候选表（splash / ramoops / kcore / devmem / minidump）+ 剩余候选排序（① UART ② 裸机 DWC3 ③ DPU+DSI+DSC ④ flash 草稿区因「用户空间一字节不改」排除）+ 决策「优先 UART，否则立 C.2c 裸机 DWC3 控制台」。

### 未完成
- **C.2 仍阻塞在输出通道**：shim 的 12 行 `TAG <hex>` 一条未读回；通道落地前不再上机（上机也读不到）。
- UART 接线方案 / C.2c 裸机 DWC3：都未启动。
- C.3 未开始：`mkadt.py` senna 参数、`platform.sm8475.conf` 的 `RUNTIME_SUPPORT`、DPU+DSI+DSC 显示、iOS 16.7.16 rootfs 均未动。
- B 剩余：EDL 演练、iOS 16.7.16 rootfs。

### 关键参数表（本轮新增/改判）

| 项 | 值 | 出处 | 状态 |
| --- | --- | --- | --- |
| CNTFRQ | 19,200,000 | `from-binary.dts:5883` + 实机 dmesg | 证 |
| PTIMER / VTIMER PPI | 14 / 11（另 13 secure-phys、12 hyp），level-low | `from-binary.dts:5882` | 证 |
| GICv3 拓扑 | 988 SPI、16 PPI、GICR stride 0x40000、ITS 0x17140000 | 实机 dmesg | 证 |
| UART 引脚 | GPIO26 TX / GPIO27 RX，qup7，115200n8 | `from-binary.dts:2573-2584` | 引脚证；可用性未证 |
| DWC3 / QMP / EUD | `0xa600000` / `88e8000` / `88e0000` | 实机 sysfs + DTB | 证 |
| DSI PHY | `ae94400`、`ae96400` | 实机 `regulator_summary` | 证 |
| ramoops 持久性 | **不持久** | `20261122T022935Z-pmsg-persist.md` | 证（通道关闭） |
| `/dev/mem`、`/proc/kcore` | 内核未编 | `/proc/config.gz` | 证（路线关闭） |

### 证据与工具索引
- `build-chain/tools/persist_test.py`（pmsg 持久性终判；0 持久 / 1 不持久 / 2 等不到设备）
- `build-chain/evidence/boot-attempts/20261122T022935Z-pmsg-persist.md`（marker `SENNA-PMSG-PERSIST-20261122T022722Z`）
- `build-chain/evidence/boot-attempts/20261122T022610Z-pstore-after-reboot.md`（重启后 pstore 复查，仍空）
- 临时脚本（不入库）：`build-chain/work/{dump_probe,minidump_probe,devmem_probe,facts_probe,debugfs_probe}.sh`

### 环境坑（新增）
- `mount -t debugfs none /sys/kernel/debug` 在 toybox 下报 `bad /etc/fstab`；改 `mount -t debugfs debugfs /sys/kernel/debug` 才成功。
- `cat /sys/class/drm/...` 即便 `su` 也 `Permission denied`（SELinux `Enforcing`）。
- 长任务（等重启、轮询 adb）必须 `run_in_background: true`：`run_code` 的 120 s 上限会杀掉前台进程，`pwsh` 的 `timeoutMs` 不覆盖它。
- 用 pwsh 拼中文长文本写文件时，`cd` 后接相对路径不生效（被解析到 `default-workspace`）→ 一律用绝对路径，或改用 `edit` 在唯一锚点后追加。

## 2026-11-22（续 2）C.2c 裸机 DWC3 控制台设计 v1（离线，未上机）

### 背景与决策
- 用户 m01641 在三个选项里选「2」：**UART 硬件不可接触** → 走 C.2c 裸机 DWC3 控制台，先离线设计、不占用设备。
- 前序结论不变：画屏（cmd-mode 面板）、ramoops/pstore、`/proc/kcore`、`/dev/mem` 四条通道全关闭（见上一节）。
- UART 设计 `build-chain/boot-chain/UART.md` 保留备查，不再推进。

### 已完成
1. 新增 **`build-chain/boot-chain/USB-CONSOLE.md`（v1）**：目的/非目标、通道对比、DTB 证据表、DWC3 寄存器表（Linux v6.6 出处）、U1/U2/U3 三个未知、路径 A/B/C、D0–D4 计划、主机工具、风险表、决策记录。
2. 新增 **`build-chain/tools/usb_watch.py`**（D0 主机侧观测器）：每 `--interval` 秒跑一次 `fastboot devices`，设备在场时再跑 `getvar product` 判是否应答，可选抓 `Get-PnpDevice` 快照，写 CSV，结束按 A/B/C 三种结论打印退出码（A=0 / B=1 / C=3 / 无样本=2）。
   - 冒烟（设备在 Android 时）：`dev=0` 采样 2 次 → `VERDICT B`，脚本可用。
3. `DESIGN.md`：§5 新增「C.2c 裸机 DWC3 控制台」小节；§9 决策记录加 1 条；§10 待办改为 6 / 6a / 6b（决策完成 → 设计完成 → D0 待做）。

### 关键判据（D0 / U1）

| 主机侧现象 | 含义 | 下一步 |
| --- | --- | --- |
| 设备在场、`fastboot devices` 有设备、`getvar` 超时 | ABL 留下的 gadget 还在总线上 | **路径 A**：复用 EP1 bulk IN 发数据（~200 行） |
| 设备消失（`Get-PnpDevice` 里也无 18D1） | ABL 已拆 USB | **路径 B**：重配 DWC3 + EP0 状态机（~600 行） |
| 设备在场且 `getvar` 正常应答 | ABL 仍在跑 / 设备已回 fastboot | 重测（正常不可能） |

### 关键参数表（本轮新增，全部有出处）

| 项 | 值 | 出处 |
| --- | --- | --- |
| USB 控制器 | `ssusb@a600000`，`reg = <0xa600000 0x100000>` | `from-binary.dts:20889-20895` |
| DWC3 核 | `dwc3@a600000`，`reg = <0xa600000 0xd93c>` | `:20918-20920` |
| DWC3 中断 | SPI 133（`<0 0x85 4>`） | `:20925` |
| wrapper 中断 | pwr_event SPI 130（PDC）、ss_phy 17、dp_hs_phy 14、dm_hs_phy 15 | `:20901-20902` |
| 核时钟 | 200 MHz（`0xbebc200`）/ 断连 133.3 MHz / HS 66.7 MHz | `:20906-20908` |
| USB2 PHY | `hsphy@88e3000`，`qcom,usb-snps-eusb2-phy`（**eUSB2**，+外部 repeater） | `:20953-20967` |
| USB3/DP PHY | `ssphy@88e8000`，`0x88e8000+0x3000`，init-seq 164 组 + 13 项偏移表**在 DTB 里** | `:20969-20986` |
| EUD | `0x88e0000+0x2000`，SPI 11，`qcom,secure-eud-en` | `:12884-12896` |
| DWC3 寄存器 | `GCTL 0xc110`、`DCFG 0xc700`、`DCTL 0xc704`、`DEVTEN 0xc708`、`DSTS 0xc70c`、`GEVNT* 0xc400+`、`DEP_BASE(n)=0xc800+n*0x10` | Linux v6.6 `drivers/usb/dwc3/core.h` |
| 事件缓冲 | 4096 B / 4 B 一项 = 1024 项；`GEVNTCOUNT.EHB` bit31 | 同上 |
| TRB | 16 B（bpl/bph/size/ctrl）；`TRBCTL(n)=n<<4`、`IOC` bit11、`LST` bit1、`HWO` bit0 | 同上 |

### 未完成
- ~~`senna-shim-v0.6spin` 镜像~~ 已出（见下节）；**D0 仍未执行，U1 未判**。
- `build-chain/tools/usb_console.py`（pyusb 读 EP1 IN）未写，等 U1 结论。
- 路径 B 的 EP0 状态机、CDC-ACM 描述符未设计到代码级。

### 环境坑（新增）
- 用 JS 模板字符串写含大量 Markdown 反引号的文档会直接截断模板（报 `Identifier cannot follow number`）→ 先拿 `¶` 当反引号占位，写完后在 JS 里把占位符替换回真反引号。
- PowerShell 5.1 控制台是 cp936，python 打印中文变乱码 → 脚本对外输出统一用 ASCII（日志/CSV 里再写中文）。

## 2026-11-22（续 3）v0.6spin（D0 保持构建）就绪

**目的**：把 D0 从「还要先出镜像」变成「一条命令 + 2 分钟窗口」，不占用设备、不引入新参数。

### 已完成
- `build-chain/work/senna-shim/senna.c` 两处改动（单变量，别的没动）：`SENNA_RAMOOPS_WRITE 0`（`ramoops_write()`/`flush_range()`/`dc_civac()` 整段编译掉，D0 不写任何内存）、`SENNA_D0_HOLD_MS 120000`（静置 2 min 后 `PSCI_SYSTEM_RESET`）；版本串 `v0.6spin` / `D0 HOLD`，标题 `SENNA SHIM v0.6spin (D0 hold)`。
- CI run **`44977828469`** success（39 s）；产物 `build-chain/work/senna-shim/out/`：`shim.bin` 81,920 B、`shim.elf` 38,560 B、`senna-shim-v4.img` 86,016 B、`senna-shim-v2.img` 86,016 B。
- sha256：v4 `bb0a77605dcca97ccb33ed9824e36314c0abef0a6b5133ed0a4e56a294cb0caf`；v2 `27280276aadaa0921ad1707cb45bba40d3670e989b17f3c6f9d98012ad8e635c`。
- 校验：`shim.bin` 含 `v0.6spin`×2 / `D0 HOLD`×1，**不含** `v0.5`；arm64 Image magic `0x644d5241`、text_offset 0、image_size 81,920；v4 头 `ANDROID!`、hdrver 4、ksize 81,920、rsize 0、hsz 1584。
- `build-chain/tools/boot-attempt.ps1` 基线同步为上面的 v4/v2 sha（按字节替换，保住 UTF-8 BOM + CRLF，diff 只 2 行）；`-Image shim-v4` 计划模式实跑通过（sha 命中），写出 `build-chain/evidence/boot-attempts/20261122T025031Z-shim-v4.md`（plan-only）。
- `build-chain/work/senna-shim/README.md` 增「v0.6spin（D0 保持构建）」小节（一次性构建、A/B/C 判读口径、完事把 `SENNA_RAMOOPS_WRITE` 改回 1）。

### 未完成
- **D0 本体未执行**（需要设备在场 + 2 分钟窗口）：先起 `python build-chain/tools/usb_watch.py --pnp-only --duration 150 --out build-chain/evidence/boot-attempts/d0-usb-watch.csv`，再另一个窗口 `boot-attempt.ps1 -Image shim-v4 -Confirm`。（**2026-11-22 修正**：必须 `--pnp-only`，见「续 4」事故。）
- U1 未判 → 路径 A（继承 EP1，~200 行）/ 路径 B（重建 DWC3，~600 行）未选。

### 环境坑
- `python io.open(..., encoding="utf-8-sig")` 读 `.ps1` 会把 CRLF 统一成 LF，再用 `newline=""` 写回会整文件换行全变（129 行全 dirty）→ 改 `.ps1` 一律按 `rb`/`wb` 做字节替换。
- **`boot-attempt.ps1` 生成证据文件的隐藏 bug（本轮修掉）**：PowerShell 里 `,` 比 `+` 结合更紧，`'a' + $x,` 会把后面的数组元素当字符串拼进来（用空格连接）→ 整个计划段被压成一行（`Set-Content`/`WriteAllLines` 都救不回）。修法：这些行改用 `-f` 格式化（`('# boot attempt {0} ({1})' -f $stamp, $Image),`），并用 `[System.IO.File]::WriteAllLines(..., UTF8Encoding($true))` 显式写 BOM+CRLF。此前 3 次「计划模式」证据文件（`20261122T011007Z/011026Z/025031Z-*`）都是压成一行，已删掉重生成（`20261122T025215Z-shim-v4.md`）。


## 2026-11-22（续 4）D0 首次执行失败：ABL fastboot 栈被并发轮询写坏（设备已 wedge，待电源键）

### 目标 / 做法 / 验收
- 目标：判 U1 —— `fastboot boot` 跳进 shim 后，ABL 建的 fastboot gadget 是否还在总线上。
- 做法：设备在 Android（`78ad6b26 device`）→ `adb reboot bootloader` → 后台起 `usb_watch.py --duration 150` → 4 s 后 `boot-attempt.ps1 -Image shim-v4 -Confirm`。
- 验收：观测器中 `18D1` 设备持续在场且 `getvar` 超时 = 路径 A；设备消失 = 路径 B。

### 结果：失败，两次都是 121
- 第一次（观测器并发）：`Sending 'boot.img' (84 KB) FAILED (AdbWriteEndpointSync failed: 信号灯超时时间已到 (121))`，`.fastboot.log` 0 字节。
- kill 观测器后单独重跑（无并发）：**同样 121** → 设备侧已经 wedge，不是「并发抢带宽」这类瞬态。
- wedge 判定：`getvar product` 5.003 s 后 121；`reboot-bootloader` 121；但 `fastboot devices` 仍列出 `78ad6b26 fastboot`（本地枚举 ≠ 设备侧应答）。无残留 fastboot/python 进程。
- 恢复：**只能长按电源键 ~15 s**。设备当前停在 wedge 的 bootloader，未回 Android。

### 根因与修正
- 根因：旧 `usb_watch.py` 每 1 s 跑 `fastboot devices` + `getvar product`，与 `fastboot boot` 的 bulk 写共用 ABL 的同一个 fastboot 栈；ABL 的 EP 被写挂后**不自愈**。
- 修正 1：`usb_watch.py` 新增 **`--pnp-only`**（默认推荐）：完全不走 fastboot 协议，只读 `Win32_PnPEntity`，按 `VID_18D1` 在场判 U1；docstring 顶部写明并发会让 ABL 报 121 的警告。
- 修正 2：**PID 不是 4EE0**。senna bootloader 枚举为 `USB\VID_18D1&PID_D00D`（FriendlyName `Android Bootloader Interface`），回到 Android 是 `18D1:4EE8`（MTP）。`Get-PnpDevice -Class USB` 看不到它（类不属 USB），旧的 `pnp_snapshot()` 因此一直返回空 → 改用 `Get-CimInstance Win32_PnPEntity` + `DeviceID -match 'VID_18D1|VID_05C6'`。
- 修正 3：`boot-attempt.ps1` 计划段第 4 条与下一步提示改为「`usb_watch.py --pnp-only`，绝不并发 fastboot 轮询」，并加黄色警告；**改 .ps1 后 BOM 丢失（编辑工具按 UTF-8 无 BOM 重写）→ 已用 `WriteAllText + UTF8Encoding($true)` 补回 BOM**（首字节 `EF BB BF` 已验证）。
- 冒烟：`--pnp-only --duration 3` → `fastboot_gadget=True` 2/2 → `VERDICT A`（此刻设备正是 wedge 的 bootloader，说明 PnP 判在场是可靠的）。

### 证据文件
- `build-chain/evidence/boot-attempts/20261122T051802Z-shim-v4.md` + `.fastboot.log`(0 B) + `.fastboot.err`(157 B)：并发那次。
- `build-chain/evidence/boot-attempts/20261122T051827Z-shim-v4.md` + `.fastboot.log`(0 B) + `.fastboot.err`：单独重跑那次。
- 两份 md 的「结果」段已按上面结论回填（不再留「待填」）。

### 关键参数表（本轮新增）

| 项 | 值 | 出处 |
| --- | --- | --- |
| bootloader USB ID | `USB\VID_18D1&PID_D00D`，`Android Bootloader Interface` | `Get-CimInstance Win32_PnPEntity`（2026-11-22 实测） |
| Android(MTP) USB ID | `VID_18D1&PID_4EE8` | 同上 |
| 失败码 | `AdbWriteEndpointSync failed` = WinUSB 写超时（127/121） | fastboot 报错原文 |
| 恢复方式 | 长按电源键 ~15 s | 本轮实测（`reboot-bootloader` 失败） |

### 未完成
- U1 仍未判：设备 wedge，需用户电源键重启回 Android 后重跑 D0。
- 重跑口径：先 `python build-chain/tools/usb_watch.py --pnp-only --duration 150 --out build-chain/evidence/boot-attempts/d0-usb-watch.csv`（只读 PnP），**等它真的开始采样后**再 `powershell -NoProfile -ExecutionPolicy Bypass -File build-chain/tools/boot-attempt.ps1 -Image shim-v4 -Confirm`；引导期间不跑任何 fastboot 命令。
