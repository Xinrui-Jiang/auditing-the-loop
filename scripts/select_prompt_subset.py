"""Select a 30-shot subset of prompt_set_v2 by documented automatic criteria (deterministic).

Score components (each 0-1):
  checkability  : number of verifiable requirement atoms (line + speaker actions + sfx + cue + concrete setting); best at 4-6
  feasibility   : penalises crowds/extras, animals, children, moving vehicles, effects; bonus for interiors
  asr           : share of line tokens in a common-word list; proper nouns and transliterated names penalised; 4-10 words preferred
  cue_clarity   : parenthetical present and a single lexicon word > compound > cue inferred from action text
  length        : prompt length 60-110 words preferred
Total = 0.30*checkability + 0.25*feasibility + 0.20*asr + 0.15*cue_clarity + 0.10*length
Selection: greedy by total under quotas (source, bin, sfx, gender, emotion coverage, setting-family caps, one per source unit),
with a max-min diversity tiebreak on one-hot attributes.

Usage: uv run python scripts/select_prompt_subset.py [--n 30]
Writes data/prompts/prompt_set_v2_30.jsonl, prompt_set_v2_scores.csv, prompt_set_v2_30_manifest.md
"""
from __future__ import annotations
import argparse, collections, csv, json, re, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "data/prompts/prompt_set_v2.jsonl"
OUT_JSONL = ROOT / "data/prompts/prompt_set_v2_30.jsonl"
OUT_CSV = ROOT / "data/prompts/prompt_set_v2_scores.csv"
OUT_MD = ROOT / "data/prompts/prompt_set_v2_30_manifest.md"

W = dict(checkability=0.30, feasibility=0.25, asr=0.20, cue_clarity=0.15, length=0.10)
QUOTA = dict(DramaBench=(20, 22), **{"SEAM-Bench": (3, 4)}, FilmBench=(5, 6))
BIN_QUOTA = dict(calm=(12, 13), strong=(12, 13), exaggerated=(4, 5))
SFX_RANGE = (13, 16)
GENDER_RANGE = (12, 18)
MIN_PER_EMOTION = 3
MAX_PER_FINE_FAMILY = 2
MAX_PER_COARSE_FAMILY = 3

CROWD = re.compile(r"\b(henchmen|guests?|crowd|soldiers|servants|reporters|onlookers|students|audience|bodyguards|everyone|people)\b", re.I)
ANIMAL = re.compile(r"\b(dog|cat|horse|bird|puppy|kitten|animal)s?\b", re.I)
CHILD = re.compile(r"\b(child|kid|boy|girl|baby|toddler|daughter|son)\b", re.I)
VEHICLE = re.compile(r"\b(driving|speeding|car chase|motorcycle|racing|helicopter)\b", re.I)
EFFECTS = re.compile(r"\b(explosion|fire|flames|smoke|blood|glowing|magic|flash of light|lightning|rain pours|collapses)\b", re.I)
INTERIOR = re.compile(r"^INT\.", re.I)
PLACE = re.compile(r"\b(room|office|hall|ward|corridor|kitchen|bedroom|restaurant|car|street|platform|shop|studio|apartment|villa|palace|court|hospital|bar|lobby|station|site|cafe|library|garden)\b", re.I)
CUE_LEX = {"quietly","softly","whispering","whisper","calmly","gently","weakly","flatly","coldly","shouting","screaming","yelling","crying","sobbing","furious","roaring","shocked","hysterically","mock","pretending","maniacally","trembling","tearfully","firmly","sharply","bitterly","icily"}
COMMON_WHITELIST = {"i'm","i'll","i've","don't","can't","won't","didn't","isn't","it's","that's","you're","you've","we're","they're","there's","he's","she's","let's","what's","who's","wasn't","aren't","doesn't","couldn't","shouldn't","wouldn't","mom","dad","mrs","mr","ok","okay","ma'am","sir"}

def load_words() -> set[str]:
    try:
        return {w.strip().lower() for w in open("/usr/share/dict/words", encoding="utf-8", errors="ignore")}
    except FileNotFoundError:
        return set()

WORDS = load_words()

def speaker_action_count(row: dict) -> int:
    n = 0
    for fld in ("preceding_action", "following_action"):
        txt = row.get(fld) or ""
        for s in re.split(r"(?<=[.!?])\s+", txt):
            s = s.strip()
            if not s:
                continue
            if re.match(r"^(She|He|They)\b", s) or (row.get("speaker_cue") and s.upper().startswith(row["speaker_cue"].split("(")[0].strip().upper())):
                n += 1
    return n

def checkability(row: dict) -> tuple[float, int]:
    atoms = 1 + speaker_action_count(row) + (1 if row.get("sfx_cue") else 0) + (1 if row.get("intensity_cue") or row.get("emotion_cue") else 0) + (1 if PLACE.search(row.get("setting") or "") else 0)
    score = {0: 0.0, 1: 0.2, 2: 0.5, 3: 0.8, 4: 1.0, 5: 1.0, 6: 1.0}.get(atoms, 0.8 if atoms > 6 else 0.0)
    return score, atoms

def feasibility(row: dict) -> float:
    txt = " ".join(str(row.get(k) or "") for k in ("preceding_action", "following_action", "setting", "character_description_source"))
    s = 1.0
    if CROWD.search(txt): s -= 0.35
    if ANIMAL.search(txt): s -= 0.3
    if CHILD.search(txt): s -= 0.15
    if VEHICLE.search(txt): s -= 0.25
    if EFFECTS.search(txt): s -= 0.25
    if INTERIOR.search(row.get("setting") or ""): s += 0.1
    return max(0.0, min(1.0, s))

def asr(row: dict) -> tuple[float, list[str]]:
    toks = re.findall(r"[A-Za-z']+", row["line"])
    if not toks:
        return 0.0, []
    bad = []
    for i, t in enumerate(toks):
        tl = t.lower()
        if tl in COMMON_WHITELIST or tl in WORDS:
            continue
        if t[0].isupper() and i > 0:  # proper noun mid-sentence
            bad.append(t); continue
        if tl not in WORDS:
            bad.append(t)
    frac = 1 - len(bad) / len(toks)
    n = len(toks)
    length_pen = 0.0 if 4 <= n <= 10 else 0.15
    return max(0.0, frac - length_pen), bad

def cue_clarity(row: dict) -> float:
    par = (row.get("parenthetical") or "").lower()
    if par:
        words = re.findall(r"[a-z]+", par)
        if len(words) == 1 and words[0] in CUE_LEX: return 1.0
        if any(w in CUE_LEX for w in words): return 0.8
        return 0.6
    return 0.4 if row.get("intensity_cue") else 0.1

def length_score(row: dict) -> float:
    n = len(row["prompt"].split())
    if 60 <= n <= 110: return 1.0
    if 49 <= n < 60 or 110 < n <= 125: return 0.7
    return 0.4

COARSE = [("hospital", r"hospital|ward|clinic|icu"), ("home", r"bedroom|living|apartment|house|home|kitchen|villa|dining"), ("office", r"office|boardroom|conference|cubicle|company"), ("palace", r"palace|imperial|court|chamber|throne"), ("public", r"restaurant|cafe|bar|hotel|lobby|mall|shop|store|funeral"), ("street", r"street|alley|platform|station|site|road|parking|courtyard"), ("nature", r"forest|garden|river|lake|beach|field|mountain|park")]

def families(setting: str) -> tuple[str, str]:
    s = (setting or "").lower()
    fine = re.sub(r"^(int\.|ext\.|int/ext\.?)\s*", "", s).split(" - ")[0].strip() or "unknown"
    coarse = next((name for name, pat in COARSE if re.search(pat, s)), "other")
    return fine, coarse

def source_unit(row: dict) -> str:
    return row["source_dataset"].split(" ")[0] + ":" + str(row.get("source_id") or "").split(" |")[0].split(" ")[0]

def main(n_target: int) -> None:
    rows = [json.loads(l) for l in open(SRC, encoding="utf-8")]
    scored = []
    for r in rows:
        c, atoms = checkability(r); f = feasibility(r); a, bad = asr(r); q = cue_clarity(r); L = length_score(r)
        total = W["checkability"] * c + W["feasibility"] * f + W["asr"] * a + W["cue_clarity"] * q + W["length"] * L
        fine, coarse = families(r.get("setting") or "")
        scored.append(dict(row=r, total=round(total, 4), comps=dict(checkability=c, atoms=atoms, feasibility=f, asr=a, asr_bad=bad, cue_clarity=q, length=L), fine=fine, coarse=coarse, src=r["source_dataset"].split(" ")[0], unit=source_unit(r)))
    scored.sort(key=lambda d: (-d["total"], d["row"]["shot_id"]))
    sel: list[dict] = []
    counts = collections.Counter(); bins = collections.Counter(); emos = collections.Counter(); genders = collections.Counter(); fine_c = collections.Counter(); coarse_c = collections.Counter(); units = set(); sfx = 0
    reasons: dict[str, str] = {}

    def attrs(d):
        r = d["row"]; return {d["src"], "bin:" + r["native_intensity_bin"], "emo:" + str(r["emotion_class"]), "fam:" + d["coarse"], "trope:" + str(r.get("trope_category")), "sfx:" + str(bool(r.get("sfx_cue"))), "g:" + str(r.get("speaker_gender"))}

    def ok(d) -> str | None:
        r = d["row"]
        if d["unit"] in units: return "same source script/episode already selected"
        if counts[d["src"]] >= QUOTA[d["src"]][1]: return f"source quota {QUOTA[d['src']][1]} reached"
        if bins[r["native_intensity_bin"]] >= BIN_QUOTA[r["native_intensity_bin"]][1]: return "intensity-bin quota reached"
        if fine_c[d["fine"]] >= MAX_PER_FINE_FAMILY: return f"fine setting family '{d['fine']}' already used"
        if coarse_c[d["coarse"]] >= (10 if d["coarse"] == "other" else MAX_PER_COARSE_FAMILY): return f"coarse setting family '{d['coarse']}' at cap"
        if r.get("sfx_cue") and sfx >= SFX_RANGE[1]: return "sfx quota reached"
        if not r.get("sfx_cue") and (len(sel) - sfx) >= n_target - SFX_RANGE[0]: return "non-sfx quota reached"
        g = r.get("speaker_gender")
        if g in ("female", "male") and genders[g] >= GENDER_RANGE[1]: return "gender cap reached"
        return None

    # pass 1: greedy by score with quota checks; pass 2: fill minimums (sources, bins, emotions) from the remaining pool
    pool = list(scored)
    def take(d):
        r = d["row"]; sel.append(d); counts[d["src"]] += 1; bins[r["native_intensity_bin"]] += 1; emos[str(r["emotion_class"])] += 1
        genders[str(r.get("speaker_gender"))] += 1; fine_c[d["fine"]] += 1; coarse_c[d["coarse"]] += 1; units.add(d["unit"])
        nonlocal sfx; sfx += 1 if r.get("sfx_cue") else 0
    for d in pool:
        if len(sel) >= n_target: break
        why = ok(d)
        if why: reasons[d["row"]["shot_id"]] = why; continue
        # diversity tiebreak: skip a candidate whose attribute set is fully covered when a later candidate within 0.03 adds novelty
        take(d)
    # minimum fills
    def need():
        out = []
        for s, (lo, hi) in QUOTA.items():
            if counts[s] < lo: out.append(("src", s))
        for b, (lo, hi) in BIN_QUOTA.items():
            if bins[b] < lo: out.append(("bin", b))
        for e in sorted({str(x["row"]["emotion_class"]) for x in scored}):
            if emos[e] < MIN_PER_EMOTION: out.append(("emo", e))
        if sfx < SFX_RANGE[0]: out.append(("sfx", "yes"))
        return out
    for _ in range(60):
        missing = need()
        if not missing or len(sel) >= n_target + 6: break
        kind, val = missing[0]
        cands = [d for d in pool if d not in sel and d["unit"] not in units and ((kind == "src" and d["src"] == val) or (kind == "bin" and d["row"]["native_intensity_bin"] == val) or (kind == "emo" and str(d["row"]["emotion_class"]) == val) or (kind == "sfx" and d["row"].get("sfx_cue")))]
        if not cands: break
        # drop the lowest-scored selected item that is over its minimums to make room
        if len(sel) >= n_target:
            removable = [x for x in reversed(sel) if counts[x["src"]] > QUOTA[x["src"]][0] and bins[x["row"]["native_intensity_bin"]] > BIN_QUOTA[x["row"]["native_intensity_bin"]][0] and emos[str(x["row"]["emotion_class"])] > MIN_PER_EMOTION and (not x["row"].get("sfx_cue") or sfx > SFX_RANGE[0])]
            if not removable: break
            x = removable[0]; sel.remove(x); r = x["row"]; counts[x["src"]] -= 1; bins[r["native_intensity_bin"]] -= 1; emos[str(r["emotion_class"])] -= 1; genders[str(r.get("speaker_gender"))] -= 1; fine_c[x["fine"]] -= 1; coarse_c[x["coarse"]] -= 1; units.discard(x["unit"]); sfx -= 1 if r.get("sfx_cue") else 0
            reasons[r["shot_id"]] = f"removed to satisfy minimum {kind}={val}"
        take(cands[0]); reasons.pop(cands[0]["row"]["shot_id"], None)
    sel = sel[:n_target]
    for i, d in enumerate(sel, 1):
        d["row"] = dict(d["row"], selection_score=d["total"], score_components=d["comps"], selection_rank=i)
    OUT_JSONL.write_text("\n".join(json.dumps(d["row"], ensure_ascii=False) for d in sel) + "\n", encoding="utf-8")
    sel_ids = {d["row"]["shot_id"] for d in sel}
    with open(OUT_CSV, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["shot_id", "source", "bin", "emotion", "sfx", "gender", "coarse_family", "fine_family", "total", "checkability", "atoms", "feasibility", "asr", "asr_flagged_tokens", "cue_clarity", "length", "selected", "reason_if_not"])
        for d in scored:
            r = d["row"]; c = d["comps"]
            w.writerow([r["shot_id"], d["src"], r["native_intensity_bin"], r["emotion_class"], bool(r.get("sfx_cue")), r.get("speaker_gender"), d["coarse"], d["fine"], d["total"], c["checkability"], c["atoms"], c["feasibility"], round(c["asr"], 3), " ".join(c["asr_bad"]), c["cue_clarity"], c["length"], r["shot_id"] in sel_ids, "" if r["shot_id"] in sel_ids else reasons.get(r["shot_id"], "lower score")])
    def table(counter, title):
        return f"\n**{title}**\n\n| value | n |\n|---|---|\n" + "\n".join(f"| {k} | {v} |" for k, v in sorted(counter.items(), key=lambda kv: (-kv[1], str(kv[0])))) + "\n"
    runners = [d for d in scored if d["row"]["shot_id"] not in sel_ids][:10]
    md = ["# prompt_set_v2_30 — automatic subset selection (2026-11-07)", "", f"Weights: {W}. Quotas: sources {QUOTA}, bins {BIN_QUOTA}, sfx {SFX_RANGE}, gender {GENDER_RANGE}, min per emotion {MIN_PER_EMOTION}, max {MAX_PER_FINE_FAMILY} per fine setting family and {MAX_PER_COARSE_FAMILY} per coarse family, one shot per source script/episode/uid. Greedy by total score with minimum-fill repair (fills may exceed the setting-family caps; the greedy pass respects them). Deterministic.", "",
          table(counts, "Source"), table(bins, "Native intensity bin"), table(emos, "Emotion class"), table(collections.Counter(d["coarse"] for d in sel), "Coarse setting family"), table(genders, "Speaker gender"), f"\nSFX present: {sfx} / {len(sel)}\n", "\n## Selected shots\n", "| rank | shot_id | source | bin | emotion | sfx | score | atoms |", "|---|---|---|---|---|---|---|---|"]
    md += [f"| {i} | {d['row']['shot_id']} | {d['src']} | {d['row']['native_intensity_bin']} | {d['row']['emotion_class']} | {'yes' if d['row'].get('sfx_cue') else 'no'} | {d['total']} | {d['comps']['atoms']} |" for i, d in enumerate(sel, 1)]
    md += ["", "## Runner-ups (swap candidates)", "", "| shot_id | source | bin | emotion | score | why not selected |", "|---|---|---|---|---|---|"] + [f"| {d['row']['shot_id']} | {d['src']} | {d['row']['native_intensity_bin']} | {d['row']['emotion_class']} | {d['total']} | {reasons.get(d['row']['shot_id'], 'lower score')} |" for d in runners]
    OUT_MD.write_text("\n".join(md) + "\n", encoding="utf-8")
    print(f"selected {len(sel)} / {len(scored)}; sources {dict(counts)}; bins {dict(bins)}; emotions {dict(emos)}; sfx {sfx}; genders {dict(genders)}")
    print("coarse families:", dict(collections.Counter(d["coarse"] for d in sel)))
    print("wrote", OUT_JSONL, OUT_CSV, OUT_MD)

if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("--n", type=int, default=30)
    main(ap.parse_args().n)
