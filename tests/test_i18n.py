"""Переклади: три мови для кожного рядка, однакові {підстановки}, жодного ключа, якого немає в таблицях."""
import glob
import os
import re
import string
import sys

from _util import ROOT

sys.path.insert(0, ROOT)
import i18n  # noqa: E402  (без Qt і без стану — можна в цьому ж процесі)


def _ph(s):
    return {f for _, f, _, _ in string.Formatter().parse(s) if f is not None}


def test_every_string_has_three_languages():
    bad = []
    for k, v in i18n.STR.items():
        assert isinstance(v, tuple) and len(v) == 3, k
        filled = [x for x in v if x]
        if filled and len(filled) < 3:  # повністю порожній рядок — навмисний (наприклад, опис «усе гаразд»)
            bad.append(k)
    assert not bad, bad


def test_placeholders_match():
    bad = []
    for k, v in i18n.STR.items():
        sets = [_ph(x) for x in v if x]
        if any(s != sets[0] for s in sets):
            bad.append((k, sets))
    assert not bad, bad[:20]


def test_tweak_texts():
    import engine as E
    for t in E.TWEAKS:
        if t._title:
            continue
        v = i18n.TWEAK_TEXT.get(t.id)
        assert v and len(v) == 6 and all(v[i] for i in (0, 2, 4)), t.id


def test_keys_used_in_code_exist():
    missing = {}
    for p in glob.glob(os.path.join(ROOT, "*.py")):
        name = os.path.basename(p)
        if name.startswith("lang_"):
            continue
        src = open(p, encoding="utf-8").read()
        for m in re.finditer(r"""\btr\(\s*["']([A-Za-z0-9_.\-]+)["']""", src):
            k = m.group(1)
            if not k.endswith(".") and k not in i18n.STR:  # «d.» + змінна — префікс, а не ключ
                missing.setdefault(k, set()).add(name)
    assert not missing, missing


def test_language_switch():
    old = i18n.LANG
    try:
        got = set()
        for code, _ in i18n.LANGS:
            i18n.set_language(code)
            got.add(i18n.tr("rs.shortcut"))
        assert len(got) == 3
    finally:
        i18n.set_language(old)
