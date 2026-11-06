"""
OptimaX — Hardware Report Center: звіт про перевірку заліза (HTML, JSON, PDF), історія звітів і порівняння двох.

Звіт збирає: залізо (процесор, відеокарти, пам'ять, плата, BIOS/UEFI, диски зі SMART, монітори, батарея), результати
тестів Hardware Center (PASS / WARN / FAIL / SKIPPED / N/A), останній GPU-тест, температури під навантаженням,
помилки й попередження, графіки, підсумковий статус, рекомендації та чи кожен тест справді йшов на цьому залізі.

Персональні дані — лише за згодою: без позначки «додати назву комп'ютера» у звіті немає ні назви ПК, ні імені
користувача, а шляхи з папкою профілю замінюються на <профіль>. Серійних номерів OptimaX не збирає взагалі.
PDF робить інтерфейс (QTextDocument + QPdfWriter з Qt, без нових залежностей) зі спрощеного HTML цього модуля.
"""
from __future__ import annotations

import html
import json
import os
import re
import time

import engine as E
import hwtests as HT
from i18n import tr

FORMAT = "optimax-hw-report"
STATUS_COLOR = {HT.PASS: "#2FB872", HT.WARN: "#E0A21F", HT.FAIL: "#E5484D", HT.SKIPPED: "#8A93A6", HT.NA: "#8A93A6"}
METRICS = (("cpu_multi", "score"), ("cpu_single", "score"), ("cpu_stress", "temp_max"), ("ram", "errors"),
           ("vram", "errors"), ("gpu", "score"), ("stress_combined", "status"), ("battery", "wear"))


def _scrub(obj, words: list):
    """Прибирає ім'я користувача, назву ПК і шлях профілю з усіх рядків звіту."""
    if isinstance(obj, str):
        for w, rep in words:
            if w:
                obj = re.sub(re.escape(w), rep, obj, flags=re.I)
        return obj
    if isinstance(obj, list):
        return [_scrub(x, words) for x in obj]
    if isinstance(obj, tuple):
        return tuple(_scrub(x, words) for x in obj)
    if isinstance(obj, dict):
        return {k: _scrub(v, words) for k, v in obj.items()}
    return obj


def privacy_words() -> list:
    home = os.path.expanduser("~")
    words = [(home, "<" + tr("rep.profile") + ">")]
    for env, rep in (("USERNAME", "<user>"), ("COMPUTERNAME", "<pc>"), ("USER", "<user>")):
        v = os.environ.get(env)
        if v and len(v) >= 3:
            words.append((v, rep))
    return words


def build(hw: dict, info: dict = None, last: dict = None, bench: list = None, inspect: dict = None,
          include_name: bool = False) -> dict:
    hw = hw or {}
    last = dict(last or {})
    if bench:
        last.setdefault("gpu", HT.gpu_bench_result(bench[-1]))
    results = {k: {kk: vv for kk, vv in v.items() if kk not in ("disks", "session")} for k, v in last.items()}
    rec = []
    for r in results.values():
        for f in r.get("findings") or []:
            if f[0] in (HT.FAIL, HT.WARN):
                t = tr(f[1], **(f[2] or {}))
                if t not in rec:
                    rec.append(t)
    main = [r["status"] for k, r in results.items() if not k.startswith(("repair_", "chkdsk"))]
    rep = dict(format=FORMAT, version=E.VERSION, created=int(time.time()),
               computer=os.environ.get("COMPUTERNAME") if include_name else None,
               hardware=dict(cpu=hw.get("cpu"), cores=hw.get("cores"), threads=hw.get("threads"),
                             gpus=[dict(name=n, vram_gb=round(v, 1), driver=d or None) for n, v, d in hw.get("gpus") or []],
                             ram_gb=round(hw.get("ram_gb") or 0, 1), ram_type=hw.get("ram_type"),
                             ram_speed=hw.get("ram_speed"), os=hw.get("os"), build=hw.get("build"),
                             vendor=hw.get("vendor"), model=hw.get("model"), laptop=hw.get("laptop"),
                             disks=[{k: d.get(k) for k in ("name", "media", "bus", "size_gb", "health", "wear", "temp")}
                                    for d in hw.get("disks") or []]),
               info={k: (info or {}).get(k) for k in ("board", "bios", "ram", "monitors", "battery")} if info else {},
               results=results, inspect=inspect or None, status=HT.worst(main) if main else HT.NA,
               recommendations=rec[:25], mock=not E.IS_WIN)
    return rep if include_name else _scrub(rep, privacy_words())


def to_json(rep: dict) -> str:
    return json.dumps(rep, ensure_ascii=False, indent=1, default=str)


def _e(v) -> str:
    return html.escape("" if v is None else str(v))


def _svg(vals, color: str = "#5B8CFF", w: int = 520, h: int = 70) -> str:
    v = [x for x in vals or [] if isinstance(x, (int, float))]
    if len(v) < 2:
        return ""
    lo, hi = min(v), max(v)
    span = (hi - lo) or 1
    pts = " ".join(f"{i * w / (len(v) - 1):.1f},{h - 4 - (x - lo) / span * (h - 8):.1f}" for i, x in enumerate(v))
    return (f'<svg width="{w}" height="{h}" viewBox="0 0 {w} {h}"><rect width="{w}" height="{h}" rx="6" fill="#F4F6FA"/>'
            f'<polyline fill="none" stroke="{color}" stroke-width="1.6" points="{pts}"/>'
            f'<text x="4" y="12" font-size="10" fill="#667">{hi:.0f}</text>'
            f'<text x="4" y="{h - 3}" font-size="10" fill="#667">{lo:.0f}</text></svg>')


def _badge(st: str) -> str:
    return (f'<span style="background:{STATUS_COLOR.get(st, "#999")};color:#fff;border-radius:8px;padding:1px 8px;'
            f'font-size:11px;font-weight:600">{_e(tr("hwc.st." + st))}</span>')


def _row_label(k) -> str:
    return tr(k) if isinstance(k, str) and "." in k and not k.startswith(" ") else str(k)


def to_html(rep: dict, for_pdf: bool = False) -> str:
    """Самодостатня сторінка (без зовнішніх файлів). for_pdf — без SVG і з простішою розміткою для QTextDocument."""
    hwd = rep.get("hardware") or {}
    created = time.strftime("%d.%m.%Y %H:%M", time.localtime(rep.get("created") or time.time()))
    out = ['<!doctype html><html><head><meta charset="utf-8"><title>OptimaX Hardware Report</title>',
           '<style>body{font-family:Segoe UI,Arial,sans-serif;color:#1d2433;margin:24px;max-width:980px}'
           'h1{font-size:22px;margin:0}h2{font-size:16px;margin:22px 0 8px}table{border-collapse:collapse;width:100%}'
           'td,th{border-bottom:1px solid #e4e8f0;padding:5px 8px;text-align:left;vertical-align:top;font-size:13px}'
           '.mute{color:#6b7385;font-size:12px}.f{margin:2px 0;font-size:13px}</style></head><body>',
           f'<h1>OptimaX Hardware Report</h1><p class="mute">{_e(created)} · OptimaX {_e(rep.get("version"))}'
           + (f' · {_e(rep["computer"])}' if rep.get("computer") else "")
           + (f' · {_e(tr("rep.mock"))}' if rep.get("mock") else "") + '</p>',
           f'<p>{_e(tr("rep.overall"))}: {_badge(rep.get("status", HT.NA))}</p>',
           f'<h2>{_e(tr("rep.hw"))}</h2><table>']
    rows = [(tr("hwc.i.cpu"), f"{hwd.get('cpu') or ''} ({hwd.get('cores')}/{hwd.get('threads')})"),
            (tr("hwc.i.gpu"), ", ".join(f"{g['name']} {g['vram_gb'] or ''} GB" + (f" · {tr('hwc.i.driver_date')} "
                                                                                    f"{g['driver']}" if g.get("driver")
                                                                                    else "")
                                        for g in hwd.get("gpus") or [])),
            (tr("hwc.i.ram"), f"{hwd.get('ram_gb')} GB {hwd.get('ram_type') or ''} {hwd.get('ram_speed') or ''}"),
            (tr("hwc.i.system"), " ".join(x for x in (hwd.get("vendor"), hwd.get("model")) if x)),
            (tr("hwc.i.os"), f"{hwd.get('os') or ''} {hwd.get('build') or ''}")]
    info = rep.get("info") or {}
    if info.get("board"):
        b = info["board"]
        rows.append((tr("hwc.i.board"), " ".join(x for x in (b.get("vendor"), b.get("model")) if x)))
    if info.get("bios"):
        b = info["bios"]
        rows.append((tr("hwc.i.bios"), " ".join(str(x) for x in (b.get("vendor"), b.get("version"), b.get("date"),
                                                                 b.get("type")) if x)))
    for d in hwd.get("disks") or []:
        rows.append((tr("hwc.i.disk"), f"{d.get('name')} · {d.get('media') or ''} · {d.get('size_gb') or '?'} GB · "
                                       f"{d.get('health') or ''}"))
    for k, v in rows:
        out.append(f"<tr><th>{_e(k)}</th><td>{_e(v)}</td></tr>")
    out.append("</table>")
    if rep.get("inspect"):
        ins = rep["inspect"]
        out.append(f'<h2>{_e(tr("hwc.sec.inspect"))}</h2><table>')
        for sid, st in (ins.get("steps") or {}).items():
            out.append(f'<tr><td>{_e(tr("insp.s." + sid))}</td><td>{_badge(st or HT.NA)}</td></tr>')
        out.append("</table>")
    out.append(f'<h2>{_e(tr("rep.tests"))}</h2>')
    for key, r in sorted((rep.get("results") or {}).items(), key=lambda kv: kv[1].get("ts") or 0, reverse=True):
        when = time.strftime("%d.%m.%Y %H:%M", time.localtime(r.get("ts") or 0))
        mock = "" if r.get("hw_tested", True) else f' · {_e(tr("hwc.mock"))}'
        out.append(f'<h3 style="font-size:14px;margin:16px 0 4px">{_e(tr("hwc.t." + key))} {_badge(r.get("status", HT.NA))}'
                   f' <span class="mute">{_e(when)}{mock}</span></h3><div class="f">{_e(r.get("summary"))}</div>')
        for f in r.get("findings") or []:
            col = {HT.FAIL: "#E5484D", HT.WARN: "#E0A21F"}.get(f[0], "#6b7385")
            out.append(f'<div class="f" style="color:{col}">• {_e(tr(f[1], **(f[2] or {})))}</div>')
        if r.get("rows"):
            out.append("<table>")
            for k, v in r["rows"]:
                out.append(f"<tr><td class='mute'>{_e(_row_label(k))}</td><td>{_e(tr('hwc.na') if v in (None, '') else v)}"
                           f"</td></tr>")
            out.append("</table>")
        if not for_pdf:
            for sk, col in (("temp", "#E0A21F"), ("gpu_temp", "#E5484D"), ("mhz", "#9B6BFF"), ("ops", "#5B8CFF"),
                            ("fps", "#5B8CFF")):
                svg = _svg((r.get("series") or {}).get(sk))
                if svg:
                    out.append(f'<div class="mute">{_e(tr("hwc.chart." + sk))}</div>{svg}')
    if rep.get("recommendations"):
        out.append(f'<h2>{_e(tr("rep.recs"))}</h2>')
        for t in rep["recommendations"]:
            out.append(f'<div class="f">• {_e(t)}</div>')
    out.append(f'<p class="mute" style="margin-top:24px">{_e(tr("rep.footer"))}</p></body></html>')
    return "".join(out)


def _metric(r: dict, key: str):
    if not r:
        return None
    return r.get(key)


def compare(a: dict, b: dict) -> list:
    """Два звіти -> [(тест, статус A, статус B, показник A, показник B, зміна %)] для тестів, що є хоч в одному."""
    ra, rb = a.get("results") or {}, b.get("results") or {}
    out = []
    keys = sorted(set(ra) | set(rb), key=lambda k: [m[0] for m in METRICS].index(k) if k in [m[0] for m in METRICS]
                  else 99)
    metric = dict(METRICS)
    for k in keys:
        x, y = ra.get(k) or {}, rb.get(k) or {}
        mk = metric.get(k)
        va, vb = (_metric(x, mk), _metric(y, mk)) if mk and mk != "status" else (None, None)
        ch = None
        if isinstance(va, (int, float)) and isinstance(vb, (int, float)) and va:
            ch = round((vb - va) / va * 100, 1)
        out.append((k, x.get("status"), y.get("status"), va, vb, ch))
    return out


def compare_html(a: dict, b: dict) -> str:
    ta = time.strftime("%d.%m.%Y %H:%M", time.localtime(a.get("created") or 0))
    tb = time.strftime("%d.%m.%Y %H:%M", time.localtime(b.get("created") or 0))
    out = ['<!doctype html><html><head><meta charset="utf-8"><title>OptimaX — compare</title><style>'
           'body{font-family:Segoe UI,Arial,sans-serif;margin:24px}td,th{border-bottom:1px solid #e4e8f0;padding:5px 8px;'
           'font-size:13px;text-align:left}table{border-collapse:collapse}</style></head><body>',
           f'<h1 style="font-size:20px">{_e(tr("rep.compare"))}</h1><table><tr><th></th><th>A · {_e(ta)}</th>'
           f'<th>B · {_e(tb)}</th><th>{_e(tr("rep.change"))}</th></tr>',
           f'<tr><td>{_e(tr("rep.overall"))}</td><td>{_badge(a.get("status", HT.NA))}</td>'
           f'<td>{_badge(b.get("status", HT.NA))}</td><td></td></tr>']
    for k, sa, sb, va, vb, ch in compare(a, b):
        val = lambda s, v: (_badge(s) if s else "—") + (f" {_e(v)}" if v is not None else "")  # noqa: E731
        out.append(f'<tr><td>{_e(tr("hwc.t." + k))}</td><td>{val(sa, va)}</td><td>{val(sb, vb)}</td>'
                   f'<td>{"" if ch is None else f"{ch:+.1f}%"}</td></tr>')
    out.append("</table></body></html>")
    return "".join(out)


def reports_dir() -> str:
    return os.path.join(E.DATA_DIR, "reports")


def save(cfg, rep: dict, fmt: str, path: str = None, pdf_writer=None) -> str:
    """fmt: html | json | pdf. pdf_writer(html, path) — з інтерфейсу (Qt). Запис у історію звітів."""
    folder = reports_dir()
    os.makedirs(folder, exist_ok=True)
    stem = time.strftime("OptimaX-report-%Y%m%d-%H%M%S", time.localtime(rep.get("created") or time.time()))
    path = path or os.path.join(folder, f"{stem}.{fmt}")
    if fmt == "json":
        with open(path, "w", encoding="utf-8") as f:
            f.write(to_json(rep))
    elif fmt == "html":
        with open(path, "w", encoding="utf-8") as f:
            f.write(to_html(rep))
    elif fmt == "pdf":
        if not pdf_writer:
            raise RuntimeError("pdf")
        pdf_writer(to_html(rep, for_pdf=True), path)
    # для історії й порівняння завжди лишаємо JSON поруч
    js = os.path.splitext(path)[0] + ".json"
    if fmt != "json":
        with open(js, "w", encoding="utf-8") as f:
            f.write(to_json(rep))
    hist = [h for h in cfg["hwc_reports"] or [] if h.get("json") != js]
    hist.append(dict(json=js, path=path, ts=rep.get("created"), status=rep.get("status"), fmt=fmt))
    cfg["hwc_reports"] = hist[-30:]
    return path


def load(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        rep = json.load(f)
    if rep.get("format") != FORMAT:
        raise ValueError("not an OptimaX hardware report")
    return rep
