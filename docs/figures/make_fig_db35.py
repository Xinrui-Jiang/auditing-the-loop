"""Before/after figure for shot DB-35: round 0 versus the final round 2 take.

Top row: six frames of the round-0 take and the round-0 prompt.
Bottom row: six frames of the round-2 take and the round-2 prompt, with its
sentence-level differences from round 0 marked: added text in green, removed
text in red strikethrough.

Run from the project root:  uv run python docs/figures/make_fig_db35.py
Frames are read from docs/figures/frames_db35/round{0,2}/t<time>s.png and are
extracted with ffmpeg every 0.5 s if that folder is missing.
"""
from __future__ import annotations

import difflib
import json
import re
import subprocess
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib import font_manager  # noqa: E402
from matplotlib.lines import Line2D  # noqa: E402
from PIL import Image, ImageFont  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "runs/loop/DB-35"
FRAMES = ROOT / "docs/figures/frames_db35"
OUT = ROOT / "docs/figures/fig_db35_before_after"
ARIAL = "/System/Library/Fonts/Supplemental/Arial.ttf"

# ---- content -------------------------------------------------------------
ROWS = [
    {"round": 0, "label": "Round 0", "times": [0.0, 1.0, 1.5, 2.5, 4.5, 7.0]},
    {"round": 2, "label": "Round 2, final", "times": [0.0, 1.0, 2.5, 4.5, 5.5, 7.5]},
]
STEP = 0.5          # extraction step in seconds
CLIP_LEN = 8.0

# ---- geometry, inches ----------------------------------------------------
W = 7.0
GAP = 0.03          # white gap between frames
N = 6
FRAME_W = (W - (N - 1) * GAP) / N
FRAME_H = FRAME_W * 864 / 496
LABEL_H = 0.19      # row label band
STAMP_H = 0.13      # time stamps under the frames
TEXT_PAD = 0.03     # gap between stamps and prompt text
ROW_GAP = 0.17      # gap between the two rows
INSET = 0.012       # left/right inset of the prompt text
TOP = 0.01
BOTTOM = 0.03

# ---- style ---------------------------------------------------------------
DARK = "#333333"
MID = "#666666"
LIGHT = "#7a7a7a"
GREEN = "#1b7f3b"
RED = "#b3261e"
PT_LABEL = 8.5
PT_TEXT = 7.0
PT_STAMP = 6.5
LEADING = 1.2       # line height as a multiple of the font size
PARA_GAP = 0.45     # blank-line gap as a multiple of the line height

font_manager.fontManager.addfont(ARIAL)
plt.rcParams.update({
    "font.family": "Arial",
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
    "text.color": DARK,
})

_MEASURE_PX = 700   # measure at a large size, then scale to points
_measure_font = ImageFont.truetype(ARIAL, _MEASURE_PX)


def text_width_in(text: str, pt: float) -> float:
    """Width of `text` in inches at `pt` points, from the Arial metrics."""
    return _measure_font.getlength(text) / _MEASURE_PX * pt / 72 * 1.01


# ---- frames ---------------------------------------------------------------
def ensure_frames(rk: int) -> None:
    folder = FRAMES / f"round{rk}"
    if folder.exists() and any(folder.glob("*.png")):
        return
    folder.mkdir(parents=True, exist_ok=True)
    src = RUN / f"rounds/{rk}/take.mp4"
    t = 0.0
    while t < CLIP_LEN:
        subprocess.run(
            ["ffmpeg", "-v", "error", "-y", "-ss", f"{t:.1f}", "-i", str(src),
             "-frames:v", "1", str(folder / f"t{t:.1f}s.png")],
            check=True,
        )
        t += STEP


def frame_path(rk: int, t: float) -> Path:
    return FRAMES / f"round{rk}" / f"t{t:.1f}s.png"


# ---- sentence-level diff -------------------------------------------------
def units_of_line(line: str) -> list[str]:
    """Split a line into sentence or phrase units.

    A unit ends at a word that ends with . ! or ? once closing quotes are
    stripped, or at a word ending with a colon that introduces a quotation.
    """
    words = line.split()
    units: list[str] = []
    cur: list[str] = []
    for i, w in enumerate(words):
        cur.append(w)
        core = w.rstrip("\"”'’")
        ends_sentence = core.endswith((".", "!", "?"))
        colon_quote = w.endswith(":") and i + 1 < len(words) and words[i + 1][0] in "\"“"
        if ends_sentence or colon_quote:
            units.append(" ".join(cur))
            cur = []
    if cur:
        units.append(" ".join(cur))
    return units


def norm(unit: str) -> str:
    """Comparison key: case, quotes, whitespace and end punctuation ignored."""
    u = unit.lower()
    u = re.sub(r"[\"“”'‘’]", "", u)
    u = re.sub(r"\s+", " ", u).strip()
    u = u.rstrip(".!?:;,")
    return u


def plain_stream(text: str, style: str = "same") -> list[list[tuple[str, str]]]:
    """Lines of (word, style) tokens; an empty list marks a blank line."""
    lines = []
    for line in text.split("\n"):
        lines.append([(w, style) for w in line.split()])
    return lines


def diff_stream(old: str, new: str) -> list[list[tuple[str, str]]]:
    """Token lines for `new`, with removed units of `old` inserted in red."""
    old_units = [u for line in old.split("\n") for u in units_of_line(line)]
    new_lines = new.split("\n")
    new_units: list[tuple[int, str]] = []            # (line index, text)
    for li, line in enumerate(new_lines):
        for u in units_of_line(line):
            new_units.append((li, u))

    style = ["same"] * len(new_units)
    pre_removed: dict[int, list[str]] = {}          # index in new_units -> old units
    tail_removed: list[str] = []
    sm = difflib.SequenceMatcher(
        None, [norm(u) for u in old_units], [norm(u) for _, u in new_units], autojunk=False
    )
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag in ("replace", "insert"):
            for j in range(j1, j2):
                style[j] = "added"
        if tag in ("replace", "delete"):
            if j1 < len(new_units):
                pre_removed.setdefault(j1, []).extend(old_units[i1:i2])
            else:
                tail_removed.extend(old_units[i1:i2])

    lines: list[list[tuple[str, str]]] = [[] for _ in new_lines]
    for j, (li, u) in enumerate(new_units):
        for r in pre_removed.get(j, []):
            lines[li].extend((w, "removed") for w in r.split())
        lines[li].extend((w, style[j]) for w in u.split())
    for r in tail_removed:
        lines[-1].extend((w, "removed") for w in r.split())
    return lines


# ---- text layout ---------------------------------------------------------
COLOR = {"same": DARK, "added": GREEN, "removed": RED, "gray": LIGHT}


def wrap_tokens(tokens: list[tuple[str, str]], max_w: float, pt: float):
    """Greedy wrap. Returns lines of runs; a run is (x_offset, text, style)."""
    space = text_width_in(" ", pt)
    out_lines: list[list[tuple[float, str, str]]] = []
    cur: list[tuple[str, str]] = []
    cur_w = 0.0
    for word, st in tokens:
        ww = text_width_in(word, pt)
        add = ww if not cur else space + ww
        if cur and cur_w + add > max_w:
            out_lines.append(runs_of(cur, pt))
            cur, cur_w = [(word, st)], ww
        else:
            cur.append((word, st))
            cur_w += add
    if cur:
        out_lines.append(runs_of(cur, pt))
    return out_lines


def runs_of(words: list[tuple[str, str]], pt: float) -> list[tuple[float, str, str]]:
    """Merge consecutive same-style words into runs with x offsets."""
    runs: list[tuple[float, str, str]] = []
    x = 0.0
    i = 0
    while i < len(words):
        st = words[i][1]
        j = i
        while j < len(words) and words[j][1] == st:
            j += 1
        text = " ".join(w for w, _ in words[i:j])
        runs.append((x, text, st))
        x += text_width_in(text, pt)
        if j < len(words):
            x += text_width_in(" ", pt)
        i = j
    return runs


def layout_text(lines, max_w: float, pt: float):
    """Wrap every source line; returns (wrapped lines, total height in inches)."""
    line_h = pt / 72 * LEADING
    wrapped: list[list[tuple[float, str, str]] | None] = []
    for tokens in lines:
        if not tokens:
            wrapped.append(None)          # blank line
            continue
        wrapped.extend(wrap_tokens(tokens, max_w, pt))
    height = sum(line_h * PARA_GAP if w is None else line_h for w in wrapped)
    return wrapped, height


def draw_text(fig, H, x0: float, y_top: float, wrapped, pt: float) -> float:
    """Draw wrapped runs with the first baseline below y_top. Returns bottom y."""
    line_h = pt / 72 * LEADING
    ascent = pt / 72 * 0.9
    y = y_top
    for runs in wrapped:
        if runs is None:
            y += line_h * PARA_GAP
            continue
        base = y + ascent
        for xo, text, st in runs:
            fig.text((x0 + xo) / W, 1 - base / H, text, fontsize=pt,
                     color=COLOR[st], ha="left", va="baseline")
            if st == "removed":
                w = text_width_in(text, pt)
                ys = base - pt / 72 * 0.30
                fig.add_artist(Line2D([(x0 + xo) / W, (x0 + xo + w) / W],
                                      [1 - ys / H, 1 - ys / H],
                                      color=RED, linewidth=0.6, solid_capstyle="butt"))
        y += line_h
    return y


def add_image(fig, H, x, y_top, w, h, path):
    ax = fig.add_axes([x / W, 1 - (y_top + h) / H, w / W, h / H])
    ax.imshow(Image.open(path).convert("RGB"), interpolation="antialiased")
    ax.set_axis_off()


# ---- main ----------------------------------------------------------------
def main() -> None:
    traj = json.loads((RUN / "trajectory.json").read_text())
    prompts = {r["round"]: r["prompt"] for r in traj["rounds"]}
    for row in ROWS:
        ensure_frames(row["round"])

    text_w = W - 2 * INSET
    streams = {
        0: plain_stream(prompts[0]),
        2: diff_stream(prompts[0], prompts[2]),
    }
    wrapped = {k: layout_text(v, text_w, PT_TEXT) for k, v in streams.items()}

    row_h = [LABEL_H + FRAME_H + STAMP_H + TEXT_PAD + wrapped[r["round"]][1] for r in ROWS]
    H = TOP + sum(row_h) + ROW_GAP * (len(ROWS) - 1) + BOTTOM

    fig = plt.figure(figsize=(W, H))
    y = TOP
    for row, rh in zip(ROWS, row_h):
        rk = row["round"]
        # row label
        fig.text(INSET / W, 1 - (y + LABEL_H * 0.72) / H, row["label"],
                 fontsize=PT_LABEL, color=DARK, ha="left", va="baseline")
        if rk == 2:
            legend = [("prompt text:", "gray"), ("unchanged", "same"),
                      ("added in round 2", "added"), ("removed from round 0", "removed")]
            sep = text_width_in("   ", PT_TEXT)
            widths = [text_width_in(t, PT_TEXT) for t, _ in legend]
            x = W - INSET - sum(widths) - sep * (len(legend) - 1)
            base = y + LABEL_H * 0.72
            for (t, st), tw in zip(legend, widths):
                fig.text(x / W, 1 - base / H, t, fontsize=PT_TEXT, color=COLOR[st],
                         ha="left", va="baseline")
                if st == "removed":
                    ys = base - PT_TEXT / 72 * 0.30
                    fig.add_artist(Line2D([x / W, (x + tw) / W], [1 - ys / H, 1 - ys / H],
                                          color=RED, linewidth=0.6))
                x += tw + sep
        y += LABEL_H
        # frames and time stamps
        for i, t in enumerate(row["times"]):
            x = i * (FRAME_W + GAP)
            add_image(fig, H, x, y, FRAME_W, FRAME_H, frame_path(rk, t))
            fig.text((x + FRAME_W / 2) / W, 1 - (y + FRAME_H + STAMP_H * 0.78) / H,
                     f"{t:.1f} s", fontsize=PT_STAMP, color=LIGHT,
                     ha="center", va="baseline")
        y += FRAME_H + STAMP_H + TEXT_PAD
        # prompt text
        y = draw_text(fig, H, INSET, y, wrapped[rk][0], PT_TEXT)
        y += ROW_GAP

    fig.savefig(OUT.with_suffix(".png"), dpi=300, facecolor="white")
    fig.savefig(OUT.with_suffix(".pdf"), facecolor="white")
    print(f"figure {W:.2f} x {H:.2f} in; frame {FRAME_W:.3f} x {FRAME_H:.3f} in")
    for rk in (0, 2):
        n = sum(1 for w in wrapped[rk][0] if w is not None)
        print(f"round {rk}: {n} text lines, {wrapped[rk][1]:.2f} in")
    print(OUT.with_suffix(".png"))


if __name__ == "__main__":
    main()
