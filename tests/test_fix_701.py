"""OptimaX 7.0.1 — скарги користувачів після 7.0.0:

• «Resizable BAR вимкнено», хоча SmartAccess Memory у драйвері AMD увімкнено: WMI не бачить вікон пам'яті понад 4 ГБ,
  тож розмір BAR читаємо з карти ресурсів PnP, а «вимкнено» кажемо лише тоді, коли її прочитано;
• CrystalDiskInfo — «Bad 0%», а OptimaX — «диски в порядку»: знос і збої — з атрибутів SMART SATA-диска;
• Interrupt Moderation і Flow Control вимкнені вручну, а OptimaX цього не бачить: Ethernet з NdisPhysicalMedium = 0
  і невикористаний другий порт на платі."""
import base64
import os
import struct
import sys
import tempfile

from _util import IS_WIN, ROOT, skip

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
import hardware as H  # noqa: E402
from test_health import card, facts  # noqa: E402
import healthcheck as HC  # noqa: E402


# ── Resizable BAR ──
def resource_list(*descs) -> bytes:
    """REG_RESOURCE_LIST (x64) з одним повним дескриптором: (тип, прапорці, початок, довжина)."""
    b = struct.pack("<I", 1) + struct.pack("<iIHHI", 5, 3, 1, 1, len(descs))
    for typ, flags, start, length in descs:
        b += struct.pack("<BBHQI", typ, 0, flags, start, length)
    return b


def test_resource_map_sees_the_large_bar():
    rx7800 = resource_list((3, 0, 0xFCE00000, 2 << 20),          # регістри — 2 МБ
                           (7, 0x0800, 0x7C00000000, 4),          # BAR відеопам'яті: 4 << 32 = 16 ГБ (MemoryLarge 64)
                           (1, 0, 0xE000, 0x100))                 # порти вводу-виводу — не пам'ять
    assert H.parse_resource_list(rx7800) == 16 << 30
    legacy = resource_list((3, 0, 0xE0000000, 256 << 20), (3, 0, 0xFCE00000, 2 << 20))
    assert H.parse_resource_list(legacy) == 256 << 20
    assert H.parse_resource_list(resource_list((7, 0x0200, 0, 1 << 20))) == 256 << 20  # LARGE_40: довжина << 8
    assert H.parse_resource_list(b"\x01\x00") is None, "обрізані дані — невідомо, а не 0"


def rebar(**g):
    hw = dict(gpu_pci=[dict(name="AMD Radeon RX 7800 XT", cw=16, mw=16, **g)], gpus=[], disks=[])
    return next((r for r in H.build_check(hw) if r.get("id") == "rebar"), None)


def test_rebar_off_only_when_the_whole_memory_map_was_read():
    assert rebar(bar_mb=16384, bar_known=True)["level"] == "ok"
    assert rebar(bar_mb=2, bar_known=False) is None, "WMI бачить лише 2 МБ регістрів — це ще не «вимкнено»"
    assert rebar(bar_mb=256, bar_known=True)["level"] == "info", "карту ресурсів прочитано: справді 256 МБ"
    assert "DEVPKEY_Device_PDOName" in H.GPU_PCI_SCRIPT


# ── SMART SATA-диска ──
def attr(i, cur, raw):
    return bytes([i, 0x32, 0, cur, cur]) + raw.to_bytes(6, "little") + b"\0"


def blob(*attrs) -> bytes:
    b = b"\x10\x00" + b"".join(attrs)
    return b + b"\0" * (512 - len(b))


def thresholds(**t) -> bytes:
    b = b"\x10\x00" + b"".join(bytes([int(k[1:], 16), v]) + b"\0" * 10 for k, v in t.items())
    return b + b"\0" * (512 - len(b))


def test_kingston_a400_worn_out_is_seen():
    # знімок з CrystalDiskInfo користувача: KINGSTON SA400S37480G, 33 736 год, «Bad 0%»
    data = blob(attr(0x09, 100, 33736), attr(0xA9, 100, 5), attr(0xAA, 100, 5), attr(0xE7, 0, 0))
    sm = H.smart_summary(data, thresholds(xAA=10))
    assert sm["life"] == 0 and sm["fail"] == [] and not sm["predict"]
    disks = [dict(id="0", name="KINGSTON SA400S37480G", health="Healthy", wear=0)]
    H.apply_smart(disks, [dict(id="0", v=base64.b64encode(data).decode(), t="", pf=False)])
    assert disks[0]["wear"] == 100
    f = facts()
    f["disks"] = [dict(name="KINGSTON SA400S37480G", health="Healthy", wear=100, temp=34, smart_fail=[],
                       free=[dict(l="C", free=290.0, total=479.0)])]
    c = card(f, "disk")
    assert c["st"] == HC.BAD and any(d[0] == "hc.disk.worn" for d in c["det"])


def test_smart_life_sources_and_failure_threshold():
    assert H.smart_summary(blob(attr(0xA9, 100, 7)))["life"] == 93, "WD: у raw — відсоток використаного"
    assert H.smart_summary(blob(attr(0xB1, 61, 1200)))["life"] == 61, "Samsung: нормалізоване значення"
    assert H.smart_summary(blob(attr(0xE7, 100, 0x64)))["life"] == 100
    assert H.smart_summary(blob(attr(0x05, 100, 0)))["life"] is None, "немає атрибута ресурсу — невідомо"
    sm = H.smart_summary(blob(attr(0x05, 9, 2000)), thresholds(x05=10))
    assert sm["fail"] == [0x05], "атрибут нижче порогу — диск відмовляє, хоч Windows і пише «Healthy»"
    disks = [dict(id="1", name="HDD", health="Healthy", wear=None)]
    H.apply_smart(disks, [dict(id="1", v=base64.b64encode(blob(attr(0x05, 9, 2000))).decode(),
                               t=base64.b64encode(thresholds(x05=10)).decode(), pf=False)])
    assert disks[0]["smart_fail"] == ["05"] and disks[0]["wear"] is None
    f = facts()
    f["disks"][0]["smart_fail"] = ["05"]
    assert card(f, "disk")["st"] == HC.BAD
    assert H.smart_summary(b"") == {}


def test_storage_script_reads_smart_by_disk_number():
    s = H.STORAGE_SCRIPT
    assert "MSStorageDriver_FailurePredictData" in s and "Win32_DiskDrive" in s and "smart=$sm" in s


# ── Ethernet: Interrupt Moderation / Flow Control ──
def nic(m=14, mt="802.3", up=True, im="0", fc="0", name="Ethernet"):
    return dict(n=name, m=m, mt=mt, up=up, desc="Realtek Gaming 2.5GbE Family Controller", pm="",
                p=[dict(k="*InterruptModeration", v=im, d="Interrupt Moderation", valid=["0", "1"]),
                   dict(k="*FlowControl", v=fc, d="Flow Control", valid=["0", "1", "2", "3"])])


def test_eth_state_sees_unspecified_medium_and_ignores_unused_port():
    assert E.eth_latency_state([nic(m=0)]) is True, "Realtek 2.5G з NdisPhysicalMedium = 0 — теж Ethernet"
    assert E.eth_latency_state([nic(m=0, mt="Native 802.11")]) == "na"
    both = [nic(), nic(up=False, im="1", fc="3", name="Ethernet 2")]
    assert E.eth_latency_state(both) is True, "невикористаний другий порт не робить твік «не застосованим»"
    assert E.eth_latency_state([nic(), nic(im="1", name="Ethernet 2")]) is False, "обидва підключені — обидва важать"
    off = [nic(up=False, im="1"), nic(up=False, name="Ethernet 2")]
    assert E.eth_latency_state(off) is False, "жоден не підключений — дивимося на всі"
    assert "MediaType -eq '802.3'" in E.ETH_FILTER and "mt=[string]$a.MediaType" in E.NIC_STATE_PS


def test_scripts_on_real_windows():
    """CI windows-2022/2025: нові запити PowerShell не ламають збір даних (SMART на віртуалці може бути порожнім)."""
    if not IS_WIN:
        skip("потрібна справжня Windows")
    st = E.ps_json(H.STORAGE_SCRIPT, 120)
    assert isinstance(st, dict) and st.get("disks"), st
    assert isinstance(E.as_list(st.get("smart")), list)
    nics = E.nic_snapshot()
    assert nics is not None and all("mt" in a and "up" in a for a in nics)
    pci = E.as_list(E.ps_json(H.GPU_PCI_SCRIPT, 120))
    for g in pci:
        assert "pdo" in g
        big = H.resource_map_max_mem(g.get("pdo"))
        assert big is None or big > 0
