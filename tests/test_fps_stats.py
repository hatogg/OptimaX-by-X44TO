"""Точний тест FPS (6.4): 3–5 прогонів, медіана, 1% і 0.1% low, плавність, похибка порівняння «до/після»."""
import random
import sys

from _util import IS_WIN, ROOT, skip

sys.path.insert(0, ROOT)
import fpstest as FT  # noqa: E402  (на Linux — демо-кадри, без PresentMon і без змін у системі)


def frames(base_ms=8.0, n=4000, spikes=0.0, seed=1, jitter=0.05):
    rnd = random.Random(seed)
    out = []
    for _ in range(n):
        x = base_ms * rnd.uniform(1 - jitter, 1 + jitter)
        if rnd.random() < spikes:
            x *= 3.5
        out.append(x)
    return out


def run(fps, spread=0.0, seed=1, spikes=0.002):
    rnd = random.Random(seed)
    f = fps * (1 + rnd.uniform(-spread, spread))
    st = FT.stats(frames(1000 / f, spikes=spikes, seed=seed))
    st["ts"] = 1000 + seed
    return st


def test_stats_metrics():
    even = FT.stats(frames(10.0, jitter=0.0))
    assert even["avg"] == 100.0 and even["smooth"] == 100.0 and even["stutters"] == 0
    rough = FT.stats(frames(10.0, spikes=0.02, seed=3))
    assert rough["low01"] < rough["low1"] < rough["avg"]
    assert rough["smooth"] < 60 and rough["stutters_pm"] > 0


def test_median_and_outlier():
    runs = [run(150, seed=s) for s in range(1, 5)] + [dict(run(150, seed=9), avg=95.0)]  # один невдалий прогін
    sm = FT.summarize_runs(runs)
    assert sm["runs"] == 4 and sm["dropped"] == 1 and 140 < sm["avg"] < 160, sm
    three = FT.summarize_runs(runs[:2] + runs[-1:])  # із трьох нічого не викидаємо — медіана й так стійка
    assert three["runs"] == 3 and three["dropped"] == 0 and three["avg"] > 140
    assert all(three["spread"][k] is not None for k in FT.METRICS)


def test_no_change_is_rarely_called_a_change():
    """Однакова гра «до» і «після», FPS гуляє на ±2% між прогонами, а 1% low — ще сильніше (фризи випадкові).
    «Стало краще» чи «гірше» — не частіше ніж у ~5% серій у кожен бік. Перевіряємо на 200 серіях по 3 прогони."""
    better = worse = 0
    for t in range(200):
        b = FT.summarize_runs([run(150, 0.02, seed=1000 * t + s) for s in range(3)])
        a = FT.summarize_runs([run(150, 0.02, seed=1000 * t + 500 + s) for s in range(3)])
        v = FT.compare_runs(b, a)["verdict"]
        better += v == "better"
        worse += v == "worse"
    assert better <= 16 and worse <= 16, (better, worse)


def test_real_gain_and_loss():
    before = FT.summarize_runs([run(150, 0.005, seed=s) for s in range(1, 4)])
    better = FT.summarize_runs([run(165, 0.005, seed=s + 20) for s in range(1, 4)])  # +10%
    worse = FT.summarize_runs([run(135, 0.005, seed=s + 40) for s in range(1, 4)])  # −10%
    up, down = FT.compare_runs(before, better), FT.compare_runs(before, worse)
    assert up["verdict"] == "better" and up["metrics"]["avg"]["sig"] and 8 < up["d_avg"] < 12, up
    assert down["verdict"] == "worse" and down["metrics"]["avg"]["dir"] == -1, down
    assert up["confidence"] == "high"


def test_more_runs_shrink_the_error():
    b3 = FT.summarize_runs([run(150, 0.03, seed=s) for s in range(1, 4)])
    b5 = FT.summarize_runs([run(150, 0.03, seed=s) for s in range(1, 6)])
    a3 = FT.summarize_runs([run(150, 0.03, seed=s + 50) for s in range(1, 4)])
    a5 = FT.summarize_runs([run(150, 0.03, seed=s + 50) for s in range(1, 6)])
    # та сама мінливість (cv), більше прогонів — менша похибка
    for s in (b3, b5, a3, a5):
        s["spread"] = {"avg": 0.02, "low1": 0.04, "low01": 0.08}
    assert FT.margin(b5, a5, "avg") < FT.margin(b3, a3, "avg")


def test_old_single_measurements_still_compare():
    """Заміри з 6.3 (один прогін, без розкиду): порівнюються з типовою похибкою й позначкою «мало замірів»."""
    b = {"avg": 100.0, "low1": 70.0, "low01": 50.0, "stutters": 3, "ts": 1}
    a = {"avg": 112.0, "low1": 80.0, "low01": 55.0, "stutters": 1, "ts": 2}
    c = FT.compare(b, a)
    assert c["verdict"] == "better" and c["confidence"] == "low" and c["runs"] == (1, 1)
    assert FT.compare(b, dict(a, avg=103.0, low1=71.0))["verdict"] == "same"


def test_capture_runs_demo():
    if IS_WIN:
        skip("demo frames exist only outside Windows; on Windows capture needs a running game and PresentMon")
    log = []
    res = FT.capture_runs("cs2.exe", 5, 3, log.append, None)
    assert res["runs"] == 3 and res["avg"] > 0 and res["low01"] > 0 and res["smooth"]
    assert res["spread"]["avg"] is not None and len(res["values"]["avg"]) == 3
    assert any("3" in str(x) for x in log)
