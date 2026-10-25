"""Визначення заліза без справжньої Windows: розбір SMBIOS і відповідей PowerShell, злиття джерел, підписи, оновлення."""
import _boot
import struct
import sys
import time

sys.argv = _boot.argv("--lang=uk")
import engine as E  # noqa: E402
import hardware as H  # noqa: E402
import hwnative as HN  # noqa: E402
import updater as U  # noqa: E402

R = {}


# ───────────── SMBIOS ─────────────
def st(typ, handle, length, fields=None, strings=()):
    b = bytearray(length)
    b[0], b[1] = typ, length
    struct.pack_into("<H", b, 2, handle)
    for off, (fmt, val) in (fields or {}).items():
        struct.pack_into(fmt, b, off, val)
    tail = b"".join(s.encode() + b"\0" for s in strings) + b"\0" if strings else b"\0\0"
    return bytes(b) + tail


def raw(*structs, ver=(3, 3)):
    table = b"".join(structs) + st(127, 0xFFFF, 4)
    return bytes([0, ver[0], ver[1], 0]) + struct.pack("<I", len(table)) + table


def mem(handle, array, size, mtype, speed, conf, ext=0, ext_speed=0, ext_conf=0, length=0x28):
    f = {0x04: ("<H", array), 0x0C: ("<H", size), 0x12: ("B", mtype), 0x15: ("<H", speed), 0x17: ("B", 1),
         0x1A: ("B", 2), 0x1C: ("<I", ext), 0x20: ("<H", conf)}
    if length >= 0x5C:
        f[0x54] = ("<I", ext_speed)
        f[0x58] = ("<I", ext_conf)
    return st(17, handle, length, f, ("Kingston", "KF432C16BB/16"))


ddr4 = raw(
    st(16, 0x10, 0x17, {0x05: ("B", 3)}),                     # системна пам'ять
    st(16, 0x11, 0x17, {0x05: ("B", 4)}),                     # пам'ять відеокарти — не рахуємо
    mem(0x20, 0x10, 16384, 26, 3200, 3200),
    mem(0x21, 0x10, 0x7FFF, 26, 3200, 3200, ext=32768),        # 32 ГБ через розширене поле
    mem(0x22, 0x10, 0, 2, 0, 0),                               # порожній слот
    mem(0x23, 0x11, 8192, 26, 3200, 3200),
    st(4, 0x30, 0x2A, {0x05: ("B", 3), 0x18: ("B", 0x41)}),
    st(4, 0x31, 0x2A, {0x05: ("B", 3), 0x18: ("B", 0x41)}),
    st(4, 0x32, 0x2A, {0x05: ("B", 3), 0x18: ("B", 0x00)}),   # порожній сокет
    st(3, 0x40, 0x15, {0x05: ("B", 0x83)}),                   # десктоп + біт замка
    st(1, 0x50, 0x1B, {0x04: ("B", 1), 0x05: ("B", 2)}, ("To be filled by O.E.M.", "Default string")),
    st(2, 0x60, 0x08, {0x04: ("B", 1), 0x05: ("B", 2)}, ("HUANANZHI", "X99-F8D")),
)
R["ddr4"] = HN.smbios_info(ddr4)
ddr5 = raw(mem(0x20, 0x10, 0x8000 | 0, 34, 0xFFFF, 0xFFFF, ext_speed=8000, ext_conf=7200, length=0x5C),  # 0 КБ — пропуск
           mem(0x21, 0x10, 0x7FFF, 34, 0xFFFF, 0xFFFF, ext=24576, ext_speed=8000, ext_conf=7200, length=0x5C),
           mem(0x22, 0x10, 8192, 35, 7500, 7500),
           st(1, 0x50, 0x1B, {0x04: ("B", 1), 0x05: ("B", 2)}, ("ASUSTeK COMPUTER INC.", "ROG Zephyrus")))
R["ddr5"] = HN.smbios_info(ddr5)
R["broken"] = HN.smbios_info(b"\x00\x03\x03\x00\xff\x00\x00\x00\x11\x02")  # обрізана таблиця — без винятку


# ───────────── дескриптор диска ─────────────
def descriptor(bus, vendor, product):
    head = bytearray(40)
    strings = b""
    off = 40
    vo = po = 0
    if vendor:
        vo, strings, off = off, strings + vendor.encode() + b"\0", off + len(vendor) + 1
    if product:
        po, strings = off, strings + product.encode() + b"\0"
    struct.pack_into("<II", head, 0, 1, 40 + len(strings))
    struct.pack_into("<IIII", head, 12, vo, po, 0, 0)
    struct.pack_into("<I", head, 28, bus)
    return bytes(head) + strings


R["desc_nvme"] = HN.parse_device_descriptor(descriptor(17, "", "Samsung SSD 980 1TB"))
R["desc_sata"] = HN.parse_device_descriptor(descriptor(11, "ATA     ", "ST2000DM008-2FR102"))
R["names"] = [HN.disk_name("ATA", "ST2000DM008"), HN.disk_name("WDC", "WDC WD10EZEX"), HN.disk_name("Kingston", "SA400"),
              HN.disk_name("", "")]
R["oem"] = [HN.clean_oem(x) for x in ("To be filled by O.E.M.", "System Product Name", "  MSI  ", "Default string")]
R["os"] = [HN.clean_os("Майкрософт Windows 11 Pro"), HN.clean_os("Microsoft Windows 10 Home"), HN.clean_os("")]

# ───────────── JSON із засміченого виводу PowerShell ─────────────
R["json"] = [
    E.parse_json_out('Cannot set property. Property setting is supported only on core types in this language mode.\n'
                     '{"cpu":[{"Name":"X"}]}\n'),
    E.parse_json_out('{"a":1}\nGet-NetAdapter : Access denied\n    + CategoryInfo'),
    E.parse_json_out('warning\n[\n  1,\n  2\n]\nmore text'),
    E.parse_json_out("Помилка: WMI не відповідає"),
    E.parse_json_out(""),
]

# ───────────── злиття дисків ─────────────
native = [dict(id="0", name="Samsung SSD 980 1TB", media="NVMe", bus="NVMe", health="", size_gb=1000, wear=None,
               temp=None, letters=["C"]),
          dict(id="1", name="ST2000DM008", media="HDD", bus="SATA", health="", size_gb=2000, wear=None, temp=None,
               letters=["D"])]
ps = [dict(id="0", name="Samsung SSD 980 1TB", media="4", bus="17", health="0", size=1000204886016, wear=2, temp=41),
      dict(id="1", name="ST2000DM008-2FR102", media="0", bus="11", health="5", size=2000398934016, wear=None, temp=None),
      dict(id="2", name="SanDisk Ultra", media="0", bus="7", health="0", size=32015679488)]
parts = [dict(l="C", d="0"), dict(l="D", d="1"), dict(l="E", d="2"), dict(l="F", d="9")]
R["disks"] = H.merge_disks(ps, parts, native)
R["disks_ps_only"] = H.merge_disks(ps[:2], parts, [])
R["disks_native_only"] = H.merge_disks([], [], native)
R["speed_fix"] = [H.ram_speed_fix(3200, 1600), H.ram_speed_fix(3200, 2666), H.ram_speed_fix(0, 2400),
                  H.ram_speed_fix(2133, 1066), H.ram_speed_fix(3200, 0)]


# ───────────── detect_hw на «Windows» з підмінами ─────────────
def fake_detect(core, storage, nat):
    E.IS_WIN = True
    answers = {H.CORE_SCRIPT: core, H.STORAGE_SCRIPT: storage, H.GPU_PCI_SCRIPT: None}
    E.ps_json = lambda script, timeout=40: answers.get(script)
    HN.collect = lambda: dict(nat)
    H.gpu_temp = lambda: None
    H.display_adapter = lambda: ""
    H.refresh_rates = lambda: (144, 165)
    H.cpu_topology = lambda: {}
    H._efficiency_classes = lambda: (0, 0)
    H._battery = lambda: False
    H._power_caps = lambda: (False, False)
    H._vram_from_registry = lambda name: 0.0
    HN.driver_key_for = lambda pnp: "{4d36e968-e325-11ce-bfc1-08002be10318}\\0000" if "VEN_10DE" in pnp else ""
    HN.driver_info = lambda key: dict(vram=12.0, date="2025-01-01") if key else {}
    try:
        return H.detect_hw()
    finally:
        E.IS_WIN = False


NATIVE = dict(cpu="Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz", mhz=2394, cores=28, threads=56, sockets=2,
              ram_gb=64.0, ram_modules=4, ram_type="DDR4", ram_max_speed=2400, ram_speed=2133, installed_gb=64.0,
              chassis=[3], vendor="HUANANZHI", model="X99-F8D", build=19045, os="Windows 10 Pro",
              gpus=[dict(name="NVIDIA GeForce GTX 1660 SUPER", vram=6.0, date="2024-05-01"),
                    dict(name="Microsoft Basic Display Adapter", vram=0.0, date="")],
              disks=native, wifi=False, ethernet=True)
keep = (E.ps_json, HN.collect, H.gpu_temp, H.display_adapter, H.refresh_rates, H.cpu_topology, H._efficiency_classes,
        H._battery, H._power_caps, H._vram_from_registry, HN.driver_key_for, HN.driver_info)
hw = fake_detect(None, None, NATIVE)  # PowerShell не відповів зовсім
R["native_only"] = {k: hw.get(k) for k in ("cpu", "cores", "threads", "sockets", "mhz", "ram_gb", "ram_type", "ram_speed",
                                           "ram_modules", "gpus", "disk_type", "disk_bus", "disk_name", "os", "build",
                                           "vendor", "model", "ethernet", "profile", "sources")}
CORE = {"cpu": [{"Name": "Intel(R) Xeon(R) CPU E5-2680 v4 @ 2.40GHz  ", "NumberOfCores": 14,
                 "NumberOfLogicalProcessors": 28, "MaxClockSpeed": 2400}] * 2,
        "ram": [{"Capacity": 17179869184, "Speed": 3200, "ConfiguredClockSpeed": 1600, "SMBIOSMemoryType": 26}] * 2,
        "os": {"Caption": "Майкрософт Windows 11 Pro", "BuildNumber": "22631"},
        "gpu": [{"Name": "NVIDIA GeForce RTX 4070", "AdapterRAM": 4293918720, "PNPDeviceID": "PCI\\VEN_10DE&DEV_2786\\4",
                 "DriverDate": "2025-02-01"},
                {"Name": "Parsec Virtual Display Adapter", "AdapterRAM": 0, "PNPDeviceID": "ROOT\\DISPLAY\\0000"}],
        "chassis": 3, "vbs": 2, "cs": {"Manufacturer": "System manufacturer", "Model": "System Product Name"},
        "net": {"InterfaceDescription": "Intel(R) Wi-Fi 6 AX201", "NdisPhysicalMedium": 9}}
STORAGE = {"disks": ps[:2], "parts": parts[:2]}
nat2 = dict(NATIVE, vendor="ASUSTeK COMPUTER INC.", model="PRIME B550-PLUS")
hw = fake_detect(CORE, STORAGE, nat2)
R["merged"] = {k: hw.get(k) for k in ("cpu", "cores", "threads", "sockets", "mhz", "ram_gb", "ram_type", "ram_speed",
                                      "ram_max_speed", "ram_modules", "gpus", "disk_type", "disk_bus", "disk_name", "os",
                                      "build", "vendor", "model", "wifi", "vbs_running")}
R["labels"] = dict(cpu=H.cpu_sub(hw), ram=H.ram_line(hw), ram_sub=H.ram_sub(hw), disk=H.disk_line(hw),
                   kind=H.disk_kind(hw))
(E.ps_json, HN.collect, H.gpu_temp, H.display_adapter, H.refresh_rates, H.cpu_topology, H._efficiency_classes,
 H._battery, H._power_caps, H._vram_from_registry, HN.driver_key_for, HN.driver_info) = keep

# ───────────── підписи ─────────────
R["fmt"] = [H.ram_line({"ram_gb": 15.96}), H.ram_line({}), H.vram_text(0.5), H.vram_text(7.99), H.vram_text(1.5),
            H.vram_text(0), H.disk_kind({"disk_type": "?", "disk_bus": "SATA"}),
            H.disk_kind({"disk_type": "NVMe", "disk_bus": "NVMe"}), H.disk_kind({}), H.disk_line({"disk_name": "WDC"}),
            H.cpu_sub({"cores": 0}), H.ram_sub({"ram_type": "", "ram_speed": 0, "ram_modules": 0})]
demo = H.detect_hw()
R["demo"] = dict(ram_type=demo["ram_type"], ram=H.ram_line(demo), cpu=H.cpu_sub(demo))
checks = H.build_check(dict(demo, ram_modules=0, ram_speed=0, ram_max_speed=0, refresh=(0, 0), disk_type="?",
                            hdd=False), [])
R["checks_unknown"] = sorted(c["id"] for c in checks)

# ───────────── оновлення ─────────────
now = time.time()
R["due"] = [U.due({"last_check": now - 7 * 3600}, now), U.due({"last_check": now - 3600}, now),
            U.due({"last_check": 0, "last_try": now - 60}, now), U.due({"last_check": 0, "last_try": now - 3600}, now),
            U.due({}, now)]
R["cached"] = [U.cached({"latest": {"version": "99.0"}}), U.cached({"latest": {"version": E.VERSION}}), U.cached({})]
R["snoozed"] = [U.snoozed({"snooze": {"v": "9.9", "until": now + 100}}, "9.9", now),
                U.snoozed({"snooze": {"v": "9.9", "until": now + 100}}, "9.10", now),
                U.snoozed({"snooze": {"v": "9.9", "until": now - 1}}, "9.9", now)]
rel = {"tag_name": "v99.1", "html_url": "https://github.com/x/y/releases/tag/v99.1", "body": "notes",
       "assets": [{"name": "OptimaX-Setup-99.1.exe", "browser_download_url": "https://e/s.exe", "size": 5},
                  {"name": "OptimaX-99.1-portable.exe", "browser_download_url": "https://e/p.exe", "size": 6}]}
R["release"] = [U.from_release(rel, True), U.from_release(rel, False), U.from_release(dict(rel, tag_name="v1.0"), True)]
_boot.result(**R)
