"""Монітор на другій NVIDIA (P106 + GT 710) на фальшивій Windows: OptimaX сама ставить EnableMsHybrid у розділи
драйверів обох карт (1 — майнінговій, 2 — карті з монітором), лише коли Windows віддає «Високу продуктивність» карті з
монітором; повторний запуск нічого не пише; стан «перезавантажте» / «перевірено» / «не допомогло» — за тим, що каже
DXGI; ручні значення користувача OptimaX не чіпає й не повертає; без прав адміністратора нічого не пише; «Повернути
все» прибирає лише свої значення, і OptimaX-Rescue.cmd уміє їх прибрати.

Запуск: FAKE_TARGET=tests/scripts/hybrid_fake.py python tests/scripts/fake_windows.py --out DIR"""
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "tests"))
import engine as E  # noqa: E402
import features as F  # noqa: E402
import gpudiag as GD  # noqa: E402
import gpuinfo as GI  # noqa: E402
import hardware as H  # noqa: E402
import mining as MG  # noqa: E402
import rescue as RS  # noqa: E402
from i18n import tr  # noqa: E402

R = {}
LOG = []
log = LOG.append
hw = H._from_demo("mining")
F.CFG["games"] = []

GT, P106, HD = "0x00000000_0x0000A001", "0x00000000_0x0000B002", "0x00000000_0x0000C003"
NV = GI.NVIDIA


def probe(high: str, ts: float = None, display="gt710") -> dict:
    gt = dict(name="NVIDIA GeForce GT 710", ven=NV, dev=0x128B, sub=0x8C931462, vram_mb=980, luid=GT, software=False,
              outputs=1, dx12=True)
    hd = dict(name="Intel(R) HD Graphics 4000", ven=GI.INTEL, dev=0x0162, vram_mb=32, luid=HD, software=False,
              outputs=1, dx12=False)
    # P106 без виходів; DXGI на гібридному ПК «позичає» їй виходи карти з монітором — display_adapter це враховує
    p = dict(name="NVIDIA P106-100", ven=NV, dev=0x1C07, sub=0, vram_mb=6070, luid=P106, software=False, outputs=1,
             dx12=True)
    first = gt if display == "gt710" else hd
    return {"ts": int(ts or time.time()), "dxgi": [first, p], "vulkan": [], "errors": [],
            "pref": {"high": high, "low": first["luid"]} if high else {}}


def hidden() -> dict:
    """До EnableMsHybrid драйвер NVIDIA не дає P106 DirectX: DXGI бачить лише GT 710 (так і в «Графіці» Windows)."""
    pr = probe(GT)
    pr["dxgi"] = pr["dxgi"][:1]
    return pr


CLS = E.GPU_CLASS
E.reg_set(CLS + r"\0000", "MatchingDeviceId", r"pci\cc_0300", "sz")  # стандартний адаптер Microsoft — без VEN/DEV
E.reg_set(CLS + r"\0000", "DriverDesc", "Microsoft Basic Display Adapter", "sz")
E.reg_set(CLS + r"\0001", "MatchingDeviceId", r"pci\ven_10de&dev_128b&subsys_8c931462", "sz")
E.reg_set(CLS + r"\0001", "DriverDesc", "NVIDIA GeForce GT 710", "sz")
E.reg_set(CLS + r"\0002", "MatchingDeviceId", r"pci\ven_10de&dev_1c07", "sz")
E.reg_set(CLS + r"\0002", "DriverDesc", "NVIDIA P106-100", "sz")
E.reg_set(CLS + r"\Configuration\x", "x", 1, "dword")  # службові підрозділи без номера — не карти


def val(sub: str):
    v = E.reg_get(CLS + "\\" + sub, MG.HYBRID_VALUE)
    return v[1] if v else None


def vals() -> dict:
    return {"gt710": val("0001"), "p106": val("0002"), "basic": val("0000")}


R["keys"] = [(k["sub"], f"{k['ven']:04X}:{k['dev']:04X}", k["desc"]) for k in MG.class_keys()]
# монітор на HD 4000 — налаштовувати нічого (Windows сама вважає вбудовану енергоощадною)
R["igpu"] = MG.hybrid_state(probe(HD, display="hd"))["state"]
R["igpu_tweak"] = len(MG.hybrid_tweak(probe(HD, display="hd")).ops)

# P106 невидима для DirectX: OptimaX знаходить її за PCI ID у розділах драйверів і не плутає з GT 710
st = MG.hybrid_state(hidden())
R["hidden"] = {"state": st["state"], "visible": st["visible"], "render": st["render"],
               "ops": len(MG.hybrid_tweak(hidden()).ops), "summary_gpu": GI.summary(hidden())["gpu"],
               "rows": [k for _, k, _ in GD.driver_report(hw, hidden())["rows"]]}

# Windows віддає «Високу продуктивність» GT 710: OptimaX ставить значення сама, коли шукає ігри
F.CFG["gpu_probe"] = probe(GT)
R["before"] = MG.hybrid_state()["state"]
res = MG.assign(log, hw, [])
R["assign1"] = {k: res.get(k) for k in ("hybrid", "hybrid_applied")}
R["after"] = vals()
R["journal"] = E.JOURNAL.has(MG.HYBRID_ID)
R["pending"] = MG.hybrid_state()["state"]
n = E.JOURNAL.count()
res = MG.assign(log, hw, [])
R["assign2"] = {k: res.get(k) for k in ("hybrid", "hybrid_applied")}
R["journal_same"] = E.JOURNAL.count() == n
R["set_again"] = MG.set_hybrid(log).get("applied", False)

# після перезавантаження DXGI дає «Високу продуктивність» P106 — перевірено
at = float(F.CFG["mining"]["hybrid_at"])
R["ok"] = MG.hybrid_state(probe(P106, ts=at + 60))["state"]
# перезавантажувався, а Windows і далі обирає GT 710
orig_boot = GI.boot_time
GI.boot_time = lambda: at + 30
R["wrong"] = MG.hybrid_state(probe(GT, ts=at + 60))["state"]
R["stale_probe"] = MG.hybrid_state(probe(GT, ts=at - 5))["state"]  # перевірка ще до зміни — чекаємо перезавантаження
GI.boot_time = orig_boot
R["no_pref"] = MG.hybrid_state(probe(""))["state"]  # Windows без EnumAdapterByGpuPreference — перевірити нічим

# рядки OptimaX-Rescue.cmd для цього запису
entry = E.JOURNAL.get(MG.HYBRID_ID) or {}
lines = [ln for rec in entry.get("undo", []) for ln in RS.undo_lines(rec)]
R["rescue"] = sum(1 for ln in lines if "EnableMsHybrid" in ln)

# «Повернути все» прибирає свої значення
MG.revert(log)
R["reverted"] = vals()
R["after_revert"] = MG.hybrid_state(probe(GT))["state"]

# значення, які користувач поставив сам (PowerShell), OptimaX не чіпає й не повертає
E.reg_set(CLS + r"\0001", MG.HYBRID_VALUE, 2, "dword")
E.reg_set(CLS + r"\0002", MG.HYBRID_VALUE, 1, "dword")
F.CFG["mining"] = dict(F.CFG["mining"], hybrid_at=0)
R["manual"] = MG.hybrid_state(probe(GT))["state"]
R["manual_assign"] = MG.assign(log, hw, []).get("hybrid_applied", False)
MG.revert(log)
R["manual_kept"] = vals()

# частково чужі значення (0 у GT 710) — OptimaX дописує лише те, чого бракує, і повертає саме своє
E.reg_set(CLS + r"\0001", MG.HYBRID_VALUE, 0, "dword")
R["partial_ops"] = [(op[1].rsplit("\\", 1)[-1], op[3]) for op in MG.hybrid_tweak(probe(GT)).ops]
MG.set_hybrid(log, probe(GT))
R["partial_after"] = vals()
MG.revert(log)
R["partial_reverted"] = vals()

# без прав адміністратора — нічого не пише й не повторює
E.reg_del_value(CLS + r"\0001", MG.HYBRID_VALUE)
E.reg_del_value(CLS + r"\0002", MG.HYBRID_VALUE)
orig_admin = E.is_admin
E.is_admin = lambda: False
R["no_admin"] = MG.set_hybrid(log, probe(GT)).get("error")
E.is_admin = orig_admin
R["no_admin_vals"] = vals()

# той самий шлях, коли DirectX P106 ще не бачить: значення ставляться, а після перезавантаження — «перевірено»
F.CFG["gpu_probe"] = hidden()
R["hidden_assign"] = MG.assign(log, hw, []).get("hybrid_applied", False)
R["hidden_vals"] = vals()
R["hidden_ok"] = MG.hybrid_state(probe(P106, ts=time.time() + 60))["state"]
MG.revert(log)
R["hidden_reverted"] = vals()

# драйвер однієї з карт не встановлено (GT 710 на стандартному адаптері Microsoft)
E.reg_set(CLS + r"\0001", "MatchingDeviceId", r"pci\cc_0300", "sz")
R["missing"] = MG.hybrid_state(probe(GT))["state"]
R["missing_assign"] = MG.assign(log, hw, []).get("hybrid")
R["log_missing"] = tr("mg.hybrid_missing", gpu="NVIDIA P106-100", display="NVIDIA GeForce GT 710") in LOG

out_dir = sys.argv[sys.argv.index("--out") + 1] if "--out" in sys.argv else "."
with open(os.path.join(out_dir, "roundtrip.json"), "w", encoding="utf-8") as f:
    json.dump(R, f, ensure_ascii=False, indent=1, default=str)
print("RESULT " + json.dumps(R, ensure_ascii=False, default=str), flush=True)
