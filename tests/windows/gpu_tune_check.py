"""
Перевірка «Кулерів і андервольту» на справжній відеокарті — для тестерів із картами NVIDIA й AMD.

    python tests\\windows\\gpu_tune_check.py               — лише читає: що вміє карта, датчики (нічого не змінює)
    python tests\\windows\\gpu_tune_check.py --change      — ще й кожну зміну окремо: застосувати → перечитати з
                                                             драйвера → повернути заводське → перечитати

Запускати від імені адміністратора. Зміни малі й короткі (вентилятор 60 % на 6 с, потужність −10 %, зсув +15 МГц,
напруга −5 мВ), кожна повертається одразу, а наприкінці — ще раз усе заводське (і при Ctrl+C чи помилці). Звіт —
gpu_tune_report.json і gpu_tune_report.md поруч зі скриптом або в --out; його й треба надіслати розробникам.
Справжній журнал OptimaX скрипт не чіпає (тимчасова папка налаштувань і журнал у ній).
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxgtc_")  # налаштування OptimaX — тимчасові
sys.path.insert(0, ROOT)

import engine as E  # noqa: E402
import gputune as GT  # noqa: E402

E.JOURNAL = E.Journal(os.path.join(os.environ["APPDATA"], "back.json"))  # не справжній журнал OptimaX


class Cfg(dict):
    def __getitem__(self, k):
        return self.get(k)


def check(rep: dict, name: str, fn) -> None:
    t0 = time.time()
    try:
        ok, detail = fn()
    except Exception as e:  # noqa: BLE001 — у звіт, а не падіння
        ok, detail = False, f"{type(e).__name__}: {e}\n{traceback.format_exc(limit=3)}"
    rep["checks"].append(dict(name=name, ok=bool(ok), detail=detail, s=round(time.time() - t0, 1)))
    print(f"  [{'OK' if ok else 'FAIL'}] {name}: {detail}")


def main(argv) -> int:
    change = "--change" in argv
    out = next((a.split("=", 1)[1] for a in argv if a.startswith("--out=")), HERE)
    rep = dict(ts=time.strftime("%Y-%m-%d %H:%M:%S"), version=E.VERSION, admin=E.is_admin(), change=change,
               checks=[], caps={}, why={}, reads=[])
    t = GT.open_tuner("")
    rep.update(gpu=t.name, vendor=t.vendor, caps=t.caps, why=t.why, error=t.last_error)
    print(f"GPU: {t.name or '—'} ({t.vendor or '—'}), admin={rep['admin']}")
    for k, have, why in GT.describe_caps(t):
        print(f"  {'+' if have else '-'} {k}: {why}")
    if not t.ok():
        _write(rep, out)
        return 2
    for _ in range(3):
        rep["reads"].append(t.read())
        time.sleep(1)
    print(f"  sensors: {rep['reads'][-1]}")
    if not change:
        _write(rep, out)
        return 0
    if not rep["admin"]:
        print("  --change needs administrator rights")
        _write(rep, out)
        return 3
    cfg = Cfg(gpu_tune={"profile": None, "orig": {}, "active": False, "on_start": False})
    orig = GT.remember_original(cfg, t)
    rep["orig"] = orig
    try:
        if "fan" in t.caps and t.caps["fan"].get("mode") == "manual":
            def fan():
                ok = t.fan_set(60)
                time.sleep(6)
                r = t.read()
                back = t.fan_auto()
                time.sleep(4)
                r2 = t.read()
                return ok and back and abs((r.get("fan") or 0) - 60) <= 8 and r2.get("fan_auto", True), \
                    f"60% -> {r.get('fan')}%, auto={r2.get('fan_auto')} ({r2.get('fan')}%)"
            check(rep, "fan manual 60% then auto", fan)
        if "fan" in t.caps and t.caps["fan"].get("mode") == "native":
            def curve():
                before = t._fan_states()
                ok = t.fan_curve_native(GT.CURVE_PRESETS["cool"])
                mid = t._fan_states()
                back = t.restore(dict(fan=before))
                after = t._fan_states()
                return ok and back and after == before and mid != before, f"{before} -> {mid} -> {after}"
            check(rep, "AMD fan curve then factory", curve)
        if "power" in t.caps:
            p = t.caps["power"]

            def power():
                cur = t.read().get("power_limit")
                want = max(p["min"], round(cur * 0.9)) if p["unit"] == "W" else max(p["min"], (cur or 0) - 5)
                ok = t.power_set(want)
                got = t.read().get("power_limit")
                back = t.power_set(cur)
                return ok and back and got == want and t.read().get("power_limit") == cur, f"{cur} -> {got} -> {cur}"
            check(rep, "power limit -10% then back", power)
        if "clock" in t.caps:
            def cap():
                ok = t.clock_cap(t.caps["clock"]["max"] - 300)
                back = t.clock_cap(None)
                return ok and back, f"cap {t.caps['clock']['max'] - 300} MHz, reset={back} ({t.last_error})"
            check(rep, "clock cap then reset", cap)
        if "offset" in t.caps:
            def offset():
                cur = t.read().get("offset") or 0
                ok = t.offset_set(cur + 15)
                got = t.read().get("offset")
                back = t.offset_set(cur)
                return ok and back and got == cur + 15, f"{cur} -> {got} -> {t.read().get('offset')} ({t.last_error})"
            check(rep, "clock offset +15 MHz then back", offset)
        if "voltage" in t.caps:
            def volt():
                cur = t.read().get("voltage_set")
                ok = t.voltage_set(cur - 5)
                got = t.read().get("voltage_set")
                back = t.voltage_set(cur)
                return ok and back and got == cur - 5, f"{cur} -> {got} -> {t.read().get('voltage_set')}"
            check(rep, "voltage -5 mV then back", volt)
    finally:
        check(rep, "factory values restored", lambda: (GT.restore_original(cfg, t), str(t.snapshot())))
        t.close()
    _write(rep, out)
    return 0 if all(c["ok"] for c in rep["checks"]) else 1


def _write(rep: dict, out: str) -> None:
    os.makedirs(out, exist_ok=True)
    with open(os.path.join(out, "gpu_tune_report.json"), "w", encoding="utf-8") as f:
        json.dump(rep, f, ensure_ascii=False, indent=1, default=str)
    lines = [f"# GPU tune check — {rep.get('gpu') or 'no GPU'}", "",
             f"OptimaX {rep['version']}, {rep['ts']}, vendor {rep.get('vendor') or '—'}, admin {rep['admin']}", "",
             "| Feature | Supported | Why not |", "| --- | --- | --- |"]
    for k in ("fan", "power", "clock", "maxfreq", "offset", "voltage"):
        lines.append(f"| {k} | {'yes' if k in rep.get('caps', {}) else 'no'} | {rep.get('why', {}).get(k, '')} |")
    if rep["checks"]:
        lines += ["", "| Check | Result | Detail |", "| --- | --- | --- |"]
        lines += [f"| {c['name']} | {'OK' if c['ok'] else 'FAIL'} | {str(c['detail'])[:160]} |" for c in rep["checks"]]
    with open(os.path.join(out, "gpu_tune_report.md"), "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    print(f"report: {os.path.join(out, 'gpu_tune_report.md')}")


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
