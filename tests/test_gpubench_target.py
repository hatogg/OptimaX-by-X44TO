"""GPU-тест на гібридних системах: результат підписаний картою, що справді малює, датчики NVML — лише цієї карти,
а бали вбудованої графіки не порівнюються з балами ігрової карти."""
import sys

from _util import ROOT

sys.path.insert(0, ROOT)
import gpubench as GB  # noqa: E402  (без Qt і без змін у системі)

NV = "NVIDIA GeForce GTX 1060 6GB"
HD = "Intel(R) HD Graphics 4000"


def test_renders_on_nvidia():
    t = GB.render_target("NVIDIA Corporation", "NVIDIA GeForce GTX 1060 6GB/PCIe/SSE2", True, NV)
    assert t == dict(gpu=NV, sensors=True, idle="")


def test_renders_on_igpu_while_nvidia_idles():
    # майнінгова P106 / Optimus: вікно OpenGL малює Intel, NVML бачить NVIDIA
    t = GB.render_target("Intel", HD, True, NV)
    assert t["gpu"] == HD, "the result must be labelled with the GPU that rendered it"
    assert t["sensors"] is False, "sensors of an idle NVIDIA must not be shown next to Intel FPS"
    assert t["idle"] == NV


def test_no_nvidia_at_all():
    t = GB.render_target("Mesa", "llvmpipe (LLVM 17.0.6, 256 bits)", False, "")
    assert t == dict(gpu="llvmpipe (LLVM 17.0.6, 256 bits)", sensors=False, idle="")
    t = GB.render_target("AMD", "AMD Radeon RX 570 Series", False, "")
    assert t["gpu"] == "AMD Radeon RX 570 Series" and not t["idle"]


def test_nvidia_render_without_nvml():
    t = GB.render_target("NVIDIA Corporation", "NVIDIA GeForce RTX 3060/PCIe/SSE2", False, "")
    assert t == dict(gpu="NVIDIA GeForce RTX 3060/PCIe/SSE2", sensors=False, idle="")


def _res(score, gpu, idle=""):
    r = dict(kind="own", preset="1080p", mode="bench", score=score, gpu=gpu, avg=score / 100)
    if idle:
        r["idle_gpu"] = idle
    return r


def test_history_compares_only_same_gpu():
    cfg = {"bench": [_res(6000, NV)]}
    r = GB.save_result(cfg, _res(700, HD, idle=NV))
    assert "delta" not in r, "an integrated-graphics run must not be compared with a gaming-GPU run"
    r = GB.save_result(cfg, _res(6300, NV))
    assert r.get("delta") == 5.0, "the NVIDIA run is compared with the previous NVIDIA run, skipping the Intel one"


def test_history_old_entries_without_gpu_still_compare():
    cfg = {"bench": [dict(_res(5000, NV), gpu=None)]}
    r = GB.save_result(cfg, _res(5500, NV))
    assert r.get("delta") == 10.0
