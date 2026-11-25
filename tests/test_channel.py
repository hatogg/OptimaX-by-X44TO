"""Канал оновлень «Стабільний / Бета» (7.2): порядок версій, вибір релізу зі списку GitHub (чернетки, pre-release,
сміттєві теги), перевірка значення з settings.json, імена файлів бети, release.yml. Мережі немає — відповіді GitHub
підмінені."""
import contextlib
import io
import json
import os
import re
import sys
import tempfile

from _util import ROOT

sys.path.insert(0, ROOT)
if "engine" not in sys.modules:  # окремий запуск цього файла: режим перегляду й чиста папка налаштувань
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
import features as F  # noqa: E402
import lifecycle as L  # noqa: E402
import updater as U  # noqa: E402


@contextlib.contextmanager
def patched(obj, **attrs):
    old = {k: getattr(obj, k) for k in attrs}
    for k, v in attrs.items():
        setattr(obj, k, v)
    try:
        yield
    finally:
        for k, v in old.items():
            setattr(obj, k, v)


def rel(tag, prerelease=False, draft=False, repo=None):
    repo = repo or U._trusted_repo()
    ver = tag.lstrip("vV")
    base = f"https://github.com/{repo}/releases/download/{tag}/"
    names = (f"OptimaX-Setup-{ver}.exe", f"OptimaX-{ver}-portable.exe", U.SUMS_NAME)
    return {"tag_name": tag, "prerelease": prerelease, "draft": draft, "body": f"notes {tag}",
            "html_url": f"https://github.com/{repo}/releases/tag/{tag}",
            "assets": [{"name": n, "browser_download_url": base + n, "size": 10} for n in names]}


# ───────────────────────── порядок версій ─────────────────────────
def test_version_ordering():
    chain = ["6.9", "6.10", "6.13", "6.13.1", "6.15", "7.1.1", "7.2.0-beta.1", "7.2.0-beta.2", "7.2.0-beta.10",
             "7.2.0", "7.2.1-beta.1", "7.2.1", "7.10-beta.1", "7.10"]
    keys = [U.vkey(v) for v in chain]
    assert keys == sorted(keys) and len(set(keys)) == len(keys), list(zip(chain, keys))
    assert U.newer("7.2.0", "7.2.0-beta.3") and not U.newer("7.2.0-beta.3", "7.2.0")
    assert U.newer("7.2.1-beta.1", "7.2.0") and U.newer("7.2.0-beta.1", "7.1.1")
    assert not U.newer("7.2", "7.2.0") and not U.newer("7.2.0", "7.2"), "7.2 and 7.2.0 are the same version"
    assert U.newer("v7.2.0", "7.1.1") and U.parse_version("V6.13.1") == ((6, 13, 1, 0), 1, 0)
    assert U.is_beta("v7.2.0-beta.1") and not U.is_beta("7.2.0") and not U.is_beta("garbage")


def test_garbage_versions_never_newer():
    for bad in ("", None, "latest", "v", "7.2.0-rc.1", "7.2.0-beta", "7.2.0-BETA.1x", "7.2.0-beta.1.exe",
                "../../7.3", "7.2.0 beta 1", "1.2.3.4.5", "99999999.0", "7.2.0-beta.12345", "7..2", ["7.3"], 8):
        assert U.parse_version(bad) is None, bad
        assert not U.newer(bad, E.VERSION), bad
    assert U.newer("99.0", "not-a-version"), "an odd current version falls back to its digits"


# ───────────────────────── канал із settings.json ─────────────────────────
def test_channel_whitelist():
    assert U.channel({"channel": "beta"}) == "beta"
    for bad in ("stable", "BETA", "Beta", " beta", "beta ", "", None, ["beta"], {"beta": 1}, 1, True, "nightly"):
        assert U.channel({"channel": bad}) == "stable", bad
    assert U.channel({}) == "stable" and U.channel(None) == "stable" and U.channel("beta") == "stable"
    assert F.DEFAULTS["updates"]["channel"] == "stable"


def test_settings_file_channel(tmp_path=None):
    d = tempfile.mkdtemp(prefix="oxch_")
    for raw, want in (("beta", "beta"), ("../beta", "stable"), (["beta"], "stable"), (None, "stable")):
        p = os.path.join(d, f"s{want}{len(str(raw))}.json")
        with open(p, "w", encoding="utf-8") as f:
            json.dump({"updates": {"channel": raw}}, f)
        assert U.channel(F.Config(p)["updates"]) == want, raw
    p = os.path.join(d, "old.json")  # settings.json з 7.1.1: каналу немає — стабільний
    with open(p, "w", encoding="utf-8") as f:
        json.dump({"updates": {"auto": True, "last_check": 5}}, f)
    c = F.Config(p)["updates"]
    assert U.channel(c) == "stable" and c["last_check"] == 5


def test_cached_respects_channel():
    with patched(E, VERSION="7.1.1"):
        beta = {"latest": {"version": "7.2.0-beta.1"}}
        assert U.cached(beta) is None, "a beta found earlier is not offered on the stable channel"
        assert U.cached(dict(beta, channel="beta")) == {"version": "7.2.0-beta.1"}
        assert U.cached({"latest": {"version": "7.2.0"}}) == {"version": "7.2.0"}
        assert U.cached({"latest": {"version": "7.2.0-rc.1"}, "channel": "beta"}) is None


# ───────────────────────── вибір релізу ─────────────────────────
RELEASES = [rel("v7.3.0-beta.1", draft=True, prerelease=True), rel("v9.9", draft=True), rel("nightly", prerelease=True),
            rel("v7.2.0-rc.1", prerelease=True), rel("../../v8.0"), {"tag_name": None}, "junk", None,
            rel("v7.2.0-beta.2", prerelease=True), rel("v7.2.0-beta.1", prerelease=True), rel("v7.1.1"),
            rel("v6.15"), rel("v6.13.1")]


def test_pick_release():
    assert U.pick_release(RELEASES, "stable")["tag_name"] == "v7.1.1"
    assert U.pick_release(RELEASES, "beta")["tag_name"] == "v7.2.0-beta.2"
    final = RELEASES + [rel("v7.2.0")]
    assert U.pick_release(final, "beta")["tag_name"] == "v7.2.0", "the final release beats its betas"
    # бета, опублікована без позначки pre-release, стабільному каналу однаково не дістається
    assert U.pick_release([rel("v7.1.1"), rel("v7.2.0-beta.1")], "stable")["tag_name"] == "v7.1.1"
    # pre-release зі стабільним тегом — лише для бети
    assert U.pick_release([rel("v7.1.1"), rel("v7.2.0", prerelease=True)], "stable")["tag_name"] == "v7.1.1"
    assert U.pick_release([rel("v7.1.1"), rel("v7.2.0", prerelease=True)], "beta")["tag_name"] == "v7.2.0"
    assert U.pick_release([], "beta") is None and U.pick_release({"x": 1}, "stable") is None
    assert U.pick_release([rel("v9.0", draft=True)], "beta") is None


def test_from_release_channels():
    with patched(E, VERSION="7.1.1"):
        b = U.from_release(rel("v7.2.0-beta.1", prerelease=True), True, "beta")
        assert b["version"] == "7.2.0-beta.1" and b["beta"] is True
        assert b["name"] == "OptimaX-Setup-7.2.0-beta.1.exe" and U.release_url(b["url"], b["name"])
        p = U.from_release(rel("v7.2.0-beta.1", prerelease=True), False, "beta")
        assert p["name"] == "OptimaX-7.2.0-beta.1-portable.exe" and p["kind"] == "portable"
        assert U.from_release(rel("v7.2.0-beta.1", prerelease=True), True, "stable") is None
        assert U.from_release(rel("v7.2.0-beta.1"), True, "stable") is None, "beta tag without the pre-release flag"
        assert U.from_release(rel("v7.2.0", prerelease=True), True, "stable") is None
        assert U.from_release(rel("v7.2.0", draft=True), True, "beta") is None
        assert U.from_release(rel("v7.2.0"), True, "stable")["beta"] is False
        # без явного каналу — канал з налаштувань (типово стабільний)
        assert U.from_release(rel("v7.2.0-beta.1", prerelease=True), True) is None


def test_no_auto_downgrade_from_beta():
    with patched(E, VERSION="7.2.0-beta.2"):
        assert U.from_release(rel("v7.1.1"), True, "stable") is None, "no downgrade to the older stable"
        assert U.from_release(rel("v7.2.0-beta.1", prerelease=True), True, "beta") is None
        assert U.from_release(rel("v7.2.0-beta.2", prerelease=True), True, "beta") is None
        assert U.from_release(rel("v7.2.0"), True, "stable")["version"] == "7.2.0", "the final release is offered"
        assert U.from_release(rel("v7.2.0-beta.3", prerelease=True), True, "beta")["version"] == "7.2.0-beta.3"


def test_check_over_mocked_github():
    calls = []

    def api_list():
        calls.append("list")
        return RELEASES

    def api_latest():
        calls.append("latest")
        return rel("v7.1.1")

    with patched(E, VERSION="7.1.1", IS_WIN=True), patched(L, is_installed=lambda: True), \
            patched(U, UPDATE_REPO=U._trusted_repo(), _api_releases=api_list, _api_latest=api_latest):
        assert U.check(chan="stable") is None and calls == ["latest"]
        info = U.check(chan="beta")
        assert calls == ["latest", "list"] and info["version"] == "7.2.0-beta.2" and info["kind"] == "setup"
        # download() бере дані лише зі свіжої перевірки — бета там є
        assert U._FRESH[("7.2.0-beta.2", "setup")]["url"] == info["url"]
        assert U._trusted_info({"version": "7.2.0-beta.2", "kind": "setup"}, lambda *_: None)["url"] == info["url"]


def test_beta_list_fallback_to_feed():
    repo = U._trusted_repo()
    feed = (f'<feed><entry><link href="https://github.com/{repo}/releases/tag/v7.2.0-beta.1"/></entry>'
            f'<entry><link href="https://github.com/{repo}/releases/tag/v7.1.1"/></entry>'
            '<entry><link href="https://evil.example/x/releases/tag/..%2F..%2Fv9.0"/></entry>'
            '<entry><link href="https://evil.example/releases/tag/nightly"/></entry></feed>')

    class Resp(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    def fake_open(url, timeout, accept=None):
        if "api.github.com" in url:
            raise OSError("rate limited")
        assert url == f"https://github.com/{repo}/releases.atom", url
        return Resp(feed.encode())

    log = []
    with patched(E, VERSION="7.1.1"), patched(U, UPDATE_REPO=repo, _open=fake_open):
        rels = U.all_releases(log.append)
    assert [r["tag_name"] for r in rels] == ["v7.2.0-beta.1", "v7.1.1"], rels
    assert rels[0]["prerelease"] is True and rels[1]["prerelease"] is False
    assert all(r["html_url"].startswith(f"https://github.com/{repo}/releases/tag/") for r in rels)
    assert any("api_releases" in x for x in log), log
    with patched(E, VERSION="7.1.1"):
        info = U.from_release(U.pick_release(rels, "beta"), True, "beta")
    assert info["version"] == "7.2.0-beta.1" and U.release_url(info["url"], info["name"])
    assert info["sums_url"].endswith("/v7.2.0-beta.1/" + U.SUMS_NAME)


def test_demo_check_per_channel():
    with patched(E, IS_WIN=False, VERSION="7.1.1"):
        assert U.check(chan="stable")["version"] == "7.2"
        b = U.check(chan="beta")
        assert b["version"] == "7.2.0-beta.1" and b["beta"] is True


# ───────────────────────── імена файлів бети ─────────────────────────
def test_beta_asset_names():
    for good, kind in (("OptimaX-Setup-7.2.0-beta.1.exe", "setup"), ("OptimaX-7.2.0-beta.1-portable.exe", "portable"),
                       ("OptimaX-Setup-7.1.1.exe", "setup"), ("OptimaX-6.15-portable.exe", "portable")):
        assert U.asset_name_ok(good, kind), good
    for bad, kind in (("OptimaX-Setup-7.2.0-beta.exe", "setup"), ("OptimaX-Setup-7.2.0-rc.1.exe", "setup"),
                      ("OptimaX-Setup-7.2.0-beta.1.exe\n", "setup"), ("..\\OptimaX-Setup-7.2.0-beta.1.exe", "setup"),
                      ("OptimaX-Setup-7.2.0-beta.1/..\\x.exe", "setup"),
                      ("OptimaX-Setup-7.2.0-beta.12345.exe", "setup"),
                      ("OptimaX-Setup-7.2.0-beta.1-beta.2.exe", "setup"),
                      ("OptimaX-7.2.0-beta.1-portable.exe", "setup"),
                      ("OptimaX-Setup-7.2.0-beta.1.exe", "portable"), ("OptimaX-7.2.0-beta.-portable.exe", "portable")):
        assert not U.asset_name_ok(bad, kind), bad
    base = f"https://github.com/{U._trusted_repo()}/releases/download/v7.2.0-beta.1/"
    assert U.release_url(base + "OptimaX-Setup-7.2.0-beta.1.exe", "OptimaX-Setup-7.2.0-beta.1.exe")
    assert not U.release_url(base + "..%5COptimaX-Setup-7.2.0-beta.1.exe")


def test_shown_marks_beta():
    assert U.shown("7.1.1") == "7.1.1"
    s = U.shown("7.2.0-beta.1")
    assert s.startswith("7.2.0-beta.1") and s != "7.2.0-beta.1"


# ───────────────────────── release.yml ─────────────────────────
def test_release_workflow_prerelease():
    with open(os.path.join(ROOT, ".github", "workflows", "release.yml"), encoding="utf-8") as f:
        wf = f.read()
    m = re.search(r"\n      prerelease:\n(?:        .*\n)*?        type: boolean\n        default: false\n", wf)
    assert m, "workflow_dispatch input prerelease (boolean, default false)"
    assert '"${pre[@]}"' in wf and "pre=(--prerelease)" in wf
    assert "prerelease: ${{ steps.v.outputs.prerelease }}" in wf
    # схема бети в workflow та сама, що в updater.parse_version
    rx = re.search(r'\[\[ "\$v" =~ (\S+) \]\]', wf).group(1)
    for v in ("7.2.0-beta.1", "7.2-beta.3", "7.1.1", "7.2.0-rc.1", "7.2.0-beta", "x7.2.0-beta.1"):
        assert bool(re.fullmatch(rx, v)) == U.is_beta(v), v
