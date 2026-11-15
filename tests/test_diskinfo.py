"""OptimaX 7.1 — «Диски» як у CrystalDiskInfo: паспорт диска з ATA IDENTIFY і NVMe Identify, назви атрибутів SMART
(з уточненнями виробників), рівні рядків, записано / прочитано в правильних одиницях, журнал NVMe рядками, текстовий
звіт без серійника, якщо його не відкрили."""
import os
import struct
import sys
import tempfile

from _util import IS_WIN, ROOT, skip

sys.path.insert(0, ROOT)
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
import hardware as H  # noqa: E402
import storagehealth as SH  # noqa: E402
from test_undo_guarantees import patched  # noqa: E402


def ata_str(s: str, words: int) -> bytes:
    """Рядок ATA IDENTIFY: доповнений пробілами, байти в кожному слові переставлені."""
    b = s.ljust(words * 2).encode("ascii")
    return bytes(x for i in range(0, len(b), 2) for x in (b[i + 1], b[i]))


def identify(model="KINGSTON SA400S37480G", serial="50026B7783C331F6", fw="SBFKK1C3", rpm=1, cur_gen=3,
             trim=True) -> bytes:
    w = [0] * 256
    w[76] = 0b1110 | 1 << 8               # SATA I/II/III, NCQ
    w[77] = cur_gen << 1                  # поточна швидкість
    w[78] = 1 << 8                        # DevSleep
    w[80] = 1 << 10 | 1 << 9 | 1 << 8     # ACS-3
    w[82] = 1 << 0 | 1 << 5               # SMART, кеш запису
    w[83] = 1 << 3 | 1 << 10              # APM, 48-bit LBA
    w[84] = 1 << 5                        # GPL
    w[169] = 1 if trim else 0
    w[217] = rpm
    w[222] = 0x1000 | 1 << 8              # SATA 3.2
    b = bytearray(struct.pack("<256H", *w))
    b[20:40] = ata_str(serial, 10)
    b[46:54] = ata_str(fw, 4)
    b[54:94] = ata_str(model, 20)
    return bytes(b)


def test_ata_identify_like_crystaldiskinfo():
    d = SH.parse_ata_identify(identify())
    assert d["model"] == "KINGSTON SA400S37480G" and d["serial"] == "50026B7783C331F6" and d["firmware"] == "SBFKK1C3"
    assert d["interface"] == "Serial ATA" and d["transfer"] == "SATA/600 | SATA/600"
    assert d["standard"] == "ACS-3 | SATA 3.2"
    assert d["features"] == ["S.M.A.R.T.", "APM", "48bit LBA", "NCQ", "TRIM", "DevSleep", "GPL", "VolatileWriteCache"]
    assert d["rotation"] == "SSD"
    hdd = SH.parse_ata_identify(identify("ST2000DM008-2FR102", rpm=7200, cur_gen=2, trim=False))
    assert hdd["rotation"] == 7200 and hdd["transfer"] == "SATA/300 | SATA/600" and "TRIM" not in hdd["features"]
    assert SH.parse_ata_identify(b"") == {} and SH.parse_ata_identify(bytes(512)) == {}


def test_nvme_identify():
    b = bytearray(4096)
    b[4:24] = b"S64ANS0R123456K     "
    b[24:64] = b"Samsung SSD 980 1TB".ljust(40)
    b[64:72] = b"3B4QFXO7"
    struct.pack_into("<I", b, 80, 0x00010400)  # NVMe 1.4
    struct.pack_into("<H", b, 520, 0b100)       # Dataset Management (TRIM)
    b[525] = 1                                  # кеш запису
    d = SH.parse_nvme_identify(bytes(b))
    assert d["model"] == "Samsung SSD 980 1TB" and d["serial"] == "S64ANS0R123456K" and d["firmware"] == "3B4QFXO7"
    assert d["standard"] == "NVM Express 1.4" and d["features"] == ["S.M.A.R.T.", "TRIM", "VolatileWriteCache"]
    assert SH.parse_nvme_identify(bytes(4096)) == {}


def test_attribute_names_vendor_and_levels():
    assert SH.attr_name(0x05) == "Reallocated Sectors Count"
    assert SH.attr_name(0xE7, "KINGSTON SA400S37480G", True) == "SSD Life Left"
    assert SH.attr_name(0xE9, "KINGSTON SA400S37480G", True) == "Total NAND Writes (GiB)"
    assert SH.attr_name(0xE9, "INTEL SSDSC2KW256G8", True) == "Media Wearout Indicator"
    assert SH.attr_name(0xCA, "CT500MX500SSD1", True) == "Percent Lifetime Used"
    assert SH.attr_name(0x99) == "Vendor Specific"
    assert SH.attr_level(0x05, dict(current=100, threshold=10, raw=0)) == SH.GOOD
    assert SH.attr_level(0x05, dict(current=100, threshold=10, raw=8)) == SH.CAUTION
    assert SH.attr_level(0xC5, dict(current=100, threshold=0, raw=1)) == SH.CAUTION
    assert SH.attr_level(0x01, dict(current=40, threshold=51, raw=0)) == SH.BAD
    assert SH.attr_level(0x01, dict(current=100, threshold=0xFE, raw=0)) == SH.GOOD, "FEh/FFh — поріг не діє"


def test_host_writes_in_vendor_units():
    kingston = {0xF1: dict(raw=199_205), 0xF2: dict(raw=39_041), 0xE9: dict(raw=239_887)}
    io = SH.host_io("KINGSTON SA400S37480G", kingston)
    assert io["host_writes_gb"] == round(199_205 * 2 ** 30 / 1e9)
    assert io["nand_writes_gb"] == round(239_887 * 2 ** 30 / 1e9)
    samsung = {0xF1: dict(raw=20_000_000_000)}
    assert SH.host_io("Samsung SSD 870 EVO 1TB", samsung)["host_writes_gb"] == 10_240  # LBA по 512 байтів
    assert SH.host_io("CT500MX500SSD1", {0xF6: dict(raw=2_000_000_000)})["host_writes_gb"] == 1_024
    assert SH.host_io("Samsung SSD 870 EVO 1TB", {}) == {}


def test_nvme_table_and_health_label():
    nv = SH.parse_nvme_health(bytes([0, 0x3A, 0x01, 100, 10, 12]) + bytes(506))
    rows = SH.nvme_table(nv)
    assert [r[1] for r in rows[:5]] == [1, 2, 3, 4, 5]
    assert rows[1][6] == 0x13A, "температура NVMe в таблиці — у кельвінах, як у журналі"
    nv["spare"] = 5
    assert SH.nvme_table(nv)[2][0] == SH.BAD
    import hwtests as HT
    assert SH.health_label(dict(nvme=dict(percentage_used=12), assess=dict(status=HT.PASS))) == (SH.GOOD, 88)
    assert SH.health_label(dict(ata=dict(life_left=0), assess=dict(status=HT.FAIL))) == (SH.BAD, 0)
    assert SH.health_label(dict(assess=dict(status=HT.NA))) == (SH.UNKNOWN, None)


def test_pcie_link_text():
    assert SH.pcie_link(dict(cs=4, cw=4, ms=4, mw=4)) == "PCIe 4.0 x4 | PCIe 4.0 x4"
    assert SH.pcie_link(dict(cs=3, cw=2, ms=4, mw=4)) == "PCIe 3.0 x2 | PCIe 4.0 x4"
    assert SH.pcie_link({}) is None


def test_demo_disks_details_and_report():
    with patched(E, DEMO="gaming", IS_WIN=False):  # на справжній Windows демо-дисків немає
        hw = H._from_demo("gaming")
        disks = SH.check_all(hw)
    assert len(disks) == 2
    nvme, hdd = disks
    d = dict(SH.details(nvme))
    assert d["di.transfer"] == "PCIe 3.0 x4 | PCIe 3.0 x4" and d["di.firmware"] and d["di.host_writes"].endswith("GB")
    assert len(SH.smart_table(nvme)) == 15 and SH.health_label(nvme)[0] == SH.GOOD
    assert SH.smart_table(hdd)[0][2] == "Read Error Rate" and dict(SH.details(hdd))["di.rotation"] == "7200 RPM"
    text = SH.report_text(disks)
    assert "Samsung SSD 980 1TB" in text and "Reallocated Sectors Count" in text and "Critical Warning" in text
    with patched(E, DEMO="old", IS_WIN=False):
        old = SH.check_all(H._from_demo("old"))
    assert SH.health_label(old[0])[0] == SH.CAUTION, "8 перепризначених секторів — увага, як у CrystalDiskInfo"
    assert any(r[0] == SH.CAUTION and r[1] == 0x05 for r in SH.smart_table(old[0]))


def test_real_windows_reads_without_crashing():
    """CI windows-2022/2025: справжні IOCTL і PowerShell (віртуальний диск SMART не віддає — це «невідомо», не збій)."""
    if not IS_WIN:
        skip("потрібна справжня Windows")
    hw = H.detect_hw() if hasattr(H, "detect_hw") else None
    disks = SH.check_all(hw or {"disks": [dict(id="0", name="disk0", media="SSD", bus="SAS", letters=["C"])]})
    assert disks
    for d in disks:
        assert SH.health_label(d)[0] in (SH.GOOD, SH.CAUTION, SH.BAD, SH.UNKNOWN)
        assert len(SH.details(d)) == 13
        SH.smart_table(d)
    assert "OptimaX" in SH.report_text(disks)
    x = SH.disk_details_ps()
    assert isinstance(x, dict) and all("fw" in v for v in x.values())
