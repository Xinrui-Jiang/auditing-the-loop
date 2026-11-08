"""Render one module's inspection page: inputs on the left, outputs on the right (PLAN.md §7)."""
from __future__ import annotations

import html
from dataclasses import dataclass, field


@dataclass
class Panel:
    label: str
    body: str  # preformatted text or JSON


@dataclass
class Section:
    title: str
    note: str
    inputs: list[Panel] = field(default_factory=list)
    outputs: list[Panel] = field(default_factory=list)


CSS = """
:root{--bg:#fff;--fg:#1b1b1f;--muted:#5c5f66;--line:#d9dbe0;--in:#f3f6fb;--out:#f4faf4;--accent:#2a5bd7}
@media (prefers-color-scheme:dark){:root{--bg:#121316;--fg:#e8e8ea;--muted:#a0a3aa;--line:#33363c;--in:#1a2030;--out:#182218;--accent:#8ab4ff}}
body{margin:0;padding:24px 16px;background:var(--bg);color:var(--fg);font:15px/1.5 -apple-system,Segoe UI,Helvetica,Arial,sans-serif}
main{max-width:1500px;margin:0 auto}
h1{font-size:22px;margin:0 0 4px}h2{font-size:17px;margin:32px 0 6px;padding-top:16px;border-top:1px solid var(--line)}
.sub,.note{color:var(--muted);margin:0 0 12px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:16px}
@media (max-width:900px){.cols{grid-template-columns:1fr}}
.col h3{font-size:12px;letter-spacing:.08em;text-transform:uppercase;color:var(--muted);margin:0 0 8px}
.panel{border:1px solid var(--line);border-radius:8px;margin-bottom:12px;overflow:hidden}
.panel .label{padding:6px 10px;font-weight:600;font-size:13px;border-bottom:1px solid var(--line)}
.in .panel .label{background:var(--in)}.out .panel .label{background:var(--out)}
pre{margin:0;padding:10px;font:12.5px/1.45 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre-wrap;word-break:break-word;max-height:520px;overflow:auto}
"""


def _panels(panels: list[Panel]) -> str:
    return "".join(
        f'<div class="panel"><div class="label">{html.escape(p.label)}</div><pre>{html.escape(p.body)}</pre></div>'
        for p in panels
    )


def render(title: str, subtitle: str, sections: list[Section]) -> str:
    parts = [f"<!doctype html><html><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'>",
             f"<title>{html.escape(title)}</title><style>{CSS}</style></head><body><main>",
             f"<h1>{html.escape(title)}</h1><p class='sub'>{html.escape(subtitle)}</p>"]
    for s in sections:
        parts.append(f"<h2>{html.escape(s.title)}</h2><p class='note'>{html.escape(s.note)}</p><div class='cols'>")
        parts.append(f"<div class='col in'><h3>Input</h3>{_panels(s.inputs)}</div>")
        parts.append(f"<div class='col out'><h3>Output</h3>{_panels(s.outputs)}</div></div>")
    parts.append("</main></body></html>")
    return "".join(parts)
