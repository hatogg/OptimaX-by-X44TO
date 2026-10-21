"""
OptimaX — список усіх оптимізацій для документації, прямо з коду (engine.py + lang_tweaks.py).

    python tools/gen_docs.py           — переписати docs/uk/tweaks.md і docs/en/tweaks.md
    python tools/gen_docs.py --check   — лише перевірити, що файли актуальні (так робить CI)

Додали чи змінили твік — запустіть без --check і закомітьте обидва файли.
"""
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
sys.argv = [sys.argv[0], "--dry-run", "--lang=en"] + sys.argv[1:]

import engine as E  # noqa: E402
import i18n  # noqa: E402
from i18n import tr  # noqa: E402

IMPACT = {"habits": "🔴", "medium": "🟡", "safe": "🔵"}
TEXT = {
    "uk": dict(title="Усі оптимізації OptimaX", back="← На головну", other="English", other_link="../en/tweaks.md",
               intro="Список створено з коду програми ({n} оптимізацій у {g} розділах, версія {v}). Позначки: "
                     "🔴 впливає на звичні речі, 🟡 помірний вплив, 🔵 безпечно. «Відкат» — чи повертає OptimaX "
                     "зміну до вашого початкового значення.",
               cols="| | Оптимізація | Що робить | Профілі | Відкат |", yes="так", no="ні",
               note="Перед застосуванням OptimaX перевіряє сумісність із вашим залізом і версією Windows: "
                    "недоречне вимикається, шкідливе для вашого ПК (наприклад, вимкнення Game Bar на AMD X3D) "
                    "блокується, а причина пишеться під пунктом."),
    "en": dict(title="All OptimaX optimizations", back="← Back to the main page", other="Українська",
               other_link="../uk/tweaks.md",
               intro="Generated from the program code ({n} optimizations in {g} sections, version {v}). Marks: "
                     "🔴 affects everyday habits, 🟡 moderate impact, 🔵 safe. “Rollback” tells whether OptimaX "
                     "restores the change to your own original value.",
               cols="| | Optimization | What it does | Profiles | Rollback |", yes="yes", no="no",
               note="Before applying, OptimaX checks compatibility with your hardware and Windows version: "
                    "irrelevant items are disabled, items harmful to your PC (for example, turning off Game Bar "
                    "on AMD X3D) are blocked, and the reason is shown under the item."),
}


def build(lang: str) -> str:
    i18n.set_language(lang)
    t_ = TEXT[lang]
    readme = "../../README.md" if lang == "uk" else "../../README.en.md"
    items_all = [t for t in E.TWEAKS if not t.custom]
    out = [f"# {t_['title']}", "",
           f"[{t_['back']}]({readme}) · [{t_['other']}]({t_['other_link']})", "",
           t_["intro"].format(n=len(items_all), g=len(E.GROUP_IDS), v=E.VERSION), "", t_["note"], ""]
    for gid in E.GROUP_IDS + ["visual"]:
        items = [t for t in E.TWEAKS if t.group == gid]
        if not items:
            continue
        out += [f"## {tr('grp.' + gid)}", ""]
        d = tr(f"grp.{gid}.d")
        if d and d != f"grp.{gid}.d":
            out += [d, ""]
        out += [t_["cols"], "| --- | --- | --- | --- | --- |"]
        for t in items:
            tags = [x for x, _ in t.badges()]
            title = t.title + (f" <sub>({', '.join(tags)})</sub>" if tags else "")
            profs = ", ".join(tr(f"prof.{k}.name") for k in "FMLTOX" if k in t.p) or "—"
            desc = (t.desc or "").replace("|", "\\|").replace("\n", " ")
            out.append(f"| {IMPACT[t.impact]} | {title} | {desc} | {profs} | {t_['yes'] if t.reversible else t_['no']} |")
        out.append("")
    return "\n".join(out)


def main() -> int:
    check = "--check" in sys.argv
    stale = []
    for lang in ("uk", "en"):
        path = os.path.join(ROOT, "docs", lang, "tweaks.md")
        text = build(lang)
        old = open(path, encoding="utf-8").read() if os.path.exists(path) else ""
        if old != text:
            stale.append(path)
            if not check:
                os.makedirs(os.path.dirname(path), exist_ok=True)
                with open(path, "w", encoding="utf-8", newline="\n") as f:
                    f.write(text)
    if check and stale:
        print("Outdated, run: python tools/gen_docs.py\n  " + "\n  ".join(stale))
        return 1
    print("updated: " + ", ".join(stale) if stale else "docs are up to date")
    return 0


if __name__ == "__main__":
    sys.exit(main())
