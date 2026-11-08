"""Before/after filmstrip figure: take 1 vs final take for three shots.

Run from the project root:
    uv run python docs/figures/make_fig_before_after.py

Reads frames from docs/figures/frames/<shot>/round<k>_t<sec>s.png (extracted
with ffmpeg from runs/loop/<shot>/rounds/<k>/take.mp4) and writes
docs/figures/fig_before_after.{png,pdf}.
"""

from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
from PIL import Image, ImageFont

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[2]
FRAMES = ROOT / "docs" / "figures" / "frames"
OUT = ROOT / "docs" / "figures" / "fig_before_after"

# ---- content -------------------------------------------------------------
TIMES = [2, 5, 7]  # seconds, same for every shot and both takes
SHOTS = [
    {
        "id": "DB-38",
        "final_round": 1,
        "text": (
            "Take 1: the portfolio stays on her lap and nothing scatters. "
            "Final take: the portfolio slips from her grasp and pages scatter, "
            "including the rain-shredded resume."
        ),
    },
    {
        "id": "SB-01",
        "final_round": 2,
        "text": (
            "Take 1: Julian already stands in the room and never enters. "
            "Final take: Julian enters the space and walks through the living room."
        ),
    },
    {
        "id": "DB-60",
        "final_round": 2,
        "text": (
            "Take 1: the assistant and Jiang Yao are absent, she does not cry, "
            "and captions appear on screen. "
            "Final take: both are visible in power suits as Ruan Ningxia sees them, "
            "and she cries."
        ),
    },
]

# ---- geometry (inches) ----------------------------------------------------
W = 7.0
LEFT_COL = 1.22       # text column
PAD = 0.04            # inner padding of the text column
GAP = 0.03            # white gap between frames inside a group
GAP_GROUP = 0.20      # gap between the take-1 group and the final-take group
HEADER_H = 0.20       # group labels
STAMP_H = 0.13        # time stamps under frames
ROW_GAP = 0.12
TOP = 0.02
BOTTOM = 0.02

N = len(TIMES)
FRAME_W = (W - LEFT_COL - 2 * (N - 1) * GAP - GAP_GROUP) / (2 * N)
FRAME_H = FRAME_W * 864 / 496
ROW_H = FRAME_H + STAMP_H
H = TOP + HEADER_H + len(SHOTS) * ROW_H + (len(SHOTS) - 1) * ROW_GAP + BOTTOM

# ---- style ---------------------------------------------------------------
FONT = "Arial"
DARK = "#333333"
MID = "#555555"
LIGHT = "#777777"
PT_ID = 8.5
PT_LABEL = 7.5
PT_TEXT = 6.5
PT_STAMP = 6.0

plt.rcParams.update({
    "font.family": FONT,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "text.color": DARK,
})

_measure_font = ImageFont.truetype(
    "/System/Library/Fonts/Supplemental/Arial.ttf", int(round(PT_TEXT / 72 * 300))
)


def wrap(text: str, max_in: float) -> list[str]:
    """Greedy word wrap using measured Arial widths at 300 dpi."""
    max_px = max_in * 300
    lines, cur = [], ""
    for word in text.split():
        trial = word if not cur else cur + " " + word
        if _measure_font.getlength(trial) <= max_px:
            cur = trial
        else:
            lines.append(cur)
            cur = word
    if cur:
        lines.append(cur)
    return lines


def add_image(fig, x, y_top, w, h, path):
    """Place an image with its top-left corner at (x, y_top) in inches."""
    ax = fig.add_axes([x / W, 1 - (y_top + h) / H, w / W, h / H])
    ax.imshow(Image.open(path).convert("RGB"), interpolation="antialiased")
    ax.set_axis_off()


def main():
    fig = plt.figure(figsize=(W, H))

    x_frames = LEFT_COL
    group_w = N * FRAME_W + (N - 1) * GAP
    x_group = [x_frames, x_frames + group_w + GAP_GROUP]

    # group labels
    y_label = TOP + HEADER_H * 0.45
    for gx, label in zip(x_group, ["Take 1, round 0", "Final take"]):
        fig.text((gx + group_w / 2) / W, 1 - y_label / H, label,
                 ha="center", va="center", fontsize=PT_LABEL, color=DARK)

    for r, shot in enumerate(SHOTS):
        y0 = TOP + HEADER_H + r * (ROW_H + ROW_GAP)
        rounds = [0, shot["final_round"]]

        # frames and time stamps
        for g, rk in enumerate(rounds):
            for i, t in enumerate(TIMES):
                x = x_group[g] + i * (FRAME_W + GAP)
                add_image(fig, x, y0, FRAME_W, FRAME_H,
                          FRAMES / shot["id"] / f"round{rk}_t{t}s.png")
                fig.text((x + FRAME_W / 2) / W, 1 - (y0 + FRAME_H + STAMP_H * 0.55) / H,
                         f"{t} s", ha="center", va="center",
                         fontsize=PT_STAMP, color=LIGHT)

        # left text column
        tx = PAD
        line_h = PT_TEXT / 72 * 1.28
        y = y0 + 0.02
        fig.text(tx / W, 1 - y / H, shot["id"], ha="left", va="top",
                 fontsize=PT_ID, color=DARK)
        y += PT_ID / 72 * 1.35
        fig.text(tx / W, 1 - y / H, f"final take: round {shot['final_round']}",
                 ha="left", va="top", fontsize=PT_TEXT, color=LIGHT)
        y += PT_TEXT / 72 * 1.3 + 0.07
        for line in wrap(shot["text"], LEFT_COL - PAD - 0.08):
            fig.text(tx / W, 1 - y / H, line, ha="left", va="top",
                     fontsize=PT_TEXT, color=MID)
            y += line_h

    fig.savefig(OUT.with_suffix(".png"), dpi=300, facecolor="white")
    fig.savefig(OUT.with_suffix(".pdf"), facecolor="white")
    print(f"figure {W:.2f} x {H:.2f} in; frame {FRAME_W:.3f} x {FRAME_H:.3f} in")
    print(OUT.with_suffix(".png"))


if __name__ == "__main__":
    main()
