import os,sys,json,hashlib,re
from pathlib import Path
root=Path(os.environ['PORT_ROOT']); inv=root/'device-inventory'
sys.path.insert(0,str(root/'stage-01-platform-evidence'))
from android_fdt_tool import FDT,as_strings
checks=[]
def check(name,cond,detail=''): checks.append({'name':name,'pass':bool(cond),'detail':str(detail)})
def sha(p): return hashlib.sha256(p.read_bytes()).hexdigest().upper()
raw=(inv/'senna-live.dtb').read_bytes(); f=FDT(raw); facts=json.loads((inv/'inventory-facts.json').read_text(encoding='utf-8')); core=json.loads((inv/'core-hardware.json').read_text(encoding='utf-8')); doc=(root/'DEVICE.md').read_text(encoding='utf-8')
check('DTB magic and exact length',raw[:4]==bytes.fromhex('d00dfeed') and len(raw)==1118143,len(raw))
check('DTB hash matches structured facts',sha(inv/'senna-live.dtb')==facts['live_sha256']==core['source_sha256'],facts['live_sha256'])
check('DT model',as_strings(f.root.props['model'])==['Qualcomm Technologies, Inc. Cape MTP, Senna B'])
ext=json.loads((inv/'device-tree-extraction.json').read_text(encoding='utf-8'))
check('complete device-tree archive extraction',ext['complete'] and ext['archive_members']==35696 and ext['files']==31221 and ext['directories']==4475 and not ext['errors'])
check('DTS generated', (inv/'senna-live.dts').stat().st_size>1000000 and '/dts-v1/;' in (inv/'senna-live.dts').read_text(encoding='utf-8')[:1000])
parts=[l.split('\t') for l in (inv/'partitions.tsv').read_text(encoding='utf-8').splitlines() if l.strip()]
check('132 unique positive partitions',len(parts)==132 and len({p[0] for p in parts})==132 and all(int(p[2])>0 for p in parts))
check('every partition appears in DEVICE',all(f'`{p[0]}`' in doc and str(p[2]) in doc for p in parts))
check('55 reserved entries',len(facts['reserved_memory'])==55)
check('every reserved node appears in DEVICE',all(f'`{r["path"].split("/",1)[1]}`' in doc for r in facts['reserved_memory']))
expected={'qcom,pmk8350@0':0,'qcom,pm8350@1':1,'qcom,pm8350c@2':2,'qcom,pm8350b@3':3,'qcom,pmr735a@4':4,'qcom,pmr735b@5':5,'qcom,pm8450@7':7,'qcom,pm8010i@8':8,'qcom,pm8010j@9':9}
actual={k:v['value'][0] for k,v in facts['spmi']['/soc/qcom,spmi@c42d000']['devices'].items() if not k.startswith('qcom,pm8010@')}
check('PMIC USIDs',actual==expected,actual)
check('touch SPI0 CS0 evidence','SPI0，chip-select 0' in doc and '/soc/spi@990000/synaptics_tcm@0' in doc)
check('five selected panel timings',len([p for p in facts['panel_timings'] if '/timing@' in p])==5)
check('panel selection',facts['active_panel_path'].endswith('qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd'))
uf=(inv/'ufs-descriptors.txt').read_text(encoding='utf-8')
for name,value in [('manufacturer_id','0x012C'),('device_version','0x0011'),('specification_version','0x0310'),('unipro_version','0x0180'),('mphy_version','0x0410')]: check('UFS '+name,re.search(r'### .*/'+name+r'\n'+re.escape(value)+r'\r?$',uf,re.M) is not None,value)
check('UFS SCSI product','MICRON' in (inv/'ufs-scsi-identity.txt').read_text(encoding='utf-8') and 'MT256GAXAT4U31' in (inv/'ufs-scsi-identity.txt').read_text(encoding='utf-8'))
check('QCA6490 Wi-Fi and BT','/soc/qcom,cnss-qca6490@b0000000' in facts['wireless'] and '/soc/bt_qca6490' in facts['wireless'])
check('GICD/GICR raw decode',core['gic']['reg']==[[386924544,65536],[387448832,2097152]],core['gic']['reg'])
check('ITS raw decode',core['its']['reg']==[[387186688,131072]] and core['its']['path'].endswith('msi-controller@17140000'))
check('old GICR typo removed','0x171c0000' not in doc and '0x171c0000' not in (root/'stage-01-platform-evidence/STAGE1-REPORT.md').read_text(encoding='utf-8') and '0x171c0000' not in (root/'PROGRESS.md').read_text(encoding='utf-8'))
check('UniXNU limitation explicit','没有 SM8475/cape/taro/senna/RMX3706 设备路径' in doc)
check('rootfs modifier forbidden','sweet-root-tweaks.py' in doc and '明确禁用' in doc)
check('read-only collection scripts',all(x in (inv/'collect-device.sh').read_text(encoding='utf-8') for x in ['blockdev --getsize64','cat /proc/cmdline','dmesg']))
result={'overall_pass':all(c['pass'] for c in checks),'passed':sum(c['pass'] for c in checks),'total':len(checks),'checks':checks}
(inv/'validation-results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False,indent=2))
for c in checks:
 if not c['pass']: print('FAIL',c)
if not result['overall_pass']: raise SystemExit(1)
