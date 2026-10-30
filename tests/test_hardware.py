"""Залізо: SMBIOS, засмічений вивід PowerShell, злиття джерел, підписи без «0 ГБ» і «?», перевірка оновлень."""
from _util import run_script, tail

_R = None


def res():
    global _R
    if _R is None:
        rc, out, r = run_script("hw_parsing.py")
        assert rc == 0 and r, tail(out)
        _R = r
    return _R


def test_smbios_memory_sockets_vendor():
    r = res()
    d4 = r["ddr4"]
    assert d4["ram_modules"] == 2 and d4["ram_gb"] == 48, "empty slot and GPU memory array must be skipped"
    assert d4["ram_type"] == "DDR4" and d4["ram_speed"] == 3200 and d4["sockets"] == 2
    assert d4["chassis"] == [3] and (d4["vendor"], d4["model"]) == ("HUANANZHI", "X99-F8D")
    d5 = r["ddr5"]
    assert d5["ram_type"] == "DDR5" and d5["ram_gb"] == 32 and d5["ram_max_speed"] == 8000
    assert r["broken"] == {}


def test_storage_descriptor_and_names():
    r = res()
    assert r["desc_nvme"]["bus"] == "NVMe" and r["desc_nvme"]["product"] == "Samsung SSD 980 1TB"
    assert r["desc_sata"]["bus"] == "SATA" and r["desc_sata"]["vendor"] == "ATA"
    assert r["names"] == ["ST2000DM008", "WDC WD10EZEX", "Kingston SA400", ""]
    assert r["oem"] == ["", "", "MSI", ""]
    assert r["os"] == ["Windows 11 Pro", "Windows 10 Home", "Windows"]


def test_powershell_json_with_errors_around_it():
    assert res()["json"] == [{"cpu": [{"Name": "X"}]}, {"a": 1}, [1, 2], None, None]


def test_disk_merge():
    r = res()
    d = {x["id"]: x for x in r["disks"]}
    assert d["0"]["media"] == "NVMe" and d["0"]["health"] == "Healthy" and d["0"]["wear"] == 2
    assert d["1"]["media"] == "HDD", "unspecified MediaType must fall back to the seek penalty query"
    assert d["1"]["name"] == "ST2000DM008-2FR102" and d["1"]["health"] == "", "HealthStatus 5 is 'unknown', not a fault"
    assert d["2"]["bus"] == "USB" and d["2"]["letters"] == ["E"]
    assert [x["media"] for x in r["disks_ps_only"]] == ["NVMe", "?"]
    assert [x["media"] for x in r["disks_native_only"]] == ["NVMe", "HDD"]
    assert r["speed_fix"] == [3200, 2666, 2400, 2133, 3200]


def test_detect_without_powershell():
    n = res()["native_only"]
    assert n["cpu"].startswith("Intel(R) Xeon") and (n["cores"], n["threads"], n["sockets"]) == (28, 56, 2)
    assert n["ram_gb"] == 64 and n["ram_type"] == "DDR4" and n["ram_modules"] == 4
    assert n["gpus"] == [["NVIDIA GeForce GTX 1660 SUPER", 6.0, "2024-05-01"]], "virtual adapters are hidden"
    assert (n["disk_type"], n["disk_name"]) == ("NVMe", "Samsung SSD 980 1TB")
    assert n["os"] == "Windows 10 Pro" and n["build"] == 19045 and n["profile"] == "X"
    assert n["sources"]["ps_core"] is False and "cpu" in n["sources"]["native"]


def test_detect_merged():
    m = res()["merged"]
    assert (m["cores"], m["threads"], m["sockets"]) == (28, 56, 2), "dual-CPU systems must be summed"
    assert m["cpu"] == "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz"
    assert m["ram_type"] == "DDR4" and m["ram_speed"] == 3200 and m["ram_gb"] == 32
    assert m["gpus"] == [["NVIDIA GeForce RTX 4070", 12.0, "2025-02-01"]], "VRAM comes from the device's driver key"
    assert m["os"] == "Windows 11 Pro" and m["build"] == 22631
    assert (m["vendor"], m["model"]) == ("ASUSTeK COMPUTER INC.", "PRIME B550-PLUS"), "OEM placeholders are replaced"
    assert m["wifi"] and m["vbs_running"]
    lb = res()["labels"]
    assert lb["cpu"] == "ядер: 28, потоків: 56, процесорів: 2, базова частота 2.40 ГГц"
    assert lb["ram"] == "32 ГБ DDR4, 3200 МГц" and lb["ram_sub"] == "DDR4, 3200 МГц, модулів: 2"


def test_labels_never_show_zero_or_question_marks():
    f = res()["fmt"]
    assert f == ["16 ГБ", "Не визначено", "Відеопам'ять 512 МБ", "Відеопам'ять 8 ГБ", "Відеопам'ять 1.5 ГБ", "", "SATA",
                 "NVMe", "Не визначено", "WDC", "", ""]
    checks = res()["checks_unknown"]
    assert not {"xmp", "channel", "refresh", "disk"} & set(checks), checks


def test_update_schedule_and_snooze():
    r = res()
    assert r["due"] == [True, False, False, True, True]
    assert r["cached"] == [{"version": "99.0"}, None, None]
    assert r["snoozed"] == [True, False, False]
    setup, portable, old = r["release"]
    assert setup["url"] == "https://e/s.exe" and setup["kind"] == "setup"
    assert portable["url"] == "https://e/p.exe" and old is None
    notes = r["notes"]
    assert notes.startswith("Виправлено") and "English" not in notes and "**" not in notes and "Files" not in notes
    assert len(notes) <= 1502


def test_mining_card_is_recognised():
    m = res()["mining"]
    assert m["mining"] == [{"name": "NVIDIA GeForce GTX 1060 6GB", "model": "P106-100"}], \
        "the patched driver calls a P106-100 'GTX 1060' — it must be recognised by its PCI ID"
    assert m["mining_gpu"] == "P106-100" and m["dgpu"]
    checks = m["checks"]
    assert checks["mining"] == ["info", ["hint", "mining"]]
    assert "display" not in checks, "a card without outputs must not trigger 'move the monitor cable'"
    assert checks["driver"][0] == "ok", "never send a mining card to nvidia.com — the regular driver disables 3D"
    assert "hags" not in checks
    assert m["hags"] == "block" and m["hags_regular"] == "ok"
    assert "P106-100" in m["detail"] and "Intel(R) HD Graphics 4000" in m["detail"]


def test_mining_models_by_name_and_id():
    r = res()
    assert r["mining_names"] == ["P106-100", "P104-101", "CMP 30HX", "CMP 170HX", "", ""]
    assert r["mining_ids"] == ["P106-090", "CMP 90HX", "", ""], "GTX 1060 (1C03) and non-NVIDIA IDs are not mining cards"
