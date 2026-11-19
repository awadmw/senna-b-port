import os,sys,json,re,struct,hashlib
from pathlib import Path
root=Path(os.environ['PORT_ROOT']); inv=root/'device-inventory'
sys.path.insert(0,str(root/'stage-01-platform-evidence'))
from android_fdt_tool import FDT, as_strings
raw=(inv/'senna-live.dtb').read_bytes(); fdt=FDT(raw); nodes={n.path:n for n in fdt.root.walk()}
facts=json.loads((inv/'inventory-facts.json').read_text(encoding='utf-8'))
def u32(b): return list(struct.unpack('>'+str(len(b)//4)+'I',b)) if b and len(b)%4==0 else []
def strings(b): return as_strings(b) or []
def one(v,default='—'):
    if isinstance(v,list): return v[0] if v else default
    return v if v is not None else default
def hx(v): return f'0x{v:x}'
def regpairs(path,ac=1,sc=1):
    b=nodes[path].props.get('reg',b''); v=u32(b); out=[]; step=ac+sc
    for i in range(0,len(v),step):
        a=0;s=0
        for x in v[i:i+ac]: a=(a<<32)|x
        for x in v[i+ac:i+step]: s=(s<<32)|x
        out.append((a,s))
    return out
def rtext(ranges): return '<br>'.join(f'`0x{a:016x} + 0x{s:x}`' for a,s in ranges)
def digest(path): return hashlib.sha256(path.read_bytes()).hexdigest().upper()
# Current-DT core evidence, independent of the old hand-written summary.
core={'source_sha256':digest(inv/'senna-live.dtb'),'model':strings(nodes['/'].props['model']),'compatible':strings(nodes['/'].props['compatible']),'msm_id':u32(nodes['/'].props['qcom,msm-id']),'board_id':u32(nodes['/'].props['qcom,board-id']),'memory':regpairs('/memory',2,2)}
for key,path in [('gic','/soc/interrupt-controller@17100000'),('pdc','/soc/interrupt-controller@b220000'),('timer','/soc/timer@17420000'),('uart','/soc/qcom,qup_uart@99c000'),('ufs','/soc/ufshc@1d84000'),('mdp','/soc/qcom,mdss_mdp@ae00000')]:
    n=nodes[path]; core[key]={'path':path,'compatible':strings(n.props.get('compatible',b'')),'reg':regpairs(path),'reg_names':strings(n.props.get('reg-names',b'')),'interrupts':u32(n.props.get('interrupts',b'')),'clock_frequency':one(u32(n.props.get('clock-frequency',b'')),None)}
its=next(n for n in nodes.values() if 'arm,gic-v3-its' in strings(n.props.get('compatible',b'')))
core['its']={'path':its.path,'reg':regpairs(its.path)}
core['timer_frames']={n.path:{'reg':regpairs(n.path),'interrupts':u32(n.props.get('interrupts',b'')),'status':strings(n.props.get('status',b''))} for n in nodes.values() if n.path.startswith('/soc/timer@17420000/frame@')}
core['cpu_paths']=[p for p in nodes if re.fullmatch(r'/cpus/cpu@[0-9a-f]+',p)]
core['psci']={k:strings(nodes['/soc/psci'].props.get(k,b'')) for k in ['compatible','method']}
(inv/'core-hardware.json').write_text(json.dumps(core,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Properties and descriptors.
props={}
for line in (inv/'getprop.txt').read_text(encoding='utf-8',errors='replace').splitlines():
    m=re.match(r'^\[([^]]+)\]: \[(.*)\]$',line)
    if m: props[m.group(1)]=m.group(2)
ufs_text=(inv/'ufs-descriptors.txt').read_text(encoding='utf-8',errors='replace')
desc={}
for m in re.finditer(r'^### .*/(device_descriptor|interconnect_descriptor)/([^\n]+)\n([^\n]*)',ufs_text,re.M): desc[m.group(2)]=m.group(3).strip()
scsi=(inv/'ufs-scsi-identity.txt').read_text(encoding='utf-8',errors='replace')
def scsi_value(k):
    m=re.search(r'^'+re.escape(k)+r'=(.*)$',scsi,re.M); return m.group(1).strip() if m else '—'
parts=[]
for line in (inv/'partitions.tsv').read_text(encoding='utf-8').splitlines():
    if not line.strip(): continue
    name,dev,size,link=line.split('\t'); parts.append((name,dev,int(size),link))
parts.sort(key=lambda x:x[0])
# Panel helpers.
def pv(key): return facts['panel_properties'].get(key,{}).get('value','—')
def tv(node,key): return facts['panel_timings'].get(node,{}).get(key,{}).get('value','—')
timing_rows=[]
for path in sorted(facts['panel_timings']):
    if '/timing@' not in path: continue
    name=path.rsplit('/',1)[1].replace('timing@','')
    timing_rows.append((name,one(tv(path,'qcom,mdss-dsi-panel-framerate')),one(tv(path,'qcom,mdss-dsi-panel-width')),one(tv(path,'qcom,mdss-dsi-panel-height')),one(tv(path,'qcom,mdss-dsi-panel-clockrate')),one(tv(path,'qcom,mdss-dsi-h-front-porch')),one(tv(path,'qcom,mdss-dsi-h-back-porch')),one(tv(path,'qcom,mdss-dsi-h-pulse-width')),one(tv(path,'qcom,mdss-dsi-v-front-porch')),one(tv(path,'qcom,mdss-dsi-v-back-porch')),one(tv(path,'qcom,mdss-dsi-v-pulse-width')),one(tv(path,'qcom,mdss-dsc-bit-per-component')),one(tv(path,'qcom,mdss-dsc-bit-per-pixel')),one(tv(path,'qcom,mdss-dsc-slice-width')),one(tv(path,'qcom,mdss-dsc-slice-height')),one(tv(path,'qcom,mdss-mdp-transfer-time-us'))))
L=[]
a=L.append
a('# senna 移植参数表（DEVICE.md）')
a('')
a('> 状态：移植前只读信息采集完成；本文不包含移植代码，也不代表已具备可启动的 UEFI/XNU。')
a('> 采集设备：ADB `78ad6b26`；全程未重启、未解锁、未清数据、未刷写、未在手机创建或修改文件。')
a('')
a('## 1. 证据范围与结论边界')
a('')
a(f'- 当前合并 DTB：[`device-inventory/senna-live.dtb`](<device-inventory/senna-live.dtb>)，{len(raw)} 字节，SHA-256 `{core["source_sha256"]}`。')
a(f'- 完整 `/proc/device-tree`：[`device-inventory/device-tree.tar`](<device-inventory/device-tree.tar>)，35,696 个 tar 成员；已完整展开 31,221 个文件和 4,475 个目录，零错误，见 [`device-tree-extraction.json`](<device-inventory/device-tree-extraction.json>)。')
a('- DTS 文本：[`device-inventory/senna-live.dts`](<device-inventory/senna-live.dts>)。由本地 FDT 解析器生成，尚未用 `dtc` 二次编译验证。')
a('- 本机已有实时 DT，因此本次没有从官方 OTA `payload.bin` 重复提取；匹配全量 OTA 仍未提供。')
a('- 当前 DT 与阶段0 DT 只有 `/hypervisor` 下动态 resource-manager-rpc 节点一增一删，硬件属性无差异；见 [`dt-generation-diff.json`](<device-inventory/dt-generation-diff.json>)。')
a('- `dmesg` 环形缓冲只保留约 189 秒以后，早期启动日志已被 Wi-Fi 日志冲刷；硬件结论以 DT、sysfs 和尚存日志交叉确认，不拿缺失日志补猜。')
a('')
a('## 2. 准确型号、系统与启动状态')
a('')
a('| 项目 | 实测值 | 来源 |')
a('|---|---|---|')
identity=[('销售型号','ro.product.model'),('Android 设备代号','ro.product.device'),('产品名','ro.product.name'),('品牌','ro.product.brand'),('制造商','ro.product.manufacturer'),('主板属性','ro.product.board'),('硬件属性','ro.product.hardware'),('Android 版本','ro.build.version.release'),('SDK','ro.build.version.sdk'),('系统显示版本','ro.build.display.id'),('OTA 版本','ro.build.version.ota'),('安全补丁','ro.build.version.security_patch'),('当前槽位','ro.boot.slot_suffix'),('AVB 设备状态','ro.boot.vbmeta.device_state'),('verifiedbootstate','ro.boot.verifiedbootstate'),('flash.locked','ro.boot.flash.locked')]
for label,key in identity: a(f'| {label} | `{props.get(key,"（空）")}` | `getprop {key}` |')
a('| DT 整机标识 | `Qualcomm Technologies, Inc. Cape MTP, Senna B` | 当前 DT `/model` |')
a('| 项目号 | `22624` | 当前 `/chosen/bootargs` 的 `oplusboot.prjname` |')
a(f'| Build fingerprint | `{props.get("ro.build.fingerprint","—")}` | `getprop ro.build.fingerprint` |')
a('')
a('**命名规则：** `RMX3706` 是销售型号，`RE5860` 是 Android `ro.product.device`，`senna-b` 是 DT/启动参数对应的平台代号；三者不能互相替换。`unlocked/orange/flash.locked=0` 是当前 Android 侧证据；阶段0 的部分 fastboot getvar 不受 bootloader 支持，不能补写成 fastboot 已返回这些值。')
a('')
a('## 3. SoC、内存与核心控制器')
a('')
a(f'- `qcom,msm-id`：`{core["msm_id"]}`；`qcom,board-id`：`{core["board_id"]}`。')
a(f'- CPU：{len(core["cpu_paths"])} 个节点；`enable-method=psci`。PSCI：`{core["psci"]}`。')
a(f'- 内存五段合计 `{sum(s for _,s in core["memory"]):,}` 字节；可用内存必须继续扣除后文 55 项 reserved-memory。')
a('')
a('| 项目 | 当前 DT 参数 |')
a('|---|---|')
a(f'| `/memory` | {rtext(core["memory"])} |')
a(f'| GICv3 | `{core["gic"]["path"]}`；GICD `0x{core["gic"]["reg"][0][0]:x}+0x{core["gic"]["reg"][0][1]:x}`；GICR `0x{core["gic"]["reg"][1][0]:x}+0x{core["gic"]["reg"][1][1]:x}`；`#interrupt-cells=3` |')
a(f'| GIC ITS | `{core["its"]["path"]}`；{rtext(core["its"]["reg"])} |')
a(f'| PDC | `{core["pdc"]["path"]}`；{rtext(core["pdc"]["reg"])}；names={core["pdc"]["reg_names"]} |')
a(f'| MMIO timer | `{core["timer"]["path"]}`；`clock-frequency={core["timer"]["clock_frequency"]}` Hz；该值不能直接当作 arch timer 的 CNTFRQ |')
a(f'| UART console | `{core["uart"]["path"]}`；{rtext(core["uart"]["reg"])}；`interrupts={core["uart"]["interrupts"]}`；`console=ttyMSM0,115200n8` |')
a('')
a('## 4. PMIC 与 SPMI')
a('')
spmi_path='/soc/qcom,spmi@c42d000'; spmi=facts['spmi'][spmi_path]; regs=spmi['properties']['reg']['value']; names=spmi['properties']['reg-names']['value']
a(f'主控制器 `{spmi_path}`，`compatible=qcom,spmi-pmic-arb`，`#address-cells=2`、`#size-cells=0`。第二控制器 `/soc/qcom,spmi@c432000` 在当前合并 DT 中没有直接设备节点。')
a('')
a('| SPMI 寄存器名 | 地址 + 大小 |')
a('|---|---|')
for i,name in enumerate(names): a(f'| `{name}` | `0x{regs[i*2]:08x} + 0x{regs[i*2+1]:x}` |')
a('')
a('| DT 节点 | USID（reg 第一 cell） | reg 原始值 |')
a('|---|---:|---|')
for name,p in spmi['devices'].items():
    if name.startswith('qcom,pm8010@'): continue
    a(f'| `{name}` | `{p["value"][0]}` | `{p["value"]}` |')
a('')
a('确认到的 PMIC 名称为 **PMK8350、PM8350、PM8350C、PM8350B、PMR735A、PMR735B、PM8450、PM8010I、PM8010J**。这些名称来自 DT 节点，不替代芯片丝印。`qcom,pm8010@8/@9` 与同 USID 的 `pm8010i/j` 是重复兼容节点，不能计作额外两颗 PMIC。')
a('')
a('## 5. 触摸控制器')
a('')
a('| 项目 | 实测值 |')
a('|---|---|')
a('| 控制器 | `synaptics-s3910` |')
a('| DT 节点 | `/soc/spi@990000/synaptics_tcm@0` |')
a('| 总线与地址 | **SPI0，chip-select 0**；`reg=<0>`；不是 I2C 地址 |')
a('| 父控制器 | `qcom,spi-geni`，MMIO `0x00990000 + 0x4000` |')
a('| 状态 | `okay` |')
a('| input sysfs | `/devices/platform/soc/990000.spi/spi_master/spi0/spi0.0/input/input5` |')
a('')
a('## 6. 屏幕面板与 DSI')
a('')
a(f'唯一采用启动参数选中的节点：`{facts["active_panel_path"]}`。DT 中其他候选面板没有混入本表。')
a('')
a('| 项目 | 当前选中面板参数 |')
a('|---|---|')
for label,key in [('面板名称','qcom,mdss-dsi-panel-name'),('厂商标识','oplus,mdss-dsi-vendor-name'),('制造标识','oplus,mdss-dsi-manufacture'),('模式','qcom,mdss-dsi-panel-type'),('流量模式','qcom,mdss-dsi-traffic-mode'),('lane map','qcom,mdss-dsi-lane-map'),('颜色顺序','qcom,mdss-dsi-color-order')]: a(f'| {label} | `{one(pv(key))}` |')
a(f'| DSI / PHY / VC / stream | `ctrl={one(pv("qcom,dsi-ctrl-num"))}` / `phy={one(pv("qcom,dsi-phy-num"))}` / `VC={one(pv("qcom,mdss-dsi-virtual-channel-id"))}` / `stream={one(pv("qcom,mdss-dsi-stream"))}` |')
a(f'| DSI bpp | `{one(pv("qcom,mdss-dsi-bpp"))}`；不要与 DSC 的 8 bpp 混淆 |')
a(f'| 物理尺寸 | `{one(pv("qcom,mdss-pan-physical-width-dimension"))} × {one(pv("qcom,mdss-pan-physical-height-dimension"))}` mm |')
a('| MDP | `/soc/qcom,mdss_mdp@ae00000`：`0x0ae00000+0x84000`、`0x0ae80000+0x2008`、`0x0ae7f800+0x800`，SPI 83 |')
a('')
a('五组 DT timing（clock 单位 Hz，transfer 单位 µs）：')
a('')
a('| timing | fps | 宽 | 高 | clock | HFP | HBP | HPW | VFP | VBP | VPW | DSC bpc | DSC bpp | slice W | slice H | transfer |')
a('|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|')
for row in timing_rows: a('| '+' | '.join(str(x) for x in row)+' |')
a('')
a('公共 DSC 参数：`dsc-version=0x11`、`scr-version=1`、`slice-per-pkt=2`、`encoders=2`、`lm-split=[620,620]`、`display-topology=[1,1,1,2,2,1]`。五组 timing 是支持集合，**当前实际刷新率和实时 DSI 链路状态本次未确定**。完整 81 个面板属性及所有命令字节哈希见 [`inventory-facts.json`](<device-inventory/inventory-facts.json>)。')
a('')
a('## 7. UFS')
a('')
a('| 项目 | 实测值 | 来源 |')
a('|---|---|---|')
a(f'| 控制器 | `/soc/ufshc@1d84000`；{rtext(core["ufs"]["reg"])}；names={core["ufs"]["reg_names"]}；SPI 265 | 当前 DT |')
a(f'| SCSI 厂商 | `{scsi_value("vendor")}` | 所有已列 LUN 的 sysfs `vendor` |')
a(f'| 产品型号 | `{scsi_value("model")}` | sysfs `model` / 产品字符串 |')
a(f'| 产品/固件 revision | `{scsi_value("rev")}` | sysfs `rev`；不是 UFS 规范版本 |')
a(f'| manufacturer_id | `{desc.get("manufacturer_id")}` | UFS device descriptor |')
a(f'| device_version | `{desc.get("device_version")}` | UFS device descriptor，保留原始值 |')
a(f'| UFS 规范版本 | `{desc.get("specification_version")}` → **UFS 3.1** | device descriptor BCD |')
a(f'| UniPro / M-PHY | `{desc.get("unipro_version")}` / `{desc.get("mphy_version")}` → **1.8 / 4.1** | interconnect descriptor BCD |')
a(f'| LUN / queue depth | `{desc.get("number_of_luns")}` / `{desc.get("queue_depth")}` | device descriptor |')
a('')
a('原始描述符输出见 [`ufs-descriptors.txt`](<device-inventory/ufs-descriptors.txt>)。没有从 `MT256GAXAT4U31` 的字符串反推未读出的容量、制程或功耗参数。')
a('')
a('## 8. Wi-Fi 与蓝牙')
a('')
a('| 功能 | 本机证据 | 结论 |')
a('|---|---|---|')
a('| Wi-Fi | DT `/soc/qcom,cnss-qca6490@b0000000`：`compatible=qcom,cnss-qca6490`；PCI `0000:01:00.0` vendor/device=`0x17cb:0x1103`，subsystem=`0x17cb:0x0108`，class=`0x028000` | Wi-Fi 功能为 **QCA6490**；PCI ID 不用于反推另一型号 |')
a('| 蓝牙 | DT `/soc/bt_qca6490`：`compatible=qcom,qca6490`；现有驱动日志也含 qca6490 | 蓝牙功能为 **QCA6490** |')
a('')
a('`qcom,cnss-qca6490@b0000000` 的 `reg=0xb0000000+0x10000` 名为 `smmu_iova_ipa`，**不是 PCI MMIO 地址**。本报告不据此断言芯片封装数量或未采集的固件版本。')
a('')
a('## 9. reserved-memory 全量布局')
a('')
a('共 55 项。地址均保留 64 位形式；无 `reg` 的节点列出其 `size/alignment/alloc-ranges`，不得把动态分配池猜成固定地址。')
a('')
a('| 节点 | compatible / label | reg 地址 + 大小 | size / alignment / alloc-ranges | 标志 |')
a('|---|---|---|---|---|')
for r in facts['reserved_memory']:
    name=r['path'].split('/',1)[1]; cl=[] 
    if r['compatible']: cl.append('/'.join(r['compatible']))
    if r['label']: cl.append('label='+r['label'])
    ranges='<br>'.join(f'`0x{x["address"]:016x}+0x{x["size"]:x}`' for x in r.get('ranges',[])) or '—'
    extra=[]
    for k in ['size','alignment','alloc-ranges']:
        if k in r: extra.append(f'`{k}={[hex(v) for v in r[k]]}`')
    flags=', '.join(x for x,k in [('no-map','no_map'),('reusable','reusable')] if r[k]) or '—'
    a(f'| `{name}` | {"; ".join(cl) or "—"} | {ranges} | {"<br>".join(extra) or "—"} | {flags} |')
a('')
a('## 10. 全量 by-name 分区表')
a('')
a(f'共 {len(parts)} 个唯一名称；大小由 root 下 `blockdev --getsize64` 读取，失败时才用 sysfs sectors×512。未读取或修改分区内容。')
a('')
a('| 分区名 | 块设备 | 大小（字节） | 大小（MiB） | by-name 路径 |')
a('|---|---|---:|---:|---|')
for name,dev,size,link in parts: a(f'| `{name}` | `{dev}` | {size} | {size/1048576:.3f} | `{link}` |')
a('')
a('## 11. 对照 ios-sweet 与 UniXNU 的复用分类')
a('')
a('参考固定版本：ios-sweet `45263bee51df4a0f55cdf9c649af886399488ddb`（SM7150/sweet）；UniXNU `519d80242a5028ee123447b01bc3b809baed565f`。')
a('')
a('**先纠正对照前提：上述 UniXNU main commit 没有 SM8475/cape/taro/senna/RMX3706 设备路径，因此不存在可诚实列出的“UniXNU 的 SM8475 机型参数”。若指其他分支或 fork，必须另给 commit 后再审计。**')
a('')
a('### 11.1 可直接复用（仅通用方法/框架，仍须构建与实机验证）')
a('')
a('- ios-sweet 的 xnu-8796 构建链方法：darwin-xnu-build 固定 `663906528d1cd5ea8fde7de6f16de73db9511549`、macOS 13.5、Xcode 15/iig、`DEVELOPMENT` 配置。可复用的是工具链固定方法，不是 sweet 整机镜像。')
a('- 架构通用算法/协议实现可作为候选：ARM64 PSCI 调用框架、GICv3 驱动框架、UFS/SCSI 协议层、FDT 解析与启动参数传递。SoC glue、地址、时钟、复位、PHY 不在此类。')
a('- UniXNU 的通用移植文档、代码组织方式和 BSD-2-Clause-Patent 许可文本可参考；没有可据该 commit 直接复用的 SM8475 机型参数。')
a('- **不可复用：** `tools/sweet-root-tweaks.py` 会修改 rootfs，违反本项目“用户空间一字节不改”，明确禁用。')
a('')
a('### 11.2 需改地址/本机参数')
a('')
a('| 子系统 | 不能照搬的内容 | senna-b 必须使用的证据 |')
a('|---|---|---|')
a('| 内存 | sweet/其他机型的 DRAM base、大小、保留区 | 本文 5 段 `/memory` 与 55 项 reserved-memory |')
a('| GICv3/ITS/PDC | 所有 MMIO、redistributor、IRQ 配置 | GICD `0x17100000`、GICR `0x17180000`、ITS `0x17140000`；以当前 DT 原始 reg 为准 |')
a('| Timer/UART | MMIO frame、IRQ、console base | timer `0x17420000`；UART `0x0099c000`、SPI 608 |')
a('| UFS | HC/ICE/HWKM、IRQ、PHY/clock/reset/interconnect | `0x01d84000/0x01d88000/0x01d90000`、SPI 265；描述符仅识别设备，不替代初始化代码 |')
a('| SPMI/PMIC | arbiter 五组寄存器、USID、regulator/clock 资源 | `0x0c42d000` 总线及本机 PMIC 表 |')
a('| 显示 | MDP/DSI/PHY、DSC、timing、reset/TE/backlight | 当前 NT37705 节点与五组 timing |')
a('| 触控 | I2C 地址和 sweet 触控流程 | 本机是 SPI0 CS0 的 Synaptics S3910 |')
a('| Wi-Fi/BT | sweet 的 WLAN/BT 平台 glue | QCA6490、PCI `17cb:1103`、CNSS/MHI/IOMMU 本机节点 |')
a('')
a('### 11.3 需新写或新适配')
a('')
a('- senna-b 专用 UEFI DSC/FDF、MemoryMap、DeviceConfigurationMap、启动 shim 设备配置；当前没有现成 senna-b 设备包。')
a('- SM8475/senna-b 的时钟、复位、pinctrl、regulator、互连和 PMIC 初始化序列；不能只改一个 base address。')
a('- UFS host glue 与 PHY 初始化，并单独决定 ICE/HWKM 支持策略；描述符读取成功不代表 XNU 可读写 UFS。')
a('- NT37705 的 DSI command-mode + DSC 初始化、命令包、动态刷新、背光/TE/reset，以及 Pixelworks Iris 相关依赖的启用或隔离策略。')
a('- S3910 的 GENI SPI 传输、供电/复位/中断和固件加载流程；不能从 I2C 触控驱动小改得到。')
a('- QCA6490 的 PCIe/CNSS/MHI、固件、IOMMU 与电源管理适配；Wi-Fi/BT 不能视为通用 PCIe 网卡即插即用。')
a('- UniXNU 若后续提供确切 SM8475 分支，仍需逐项重新分类；当前不能预写为已有实现。')
a('')
a('## 12. 未确定项与下一步采集')
a('')
a('- 标准 `dtc -I dtb -O dts` 复核；官方全量 OTA/payload 与哈希；bootloader 实际 base DTB 选择算法。')
a('- 当前活动帧缓冲 base/stride/format、实际刷新率/DSI 链路状态、目标启动环境 CNTFRQ 和 arch-timer IRQ。')
a('- PSCI、UART、 clocks/resets/regulators 在非 Android 环境的可访问性，需要后续受控启动实验，不能由本次只读采集推断。')
a('- 本报告只做信息采集与参数归档，未进入移植实现。')
(root/'DEVICE.md').write_text('\n'.join(L)+'\n',encoding='utf-8')
print('WROTE',root/'DEVICE.md','lines',len(L),'bytes',(root/'DEVICE.md').stat().st_size,'partitions',len(parts),'reserved',len(facts['reserved_memory']),'timings',len(timing_rows))
print('GIC',core['gic']['reg'],'ITS',core['its'])
