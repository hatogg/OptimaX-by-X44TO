"""OptimaX 6.16: «Здоров'я ПК» — оцінка карток з фактів, межі, дозволений список виправлень і їх відкат,
приватність (пароль автовходу ніколи не читається), переклади кожної перевірки й виправлення."""
import re
import sys
import time

from _util import ROOT

sys.path.insert(0, ROOT)
import engine as E  # noqa: E402
import healthcheck as HC  # noqa: E402
import i18n  # noqa: E402

NOW = 1_800_000_000
DAY = 86400


def facts(**ps):
    base = dict(wuhist=[dict(t="2026-10 Cumulative Update (KB1)", rc=2, hr="0x00000000", ts=NOW - 5 * DAY)],
                wureboot=False, wusvc="Manual", wupause="",
                mp=dict(svc=True, av=True, rtp=True, sig=1, quick=2), threats=0, defpol={},
                avs=[dict(n="Windows Defender", s=397568)], fws=[],
                fw=[dict(n="Domain", on=True), dict(n="Private", on=True), dict(n="Public", on=True)], fwpol=False,
                uac=dict(lua=1, cpa=5), smb1srv=False, smb1cli=None, rdp=dict(deny=1, nla=1),
                autologon=dict(on="0", pwd=False), autorun=dict(lm=None, cu=None, ap=1),
                timesvc=dict(st="Stopped", start="Manual"), audio=dict(srv="Running", aeb="Running", out=1, inp=1),
                hiberboot=0)
    base.update(ps)
    return dict(ts=NOW, admin=True, ps=base, offset=0.4, uptime=2 * DAY, devices=[],
                disks=[dict(name="SSD", health="Healthy", wear=5, temp=40, free=[dict(l="C", free=200.0, total=1000.0)])],
                crash=dict(days=30, incidents=[], gpu={}, whea={}, memtest={}))


def card(f, cid):
    return next(c for c in HC.evaluate(f)["checks"] if c["id"] == cid)


def test_clean_pc_scores_100():
    r = HC.evaluate(facts())
    assert r["score"] == 100, [(c["id"], c["st"]) for c in r["checks"] if c["st"] != HC.OK]
    assert [c["id"] for c in r["checks"]] == list(HC.CHECKS), "same state keeps the fixed order"
    assert HC.safe_fixes(r) == []


def test_score_is_bounded_and_problems_come_first():
    f = facts(mp=dict(svc=True, av=True, rtp=False, sig=30, quick=HC.NEVER), uac=dict(lua=0),
              fw=[dict(n="Public", on=False)], rdp=dict(deny=0, nla=0), smb1srv=True,
              autologon=dict(on="1", pwd=True))
    f["offset"] = 900.0
    f["devices"] = [dict(name="GPU", cls="Display", code=43)]
    r = HC.evaluate(f)
    assert 0 <= r["score"] < 50
    order = [HC.ORDER[c["st"]] for c in r["checks"]]
    assert order == sorted(order)


def test_windows_update_ignores_defender_and_failures_that_later_succeeded():
    hist = [dict(t="Security Intelligence Update for Microsoft Defender Antivirus - KB2267602", rc=2, ts=NOW - DAY),
            dict(t="2026-07 Cumulative Update (KB7)", rc=2, ts=NOW - 80 * DAY),
            dict(t="2026-10 Cumulative Update (KB10)", rc=4, hr="0x800F0922", ts=NOW - 9 * DAY),
            dict(t="2026-10 Cumulative Update (KB10)", rc=2, ts=NOW - 2 * DAY)]
    c = card(facts(wuhist=hist), "wu")
    assert c["st"] == HC.OK and "wu_reset" not in c["fixes"], c  # невдале потім встановилося
    c = card(facts(wuhist=hist[:3]), "wu")
    assert c["st"] == HC.BAD, "80 days without a Windows update (Defender updates don't count)"
    assert "wu_reset" in c["fixes"] and any(d[0] == "hc.wu.failed" and d[1]["code"] == "0x800F0922"
                                            for d in c["det"])


def test_windows_update_pause_and_pending_restart():
    pause = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(NOW + 10 * DAY))
    assert card(facts(wupause=pause), "wu")["st"] == HC.INFO
    assert card(facts(wureboot=True), "wu")["st"] == HC.WARN
    assert card(facts(wuhist=None, hotfix=NOW - 3 * DAY), "wu")["st"] == HC.OK, "Get-HotFix is the fallback"
    assert card(facts(wuhist=None), "wu")["st"] == HC.UNKNOWN


def test_defender_rules():
    assert card(facts(avs=[dict(n="ESET Security", s=266240)], mp=None), "defender")["head"][0] == "hc.def.other"
    c = card(facts(defpol=dict(rtp=1)), "defender")
    assert c["st"] == HC.BAD and c["fixes"] == [], "a policy wins over Set-MpPreference — no fix that can't work"
    c = card(facts(mp=dict(svc=True, av=True, rtp=True, sig=HC.DEF_SIG_WARN + 1, quick=1)), "defender")
    assert c["st"] == HC.WARN and c["fixes"] == ["def_sig"]
    c = card(facts(mp=dict(svc=True, av=True, rtp=False, sig=1, quick=HC.NEVER)), "defender")
    assert c["st"] == HC.BAD and c["fixes"] == ["def_rtp", "def_scan"]
    assert card(facts(threats=2), "defender")["st"] == HC.BAD
    assert "def_scan" not in HC.safe_fixes(HC.evaluate(facts(mp=dict(svc=True, av=True, rtp=True, sig=1,
                                                                     quick=HC.NEVER)))), \
        "a quick scan loads the PC for minutes — never in the one-click plan"


def test_defender_load_is_limited_not_disabled():
    c = card(facts(), "defender")
    assert c["st"] == HC.OK and ["tweak", "defender_limit"] in c["opens"] and "defender_limit" in E.BY_ID
    assert not E.BY_ID["defender_limit"].retired, "the hint must lead to a change the catalog still offers"
    other = card(facts(avs=[dict(n="ESET Security", s=266240)]), "defender")
    assert ["tweak", "defender_limit"] not in other["opens"], "no Defender hint when another antivirus protects"


def test_firewall_profiles_policy_and_other_firewalls():
    c = card(facts(fw=[dict(n="Private", on=False), dict(n="Public", on=True)]), "firewall")
    assert c["st"] == HC.WARN and c["fixes"] == ["fw_on"]
    r = HC.evaluate(facts(fw=[dict(n="Private", on=False), dict(n="Public", on=False)]))
    assert next(x for x in r["checks"] if x["id"] == "firewall")["st"] == HC.BAD
    assert HC.fix_command("fw_on", r) == ("netsh advfirewall set privateprofile state on; "
                                          "netsh advfirewall set publicprofile state on")
    assert card(facts(fw=[dict(n="Public", on=False)], fwpol=True), "firewall")["fixes"] == []
    assert card(facts(fw=[dict(n="Public", on=False)], fws=[dict(n="Comodo Firewall", s=266240)]),
                "firewall")["st"] == HC.OK


def test_security_settings():
    assert card(facts(uac=dict(lua=0)), "uac")["st"] == HC.BAD
    assert card(facts(uac=dict(lua=1, cpa=0)), "uac")["st"] == HC.WARN
    assert card(facts(smb1cli=2), "smb1")["st"] == HC.WARN
    assert card(facts(smb1cli=4), "smb1")["st"] == HC.OK, "mrxsmb10 disabled (Start = 4) is not SMBv1 on"
    assert card(facts(rdp=dict(deny=0, nla=0)), "rdp")["fixes"] == ["rdp_nla"]
    assert card(facts(rdp=dict(deny=0, nla=0, pol=0)), "rdp")["fixes"] == []
    assert card(facts(rdp=dict(deny=0, nla=1)), "rdp")["st"] == HC.INFO
    assert card(facts(autologon=dict(on="1", pwd=True)), "autologon")["st"] == HC.WARN
    assert card(facts(autologon=dict(on="1", pwd=False)), "autologon")["st"] == HC.INFO
    assert card(facts(autorun=dict(ap=0)), "autorun")["st"] == HC.INFO, "AutoPlay is info: it costs no score"


def test_time_devices_audio_uptime_disk():
    f = facts()
    f["offset"] = -120.0
    c = card(f, "time")
    assert c["st"] == HC.WARN and c["fixes"] == ["time_sync"]
    f["offset"] = None
    assert card(f, "time")["st"] == HC.UNKNOWN
    c = card(facts(timesvc=dict(st="Stopped", start="Disabled")), "time")
    assert c["st"] == HC.WARN and c["fixes"] == ["time_svc"], "a stopped Manual service is normal; Disabled is not"
    f = facts()
    f["devices"] = [dict(name="Bluetooth", cls="Bluetooth", code=22)]
    assert card(f, "devices")["st"] == HC.OK, "a device turned off by hand is not an error"
    f["devices"] = [dict(name="Ethernet", cls="Net", code=28)]
    assert card(f, "devices")["st"] == HC.BAD
    c = card(facts(audio=dict(srv="Stopped", aeb="Running", out=1, inp=0)), "audio")
    assert c["st"] == HC.BAD and c["fixes"] == ["audio_restart"]
    f = facts(hiberboot=1)
    f["uptime"] = 10 * DAY
    c = card(f, "uptime")
    assert c["st"] == HC.WARN and c["det"][0][0] == "hc.up.fast"
    f = facts()
    f["disks"][0]["free"][0]["free"] = 8.0
    assert card(f, "disk")["st"] == HC.BAD
    f["disks"][0]["free"][0]["free"] = 60.0  # 6 % із 1000 ГБ
    assert card(f, "disk")["st"] == HC.WARN


def test_stability_from_the_crash_log():
    f = facts()
    f["crash"] = dict(days=30, incidents=[dict(kind="bsod", ts=NOW - 2 * DAY)], gpu={}, whea={}, memtest={})
    assert card(f, "stability")["st"] == HC.BAD
    f["crash"]["incidents"] = [dict(kind="bsod", ts=NOW - 20 * DAY)]
    assert card(f, "stability")["st"] == HC.WARN
    f["crash"] = None
    assert card(f, "stability")["st"] == HC.UNKNOWN


def test_partial_recheck_keeps_other_cards():
    first = HC.evaluate(facts(uac=dict(lua=0)))
    f = facts()
    f["only"] = ["time"]
    r = HC.evaluate(f, first)
    assert len(r["checks"]) == len(HC.CHECKS)
    assert next(c for c in r["checks"] if c["id"] == "uac")["st"] == HC.BAD, "untouched cards come from before"


def test_fixes_are_an_allowlist_with_valid_undo():
    r = HC.evaluate(facts(fw=[dict(n="Public", on=False)], uac=dict(lua=1, cpa=0)))
    for fid, fx in HC.FIXES.items():
        assert fx["check"] in HC.CHECKS, fid
        if fx["safe"]:
            assert fx["kind"] == "act", ("safe = changes no setting that would need undoing", fid)
        if fx["kind"] != "tweak":
            assert HC.fix_tweak(fid, r) is None
            continue
        t = HC.fix_tweak(fid, r)
        assert t.custom and t.id == f"hc_{fid}" and t.id not in E.BY_ID and t.title, fid
        for op in t.ops:
            assert op[0] in ("reg", "cmd", "svc"), (fid, op)
            if op[0] == "cmd" and op[2]:
                assert E.valid_undo({"t": "cmd", "c": op[2]}), (fid, op)
            if op[0] == "reg":
                assert op[1].upper().startswith(("HKLM\\", "HKCU\\")), (fid, op)
    uac = HC.fix_tweak("uac_on", r)
    assert [op[2] for op in uac.ops] == ["EnableLUA", "ConsentPromptBehaviorAdmin"]


def test_autologon_password_is_never_read_or_journaled():
    t = HC.fix_tweak("autologon_off", {})
    # видалення пароля — командою без відкату, а не RD(): RD записав би старе значення (пароль) у журнал
    assert not [op for op in t.ops if op[0] in ("regdel", "reg") and op[2] == "DefaultPassword"]
    assert any(op[0] == "cmd" and "DefaultPassword" in op[1] and op[2] is None for op in t.ops)
    assert not t.reversible
    ps = HC.FACTS_PS
    assert "GetValue('DefaultPassword')" not in ps and ".DefaultPassword" not in ps
    assert "GetValueNames() -contains 'DefaultPassword'" in ps


def test_never_turns_antivirus_off():
    """Жодна команда «Здоров'я ПК» — ні виправлення, ні відкат — не вимикає захист (і не додає виключень)."""
    import inspect
    src = inspect.getsource(HC)
    assert "DisableRealtimeMonitoring $true" not in src and "Add-MpPreference" not in src


def test_facts_script_only_reads():
    verbs = re.findall(r"\b(Set|New|Remove|Disable|Enable|Start|Stop|Restart|Update|Clear)-[A-Za-z]+", HC.FACTS_PS)
    assert verbs == ["New"], verbs  # лише New-Object для COM Microsoft.Update.Session


def test_every_check_and_fix_is_translated():
    keys = ["hc.title"]
    for cid in HC.CHECKS:
        keys += [f"hc.c.{cid}", f"hc.why.{cid}", f"hc.todo.{cid}"]
        assert cid in HC.CHECK_CMD
    for fid in HC.FIXES:
        keys += [f"hc.fix.{fid}", f"hc.fixd.{fid}"]
    for code in HC.DEV_CODES:
        keys.append(f"hc.dev.c{code}")
    keys += [f"hc.st.{s}" for s in HC.ORDER] + [f"hc.out.{o}" for o in ("fixed", "still", "failed", "reboot", "done")]
    keys += ["hc.fw.p.domain", "hc.fw.p.private", "hc.fw.p.public"]
    keys += list(HC.OPEN_LABEL.values())
    assert not [k for k in keys if k not in i18n.STR], [k for k in keys if k not in i18n.STR]


def test_every_open_button_has_a_label():
    f = facts(wuhist=[dict(t="x", rc=4, hr="0x1", ts=NOW - DAY)], threats=1, fw=[dict(n="Public", on=False)],
              audio=dict(srv="Stopped", aeb="Running", out=0, inp=0))
    f["devices"] = [dict(name="d", cls="Net", code=28)]
    f["disks"][0].update(health="Warning", free=[dict(l="C", free=1.0, total=100.0)])
    f["crash"]["incidents"] = [dict(kind="bsod", ts=NOW - DAY)]
    f["offset"] = 500.0
    for c in HC.evaluate(f)["checks"]:
        for kind, val in c["opens"]:
            assert (val or kind) in HC.OPEN_LABEL, (c["id"], kind, val)


def test_every_card_text_formats_in_every_language():
    for demo_like in (facts(), facts(uac=dict(lua=0), smb1srv=True, rdp=dict(deny=0, nla=0), autorun=dict(),
                                     mp=dict(rtp=False, sig=40, quick=HC.NEVER), threats=1,
                                     wuhist=[dict(t="x", rc=4, hr="0x1", ts=NOW - DAY)], wureboot=True)):
        r = HC.evaluate(demo_like)
        old = i18n.LANG
        try:
            for code, _ in i18n.LANGS:
                i18n.set_language(code)
                for c in r["checks"]:
                    k, p = c["head"]
                    assert i18n.tr(k, **p) != k, k
                    for dk, dp in c["det"]:
                        assert i18n.tr(dk, **dp) != dk, dk
                assert HC.report_lines(r)
        finally:
            i18n.set_language(old)
