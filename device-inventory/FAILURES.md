# 采集与整理失败/修正记录

- 初次用 Python `tarfile` 普通路径展开 `/proc/device-tree` 时，在超长面板属性路径 `qcom,mdss-dsi-timing-switch-command-state` 处触发 `FileNotFoundError`。改用 Windows `\\?\` 扩展路径并拒绝非普通文件/不安全路径后，35,696 个成员全部处理，31,221 文件、4,475 目录，零错误。
- 初次 reserved-memory 解析把平坦 u64 序列错误地按两个值解包，出现 `TypeError: cannot unpack non-iterable int object`；改为遍历原始序列的相邻 `(address,size)` 对后成功。
- 初次 UFS 补采命令使用 PowerShell 不支持的 `<` 输入重定向，出现 `ParserError: RedirectionNotSupported`，脚本未执行；随后改用 .NET Process 标准输入。另一次使用了不存在的 workspace 内 adb 路径，实际工具由 `Get-Command adb.exe` 定位为 `C:\Android\platform-tools\adb.exe`，随后补采退出码 0、stderr 0。
- 阶段1人工摘要把 GICR 写成 `0x171c0000`；当前和阶段0原始 DT 的 `/soc/interrupt-controller@17100000/reg` 均为 `17100000000100001718000000200000`，即 GICD `0x17100000+0x10000`、GICR `0x17180000+0x200000`。已更正 STAGE1-REPORT.md 与 PROGRESS.md，DEVICE.md 直接由当前 DT 再解码生成。
- 本次 dmesg 只剩约 189 秒以后，早期启动信息已被后续 Wi-Fi 日志覆盖；未将缺失启动日志当作硬件证据。
- 标准 dtc 未安装；`senna-live.dts` 来自已用于阶段1的本地 FDT 解析器，未宣称完成 dtc round-trip。