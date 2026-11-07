"""Збирання сайту (tools/build_site.py): текст у HTML для кожної мови, мітки для пошуковиків, sitemap."""
import json
import os
import re
import sys
import xml.etree.ElementTree as ET

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tools"))
import build_site as BS  # noqa: E402


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("site")
    BS.build(os.path.join(ROOT, "site"), str(out), date="2026-01-01")
    return {name: (out / name).read_text(encoding="utf-8") for name in ("index.html", "en.html", "sitemap.xml")}


def test_js_literal_parser():
    v, end = BS.parse_js_value('{a: "x\\"y", "b": [1, 2.5, \'z\', true, null,], // c\n c: {d: []},}')
    assert v == {"a": 'x"y', "b": [1, 2.5, "z", True, None], "c": {"d": []}}
    with pytest.raises(BS.JsLiteralError):
        BS.parse_js_value('{a: "unterminated}')


def test_dictionaries_match():
    t = BS.extract_dict(open(os.path.join(ROOT, "site", "index.html"), encoding="utf-8").read())
    assert set(t["uk"]) == set(t["en"]), set(t["uk"]) ^ set(t["en"])
    for key in ("f", "q", "tabs"):
        assert len(t["uk"][key]) == len(t["en"][key]), key


@pytest.mark.parametrize("name,lang", [("index.html", "uk"), ("en.html", "en")])
def test_page_has_text_and_seo_tags(built, name, lang):
    s = built[name]
    m = BS.LANGS[lang]
    assert f'<html lang="{lang}" data-lang="{lang}">' in s
    # жодного порожнього елемента з data-t: пошуковик бачить текст без JavaScript
    assert not re.search(r'data-t="\w+"[^>]*>\s*</', s)
    assert re.search(r"<h1[^>]*>[^<]{10,}</h1>", s)
    assert s.count("<details>") >= 3 and s.count("<dt>") >= 6
    assert s.count("<title>") == 1 and f"<title>{BS.esc(m['title'])}</title>" in s
    assert s.count('name="description"') == 1
    assert f'<link rel="canonical" href="{m["url"]}">' in s
    for l in BS.LANGS:
        assert f'hreflang="{l}" href="{BS.LANGS[l]["url"]}"' in s
    assert 'hreflang="x-default"' in s
    ld = json.loads(re.search(r'<script type="application/ld\+json">(.*?)</script>', s, re.S).group(1))
    assert ld["@type"] == "SoftwareApplication" and ld["url"] == m["url"] and ld["offers"]["price"] == "0"
    assert "aggregateRating" not in ld  # без вигаданих оцінок
    assert f"assets/screens/{lang}/" in s
    assert len(m["title"]) <= 70 and len(m["desc"]) <= 170


def test_language_buttons_switch_pages(built):
    # на зібраній сторінці мова не береться з navigator.language (Googlebot — en-US)
    assert "const PAGE_LANG = document.documentElement.dataset.lang;" in built["index.html"]
    assert "let lang = PAGE_LANG ||" in built["index.html"]


def test_sitemap(built):
    root = ET.fromstring(built["sitemap.xml"])
    ns = {"s": "http://www.sitemaps.org/schemas/sitemap/0.9"}
    locs = [e.text for e in root.findall("s:url/s:loc", ns)]
    assert locs == [BS.LANGS[l]["url"] for l in BS.LANGS]
