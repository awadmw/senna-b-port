#!/usr/bin/env python3
import hashlib, json, struct
from pathlib import Path

STAGE = Path(__file__).resolve().parent
STAGE0 = STAGE.parent / "stage-00-evidence"
checks = []
def check(name, ok, detail):
    checks.append({"name": name, "pass": bool(ok), "detail": detail})
def sha256(path):
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()

expected0 = {}
for line in (STAGE0 / "SHA256SUMS.txt").read_text().splitlines():
    digest, name = line.split("  ", 1)
    expected0[name] = digest.upper()
for name in ["boot_b.img", "dtbo_b.img", "vendor_boot_b.img", "vbmeta_b.img", "senna-b-live-base.dtb"]:
    actual = sha256(STAGE0 / name)
    check("stage0 hash: " + name, actual == expected0[name], actual)

fdt_files = [STAGE / f"dtbo-entry-{i:02d}.dtb" for i in range(16)]
fdt_files += [STAGE / f"vendor-boot-{i:02d}.dtb" for i in range(3)]
fdt_files += [STAGE / "live-base-copy.dtb"]
for path in fdt_files:
    data = path.read_bytes()
    valid = len(data) >= 8 and data[:4] == bytes.fromhex("D00DFEED") and struct.unpack(">I", data[4:8])[0] == len(data)
    check("FDT magic/totalsize: " + path.name, valid, f"size={len(data)}")
check("FDT inventory count", len(fdt_files) == 20 and all(p.is_file() for p in fdt_files), "16 DTBO + 3 vendor base + 1 live")

selected = STAGE / "dtbo-entry-11.dtb"
selected_sha = sha256(selected)
check("senna-b entry 11 hash", selected_sha == "D3169C92C8D9FC4DC49C94F18778A81391DE2CAF1AA9D9AE5BB0BBE4504F04CD", selected_sha)
selected_text = (STAGE / "dtbo-entry-11.dtb.dts.txt").read_text(encoding="utf-8")
check("senna-b root model", "Qualcomm Technologies, Inc. Cape MTP, Senna B" in selected_text, "entry 11")
live_text = (STAGE / "live-base-copy.dtb.dts.txt").read_text(encoding="utf-8")
check("live root model agrees", "Qualcomm Technologies, Inc. Cape MTP, Senna B" in live_text, "live merged FDT")
check("live DTB copy hash", sha256(STAGE / "live-base-copy.dtb") == expected0["senna-b-live-base.dtb"], expected0["senna-b-live-base.dtb"])

hardware = json.loads((STAGE / "hardware-evidence.json").read_text(encoding="utf-8"))
nodes = {n["path"]: n for n in hardware["nodes"]}
mem = nodes["/memory"]["properties"]["reg"]["decoded"]
check("memory range count", len(mem) == 5, f"ranges={len(mem)}")
check("memory total", sum(x["size"] for x in mem) == 12655263744, str(sum(x["size"] for x in mem)))
for path in ["/soc/psci", "/soc/interrupt-controller@17100000", "/soc/timer@17420000", "/soc/qcom,qup_uart@99c000", "/soc/ufshc@1d84000", "/soc/qcom,mdss_mdp@ae00000", "/reserved-memory/splash_region"]:
    check("hardware node: " + path, path in nodes, path)

expected_repos = {
    "dipa-studio__ios-sweet": "45263bee51df4a0f55cdf9c649af886399488ddb",
    "UniXNU__UniXNU": "519d80242a5028ee123447b01bc3b809baed565f",
    "edk2-porting__edk2-msm": "e1952621f419f8db60ed28271264e1b5184c571d",
    "blacktop__darwin-xnu-build": "663906528d1cd5ea8fde7de6f16de73db9511549",
}
repo_dir = STAGE / "repository-evidence"
for slug, expected in expected_repos.items():
    commit = json.loads((repo_dir / (slug + "-commit.json")).read_text(encoding="utf-8"))
    tree = json.loads((repo_dir / (slug + "-tree.json")).read_text(encoding="utf-8"))
    check("repository commit: " + slug, commit["sha"] == expected, commit["sha"])
    check("repository complete tree: " + slug, tree.get("truncated") is False, f"entries={len(tree.get('tree', []))}")
workflow = (repo_dir / "dipa-studio__ios-sweet-source-.github__workflows__xnu.yml").read_text(encoding="utf-8")
check("ios-sweet pins darwin-xnu-build", "DXB_SHA: " + expected_repos["blacktop__darwin-xnu-build"] in workflow, expected_repos["blacktop__darwin-xnu-build"])
license_text = (repo_dir / "UniXNU__UniXNU-source-LICENSE").read_text(encoding="utf-8")
check("UniXNU actual license", "BSD-2-Clause-Patent" in license_text, "BSD-2-Clause-Patent")
for name in ["STAGE1-REPORT.md", "repository-audit.md", "FAILURES.md", "image-headers.json", "hardware-evidence.json"]:
    check("required artifact: " + name, (STAGE / name).is_file(), name)

result = {"stage": 1, "scope": "host-side evidence only; not a boot/UEFI/XNU functionality test", "overall_pass": all(c["pass"] for c in checks), "checks_passed": sum(c["pass"] for c in checks), "checks_total": len(checks), "checks": checks}
(STAGE / "validation-results.json").write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(json.dumps({k: result[k] for k in ["overall_pass", "checks_passed", "checks_total"]}, ensure_ascii=False))
if not result["overall_pass"]:
    for c in checks:
        if not c["pass"]:
            print("FAIL", c)
    raise SystemExit(1)