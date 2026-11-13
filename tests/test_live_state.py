"""Справжній стан твіків (6.15, баги від тестерів). Нічого справжнього не змінюється й не читається: реєстр, PowerShell
і стан адаптерів підмінені, журнал — тимчасовий файл.

• мережеві твіки бачать стан адаптера: Interrupt Moderation / Flow Control, вимкнені вручну, — «вже застосовано»,
  і застосування нічого не змінює; те саме читання стану — для живлення, задач, служб і програм;
• «Вимкнути Copilot»: правильні значення й гілки реєстру, застосування й відкат не переплутані, результат
  перевіряється; нова програма Copilot (Appx), якої політика не стосується, — «частково» з поясненням."""
import os
import sys
import tempfile

from _util import ROOT

sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
if "engine" not in sys.modules:
    sys.argv = ["x", "--dry-run", "--lang=en"]
    os.environ["APPDATA"] = tempfile.mkdtemp(prefix="oxt_")
import engine as E  # noqa: E402
from test_undo_guarantees import patched, temp_journal  # noqa: E402


# ── знімок адаптерів у тій формі, яку дає NIC_STATE_PS (з ноутбука розробника: I219-LM і Intel AC 7265) ──
def eth(im="1", fc="3", valid=("0", "1", "2", "3", "4")):
    return dict(n="Ethernet", m=14, desc="Intel(R) Ethernet Connection (4) I219-LM", pm="",
                p=[dict(k="*InterruptModeration", v=im, d="Interrupt Moderation", valid=["0", "1"]),
                   dict(k="*FlowControl", v=fc, d="Flow Control", valid=list(valid)),
                   dict(k="EEELinkAdvertisement", v="0", d="Energy Efficient Ethernet", valid=["0", "1"])])


def wifi(roam="2"):
    return dict(n="Wi-Fi", m=9, desc="Intel(R) Dual Band Wireless-AC 7265", pm="Enabled",
                p=[dict(k="RoamAggressiveness", v=roam, d="Roaming Aggressiveness", valid=["0", "1", "2", "3", "4"]),
                   dict(k="RoamingPreferredBandType", v="0", d="Preferred Band", valid=["0", "1", "2"])])


def live(nics=None, tasks=None, pw=None, apps=None):
    st = E.LiveState(slow=False)
    st._nic = nics
    st._tasks = tasks
    st._pw = dict(pw or {})
    st._apps = apps
    return st


def test_adapter_state_is_read_from_the_adapter():
    assert E.eth_latency_state([eth()]) is False, "Interrupt Moderation 1 / Flow Control 3 — not applied yet"
    assert E.eth_latency_state([eth("0", "0")]) is True, "turned off by hand — already applied"
    assert E.eth_latency_state([eth("0", "3", valid=("1", "2", "3"))]) is True, "a value the NIC cannot take is skipped"
    assert E.eth_latency_state([wifi()]) == "na" and E.eth_latency_state(None) is None
    assert E.wifi_gaming_state([wifi("2")]) is False and E.wifi_gaming_state([wifi("0")]) is True
    assert E.nic_power_state([wifi()]) is False, "the adapter may still be turned off to save power"


def test_ethernet_latency_already_off_shows_applied_and_changes_nothing():
    t = E.BY_ID["ethernet_latency"]
    calls = []
    with temp_journal() as j, patched(is_admin=lambda: True,
                                      ps=lambda code, *a, **k: (calls.append(code), (0, "[]"))[1]):
        ctx = E.Ctx(lambda *_: None)
        ctx.live = live(nics=[eth("0", "0")])
        assert E.run_tweak(t, ctx) == "already"
        assert calls == [] and not j.has(t.id), "nothing may be changed or journaled"
        ctx.live = live(nics=[eth()])
        assert E.run_tweak(t, ctx) != "already"  # не той стан — застосовується як звичайно
        assert any("Set-NetAdapterAdvancedProperty" in c for c in calls)


def test_probe_uses_the_real_state_not_only_the_journal():
    t = E.BY_ID["ethernet_latency"]
    try:
        with temp_journal():
            E.LIVE = live(nics=[eth("0", "0")])
            E.LIVE.ts = 10 ** 10
            assert E.probe(t), "changed by hand, not in the journal — still 'already applied'"
            E.LIVE = live(nics=[eth()])
            E.LIVE.ts = 10 ** 10
            assert not E.probe(t)
            E.invalidate_live()
            assert E.LIVE is None and not E.probe(t), "no fresh state — falls back to the journal"
    finally:
        E.invalidate_live()


def test_power_tasks_and_apps_have_their_state_read_too():
    pw = next(t for t in E.TWEAKS if t.ops and all(op[0] == "pw" for op in t.ops) and not t.retired)
    want = {(op[1], op[2], op[4]): int(op[3]) for op in pw.ops}
    assert E.tweak_state(pw, live(pw=want), strict=True) is True
    other = {k: v + 1 for k, v in want.items()}
    assert E.tweak_state(pw, live(pw=other)) is False
    assert E.tweak_state(pw, live()) is None, "power state unknown — no claim"
    tk = E.BY_ID["disable_spy_tasks"]
    names = [n.lower() for op in tk.ops if op[0] == "task" for n in op[1]]
    assert E.tweak_state(tk, live(tasks={n: False for n in names}), strict=True) is True
    assert E.tweak_state(tk, live(tasks={names[0]: True})) is False
    ap = E.BY_ID["remove_copilot"]
    assert E.tweak_state(ap, live(apps={"microsoft.windowsterminal"}), strict=True) is True
    assert E.tweak_state(ap, live(apps={"microsoft.copilot"})) is False


def test_strict_state_never_skips_what_it_cannot_read():
    t = E.BY_ID["ethernet_latency"]
    assert E.tweak_state(t, live(nics=None), strict=True) is None, "adapters not read — apply as usual"


# ───────────────────────── «Вимкнути Copilot» ─────────────────────────
class FakeReg:
    def __init__(self, init=None, broken=False):
        self.d = dict(init or {})
        self.broken = broken

    def get(self, p, n):
        return self.d.get((p.lower(), n.lower()))

    def set(self, p, n, v, t):
        if not self.broken:
            self.d[(p.lower(), n.lower())] = (4, v)

    def delete(self, p, n):
        self.d.pop((p.lower(), n.lower()), None)


def copilot(reg, apps=None):
    t = E.BY_ID["ai_copilot"]
    log = []
    with temp_journal() as j, patched(is_admin=lambda: True, win_build=lambda: 22631, IS_WIN=True,
                                      reg_get=reg.get, reg_set=reg.set, reg_del_value=reg.delete):
        ctx = E.Ctx(log.append)
        ctx.live = live(apps=apps if apps is not None else {"microsoft.windowsterminal"})
        res = E.run_tweak(t, ctx)
        entry = j.get(t.id)
        return res, entry, log, j


def test_copilot_policy_values_and_branches():
    t = E.BY_ID["ai_copilot"]
    regs = {(op[1], op[2]): (op[3], op[4]) for op in t.ops if op[0] == "reg"}
    assert regs[(r"HKCU\Software\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot")] == (1, "dword")
    assert regs[(r"HKLM\SOFTWARE\Policies\Microsoft\Windows\WindowsCopilot", "TurnOffWindowsCopilot")] == (1, "dword")
    assert regs[(r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced", "ShowCopilotButton")] == (0, "dword")


def test_copilot_apply_turns_off_and_undo_restores_not_the_other_way_round():
    adv = (r"HKCU\Software\Microsoft\Windows\CurrentVersion\Explorer\Advanced".lower(), "showcopilotbutton")
    reg = FakeReg({adv: (4, 1)})  # кнопка була ввімкнена, політик не було
    res, entry, log, _ = copilot(reg)
    assert res is True, log
    pol = [v for (p, n), v in reg.d.items() if n == "turnoffwindowscopilot"]
    assert pol == [(4, 1), (4, 1)] and reg.d[adv] == (4, 0), reg.d
    with patched(reg_get=reg.get, reg_set=reg.set, reg_del_value=reg.delete, DRY_RUN=False), temp_journal() as j:
        j.put("ai_copilot", entry["undo"])
        assert E.undo_one("ai_copilot", lambda *_: None) is True
    assert not [k for k in reg.d if k[1] == "turnoffwindowscopilot"], "undo removes the policies it added"
    assert reg.d[adv] == (4, 1), "undo turns the button back on — exactly as it was"


def test_copilot_app_that_the_policy_does_not_cover_is_reported():
    res, entry, log, _ = copilot(FakeReg(), apps={"microsoft.copilot"})
    assert res == "partial", log
    assert any("Microsoft.Copilot" in ln for ln in log), log
    assert entry and len(entry["undo"]) == 3, "the policy part is applied and can be rolled back"


def test_registry_write_that_did_not_stick_is_not_reported_as_done():
    res, _entry, log, _ = copilot(FakeReg(broken=True))
    assert res in ("partial", False), (res, log)
