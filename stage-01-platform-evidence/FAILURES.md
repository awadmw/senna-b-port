# 阶段 1：失败与修正记录

| 项目 | 原始失败/现象 | 修正与影响 |
|---|---|---|
| DTBO 魔数 | `ValueError: bad DTBO magic`；首写常量为 `0x1EABB7D7` | 改为正确 `0xD7B7AB1E`。失败发生在提取前，没有修改输入镜像 |
| DTBO 64 位 offset | 按标准大端 u64 解释得到越界值 | 对本机原始字节按 low-u32-be、high-u32-be 组合；16 项均通过文件边界、FDT 魔数和 totalsize 验证后才采用 |
| DTBO custom | 首读 4 个 u32，越到下一表项的 size | entry_size=32，custom 应为 3 个 u32；已修正并重生成 JSON，DTB 二进制不受影响 |
| vendor_boot DTB | 初期 dtb_size 误读为 0 | 结构偏移错误，不是“无 DTB”；按 v4 头部、页对齐和三个 FDT 总长重新定位，最终 `0x15e650` 精确吻合 |
| 机型筛选 | 多个 overlay 都含 senna/面板字符串，关键字命中会误选 | 改为逐条根 model，并与实时合并 FDT、项目号、当前面板和触控交叉验证，选定 entry 11 |
| 后台任务 | `Select an available model before sending a message` | code_agent 未能启动，无后台任务；文件分析在当前会话完成 |
| 原始文件下载 | ios-sweet workflow 和 tweaks 的 raw 下载出现 `Recv failure: Connection was reset` | 改用 GitHub contents API，成功后保存 API JSON、解码源码及 blob SHA；失败不是源码缺失 |
| AOSP 头文件重取 | `curl: (28) Failed to connect to android.googlesource.com port 443 after 21043 ms: Could not connect to server` | 未保存本地副本，报告明确标注；镜像布局由本机字段和长度独立验证 |
| 本地工具 | 无可用 Git、WSL/dtc | 使用本地 Python FDT parser；保留原始 DTB，文本只作可读证据，不宣称 dtc 编译通过 |

所有错误均发生在电脑侧分析过程；未对设备发出命令，未写入任何设备分区。