# 官方 OTA 分区抽取证据（RMX3706_13.1.0.115_CN01）

记录时间：2026-11-20。目的：给 REMAINING.md B.6 与阶段 2 的 DTBO / vendor_boot / boot 来源提供**官方全量包**交叉核对，减少对只读采集的间接推断的依赖。

## 来源

| 项 | 值 |
| --- | --- |
| 文件 | `C:\\Users\\hjfdw\\Documents\\deepseek-harness\\default-workspace\\downloads\\RMX3706_13.1.0.115_CN01_rollback_4.0.zip` |
| 大小 | 7,585,057,674 字节 |
| 内容 | `payload.bin` 7,585,052,078 + `payload_properties.txt` 369 + `META-INF/…` |
| payload 类型 | Payload Version 2，full payload（`no source images required`），45 个分区 |
| 抽取工具 | `payload-dumper-go` 2.1.0（windows/amd64，`downloads/payload-dumper-go.exe`，8,496,640 字节） |
| 抽取命令 | `payload-dumper-go -p dtbo,vendor_boot,uefi,boot -o build-chain/ota-evidence <zip>` |

注意：payload-dumper-go 每次抽取都会因进度条写 stderr 触发 PowerShell `NativeCommandError` 并以 1 退出，但产物完整、哈希可验证；判读以文件哈希为准，不以退出码为准。

## 交叉核对结果

| 分区 | 大小（字节） | OTA 抽取 SHA-256 | 实机备份 SHA-256 | 结论 |
| --- | --- | --- | --- | --- |
| dtbo | 25,165,824 | 4F80DE98FAF3BD9881A252AE4FE3C17C151D45AB27FDB0E4AF9CFD43C03C2169 | 4F80DE98FAF3BD9881A252AE4FE3C17C151D45AB27FDB0E4AF9CFD43C03C2169（stage-00 `dtbo_b.img`） | **一致** |
| vendor_boot | 201,326,592 | 4AAB629EEB33DCFFFD6448FBFD5C2A8AA93B7EB13953C94063DC34392DF1B6CB | 4AAB629EEB33DCFFFD6448FBFD5C2A8AA93B7EB13953C94063DC34392DF1B6CB（stage-00 `vendor_boot_b.img`） | **一致** |
| boot | 201,326,592 | D9162A96950A0FD683395968359136EA925B32381D42582BB15DB95341617ED7 | 5B470B39DB25382558D41E764C94DBC1DDCA225CAFF56A148F4B8CEDEFE33A61（stage-00 `boot_b.img`） | **不一致**，见下 |
| uefi | 3,153,920 | F4CD52E174902A71BDFFA9FB7462CAABB87AA9000B7B731CA57513393C9518C2 | 无实机备份 | 新增参考（ABL 用的 UEFI/QA 镜像，阶段 3 只作对照，不刷写） |

### boot 不一致的判读

- 两者大小相同（201,326,592）、header magic 均为 `ANDROID!`（41 4e 44 52 4f 49 44 21），第一个不同字节在偏移 12。
- `boot_b.img` 在偏移 47,679,313 处出现 `MAGISK`，并在 47,673,873 处出现 `androidboot`；同偏移在 OTA `boot.img` 中无对应字符串。
- 结论：实机 `boot_b` 是 **Magisk 打过补丁的 boot 镜像**（设备已解锁、root），与官方包不同，属于预期；本项目**不使用** `boot_b` 作为任何来源证据，也不依赖它。`dtbo` 与 `vendor_boot` 逐字节等于官方包，说明 DTBO（含 senna-b overlay entry 11）与 vendor_boot base DTB 的来源仍然成立。

## 复算

```powershell
Get-ChildItem build-chain/ota-evidence/*.img | Get-FileHash -Algorithm SHA256
```

哈希清单见同目录 `SHA256SUMS.txt`。镜像二进制已被 `.gitignore` 的 `*.img` 规则排除，不入库。
