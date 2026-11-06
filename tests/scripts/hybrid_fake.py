"""Монітор на другій NVIDIA (P106 + GT 710) на фальшивій Windows: OptimaX знаходить P106 за PCI ID у розділах
драйверів, навіть коли DirectX її не бачить; у звіті про драйвер — «для ігор не працює», а не «перевстановіть драйвер»;
пошук ігор призначає їх і попереджає; у розділи драйверів OptimaX нічого не пише.

Запуск: FAKE_TARGET=tests/scripts/hybrid_fake.py python tests/scripts/fake_windows.py --out DIR"""
import json
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import gpudiag as GD  # noqa: E402
import gpuinfo as GI  # noqa: E402
import hardware as H  # noqa: E402
import mining as MG  # noqa: E402
from i18n import tr  # noqa: E402

R = {}
LOG = []
log = LOG.append
hw = H._from_demo("mining")
F.CFG["games"] = []

GT, P106, HD = "0x00000000_0x0000A001", "0x00000000_0x0000B002", "0x00000000_0x0000C003"
NV = GI.NVIDIA


def probe(display="gt710", p106_visible=False) -> dict:
    gt = dict(name="NVIDIA GeForce GT 710", ven=NV, dev=0x128B, sub=0x8C931462, vram_mb=980, luid=GT, software=False,
              outputs=1, dx12=True)
    hd = dict(name="Intel(R) HD Graphics 4000", ven=GI.INTEL, dev=0x0162, vram_mb=32, luid=HD, software=False,
              outputs=1, dx12=False)
    p = dict(name="NVIDIA P106-100", ven=NV, dev=0x1C07, sub=0, vram_mb=6070, luid=P106, software=False, outputs=0,
             dx12=True)
    first = gt if display == "gt710" else hd
    return {"ts": 0, "dxgi": [first, p] if p106_visible else [first], "vulkan": [], "errors": []}


CLS = E.GPU_CLASS
E.reg_set(CLS + r"\0000", "MatchingDeviceId", r"pci\cc_0300", "sz")  # стандартний адаптер Microsoft — без VEN/DEV
E.reg_set(CLS + r"\0000", "DriverDesc", "Microsoft Basic Display Adapter", "sz")
E.reg_set(CLS + r"\0001", "MatchingDeviceId", r"pci\ven_10de&dev_128b&subsys_8c931462", "sz")
E.reg_set(CLS + r"\0001", "DriverDesc", "NVIDIA GeForce GT 710", "sz")
E.reg_set(CLS + r"\0002", "MatchingDeviceId", r"pci\ven_10de&dev_1c07", "sz")
E.reg_set(CLS + r"\0002", "DriverDesc", "NVIDIA P106-100", "sz")
E.reg_set(CLS + r"\Configuration\x", "x", 1, "dword")  # службові підрозділи без номера — не карти


def driver_values() -> dict:
    """Що лежить у розділах драйверів — OptimaX сюди нічого не пише."""
    out = {}
    for sub in ("0000", "0001", "0002"):
        out[sub] = sorted((n, str(v)) for n, v, _t in E.reg_values(CLS + "\\" + sub))
    return out


before = driver_values()
R["keys"] = [(k["sub"], f"{k['ven']:04X}:{k['dev']:04X}", k["desc"]) for k in MG.class_keys()]

# P106 невидима для DirectX (TCC / код 43): знайдено за PCI ID, рядок «для ігор не працює» замість «драйвер»
st = MG.nv_pair_state(probe())
rep = GD.driver_report(hw, probe())
R["hidden"] = {"state": st["state"], "visible": st["visible"], "render": st["render"], "display": st["display"],
               "summary_gpu": GI.summary(probe())["gpu"], "rows": [k for _, k, _ in rep["rows"]]}
R["findings"] = [f.get("key") or f.get("id") for f in GD.driver_findings(hw, probe())]

# P106 видима (раптом) — однаково пара, рядок однаково є
R["visible"] = {"state": MG.nv_pair_state(probe(p106_visible=True))["state"],
                "rows": [k for _, k, _ in GD.driver_report(hw, probe(p106_visible=True))["rows"]]}

# монітор на HD 4000 — звичайний випадок, пари немає
R["igpu"] = {"state": MG.nv_pair_state(probe(display="hd", p106_visible=True))["state"],
             "rows": [k for _, k, _ in GD.driver_report(hw, probe(display="hd", p106_visible=True))["rows"]]}

# пошук ігор: призначає, але попереджає; у розділи драйверів нічого
F.CFG["gpu_probe"] = probe()
res = MG.assign(log, hw, [])
R["assign_nvpair"] = res.get("nvpair", False)
R["log_nvpair"] = tr("mg.nvpair_log", gpu="NVIDIA P106-100", display="NVIDIA GeForce GT 710") in LOG
F.CFG["gpu_probe"] = probe(display="hd", p106_visible=True)
R["assign_igpu"] = MG.assign(log, hw, []).get("nvpair", False)
R["driver_keys_untouched"] = driver_values() == before
R["journal_hybrid"] = E.JOURNAL.has("mining:hybrid")

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "roundtrip.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
