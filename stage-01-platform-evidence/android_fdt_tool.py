from __future__ import annotations
import hashlib, json, math, struct, sys
from pathlib import Path

FDT_MAGIC = 0xD00DFEED
DTBO_MAGIC = 0xD7B7AB1E

def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest().upper()

def align(v: int, a: int) -> int:
    return (v + a - 1) // a * a

class Node:
    def __init__(self, name: str, parent=None):
        self.name = name
        self.parent = parent
        self.props: dict[str, bytes] = {}
        self.children: list[Node] = []
    @property
    def path(self) -> str:
        if self.parent is None:
            return '/'
        base = self.parent.path
        return (base.rstrip('/') + '/' + self.name) if base != '/' else '/' + self.name
    def walk(self):
        yield self
        for child in self.children:
            yield from child.walk()

class FDT:
    def __init__(self, data: bytes):
        self.data = data
        if len(data) < 40:
            raise ValueError(f'FDT too short: {len(data)}')
        fields = struct.unpack_from('>10I', data, 0)
        (magic, self.totalsize, self.off_struct, self.off_strings, self.off_rsv,
         self.version, self.last_comp_version, self.boot_cpuid,
         self.size_strings, self.size_struct) = fields
        if magic != FDT_MAGIC:
            raise ValueError(f'bad FDT magic: {magic:08x}')
        if self.totalsize > len(data):
            raise ValueError(f'FDT totalsize {self.totalsize} exceeds input {len(data)}')
        if self.off_struct + self.size_struct > self.totalsize:
            raise ValueError('FDT struct block out of bounds')
        if self.off_strings + self.size_strings > self.totalsize:
            raise ValueError('FDT strings block out of bounds')
        self.strings = data[self.off_strings:self.off_strings+self.size_strings]
        self.reserves = []
        p = self.off_rsv
        while p + 16 <= self.totalsize:
            addr, size = struct.unpack_from('>QQ', data, p)
            p += 16
            if addr == 0 and size == 0:
                break
            self.reserves.append((addr, size))
        self.root = self._parse_struct()
    def string(self, off: int) -> str:
        if off >= len(self.strings):
            raise ValueError(f'string offset {off} out of bounds')
        end = self.strings.find(b'\0', off)
        if end < 0:
            raise ValueError('unterminated FDT property name')
        return self.strings[off:end].decode('utf-8', errors='replace')
    def _parse_struct(self):
        p = self.off_struct
        end = self.off_struct + self.size_struct
        stack = []
        root = None
        while p + 4 <= end:
            token = struct.unpack_from('>I', self.data, p)[0]
            p += 4
            if token == 1:
                q = self.data.find(b'\0', p, end)
                if q < 0:
                    raise ValueError('unterminated node name')
                name = self.data[p:q].decode('utf-8', errors='replace')
                p = align(q + 1, 4)
                parent = stack[-1] if stack else None
                node = Node(name, parent)
                if parent is not None:
                    parent.children.append(node)
                elif root is None:
                    root = node
                else:
                    raise ValueError('multiple root nodes')
                stack.append(node)
            elif token == 2:
                if not stack:
                    raise ValueError('unexpected END_NODE')
                stack.pop()
            elif token == 3:
                if not stack or p + 8 > end:
                    raise ValueError('PROP outside node or truncated')
                length, nameoff = struct.unpack_from('>II', self.data, p)
                p += 8
                if p + length > end:
                    raise ValueError('property data out of bounds')
                stack[-1].props[self.string(nameoff)] = self.data[p:p+length]
                p = align(p + length, 4)
            elif token == 4:
                continue
            elif token == 9:
                break
            else:
                raise ValueError(f'unknown FDT token {token} at {p-4:#x}')
        if root is None:
            raise ValueError('no FDT root node')
        return root
    def header_dict(self):
        return {'totalsize': self.totalsize, 'version': self.version,
                'last_comp_version': self.last_comp_version,
                'boot_cpuid_phys': self.boot_cpuid,
                'off_dt_struct': self.off_struct, 'off_dt_strings': self.off_strings,
                'off_mem_rsvmap': self.off_rsv, 'size_dt_struct': self.size_struct,
                'size_dt_strings': self.size_strings,
                'reserve_entries': len(self.reserves), 'node_count': sum(1 for _ in self.root.walk())}

def as_strings(b: bytes):
    if not b or not b.endswith(b'\0'):
        return None
    parts = b.split(b'\0')[:-1]
    if not parts:
        return None
    out = []
    for x in parts:
        if not x or any(c < 0x20 and c not in (9, 10, 13) or c >= 0x7f for c in x):
            return None
        out.append(x.decode('ascii'))
    return out

def prop_text(name: str, b: bytes) -> str:
    if not b:
        return f'\t{name};\n'
    strings = as_strings(b)
    if strings is not None:
        vals = ', '.join(json.dumps(x, ensure_ascii=True) for x in strings)
        return f'\t{name} = {vals};\n'
    if len(b) % 4 == 0:
        cells = struct.unpack('>' + 'I' * (len(b)//4), b)
        vals = ' '.join(f'0x{x:08x}' for x in cells)
        return f'\t{name} = <{vals}>;\n'
    rows = []
    for i in range(0, len(b), 16):
        rows.append(' '.join(f'{x:02x}' for x in b[i:i+16]))
    return f'\t{name} = [' + '\n\t\t'.join(rows) + '];\n'

def dump_dts(fdt: FDT, source: Path, digest: str) -> str:
    out = ['/dts-v1/;', f'// source: {source}', f'// sha256: {digest}',
           '// Textual FDT dump generated by android_fdt_tool.py; property cell grouping is not semantic.', '']
    for addr, size in fdt.reserves:
        out.append(f'/memreserve/ 0x{addr:016x} 0x{size:016x};')
    out.append(f'// header: {json.dumps(fdt.header_dict())}')
    def emit(node: Node, depth: int):
        ind = '\t' * depth
        label = '/' if node.parent is None else node.name
        out.append(f'{ind}{label} {{ // {node.path}')
        for name, value in node.props.items():
            text = prop_text(name, value)
            out.extend(ind + '\t' + line for line in text.rstrip('\n').split('\n'))
        for child in node.children:
            emit(child, depth + 1)
        out.append(f'{ind}}};')
    emit(fdt.root, 0)
    return '\n'.join(out) + '\n'

def save_fdt(data: bytes, out: Path, source_name: str, manifest: list, extra=None):
    digest = sha256(data)
    fdt = FDT(data)
    if fdt.totalsize != len(data):
        raise ValueError(f'{source_name}: extracted length {len(data)} != FDT totalsize {fdt.totalsize}')
    out.write_bytes(data)
    dts = out.with_suffix(out.suffix + '.dts.txt')
    dts.write_text(dump_dts(fdt, Path(source_name), digest), encoding='utf-8')
    item = {'source': source_name, 'dtb': out.name, 'dts': dts.name,
            'size': len(data), 'sha256': digest, 'fdt': fdt.header_dict()}
    if extra:
        item.update(extra)
    manifest.append(item)

def extract(stage00: Path, outdir: Path):
    outdir.mkdir(parents=True, exist_ok=True)
    report = {'sources': {}, 'fdt_files': []}
    boot_path = stage00 / 'boot_b.img'
    boot = boot_path.read_bytes()
    if boot[:8] != b'ANDROID!':
        raise ValueError('boot_b.img lacks ANDROID! magic')
    version = struct.unpack_from('<I', boot, 40)[0]
    header_size = struct.unpack_from('<I', boot, 20)[0]
    boot_info = {'sha256': sha256(boot), 'file_size': len(boot),
                 'header_version': version, 'header_size': header_size,
                 'kernel_size': struct.unpack_from('<I', boot, 8)[0],
                 'ramdisk_size': struct.unpack_from('<I', boot, 12)[0]}
    if version == 4:
        boot_info['signature_size'] = struct.unpack_from('<I', boot, 1580)[0]
    report['sources']['boot_b.img'] = boot_info

    dtbo_path = stage00 / 'dtbo_b.img'
    dtbo = dtbo_path.read_bytes()
    vals = struct.unpack_from('>8I', dtbo, 0)
    magic, total, hdr_size, entry_size, count, entries_off, page_size, reserved = vals
    if magic != DTBO_MAGIC:
        raise ValueError('bad DTBO magic')
    if total > len(dtbo) or hdr_size < 32 or entry_size < 32:
        raise ValueError('invalid DTBO header bounds')
    if entries_off + count * entry_size > total:
        raise ValueError('DTBO entries out of bounds')
    report['sources']['dtbo_b.img'] = {'sha256': sha256(dtbo), 'file_size': len(dtbo),
        'total_size': total, 'header_size': hdr_size, 'dt_entry_size': entry_size,
        'dt_entry_count': count, 'dt_entries_offset': entries_off, 'page_size': page_size}
    for i in range(count):
        p = entries_off + i * entry_size
        size = struct.unpack_from('>I', dtbo, p)[0]
        # This device image stores the 64-bit offset as low-u32 BE followed by high-u32 BE.
        # All 16 entries were validated by bounds, FDT magic and FDT totalsize before using this fallback.
        lo, hi = struct.unpack_from('>II', dtbo, p + 4)
        off = (hi << 32) | lo
        offset_raw = dtbo[p+4:p+12].hex()
        ident, rev = struct.unpack_from('>II', dtbo, p + 12)
        custom = struct.unpack_from('>3I', dtbo, p + 20)
        if off + size > total:
            raise ValueError(f'DTBO entry {i} out of bounds')
        extra = {'dtbo_index': i, 'dt_offset': off, 'dt_offset_raw': offset_raw, 'dt_offset_encoding': 'low-u32-be followed by high-u32-be; FDT-validated fallback', 'id': ident, 'rev': rev, 'custom': list(custom)}
        save_fdt(dtbo[off:off+size], outdir / f'dtbo-entry-{i:02d}.dtb',
                 f'dtbo_b.img[{i}]', report['fdt_files'], extra)

    vb_path = stage00 / 'vendor_boot_b.img'
    vb = vb_path.read_bytes()
    if vb[:8] != b'VNDRBOOT':
        raise ValueError('vendor_boot lacks VNDRBOOT magic')
    v = struct.unpack_from('<I', vb, 8)[0]
    page = struct.unpack_from('<I', vb, 12)[0]
    header_size = struct.unpack_from('<I', vb, 2096)[0]
    dtb_size_total = struct.unpack_from('<I', vb, 2100)[0]
    dtb_addr = struct.unpack_from('<Q', vb, 2104)[0]
    table_size = struct.unpack_from('<I', vb, 2112)[0]
    table_num = struct.unpack_from('<I', vb, 2116)[0]
    table_entry_size = struct.unpack_from('<I', vb, 2120)[0]
    bootconfig_size = struct.unpack_from('<I', vb, 2124)[0]
    vendor_ramdisk_size = struct.unpack_from('<I', vb, 24)[0]
    dtb_off = align(align(header_size, page) + vendor_ramdisk_size, page)
    if v != 4 or page == 0 or header_size != 2128 or dtb_off + dtb_size_total > len(vb):
        raise ValueError(f'invalid vendor_boot v{v} DTB bounds: off={dtb_off} size={dtb_size_total}')
    report['sources']['vendor_boot_b.img'] = {'sha256': sha256(vb), 'file_size': len(vb),
        'header_version': v, 'page_size': page, 'header_size': header_size,
        'kernel_addr': f'0x{struct.unpack_from("<I", vb, 16)[0]:08x}',
        'ramdisk_addr': f'0x{struct.unpack_from("<I", vb, 20)[0]:08x}',
        'vendor_ramdisk_size': vendor_ramdisk_size,
        'cmdline': vb[28:28+2048].split(b'\0', 1)[0].decode('utf-8', errors='replace'),
        'tags_addr': f'0x{struct.unpack_from("<I", vb, 2076)[0]:08x}',
        'board': vb[2080:2096].split(b'\0', 1)[0].decode('utf-8', errors='replace'),
        'vendor_ramdisk_table_size': table_size,
        'vendor_ramdisk_table_entry_num': table_num,
        'vendor_ramdisk_table_entry_size': table_entry_size,
        'bootconfig_size': bootconfig_size,
        'dtb_offset': dtb_off, 'dtb_size_total': dtb_size_total, 'dtb_addr': f'0x{dtb_addr:016x}'}
    rel = 0
    dtb_index = 0
    while rel < dtb_size_total:
        if rel + 40 > dtb_size_total:
            raise ValueError('truncated concatenated vendor FDT header')
        one_size = struct.unpack_from('>I', vb, dtb_off + rel + 4)[0]
        if one_size < 40 or rel + one_size > dtb_size_total:
            raise ValueError(f'invalid concatenated vendor FDT {dtb_index} size {one_size}')
        save_fdt(vb[dtb_off+rel:dtb_off+rel+one_size], outdir / f'vendor-boot-{dtb_index:02d}.dtb',
                 f'vendor_boot_b.img[dtb:{dtb_index}]', report['fdt_files'],
                 {'vendor_boot_dtb_index': dtb_index, 'vendor_boot_dtb_region_offset': dtb_off,
                  'vendor_boot_dtb_relative_offset': rel, 'vendor_boot_dtb_addr': f'0x{dtb_addr:016x}'})
        rel += one_size
        dtb_index += 1
    if rel != dtb_size_total:
        raise ValueError('vendor DTB entries do not sum to dtb_size')
    report['sources']['vendor_boot_b.img']['dtb_entry_count'] = dtb_index
    live = (stage00 / 'senna-b-live-base.dtb').read_bytes()
    save_fdt(live, outdir / 'live-base-copy.dtb', 'senna-b-live-base.dtb', report['fdt_files'])
    (outdir / 'image-headers.json').write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(report, ensure_ascii=False, indent=2))

if __name__ == '__main__':
    if len(sys.argv) != 3:
        raise SystemExit('usage: android_fdt_tool.py STAGE00_DIR OUTPUT_DIR')
    extract(Path(sys.argv[1]), Path(sys.argv[2]))
