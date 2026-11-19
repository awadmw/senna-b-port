from __future__ import annotations
import importlib.util, json, re, struct
from pathlib import Path

STAGE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('android_fdt_tool', STAGE / 'android_fdt_tool.py')
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)
fdt = mod.FDT((STAGE / 'live-base-copy.dtb').read_bytes())

PANEL = 'qcom,mdss_dsi_oplus_senna_bc_nt37705_1240_2772_dsc_cmd'
NODE_PATTERN = re.compile(r'(^/memory|^/reserved-memory$|^/reserved-memory/|^/timer$|/timer@|^/psci$|^/cpus$|^/cpus/|^/chosen$|interrupt-controller@|ufshc|serial@|uart|mdss_mdp@|mdss_dsi[01]@|scm|smem|msm-id|board-id|firmware)', re.I)
COMPAT_PATTERN = re.compile(r'arm,gic|arm,generic-timer|arm,psci|qcom,.*(?:uart|serial|ufshc)|snps,dw-apb-uart', re.I)

def cells(n, name, default):
    while n is not None:
        if name in n.props and len(n.props[name]) == 4:
            return struct.unpack('>I', n.props[name])[0]
        n = n.parent
    return default

def decode_reg(n, raw):
    ac, sc = cells(n.parent, '#address-cells', 2), cells(n.parent, '#size-cells', 2)
    width = ac + sc
    if not width or len(raw) % (width * 4):
        return None
    words = struct.unpack('>' + str(len(raw)//4) + 'I', raw)
    out = []
    for i in range(0, len(words), width):
        out.append({'address': int.from_bytes(b''.join(x.to_bytes(4, 'big') for x in words[i:i+ac]), 'big'),
                    'size': int.from_bytes(b''.join(x.to_bytes(4, 'big') for x in words[i+ac:i+width]), 'big'),
                    'address_cells': ac, 'size_cells': sc})
    return out

def value(n, key, raw):
    item = {'length': len(raw), 'hex': raw.hex()}
    if len(raw) % 4 == 0:
        item['u32_be'] = list(struct.unpack('>' + str(len(raw)//4) + 'I', raw)) if raw else []
    strings = raw.rstrip(b'\0').split(b'\0')
    if strings and all(s and all(32 <= b < 127 for b in s) for s in strings):
        item['strings'] = [s.decode('ascii') for s in strings]
    if key == 'reg':
        item['decoded'] = decode_reg(n, raw)
    return item

def selected(n):
    if NODE_PATTERN.search(n.path):
        return True
    compat = n.props.get('compatible', b'').decode('ascii', errors='ignore')
    if COMPAT_PATTERN.search(compat):
        return True
    if n.name == PANEL or (n.parent is not None and n.parent.name == PANEL):
        return True
    if n.name == 'synaptics_tcm@0' or (n.parent is not None and n.parent.name == 'synaptics_tcm@0'):
        return True
    return False

result = {'source': {'file': 'live-base-copy.dtb', 'original': '../stage-00-evidence/senna-b-live-base.dtb',
                     'sha256': mod.sha256(fdt.data), 'totalsize': fdt.totalsize},
          'root': {k: value(fdt.root, k, v) for k, v in fdt.root.props.items()},
          'nodes': []}
lines = ['SOURCE live-base-copy.dtb', 'SHA256 ' + result['source']['sha256'], '']
for n in fdt.root.walk():
    if not selected(n):
        continue
    entry = {'path': n.path, 'address_cells_inherited': cells(n.parent, '#address-cells', 2),
             'size_cells_inherited': cells(n.parent, '#size-cells', 2),
             'properties': {k: value(n, k, v) for k, v in n.props.items()}}
    result['nodes'].append(entry)
    lines.append('NODE ' + n.path)
    for k, v in n.props.items():
        encoded = value(n, k, v)
        extra = ''
        if 'strings' in encoded:
            extra += ' strings=' + repr(encoded['strings'])
        if key_is_reg := (k == 'reg'):
            extra += ' decoded=' + repr(encoded['decoded'])
        lines.append(f'  {k}: len={len(v)} hex={v.hex()}{extra}')
    lines.append('')
(STAGE / 'hardware-evidence.json').write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding='utf-8')
(STAGE / 'hardware-nodes.txt').write_text('\n'.join(lines), encoding='utf-8')
print('nodes_selected', len(result['nodes']))
print('json_bytes', (STAGE / 'hardware-evidence.json').stat().st_size)
print('text_bytes', (STAGE / 'hardware-nodes.txt').stat().st_size)
for n in result['nodes']:
    if n['path'] == '/' or n['path'].startswith('/memory') or n['path'] in ['/timer', '/psci', '/chosen']:
        print(n['path'], json.dumps(n['properties'], ensure_ascii=False)[:2000])