"""Extract single-line shot candidates from FutureMa/DramaBench (MIT, 1,103 English short-drama scripts, Fountain format).

A candidate = one dialogue line (3-12 words) that carries a parenthetical acting direction, plus the
scene heading and the preceding action line. Verified 2026-11-02: 5,948 candidates from 1,041 scripts.

Usage: uv run python scripts/extract_dramabench_shots.py data/sources/dramabench/dramabench_continuation_1103.jsonl [N]
"""
from __future__ import annotations
import collections, json, random, re, sys

def extract(path: str) -> list[dict]:
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    cands = []
    for r in rows:
        lines = r["full_script"].split("\n")
        heading = None; last_action = None; i = 0
        while i < len(lines):
            ln = lines[i].strip()
            if re.match(r"^(INT\.|EXT\.|INT/EXT)", ln):
                heading = ln; i += 1; continue
            if ln and ln.isupper() and not ln.startswith(("INT", "EXT")) and len(ln) < 40 and i + 1 < len(lines):
                par = None; j = i + 1
                if lines[j].strip().startswith("("):
                    par = lines[j].strip().strip("()"); j += 1
                if j < len(lines) and lines[j].strip() and not lines[j].strip().isupper():
                    dlg = lines[j].strip()
                    if par and 3 <= len(dlg.split()) <= 12 and heading:
                        cands.append(dict(script=r["id"], title=r["title"], setting=heading, speaker=ln.title(),
                                          parenthetical=par, line=dlg, preceding_action=(last_action or "")[:200]))
                    i = j + 1; continue
            if ln and not ln.isupper():
                last_action = ln
            i += 1
    return cands

if __name__ == "__main__":
    cands = extract(sys.argv[1])
    n = int(sys.argv[2]) if len(sys.argv) > 2 else 5
    print(f"{len(cands)} candidates from {len({c['script'] for c in cands})} scripts")
    print("top parentheticals:", collections.Counter(c["parenthetical"] for c in cands).most_common(12))
    random.seed(7)
    for c in random.sample(cands, n):
        print(json.dumps(c, ensure_ascii=False, indent=1))
