"""Розумна оптимізація: знаходить шкідливі зміни половинним поділом і не вигадує їх у шумі."""
import json
import random
import sys

from _util import ROOT, cases

sys.path.insert(0, ROOT)
import abtest as AB  # noqa: E402  (чиста логіка без системи)


def simulate(n_live=20, bad=(), good=0.004, noise=0.004, mode="new", boot=0, seed=1, bad_effect=-0.07):
    rnd = random.Random(seed)
    live = [f"t{i}" for i in range(n_live)]
    boot_ids = [f"b{i}" for i in range(boot)]
    applied = set(live + boot_ids) if mode == "audit" else set()
    s = AB.Session(live, boot_ids, ["priv1"], mode=mode)
    for _ in range(300):
        a = s.next()
        if a["do"] == "done":
            break
        if a["do"] == "measure":
            f = 1.0
            for t in applied:
                f *= (1 + bad_effect) if t in bad else (1 + good)
            f *= 1 + rnd.uniform(-noise, noise)
            s.feed({"avg": 200 * f, "low1": 160 * f})
        elif a["do"] == "apply":
            applied |= set(a["ids"])
            s.ok(applied=sorted(applied))
        elif a["do"] == "undo":
            applied -= set(a["ids"])
            s.ok()
        else:
            s.ok()
    else:
        raise AssertionError("session did not finish")
    sm = s.summary()
    return dict(sm, left_bad=[b for b in bad if b in applied], applied=applied)


SEEDS = (1, 2, 3, 4)


@cases("seed", SEEDS)
def test_all_good(seed):
    r = simulate(seed=seed)
    # 3 заміри «до» + 3 «після» + перевірка двох половин
    assert r["result"] == "better" and not r["removed"] and r["measures"] <= 8 and r["significant"], r


@cases("seed", SEEDS)
def test_one_culprit(seed):
    r = simulate(bad={"t13"}, seed=seed)
    assert r["result"] == "fixed" and r["removed"] == ["t13"] and r["measures"] <= 16, r


@cases("seed", SEEDS)
def test_two_culprits(seed):
    r = simulate(bad={"t3", "t17"}, seed=seed)
    assert r["result"] == "fixed" and sorted(r["removed"]) == ["t17", "t3"] and not r["left_bad"], r


@cases("seed", SEEDS)
def test_audit_mode(seed):
    r = simulate(bad={"t7"}, mode="audit", seed=seed)
    assert r["result"] == "fixed" and r["removed"] == ["t7"], r


@cases("seed", SEEDS)
def test_with_reboot_tweaks(seed):
    r = simulate(bad={"t5"}, boot=3, seed=seed)
    assert r["result"] == "fixed" and r["removed"] == ["t5"] and {"b0", "b1", "b2"} <= r["applied"], r


@cases("seed", SEEDS)
def test_noise_is_not_a_culprit(seed):
    r = simulate(noise=0.015, good=0.0, seed=seed)
    assert not r["removed"] and r["result"] in ("same", "better"), r


def test_resume_after_reboot():
    s = AB.Session(["a", "b"], ["c"], [], mode="new")
    for avg in (100, 101, 99.5):  # AB.BASE_RUNS заміри «до»
        s.next()
        s.feed({"avg": avg, "low1": avg * 0.8})
    s.next()
    s.ok(applied=["a", "b", "c"])
    assert s.next()["do"] == "reboot"
    s2 = AB.Session.from_dict(json.loads(json.dumps(s.to_dict())))
    assert s2.next()["do"] == "reboot"
    s2.ok()
    nxt = s2.next()
    assert nxt["do"] == "measure" and nxt["label"] == "after", nxt


def test_noise_is_rarely_claimed_as_gain_or_harm():
    """Змін немає, а заміри «гуляють» на ±2.5%: «стало краще» чи «знайшли шкоду» — не частіше ніж у ~5% сесій
    (похибка — 2 стандартні похибки, ≈95%). Перевіряємо на 200 сесіях, а не на одній вдалій."""
    better = harm = 0
    for seed in range(1, 201):
        r = simulate(n_live=3, good=0.0, noise=0.025, seed=seed)
        better += r["result"] == "better"
        harm += r["result"] in ("fixed", "unexplained")
        assert r["margin"] >= 2.0
    assert better <= 16 and harm <= 16, (better, harm)


def test_clear_gain_is_significant_with_margin():
    r = simulate(n_live=3, good=0.02, noise=0.004, seed=3)
    assert r["result"] == "better" and r["significant"] and r["delta"]["avg"] > r["margin"], r
    assert r["runs"] == {"base": AB.BASE_RUNS, "after": AB.AFTER_RUNS}


def test_median_ignores_one_bad_run():
    """Один невдалий прогін (сповіщення, догрузка рівня) не зсуває центр заміру."""
    m = AB.mean_metric([{"avg": 200, "low1": 160}, {"avg": 120, "low1": 60}, {"avg": 202, "low1": 161}])
    assert m["avg"] == 200 and m["low1"] == 160
