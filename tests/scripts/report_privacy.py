"""Звіт для форуму не містить шляхів з іменем користувача Windows."""
import _boot
import sys

sys.argv = _boot.argv("--lang=uk")
import features as F  # noqa: E402
import hardware as H  # noqa: E402
import report as RP  # noqa: E402

GAME = r"C:\Users\SecretName\Games\Counter-Strike 2\game\bin\win64\cs2.exe"
F.CFG["fps_tests"] = {GAME: {"before": {"avg": 200, "low1": 150, "low01": 120, "stutters": 1},
                             "after": {"avg": 220, "low1": 170, "low01": 140, "stutters": 0}}}
F.CFG["diag_last"] = {"game": GAME, "findings": []}
hw = H.detect_hw()
secs = RP.sections(hw, H.build_check(hw, []), H.analyze(hw))
text, page = RP.to_text(secs), RP.to_html(secs)
_boot.result(leak=("SecretName" in text) or ("SecretName" in page), game_lines=[ln for ln in text.splitlines() if "cs2" in ln])
