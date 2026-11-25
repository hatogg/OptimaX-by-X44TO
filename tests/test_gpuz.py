"""OptimaX 7.2 — «Відеокарта» як у GPU-Z: розбір ідентифікаторів PCI, коди швидкості лінії PCIe -> покоління, стан лінії
(нижче максимуму / енергозбереження в простої), значення реєстру драйвера, зіставлення карт NVML з PnP за шиною,
кілька адаптерів (HD 4000 + P106-100) і текстовий звіт. Невідоме — «—», а не вигадане число."""
import os
import struct
import sys
import tempfile

from _util import ROOT

sys.path.insert(0, ROOT)
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import gpuinfo as GI  # noqa: E402
import gpuz as GZ  # noqa: E402


def test_link_speed_codes_to_generation():
    assert [GZ.link_gen(c) for c in (1, 2, 3, 4, 5, 6)] == ["1.1", "2.0", "3.0", "4.0", "5.0", "6.0"]
    assert GZ.link_gen(0) is None and GZ.link_gen(None) is None and GZ.link_gen("x") is None
    assert GZ.fmt_link(3, 16) == "PCIe 3.0 x16 · 8 GT/s"
    assert GZ.fmt_link(1, 1) == "PCIe 1.1 x1 · 2.5 GT/s"
    assert GZ.fmt_link(9, 8) == "PCIe x8"  # невідомий код — лише ширина, без вигаданого покоління
    assert GZ.fmt_link(4, None) is None and GZ.fmt_link(4, 0) is None


def test_link_state():
    assert GZ.link_state({"cs": 1, "cw": 1, "ms": 3, "mw": 16}) == "narrow"  # райзер x1
    assert GZ.link_state({"cs": 3, "cw": 4, "ms": 3, "mw": 16}) == "narrow"
    assert GZ.link_state({"cs": 1, "cw": 16, "ms": 4, "mw": 16}) == "slow_idle"  # простій — не несправність
    assert GZ.link_state({"cs": 1, "cw": 16, "ms": 4, "mw": 16}, util=10) == "slow_idle"
    assert GZ.link_state({"cs": 3, "cw": 16, "ms": 4, "mw": 16}, util=97) == "slow_load"
    assert GZ.link_state({"cs": 4, "cw": 16, "ms": 4, "mw": 16}) == "full"
    assert GZ.link_state({}) == "unknown" and GZ.link_state({"cs": 3, "ms": 3}) == "unknown"


def test_live_link_overrides_pnp():
    a = dict(link={"cs": 1, "cw": 16, "ms": 4, "mw": 16})
    lk = GZ.current_link(a, {"pcie_gen": 4, "pcie_width": 16})
    assert lk == {"cs": 4, "cw": 16, "ms": 4, "mw": 16} and GZ.link_state(lk) == "full"
    assert GZ.current_link(a, {}) == a["link"]


def test_instance_id_and_ids():
    ids = GZ.parse_instance_id(r"PCI\VEN_10DE&DEV_1C07&SUBSYS_11D710DE&REV_A1\4&1F0A5C3&0&00E4")
    assert ids == dict(ven=0x10DE, dev=0x1C07, sub=0x11D710DE, rev="A1")
    assert GZ.device_id_text(ids) == "10DE 1C07 - 10DE 11D7"
    assert GZ.subvendor(ids) == "NVIDIA (10DE)"
    assert GZ.subvendor(dict(sub=0x51361458)) == "Gigabyte (1458)"
    assert GZ.subvendor(dict(sub=0x0001ABCD)) == "ABCD"  # невідомий виробник — лише код
    assert GZ.parse_instance_id(r"ROOT\BasicDisplay\0000") == {}
    short = GZ.parse_instance_id(r"PCI\VEN_8086&DEV_0162\3&11583659&0&10")
    assert short["sub"] is None and short["rev"] is None and GZ.device_id_text(short) == "8086 0162"


def test_location():
    assert GZ.parse_location("PCI bus 3, device 0, function 0") == (3, 0, 0)
    assert GZ.parse_location("Шина PCI 1, устройство 0, функция 0") == (1, 0, 0)
    assert GZ.parse_location("Internal") is None and GZ.parse_location(None) is None
    assert GZ.fmt_location((3, 0, 0)) == "03:00.0" and GZ.fmt_location(None) is None


def test_registry_value_decoding():
    assert GZ.decode_reg_string("113-D7020100-102".encode("utf-16-le") + b"\0\0") == "113-D7020100-102"
    assert GZ.decode_reg_string(b"Intel Video BIOS\0") == "Intel Video BIOS"
    assert GZ.decode_reg_string(" Version 86.06 \0") == "Version 86.06"
    assert GZ.decode_reg_string(b"\x01\x02\x03\x04") is None  # не текст
    assert GZ.decode_reg_string(12345) is None and GZ.decode_reg_string(None) is None
    assert GZ.mem_type_from_reg("GDDR6".encode("utf-16-le")) == "GDDR6"
    assert GZ.mem_type_from_reg("HBM2E") == "HBM2e"
    assert GZ.mem_type_from_reg("gddr6x") == "GDDR6X"
    assert GZ.mem_type_from_reg(7) is None  # числовий код виробника — невідомо, не здогадуємось
    assert GZ.mem_type_from_reg("Unknown") is None


def test_nvidia_driver_version():
    assert GZ.nv_driver_version("31.0.15.8278") == "582.78"
    assert GZ.nv_driver_version("32.0.15.6094") == "560.94"
    assert GZ.nv_driver_version("31.0.15.3161") == "531.61"
    assert GZ.nv_driver_version("") is None and GZ.nv_driver_version("1.2.3") is None


def test_devprop_decoding():
    assert GZ.decode_devprop(0x07, struct.pack("<I", 16)) == 16
    assert GZ.decode_devprop(0x12, "\\Device\\NTPNP_PCI0012".encode("utf-16-le") + b"\0\0") == "\\Device\\NTPNP_PCI0012"
    assert GZ.decode_devprop(0x2012, "a\0b\0\0".encode("utf-16-le")) == ["a", "b"]
    assert GZ.decode_devprop(0x03, b"\x04") == 4 and GZ.decode_devprop(0x11, b"\xff") is True
    assert GZ.decode_devprop(0x07, b"\x01") is None  # обрізаний буфер — None, а не виняток
    assert GZ.decode_devprop(0x99, b"\x00\x00") is None


def test_nvml_pci_info():
    raw = b"00000000:03:00.0".ljust(16, b"\0") + struct.pack("<5I", 0, 3, 0, 0x1C0710DE, 0x11D710DE) + b"\0" * 64
    assert GZ.parse_nvml_pci(raw) == dict(domain=0, bus=3, device=0, ven=0x10DE, dev=0x1C07, sub=0x11D710DE)
    assert GZ.parse_nvml_pci(b"short") == {}


def _p106(bus):
    return dict(ven=0x10DE, dev=0x1C07, sub=0x11D710DE, loc=(bus, 0, 0))


def _nv(idx, bus):
    return dict(index=idx, pci=dict(bus=bus, device=0, ven=0x10DE, dev=0x1C07, sub=0x11D710DE))


def test_match_twin_cards_by_bus():
    # дві однакові P106: NVML перелічує їх в іншому порядку — зіставляємо за шиною, а не за назвою чи порядком
    ads = [_p106(3), _p106(5), dict(ven=0x8086, dev=0x0162, loc=(0, 2, 0))]
    GZ.match_nvml(ads, [_nv(0, 5), _nv(1, 3)])
    assert ads[0]["nv"]["index"] == 1 and ads[1]["nv"]["index"] == 0 and "nv" not in ads[2]


def test_match_without_location():
    one = [dict(ven=0x10DE, dev=0x1C07, sub=0x11D710DE, loc=None)]
    GZ.match_nvml(one, [_nv(0, 7)])
    assert one[0]["nv"]["index"] == 0  # унікальна карта — за VEN/DEV/SUBSYS
    twins = [dict(_p106(0), loc=None), dict(_p106(0), loc=None)]
    GZ.match_nvml(twins, [_nv(0, 3), _nv(1, 5)])
    assert all("nv" not in a for a in twins)  # не вгадуємо, чиї датчики — краще «—»


def _mining():
    pnps, nvs = GZ.demo_raw("mining")
    return GZ.assemble(pnps, nvs, GI.DEMO_PROBE["mining"], [], {})


def test_multi_gpu_mining_demo():
    ads = _mining()
    assert [a["name"] for a in ads] == ["Intel(R) HD Graphics 4000", "NVIDIA P106-100"]
    hd, p106 = ads
    assert hd["kind"] == "igpu" and hd["display"] and hd.get("nv_index") is None
    assert p106["kind"] == "mining" and not p106["display"] and p106["nv_index"] == 0
    assert p106["vk_api"] == "1.4.303" and p106["dx12"] is True and hd["dx12"] is False
    assert p106["nv_driver"] == "582.78" and p106["bus_width"] == 192 and p106["vbios_src"] == "nvml"
    rows = dict(GZ.bus_rows(p106))
    assert rows["gz.bus_cur"].startswith("PCIe 1.1 x1") and rows["gz.bus_max"].startswith("PCIe 3.0 x16")
    lv = dict(GZ.findings(p106))
    assert "warn" in lv and "x1" in lv["warn"] and "x16" in lv["warn"]
    hd_rows = dict(GZ.bus_rows(hd) + GZ.sensor_rows(hd) + GZ.memory_rows(hd))
    assert hd_rows["gz.bus_cur"] is None and hd_rows["gz.temp"] is None and hd_rows["gz.mem_type"] is None


def test_gaming_demo_idle_link_is_info_not_fault():
    pnps, nvs = GZ.demo_raw("gaming")
    (a,) = GZ.assemble(pnps, nvs, GI.DEMO_PROBE["gaming"], [dict(renderer="NVIDIA GeForce RTX 4070/PCIe/SSE2",
                                                                  gl="4.6.0 NVIDIA 581.57")], {})
    levels = [lvl for lvl, _ in GZ.findings(a, {"util": 3})]
    assert "warn" not in levels and levels[0] == "info"
    assert GZ.findings(a, {"util": 98, "pcie_gen": 3, "pcie_width": 16})[0][0] == "warn"  # під навантаженням — так
    assert GZ.findings(a, {"util": 98, "pcie_gen": 4, "pcie_width": 16})[0][0] == "ok"
    assert a["gl"] == "4.6.0 NVIDIA 581.57" and a["nv_driver"] == "581.57"
    assert dict(GZ.bus_rows(a))["gz.rebar"].startswith("No")  # BAR 256 МБ з повної карти ресурсів


def test_rebar_unknown_is_not_off():
    a = dict(kind="dgpu", bar_mb=256, bar_known=False, name="NVIDIA GeForce RTX 3080")
    assert GZ.rebar_text(a) is None  # WMI бачить лише 32-бітні вікна — «вимкнено» було б неправдою (7.0.1)
    assert GZ.rebar_text(dict(a, bar_mb=10240)).startswith("Yes")
    assert GZ.rebar_text(dict(a, kind="igpu", bar_known=True)) is None


def test_report_text():
    ads = _mining()
    text = GZ.report_text(dict(adapters=ads), {1: dict(temp=47, clock=139, util=0, pcie_gen=1, pcie_width=1)})
    assert "[1/2] Intel(R) HD Graphics 4000" in text and "[2/2] NVIDIA P106-100" in text
    assert "47 °C" in text and "139 MHz" in text and "10DE 1C07 - 10DE 11D7" in text
    assert "None" not in text and "—" in text
    assert "shader" not in text.lower() and "ROP" not in text  # без надійного джерела — не показуємо
    assert GZ.report_text(dict(adapters=[])).endswith(GZ.tr("gz.none"))


def test_demo_every_config_assembles():
    for name in GZ.DEMO:
        pnps, nvs = GZ.demo_raw(name)
        ads = GZ.assemble(pnps, nvs, GI.DEMO_PROBE.get(name) or {}, [], {})
        assert len(ads) == len(GZ.DEMO[name]), name
        for a in ads:
            assert (a.get("nv_index") is not None) == (a.get("ven") == 0x10DE), (name, a["name"])
            GZ.report_text(dict(adapters=[a]))


def test_real_windows_collect():
    """Справжня Windows (CI windows-2022 / 2025): SetupAPI, реєстр і NVML через ctypes не падають, звіт будується."""
    from _util import IS_WIN, skip
    if not IS_WIN:
        skip("needs real Windows")
    import engine as E
    old = E.IS_WIN
    E.IS_WIN = True
    try:
        assert isinstance(GZ.pnp_adapters(), list)
        d = GZ.collect({})
        assert isinstance(d.get("adapters"), list)
        assert "None" not in GZ.report_text(d)
        for a in d["adapters"]:
            assert isinstance(GZ.live(a), dict)
    finally:
        E.IS_WIN = old


def test_windows_reported_slow_link_promises_nothing():
    """Не NVIDIA: поточна швидкість лише з DEVPKEY (може бути станом на момент старту) — не «натисніть «Оновити»»
    і не попередження «під навантаженням», навіть якщо щось інше каже про завантаження."""
    a = dict(kind="dgpu", ven=0x1002, name="AMD Radeon RX 6600", link={"cs": 1, "cw": 16, "ms": 4, "mw": 16})
    for lv in ({}, {"util": 99}):
        lvl, text = GZ.findings(a, lv)[0]
        assert lvl == "info" and text == GZ.tr("gz.f.slow_pnp", cur="1.1", max="4.0")
    assert "Windows" in dict(GZ.bus_rows(a))["gz.bus_cur"]
    # NVIDIA з живою лінією NVML — як і раніше: простій — інформація, навантаження — попередження
    nv = dict(a, ven=0x10DE)
    assert GZ.findings(nv, {"util": 2, "pcie_gen": 1, "pcie_width": 16})[0] == \
        ("info", GZ.tr("gz.f.slow_idle", cur="1.1", max="4.0"))
    assert GZ.findings(nv, {"util": 99, "pcie_gen": 1, "pcie_width": 16})[0][0] == "warn"
    assert "Windows" not in dict(GZ.bus_rows(nv, {"pcie_gen": 1, "pcie_width": 16}))["gz.bus_cur"]


def test_panel_timer_stops_when_hidden():
    from _util import has_qt
    if not has_qt():
        from _util import skip
        skip("PyQt6 is not installed")
    src = open(os.path.join(ROOT, "pages_gpuz.py"), encoding="utf-8").read()
    assert "def hideEvent" in src and "WindowStateChange" in src and "self.timer.stop()" in src
