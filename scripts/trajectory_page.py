"""Render the trajectories under runs/loop into one page: prompt -> take -> feedback sheet, round by round,
with the Analyser's reasoning and the final outcome. Videos are linked by relative path (local viewing);
pass --video-url-map <json> to substitute uploaded asset URLs."""
from __future__ import annotations

import difflib
import html
import json
import re
import sys
from pathlib import Path

from loopauditor.schemas import Checklist, FeedbackSheet, Trajectory

ROOT = Path(__file__).resolve().parents[1]
LOOP = ROOT / "runs/loop"
OUT = ROOT / "docs/pages/trajectories.html"

CSS = """
/* layout: one page, one section per shot; rounds as a horizontal strip of cards (prompt, take, sheet) */
:root{--bg:#fbfaf7;--fg:#1f2328;--muted:#5f6670;--line:#dcdad3;--card:#f3f1ea;--panel:#ffffff;--ok:#1a7f37;--bad:#b42318;--warn:#8a6100;--accent:#2f5d9e;--add:#e3f3e8;--del:#fbe9e7;
  --display:"IBM Plex Sans",-apple-system,Segoe UI,Helvetica,Arial,sans-serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#15171b;--fg:#e6e6e3;--muted:#9aa0a8;--line:#30343b;--card:#1d2026;--panel:#23272e;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24;--accent:#8ab4ff;--add:#17311f;--del:#3a1d1a;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#15171b;--fg:#e6e6e3;--muted:#9aa0a8;--line:#30343b;--card:#1d2026;--panel:#23272e;--ok:#4ade80;--bad:#f87171;--warn:#fbbf24;--accent:#8ab4ff;--add:#17311f;--del:#3a1d1a;color-scheme:dark}
body{margin:0;padding-block:24px;padding-left:max(16px,env(safe-area-inset-left,0px));padding-right:max(16px,env(safe-area-inset-right,0px));background:var(--bg);color:var(--fg);font:15px/1.5 var(--display)}
main{max-width:1600px;margin:0 auto}h1{font-size:24px;margin:0 0 4px;text-wrap:balance}h2{font-size:18px;margin:36px 0 8px;padding-top:16px;border-top:2px solid var(--line)}
.sub{color:var(--muted);margin:0 0 12px;max-width:70ch}.badge{display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;color:#fff;vertical-align:middle;letter-spacing:.02em}
.out{background:var(--ok)}.hand{background:var(--warn)}.run{background:var(--accent)}
.rounds{display:flex;gap:14px;overflow-x:auto;padding-bottom:12px}
.round{flex:0 0 min(420px,88vw);min-width:0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px}
.round h3{margin:0 0 6px;font-size:15px}.round video{width:100%;max-width:100%;max-height:460px;background:#000;border-radius:6px}
pre{margin:6px 0;padding:8px;font:12px/1.4 var(--mono);white-space:pre-wrap;word-break:break-word;background:var(--panel);border:1px solid var(--line);border-radius:6px;max-height:260px;overflow:auto}
.diff .add{background:var(--add)}.diff .del{background:var(--del);text-decoration:line-through}
.tbl{overflow-x:auto}table{border-collapse:collapse;width:100%;font-size:12px;font-variant-numeric:tabular-nums}td,th{border-bottom:1px solid var(--line);padding:3px 5px;text-align:left;vertical-align:top}
tr.block td{color:var(--bad);font-weight:600}tr.pass td.s{color:var(--ok)}
details summary{cursor:pointer;color:var(--muted);font-size:13px}.k{color:var(--muted);font-size:12px}
"""


def sentences(text: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?\"])\s+|\n", text) if s.strip()]


def prompt_diff(old: str, new: str) -> str:
    a, b = sentences(old), sentences(new)
    out = []
    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(None, a, b).get_opcodes():
        if tag == "equal":
            out += [html.escape(s) for s in a[i1:i2]]
        if tag in ("delete", "replace"):
            out += [f'<span class="del">{html.escape(s)}</span>' for s in a[i1:i2]]
        if tag in ("insert", "replace"):
            out += [f'<span class="add">{html.escape(s)}</span>' for s in b[j1:j2]]
    return " ".join(out)


def sheet_table(sheet: FeedbackSheet) -> str:
    rows = []
    blocking = {v.item_id for v in sheet.blocking()}
    for v in sheet.verdicts:
        cls = "block" if v.item_id in blocking else ("pass" if v.status == "pass" else "")
        ev = html.escape((v.evidence[0] if v.evidence else "")[:160])
        rows.append(f"<tr class='{cls}'><td>{v.item_id}</td><td class='s'>{v.status}</td><td>{v.severity}</td><td>{v.uncertainty_state}</td><td>{v.fixability}</td><td>{ev}</td></tr>")
    return "<table><tr><th>item</th><th>status</th><th>severity</th><th>uncertainty</th><th>fixability</th><th>evidence (first source)</th></tr>" + "".join(rows) + "</table>"


def render_shot(shot_dir: Path, video_url: dict[str, str]) -> str:
    tr = Trajectory.model_validate_json((shot_dir / "trajectory.json").read_text())
    cl = Checklist.model_validate_json((shot_dir / "checklist.json").read_text())
    sheets = [FeedbackSheet.model_validate_json((ROOT / r.sheet_path).read_text()) for r in tr.rounds]
    total = sum(r.cost_usd for r in tr.rounds)
    badge = {"output": ("out", f"OUTPUT: round {tr.output_round}"), "hand_off": ("hand", f"HAND-OFF: best round {tr.output_round}"), "running": ("run", "running")}[tr.status]
    handoff = ""
    if (shot_dir / "handoff.json").exists():
        h = json.loads((shot_dir / "handoff.json").read_text())
        handoff = f"<p><b>Hand-off reason:</b> {html.escape(h['reason'])} Open items: {', '.join(h['open_item_ids']) or 'none'}</p>"
    cards = []
    for r, sheet in zip(tr.rounds, sheets):
        take = Path(r.take_path)
        rel = (take.relative_to(ROOT) if take.is_absolute() else take).as_posix()  # paths are stored as the CLI received them
        src = video_url.get(rel, "../../" + rel)
        parent = tr.rounds[r.branched_from].prompt if r.branched_from is not None else None
        prompt_html = f"<div class='diff'>{prompt_diff(parent, r.prompt)}</div>" if parent else html.escape(r.prompt)
        reasoning = f"<details><summary>Analyser's reasoning for this round · targets {', '.join(r.targets) or '—'}</summary><pre>{html.escape(r.rationale)}</pre></details>" if r.rationale else "<p class='k'>round 0: the original prompt</p>"
        blocking = [v.item_id for v in sheet.blocking()]
        cards.append(f"""<div class="round"><h3>Round {r.round}{'' if r.branched_from is None else f' <span class="k">(branched from round {r.branched_from})</span>'}</h3>
<video controls preload="metadata" src="{src}"></video>
<p class="k">take ${r.cost_usd - sheet.cost_usd:.2f} · verification ${sheet.cost_usd:.3f} · blocking: {', '.join(blocking) or 'none'}</p>
<details open><summary>prompt {'(changes vs round ' + str(r.branched_from) + ' marked)' if parent else ''}</summary><pre>{prompt_html}</pre></details>
{reasoning}
<details><summary>feedback sheet ({len(sheet.verdicts)} items)</summary><div class="tbl">{sheet_table(sheet)}</div></details></div>""")
    items = "\n".join(f"{i.id} [{i.kind}, {i.priority}] {i.text}" for i in cl.items)
    return f"""<h2>{html.escape(tr.shot_id)} <span class="badge {badge[0]}">{badge[1]}</span></h2>
<p class="sub">{len(tr.rounds)} round(s) · total ${total:.2f} · checklist {len(cl.items)} items</p>{handoff}
<details><summary>checklist (written once at round 0)</summary><pre>{html.escape(items)}</pre></details>
<div class="rounds">{''.join(cards)}</div>"""


INTRO = ("Each card is one round: the prompt the Analyser sent (changes against the round it branched from are marked), "
         "the take, and the feedback sheet. Red rows block the output.")
FONTS = '<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:wght@400;600&family=IBM+Plex+Mono&display=swap">'


def main() -> None:
    video_url: dict[str, str] = {}
    if len(sys.argv) > 2 and sys.argv[1] == "--video-url-map":
        video_url = json.loads(Path(sys.argv[2]).read_text())
    shots = sorted(p for p in LOOP.iterdir() if (p / "trajectory.json").exists())
    body = "".join(render_shot(p, video_url) for p in shots)
    page = f"<main><h1>LoopAuditor trajectories</h1><p class='sub'>{INTRO}</p>{body}</main>"
    OUT.write_text(f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>"
                   f"<title>LoopAuditor Trajectories</title>{FONTS}<style>{CSS}</style></head><body>{page}</body></html>")
    # the artifact version: no document skeleton (the publisher adds it), asset URLs for the videos
    (OUT.parent / "trajectories_artifact.html").write_text(
        f"<title>LoopAuditor Trajectories</title>{FONTS}<style>{CSS}</style>{page}")
    print(f"wrote {OUT} (+ artifact version) for {len(shots)} shot(s)")


if __name__ == "__main__":
    main()
