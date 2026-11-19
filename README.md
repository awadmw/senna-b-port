# senna-b-port — RMX3706 (SM8475) 的 XNU / iOS 移植证据库

本仓库记录把 **xnu-8796** 与 **iPhone X / iOS 16.7.16 (20H392) 原版 rootfs** 移植到
**真我 GT Neo5 RMX3706（senna-b，SM8475）** 的过程证据。当前处于“平台证据 + 构建链”阶段，
**未刷写任何分区，未连接实机跑移植镜像，未修改 iOS 用户空间**。**

## 目录

| 路径 | 内容 |
|---|---|
| `DEVICE.md` | senna 移植参数表：型号/DT/分区/PMIC/触控/面板/UFS/Wi-Fi-BT/reserved-memory |
| `RETROSPECTIVE.md` | 阶段 0 → 构建链 run12 的完整复盘（含每次失败的精确原因） |
| `REMAINING.md` | 剩余工作清单（构建链收尾、证据补证、引导链、内核适配） |
| `PROGRESS.md` | 跨阶段续接记录 |
| `stage-00-evidence/` | 设备/固件/分区/槽位/锁状态证据与哈希 |
| `stage-01-platform-evidence/` | DTBO/vendor_boot 解析工具、DTB 选择、硬件证据、参考仓库审计、验收结果 |
| `device-inventory/` | 只读采集脚本与结果（132 分区、55 保留区、UFS 描述符等） |
| `build-chain/` | GitHub Actions 工作流、运行记录、失败证据、构建说明 |

## 关键事实

- senna-b 对应 **`dtbo-entry-11.dtb`**（`Cape MTP, Senna B`，SHA256 `D3169C92C8D9FC4DC49C94F18778A81391DE2CAF1AA9D9AE5BB0BBE4504F04CD`）。
- 内存 5 段合计 12655263744 字节；GICD `0x17100000+0x10000`、GICR `0x17180000+0x200000`。
- 串口 `0x0099c000`（SPI 608，`115200n8`）；UFS `0x01d84000`（SPI 265）。
- 面板 NT37705 1240×2772 DSC；触控 `synaptics-s3910` 在 SPI0 CS0；PMIC 系列与 USID 见 `DEVICE.md`。
- 构建链固定在 ios-sweet `45263bee…` + darwin-xnu-build `66390652…`，XNU 版本 macOS 13.5 = `xnu-8796.141.3`。

## 复现

- 采集：`device-inventory/collect-device.sh`、`collect-ufs.sh`（只读）。
- 镜像解析：`stage-01-platform-evidence/android_fdt_tool.py <STAGE00> <OUT>`。
- 验收：`stage-01-platform-evidence/validate_stage1.py`、`device-inventory/validate-inventory.py`。
- 构建：见 `build-chain/work/ios-sweet/BUILDING.md`（GitHub Actions，`macos-15`）。

## 边界与免责

本仓库**不包含**任何厂商专有镜像、rootfs 内容或密钥；不含 `*.img`、`*.dtb`、`*.tar` 等大体积二进制
（见 `.gitignore` 与 `UPLOAD-MANIFEST.json`）。所有硬件参数仅对 RMX3706 / SM8475 有效，
不得套用到其它机型。当前产物**不可在真机启动**。
