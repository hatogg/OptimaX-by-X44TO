"""
OptimaX — на якій відеокарті малює GPU-тест (ноутбуки з гібридною графікою, ПК з кількома картами, майнінгова карта).

Тест OptimaX малює через OpenGL (gpubench.py), а OpenGL сам адаптер не обирає: контекст дістається карті, до якої
під'єднано монітор, якщо драйвер не перенаправить процес. На ноутбуці з NVIDIA Optimus чи AMD Hybrid монітор
під'єднано до вбудованої графіки, тож без підказки тест малювала вона, а RTX 4060 простоювала (відгук користувача
портативної версії).

Як OptimaX просить потрібну карту — від способу, що нічого не змінює в системі:
• NVIDIA Optimus — змінна середовища SHIM_MCCOMPAT лише для процесу тесту: 0x800000001 — NVIDIA, 0x800000000 —
  вбудована. Те саме робить пункт «Запустити з графічним процесором» у контекстному меню драйвера NVIDIA.
• Mesa (завантажується окремо, mining.py) — OpenGL через DirectX 12 на адаптері з потрібною назвою
  (MESA_D3D12_DEFAULT_ADAPTER_NAME). Працює з будь-якою картою з DirectX 12, але повільніше за рідний драйвер, тож бали
  з Mesa порівнюються лише з балами з Mesa.
• Налаштування «Графіка» Windows (UserGpuPreferences, GpuPreference=2) для exe OptimaX — лише за згодою й через журнал
  відкату. Для портативної версії воно прив'язане до поточного шляху exe.

Жоден спосіб не вважається спрацьованим наперед. Після тесту OptimaX звіряє GL_RENDERER з вибраною картою, а на Windows
ще й лічильники «GPU Engine»: 3D-навантаження процесу тесту на кожному адаптері (за LUID). LUID змінюється після
перезавантаження, тож вибір зберігається за VEN/DEV/SUBSYS карти, а LUID береться з поточного переліку.
"""
from __future__ import annotations

import re
import sys

import engine as E
from i18n import tr

AUTO = "auto"
SHIM_VAR = "SHIM_MCCOMPAT"
SHIM_DGPU = "0x800000001"
SHIM_IGPU = "0x800000000"
MESA_VAR = "MESA_D3D12_DEFAULT_ADAPTER_NAME"
PREF_ID = "bench:gpupref"
PREF_HIGH = "GpuPreference=2;"
VENDORS = {0x10DE: "nvidia", 0x1002: "amd", 0x1022: "amd", 0x8086: "intel", 0x1414: "microsoft"}
VENDOR_WORDS = {"nvidia": ("nvidia", "geforce", "quadro", "tesla", "rtx", "gtx"),
                "amd": ("amd", "radeon", "ati technologies", "ati "),
                "intel": ("intel",)}
SOFTWARE_GL = ("llvmpipe", "softpipe", "gdi generic", "microsoft basic render", "swrast", "warp")
STOP_WORDS = {"amd", "ati", "nvidia", "geforce", "intel", "radeon", "r", "tm", "graphics", "gpu", "laptop", "series",
              "corporation", "technologies", "inc", "with", "max", "q", "design", "the", "d3d12", "mobile", "family",
              "core", "processor", "opengl", "engine", "pcie", "sse2", "x86", "x64"}
STATUSES = ("confirmed", "renderer", "likely", "wrong", "unknown")


# ───────────────────────── перелік адаптерів ─────────────────────────
def vendor_of(a: dict) -> str:
    v = VENDORS.get(int(a.get("ven") or 0))
    if v:
        return v
    n = (a.get("name") or "").lower()
    return next((k for k, words in VENDOR_WORDS.items() if any(w in n for w in words)), "other")


def base_key(a: dict) -> str:
    """Стабільний між перезавантаженнями ідентифікатор моделі: VEN-DEV-SUBSYS."""
    try:
        return f"{int(a.get('ven') or 0):04X}-{int(a.get('dev') or 0):04X}-{int(a.get('sub') or 0) & 0xFFFFFFFF:08X}"
    except (TypeError, ValueError):
        return re.sub(r"\W+", "-", (a.get("name") or "gpu").lower()).strip("-")


def kind_of(a: dict) -> str:
    """igpu — вбудована графіка; mining — майнінгова карта без виходів; dgpu — дискретна."""
    import gpuinfo as GI
    import hardware as H
    if GI.headless(a):
        return "mining"
    vram_gb = (a.get("vram_mb") or 0) / 1024
    if vendor_of(a) == "intel" and not H.ARC_DGPU.search(a.get("name") or ""):
        return "igpu"
    return "igpu" if H.is_integrated(a.get("name") or "", vram_gb) else "dgpu"


def adapters(pr: dict) -> list:
    """Фізичні адаптери з переліку DXGI (gpuinfo.probe): без програмних (WARP) і віддалених."""
    import gpuinfo as GI
    disp = GI.display_adapter(pr or {})
    out, seen = [], {}
    for a in (pr or {}).get("dxgi") or []:
        if a.get("software") or vendor_of(a) == "microsoft":
            continue
        base = base_key(a)
        n = seen.get(base, 0)
        seen[base] = n + 1
        item = dict(a, key=base if n == 0 else f"{base}#{n + 1}", vendor=vendor_of(a), kind=kind_of(a))
        item["display"] = bool(disp) and disp.get("luid") == a.get("luid")
        out.append(item)
    return out


def high_performance(ads: list) -> dict:
    """Карта, яку взяв би режим «Висока продуктивність»: дискретна (чи майнінгова) з найбільшою відеопам'яттю."""
    if not ads:
        return {}
    strong = [a for a in ads if a.get("kind") in ("dgpu", "mining")]
    if strong:
        return max(strong, key=lambda a: (a.get("vram_mb") or 0, a.get("kind") == "dgpu"))
    return ads[0]


def resolve(choice: str, ads: list) -> dict:
    """Збережений вибір (AUTO або ключ карти) -> адаптер. Карти з таким ключем більше немає — як AUTO."""
    if choice and choice != AUTO:
        hit = next((a for a in ads if a.get("key") == choice), None)
        if hit:
            return hit
    return high_performance(ads)


def describe(a: dict) -> str:
    """«NVIDIA GeForce RTX 4060 Laptop GPU · дискретна · 8 ГБ»."""
    if not a:
        return ""
    parts = [a.get("name") or "GPU", tr(f"gs.kind.{a.get('kind', 'dgpu')}")]
    vr = a.get("vram_mb") or 0
    if vr >= 512:
        parts.append(tr("u.gb", v=f"{vr / 1024:.0f}") if vr >= 1536 else f"{vr} {tr('u.mb')}")
    if a.get("display"):
        parts.append(tr("gs.display"))
    return " · ".join(parts)


# ───────────────────────── як попросити потрібну карту ─────────────────────────
def exe_path() -> str:
    """exe, для якого Windows зберігає налаштування «Графіка»: OptimaX.exe (і портативний) або python(w).exe."""
    import gpubench as GB
    return GB.self_command()[0] if getattr(sys, "frozen", False) else sys.executable


def winpref(exe: str = None) -> int:
    """Поточне налаштування «Графіка» Windows для exe: 0 — вирішує Windows, 1 — енергозбереження, 2 — продуктивність."""
    exe = exe or exe_path()
    cur = E.reg_get(E.DX_PREF, exe)
    m = re.search(r"GpuPreference=(\d)", str(cur[1]) if cur else "")
    return int(m.group(1)) if m else 0


def pref_tweak(exe: str = None) -> E.Tweak:
    exe = exe or exe_path()
    t = E.Tweak(PREF_ID, "bench", [E.R(E.DX_PREF, exe, PREF_HIGH, "sz")])
    t._title = tr("gs.pref_title")
    return t


def plan(target: dict, ads: list, mesa_dir: str = "", prefer_mesa: bool = False) -> dict:
    """Як запустити процес тесту, щоб малювала target.

    -> {method: native | optimus | winpref | mesa | none, env: {...}, mesa: папка Mesa або "", key, name, vendor, luid,
        fallback: mesa | winpref | "", needs_pref: bool}
    native — монітор на цій карті (або карта одна): OpenGL і так отримає її; none — без Mesa цю карту з OpenGL не
    дістати (майнінгова карта на ПК без Optimus)."""
    res = dict(method="native", env={}, mesa="", key=(target or {}).get("key", ""), name=(target or {}).get("name", ""),
               vendor=(target or {}).get("vendor", ""), luid=(target or {}).get("luid", ""), kind=(target or {}).get("kind", ""),
               fallback="", needs_pref=False)
    if not target or len(ads) <= 1:
        return res
    has_nv = any(a.get("vendor") == "nvidia" for a in ads)
    if prefer_mesa and mesa_dir and target.get("dx12") is not False:
        res.update(method="mesa", mesa=mesa_dir)
        res["env"][MESA_VAR] = target.get("name") or ""
        return res
    if target.get("display"):
        # монітор під'єднано до цієї карти: OpenGL і так тут. На ноутбуці з Optimus прямо просимо вбудовану, щоб драйвер
        # NVIDIA не забрав процес собі за своїм профілем
        if has_nv and target.get("vendor") != "nvidia":
            res["env"][SHIM_VAR] = SHIM_IGPU
        return res
    if target.get("kind") == "mining":
        # майнінгова карта на настільному ПК: Optimus немає, OpenGL її не бачить — лише Mesa (mining.py)
        if mesa_dir:
            res.update(method="mesa", mesa=mesa_dir)
            res["env"][MESA_VAR] = target.get("name") or ""
        else:
            res["method"] = "none"
        return res
    if target.get("vendor") == "nvidia":
        res["method"] = "optimus"
        res["env"][SHIM_VAR] = SHIM_DGPU
        res["fallback"] = "mesa" if mesa_dir else "winpref"
        return res
    # AMD / Intel Arc без монітора: драйвери слухаються налаштування «Графіка» Windows
    res["method"] = "winpref"
    res["needs_pref"] = winpref() != 2
    res["fallback"] = "mesa" if mesa_dir else ""
    if has_nv:
        res["env"][SHIM_VAR] = SHIM_IGPU  # щоб Optimus не забрав процес на NVIDIA, якщо вона теж є
    return res


def child_env(p: dict, base: dict = None) -> dict:
    """Середовище процесу тесту: усе як у програми плюс змінні з плану (і без чужого SHIM_MCCOMPAT)."""
    env = dict(base if base is not None else __import__("os").environ)
    env.pop(SHIM_VAR, None)
    env.update({k: str(v) for k, v in (p or {}).get("env", {}).items() if v})
    return env


# ───────────────────────── хто справді малював ─────────────────────────
def gl_vendor(text: str) -> str:
    t = (text or "").lower()
    if any(w in t for w in SOFTWARE_GL):
        return "software"
    return next((k for k, words in VENDOR_WORDS.items() if any(w in t for w in words)), "")


def _tokens(name: str) -> set:
    return {w for w in re.findall(r"[a-z0-9]+", (name or "").lower()) if w not in STOP_WORDS}


def render_match(target: dict, vendor: str, renderer: str) -> str:
    """Чи збігається карта з GL_VENDOR / GL_RENDERER з вибраною.
    match — та сама модель; vendor — той самий виробник, а модель із рядка не видно; other — інша карта чи програмний
    рендер; "" — невідомо (немає рядків або вибору)."""
    if not target or not (target.get("name") or target.get("vendor")):
        return ""
    text = f"{vendor or ''} {renderer or ''}"
    if not text.strip():
        return ""
    m = re.search(r"d3d12 \((.+?)\)\s*$", renderer or "", re.I)  # Mesa: «D3D12 (NVIDIA GeForce GTX 1060 6GB)»
    if m:
        text = m.group(1)
        renderer = m.group(1)
    got = gl_vendor(text)
    if got == "software":
        return "other"
    want = target.get("vendor") or gl_vendor(target.get("name") or "")
    if not got or not want:
        return ""
    if got != want:
        return "other"
    tw, tr_ = _tokens(target.get("name")), _tokens(renderer)
    digits = {w for w in tw if any(c.isdigit() for c in w)}
    model = digits or tw  # «RTX 4060» -> {4060}; «Iris Xe» -> {iris, xe}
    if model and model <= tr_:
        return "match"
    if digits and {w for w in tr_ if any(c.isdigit() for c in w)} and not digits & tr_:
        return "other"  # той самий виробник, інша модель: AMD APU замість Radeon RX, Intel UHD замість Arc
    return "vendor"


def engine_share(samples: list, luid: str) -> dict:
    """Середнє 3D-навантаження процесу тесту: на вибраній карті й найбільше на інших.
    samples — [{luid: {"3d": %, ...}}] (gpuinfo.engine_split по PID процесу тесту)."""
    use = [s for s in samples or [] if s]
    if not use or not luid:
        return dict(n=0, target=0.0, other=0.0, other_luid="")
    luids = {k for s in use for k in s}
    avg = {k: sum((s.get(k) or {}).get("3d", 0.0) for s in use) / len(use) for k in luids}
    tgt = avg.get(luid, 0.0)
    others = {k: v for k, v in avg.items() if k != luid}
    ol = max(others, key=others.get) if others else ""
    return dict(n=len(use), target=round(tgt, 1), other=round(others.get(ol, 0.0), 1), other_luid=ol)


def confirm(p: dict, match: str, eng: dict, got: str = "") -> dict:
    """Висновок: confirmed — назва з OpenGL і лічильники сходяться на вибраній карті; renderer — збігається назва з
    OpenGL, лічильників немає (WDDM < 2.0); likely — той самий виробник, лічильників немає; wrong — малювала інша карта;
    unknown — даних замало."""
    out = dict(status="unknown", want=(p or {}).get("name", ""), got=got or "", method=(p or {}).get("method", ""),
               key=(p or {}).get("key", ""), target3d=(eng or {}).get("target", 0.0), other3d=(eng or {}).get("other", 0.0))
    if not p or not p.get("name"):
        return out
    eng = eng or {}
    busy = eng.get("n", 0) >= 3 and max(eng.get("target", 0.0), eng.get("other", 0.0)) >= 3.0
    eng_ok = busy and eng["target"] >= 3.0 and eng["target"] >= eng["other"]
    eng_bad = busy and eng["other"] >= 3.0 and eng["other"] > eng["target"] * 1.5
    if match == "other" or (eng_bad and match != "match"):
        out["status"] = "wrong"
    elif match == "match":
        out["status"] = "confirmed" if eng_ok else "renderer"
    elif match == "vendor":
        out["status"] = "confirmed" if eng_ok else "likely"
    elif eng_ok:
        out["status"] = "confirmed"
    return out


# ───────────────────────── вибір із налаштувань ─────────────────────────
def cached_probe() -> dict:
    """Перелік адаптерів, якщо він уже є (gpuinfo.probe кешує його на 6 годин), без запуску перевірки."""
    import features as F
    pr = F.CFG["gpu_probe"]
    return pr if isinstance(pr, dict) and pr.get("dxgi") is not None else {}


def selection(hw: dict = None, pr: dict = None, choice: str = None, prefer_mesa: bool = False) -> dict:
    """План для тесту з вибору в налаштуваннях (bench_gpu). Без переліку адаптерів — {} (як раніше: малює, хто дасть)."""
    import features as F
    pr = pr if pr is not None else cached_probe()
    ads = adapters(pr)
    if not ads:
        return {}
    choice = choice if choice is not None else (F.CFG["bench_gpu"] or AUTO)
    target = resolve(choice, ads)
    mesa = ""
    try:
        import mining as MG
        info = MG.mesa_info() if E.IS_WIN else None
        mesa = info["dir"] if info and "x64" in info.get("arch", ()) else ""
    except Exception:
        mesa = ""
    p = plan(target, ads, mesa, prefer_mesa)
    p["choice"] = choice or AUTO
    p["count"] = len(ads)
    return p
