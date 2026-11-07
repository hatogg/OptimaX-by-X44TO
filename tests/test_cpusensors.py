"""Точність Hardware Center: температура процесора з Core Temp / HWiNFO / AIDA64 / LibreHardwareMonitor, стала
теплова зона ACPI не видається за процесор, датчики NVML тієї карти, що треба, швидкість і виробник модулів пам'яті."""
import struct
import sys

from _util import ROOT

sys.path.insert(0, ROOT)
import cpusensors as CS  # noqa: E402
import gpubench as GB  # noqa: E402
import hwinfo as HI  # noqa: E402
import hwtests as HT  # noqa: E402


# ── Core Temp ──
def coretemp_buf(temps, cores, cpus=1, tjmax=100, fahr=0, delta=0, name=b"Intel Core i5 3570K"):
    b = bytearray(2700)
    for i in range(cpus):
        struct.pack_into("<I", b, CS.CT_TJMAX + 4 * i, tjmax)
    struct.pack_into("<II", b, CS.CT_CNT, cores, cpus)
    for i, t in enumerate(temps):
        struct.pack_into("<f", b, CS.CT_TEMP + 4 * i, t)
    b[CS.CT_NAME:CS.CT_NAME + len(name)] = name
    b[CS.CT_FAHR], b[CS.CT_DELTA] = fahr, delta
    return bytes(b)


def test_coretemp_hottest_core():
    assert CS.parse_coretemp(coretemp_buf([51.0, 55.0, 49.0, 53.0], 4)) == (55.0, "Intel Core i5 3570K")


def test_coretemp_distance_to_tjmax_and_fahrenheit():
    # режим «до TjMax»: 45 означає 105 - 45 = 60 °C
    assert CS.parse_coretemp(coretemp_buf([45.0, 50.0], 2, tjmax=105, delta=1))[0] == 60.0
    assert CS.parse_coretemp(coretemp_buf([140.0], 1, fahr=1))[0] == 60.0


def test_coretemp_rejects_garbage():
    assert CS.parse_coretemp(b"\0" * 100) is None
    assert CS.parse_coretemp(coretemp_buf([50.0], 0)) is None  # нуль ядер — не ті дані
    assert CS.parse_coretemp(coretemp_buf([0.0, 0.0], 2)) is None


# ── HWiNFO ──
def hwinfo_buf(readings, sensors, poll=1000):
    """readings: [(тип, індекс датчика, підпис, одиниця, значення)], sensors: [назва]."""
    s_size, r_size = 264 + 128, 316 + 144
    s_off = CS.HWI_HEAD.size
    r_off = s_off + s_size * len(sensors)
    b = bytearray(r_off + r_size * len(readings))
    CS.HWI_HEAD.pack_into(b, 0, CS.HWI_SIG, 2, 0, poll, s_off, s_size, len(sensors), r_off, r_size, len(readings))
    for i, n in enumerate(sensors):
        o = s_off + i * s_size
        b[o + 8:o + 8 + len(n)] = n.encode("cp1252")
    for i, (typ, si, label, unit, val) in enumerate(readings):
        o = r_off + i * r_size
        struct.pack_into("<II", b, o, typ, si)
        b[o + 12:o + 12 + len(label)] = label.encode("cp1252")
        b[o + 268:o + 268 + len(unit)] = unit.encode("cp1252")
        struct.pack_into("<d", b, o + 284, val)
    return bytes(b)


def test_hwinfo_prefers_cpu_package_over_motherboard_cpu():
    buf = hwinfo_buf([(1, 1, "CPU", "°C", 38.0), (1, 0, "Core Max", "°C", 63.0), (1, 0, "CPU Package", "°C", 61.0),
                      (6, 0, "Core 0 Clock", "MHz", 3800.0)],
                     ["CPU [#0]: Intel Core i5-3570K: DTS", "ASUS P8H67-M PRO (Nuvoton NCT6776F)"])
    assert CS.parse_hwinfo(buf, now=1005) == (61.0, "cpu package")


def test_hwinfo_amd_and_fahrenheit_and_stale():
    buf = hwinfo_buf([(1, 0, "CPU (Tctl/Tdie)", "°F", 158.0)], ["CPU [#0]: AMD Ryzen 5 3550H: Enhanced"])
    assert CS.parse_hwinfo(buf, now=1000) == (70.0, "cpu (tctl/tdie)")
    assert CS.parse_hwinfo(buf, now=5000) is None, "HWiNFO stopped polling: stale data is not a reading"
    assert CS.parse_hwinfo(b"DEAD" + b"\0" * 60) is None


# ── AIDA64 і LibreHardwareMonitor ──
def test_aida64():
    xml = (b"<sys><id>SCPUCLK</id><label>CPU Clock</label><value>3800</value></sys>"
           b"<temp><id>TMOBO</id><label>Motherboard</label><value>31</value></temp>"
           b"<temp><id>TCC-1-1</id><label>CPU Core #1</label><value>58</value></temp>"
           b"<temp><id>TCC-1-2</id><label>CPU Core #2</label><value>61</value></temp>\0junk")
    assert CS.parse_aida64(xml) == (61.0, "CPU Core #2")
    assert CS.parse_aida64(xml.replace(b"<temp><id>TMOBO", b"<temp><id>TCPUPKG</id><label>CPU Package</label>"
                                       b"<value>64</value></temp><temp><id>TMOBO"))[0] == 64.0


def test_lhm_only_cpu_sensors():
    tree = {"Text": "Sensor", "Children": [{"Text": "PC", "Children": [
        {"Text": "ASUS P8H67-M PRO", "ImageURL": "images_icon/mainboard.png", "Children": [
            {"Text": "Temperatures", "Children": [{"Text": "CPU Core", "Value": "33.0 °C"}]}]},
        {"Text": "Intel Core i5-3570K", "ImageURL": "images_icon/cpu.png", "Children": [
            {"Text": "Temperatures", "Children": [
                {"Text": "Core Max", "Value": "66.0 °C"}, {"Text": "CPU Package", "Value": "64.0 °C"}]}]}]}]}
    assert CS.parse_lhm(tree) == (64.0, "cpu package")
    assert CS.parse_lhm({"Text": "x", "Children": []}) is None


# ── теплова зона ACPI ──
def zone_samples(n, temp, src="acpi", util=99.0):
    return [dict(util=util, mhz=3800, limit=100.0, passive=100.0, temp=temp, temp_src=src, zone=temp)] * n


def test_static_acpi_zone_is_not_cpu_temperature():
    s = zone_samples(60, 27.8)
    temps, src = HT.cpu_temps(s)
    assert temps == [] and src == "acpi_static"
    keys = {k for _, k, _ in HT.cpu_findings(s)}
    assert "hwc.f.acpi_static" in keys and "hwc.f.cpu_hot" not in keys
    assert all(v is None for v in HT.temp_series(s)), "a flat 27.8 °C line must not pose as the CPU"


def test_moving_zone_is_kept_but_labelled():
    s = [dict(util=99.0, mhz=3800, limit=100.0, passive=100.0, temp=55 + i * 0.5, temp_src="acpi") for i in range(40)]
    temps, src = HT.cpu_temps(s)
    assert src == "acpi" and max(temps) == 74.5
    assert "hwc.f.acpi_zone" in {k for _, k, _ in HT.cpu_findings(s)}
    assert HT.temp_text(74.5, src).endswith("(ACPI)")
    assert HT.live_temp(s[0]).startswith("ACPI ")


def test_real_sensor_wins_and_short_or_hot_zones_are_not_static():
    s = zone_samples(10, 27.8) + zone_samples(30, 66.0, src="coretemp")
    temps, src = HT.cpu_temps(s)
    assert src == "coretemp" and set(temps) == {66.0}
    assert HT.live_temp(s[-1]) == "CPU 66 °C"
    assert not CS.acpi_static([27.8] * 10), "too short to call it a constant"
    assert not CS.acpi_static([70.0] * 40), "a coarse laptop zone at 70 °C is still a reading"


def test_old_findings_render_without_new_fields():
    text = HT.finding_str((HT.WARN, "hwc.f.cpu_hot", dict(t=91)))
    assert "{" not in text and "91" in text


# ── NVML: котра карта ──
def test_nvml_picks_card_by_name_then_by_memory():
    devs = [(0, "NVIDIA GeForce GT 710", 2 << 30), (1, "P106-100", 6 << 30)]
    assert GB.pick_device(devs, "") == 1, "without a name: the gaming card, not the GT 710 first on the bus"
    assert GB.pick_device(devs, "NVIDIA P106-100") == 1
    assert GB.pick_device(devs, "NVIDIA GeForce GT 710/PCIe/SSE2") == 0
    assert GB.pick_device(devs, "Intel(R) HD Graphics 4000") == 1
    assert GB.pick_device([], "x") == -1
    assert GB.gpu_key("NVIDIA GeForce GTX 1060 6GB/PCIe/SSE2") == GB.gpu_key("GeForce GTX 1060 6GB")


# ── пам'ять ──
def test_memory_vendor_codes():
    assert HI.mem_vendor("80CE000080CE") == "Samsung"
    assert HI.mem_vendor("CE00000000000000") == "Samsung"
    assert HI.mem_vendor("0198") == "Kingston"
    assert HI.mem_vendor("0x029E") == "Corsair"
    assert HI.mem_vendor("04CD") == "G.Skill"
    assert HI.mem_vendor("0000") == ""
    assert HI.mem_vendor("Kingston") == "Kingston"
    assert HI.mem_vendor("ABCD") == "ABCD", "unknown code stays as reported"


def smbios_type17(size_mb, speed, conf, form=9, mtype=24, strings=(b"DIMM_A1", b"BANK0", b"0198", b"SN", b"AS", b"99U5471")):
    fmt = bytearray(0x22)
    fmt[0], fmt[1] = 17, 0x22
    struct.pack_into("<H", fmt, 0x0C, size_mb)
    fmt[0x0E], fmt[0x10], fmt[0x11], fmt[0x12] = form, 1, 2, mtype
    struct.pack_into("<H", fmt, 0x15, speed)
    fmt[0x17], fmt[0x18], fmt[0x19], fmt[0x1A] = 3, 4, 5, 6
    struct.pack_into("<H", fmt, 0x20, conf)
    return bytes(fmt) + b"\0".join(strings) + b"\0\0"


def raw_smbios(*structs):
    data = b"".join(structs) + bytes([127, 4, 0, 0]) + b"\0\0"
    return bytes([0, 2, 7, 0]) + struct.pack("<I", len(data)) + data


def test_module_table_speed_type_form_and_vendor():
    raw = raw_smbios(smbios_type17(4096, 1333, 667), smbios_type17(4096, 1600, 1600, form=13),
                     smbios_type17(0, 0, 0, strings=(b"DIMM_B1", b"BANK2", b"Empty", b"", b"", b"")))
    mods = HI.smbios_details(raw)["modules"]
    assert [m["conf"] for m in mods] == [1333, 1600, 0], "SMBIOS 2.7 writes MHz: 667 is DDR3-1333"
    assert [m["form"] for m in mods] == ["DIMM", "SO-DIMM", ""]
    assert mods[0]["vendor"] == "Kingston" and mods[0]["type"] == "DDR3" and mods[0]["part"] == "99U5471"
    assert mods[2]["mb"] == 0 and mods[2]["vendor"] == "", "an empty slot has no vendor"
    assert HI.MEM_FORM[12] == "RIMM" and HI.MEM_FORM[13] == "SO-DIMM"
