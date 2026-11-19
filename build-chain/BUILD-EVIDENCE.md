# 构建链证据：SWEET kernelcache（GitHub Actions）

记录时间：2026-11-19。全部证据来自 GitHub Actions 运行产物与本地校验，**未连接实机、未刷写、未修改 rootfs**。

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

## 4. SENNA 目标（编译别名，进行中）

SENNA 目标定义在 `xnu/senna/platform.sm8475.conf`：MACHINE_CONFIG=SENNA、SOC=SM8475、BASE_MACHINE_CONFIG=SWEET、XNU_BOARD_CONFIG=SWEET、RUNTIME_SUPPORT=not-implemented；`xnu/senna/0001-empty.patch` 为纯注释空补丁。它**只是编译别名**，不代表 SM8475 已适配。

失败与修复序列（均为真实日志）：

1. run 44483651048：`fatal error: 'sweet_bearssl/src/symcipher/aes_ct_enc.c' file not found`、`'sweet_libpthread/kern/kern_init.c' file not found`、`'hfs.h' file not found`。根因：`xnu/patches/0019-stage-libpthread.sh`、`0020-stage-bearssl.sh`、`0026-stage-hfs.sh` 首行都是 `[[ "${MACHINE_CONFIG:-}" == SWEET ]] || exit 0`，SENNA 下直接跳过暂存。修复：提交 3c466f3，将判断改为 `case "${MACHINE_CONFIG:-}" in SWEET|SENNA) ;; *) … exit 0 ;; esac`。
2. run 44485081625：bearssl/libpthread 已暂存，但 HFS 报 `cp_fs_protected`、`VTOCMP`、`AppleKeyStore/AppleKeyStoreFSServices.h`、`hfs.h` 未声明/找不到。根因：`bsd/conf/Makefile.template` 里 `ifeq ($(CURRENT_MACHINE_CONFIG),SWEET)` 把 `-include sweet_hfs_compat.h -I$(SWEET_HFS_ROOT)` 等开关限制在 SWEET，SENNA 编 HFS 时按内核视图编译。修复：提交 19fb11b，在 prepare-senna.sh 中把该守卫放宽为 `ifneq ($(filter $(CURRENT_MACHINE_CONFIG),SWEET SENNA),)`。
3. 当前：run 44486857317（head 19fb11b）进行中；结果以实际日志为准，未完成前不宣称 SENNA 通过。

## 5. 复现命令

```bash
gh workflow run xnu.yml -R awadmw/ios-sweet -f machine_config=SWEET -f kernel_config=DEVELOPMENT
gh workflow run xnu.yml -R awadmw/ios-sweet -f machine_config=SENNA -f kernel_config=DEVELOPMENT
gh run download <run-id> -R awadmw/ios-sweet -n xnu-kernelcache-SWEET
```