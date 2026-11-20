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
- B.1 dtc round-trip：脚本与 workflow 已就绪（`device-inventory/verify-dts-roundtrip.sh`、`.github/workflows/verify-dts.yml`），需 release `dtb-evidence-v1` 提供原始 DTB 后在 Actions 实跑；本地无 dtc，未在本机执行。
- iOS 16.7.16 (20H392) rootfs 仍未获取/未做哈希登记；EDL 演练仍未做。

