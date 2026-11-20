# 构建链证据：SWEET / SENNA kernelcache（GitHub Actions）

记录时间：2026-11-19（SWEET）、2026-11-20（SENNA 下载校验与官方 OTA 交叉核对）。全部证据来自 GitHub Actions 运行产物与本地校验，**未连接实机、未刷写、未修改 rootfs**。

## 1. SWEET 基线（通过）

| 项 | 值 |
| --- | --- |
| 仓库 | https://github.com/awadmw/ios-sweet （Fork，上游 45263bee51df4a0f55cdf9c649af886399488ddb） |
| 运行 | run 44481202871（push 触发） |
| 提交 | c1c360ddd64f05812b4fdd52ab9defce0bfead5d |
| 运行环境 | macos-15（Xcode 16），固定 DXB 663906528d1cd5ea8fde7de6f16de73db9511549 |
| 结论 | success，全部步骤通过，耗时 8m44s |
| 构建输入 | xnu-8796.141.3（macOS 13.5 / macos-135 release.json），KDK_13.5_22G74 |
| 机器配置 | MACHINE_CONFIG=SWEET（SM7150 参考目标） |

Artifacts：

- `xnu-kernelcache-SWEET` id=14509386243，67,562,895 字节，GitHub digest `sha256:6084969434F242277F2FAACD051D2ADDFC7671402A1AAC7EBD44E76D06BDBF5B`
- `xnu-buildtree-SWEET` id=14509246494，22.1 MB（本地编译用源码树）

## 2. 本地校验

- 下载 `gh run download 44481202871 -n xnu-kernelcache-SWEET` 得到 `build-chain/kc-sweet.zip`，`Get-FileHash -Algorithm SHA256` = `6084969434F242277F2FAACD051D2ADDFC7671402A1AAC7EBD44E76D06BDBF5B`，与 GitHub 记录的 artifact digest **逐字符一致**。
- 解包内容（`build-chain/artifacts/kc-sweet/`）：

| 文件 | 大小（字节） | SHA256 |
| --- | --- | --- |
| kernelcache.sweet | 21,184,512 | D1B13A15B78E54E3CC7E19E54725C633E989D5CCAE007B2B37A3AE669B8B6BC1 |
| kernel.development.sweet | 18,388,744 | DD31242D4DFC0878D299ABD46C9274840A707071BF2886EE225E89C45173735A |

- `kmutil inspect` 输出（kc-inspect.txt）：

```
boot kernel collection at .../oss-xnu.macOS.13.5.kc.sweet.development (08A074F3-DF8A-CCEF-63BE-53FEB9362B67):
com.apple.kernel	0	<unknown>	(628D9966-43C4-3A18-8F89-4FF3F4F4D86B)
Extension Information:
```

即产物是**真实内核集合**（boot KC，含 com.apple.kernel 内核 UUID），不是改名的普通文件。

- build-metadata.json：machine_config=SWEET、soc=SM7150、runtime_support=sweet-reference-only、source_commit=c1c360d…、dxb_commit=66390652…、kernelcache=kernelcache.sweet。

## 3. 边界（必须与结论一起读）

- 该 KC 是 **kernel-only boot kernel collection**（`kmutil create -a arm64 -x`，只含 xnu 内核，不含 KDK kext），**不是可引导的 iOS/SWEET payload**，不能直接 fastboot 启动。
- 机器配置是上游 SWEET（SM7150 参考），与 senna/SM8475 硬件无关；内核仍是 plain arm64，未做任何 senna 硬件适配。
- 上游 ios-sweet 的真实启动链用 `tools/mkpayload.py` 生成 raw kernel payload 而不经 kmutil；本 KC 仅用于证明“独立构建链能产出内核集合”。

## 4. SENNA 目标（通过）

SENNA 目标定义在 `xnu/senna/platform.sm8475.conf`：MACHINE_CONFIG=SENNA、SOC=SM8475、BASE_MACHINE_CONFIG=SWEET、XNU_BOARD_CONFIG=SWEET、RUNTIME_SUPPORT=not-implemented；`xnu/senna/0001-empty.patch` 为纯注释空补丁。它**只是编译别名**，不代表 SM8475 已适配。

失败与修复序列（均为真实日志）：

1. run 44483651048：`fatal error: 'sweet_bearssl/src/symcipher/aes_ct_enc.c' file not found`、`'sweet_libpthread/kern/kern_init.c' file not found`、`'hfs.h' file not found`。根因：`xnu/patches/0019-stage-libpthread.sh`、`0020-stage-bearssl.sh`、`0026-stage-hfs.sh` 首行都是 `[[ "${MACHINE_CONFIG:-}" == SWEET ]] || exit 0`，SENNA 下直接跳过暂存。修复：提交 3c466f3，将判断改为 `case "${MACHINE_CONFIG:-}" in SWEET|SENNA) ;; *) … exit 0 ;; esac`。
2. run 44485081625：bearssl/libpthread 已暂存，但 HFS 报 `cp_fs_protected`、`VTOCMP`、`AppleKeyStore/AppleKeyStoreFSServices.h`、`hfs.h` 未声明/找不到。根因：`bsd/conf/Makefile.template` 里 `ifeq ($(CURRENT_MACHINE_CONFIG),SWEET)` 把 `-include sweet_hfs_compat.h -I$(SWEET_HFS_ROOT)` 等开关限制在 SWEET，SENNA 编 HFS 时按内核视图编译。修复：提交 19fb11b，在 prepare-senna.sh 中把该守卫放宽为 `ifneq ($(filter $(CURRENT_MACHINE_CONFIG),SWEET SENNA),)`。
3. run 44486857317（head 19fb11b）：failure，暴露出 kmutil 步骤缺少失败诊断、`conf/Makefile.template` 守卫只覆盖 prepare 阶段的问题。
4. run 44489106397（head aea14cdc9f45289803caa76c02673a71c64253e3）：**success**，08:37–08:47Z，全部步骤通过。

Artifacts：

- `xnu-kernelcache-SENNA` id=14512706375，67,563,990 字节，GitHub digest `sha256:ae380407d52993b7611310fb424f8468ec50ce7e65792fb408da1cd6b1bda332`
- `xnu-buildtree-SENNA` id=14512860694，23,196,244 字节，digest `sha256:288407ec89c72012794b0fdaf08e04847e7aa529336ec27667298fcc14acb2af`

本地校验（`build-chain/artifacts/kc-senna-artifact/`）：

- 下载：`gh run download` 在本机两次卡死（目标文件长时间 0 字节，约 13 分钟无进展）；改用 `curl -r` 分段并行。观测：单连接约 60 KB/s，SAS URL 约 10 分钟过期，过期后连接挂起到 0 字节；补救方式是重取 302 `Location` 后只补缺失的 byte range，并用脚本按偏移顺序拼接。
- `xnu-kernelcache-SENNA.zip` = 67,563,990 字节，SHA-256 `AE380407D52993B7611310FB424F8468EC50CE7E65792FB408DA1CD6B1BDA332`，与 artifact digest **逐字符一致**。

| 文件 | 大小（字节） | SHA256 |
| --- | --- | --- |
| kernelcache.senna | 21,184,512 | 3F04B42B716A7F1B29B6A2F73192EF3E14E015E761AA346DB4C8D7DE9ED8E294 |
| kernel.development.senna | 18,388,744 | 1BE4BDD1603326F0280C079BC0EC723DDDCE3D53E6FC6AB5B73210092549919C |
| kernel.development.senna.link/kernel.development.senna.a | 137,241,240 | 未单独登记（链接输入，体积大） |

- `kmutil inspect`（kc-inspect.txt）：boot kernel collection `oss-xnu.macOS.13.5.kc.senna.development (BD57BEA7-2F30-1A64-7A68-88AA0EC28235)`，`com.apple.kernel 0 <unknown> (F84769AE-DEF9-3BB1-BAE4-0A9C0F66BC22)`，Extension Information 为空（kernel-only）。
- `build-metadata.json`：machine_config=SENNA、soc=SM8475、runtime_support=not-implemented、source_commit=aea14cdc9f45289803caa76c02673a71c64253e3、dxb_commit=663906528d1cd5ea8fde7de6f16de73db9511549、developer_dir=/Applications/Xcode_16.app/Contents/Developer、kernelcache=kernelcache.senna。
- 与 SWEET 对比：大小完全相同（21,184,512 / 18,388,744），但 SHA-256 不同（SWEET 为 D1B13A15… / DD31242D…）→ SENNA 配置确实改变了产物字节，不是重复打包同一份 KC。
- 原始运行 JSON：`build-chain/evidence/run21-senna-artifacts.json`。

## 5. 官方 OTA 与实机分区交叉核对

目的：把阶段 2 依赖的 DTBO / vendor_boot 来源从“只读采集推断”升级为“与官方全量包逐字节一致”。详细记录见 `build-chain/ota-evidence/README.md`。

来源：本机 `downloads/RMX3706_13.1.0.115_CN01_rollback_4.0.zip`（7,585,057,674 字节；payload.bin 7,585,052,078 字节；Payload Version 2 full payload，`no source images required`，45 个分区），用 `payload-dumper-go` 2.1.0 抽取 `dtbo,vendor_boot,uefi,boot` 到 `build-chain/ota-evidence/`。

| 分区 | OTA 抽取 SHA-256 | 实机备份 SHA-256（stage-00） | 结论 |
| --- | --- | --- | --- |
| dtbo（25,165,824） | 4F80DE98FAF3BD9881A252AE4FE3C17C151D45AB27FDB0E4AF9CFD43C03C2169 | 4F80DE98…（`dtbo_b.img`） | 一致 |
| vendor_boot（201,326,592） | 4AAB629EEB33DCFFFD6448FBFD5C2A8AA93B7EB13953C94063DC34392DF1B6CB | 4AAB629E…（`vendor_boot_b.img`） | 一致 |
| boot（201,326,592） | D9162A96950A0FD683395968359136EA925B32381D42582BB15DB95341617ED7 | 5B470B39…（`boot_b.img`） | 不一致：实机 boot 在偏移 47,679,313 含 `MAGISK`、47,673,873 含 `androidboot`，是 Magisk 补丁镜像；本项目不使用 boot_b |
| uefi（3,153,920） | F4CD52E174902A71BDFFA9FB7462CAABB87AA9000B7B731CA57513393C9518C2 | 无实机备份 | 仅作阶段 3 对照，不刷写 |

结论：senna-b 的 `dtbo`（含 entry 11 overlay）与 `vendor_boot`（base DTB 来源）逐字节等于官方 13.1.0.115 CN01 全量包；设备确为官方系统 + Magisk 补丁 boot。

## 6. DTS 往返一致性（dtc round-trip）

目的：证明仓库里的 `device-inventory/senna-live.dts` 不是手抄/推测文本，而是能由原始 DTB 逐节点还原、再由 dtc 编回语义等价树（REMAINING B.1）。

做法：DTB 被 `.gitignore` 排除，因此原始二进制通过 release asset 提供。GitHub Actions（`ubuntu-24.04`，apt 装 `device-tree-compiler` 1.7.0）执行：

1. `gh release download dtb-evidence-v1 -p senna-live.dtb`（GitHub 计算 digest `sha256:7a290b13563a058464fa01287fa801687b76e55a85a80867dda76aac73743094`，与实机 DTB 一致）
2. `dtc -I dtb -O dts`（原 DTB → dts）→ `dtc -I dts -O dtb`（senna-live.dts → 重建 DTB）→ `dtc -I dtb -O dts`（重建 DTB → dts）
3. 比对两次渲染的 DTS、节点数、属性数

结果（run 44673153305，job roundtrip id=136078641822，`conclusion=success`；证据 `build-chain/evidence/dts-roundtrip/report.txt`）：

| 项目 | 值 |
| --- | --- |
| 输入 DTB | 1,118,143 字节，sha256 `7a290b13…3094` |
| 输入 DTS | 2,716,184 字节，sha256 `1e371ae715092dd5d7030ad6e27910e423842341ce0561169b77ec00d99cb88f` |
| 重建 DTB | 1,116,869 字节，sha256 `0dd5478cb529e76d4c3492b352a87bd8fb86c3d1a9c44db4cfe18a7ddd00f142`（体积差异来自字符串表/对齐，非语义差异） |
| 节点数 | 二进制 4475 = 重建 4475 |
| 属性数 | 二进制 31220 = 重建 31220 |
| DTS diff | 0 行（`dts.diff` 为空文件） |
| 结论 | **PASS — dtc round-trip is identical** |

边界：这只证明 DTS 与 DTB 语义一致，不证明 DTS 里的每个节点在实机可访问（时钟、regulator、PHY 等依赖仍未闭环）。

## 7. 复现命令

```bash
gh workflow run xnu.yml -R awadmw/ios-sweet -f machine_config=SWEET -f kernel_config=DEVELOPMENT
gh workflow run xnu.yml -R awadmw/ios-sweet -f machine_config=SENNA -f kernel_config=DEVELOPMENT
gh run download <run-id> -R awadmw/ios-sweet -n xnu-kernelcache-SENNA   # 本机实测会挂起，见 4 节下载说明
```

```powershell
# 分段下载（SAS URL 约 10 分钟过期，过期后重取 302 Location 只补缺失区间）
$tok = gh auth token
$h = curl.exe -s -o NUL -D - -H "Authorization: token $tok" https://api.github.com/repos/awadmw/ios-sweet/actions/artifacts/14512706375/zip
$url = (($h | Select-String '^location:').ToString() -replace '^location:\s*','').Trim()
curl.exe -sS --retry 8 -r <start>-<end> -o partNN.bin $url
```