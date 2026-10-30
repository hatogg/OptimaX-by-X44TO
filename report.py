"""
OptimaX — звіт для форуму або майстра: залізо, перевірка збірки, застосовані зміни, остання діагностика,
тести FPS і мережі. Два формати: HTML-файл і короткий текст для чату.
"""
from __future__ import annotations

import html
import ntpath
import time
from datetime import datetime

import engine as E
import features as F
import hardware as H
from i18n import tr


def _exe_name(path) -> str:
    """Лише ім'я файлу гри: повний шлях може містити ім'я користувача Windows (C:\\Users\\<ім'я>\\…)."""
    return ntpath.basename(str(path)) if path else ""


def gpus_line(hw):
    """«NVIDIA GeForce RTX 4070 (12 GB), Intel UHD Graphics» — обсяг лише для дискретних відеокарт."""
    return ", ".join(f"{n} ({H.fmt_gb(vr)} GB)" if vr >= 0.95 and not H.is_integrated(n, vr) else n
                     for n, vr, _ in hw.get("gpus", []))



def sections(hw: dict, checks: list, analysis: dict) -> list:
    """-> [(заголовок, [(ключ, значення)] | [рядки])]"""
    hw = hw or {}
    cpu = hw.get("cpu", "?")
    if (hw.get("sockets") or 1) > 1:
        cpu = f"{hw['sockets']} × {cpu}"
    if hw.get("cores"):
        cpu += f" ({H.cpu_sub(hw)})"
    spec = [(tr("hw.cpu"), cpu), (tr("hw.gpu"), gpus_line(hw) or "?"),
            (tr("hw.ram"), H.ram_line(hw) + (f", {hw['ram_modules']}×" if hw.get("ram_modules") else "")),
            (tr("hw.disk"), "; ".join(f"{d['name']} ({d['media']}, {d.get('size_gb', '?')} GB"
                                      + (f", {tr('rep.wear')} {d['wear']}%" if d.get("wear") is not None else "")
                                      + ")" for d in hw.get("disks") or []) or hw.get("disk_name", "?")),
            (tr("hw.display"), tr("hw.hz", hz=(hw.get("refresh") or (0, 0))[0]) if (hw.get("refresh") or (0, 0))[0]
             else "—"),
            (tr("hw.os"), f"{hw.get('os', '')}" + (f" ({hw['build']})" if hw.get("build") else "")),
            (tr("rep.vendor"), " ".join(x for x in (hw.get("vendor"), hw.get("model")) if x) or "—")]
    out = [(tr("rep.spec"), spec)]
    if analysis:
        out.append((tr("rep.analysis"), [(tr("home.opt_level"), f"{analysis['opt']}%"),
                                         (tr("home.privacy_level"), f"{analysis['privacy']}%"),
                                         (tr("home.bottleneck"), tr(f"neck.{analysis['neck']}"))]))
    mark = {"warn": "⚠", "info": "•", "ok": "✓"}
    out.append((tr("home.build_check"), [f"{mark[c['level']]} {c['title']}" for c in
                                         sorted(checks or [], key=lambda c: {"warn": 0, "info": 1, "ok": 2}[c["level"]])]))
    applied = [E.entry_title(t) for t in E.JOURNAL.newest_first()]
    out.append((tr("rep.applied", n=len(applied)), applied or [tr("rep.none")]))
    d = F.CFG["diag_last"]
    if d:
        lines = [f"{tr('rep.game')}: {_exe_name(d.get('game')) or '—'}"]
        lines += [tr(f"diag.f.{x['key']}.t", **x.get("kw", {})) for x in d.get("findings", [])]
        out.append((tr("rep.diag"), lines))
    pr = F.CFG["gpu_probe"]
    profs = (F.CFG["mining"] or {}).get("profiles") or {}
    if isinstance(pr, dict) and (pr.get("dxgi") or profs):  # Universal GPU Renderer: що бачать API й режими ігор
        import gpuinfo as GI
        s = GI.summary(pr)
        lines = [tr("rep.gpu_probe", gpu=s.get("gpu") or "—", driver=s.get("driver") or "?",
                    dx12=tr("gr.yes") if s.get("dx12") else tr("gr.no"), vk=s.get("vk_api") or tr("gr.no"),
                    display=s.get("display") or "—")]
        for p in list(profs.values())[:20]:
            last = (p.get("checks") or [{}])[-1]
            lines.append(tr("rep.gpu_game", game=p.get("name") or "?", mode=tr(f"mg.mode.{p.get('mode') or 'native'}"),
                            verdict=tr(f"diag.render.{last['verdict']}") if last.get("verdict") in
                            ("mining", "igpu", "warp") else "—"))
        out.append((tr("rep.gpu"), lines))
    tests = F.CFG["fps_tests"] or {}
    if tests:
        lines = []
        for exe, t in tests.items():
            for k in ("before", "after"):
                r = t.get(k)
                if r:
                    lines.append(f"{_exe_name(exe)} — {tr('fps.' + k)}: {r['avg']} FPS, 1% low {r['low1']}, "
                                 f"0.1% low {r['low01']}, {tr('fps.stutters')}: {r['stutters']}")
        out.append((tr("rep.fps"), lines))
    net = F.CFG["net"] or {}
    if net.get("dns") or net.get("bb"):
        lines = []
        if net.get("dns"):
            best = net["dns"][0]
            lines.append(tr("rep.dns_best", name=best["name"], ms=best.get("ms")))
        if net.get("bb"):
            b = net["bb"]
            lines.append(tr("rep.bb", grade=b["grade"], idle=b["idle"], loaded=b["loaded"]))
        out.append((tr("nav.network"), lines))
    return out


def to_text(secs) -> str:
    lines = [f"{E.APP_TITLE} {E.VERSION} — {tr('rep.title')} ({datetime.now():%d.%m.%Y %H:%M})", ""]
    for title, rows in secs:
        lines.append(f"■ {title}")
        for r in rows:
            lines.append(f"  {r[0]}: {r[1]}" if isinstance(r, tuple) else f"  {r}")
        lines.append("")
    return "\n".join(lines).strip() + "\n"


CSS = """body{font:14px/1.5 'Segoe UI',system-ui,sans-serif;background:#0A0C11;color:#ECEFF4;margin:0;padding:32px}
main{max-width:900px;margin:auto}h1{font-size:24px;margin:0 0 4px}.sub{color:#9AA3B5;margin-bottom:24px}
section{background:#12161E;border:1px solid #202734;border-radius:14px;padding:18px 22px;margin-bottom:14px}
h2{font-size:16px;margin:0 0 10px}table{border-collapse:collapse;width:100%}td{padding:4px 0;vertical-align:top}
td:first-child{color:#9AA3B5;width:220px}li{margin:2px 0}ul{margin:0;padding-left:18px}
@media print{body{background:#fff;color:#000}section{background:#fff;border-color:#ccc}}"""


def to_html(secs) -> str:
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><title>{html.escape(tr('rep.title'))}</title>"
             f"<style>{CSS}</style></head><body><main><h1>{html.escape(E.APP_TITLE)} — {html.escape(tr('rep.title'))}"
             f"</h1><div class='sub'>{datetime.now():%d.%m.%Y %H:%M} · {E.APP_NAME} {E.VERSION}</div>"]
    for title, rows in secs:
        parts.append(f"<section><h2>{html.escape(title)}</h2>")
        if rows and isinstance(rows[0], tuple):
            parts.append("<table>" + "".join(f"<tr><td>{html.escape(str(k))}</td><td>{html.escape(str(v))}</td></tr>"
                                             for k, v in rows) + "</table>")
        else:
            parts.append("<ul>" + "".join(f"<li>{html.escape(str(r))}</li>" for r in rows) + "</ul>")
        parts.append("</section>")
    parts.append("</main></body></html>")
    return "".join(parts)


def default_name() -> str:
    return f"OptimaX-report-{time.strftime('%Y%m%d-%H%M')}.html"
