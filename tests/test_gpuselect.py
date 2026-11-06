"""Вибір відеокарти для GPU-тесту (gpuselect.py): ноутбук з Optimus (відгук: тест малювала вбудована графіка, а RTX 4060
простоювала), AMD/Intel з двома картами, майнінгова карта, ПК з однією картою; звірка, хто справді малював."""
import json
import os
import sys
import time

from _util import ROOT

sys.path.insert(0, ROOT)
import gpubench as GB  # noqa: E402
import gpuinfo as GI  # noqa: E402
import gpuselect as GS  # noqa: E402

IG_LUID = "0x00000000_0x0000B1A2"
NV_LUID = "0x00000000_0x0000C3D4"


def laptop():
    return GS.adapters(GI.DEMO_PROBE["laptop"])


def amd_hybrid():
    pr = {"dxgi": [dict(name="AMD Radeon(TM) Graphics", ven=0x1002, dev=0x1681, sub=0x13A1103C, vram_mb=512,
                        luid="0x0_0x1", software=False, outputs=1, dx12=True),
                   dict(name="AMD Radeon RX 6650M", ven=0x1002, dev=0x73EF, sub=0x13A1103C, vram_mb=8176,
                        luid="0x0_0x2", software=False, outputs=0, dx12=True)]}
    return GS.adapters(pr)


def test_adapters_skip_software_and_mark_display():
    ads = laptop()
    assert [a["kind"] for a in ads] == ["igpu", "dgpu"], ads
    assert [a["display"] for a in ads] == [True, False]
    assert all(a["vendor"] in ("intel", "nvidia") for a in ads)
    assert not any("Basic Render" in a["name"] for a in ads), "WARP must never be offered as a graphics card"


def test_keys_survive_reboots_and_tell_twins_apart():
    """LUID змінюється після перезавантаження — ключ ні; дві однакові карти отримують різні ключі."""
    ads = laptop()
    assert ads[1]["key"] == "10DE-28A1-1E1F1043"
    twin = dict(GI.DEMO_PROBE["gaming"]["dxgi"][0])
    pr = {"dxgi": [twin, dict(twin, luid="0x0_0x99", outputs=0)]}
    keys = [a["key"] for a in GS.adapters(pr)]
    assert keys == ["10DE-2786-51361458", "10DE-2786-51361458#2"], keys


def test_auto_is_high_performance():
    assert GS.resolve(GS.AUTO, laptop())["name"].startswith("NVIDIA"), "auto must pick the RTX, not the Iris Xe"
    assert GS.resolve(GS.AUTO, amd_hybrid())["name"] == "AMD Radeon RX 6650M"
    assert GS.resolve("10DE-28A1-1E1F1043", laptop())["kind"] == "dgpu"
    assert GS.resolve("8086-A7A0-1E1F1043", laptop())["kind"] == "igpu"
    assert GS.resolve("gone-card", laptop())["kind"] == "dgpu", "a card that disappeared falls back to auto"
    assert GS.high_performance([]) == {}


def test_optimus_plan_asks_nvidia_only_for_the_test_process():
    ads = laptop()
    p = GS.plan(GS.resolve(GS.AUTO, ads), ads)
    assert p["method"] == "optimus" and p["env"] == {GS.SHIM_VAR: GS.SHIM_DGPU}, p
    assert p["luid"] == NV_LUID and p["key"] == "10DE-28A1-1E1F1043"
    env = GS.child_env(p, base={"PATH": "x", GS.SHIM_VAR: "junk"})
    assert env == {"PATH": "x", GS.SHIM_VAR: GS.SHIM_DGPU}, "only the child gets the variable, a stale one is replaced"
    ig = GS.plan(GS.resolve("8086-A7A0-1E1F1043", ads), ads)
    assert ig["method"] == "native" and ig["env"] == {GS.SHIM_VAR: GS.SHIM_IGPU}, \
        "the integrated GPU is asked for explicitly, so an NVIDIA profile can't take the test over"


def test_amd_hybrid_uses_windows_preference():
    ads = amd_hybrid()
    p = GS.plan(GS.resolve(GS.AUTO, ads), ads)
    assert p["method"] == "winpref" and p["env"] == {}, p
    assert p["needs_pref"] is True  # демо: налаштування «Графіка» ще не задане
    p = GS.plan(GS.resolve(GS.AUTO, ads), ads, mesa_dir="C:\\mesa")
    assert p["fallback"] == "mesa"


def test_mining_card_needs_mesa():
    ads = GS.adapters(GI.DEMO_PROBE["mining"])
    t = GS.resolve(GS.AUTO, ads)
    assert t["kind"] == "mining"
    assert GS.plan(t, ads)["method"] == "none"
    p = GS.plan(t, ads, mesa_dir="C:\\mesa")
    assert p["method"] == "mesa" and p["env"][GS.MESA_VAR] == t["name"] and p["mesa"] == "C:\\mesa"


def test_prefer_mesa_and_single_gpu():
    ads = laptop()
    p = GS.plan(GS.resolve(GS.AUTO, ads), ads, mesa_dir="C:\\m", prefer_mesa=True)
    assert p["method"] == "mesa" and p["env"] == {GS.MESA_VAR: "NVIDIA GeForce RTX 4050 Laptop GPU"}
    one = GS.adapters(GI.DEMO_PROBE["gaming"])
    assert len(one) == 1
    assert GS.plan(one[0], one) == dict(GS.plan(one[0], one), method="native", env={})


def test_render_match():
    nv = laptop()[1]
    ig = laptop()[0]
    assert GS.render_match(nv, "NVIDIA Corporation", "NVIDIA GeForce RTX 4050 Laptop GPU/PCIe/SSE2") == "match"
    assert GS.render_match(nv, "Intel", "Intel(R) Iris(R) Xe Graphics") == "other"
    assert GS.render_match(nv, "Mesa", "D3D12 (NVIDIA GeForce RTX 4050 Laptop GPU)") == "match"
    assert GS.render_match(nv, "Mesa", "llvmpipe (LLVM 17.0.6, 256 bits)") == "other"
    assert GS.render_match(ig, "Intel", "Intel(R) Iris(R) Xe Graphics") == "match"
    amd = amd_hybrid()
    assert GS.render_match(amd[1], "ATI Technologies Inc.", "AMD Radeon RX 6650M") == "match"
    assert GS.render_match(amd[1], "ATI Technologies Inc.", "AMD Radeon 680M") == "other", "APU instead of the RX"
    assert GS.render_match(amd[1], "ATI Technologies Inc.", "AMD Radeon(TM) Graphics") == "vendor"
    assert GS.render_match({}, "NVIDIA", "x") == ""
    assert GS.render_match(nv, "", "") == ""


def test_confirm_combines_renderer_and_engine_counters():
    p = GS.plan(laptop()[1], laptop())
    busy_nv = [{NV_LUID: {"3d": 95.0}, IG_LUID: {"3d": 4.0}}] * 6
    busy_ig = [{IG_LUID: {"3d": 97.0}, NV_LUID: {"3d": 0.0}}] * 6
    eng = GS.engine_share(busy_nv, NV_LUID)
    assert eng == dict(n=6, target=95.0, other=4.0, other_luid=IG_LUID)
    assert GS.confirm(p, "match", eng)["status"] == "confirmed"
    assert GS.confirm(p, "match", GS.engine_share([], NV_LUID))["status"] == "renderer", "no counters (WDDM < 2.0)"
    assert GS.confirm(p, "other", eng)["status"] == "wrong"
    assert GS.confirm(p, "vendor", GS.engine_share(busy_ig, NV_LUID))["status"] == "wrong"
    assert GS.confirm(p, "vendor", eng)["status"] == "confirmed"
    assert GS.confirm(p, "vendor", GS.engine_share([], NV_LUID))["status"] == "likely"
    assert GS.confirm(p, "", GS.engine_share([{}, {}], NV_LUID))["status"] == "unknown"
    assert GS.confirm({}, "match", eng)["status"] == "unknown"
    c = GS.confirm(p, "other", eng, got="Intel(R) Iris(R) Xe Graphics")
    assert c["want"] == "NVIDIA GeForce RTX 4050 Laptop GPU" and c["got"].startswith("Intel") and c["method"] == "optimus"


def test_results_on_different_cards_are_not_compared():
    a = dict(gpu="NVIDIA GeForce RTX 4050 Laptop GPU", adapter_key="10DE-28A1-1E1F1043", score=9000)
    b = dict(a, score=9100)
    assert GB.same_gpu(a, b)
    assert not GB.same_gpu(a, dict(b, adapter_key="8086-A7A0-1E1F1043"))
    assert not GB.same_gpu(a, dict(b, gpu_check={"status": "wrong"})), "a run on the wrong card is never a baseline"
    assert GB.same_gpu(dict(gpu="X"), dict(gpu="X")), "old results without keys compare by name as before"


def test_child_arguments_and_environment():
    p = GS.plan(laptop()[1], laptop())
    args, env, mesa = GB._plan_args(p, "")
    assert "--want-name=NVIDIA GeForce RTX 4050 Laptop GPU" in args and "--want-vendor=nvidia" in args
    assert env == {GS.SHIM_VAR: GS.SHIM_DGPU} and mesa == ""
    pm = GS.plan(laptop()[1], laptop(), mesa_dir="C:\\m", prefer_mesa=True)
    assert GB._plan_args(pm, "")[2] == "C:\\m"
    assert GB._plan_args({}, "C:\\old")[2] == "C:\\old", "the mining-card Mesa path still works without a plan"


def _finish(run, timeout: float = 10.0) -> dict:
    """Демо-тест іде за годинником: на Windows time.time() крокує по ~15 мс, тож чекаємо, а не рахуємо опитування."""
    end = time.time() + timeout
    st = {}
    while time.time() < end:
        st = run.poll()
        if st.get("state") == "done":
            break
        time.sleep(0.005)
    return st


def test_demo_run_on_the_chosen_card():
    os.environ.setdefault("OPTIMAX_DEMO", "laptop")
    GB.DemoRun.SPEED = 100000.0
    nv = GB.DemoRun("1080p", "bench", 1, adapter=GS.plan(laptop()[1], laptop()))
    st = _finish(nv)
    r = st["result"]
    assert r["gpu"] == "NVIDIA GeForce RTX 4050 Laptop GPU" and r["gpu_check"]["status"] == "confirmed", r.get("gpu_check")
    assert r["adapter_key"] == "10DE-28A1-1E1F1043"
    ig = GB.DemoRun("1080p", "bench", 1, adapter=GS.plan(laptop()[0], laptop()))
    st = _finish(ig)
    assert st["result"]["avg"] < r["avg"] * 0.5, "the integrated GPU is much slower in the demo, as in real life"
    json.dumps(r)  # результат зберігається в налаштуваннях — лише прості типи
