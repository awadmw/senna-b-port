# 阶段 1：参考仓库固定版本审计

审计日期：2026-11-19。审计只证明下列固定 commit 的源码内容，不把 README 的功能声明当成实机验证结果。API 返回、递归树和关键源码保存在 `repository-evidence/`；后续引用应使用 commit 永久链接，不使用会移动的分支链接。

| 仓库 | 固定 ref / commit | 该版本实际范围 | 对 senna-b 的结论 |
|---|---|---|---|
| `dipa-studio/ios-sweet` | `main` / `45263bee51df4a0f55cdf9c649af886399488ddb` | Redmi Note 10 Pro `sweet` / SM7150；README 描述 xnu-8796、iPhone X iOS 16.7.16 rootfs、fastboot boot shim、PSCI/GICv3/UFS/显示/触控流程 | 只能参考方法。树中无 `sm8475`、`cape`、`taro`、`senna`、`rmx3706` 路径；不得复制其平台常量或修改 rootfs 的流程 |
| `UniXNU/UniXNU` | `main` / `519d80242a5028ee123447b01bc3b809baed565f` | README 列出 `UniXNU-sm8550-common`、`UniXNU-sheng`、`uefi-sheng` 等 | 没有 SM8475/senna-b 支持证据，不能据此宣称可直接启动 |
| `edk2-porting/edk2-msm` | `master` / `e1952621f419f8db60ed28271264e1b5184c571d` | 有 `Platform/Qualcomm/sm8475`、`Silicon/Qualcomm/sm8475`、`configs/sm8475.conf`；唯一 SM8475 设备描述为 `Platform/Xiaomi/sm8475/yudi.dsc` | SoC 代码可供逐项核对，但没有 senna-b 设备包；yudi 与通用示例参数不得直接采用 |
| `blacktop/darwin-xnu-build` | `main` / `663906528d1cd5ea8fde7de6f16de73db9511549` | Darwin XNU 构建脚本与补丁，不含 senna-b 平台支持 | 仅作为构建工具；能否用于本项目仍需独立构建验证 |

## 关键交叉证据

- ios-sweet 的 `.github/workflows/xnu.yml` 明确写 `DXB_SHA: 663906528d1cd5ea8fde7de6f16de73db9511549`，与上表 blacktop commit 一致；默认 `macos_version=13.5`（文件注释为 xnu-8796 / iOS 16 era）、`MACHINE_CONFIG=SWEET`、`KERNEL_CONFIG=DEVELOPMENT`。
- 该工作流使用 `macos-14`，注释说明 Xcode 15.x 的 `iig` 与 xnu-8796 IORPC ABI 匹配，而 Xcode 16 的输出不兼容。这里只记录参考构建条件，本机尚未构建。
- ios-sweet 的 `tools/sweet-root-tweaks.py` 会读写已挂载 rootfs，并修改 `System/Library/xpc/launchd.plist` 等。本项目要求用户空间一字节不改，因此明确禁用该脚本及其等价修改。
- edk2-msm 的 `configs/sm8475.conf` 在该 commit 中写 `FD_BASE=0xCE000000`、`FD_SIZE=0x02000000`，yudi 分辨率是 2880x1800。它们不是 RMX3706 的本机证据，列入隔离清单。
- UniXNU GitHub API 的 license 字段为 `NOASSERTION`，但固定 commit 的 `LICENSE` 与 README 标明 `BSD-2-Clause-Patent`；报告采用实际 LICENSE 文件，不仅依赖 API 分类。
- 各仓库递归树均 `truncated=false`：ios-sweet 149 项、UniXNU 2452 项、edk2-msm 1890 项、darwin-xnu-build 51 项。

## 固定来源

- https://github.com/dipa-studio/ios-sweet/tree/45263bee51df4a0f55cdf9c649af886399488ddb
- https://github.com/UniXNU/UniXNU/tree/519d80242a5028ee123447b01bc3b809baed565f
- https://github.com/edk2-porting/edk2-msm/tree/e1952621f419f8db60ed28271264e1b5184c571d
- https://github.com/blacktop/darwin-xnu-build/tree/663906528d1cd5ea8fde7de6f16de73db9511549
- AOSP Android 13 bootimg 结构参考：https://android.googlesource.com/platform/system/tools/mkbootimg/+/refs/heads/android13-release/include/bootimg/bootimg.h 。最近一次本地下载失败，未保存成本地副本；本机布局另由头部字段、页对齐、三个 FDT 总长精确交叉验证。