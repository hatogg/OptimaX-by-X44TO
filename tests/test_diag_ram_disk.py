"""«Чому лагає?» / «Чому зависає?» (6.15, баг від тестерів): «бракує оперативної пам'яті» — лише коли вільної
справді мало І Windows підкачує; «фризи від диска» — коли пам'яті вистачає, а фризи збігаються з повільним читанням
диска (який диск і затримка); пам'яті вдосталь і диск швидкий — жодної з цих карток."""
import os
import sys
import tempfile

from _util import ROOT

sys.path.insert(0, ROOT)
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import freezecatch as FZ  # noqa: E402
import monitor as M  # noqa: E402

GB = 1024


def sample(**kw):
    s = dict(cpu=50, core_max=70, gpu=90, avail_mb=21 * GB, pages_in=10, commit_pct=40, disk=20, disk_ms=1.0,
             disk_q=0.5, disk_inst="0 C:", temp=60, passive=100, limit=100, vram_used=4.0, gpu_t=65, fg="game.exe",
             bg={})
    s.update(kw)
    return s


HW = {"ram_gb": 32, "gpus": [("GPU", 8.0, "")], "disks": [dict(id="0", letters=["C"], media="HDD", name="WD Blue")]}


def keys(samples, hw=HW, frametimes=None):
    extra = {"frametimes": frametimes} if frametimes else {}
    return M.summarize(samples, hw, "game.exe", {}, extra=extra)["findings"]


def test_reading_game_files_is_not_a_ram_shortage():
    """Скарга тестерів: вільно 21 з 32 ГБ, а програма каже «бракує пам'яті» — через високий Pages Input/sec."""
    s = [sample(pages_in=2500) for _ in range(30)]
    found = [f["key"] for f in keys(s)]
    assert "ram" not in found and "disk" not in found, found
    assert M.classify(s[0], 32 * GB) != "ram"
    assert not M.ram_short(21 * GB, 32 * GB, pages_in=5000, commit_pct=99), "never advise more RAM above 25 % free"


def test_ram_shortage_needs_low_free_memory_and_paging():
    assert M.ram_short(1.5 * GB, 16 * GB, pages_in=400)
    assert M.ram_short(1.5 * GB, 16 * GB, pages_in=10, commit_pct=95), "commit near the limit is paging pressure too"
    assert not M.ram_short(1.5 * GB, 16 * GB, pages_in=10, commit_pct=50), "little free RAM but no paging"
    assert not M.ram_short(5 * GB, 16 * GB, pages_in=5000, commit_pct=99), "31 % free is never 'not enough RAM'"
    assert M.ram_short(300, None), "under 500 MB free Windows is paging for sure"
    s = [sample(avail_mb=1.2 * GB, pages_in=600, commit_pct=93) for _ in range(30)]
    ram = [f for f in keys(s, dict(HW, ram_gb=16)) if f["key"] == "ram"]
    assert ram and ram[0]["kw"]["free"] == "1.2", ram


def _stutter_frames():
    ft = [10.0] * 3000
    for i in (300, 900, 1500, 2100, 2700):  # фризи на ~3, 9, 15, 21 і 27-й секунді
        ft[i] = 90.0
    return ft


def test_disk_stutter_names_the_disk_and_its_latency():
    s = [sample() for _ in range(32)]
    for sec in (3, 9, 15, 21, 27):
        s[sec].update(disk=99, disk_ms=85.0, disk_q=7.0)
    f = {x["key"]: x for x in keys(s, frametimes=_stutter_frames())}
    assert "stutter_disk" in f, list(f)
    kw = f["stutter_disk"]["kw"]
    assert kw["what"] == "C: (HDD)" and kw["lat"] == 85, kw
    assert "ram" not in f and "stutter_ram" not in f


def test_fast_disk_and_enough_ram_show_neither_card():
    s = [sample() for _ in range(32)]
    for sec in (3, 9, 15, 21, 27):
        s[sec].update(disk=99, disk_ms=0.6, disk_q=1.0, pages_in=4000)  # NVMe зайнятий, але встигає
    found = [x["key"] for x in keys(s, frametimes=_stutter_frames())]
    assert not {"ram", "disk", "stutter_ram", "stutter_disk"} & set(found), found
    assert M.classify(s[3], 32 * GB) != "disk", "a busy but fast disk is not the bottleneck"


def test_disk_label_from_the_counter_instance():
    assert M.disk_label("0 C:", HW) == ("C:", "HDD")
    hw = {"disks": [dict(id="0", letters=["C"], media="NVMe"), dict(id="1", letters=["D", "E"], media="HDD")]}
    assert M.disk_label("1 D: E:", hw) == ("D:, E:", "HDD")


def test_freeze_catcher_uses_the_same_ram_rule():
    quiet = dict(core_max=2.0, core="0", cpu=12.0, win=4.0, didle=96.0, dq=0.0, avail_mb=9000.0, pages_in=5000.0)
    assert FZ.classify(3.0, quiet, [])[0] != "memory", "a high Pages Input/sec alone is not a RAM shortage"
    assert FZ.classify(3.0, dict(quiet, avail_mb=150.0), [])[0] == "memory"
