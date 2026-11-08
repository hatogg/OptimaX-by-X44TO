"""
OptimaX — збирання сайту для GitHub Pages: окрема статична сторінка для кожної мови.

Чому так. site/index.html малює текст скриптом і вибирає мову за navigator.language. Пошуковий робот
(Googlebot — en-US) бачив або порожні заголовки, або англійський текст під <html lang="uk"> і українським
описом, тож українською сайт майже не знаходився. Тут той самий словник T зі сторінки розбирається
на етапі збирання, і кожна мова отримує готову сторінку з текстом у HTML:

  index.html — українська (канонічна, x-default)
  en.html    — англійська

Плюс для пошуку: власні <title> і опис для кожної мови, canonical, hreflang, Open Graph і Twitter,
структуровані дані schema.org (SoftwareApplication) і sitemap.xml. Скрипт на сторінці лишається: на
зібраній сторінці мову задає адреса, а кнопки UA/EN переходять на сторінку іншої мови.

Запуск: python tools/build_site.py <тека-джерела> <тека-сайту>   (у .github/workflows/pages.yml)
"""
from __future__ import annotations

import datetime
import html
import json
import os
import re
import sys

BASE = "https://hatogg.github.io/OptimaX-by-X44TO/"
REPO = "https://github.com/hatogg/OptimaX-by-X44TO"

LANGS = {
    "uk": dict(
        file="index.html", url=BASE, locale="uk_UA", image="social-preview-uk.png", nav="Розділи",
        title="OptimaX — безкоштовний оптимізатор Windows 10 і 11 для ігор",
        desc="Безкоштовний оптимізатор Windows 10 і 11 для ігор: план під ваше залізо, тест FPS до і після, "
             "FPS-оверлей і повний відкат. Відкритий код, українською."),
    "en": dict(
        file="en.html", url=BASE + "en.html", locale="en_US", image="social-preview-en.png", nav="Sections",
        title="OptimaX — free Windows 10 & 11 optimizer for gaming",
        desc="Free, open-source Windows 10 and 11 optimizer for gaming: a plan for your hardware, before/after "
             "FPS tests, an FPS overlay and full rollback."),
}
DEFAULT = "uk"


# ───────────────────────── розбір словника T (літерал JavaScript) ─────────────────────────
class JsLiteralError(ValueError):
    pass


def _skip(s: str, i: int) -> int:
    """Пропуск пробілів і коментарів."""
    while i < len(s):
        if s[i].isspace():
            i += 1
        elif s.startswith("//", i):
            j = s.find("\n", i)
            i = len(s) if j < 0 else j + 1
        elif s.startswith("/*", i):
            j = s.find("*/", i + 2)
            if j < 0:
                raise JsLiteralError("unterminated comment")
            i = j + 2
        else:
            break
    return i


def _string(s: str, i: int):
    q = s[i]
    j = i + 1
    while j < len(s):
        if s[j] == "\\":
            j += 2
            continue
        if s[j] == q:
            body = s[i + 1:j]
            if q == "'":
                body = body.replace('\\\'', "'").replace('"', '\\"')
            try:
                return json.loads('"' + body + '"'), j + 1
            except json.JSONDecodeError as e:
                raise JsLiteralError(f"bad string at {i}: {e}") from e
        if s[j] == "\n":
            break
        j += 1
    raise JsLiteralError(f"unterminated string at {i}")


def parse_js_value(s: str, i: int = 0):
    """Літерал JS з об'єктів, масивів, рядків у лапках, чисел, true/false/null -> (значення, кінець)."""
    i = _skip(s, i)
    if i >= len(s):
        raise JsLiteralError("unexpected end")
    c = s[i]
    if c == "{":
        out, i = {}, _skip(s, i + 1)
        while True:
            if i < len(s) and s[i] == "}":
                return out, i + 1
            if s[i] in "\"'":
                key, i = _string(s, i)
            else:
                m = re.compile(r"[A-Za-z_$][\w$]*").match(s, i)
                if not m:
                    raise JsLiteralError(f"bad key at {i}")
                key, i = m.group(0), m.end()
            i = _skip(s, i)
            if i >= len(s) or s[i] != ":":
                raise JsLiteralError(f"expected ':' at {i}")
            out[key], i = parse_js_value(s, i + 1)
            i = _skip(s, i)
            if i < len(s) and s[i] == ",":
                i = _skip(s, i + 1)
            elif i < len(s) and s[i] == "}":
                continue
            else:
                raise JsLiteralError(f"expected ',' or '}}' at {i}")
    if c == "[":
        out, i = [], _skip(s, i + 1)
        while True:
            if i < len(s) and s[i] == "]":
                return out, i + 1
            v, i = parse_js_value(s, i)
            out.append(v)
            i = _skip(s, i)
            if i < len(s) and s[i] == ",":
                i = _skip(s, i + 1)
            elif i < len(s) and s[i] == "]":
                continue
            else:
                raise JsLiteralError(f"expected ',' or ']' at {i}")
    if c in "\"'":
        return _string(s, i)
    m = re.compile(r"-?\d+(\.\d+)?").match(s, i)
    if m:
        return (float(m.group(0)) if m.group(1) else int(m.group(0))), m.end()
    m = re.compile(r"(true|false|null)\b").match(s, i)
    if m:
        return {"true": True, "false": False, "null": None}[m.group(1)], m.end()
    raise JsLiteralError(f"unexpected {c!r} at {i}")


def extract_dict(page: str) -> dict:
    m = re.search(r"\bconst T\s*=\s*", page)
    if not m:
        raise JsLiteralError("const T not found")
    t, _ = parse_js_value(page, m.end())
    if not isinstance(t, dict) or not all(isinstance(t.get(l), dict) for l in LANGS):
        raise JsLiteralError("T must have uk and en dictionaries")
    return t


# ───────────────────────── сторінка мови ─────────────────────────
def esc(s) -> str:
    return html.escape(str(s), quote=True)


def head_block(lang: str, t: dict) -> str:
    m = LANGS[lang]
    alts = "".join(f'<link rel="alternate" hreflang="{l}" href="{LANGS[l]["url"]}">\n' for l in LANGS)
    alts += f'<link rel="alternate" hreflang="x-default" href="{LANGS[DEFAULT]["url"]}">\n'
    other = [LANGS[l]["locale"] for l in LANGS if l != lang]
    ld = {
        "@context": "https://schema.org",
        "@type": "SoftwareApplication",
        "name": "OptimaX",
        "alternateName": "OptimaX by X44TO",
        "description": m["desc"],
        "url": m["url"],
        "applicationCategory": "UtilitiesApplication",
        "operatingSystem": "Windows 10, Windows 11",
        "downloadUrl": REPO + "/releases/latest",
        "installUrl": REPO + "/releases/latest",
        "softwareHelp": f"{REPO}/blob/main/{t.get('docs') or 'docs/uk/guide.md'}",
        "license": "https://opensource.org/licenses/MIT",
        "isAccessibleForFree": True,
        "offers": {"@type": "Offer", "price": "0", "priceCurrency": "USD"},
        "inLanguage": list(LANGS),
        "image": BASE + "assets/logo.png",
        "screenshot": f"{BASE}assets/screens/{lang}/analysis.png",
        "author": {"@type": "Person", "name": "X44TO", "url": "https://github.com/hatogg"},
        "sameAs": [REPO],
    }
    ld_json = json.dumps(ld, ensure_ascii=False, indent=1).replace("</", "<\\/")
    return (
        f'<title>{esc(m["title"])}</title>\n'
        f'<meta name="description" content="{esc(m["desc"])}">\n'
        f'<meta name="robots" content="index, follow, max-image-preview:large">\n'
        f'<link rel="canonical" href="{m["url"]}">\n'
        f"{alts}"
        f'<meta property="og:type" content="website">\n'
        f'<meta property="og:site_name" content="OptimaX">\n'
        f'<meta property="og:title" content="{esc(m["title"])}">\n'
        f'<meta property="og:description" content="{esc(m["desc"])}">\n'
        f'<meta property="og:url" content="{m["url"]}">\n'
        f'<meta property="og:image" content="{BASE}assets/{m["image"]}">\n'
        f'<meta property="og:locale" content="{m["locale"]}">\n'
        + "".join(f'<meta property="og:locale:alternate" content="{o}">\n' for o in other) +
        f'<meta name="twitter:card" content="summary_large_image">\n'
        f'<meta name="twitter:title" content="{esc(m["title"])}">\n'
        f'<meta name="twitter:description" content="{esc(m["desc"])}">\n'
        f'<meta name="twitter:image" content="{BASE}assets/{m["image"]}">\n'
        f'<script type="application/ld+json">\n{ld_json}\n</script>\n')


HEAD_TAGS = re.compile(
    r'[ \t]*(<title>.*?</title>|<meta\s+(name="(description|robots|twitter:[\w:]+)"|property="og:[\w:]+")[^>]*>|'
    r'<link\s+rel="(canonical|alternate)"[^>]*>|<script type="application/ld\+json">.*?</script>)[ \t]*\n?', re.S)


def render(page: str, lang: str, t_all: dict) -> str:
    t = t_all[lang]
    m = LANGS[lang]
    out = HEAD_TAGS.sub("", page)
    out = re.sub(r'(<meta name="viewport"[^>]*>\n)', lambda g: g.group(1) + head_block(lang, t), out, count=1)
    out = re.sub(r"<html[^>]*>", f'<html lang="{lang}" data-lang="{lang}">', out, count=1)

    # текст елементів із data-t (як apply() у скрипті, але одразу в HTML)
    def fill(g):
        key = g.group(3)
        val = t.get(key)
        return g.group(1) + (esc(val) if isinstance(val, str) else "") + g.group(4)
    out = re.sub(r'(<(\w+)\b[^>]*\sdata-t="(\w+)"[^>]*>)\s*(</\2>)', fill, out)

    # списки можливостей, питання, вкладки зі скриншотами
    for g in ("fg1", "fg2", "fg3"):
        items = "".join(f"<dt>{esc(title)}</dt><dd>{esc(d)}</dd>" for grp, title, d in t.get("f") or [] if grp == g)
        out = re.sub(rf'(<dl id="{g}">)\s*(</dl>)', lambda x: x.group(1) + items + x.group(2), out, count=1)
    faq = "".join(f"<details><summary>{esc(q)}</summary><p>{esc(a)}</p></details>" for q, a in t.get("q") or [])
    out = re.sub(r'(<div id="faq-list">)\s*(</div>)', lambda x: x.group(1) + faq + x.group(2), out, count=1)
    tabs = t.get("tabs") or []
    if tabs:
        btns = "".join(
            f'<button type="button" role="tab" id="tab-{esc(i)}" aria-selected="{"true" if n == 0 else "false"}" '
            f'aria-controls="shot-panel" tabindex="{0 if n == 0 else -1}">{esc(name)}</button>'
            for n, (i, name, _cap) in enumerate(tabs))
        out = re.sub(r'(<div class="tabs" role="tablist" id="tabs">)\s*(</div>)', lambda x: x.group(1) + btns + x.group(2),
                     out, count=1)
        sid, sname, scap = tabs[0]
        out = re.sub(r'<img id="shot" src="[^"]*" alt="[^"]*"',
                     f'<img id="shot" src="assets/screens/{lang}/{esc(sid)}.png" alt="{esc(sname)}: {esc(scap)}"', out, count=1)
        out = re.sub(r'(<p class="caption" id="caption"[^>]*>)\s*(</p>)', lambda x: x.group(1) + esc(scap) + x.group(2),
                     out, count=1)
    out = re.sub(r'(<a id="f-docs" href=")[^"]*(")',
                 lambda x: x.group(1) + f"{REPO}/blob/main/{t.get('docs') or 'docs/uk/guide.md'}" + x.group(2), out, count=1)
    out = re.sub(r'(<a id="privacy-link" href=")[^"]*(")',
                 lambda x: x.group(1) + f"{REPO}/blob/main/{t.get('privacy_doc') or 'docs/uk/code-signing.md'}" + x.group(2),
                 out, count=1)
    out = re.sub(r'(<nav class="links" aria-label=")[^"]*(")', lambda x: x.group(1) + m["nav"] + x.group(2), out, count=1)
    return out


def sitemap(date: str) -> str:
    alts = "".join(f'    <xhtml:link rel="alternate" hreflang="{l}" href="{LANGS[l]["url"]}"/>\n' for l in LANGS)
    alts += f'    <xhtml:link rel="alternate" hreflang="x-default" href="{LANGS[DEFAULT]["url"]}"/>\n'
    urls = "".join(f'  <url>\n    <loc>{LANGS[l]["url"]}</loc>\n    <lastmod>{date}</lastmod>\n{alts}  </url>\n' for l in LANGS)
    return ('<?xml version="1.0" encoding="UTF-8"?>\n'
            '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n'
            f"{urls}</urlset>\n")


def build(src_dir: str, out_dir: str, date: str = None) -> list:
    with open(os.path.join(src_dir, "index.html"), encoding="utf-8") as f:
        page = f.read()
    t = extract_dict(page)
    os.makedirs(out_dir, exist_ok=True)
    written = []
    for lang, m in LANGS.items():
        path = os.path.join(out_dir, m["file"])
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(render(page, lang, t))
        written.append(path)
    path = os.path.join(out_dir, "sitemap.xml")
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(sitemap(date or datetime.date.today().isoformat()))
    written.append(path)
    return written


if __name__ == "__main__":
    if len(sys.argv) != 3:
        sys.exit("usage: build_site.py <site-src-dir> <out-dir>")
    for p in build(sys.argv[1], sys.argv[2]):
        print("wrote", p)
