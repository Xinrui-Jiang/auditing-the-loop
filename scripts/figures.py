"""Figures for the report: data distribution of the prompt set and the loop results. PNG + PDF in docs/figures/.
Colours follow the validated reference palette (categorical slots blue/orange/aqua; sequential blue ramp)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from loopauditor.schemas import FeedbackSheet, Trajectory  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "docs/figures"
CAT = ["#2a78d6", "#eb6834", "#1baf7a"]  # categorical slots 1-3
SEQ = ["#86b6ef", "#2a78d6", "#104281"]  # ordinal: calm < strong < exaggerated
INK, INK2, GRID = "#0b0b0b", "#52514e", "#e1e0d9"
SOURCES = ["DramaBench", "SEAM-Bench", "FilmBench"]
BINS = ["calm", "strong", "exaggerated"]
EMOTIONS = ["anger", "sadness", "fear", "surprise", "happiness", "contempt"]
plt.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Helvetica Neue", "Arial", "DejaVu Sans"], "font.size": 9,
                     "axes.edgecolor": "#c3c2b7", "axes.labelcolor": INK2, "xtick.color": INK2, "ytick.color": INK2,
                     "axes.spines.top": False, "axes.spines.right": False, "figure.dpi": 150})


def rows(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.open()]


def save(fig, name: str) -> None:
    fig.tight_layout()
    fig.savefig(OUT / f"{name}.png", dpi=300, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)


def fig_source_by_bin(r90, r30):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.6), sharey=False)
    for ax, data, title in ((axes[0], r90, "All 90 shots"), (axes[1], r30, "30-shot working set")):
        counts = {s: Counter(x["native_intensity_bin"] for x in data if x["source_dataset"] == s) for s in SOURCES}
        left = [0] * len(SOURCES)
        for b, colour in zip(BINS, SEQ):
            vals = [counts[s][b] for s in SOURCES]
            ax.barh(SOURCES, vals, left=left, color=colour, edgecolor="white", linewidth=2, height=0.55, label=b)
            for i, (v, l) in enumerate(zip(vals, left)):
                if v >= 3:
                    ax.text(l + v / 2, i, str(v), ha="center", va="center", color="white" if b != "calm" else INK, fontsize=8)
            left = [l + v for l, v in zip(left, vals)]
        for i, s in enumerate(SOURCES):
            ax.text(left[i] + 0.8, i, str(left[i]), va="center", color=INK2, fontsize=8)
        ax.set_title(title, loc="left", color=INK, fontsize=10)
        ax.invert_yaxis()
        ax.xaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.set_xlabel("shots")
    axes[0].legend(title="native intensity bin", frameon=False, loc="lower right", fontsize=8, title_fontsize=8)
    save(fig, "fig_source_by_bin")


def fig_emotion_heatmap(r90):
    grid = [[sum(1 for x in r90 if x["native_intensity_bin"] == b and x["emotion_class"] == e) for e in EMOTIONS] for b in BINS]
    fig, ax = plt.subplots(figsize=(6.4, 2.3))
    im = ax.imshow(grid, cmap=matplotlib.colors.LinearSegmentedColormap.from_list("blue", ["#fcfcfb", "#cde2fb", "#2a78d6", "#0d366b"]), aspect="auto")
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            ax.text(j, i, str(v), ha="center", va="center", color="white" if v >= 7 else INK, fontsize=9)
    ax.set_xticks(range(len(EMOTIONS)), EMOTIONS)
    ax.set_yticks(range(len(BINS)), BINS)
    ax.set_title("Emotion class × native intensity bin (90 shots)", loc="left", color=INK, fontsize=10)
    for s in ax.spines.values():
        s.set_visible(False)
    fig.colorbar(im, ax=ax, fraction=0.03, pad=0.02).set_label("shots", color=INK2)
    save(fig, "fig_emotion_by_bin")


def fig_funnel():
    # counts from data/prompts/prompt_set_v2_manifest.md §2 and the 30-shot manifest
    funnels = {
        "DramaBench": [("dialogue candidates", 5948), ("native intensity bin", 2774), ("+ emotion class", 1773), ("eligible after drops", 1025), ("in prompt set", 69), ("in working set", 22)],
        "SEAM-Bench": [("dialogue cues", 132), ("after episode exclusion", 97), ("eligible after drops", 19), ("bin + emotion class", 7), ("in prompt set", 7), ("in working set", 3)],
        "FilmBench": [("one-quote segments", 1869), ("strictly single speaker", 628), ("live action", 261), ("3–12-word quote", 170), ("intensity cue", 134), ("eligible after drops", 17), ("in prompt set", 14), ("in working set", 5)],
    }
    fig, axes = plt.subplots(1, 3, figsize=(9.6, 2.8))
    for ax, (src, steps), colour in zip(axes, funnels.items(), CAT):
        labels = [s for s, _ in steps]
        vals = [v for _, v in steps]
        ax.barh(labels, vals, color=colour, height=0.6, edgecolor="white", linewidth=1)
        ax.set_xscale("log")
        ax.invert_yaxis()
        for i, v in enumerate(vals):
            ax.text(v * 1.15, i, f"{v:,}", va="center", color=INK2, fontsize=8)
        ax.set_xlim(1, max(vals) * 6)
        ax.set_title(src, loc="left", color=INK, fontsize=10)
        ax.xaxis.grid(True, color=GRID, linewidth=0.6, which="major")
        ax.set_axisbelow(True)
        ax.tick_params(axis="y", labelsize=8)
    axes[0].set_xlabel("count (log scale)")
    save(fig, "fig_filter_funnel")


def fig_lengths(r90):
    fig, axes = plt.subplots(1, 2, figsize=(7.2, 2.3))
    line_words = [len(x["line"].split()) for x in r90]
    prompt_words = [len(x["prompt"].split()) for x in r90]
    axes[0].hist(line_words, bins=range(3, 14), color=CAT[0], edgecolor="white", linewidth=1.5, rwidth=1.0)
    axes[0].set_title("Spoken line length (words)", loc="left", color=INK, fontsize=10)
    axes[1].hist(prompt_words, bins=range(40, 130, 10), color=CAT[0], edgecolor="white", linewidth=1.5)
    axes[1].set_title("Prompt length (words)", loc="left", color=INK, fontsize=10)
    for ax in axes:
        ax.yaxis.grid(True, color=GRID, linewidth=0.6)
        ax.set_axisbelow(True)
        ax.set_ylabel("shots")
    save(fig, "fig_lengths")


def fig_loop():
    loop = ROOT / "runs/loop"
    shots = sorted(p for p in loop.iterdir() if (p / "trajectory.json").exists())
    fig, axes = plt.subplots(1, 2, figsize=(7.6, 2.6), gridspec_kw={"width_ratios": [3, 2]})
    ax = axes[0]
    palette = ["#2a78d6", "#eb6834", "#1baf7a", "#eda100", "#e87ba4"]
    round0 = Counter()
    ends: dict[tuple[int, int], list[str]] = {}
    for i, (p, colour) in enumerate(zip(shots, palette)):
        tr = Trajectory.model_validate_json((p / "trajectory.json").read_text())
        sheets = [FeedbackSheet.model_validate_json((ROOT / r.sheet_path).read_text()) for r in tr.rounds]
        ys = [len(s.blocking()) for s in sheets]
        round0.update(v.item_id.split(".")[0] for v in sheets[0].blocking())
        jitter = (i - 2) * 0.05  # identical paths (DB-60 and SB-01) would otherwise hide each other
        ax.plot(range(len(ys)), [y + jitter for y in ys], color=colour, linewidth=2, marker="o", markersize=5, label=tr.shot_id)
        end = "output" if tr.status == "output" else "hand-off"
        ends.setdefault((len(ys) - 1, ys[-1]), []).append(f"{tr.shot_id} · {end}")
    for (x, y), labels in ends.items():
        for j, label in enumerate(labels):  # stack labels that share an endpoint
            ax.annotate(label, (x, y), textcoords="offset points", xytext=(8, 9 * (len(labels) - 1) / 2 - 9 * j), fontsize=7.5, color=INK2, va="center")
    ax.set_xlabel("round")
    ax.set_ylabel("blocking items")
    ax.set_xlim(-0.2, 6.5)
    ax.set_xticks(range(0, 5))
    ax.yaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    ax.set_title("Blocking items per round, 5 shots", loc="left", color=INK, fontsize=10)
    ax = axes[1]
    checks = [c for c, _ in round0.most_common()]
    ax.barh(checks, [round0[c] for c in checks], color=CAT[0], height=0.6, edgecolor="white")
    for i, c in enumerate(checks):
        ax.text(round0[c] + 0.15, i, str(round0[c]), va="center", color=INK2, fontsize=8)
    ax.invert_yaxis()
    ax.set_title("What blocked at round 0", loc="left", color=INK, fontsize=10)
    ax.set_xlabel("items")
    ax.xaxis.grid(True, color=GRID, linewidth=0.6)
    ax.set_axisbelow(True)
    save(fig, "fig_loop_results")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    r90 = rows(ROOT / "data/prompts/prompt_set_v2.jsonl")
    r30 = rows(ROOT / "data/prompts/prompt_set_v2_30.jsonl")
    fig_source_by_bin(r90, r30)
    fig_emotion_heatmap(r90)
    fig_funnel()
    fig_lengths(r90)
    fig_loop()
    names = sorted(p.name for p in OUT.glob("*.png"))
    cards = "".join(f"<figure><img src='{n}' alt='{n}'><figcaption>{n}</figcaption></figure>" for n in names)
    (OUT / "index.html").write_text("<!doctype html><meta charset='utf-8'><title>LoopAuditor figures</title>"
                                    "<style>body{font-family:system-ui;margin:24px;background:#fcfcfb;color:#0b0b0b}figure{margin:0 0 28px}img{max-width:100%;border:1px solid #e1e0d9}figcaption{color:#52514e;font-size:13px}</style>"
                                    f"<h1>LoopAuditor figures</h1>{cards}")
    print("wrote", names)


if __name__ == "__main__":
    main()
