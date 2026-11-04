"""Fig. 1 (two panels), Fig. 2 and Fig. S1 of the confirm2 results with the tick rule of instruction 12 §5(j) and verdict 14 A4.

    python scripts/make_fig1_2panel.py          (run from paper/; CCPILOT_REPO=/home/user/ccpilot for a work copy)

Origin: ccpilot work/paper_builds/09-0/make_fig1_2panel.py (trial typesetting, report 09-0) and
work/paper_builds/12/make_fig_ticks.py (report 12); moved here by verdict 14 A2 so that the paper repository builds Fig. 1.
Calls the locked ccpilot confirm2_figures.f1/f2 unchanged on the frozen analysis directory; inside this process only the
module method list and subplot grid (Fig. 1) and the ticks just before saving are replaced, and the suptitle is dropped
(captions are in LaTeX).
Ticks (verdict 15 A1, replacing the 45-degree labels of report 13): x axis of the calibration figures at the five
targets, labelled .90 .93 .95 .97 .98, horizontal; y axis of all three figures at steps of 0.05 in the same form (.85 .90
.95; 1.00 keeps its leading digit). Fig. 2 keeps the locked log cost axis. Legend label of hopkind 2 = ch6lib.POSTGAP_LABEL
(confirm2_figures.KEY replaced in this process only, verdict 14 A2).
Fig. 2 y label (instruction 23 §1): the locked text "worst-group recall t - D(t)" is replaced by mathtext
$t-\bar{D}(t)$ just before saving. Fig. 2, one column (instruction 23 §10): the same f2 with the two panels stacked
(2 x 1, shared x axis, legends inside the panels, y label on both), written to fig_c2_cost_1col.pdf.
Outputs: generated/figures/fig_c2_calibration_2panel.pdf (Fig. 1), fig_c2_cost.pdf (Fig. 2), fig_c2_calibration.pdf (S1),
fig_c2_cost_1col.pdf (Fig. 2 stacked, one column).
"""
import os
import shutil
import sys
import tempfile
from pathlib import Path

PAPER = Path(__file__).resolve().parents[1]
REPO = Path(os.environ.get("CCPILOT_REPO", PAPER.parent))
sys.path.insert(0, str(REPO))
import confirm2_figures as C2F  # noqa: E402  (locked code; imported, not modified)
sys.path.insert(0, str(PAPER / "scripts"))
from ch6lib import POSTGAP_LABEL  # noqa: E402
import matplotlib.figure  # noqa: E402
import matplotlib.ticker as mt  # noqa: E402

OUT = PAPER / "generated" / "figures"
AN = REPO / "results/porto_cctv_confirm2/analysis"
T5 = [0.90, 0.93, 0.95, 0.97, 0.98]
DOT = mt.FuncFormatter(lambda x, _: f"{x:.2f}"[1:] if f"{x:.2f}".startswith("0") else f"{x:.2f}")   # 0.90 -> .90
YLAB_LOCKED, YLAB = "worst-group recall t - D(t)", r"worst-group recall $t-\bar{D}(t)$"


def ticks(save, xtargets):
    def wrapped(fig, path):
        for ax in fig.axes:
            if xtargets:
                ax.set_xticks(T5)
                ax.xaxis.set_major_formatter(DOT)
            ax.yaxis.set_major_locator(mt.MultipleLocator(0.05))
            ax.yaxis.set_major_formatter(DOT)
            if ax.get_ylabel() == YLAB_LOCKED:
                ax.set_ylabel(YLAB)
        return save(fig, path)
    return wrapped


def stacked(save):
    """Fig. 2 in one column: y label on both stacked panels, x label only on the lower one."""
    def wrapped(fig, path):
        top, bottom = fig.axes
        top.set_ylabel(YLAB); bottom.set_ylabel(YLAB); top.set_xlabel("")
        return save(fig, path)
    return wrapped


def main():
    keep_title, keep_save, keep_sub, keep_m = matplotlib.figure.Figure.suptitle, C2F.save, C2F.plt.subplots, list(C2F.F1_METHODS)
    keep_key = dict(C2F.KEY)
    matplotlib.figure.Figure.suptitle = lambda self, *a, **k: None
    C2F.KEY["reacquired"] = C2F.KEY["reacquired"][:2] + (POSTGAP_LABEL,)
    try:
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            C2F.save = ticks(keep_save, True)                                   # Fig. S1: nine panels
            shutil.copyfile(C2F.f1(AN, "combined", td / "s1", "confirm2"), OUT / "fig_c2_calibration.pdf")
            C2F.F1_METHODS = ["static", "mvp_log"]                              # Fig. 1: two panels
            C2F.plt.subplots = lambda *a, **k: keep_sub(1, 2, figsize=(3.5, 2.1), sharex=True, sharey=True, squeeze=False)
            shutil.copyfile(C2F.f1(AN, "combined", td / "f1", "confirm2"), OUT / "fig_c2_calibration_2panel.pdf")
            C2F.F1_METHODS, C2F.plt.subplots = keep_m, keep_sub
            C2F.save = ticks(keep_save, False)                                  # Fig. 2: log cost on x
            shutil.copyfile(C2F.f2(AN, "combined", td / "f2", "confirm2", True), OUT / "fig_c2_cost.pdf")
            C2F.save = stacked(ticks(keep_save, False))                         # Fig. 2: stacked, one column
            C2F.plt.subplots = lambda *a, **k: keep_sub(2, 1, figsize=(3.5, 4.6), sharex=True, sharey=True)
            shutil.copyfile(C2F.f2(AN, "combined", td / "f2c", "confirm2", True), OUT / "fig_c2_cost_1col.pdf")
    finally:
        matplotlib.figure.Figure.suptitle, C2F.save, C2F.plt.subplots, C2F.F1_METHODS = keep_title, keep_save, keep_sub, keep_m
        C2F.KEY.clear(); C2F.KEY.update(keep_key)
    print("[make_fig1_2panel] fig_c2_calibration_2panel.pdf, fig_c2_cost.pdf, fig_c2_calibration.pdf, fig_c2_cost_1col.pdf")


if __name__ == "__main__":
    main()
