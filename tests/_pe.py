"""Крихітні PE-файли для тестів mining.py: лише заголовки й таблиці імпорту, які читає mining.pe_imports."""
import struct


def make_pe(imports=(), delay=(), pe32=False) -> bytes:
    """exe з таблицею імпорту (DLL у `imports`) і таблицею відкладеного імпорту (`delay`)."""
    e_lfanew = 0x80
    opt_size = 224 if pe32 else 240
    sec_va, sec_raw, sec_size = 0x1000, 0x400, 0x1000
    imp_rva = sec_va
    imp_size = 20 * (len(imports) + 1)
    dly_rva = sec_va + 0x400
    dly_size = 32 * (len(delay) + 1)
    names_rva = sec_va + 0x800
    body = bytearray(sec_size)
    pos, name_rvas = names_rva, {}
    for n in list(imports) + list(delay):
        if n in name_rvas:
            continue
        name_rvas[n] = pos
        off = pos - sec_va
        body[off:off + len(n) + 1] = n.encode() + b"\0"
        pos += len(n) + 1
    for i, n in enumerate(imports):
        struct.pack_into("<IIIII", body, imp_rva - sec_va + 20 * i, 0, 0, 0, name_rvas[n], 0)
    for i, n in enumerate(delay):
        struct.pack_into("<IIIIIIII", body, dly_rva - sec_va + 32 * i, 1, name_rvas[n], 0, 0, 0, 0, 0, 0)
    head = bytearray(sec_raw)
    head[0:2] = b"MZ"
    struct.pack_into("<I", head, 0x3C, e_lfanew)
    head[e_lfanew:e_lfanew + 4] = b"PE\0\0"
    coff = e_lfanew + 4
    struct.pack_into("<HHIIIHH", head, coff, 0x14C if pe32 else 0x8664, 1, 0, 0, 0, opt_size, 0x22)
    opt = coff + 20
    struct.pack_into("<H", head, opt, 0x10B if pe32 else 0x20B)
    dd = opt + (96 if pe32 else 112)
    struct.pack_into("<I", head, dd - 4, 16)
    struct.pack_into("<II", head, dd + 8 * 1, imp_rva if imports else 0, imp_size if imports else 0)
    struct.pack_into("<II", head, dd + 8 * 13, dly_rva if delay else 0, dly_size if delay else 0)
    sec = opt + opt_size
    head[sec:sec + 8] = b".rdata\0\0"
    struct.pack_into("<IIII", head, sec + 8, sec_size, sec_va, sec_size, sec_raw)
    return bytes(head) + bytes(body)


def write_pe(path: str, *imports, delay=()) -> str:
    with open(path, "wb") as f:
        f.write(make_pe(imports, delay))
    return path
