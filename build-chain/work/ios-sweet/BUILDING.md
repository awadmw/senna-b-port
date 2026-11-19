# xnu-8796 构建说明：SWEET 基线与 SENNA 编译目标

## 目标与边界

本仓库使用 GitHub Actions macOS runner 和固定版本的
[`blacktop/darwin-xnu-build`](https://github.com/blacktop/darwin-xnu-build)
构建 `macOS_VERSION=13.5` 对应的 xnu-8796。

- `SWEET`：保留 ios-sweet 上游全部 XNU 补丁的 SM7150 编译基线。
- `SENNA`：RMX3706 / SM8475 的**独立编译目标**，生成自己的
  `MASTER.arm64.senna` 和 `kernelcache.senna`。
- `SENNA` 暂时设置 `XNU_BOARD_CONFIG=SWEET`，即继承 SWEET 的板级实现来打通
  编译、链接和 `kmutil create`。它是 compile-only alias，**不是可在 senna
  上启动的内核，也不代表 SM8475 的 GIC、timer、UFS 或 display 已适配**。
- 本阶段不下载、不挂载、不修改 iOS rootfs，不连接或启动实机。

## 固定输入

| 输入 | 值 |
|---|---|
| ios-sweet 上游基线 | `45263bee51df4a0f55cdf9c649af886399488ddb` |
| darwin-xnu-build | `663906528d1cd5ea8fde7de6f16de73db9511549` |
| XNU 版本 | macOS 13.5 / xnu-8796 |
| 默认内核配置 | `DEVELOPMENT` |
| 当前 CI runner | `macos-15`（Arm64） |
| runner 默认 Xcode | `16.0`，由 workflow 输出实际 `DEVELOPER_DIR` |

上游 workflow 的 `macos-14` 已不能创建 GitHub-hosted runner，因此 runner
迁移是必要修改。当前 runner 没有 Xcode 15；Xcode 16 的 IORPC ABI 风险通过
实际构建日志验证，不能根据上游注释预先宣称兼容或不兼容。

## senna 目录

`xnu/senna/` 只包含：

1. `0001-empty.patch`：只有两行注释、没有 diff 的空补丁。workflow 拒绝其中任何非注释内容，也不会把它交给
   `git apply`。GitHub 网页不接受空文件，因此用注释表达“无补丁内容”。
2. `platform.sm8475.conf`：声明 `MACHINE_CONFIG=SENNA`、`SOC=SM8475`、
   `BASE_MACHINE_CONFIG=SWEET`、`XNU_BOARD_CONFIG=SWEET` 和
   `RUNTIME_SUPPORT=not-implemented`。

应用上游补丁后，workflow 在 XNU 源码树中生成：

- `config/MASTER.arm64.senna`（由 SWEET MASTER 复制）；
- `SUPPORTED_ARM64_MACHINE_CONFIGS` 中的 `SENNA`；
- `MACHINE_FLAGS_ARM64_SENNA`，复用 `ARM64_BOARD_CONFIG_SWEET`，并显式加入
  `SENNA=1`；
- 与 SWEET 相同的 plain arm64 选择，避免误切到 arm64e。

这些生成动作只解决构建系统目标选择，不写入任何未经证实的 senna 硬件地址。

## 在 GitHub Actions 构建

1. 打开仓库 **Actions → xnu → Run workflow**。
2. 保持 `macos_version=13.5`、`kernel_config=DEVELOPMENT`。
3. 基线构建设置 `machine_config=SWEET`；senna 构建设置
   `machine_config=SENNA`。
4. 首次排错保持 `keep_going=true`，让 make 汇总更多错误；需要遇错即停时设为
   `false`。

workflow 固定 checkout `DXB_SHA`，应用 `xnu/patches/`，随后执行
`bash build.sh -k`。`-k` 设置 DXB 的 `BUILDKC=1`，不能省略。`Build` 步骤成功必须包含 XNU 编译和
`kmutil create`，单独 checkout 或复制配置不算成功。

ios-sweet 的实际启动链由 `tools/mkpayload.py` 处理 plain-arm64 raw kernel，明确不依赖
kmutil/iBoot。本阶段按任务要求另行生成 **kernel-only kernelcache**：使用 `-a arm64 -x`
且不传任何 `-b` kext，避免把 KDK 中 arm64e-only 扩展混入 plain-arm64 内核。这个 KC
用于构建链验收，**不是 ios-sweet 的可启动 payload，也不表示已经具备 senna 驱动**。

macOS 15.8.2 (24H232) 的 kmutil 会检查宿主匹配 KDK。workflow 因此从固定的
KdkSupportPkg `24H232` release 安装宿主 KDK，同时仍用 KDK 13.5 作为目标 KDK；
二者用途不同，不能互相替代。

## 产物与验收

成功运行上传：

- `xnu-kernelcache-SWEET/kernelcache.sweet`
- `xnu-kernelcache-SENNA/kernelcache.senna`
- 对应 `kernel.development.*`、`build-metadata.json` 和 `SHA256SUMS`
- `xnu-buildtree-<MACHINE>/buildtree.tgz`（排错用，保留 7 天）

`Verify and collect kernelcache` 会检查以下文件非空，缺失即让 job 失败：

```text
dxb/fakeroot/oss-xnu.macOS.13.5.kc.sweet
dxb/fakeroot/oss-xnu.macOS.13.5.kc.senna
```

下载 artifact 后可本地核对：

```bash
cat build-metadata.json
shasum -a 256 -c SHA256SUMS
file kernelcache.senna   # 或 kernelcache.sweet
```

`build-metadata.json` 记录 machine config、SoC、runtime 状态、源代码 commit、
DXB commit 和实际 Xcode 路径。SENNA 的 `runtime_support` 必须为
`not-implemented`。

## 验收记录

| 项目 | 结果 |
|---|---|
| 原始 workflow / run 1 | 未进入编译：GitHub 不支持 `macos-14-arm64-us-default` |
| SWEET / run 2 / macOS 15 | 原始内核编译通过；未传 DXB `-k`，没有 kernelcache |
| SWEET / run 5–7 | XNU 编译通过；kmutil 报宿主 KDK 24H232 缺失（Code 34） |
| SWEET / run 8 | 宿主 KDK 已安装；无 `-x` 扫描 KDK 导致 AppleRTC/IOACPIFamily 依赖失败（Code 71） |
| SWEET / run 9 | arm64 KC 无法接收 arm64e-only AppleUSBTDM（Code 31） |
| SWEET / run 10 | arm64e KC 无法接收 plain-arm64 kernel（Code 31） |
| SWEET / run 11 | kernel-only arm64 KC，等待最终结果 |
| SENNA / macOS 15 | 等待 SWEET 基线通过后运行 |

最终通过标准是 SWEET 与 SENNA 两个 GitHub Actions job 都为绿色，且各自 artifact
含非空 kernelcache、`kmutil inspect` UUID 和匹配元数据。编译成功不等于实机启动成功。
