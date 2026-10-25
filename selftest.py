"""
OptimaX — самоперевірка збірки. Нічого не змінює в системі.

    OptimaX.exe --selftest=report.json              — модулі, переклади, твіки, залізо, Rescue, A/B, фільтр
    OptimaX.exe --selftest=report.json --selftest-ui — те саме + головне вікно: усі розділи, картка результату

Поруч зі звітом JSON з'являється report.md (короткий підсумок) і, з --selftest-ui, знімки розділів.
Код виходу 0 — усе гаразд, 1 — є помилки. Цим режимом CI перевіряє зібраний OptimaX.exe і інсталятор.
Програма запускається з тимчасовою папкою налаштувань і в режимі перегляду (див. optimizer.py).
"""
from __future__ import annotations

import importlib
import json
import os
import platform
import re
import string
import sys
import time
import traceback

MODULES = ("engine", "features", "guard", "hardware", "hwnative", "hotkeys", "lifecycle", "monitor", "power", "report",
           "updater", "apps", "netlab", "fpstest", "benchtools", "adblock", "rescue", "abtest", "i18n",
           "lang_ui", "lang_engine", "lang_tweaks", "lang_extra", "lang_setup", "lang_lab", "lang_safe",
           "gpubench", "ui_kit", "pages_optimize", "pages_tools", "pages_extra", "pages_lab", "smart_ui",
           "sharecard")
UI_TIMEOUT = 120  # секунд на визначення заліза у вікні
_PROGRESS = None  # <звіт>-progress.txt: що робилося перед аварійним завершенням
_CRASH = None     # <звіт>-crash.txt: стек Python у момент нативного збою (faulthandler)


def mark(text: str) -> None:
    """Рядок у журнал ходу перевірки — одразу на диск, щоб пережити аварійне завершення процесу."""
    if not _PROGRESS:
        return
    try:
        with open(_PROGRESS, "a", encoding="utf-8") as f:
            f.write(f"{time.strftime('%H:%M:%S')} {text}\n")
            f.flush()
            os.fsync(f.fileno())
    except OSError:
        pass


def wanted(argv) -> bool:
    return any(a == "--selftest" or a.startswith("--selftest=") for a in argv)


def prepare(argv) -> None:
    """Викликається до імпорту engine: тимчасові налаштування й режим перегляду."""
    import tempfile
    if "--selftest-keep-data" not in argv:
        os.environ["APPDATA"] = tempfile.mkdtemp(prefix="optimax-selftest-")
    if "--dry-run" not in argv:
        argv.append("--dry-run")
    os.environ.setdefault("OPTIMAX_BENCH_FAST", "1")


def _report_path(argv) -> str:
    for a in argv:
        if a.startswith("--selftest="):
            return os.path.abspath(a.split("=", 1)[1])
    return os.path.abspath("optimax-selftest.json")


class Result:
    def __init__(self):
        self.checks = []

    def run(self, name, fn, *a):
        t0 = time.perf_counter()
        mark(f"start {name}")
        item = {"name": name, "ok": False}
        try:
            info = fn(*a)
            item["ok"] = True
            if info is not None:
                item["info"] = info
        except Skip as e:
            item.update(ok=True, skipped=str(e))
        except Exception as e:
            item["error"] = f"{type(e).__name__}: {e}"
            item["trace"] = traceback.format_exc()[-3000:]
        item["ms"] = round((time.perf_counter() - t0) * 1000)
        mark(f"end {name}: {'ok' if item['ok'] else 'FAIL ' + str(item.get('error'))[:300]}")
        self.checks.append(item)
        _say(("  ok   " if item["ok"] else "  FAIL ") + name + (f" — {item.get('error')}" if not item["ok"] else ""))
        return item["ok"]


class Skip(Exception):
    pass


def _say(s: str) -> None:
    try:
        if sys.stdout:
            print(s, flush=True)
    except Exception:
        pass


# ───────────────────────── перевірки без вікна ─────────────────────────
def check_modules():
    bad = {}
    for m in MODULES:
        try:
            importlib.import_module(m)
        except Exception as e:
            bad[m] = f"{type(e).__name__}: {e}"
    if bad:
        raise AssertionError(json.dumps(bad, ensure_ascii=False))
    return {"count": len(MODULES)}


def _placeholders(s: str) -> set:
    return {f for _, f, _, _ in string.Formatter().parse(s) if f is not None}


def check_i18n():
    import i18n
    problems = []
    for k, v in i18n.STR.items():
        if not isinstance(v, tuple) or len(v) != 3:
            problems.append(f"{k}: not (uk, ru, en)")
            continue
        filled = [x for x in v if x]
        if not filled:
            continue  # навмисно порожній рядок (наприклад, опис «усе гаразд»)
        if len(filled) < 3:
            problems.append(f"{k}: missing " + ",".join(c for c, x in zip(("uk", "ru", "en"), v) if not x))
        try:
            sets = [_placeholders(x) for x in filled]
        except ValueError as e:
            problems.append(f"{k}: bad format ({e})")
            continue
        if any(s != sets[0] for s in sets):
            problems.append(f"{k}: placeholders differ {sets}")
    if problems:
        raise AssertionError("; ".join(problems[:25]))
    return {"keys": len(i18n.STR), "tweak_texts": len(i18n.TWEAK_TEXT)}


def check_tweaks(hw):
    import engine as E
    import i18n
    ids, errors, applied, states = set(), [], 0, {}
    for t in E.TWEAKS:
        if t.id in ids:
            errors.append(f"duplicate id {t.id}")
        ids.add(t.id)
        if not t._title:
            v = i18n.TWEAK_TEXT.get(t.id)
            if not v or len(v) != 6 or not all(v[i] for i in (0, 2, 4)):
                errors.append(f"{t.id}: no title in every language")
        try:
            E.describe_ops(t)
            st, _ = E.compat(t, hw or {})
            states[st] = states.get(st, 0) + 1
            applied += bool(E.probe(t))
        except Exception as e:
            errors.append(f"{t.id}: {type(e).__name__}: {e}")
    if errors:
        raise AssertionError("; ".join(errors[:25]))
    return {"tweaks": len(E.TWEAKS), "already_applied": applied, "compat": states}


def check_hardware(store):
    import hardware as H
    t0 = time.time()
    hw = H.detect_hw()
    an = H.analyze(hw)
    checks = H.build_check(hw, [])
    store["hw"] = hw
    if not hw.get("cpu"):
        raise AssertionError("CPU not detected")
    res = {"cpu": hw.get("cpu"), "cores": hw.get("cores"), "threads": hw.get("threads"), "sockets": hw.get("sockets"),
           "mhz": hw.get("mhz"), "gpus": [list(g) for g in hw.get("gpus") or []], "ram_gb": round(hw.get("ram_gb") or 0, 2),
           "ram": [hw.get("ram_type"), hw.get("ram_speed"), hw.get("ram_max_speed"), hw.get("ram_modules")],
           "disk": [hw.get("disk_type"), hw.get("disk_bus"), hw.get("disk_name")],
           "disks": [[d.get("id"), d.get("name"), d.get("media"), d.get("bus"), d.get("size_gb"), d.get("letters")]
                     for d in hw.get("disks") or []],
           "os": hw.get("os"), "build": hw.get("build"), "vendor": [hw.get("vendor"), hw.get("model")],
           "device": hw.get("device"), "sources": hw.get("sources"),
           "recommended": len(an.get("recommended") or []), "checks": len(checks),
           "seconds": round(time.time() - t0, 1)}
    unknown = H.tr("hw.unknown")
    if hw.get("sources") is not None:  # справжня Windows, не демо
        import hwnative as HN
        nat = HN.collect()
        res["native"] = {k: (v if k != "gpus" else [[g.get("name"), round(g.get("vram") or 0, 2)] for g in v])
                         for k, v in nat.items() if k != "disks"}
        res["native_disks"] = [[d["id"], d["name"], d["media"], d["bus"], d["size_gb"], d["letters"]]
                               for d in nat.get("disks") or []]
        if hw["cpu"] == unknown or not hw.get("cores") or not hw.get("ram_gb"):
            raise AssertionError(f"hardware not detected: {res}")
        if not nat.get("cpu") or not nat.get("threads"):
            raise AssertionError(f"native CPU detection failed: {nat.get('errors')}")
    return res


def check_rescue():
    import engine as E
    import rescue as RS
    import tempfile
    j = E.Journal(os.path.join(tempfile.mkdtemp(prefix="oxst_"), "journal.json"))
    now = int(time.time())
    j.data["applied"] = {
        "a": {"ts": now - 7200, "undo": [{"t": "svc", "n": "SysMain", "old": "auto"}], "title": "Old & <new> 100%"},
        "b": {"ts": now - 10, "undo": [
            {"t": "reg", "p": r"HKCU\Software\OptimaX-Selftest", "n": "Dw", "old": [4, 1]},
            {"t": "reg", "p": r"HKCU\Software\OptimaX-Selftest", "n": "", "old": None},
            {"t": "reg", "p": r"HKCU\Software\OptimaX-Selftest", "n": "Bin", "old": [3, {"hex": "00ff"}]},
            {"t": "reg", "p": r"HKCU\Software\OptimaX-Selftest", "n": "Multi", "old": [7, ["a", "b c"]]},
            {"t": "task", "n": r"\Microsoft\Windows\Feedback\Siuf\DmClient"},
            {"t": "pw", "g": "381b4222-f694-41f0-9685-ff5bb260df2e", "s": "SUB_PROCESSOR", "st": "CPMINCORES",
             "old": 10, "m": "ac"},
            {"t": "ps", "c": "Write-Output 'x'"},
            {"t": "live", "k": "explorer"}]},
    }
    s = RS.build_script(j)
    lone = s.count("\n") - s.count("\r\n")
    calls = set(re.findall(r"call :(x\d+)", s))
    labels = set(re.findall(r"^:(x\d+)\r?$", s, re.M))
    if lone or not calls or not calls <= labels or "chcp 65001" not in s:
        raise AssertionError(f"lone LF {lone}, calls {sorted(calls)}, labels {sorted(labels)}")
    if len(RS.batches(j)) != 2:
        raise AssertionError(f"batches {RS.batches(j)}")
    return {"bytes": len(s.encode("utf-8")), "subroutines": len(labels)}


def check_abtest():
    import random
    import abtest as AB
    rnd = random.Random(7)
    live = [f"t{i}" for i in range(16)]
    s = AB.Session(live, [], [], mode="new")
    on = set()
    for _ in range(300):
        a = s.next()
        if a["do"] == "done":
            break
        if a["do"] == "measure":
            f = 1.0
            for t in on:
                f *= 0.93 if t == "t11" else 1.004
            f *= 1 + rnd.uniform(-0.004, 0.004)
            s.feed({"avg": 200 * f, "low1": 160 * f})
        elif a["do"] == "apply":
            on |= set(a["ids"])
            s.ok(applied=sorted(on))
        elif a["do"] == "undo":
            on -= set(a["ids"])
            s.ok()
        else:
            s.ok()
    sm = s.summary()
    if sm["result"] != "fixed" or sm["removed"] != ["t11"]:
        raise AssertionError(f"{sm['result']} removed={sm['removed']}")
    return {"measures": sm["measures"], "delta": sm["delta"]}


def check_adblock():
    import adblock as AB
    e1, w1 = AB.parse_list("0.0.0.0 ads.example.com\n127.0.0.1 tracker.test # c\n0.0.0.0 localhost\n", "hosts")
    e2, w2 = AB.parse_list("||adserver.test^\n@@||good.test^\n", "adblock")
    if e1 != {"ads.example.com", "tracker.test"} or w2 != {"adserver.test"}:
        raise AssertionError(f"parse {e1} {w2}")
    return {"lists": len(AB.LISTS)}


def check_buildinfo():
    import engine as E
    import updater as U
    info = {"version": E.VERSION, "update_repo": U.UPDATE_REPO or None, "frozen": bool(getattr(sys, "frozen", False))}
    try:
        import buildinfo
        info.update(build=getattr(buildinfo, "BUILD", None), built=getattr(buildinfo, "BUILT", None))
    except ImportError:
        pass
    return info


# ───────────────────────── перевірка вікна ─────────────────────────
def check_ui(factory, out_dir, store):
    """Головне вікно в режимі перегляду: визначення заліза, кожен розділ, картка результату."""
    from PyQt6.QtWidgets import QApplication, QDialog, QFileDialog
    import engine as E
    import lifecycle as L
    import updater as U
    for a in sys.argv:
        if a.startswith("--selftest-platform="):  # напр. offscreen — щоб відокремити збої вікон Windows
            os.environ["QT_QPA_PLATFORM"] = a.split("=", 1)[1]
    mark(f"ui: platform {os.environ.get('QT_QPA_PLATFORM') or 'default'}")
    Main, apply_theme = factory()
    errors = []
    old_hook = sys.excepthook
    sys.excepthook = lambda tp, v, tb: errors.append("".join(traceback.format_exception(tp, v, tb))[-1500:])
    L.start_server = lambda *a, **k: None  # не перехоплювати вікно справжньої копії OptimaX
    U.UPDATE_REPO = ""
    app = QApplication.instance()
    if not isinstance(app, QApplication):
        mark("ui: QApplication")
        app = QApplication(sys.argv)
    mark(f"ui: theme ({app.platformName()})")
    apply_theme(app)
    shown = []

    def fake_exec(dlg, *a):
        shown.append(type(dlg).__name__)
        dlg.show()
        for _ in range(10):
            app.processEvents()
            time.sleep(0.01)
        _grab(dlg, os.path.join(out_dir, f"dialog-{len(shown):02d}-{type(dlg).__name__}.png"))
        dlg.hide()
        return 0
    QDialog.exec = fake_exec
    QFileDialog.getSaveFileName = staticmethod(lambda *a, **k: ("", ""))
    QFileDialog.getOpenFileName = staticmethod(lambda *a, **k: ("", ""))
    QFileDialog.getExistingDirectory = staticmethod(lambda *a, **k: "")
    toasts = []
    try:
        # голе вікно Qt без коду OptimaX: якщо падіння тут — винна збірка/середовище, а не програма
        from PyQt6.QtWidgets import QWidget
        mark("ui: native probe")
        probe = QWidget()
        int(probe.winId())
        probe.show()
        app.processEvents()
        probe.close()
        probe.deleteLater()
        mark("ui: Main()")
        w = Main()
        mark("ui: show")
        w._toast.show_msg = lambda text, kind="ok", area=None: toasts.append([kind, text])
        w.show()
        deadline = time.time() + UI_TIMEOUT
        while w.hw is None and time.time() < deadline:
            app.processEvents()
            time.sleep(0.02)
        if w.hw is None:
            raise AssertionError(f"hardware detection did not finish in {UI_TIMEOUT}s")
        pages = []
        for key in list(w.nav_keys):
            mark(f"ui: page {key}")
            w.go(key)
            for _ in range(15):
                app.processEvents()
                time.sleep(0.01)
            _grab(w, os.path.join(out_dir, f"page-{len(pages):02d}-{key}.png"))
            pages.append(key)
        import sharecard as SC
        mark("ui: share card")
        card = SC.render(SC.collect(w), 1.0)
        card.save(os.path.join(out_dir, "share-card.png"))
        mark("ui: share dialog")
        w.share_result()
        bad = [t for k, t in toasts if k == "bad"]
        raw = [t for _, t in toasts if re.fullmatch(r"[a-z0-9_]+(\.[a-z0-9_]+)+", t or "")]
        mark("ui: quit")
        w.quit_app()
        for _ in range(20):
            app.processEvents()
            time.sleep(0.01)
    finally:
        sys.excepthook = old_hook
    if errors or bad or raw:
        raise AssertionError(json.dumps({"exceptions": errors[:5], "bad_toasts": bad, "raw_keys": raw},
                                        ensure_ascii=False))
    return {"pages": pages, "dialogs": shown, "toasts": len(toasts), "platform": app.platformName(),
            "card": [card.width(), card.height()], "dry_run": E.DRY_RUN}


def _grab(widget, path) -> None:
    try:
        widget.grab().save(path)
    except Exception:
        pass


# ───────────────────────── звіт ─────────────────────────
def main(argv, ui_factory=None) -> int:
    global _PROGRESS, _CRASH
    path = _report_path(argv)
    out_dir = os.path.splitext(path)[0] + "-shots"
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    base = os.path.splitext(path)[0]
    _PROGRESS = base + "-progress.txt"
    for f in (_PROGRESS, base + "-crash.txt", path):
        try:
            os.remove(f)
        except OSError:
            pass
    try:  # нативний збій (access violation тощо) — стек Python у файл; файл має лишатися відкритим
        import faulthandler
        _CRASH = open(base + "-crash.txt", "w", encoding="utf-8")
        faulthandler.enable(file=_CRASH, all_threads=True)
    except Exception:
        _CRASH = None
    mark(f"selftest {' '.join(a for a in argv[1:] if a.startswith('--'))}")
    t0 = time.time()
    res = Result()
    store = {}
    _say(f"OptimaX selftest -> {path}")
    if res.run("modules", check_modules):
        res.run("i18n", check_i18n)
        res.run("hardware", check_hardware, store)
        res.run("tweaks", check_tweaks, store.get("hw"))
        res.run("rescue", check_rescue)
        res.run("abtest", check_abtest)
        res.run("adblock", check_adblock)
        res.run("buildinfo", check_buildinfo)
        if "--selftest-ui" in argv and ui_factory:
            os.makedirs(out_dir, exist_ok=True)
            res.run("ui", check_ui, ui_factory, out_dir, store)
    import engine as E
    ok = all(c["ok"] for c in res.checks)
    try:
        from PyQt6.QtCore import QT_VERSION_STR, PYQT_VERSION_STR
        qt = f"Qt {QT_VERSION_STR} / PyQt {PYQT_VERSION_STR}"
    except Exception:
        qt = None
    rep = {"ok": ok, "version": E.VERSION, "platform": platform.platform(), "python": sys.version.split()[0],
           "qt": qt, "frozen": bool(getattr(sys, "frozen", False)), "dry_run": E.DRY_RUN,
           "seconds": round(time.time() - t0, 1), "checks": res.checks}
    with open(path, "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=str)
    lines = [f"### OptimaX {E.VERSION} selftest: {'passed' if ok else 'FAILED'}", "",
             f"{rep['platform']} · Python {rep['python']} · {qt or 'no Qt'} · "
             f"{'frozen exe' if rep['frozen'] else 'source'} · {rep['seconds']} s", "",
             "| check | result | time | details |", "|---|---|---|---|"]
    for c in res.checks:
        state = "skipped" if c.get("skipped") else "ok" if c["ok"] else "**FAIL**"
        det = c.get("error") or c.get("skipped") or json.dumps(c.get("info", ""), ensure_ascii=False, default=str)
        lines.append(f"| {c['name']} | {state} | {c['ms']} ms | {det[:300].replace('|', '/')} |")
    with open(os.path.splitext(path)[0] + ".md", "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    _say("selftest " + ("passed" if ok else "FAILED"))
    return 0 if ok else 1
