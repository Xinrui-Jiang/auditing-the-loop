"""Build prompt_set_v2: up to 90 DISTINCT single-speaker English dialogue shots, verbatim source text only.

Rule of the set: every rendered prompt = source text (verbatim) + a fixed technical frame + minimal glue.
Nothing else is authored. Emotion class and intensity bin come from the SOURCE's own acting cues
(parenthetical / adjacent action line / storyboard cue); no rewriting, no variants.

Deterministic (SEED = 20261103). No network, no paid API. Run from the avharness repo root:

    uv run python scripts/build_prompt_set_v2.py             # build + validate + write jsonl/manifest
    uv run python scripts/build_prompt_set_v2.py --explore   # pool statistics only

Inputs (all local):
  data/sources/dramabench/dramabench_candidates_native.jsonl  native bin / emotion / SFX labels (5,948 rows)
  data/sources/dramabench/dramabench_continuation_1103.jsonl  full scripts (verbatim spans, first-appearance lines)
  data/sources/seambench/dramas/his-toyboy/director/epNN.csv  lines + parenthetical + 景别/拍摄角度/运镜
  data/sources/seambench/dramas/his-toyboy/script/episodes/epNN_en.txt  heading + preceding action + intro line
  data/sources/filmbench/filmbench_single_speaker_segments.jsonl  one-quote shot segments with flags
  data/sources/filmbench/filmbench_prompts_en.csv              raw FilmBench rows (verbatim check)
Outputs:
  data/prompts/prompt_set_v2.jsonl, data/prompts/prompt_set_v2_manifest.md
  Each row carries `prompt` (header + source spans + whitelist glue + footer) and `prompt_raw` (the same source spans
  only, one per line, in source order). Speaker cues are rendered verbatim: no name substitution (user decision 2026-11-07).

Intensity intervals from docs/DESIGN_v2.md section 7: calm [0,1], strong [2,3], exaggerated/comedic [3,4].
Lexicons (calm / strong / exaggerated / six emotion classes / SFX regexes / ambiguous words) are the ones that
produced dramabench_candidates_native.jsonl (research_notes/数据侧最终复核/sources_deep_dive.md, Task 5), copied
here so SEAM-Bench and FilmBench are labelled by the same rule.
"""
from __future__ import annotations

import argparse
import collections
import csv
import difflib
import glob
import io
import json
import random
import re
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO / "scripts"))
from build_prompt_set import (  # noqa: E402  (v1 helpers only: regex tables, sha256, tables, excerpts)
    DICT_WORDS, FEMALE_ROLE, MALE_ROLE, PHONE_ACTION, PHONE_LINE, classify_trope, cross_table,
    excerpt_around, infer_gender, script_names, setting_family, sha256, table, words,
)

SEED = 20261103
DATE = "2026-11-07"
TARGETS = {"DramaBench": 60, "SEAM-Bench": 15, "FilmBench": 15}
EMOTIONS = ["anger", "sadness", "fear", "surprise", "happiness", "contempt"]
BINS = ["calm", "strong", "exaggerated"]
INTERVALS = {"calm": [0, 1], "strong": [2, 3], "exaggerated": [3, 4]}
EXAG_TARGET_DB = 12          # DramaBench exaggerated target (supply-capped)
MAX_PER_FAMILY = 2           # fine setting family, DramaBench
SFX_TARGET_DB = 30           # prefer SFX candidates until this many DramaBench shots carry one
MAX_UNKNOWN_GENDER_DB = 4
WORD_RANGE = (40, 160)
SEAM_EXCLUDED_EPISODES = {1, 2, 7, 8, 9}
SEAM_MAX_PER_EPISODE = 2
SEAM_MAX_PER_SPEAKER = 6
FB_MAX_PER_GENRE = 3

DB_CANDS = REPO / "data/sources/dramabench/dramabench_candidates_native.jsonl"
DB_SCRIPTS = REPO / "data/sources/dramabench/dramabench_continuation_1103.jsonl"
SEAM_DIR = REPO / "data/sources/seambench/dramas/his-toyboy"
FB_SEGS = REPO / "data/sources/filmbench/filmbench_single_speaker_segments.jsonl"
FB_RAW = REPO / "data/sources/filmbench/filmbench_prompts_en.csv"
OUT_JSONL = REPO / "data/prompts/prompt_set_v2.jsonl"
OUT_MANIFEST = REPO / "data/prompts/prompt_set_v2_manifest.md"

SOURCE_META = {
    "DramaBench": dict(license="MIT (HF README; provenance caveat: paper says scripts come from an "
                               "'english_short_drama_scripts_dataset' whose license is never named)",
                       url="https://huggingface.co/datasets/FutureMa/DramaBench",
                       file="data/sources/dramabench/dramabench_continuation_1103.jsonl"),
    "SEAM-Bench": dict(license="CC BY-NC 4.0", url="https://huggingface.co/datasets/Jackyqq/SEAM-Bench",
                       file="data/sources/seambench/dramas/his-toyboy/"),
    "FilmBench": dict(license="Apache-2.0", url="https://huggingface.co/datasets/skylenage/FilmBench",
                      file="data/sources/filmbench/filmbench_prompts_en.csv"),
}
NEGATIVE_PROMPT = "background music, subtitles, on-screen text"
RAW_NOTE = "prompt = header + source spans + whitelist glue + footer; prompt_raw = source spans only"

# ----------------------------------------------------------------------------------------------
# The fixed whitelist of non-source text. Every string the renderer may emit that is not a verbatim
# source span must be in this table. Speaker cues (personal names and role nouns) are verbatim source spans:
# no name substitution (user decision 2026-11-07).
# ----------------------------------------------------------------------------------------------
HEADER = "Vertical 9:16 framing, head and shoulders fill the frame, subject centred. "
SCALE_DEFAULT = "medium close-up"
CAMERA_DEFAULT = "static camera, eye level"
FOOTER = "Live-action short-drama look. Audio on; the line is spoken on camera."
SFX_LEAD = "Sound: "
SEAM_DICT = {  # fixed Chinese -> English dictionary for the director CSV fields (景别 / 拍摄角度 / 运镜)
    "景别": {
        "大特写": "extreme close-up", "特写": "close-up", "近景": "medium close-up", "近": "medium close-up",
        "中近景": "medium close-up", "中近": "medium close-up", "中景": "medium shot", "中": "medium shot",
        "小全": "medium long shot", "小全景": "medium long shot", "全景": "wide shot", "全": "wide shot",
    },
    "拍摄角度": {
        "平视": "eye level", "微微仰视": "slight low angle", "仰视": "low angle", "微微俯视": "slight high angle",
        "俯视": "high angle", "俯拍": "high angle", "微微俯拍": "slight high angle", "仰拍": "low angle",
        "侧面": "profile", "微微侧面": "slight profile", "正面": "frontal", "微微倾斜": "slight Dutch tilt",
        "过肩": "over-the-shoulder", "过手机拍": "framed past the phone", "过手机": "framed past the phone",
        "过窗户": "through the window",
    },
    "运镜": {
        "固定镜头": "static camera", "固定": "static camera", "缓推": "slow push-in", "缓拉": "slow pull-back",
        "缓慢横移": "slow lateral tracking", "横移": "lateral tracking", "微微晃动": "slight handheld shake",
        "跟摇": "tracking pan", "跟": "tracking shot", "升格": "slow motion", "缓慢移": "slow camera move",
        "快推": "fast push-in", "推": "push-in", "拉": "pull-back", "摇": "pan", "环绕": "orbit",
    },
}
SEAM_OTS = ("over-the-shoulder", r"^过(朱利安|维克多|维克托|赛琳娜|瑟瑞娜|米洛|迈洛|哈珀|佩奇|艾玛|埃莉诺|经理|收银员)(关系)?$")
SEAM_NAME_PREFIX = r"^(朱利安|维克多|维克托|赛琳娜|瑟瑞娜|米洛|迈洛|哈珀|佩奇|艾玛|埃莉诺)"
GLUE = {  # key -> exact string
    "HEADER": HEADER,
    "SCALE_DEFAULT": SCALE_DEFAULT,
    "CAMERA_DEFAULT": CAMERA_DEFAULT,
    "FOOTER": FOOTER,
    "SFX_LEAD": SFX_LEAD,
    "says": " says: \"",            # {role} says: "{line}"
    "says {parenthetical}": " says ",  # {role} says {parenthetical}: "{line}"
    "{parenthetical}, says": ", ",     # {role}, {parenthetical}, says: "{line}"
    "colon-quote": ": \"",
    "close-quote": "\"",
    "comma": ", ",
    "period": ".",
    "space": " ",
    "newline": "\n",
}
for _field, _d in SEAM_DICT.items():
    for _zh, _en in _d.items():
        GLUE[f"SEAM:{_field}:{_zh}"] = _en
GLUE["SEAM:拍摄角度:过X关系"] = SEAM_OTS[0]
GLUE["SEAM:to-connector"] = " to "
WHITELIST = sorted(set(GLUE.values()), key=len, reverse=True)

# ----------------------------------------------------------------------------------------------
# Lexicons (verbatim copy of the deep-dive labeller that produced dramabench_candidates_native.jsonl)
# ----------------------------------------------------------------------------------------------
CALM = ["quietly","softly","whispering","whispers","whisper","calmly","gently","weakly","flatly","quiet","soft","low","in a low voice","low voice","murmuring","murmurs","murmur","mutters","muttering","mutter","under his breath","under her breath","hushed","evenly","numbly","faintly","tenderly","barely audible","barely a whisper","subdued","hoarsely","half-whisper","half to himself","half to herself","almost inaudible","voice low","voice soft","voice quiet","matter-of-fact","matter-of-factly","deadpan","coldly","icily","cold","flat","tired","wearily","exhausted","resigned","breathless","breathlessly","slowly","measured","level","steady","steadily","composed"]
STRONG = ["shouting","shouts","shout","screaming","screams","scream","yelling","yells","yell","crying","cries","sobbing","sobs","sob","furious","furiously","roaring","roars","roar","shocked","slamming","slams","slam","snaps","snapping","angrily","enraged","raging","bellowing","bellows","bursting","bursts out","explodes","exploding","outraged","desperate","desperately","frantically","frantic","trembling","shaking","choking","choked","choking up","gasping","gasps","tearfully","through tears","voice breaking","breaking","cracking","voice cracking","pleading","begging","panicked","panicking","terrified","horrified","stunned","loudly","loud","raising voice","voice rising","raising her voice","raising his voice","harshly","fiercely","sharply","sharp","hissing","hisses","spitting","spits","growling","growls","snarling","snarls","shrieking","shrieks","howling","howls","wailing","wails","screeching","exploding","violently","seething","shaken","voice shaking","shaking with rage","fuming","heated","heatedly","vehemently","forcefully","thundering","booming","barking","barks","in tears","tears streaming","breaking down","collapsing","hysterical"]
EXAG = ["hysterically","over the top","over-the-top","cackling","cackles","cackle","wailing dramatically","dramatically","melodramatic","melodramatically","mock-","theatrical","theatrically","laughing uncontrollably","laughing hysterically","bursting into laughter","burst out laughing","bursts out laughing","howling with laughter","giggling uncontrollably","exaggerated","exaggeratedly","overdramatic","over-dramatic","flamboyant","flamboyantly","singsong","sing-song","sing song","squealing","squeals","gleefully","giddy","giddily","comically","comic","whining","whiny","whines","pouting","pouts","flailing","swooning","swoons","feigning","feigned","fake","faking","pretending","overly","gushing","gushes","chirpily","chirps","chirpy","bubbly","squeaking","squeaks","with exaggerated","dramatic gasp","dramatic sigh","clutching his chest","clutching her chest","clutching pearls","wide-eyed innocence","batting her eyelashes","batting eyelashes","in a baby voice","baby voice","cutesy","sarcastically sweet","sickly sweet","sweetly sarcastic","mock horror","mock surprise","mock offended","mock serious","mock-horror","mock-surprise","mock-offense","mock-innocence","mock-sympathy","mock-concern","mock-pity","mock-salute","mock-bow","mock-gasp","mock-whisper","mock-indignation","mock-despair","mock-solemnity","mock-formal","mock-casual","mock-serious","mock-offended","mock-innocent","mock-outraged","mock-stern","ham","hamming","playing it up","milking it","theatrical sigh","theatrical gasp","laughing maniacally","maniacal","maniacally","manic","manically","unhinged"]
EMO = {
 "anger":["angry","angrily","anger","furious","furiously","fury","rage","enraged","irritated","irritation","annoyed","annoyance","snapping","snaps","gritted teeth","through gritted teeth","hissing","hisses","growling","growls","snarling","snarls","seething","bitterly","bitter","fuming","exasperated","exasperation","harshly","sharply","glaring","glares","glare","slams","slamming","frustrated","frustration","outraged","indignant","indignantly","heated","hostile","accusing","accusingly","accusatory","resentful","resentment","spitting","venomous","venom","raging","livid","clenched","clenching","jaw tight","jaw clenched","shouting","shouts","yelling","yells","roaring","roars","bellows","bellowing","barking","barks","explodes","exploding","losing it","temper"],
 "sadness":["sad","sadly","sadness","tears","tearful","tearfully","crying","cries","cry","sobbing","sobs","sob","weeping","weeps","voice breaking","voice cracking","choking up","choked up","choked","grief","grieving","mournful","mourning","heartbroken","heartbreak","broken","brokenly","wistful","wistfully","melancholy","regret","regretful","hurt","pained","pain","devastated","numb","numbly","sniffling","sniffles","trembling lip","lip trembling","despair","despairing","hopeless","hopelessly","dejected","defeated","forlorn","sorrow","sorrowful","miserable","in tears","eyes welling","welling up","wiping tears","wipes tears","wipes her eyes","wipes his eyes","eyes red","red-eyed","lonely","loneliness","ashamed","guilty","guilt","apologetic","apologetically","disappointed","disappointment","heavy","heavily","sighs","sighing","sigh","quietly devastated","breaking down","collapses","crumbling","aching","longing","wistful","mourn","weary","wearily","tired","exhausted","resigned","resignation"],
 "fear":["afraid","scared","frightened","terrified","terror","fearful","fear","nervous","nervously","nervousness","anxious","anxiously","anxiety","panicked","panicking","panic","trembling","tremble","trembles","shaking","shakes","shaky","shakily","alarmed","alarm","uneasy","unease","dread","horrified","horror","stammering","stammers","stutters","stuttering","worried","worry","worriedly","frantic","frantically","desperate","desperately","pleading","pleads","begging","begs","cowering","cowers","flinches","flinching","backing away","backs away","wary","warily","cautious","cautiously","hesitant","hesitantly","hesitates","gulps","swallows hard","swallowing hard","breath catching","holding her breath","holding his breath","petrified","frozen","freezes","paralyzed","jittery","jumpy","startled","timid","timidly","intimidated","threatened","unsettled","uncertain","uncertainly","shrinks","shrinking"],
 "surprise":["surprised","surprise","shocked","shock","stunned","startled","astonished","astonishment","amazed","amazement","disbelief","in disbelief","incredulous","incredulously","bewildered","bewilderment","gasping","gasps","gasp","wide-eyed","eyes widen","eyes widening","eyes wide","jaw drops","jaw dropping","mouth agape","mouth falls open","taken aback","blinking","blinks","dumbfounded","speechless","stares","staring","stunned silence","does a double take","double-take","confused","confusion","puzzled","baffled","perplexed","what?","realization","realizing","realises","realizes","dawning","can't believe","cannot believe","freezing","freezes mid","stops short","stops dead","caught off guard","unexpected","sudden","suddenly"],
 "happiness":["happy","happily","happiness","smiling","smiles","smile","grinning","grins","grin","laughing","laughs","laugh","laughter","giggling","giggles","giggle","chuckling","chuckles","chuckle","delighted","delight","joyful","joy","joyfully","excited","excitedly","excitement","cheerful","cheerfully","beaming","beams","relieved","relief","warmly","warm","gleeful","thrilled","pleased","amused","amusement","playful","playfully","teasing","teases","fondly","fond","affectionately","affectionate","tenderly","tender","lovingly","loving","brightly","bright","brightening","lights up","eyes light up","elated","overjoyed","ecstatic","content","contented","satisfied","proud","proudly","eager","eagerly","enthusiastic","enthusiastically","hopeful","hopefully","grateful","gratefully","touched","moved","lightly","lighthearted","jokingly","joking","jokes","wryly","wry","smirking","smirks","smirk","flirtatious","flirting","flirty","coy","coyly","sweetly","sweet","gently teasing","winking","winks"],
 "contempt":["contempt","contemptuous","contemptuously","disdain","disdainful","disdainfully","sneering","sneers","sneer","scoffing","scoffs","scoff","mocking","mockingly","mocks","mock","sarcastic","sarcastically","sarcasm","coldly","cold","icily","icy","dismissive","dismissively","dismisses","condescending","condescendingly","patronizing","patronising","smug","smugly","scornful","scorn","scornfully","derisive","derisively","snorts","snort","rolling her eyes","rolling his eyes","rolls her eyes","rolls his eyes","eye roll","haughty","haughtily","arrogantly","arrogant","dryly","dry","superior","superiority","looking down","looks down on","disgusted","disgust","disgustedly","revulsion","repulsed","curling her lip","lip curling","curls his lip","sniffs","sniffing","unimpressed","bored","boredom","indifferent","indifferently","cutting","cuttingly","withering","with a withering","belittling","taunting","taunts","jeering","jeers","sardonic","sardonically","cynical","cynically","flat","flatly","deadpan","matter-of-fact","matter-of-factly","aloof","coolly","cool"],
}
SFX_PATTERNS = [r"door\s+slams?", r"slams?\s+the\s+door", r"door\s+(?:bangs?|bursts?\s+open|flies\s+open|swings\s+open|creaks?|clicks?\s+shut|closes?\s+with)", r"phones?\s+(?:rings?|ringing|buzz(?:es|ing)?|vibrat(?:es|ing)|chimes?|beeps?|pings?|dings?)", r"ringtone", r"(?:glass|vase|plate|cup|mug|bottle|mirror|window)\s+(?:shatters?|shattering|breaks?|smashes?|crashes?)\b", r"shatters?\b", r"\bslaps?\b", r"\bslapping\b", r"car\s+horn", r"\bhonks?\b", r"\bhonking\b", r"\bthunder\b", r"\bgunshots?\b", r"\bgunfire\b", r"\bknocks?\b", r"\bknocking\b", r"\bdoorbell\b", r"\bsirens?\b", r"\balarm\b", r"\bcrash(?:es|ing)?\b", r"\bclatters?\b", r"\bclattering\b", r"\bbangs?\b", r"\bbanging\b", r"\bfootsteps\b", r"\bengine\b", r"tires?\s+(?:screech|squeal)", r"\bscreech(?:es|ing)?\b", r"\bexplosion\b", r"\bexplodes\b", r"\bapplause\b", r"\bclapping\b", r"\bclaps\b", r"\bmusic\b", r"\bringing\b", r"\bbeeps?\b", r"\bbeeping\b", r"\bbarks?\b", r"\bbarking\b", r"\brain\b", r"\bwind\s+(?:howls?|howling|whistles?)", r"\bglass\s+breaking\b", r"\bsmash(?:es|ing)?\b", r"\bpounds?\s+(?:on|the)\b", r"\bpounding\b", r"\bthuds?\b", r"\bthudding\b", r"\bsplash(?:es|ing)?\b", r"\bgasps?\s+(?:from|around|in the)\b", r"\bmurmurs?\s+(?:from|around|ripple)\b", r"\bwhispers\s+(?:spread|ripple)\b", r"\bcheers?\b", r"\bcheering\b", r"\bscreams?\s+(?:from|offscreen|off-screen|outside)\b", r"\bchatter\b", r"\bcommotion\b", r"\btv\b", r"\btelevision\b", r"\bradio\b", r"\bspeaker(?:s)?\b", r"\bloudspeaker\b", r"\bintercom\b", r"\bnotification\b", r"\bchimes?\b", r"\bbell\b", r"\bclinks?\b", r"\bclinking\b", r"\bsizzl(?:es|ing)\b", r"\bsplatters?\b", r"\bsnaps?\s+(?:shut|closed)\b", r"\bslam(?:s|med|ming)?\s+(?:down|his|her|the|a)\b", r"\bthrows?\b.*\b(?:floor|wall|ground)\b", r"\bsmack(?:s|ed|ing)?\b", r"\bpunch(?:es|ed|ing)?\b", r"\bkicks?\b.*\b(?:door|table|chair)\b", r"\bkicks?\s+over\b", r"\bdrops?\s+(?:the|her|his|a)\b.*\b(?:tray|glass|plate|phone|cup|bowl)\b", r"\btears\s+(?:the|up|apart)\b", r"\brips?\b", r"\bstomps?\b", r"\bstomping\b", r"\bheels?\s+click", r"\bclick(?:s|ing)?\s+of\s+heels", r"\bcamera\s+(?:shutters?|flash)", r"\bshutter\b", r"\bflashes\b", r"\bhorns?\b", r"\btraffic\b", r"\bwaves\b", r"\bbirds\b", r"\bclock\s+(?:ticks|ticking|chimes)", r"\bticking\b"]
SFX_RE = [re.compile(p, re.I) for p in SFX_PATTERNS]
# matches that are not reliably a sound (camera flash / background music / the sea vs a hand wave / crying "tears")
SFX_NOT_SOUND = {"flashes", "music", "tv", "television", "radio", "speaker", "speakers", "loudspeaker", "intercom",
                 "shutter", "waves", "camera flash", "tears the", "tears up", "tears apart", "notification", "birds"}
FIGURATIVE = re.compile(r"\b(smile|expression|face|heart|memories|memory|world|silence|composure|facade|illusion|hope|dream|mask|patience|confidence|"
                        r"mind|nerves|spirit|resolve|soul|pride|ego|the wind from|wind out of|voice)\b", re.I)
FIG_VERBS = {"shatters", "shatter", "crash", "crashes", "cracks", "crack", "breaks", "break", "snaps", "snap", "knocks", "knock", "explodes", "smashes"}
AMBIG = {"sharp","cold","low","flat","light","heavy","cutting","broken","pain","breaking","cracking","steady","level","measured","tired","exhausted","frozen","freezes","freezing","stares","staring","suddenly","sudden","unexpected","bright","dry","cool","soft","quiet","composed","content","grave","hurt","blank","relaxed","still","firm","stern","dark","collapses","shaken","sharply","heated","bitter","barks","barking","slams","slamming","slam","snaps","snapping","bursting","explodes","exploding","shattering"}


def find_words(text: str, lex: list[str], skip_ambig: bool = False) -> list[str]:
    low = text.lower()
    return [w for w in lex if not (skip_ambig and w in AMBIG) and re.search(r"(?<![a-z-])" + re.escape(w) + r"(?![a-z])", low)]


def label(par: str, act: str = "") -> tuple[str, list[str], str, str | None, list[str], str]:
    """Same rule as the deep-dive labeller: parenthetical first, adjacent action second (ambiguous words off)."""
    ex, st, ca = find_words(par, EXAG), find_words(par, STRONG), find_words(par, CALM)
    src = "parenthetical"
    if not (ex or st or ca):
        ex, st, ca = find_words(act, EXAG, True), find_words(act, STRONG, True), find_words(act, CALM, True)
        src = "action"
    if ex: b, cue = "exaggerated", ex
    elif st: b, cue = "strong", st
    elif ca: b, cue = "calm", ca
    else: b, cue, src = "unbinned", [], ""
    hits = {k: find_words(par, v) for k, v in EMO.items()}; hits = {k: v for k, v in hits.items() if v}
    esrc = "parenthetical"
    if not hits:
        hits = {k: find_words(act, v, True) for k, v in EMO.items()}; hits = {k: v for k, v in hits.items() if v}
        esrc = "action"
    if hits:
        text = (par + " " + act).lower()
        ecls = min(hits, key=lambda k: min(text.find(w) for w in hits[k]))
        ecue = hits[ecls]
    else:
        ecls, ecue, esrc = None, [], ""
    return b, cue, src, ecls, ecue, esrc


def sfx_sentence(*texts: str) -> tuple[str | None, str | None]:
    """First sentence in the given action texts that carries a sound cue (returns sentence, matched cue)."""
    for t in texts:
        if not t:
            continue
        for sent in re.split(r"(?<=[.!?])\s+", t):
            for rx in SFX_RE:
                m = rx.search(sent)
                if m and m.group(0).lower() not in SFX_NOT_SOUND:
                    if m.group(0).lower().split()[-1] in FIG_VERBS and FIGURATIVE.search(sent):
                        continue  # 'her smile shatters', 'memories crash like waves'
                    return sent.strip(), m.group(0)
    return None, None


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


def sentence_split(t: str) -> list[str]:
    return [s for s in re.split(r"(?<=[.!?])\s+", t) if s]


# ----------------------------------------------------------------------------------------------
# Prompt segments: ("source", text, file_key) | ("glue", text, glue_key)
# ----------------------------------------------------------------------------------------------
class Prompt:
    def __init__(self):
        self.segs: list[tuple[str, str, str]] = []

    def src(self, text: str, file_key: str):
        assert text, "empty source span"
        self.segs.append(("source", text, file_key)); return self

    def glue(self, key: str):
        self.segs.append(("glue", GLUE[key], key)); return self

    def text(self) -> str:
        return "".join(t for _, t, _ in self.segs)

    def glue_keys(self) -> list[str]:
        seen = []
        for k, _, key in self.segs:
            if k == "glue" and key not in seen:
                seen.append(key)
        return seen


ADVERB_PAREN = re.compile(r"^(?:[a-z-]+ly|almost [a-z-]+ly|very [a-z-]+ly|[a-z-]+ly(?:,| and| but) [a-z-]+ly|[a-z-]+ly but [a-z-]+ly)$")


CONTD = re.compile(r"\s*\(CONT'D\)\s*$")


def rendered_cue(cue: str) -> str:
    """Speaker cue as rendered: the verbatim cue line minus a trailing (CONT'D) continuation marker; the name or role
    noun is itself a verbatim source span. No name substitution (user decision 2026-11-07)."""
    return CONTD.sub("", cue).strip()


def raw_lines(setting: str, intro: str | None, pre: str, cue: str, paren: str | None, line: str, fol: str | None = None) -> list[str]:
    """prompt_raw: the source spans used in the prompt, in source order, one per line; no header, footer or glue."""
    out = [setting]
    if intro:
        out.append(intro)
    out += [pre, cue]
    if paren:
        out.append("(" + paren + ")")
    out.append(line)
    if fol:
        out.append(fol)
    return out


def speech_segment(p: Prompt, cue: str, paren: str | None, line: str, file_key: str):
    """{cue} says {paren}: "{line}"  (adverb parentheticals)  |  {cue}, {paren}, says: "{line}"  |  {cue} says: "{line}"
    The cue is always a verbatim source span (personal name or role noun)."""
    p.src(cue, file_key)
    if paren is None:
        p.glue("says")
    elif ADVERB_PAREN.match(paren.strip()):
        p.glue("says {parenthetical}").src(paren, file_key).glue("colon-quote")
    else:
        p.glue("{parenthetical}, says").src(paren, file_key).glue("comma").segs.append(("glue", "says: \"", "says-verb"))
    p.src(line, file_key).glue("close-quote")


GLUE["says-verb"] = "says: \""
WHITELIST = sorted(set(GLUE.values()), key=len, reverse=True)


def header_segment(p: Prompt, scale: tuple[str, str, str], camera: tuple[str, str, str]):
    """scale/camera = (kind, text, key) with kind in {glue, source}."""
    p.glue("HEADER")
    for kind, text, key in (scale, camera):
        if kind == "glue":
            p.segs.append(("glue", text, key))
        else:
            p.src(text, key)
        if (kind, text, key) == scale:
            p.glue("comma")
    p.glue("period").glue("newline")


NEGATION = re.compile(r"\b(not|no|never|without|hardly|barely|stops?|stopped|no longer|un)[\s-]+(?:[a-z]+\s+)?CUE\b", re.I)
PHYSICAL_DIRECTION = re.compile(r"\b(head snaps|snaps (his|her) head|shaking (him|her|them|off|his head|her head)|shakes (his|her) head|shaking off|"
                                r"breaking (the silence|away|free|off|into)|cracking (his|her) knuckles|slamming (the|a) (door|drawer|phone) shut)\b", re.I)


EXAG_GESTURE = {"clutching her chest", "clutching his chest", "clutching pearls", "pretending", "feigning", "feigned", "fake", "faking", "overly", "with exaggerated", "dramatic gasp", "dramatic sigh", "hysterically"}


def emotion_classes_in(text: str) -> list[str]:
    return [k for k in EMOTIONS if find_words(text, EMO[k])]


ENV_NOUN = re.compile(r"\s+(light|lights|lighting|candlelight|glow|lamp|lamplight|sunlight|moonlight|sun|room|air|wind|breeze|water|tea|coffee|bath|rain|snow|colou?rs?|tones?|hues?|"
                      r"afternoon|morning|evening|night|day|fire|fireplace|blanket|coat|scarf|sweater|wood|floor|walls?|sky|weather|season|spring|summer|autumn|winter|silence|music|smell|scent|"
                      r"towel|cloth|soup|milk|food|meal|bowl|cup|glass|porridge|bread|rice|noodles|broth|stove|kettle|bed|quilt|pillow)\b", re.I)
OTHER_SUBJECTS = {"children", "kids", "crowd", "people", "guests", "customers", "students", "soldiers", "guards", "men", "women", "others", "everyone", "audience",
                  "gallery", "hall", "room", "baby", "infant", "child", "boy", "girl", "servants", "maids", "nurses", "doctors", "reporters", "villagers", "onlookers",
                  "bystanders", "passengers", "workers", "staff", "followers", "henchmen", "thugs", "bodyguards", "family", "parents", "siblings", "brothers", "sisters",
                  "prisoners", "inmates", "officers", "colleagues", "employees", "classmates", "teammates", "players", "fans", "journalists", "paparazzi", "subordinates",
                  "assistants", "relatives", "neighbors", "neighbours", "strangers", "double"}


def cue_problems(par: str, pre: str, fol: str | None, icue: list[str], ecue: list[str], isrc: str, esrc: str, speaker_upper: str, other_names: set[str], speaker_gender: str = "unknown") -> str | None:
    """Reasons to drop a candidate whose native cue would be misread: negated cue ('not panicked'), a physical stage
    direction mistaken for delivery ('head snaps to the side'), or an action-line cue that belongs to another character."""
    for text, cues in ((par, icue + ecue), (pre + " " + (fol or ""), [w for w in icue + ecue if (isrc == "action" or esrc == "action")])):
        for w in cues:
            if any(w != v and w in v for v in icue + ecue):
                continue
            if re.search(NEGATION.pattern.replace("CUE", re.escape(w)), text):
                return "negated cue (e.g. 'not panicked')"
    if icue and all(PHYSICAL_DIRECTION.search(par) and w in PHYSICAL_DIRECTION.search(par).group(0).lower() for w in icue):
        return "intensity cue is a physical stage direction, not delivery (head snaps, shaking off)"
    for src, cues in ((isrc, icue), (esrc, ecue)):
        if src != "action":
            continue
        for w in cues:
            text = pre + " " + (fol or "")
            occ = [m for m in re.finditer(r"(?<![a-z-])" + re.escape(w) + r"(?![a-z])", text, re.I)]
            if occ and all(ENV_NOUN.match(text[m.end():]) for m in occ):
                return "action-line cue describes lighting / environment, not the speaker (warm candlelight)"
            for para in (pre, fol or ""):
                sents = sentence_split(para)
                for si, sent in enumerate(sents):
                    cm = re.search(r"(?<![a-z-])" + re.escape(w) + r"(?![a-z])", sent, re.I)
                    if not cm:
                        continue
                    if re.match(r"\s+(?:\w+\s+){0,2}(vanish\w*|fad\w*|disappear\w*|dies|dying|drops|falter\w*|freez\w*|collaps\w*|gone|evaporat\w*|slips|calcif\w*|harden\w*|stiffen\w*|twist\w*|sours?|curdl\w*|crack\w*)\b", sent[cm.end():]):
                        return "action-line cue is withdrawn by the next verb (smile fades / grin vanishes)"
                    before = sent[:cm.start()].split()[-4:]
                    if any(re.sub(r"[’']s$", "", b.upper()) in other_names and len(b) > 2 for b in before):
                        return "action-line cue belongs to another character"
                    if any(re.sub(r"[^a-z]", "", b.lower()) in OTHER_SUBJECTS for b in before):
                        return "action-line cue belongs to bystanders (children, crowd, guests)"
                    # subject of the cue sentence: explicit, or carried over from the previous subject-bearing sentence
                    subj = None
                    for prev in [sent] + sents[:si][::-1]:
                        if re.match(r"^(?:\w+,?\s+){0,2}" + re.escape(speaker_upper) + r"\b", prev, re.I):
                            subj = "speaker"; break
                        pm = re.match(r"^(He|She|His|Her)\b", prev)
                        if pm:
                            if speaker_gender in ("female", "male"):
                                subj = "speaker" if ((pm.group(1) in ("He", "His")) == (speaker_gender == "male")) else "other"
                            else:
                                subj = "unknown"
                            break
                        if any(len(n) > 2 and re.search(r"\b" + re.escape(n) + r"\b", prev.upper()) for n in other_names):
                            subj = "other"; break
                        if re.match(r"^(The|A|An|Two|Three|Several|Some|Everyone|Nobody|Their|Its|Gallery|Customers|People)\b", prev) and len(prev.split()) > 3:
                            subj = "other"; break
                    if subj == "other":
                        return "action-line cue belongs to another character"
                    if subj is None and len(sent.split()) > 3 and re.match(r"^[A-Z][a-z]+\s", sent) and not re.match(r"^(Then|Suddenly|Now|Slowly|Quietly|Finally|Still|Again|Mechanically)\b", sent):
                        return "action-line cue sentence has another subject (a BABY cries, the gallery murmurs)"
    return None


# ----------------------------------------------------------------------------------------------
# DramaBench
# ----------------------------------------------------------------------------------------------
OFFCAMERA = re.compile(r"\b(v\.?o\.?|o\.?s\.?|o\.?c\.?|voice[- ]?over|off[- ]?screen|offscreen|internal monologue|in unison|together|"
                       r"narrat\w*|recording|intercom|loudspeaker|speaker ?phone|on speaker|into (the |his |her )?phone|on (the )?phone|"
                       r"over (the )?phone|through (the )?phone|to (her|him)self|from (outside|behind|the other|inside|offscreen|off))\b", re.I)
GROUP_CUE = re.compile(r"(/|&| AND |\bALL\b|\bBOTH\b|\bEVERYONE\b|\bCROWD\b|\bVOICE\b|\bVOICES\b|\bUNISON\b|\bGUESTS\b|\bSTUDENTS\b|\bREPORTERS\b)")
ROLE_TAIL = re.compile(r"(MOTHER|FATHER|MOM|DAD|MUM|WIFE|HUSBAND|SON|DAUGHTER|BROTHER|SISTER|UNCLE|AUNT|AUNTIE|GRANDMA|GRANDPA|GRANDMOTHER|GRANDFATHER|"
                       r"DOCTOR|NURSE|DRIVER|GUARD|BODYGUARD|BUTLER|MAID|SERVANT|ASSISTANT|SECRETARY|MANAGER|WAITER|WAITRESS|CASHIER|CLERK|OFFICER|"
                       r"POLICEMAN|COP|LAWYER|JUDGE|TEACHER|PROFESSOR|STUDENT|BOSS|CEO|CHAIRMAN|PRESIDENT|DIRECTOR|EMPEROR|EMPRESS|PRINCE|PRINCESS|KING|QUEEN|"
                       r"CONCUBINE|CONSORT|EUNUCH|GENERAL|MINISTER|MAN|WOMAN|BOY|GIRL|LADY|GENTLEMAN|GUY|STRANGER|PASSERBY|BYSTANDER|CUSTOMER|PATIENT|"
                       r"REPORTER|HOST|MC|COMPANION|FRIEND|COLLEAGUE|EMPLOYEE|WORKER|NEIGHBOR|LANDLORD|LANDLADY|TENANT|MATRIARCH|PATRIARCH|HEIRESS|HEIR|"
                       r"MASTER|MISTRESS|MONK|NUN|PRIEST|SOLDIER|CAPTAIN|VILLAGER|FARMER|BEGGAR|THUG|HENCHMAN|GOON|SECURITY|RECEPTIONIST|HOSTESS|INTERN|"
                       r"FIANC[EÉ]E?|BRIDE|GROOM|STEPMOTHER|STEPFATHER|MOTHER-IN-LAW|FATHER-IN-LAW|SISTER-IN-LAW|BROTHER-IN-LAW|DAUGHTER-IN-LAW|SON-IN-LAW|EX-WIFE|EX-HUSBAND|"
                       r"[A-Z]+-IN-LAW|AGENT|DETECTIVE|INSPECTOR|CHEF|COOK|PILOT|STEWARDESS|ATTENDANT|SALESMAN|SALESWOMAN|VENDOR|OWNER|SHOPKEEPER|TAILOR|BARBER|"
                       r"DEALER|BANKER|INVESTOR|SHAREHOLDER|EXECUTIVE|SUPERVISOR|FOREMAN|COACH|PLAYER|REFEREE|AUCTIONEER|APPRAISER|EXPERT|SPECIALIST|SURGEON|"
                       r"PHYSICIAN|PHARMACIST|VET|MIDWIFE|CAREGIVER|NANNY|TUTOR|HEADMASTER|PRINCIPAL|DEAN|SCHOLAR|ELDER|CHIEF|LEADER|SPOKESPERSON|ANCHOR|"
                       r"PHOTOGRAPHER|MODEL|ACTOR|ACTRESS|SINGER|ARTIST|WRITER|AUTHOR|EDITOR|DESIGNER|ARCHITECT|ENGINEER|SCIENTIST|RESEARCHER|TECHNICIAN|"
                       r"MECHANIC|PLUMBER|ELECTRICIAN|CARPENTER|GARDENER|CLEANER|JANITOR|GUARDIAN|WARDEN|PRISONER|INMATE|CONVICT|SUSPECT|WITNESS|VICTIM|"
                       r"CLIENT|BUYER|SELLER|GUEST|VISITOR|TOURIST|PASSENGER|RIDER|COURIER|DELIVERYMAN|MESSENGER|HERALD|SCRIBE|ADVISOR|COUNSELOR|STEWARD|"
                       r"PAGE|SQUIRE|KNIGHT|LORD|DUKE|DUCHESS|COUNT|COUNTESS|BARON|MARQUIS|SIR|MADAM|MADAME|MISS|MRS|MR|MS)\.?$")
TITLE_HEAD = re.compile(r"^(MR|MRS|MS|MISS|DR|MADAM|MADAME|SIR|LADY|LORD|MASTER|YOUNG MASTER|UNCLE|AUNT|AUNTIE|GRANDMA|GRANDPA|BROTHER|SISTER|TEACHER|"
                        r"PROFESSOR|DOCTOR|NURSE|OFFICER|CAPTAIN|GENERAL|MANAGER|DIRECTOR|PRESIDENT|CHAIRMAN|SECRETARY|BOSS|PRINCE|PRINCESS|EMPEROR|EMPRESS|"
                        r"KING|QUEEN|CONSORT|CONCUBINE|GENERAL)\.?\s+[A-Z]", re.I)
GENERIC_LOC = {"room", "hall", "corridor", "office", "lobby", "lot", "station", "stop", "ward", "suite", "area", "entrance", "gate", "garden",
               "courtyard", "car", "house", "building", "floor", "shop", "store", "street", "road", "bridge", "bar", "club", "center", "centre",
               "quarters", "chamber", "wing", "deck", "yard", "pavilion", "tent", "stairs", "staircase", "stairwell", "window", "door", "doorway"}
DB_SKIP_PAREN = re.compile(r"^(beat|pause|cont'd|continuing|reading|singing|in [a-z]+|on (the )?tv|on screen|text message|caption|subtitle|cutting (him |her |them )?off|interrupting|overlapping)$", re.I)


def db_parse(fs: str) -> list[dict]:
    items = []
    heading = None
    for p in re.split(r"\n\s*\n", fs):
        p = p.strip("\n")
        if not p.strip():
            continue
        lines = [l.rstrip() for l in p.split("\n")]
        first = lines[0].strip()
        if re.match(r"^(INT\.|EXT\.|INT/EXT|I/E)", first):
            kind, heading = "heading", first
        elif first.isupper() and len(lines) >= 2 and len(first) < 40 and not first.startswith(("CUT TO", "FADE", "TITLE", "SMASH", "ON SCREEN")):
            kind = "dialogue"
        elif first.isupper():
            kind = "other"
        else:
            kind = "action"
        items.append(dict(kind=kind, lines=lines, heading=heading, text=norm(" ".join(l.strip() for l in lines))))
    return items


def db_intro(items: list[dict], name_upper: str) -> str | None:
    """First-appearance chunk 'NAME (...)' on an action line; extends to the sentence end when ', ' or ' —' follows."""
    rx = re.compile(r"(?:\b(?:A|AN|THE) )?\b" + re.escape(name_upper) + r" \((?!V\.O\.|O\.S\.|O\.C\.|CONT'D)[^)\n]*\)")
    for it in items:
        if it["kind"] != "action":
            continue
        m = rx.search(it["text"])
        if not m:
            continue
        return m.group(0) if INTRO_OK.search(m.group(0)[m.group(0).find("("):]) and not INTRO_BAD.search(m.group(0)) else None
    return None


INTRO_OK = re.compile(r"\d|,|\b(man|woman|boy|girl|male|female|suit|dress|hair|eyes|face|tall|short|young|old|elderly|wearing|robe|uniform|coat|glasses|beard|daughter|son|wife|husband|mother|father|in [a-z]+)\b", re.I)
INTRO_BAD = re.compile(r"\b(monologue|voice|phone|thought|thinking|off|whisper\w*|shout\w*|scream\w*|crying|laughing|smiling|to [a-z]+)\b", re.I)


def fine_family(heading: str) -> str:
    core = re.sub(r"^(INT\.?/EXT\.?|INT\.|EXT\.|I/E\.?)\s*", "", heading).split(" - ")[0].split(" – ")[0].strip().lower()
    core = re.sub(r"[^a-z' -]", " ", core)
    toks = [t for t in core.split() if t and not t.endswith("'s") and t != "family" and (t in DICT_WORDS or t in GENERIC_LOC or len(t) > 9)]
    if not toks:
        return core or "unknown"
    if len(toks) >= 2 and toks[-1] in GENERIC_LOC:
        return toks[-2] + " " + toks[-1]
    return toks[-1]


def db_speaker_kind(cue: str) -> str:
    """'role' (role-noun cue) or 'name' (personal-name cue); both render verbatim (no name substitution), the kind only drives drop rules and notes.
    A cue is a role noun only when it ends with a role word (MOTHER, DRIVER, CASHIER, FEMALE EMPLOYEE 1, ELDEST DAUGHTER OF
    THE YE FAMILY); a title + surname (MRS. SONG, BOSS ZHOU) or any other cue (LIN XI, VICTOR, LILIAN) is a personal name."""
    c = re.sub(r"\s*\(.*\)$", "", cue).strip()
    c = re.sub(r"\s+(\d+|[A-Z]|#\d+)$", "", c)
    if TITLE_HEAD.match(c):
        return "name"
    if ROLE_TAIL.search(c) or re.search(r"\bOF THE [A-Z]+ FAMILY$", c) or c.endswith("FAMILY"):
        return "role"
    return "name"


LINK = r"(?:(?:named|called|the|a|an|young|old|elderly|little|big|-|–|—|,)[ \t]+){0,2}"
FEMALE_BEFORE = re.compile(r"\b(aunt|auntie|mother|mom|mum|wife|girlfriend|daughter|sister|grandmother|grandma|niece|woman|girl|lady|madam|mrs\.?|miss|ms\.?|fianc[eé]e|bride|widow|queen|empress|princess|concubine|consort|nanny|maid|actress|waitress|heiress|stepmother|mother-in-law|sister-in-law|daughter-in-law|cousin sister)[ \t]+" + LINK + r"NAME\b", re.I)
MALE_BEFORE = re.compile(r"\b(uncle|father|dad|papa|husband|boyfriend|son|brother|grandfather|grandpa|nephew|man|boy|gentleman|sir|mr\.?|master|young master|fianc[eé]|groom|widower|king|emperor|prince|duke|lord|butler|bodyguard|actor|waiter|heir|stepfather|father-in-law|brother-in-law|son-in-law|patriarch|monk|eunuch)[ \t]+" + LINK + r"NAME\b", re.I)
FEMALE_IN = re.compile(r"\b(woman|girl|lady|matriarch|mother|wife|daughter|nanny|maid|female|actress|widow|heiress|bride|she|her)\b", re.I)
MALE_IN = re.compile(r"\b(man|boy|gentleman|patriarch|father|husband|son|male|actor|widower|groom|he|his)\b", re.I)


def gender_of(name_upper: str, name_title: str, script_text: str, intro: str | None) -> tuple[str, str]:
    """Gender stated by the source text: (1) a gendered role word right before the name ('aunt CHEN YUZHEN', 'Mrs. Song'),
    (2) a gendered word in the first-appearance parenthetical ('(60, elegant, intimidating matriarch)'), (3) pronouns in
    sentences that mention the speaker (v1 infer_gender). Returns (gender, evidence)."""
    f_cue, m_cue = bool(FEMALE_ROLE.search(name_title)), bool(MALE_ROLE.search(name_title))
    if f_cue != m_cue:
        return ("female" if f_cue else "male"), f"role word in cue: {name_upper!r}"
    for rx, g in ((FEMALE_BEFORE, "female"), (MALE_BEFORE, "male")):
        m = re.search(rx.pattern.replace("NAME", re.escape(name_upper)), script_text, re.I)
        if m:
            other = MALE_BEFORE if g == "female" else FEMALE_BEFORE
            if not re.search(other.pattern.replace("NAME", re.escape(name_upper)), script_text, re.I):
                return g, f"role word before name: {m.group(0)!r}"
    if intro:
        inside = intro[intro.find("("):]
        f, mm = bool(FEMALE_IN.search(inside)), bool(MALE_IN.search(inside))
        if f != mm:
            return ("female" if f else "male"), f"first-appearance line: {intro!r}"
    g, ev = infer_gender(name_title, script_text)
    if g != "unknown":
        return g, ev
    # paragraph-initial subject: sentences that follow 'NAME ...' inside the same action paragraph, until another name appears
    f = mm = 0
    for para in re.split(r"\n\s*\n", script_text):
        sents = sentence_split(norm(para))
        if not sents or not re.match(r"^(?:\w+,?\s+){0,2}" + re.escape(name_upper) + r"\b", sents[0], re.I):
            continue
        for sent in sents[1:]:
            if re.search(r"\b(?!" + re.escape(name_upper.split()[0]) + r")[A-Z]{2,}\b", sent) and not sent.isupper():
                caps = [w for w in re.findall(r"\b[A-Z]{2,}\b", sent) if w.lower() not in DICT_WORDS and w not in name_upper.split()]
                if caps:
                    break
            m = re.match(r"^(He|She|His|Her)\b", sent)
            if m:
                if m.group(1) in ("He", "His"): mm += 1
                else: f += 1
    if (f > 0) != (mm > 0):
        return ("female" if f else "male"), f"paragraph pronouns after the name: {f}f/{mm}m"
    return g, ev


def seam_bios_gender() -> dict[str, tuple[str, str]]:
    """Gender from character_bios.txt pronouns (她 / 他) per bio block; keyed by the English given name in caps."""
    out = {}
    bios = (SEAM_DIR / "script/character_bios.txt").read_text(encoding="utf-8")
    blocks = re.split(r"\n(?=[^\n]*\([A-Z][a-z]+(?: [A-Z][a-z]+)?\) \|)", bios)
    for b in blocks:
        m = re.search(r"\(([A-Z][a-z]+)(?: [A-Z][a-z]+)?\) \|", b)
        if not m:
            continue
        f, mm = b.count("她"), b.count("他")
        if f != mm:
            out[m.group(1).upper()] = (("female" if f > mm else "male"), f"character_bios.txt pronouns 她x{f}/他x{mm}")
    return out


def build_dramabench(explore: bool, target: int = TARGETS["DramaBench"]) -> tuple[list[dict], dict]:
    cands = [json.loads(l) for l in open(DB_CANDS, encoding="utf-8")]
    scripts = {}
    for ln in open(DB_SCRIPTS, encoding="utf-8"):
        r = json.loads(ln)
        scripts[r["id"]] = r
    filt = collections.OrderedDict()
    filt["candidates in dramabench_candidates_native.jsonl"] = len(cands)
    pool = []
    c1 = [c for c in cands if c["native_intensity_bin"] in BINS]
    filt["native intensity bin (calm/strong/exaggerated)"] = len(c1)
    c2 = [c for c in c1 if c["emotion_class"] in EMOTIONS]
    filt["+ native emotion class"] = len(c2)
    c3 = [c for c in c2 if 3 <= words(c["line"]) <= 12]
    filt["+ line 3-12 words"] = len(c3)
    drops = collections.Counter()
    parsed_cache, names_cache = {}, {}
    for c in c3:
        sid = c["script_id"]
        if sid not in parsed_cache:
            parsed_cache[sid] = db_parse(scripts[sid]["full_script"])
        items = parsed_cache[sid]
        idx = None
        for i, it in enumerate(items):
            if it["kind"] == "dialogue" and len(it["lines"]) >= 3 and it["lines"][1].strip() == "(" + c["parenthetical"] + ")" \
                    and it["lines"][2].strip() == c["line"] and it["heading"] == c["setting"]:
                idx = i; break
        if idx is None:
            drops["block not found in full_script"] += 1; continue
        it = items[idx]
        if len(it["lines"]) != 3:
            drops["dialogue block has more than one line (line is not the whole speech)"] += 1; continue
        cue = it["lines"][0].strip()
        if re.search(r"\((V\.O\.|O\.S\.|O\.C\.|V\.O|O\.S)\)", cue) or OFFCAMERA.search(re.sub(r"\(CONT'D\)", "", cue)):
            drops["speaker cue off-camera (V.O./O.S.)"] += 1; continue
        if "(CONT'D)" in cue and db_speaker_kind(cue) == "role":
            drops["role-noun cue with (CONT'D) (would render verbatim)"] += 1; continue
        if GROUP_CUE.search(cue):
            drops["group / voice speaker cue"] += 1; continue
        if OFFCAMERA.search(c["parenthetical"]):
            drops["parenthetical is off-camera stage business (V.O., into phone, in unison, to himself...)"] += 1; continue
        if DB_SKIP_PAREN.match(c["parenthetical"]):
            drops["parenthetical is beat/pause/reading"] += 1; continue
        pre, adjacent = None, False
        for j in range(idx - 1, -1, -1):
            if items[j]["kind"] == "heading" or items[j]["heading"] != it["heading"]:
                break
            if items[j]["kind"] == "action":
                pre, adjacent = items[j]["text"], (j == idx - 1); break
        if not pre:
            drops["no action paragraph in the scene before the cue"] += 1; continue
        if re.search(r"audio:|\"[^\"]{15,}\"|“[^”]{15,}”", pre):
            drops["preceding action carries a second spoken line (audio/quote)"] += 1; continue
        if PHONE_ACTION.search(pre) or PHONE_LINE.search(c["line"]) or re.search(r"\bphone\b", c["parenthetical"], re.I):
            drops["phone conversation (action/line)"] += 1; continue
        if re.search(r"\((V\.O\.|O\.S\.)\)|\bV\.O\.|\bO\.S\.", pre):
            drops["preceding action contains V.O./O.S. marker"] += 1; continue
        # following action: only when it is the speaker's own action
        name_upper = re.sub(r"\s*\(.*\)$", "", cue).strip()
        name_title = name_upper.title()
        if sid not in names_cache:
            names_cache[sid] = script_names(scripts[sid]["full_script"])
        nxt = items[idx + 1] if idx + 1 < len(items) else None
        fol = None
        if nxt and nxt["kind"] == "action" and nxt["heading"] == it["heading"]:
            first_sent = sentence_split(nxt["text"])[0]
            starts = re.match(r"^(" + re.escape(name_upper) + r"|" + re.escape(name_title) + r"|" + re.escape(name_title.split()[0]) + r")\b", first_sent)
            others = names_cache[sid] - {t.title() for t in name_upper.split()}
            others = {o for o in others if o not in {"The", "A", "An"}}
            if starts and not any(re.search(r"\b" + re.escape(o) + r"\b", nxt["text"]) for o in others if len(o) > 2):
                fol = nxt["text"]
        # cues must be visible in the rendered source text
        src_text = (pre + " " + c["parenthetical"] + " " + (fol or "")).lower()
        if not all(w.lower() in src_text for w in c["intensity_cue"]) or not all(w.lower() in src_text for w in c["emotion_cue"]):
            drops["native cue not inside the rendered spans (came from a non-adjacent / unused action line)"] += 1; continue
        kind = db_speaker_kind(cue)
        intro = db_intro(items, name_upper)
        gender, gev = gender_of(name_upper, name_title, scripts[sid]["full_script"], intro)
        if intro and (intro in pre or (fol and intro in fol)):
            intro = None  # already inside the action span
        if kind == "name" and gender == "unknown":
            drops["personal-name speaker whose gender the script does not state"] += 1; continue
        problem = cue_problems(c["parenthetical"], pre, fol, c["intensity_cue"], c["emotion_cue"], c["intensity_cue_source"], c["emotion_cue_source"],
                               name_upper, {n.upper() for n in names_cache[sid]} - set(name_upper.split()), gender)
        if problem:
            drops[problem] += 1; continue
        sfx_sent, sfx_hit = sfx_sentence(pre, fol or "")
        shot = dict(c, cue=cue, name_upper=name_upper, speaker_kind=kind, gender=gender, gender_evidence=gev, pre=pre, fol=fol,
                    intro=intro, sfx_sent=sfx_sent, sfx_hit=sfx_hit, family=fine_family(c["setting"]), adjacent=adjacent,
                    coarse_family=setting_family(c["setting"]), items=items, multi_class=emotion_classes_in(c["parenthetical"]))
        p, _ = render_db(shot)
        n = words(p.text())
        if not (WORD_RANGE[0] <= n <= WORD_RANGE[1]):
            drops[f"rendered prompt outside {WORD_RANGE[0]}-{WORD_RANGE[1]} words"] += 1; continue
        shot["nwords"] = n
        pool.append(shot)
    for k, v in drops.items():
        filt[f"drop: {k}"] = v
    filt["eligible pool"] = len(pool)
    stats = dict(filters=filt)
    stats["pool_bin_emotion"] = collections.Counter((s["native_intensity_bin"], s["emotion_class"]) for s in pool)
    stats["pool_sfx"] = sum(1 for s in pool if s["sfx_sent"])
    stats["pool_gender"] = collections.Counter(s["gender"] for s in pool)
    stats["pool_scripts"] = len({s["script_id"] for s in pool})
    if explore:
        print("DramaBench filters:")
        for k, v in filt.items():
            print(f"  {k}: {v}")
        print("  pool bin x emotion:", dict(stats["pool_bin_emotion"]))
        print("  pool with sfx:", stats["pool_sfx"], "gender:", dict(stats["pool_gender"]), "scripts:", stats["pool_scripts"])
    # ---- selection ----
    rng = random.Random(SEED)
    order = list(range(len(pool)))
    rng.shuffle(order)
    pool = [pool[i] for i in order]
    chosen: list[dict] = []
    used_scripts, fam_count, gender_count = set(), collections.Counter(), collections.Counter()
    sfx_count = 0
    supply = collections.Counter((s["native_intensity_bin"], s["emotion_class"]) for s in pool)
    # exaggerated: water-fill over classes as supply allows
    exag_target = collections.Counter()
    for _ in range(min(EXAG_TARGET_DB, sum(v for (b, e), v in supply.items() if b == "exaggerated"))):
        opts = [e for e in EMOTIONS if supply[("exaggerated", e)] > exag_target[e]]
        if not opts:
            break
        e = min(opts, key=lambda e: (exag_target[e], EMOTIONS.index(e)))
        exag_target[e] += 1
    n_exag = sum(exag_target.values())
    rest = target - n_exag
    per_cell = rest // 12
    targets = {("exaggerated", e): exag_target[e] for e in EMOTIONS}
    for b in ("calm", "strong"):
        for e in EMOTIONS:
            targets[(b, e)] = per_cell
    # distribute remainder (rest - 12*per_cell) one by one to calm/strong cells with most supply
    extra = rest - per_cell * 12
    for e in sorted(EMOTIONS, key=lambda e: -min(supply[("calm", e)], supply[("strong", e)]))[:extra]:
        targets[("calm" if supply[("calm", e)] >= supply[("strong", e)] else "strong", e)] += 1

    def pick(cell):
        nonlocal sfx_count
        b, e = cell
        best, best_score = None, None
        need_gender = "female" if gender_count["female"] <= gender_count["male"] else "male"
        for s in pool:
            if (s["native_intensity_bin"], s["emotion_class"]) != cell or s["script_id"] in used_scripts:
                continue
            if fam_count[s["family"]] >= MAX_PER_FAMILY:
                continue
            if s["gender"] == "unknown" and gender_count["unknown"] >= MAX_UNKNOWN_GENDER_DB:
                continue
            score = 0
            if s["sfx_sent"] and sfx_count < SFX_TARGET_DB:
                score += 3
            if s["gender"] == need_gender:
                score += 2
            elif s["gender"] == "unknown":
                score -= 1
            if s["intro"]:
                score += 1
            if s["intensity_cue_source"] == "parenthetical":
                score += 1
            if s["adjacent"]:
                score += 2
            if best is None or score > best_score:
                best, best_score = s, score
        if best is None:
            return False
        chosen.append(best); used_scripts.add(best["script_id"]); fam_count[best["family"]] += 1
        gender_count[best["gender"]] += 1
        if best["sfx_sent"]:
            sfx_count += 1
        return True

    shortfall = collections.Counter()
    # exaggerated first (scarce), then calm/strong round-robin
    remaining = dict(targets)
    for e in EMOTIONS:
        while remaining[("exaggerated", e)] > 0:
            if pick(("exaggerated", e)):
                remaining[("exaggerated", e)] -= 1
            else:
                shortfall[("exaggerated", e)] += remaining[("exaggerated", e)]; remaining[("exaggerated", e)] = 0
    progress = True
    while progress:
        progress = False
        for e in EMOTIONS:
            for b in ("calm", "strong"):
                if remaining[(b, e)] > 0:
                    if pick((b, e)):
                        remaining[(b, e)] -= 1; progress = True
                    else:
                        shortfall[(b, e)] += remaining[(b, e)]; remaining[(b, e)] = 0
    # fill any shortfall from the same bin, any class
    missing = target - len(chosen)
    refill = collections.Counter()
    while missing > 0:
        filled = False
        for b in ("exaggerated", "calm", "strong"):
            for e in EMOTIONS:
                if missing > 0 and pick((b, e)):
                    refill[(b, e)] += 1; missing -= 1; filled = True
        if not filled:
            break
    stats.update(targets=targets, shortfall=shortfall, refill=refill, n_exag_target=n_exag, target=target)
    return chosen, stats


def render_db(shot: dict) -> tuple[Prompt, dict]:
    p = Prompt()
    header_segment(p, ("glue", SCALE_DEFAULT, "SCALE_DEFAULT"), ("glue", CAMERA_DEFAULT, "CAMERA_DEFAULT"))
    p.src(shot["setting"], "script").glue("period").glue("space")
    if shot["intro"]:
        p.src(shot["intro"], "script")
        if not shot["intro"].endswith("."):
            p.glue("period")
        p.glue("space")
    p.src(shot["pre"], "script").glue("space")
    cue = rendered_cue(shot["cue"])
    speech_segment(p, cue, shot["parenthetical"], shot["line"], "script")
    if shot["fol"]:
        p.glue("space").src(shot["fol"], "script")
    if shot["sfx_sent"]:
        p.glue("space").glue("SFX_LEAD").src(shot["sfx_sent"], "script")
    p.glue("newline").glue("FOOTER")
    return p, dict(role=cue, name_substitution=None)


def db_raw(shot: dict) -> list[str]:
    return raw_lines(shot["setting"], shot["intro"], shot["pre"], rendered_cue(shot["cue"]), shot["parenthetical"], shot["line"], shot["fol"])


def db_excerpt(fs: str, shot: dict, limit: int = 400) -> str:
    block = "\n".join(l for l in shot["items"][[i for i, it in enumerate(shot["items"]) if it["kind"] == "dialogue" and it["lines"][0].strip() == shot["cue"] and len(it["lines"]) >= 3 and it["lines"][2].strip() == shot["line"]][0]]["lines"])
    i = fs.find(block)
    assert i >= 0
    start = max(0, i - (limit - len(block) - 1))
    window = fs[start:i + len(block)]
    if start > 0 and "\n" in window:
        window = window.split("\n", 1)[1]
    window = window.strip("\n")
    assert window in fs and len(window) <= limit and shot["line"] in window
    return window


# ----------------------------------------------------------------------------------------------
# SEAM-Bench (line source = episode .txt; director CSV supplies 景别/拍摄角度/运镜 + 中文台词 when a row matches)
# ----------------------------------------------------------------------------------------------
CUE_LINE = re.compile(r"^[A-Z][A-Z .'’\-]*[A-Z.]?(?:\s*\((?:V\.O\.|O\.S\.|O\.C\.|CONT'D|ON CARD)\))*\s*$")
HEAD_LINE = re.compile(r"^(INT\.|EXT\.|INT/EXT)")
TRANS_LINE = re.compile(r"^(CUT TO|SMASH CUT|QUICK CUT|HARD CUT|MATCH CUT|FADE|TITLE CARD|INSERT|EPISODE|FLASHBACK|END OF|THE END|BASS BOOM|FREEZE|SUPER:|MONTAGE|BACK TO)")
SEAM_CAST = "Julian|Victor|Serena|Milo|Harper|Eleanor|Emma|Paige|Manager|Cashier|Nurses|Guards|Guard|Doctor|Staff|Paparazzi|Reporters|Crowd"
ACTION_START = re.compile(r"^(?:(?:%s)(?:’s|'s)?\s+(?!,)|(?:He|She|His|Her|They|Their|Both|The|A|An|Camera|CAMERA|Dead|Soft|Sharp|Cold|Bright|Heavy|Elevator|Phone|"
                          r"Footsteps|Tiny|Sound|Silence|Music|Rain|Wind|Then|Suddenly|Slowly|Beat|Close on|CLOSE|ON |Montage|Later|Lights|Door|Doors|Glass|Snow|Sun|"
                          r"Night|Day|Morning|Outside|Inside|Through|Across|Behind|Beside|Over|Under|Near|Somewhere|Nothing|Everything|No one|Nobody|Everyone|Chilling)\b)" % SEAM_CAST)
PAGE_GLUE = re.compile(r"(?<=[A-Za-z.!?’”\")…])\d{1,2}\.\s*$")
SEAM_DIALOGUE_MAX_WIDTH = 40   # PDF dialogue column; action lines wrap wider


def cut_glue(line: str) -> str:
    """Drop a PDF page number glued to the last word of a page ('back.6.' -> 'back.'); the result is a verbatim prefix."""
    return PAGE_GLUE.sub("", line).rstrip()


def seam_parse_episode(text: str, dialogue_corpus: str = "") -> list[dict]:
    """dialogue_corpus = apost-normalised director-CSV lines of the episode (and neighbours); a wrapped line that looks like an
    action start ('Victor's right-hand woman.') but occurs in the CSV dialogue is kept as dialogue."""
    lines = [l.rstrip() for l in text.split("\n")]
    items, heading, i = [], None, 0
    while i < len(lines):
        s = lines[i].strip()
        if not s:
            i += 1; continue
        if HEAD_LINE.match(s):
            heading = cut_glue(s); items.append(dict(kind="heading", text=heading, heading=heading)); i += 1; continue
        if TRANS_LINE.match(s):
            items.append(dict(kind="other", text=s, heading=heading)); i += 1; continue
        if CUE_LINE.match(s) and len(s) < 40:
            cue, j, pars = s, i + 1, []
            while j < len(lines) and lines[j].strip().startswith("("):
                buf = lines[j].strip()
                while not buf.endswith(")") and j + 1 < len(lines):
                    j += 1; buf += " " + lines[j].strip()
                pars.append(buf); j += 1
            dlg, multipart = [], False
            while j < len(lines):
                t = lines[j].strip()
                if not t or (CUE_LINE.match(t) and len(t) < 40) or HEAD_LINE.match(t) or TRANS_LINE.match(t):
                    break
                if t.startswith("("):
                    multipart = True; break
                if len(t) > SEAM_DIALOGUE_MAX_WIDTH:
                    break
                if dlg and ACTION_START.match(t) and re.search(r"[.!?…—\"”’]$", dlg[-1]) and not (dialogue_corpus and apost(t).rstrip(".!?,") in dialogue_corpus):
                    break
                dlg.append(t); j += 1
            items.append(dict(kind="dialogue", cue=cue, pars=pars, dlg=dlg, multipart=multipart, heading=heading, text=" ".join(dlg)))
            i = j; continue
        buf, j = [], i
        while j < len(lines):
            t = lines[j].strip()
            if not t or (CUE_LINE.match(t) and len(t) < 40) or HEAD_LINE.match(t) or TRANS_LINE.match(t):
                break
            buf.append(t); j += 1
        if not buf:
            buf, j = [s], i + 1
        items.append(dict(kind="action", lines=buf, heading=heading))
        i = j
    return items


def seam_action_text(it: dict) -> str | None:
    """Action paragraph as one verbatim-normalised span; a glued page number ends a page, so keep the text after it
    (a new page) when there is any, else the text before it (cut at the glue)."""
    ls = it["lines"]
    for k in range(len(ls) - 1, -1, -1):
        if PAGE_GLUE.search(ls[k]):
            after = ls[k + 1:]
            if after:
                return norm(" ".join(after))
            return norm(" ".join(ls[:k] + [cut_glue(ls[k])]))
    return norm(" ".join(ls))


def seam_translate(field: str, value: str) -> tuple[str | None, list[tuple[str, str]], str | None]:
    """Fixed-dictionary translation. Returns (english, [(glue_key, text)...], untranslated remainder)."""
    v = value.strip().replace("，", ",").replace("（", "(").replace("）", ")")
    if not v:
        return None, [], None
    v = re.sub(SEAM_NAME_PREFIX, "", v)
    rest = None
    if field == "拍摄角度":
        if re.match(SEAM_OTS[1], v):
            return SEAM_OTS[0], [("SEAM:拍摄角度:过X关系", SEAM_OTS[0])], None
        tokens, s = [], v
        while s:
            hit = None
            for zh in sorted(SEAM_DICT[field], key=len, reverse=True):
                if s.startswith(zh):
                    hit = zh; break
            if hit is None:
                m = re.match(SEAM_OTS[1].rstrip("$"), s)
                if m:
                    tokens.append(("SEAM:拍摄角度:过X关系", SEAM_OTS[0])); s = s[m.end():]; continue
                if s[0] in "-, ":
                    s = s[1:]; continue
                rest = s; break
            tokens.append((f"SEAM:{field}:{hit}", SEAM_DICT[field][hit])); s = s[len(hit):]
        if not tokens:
            return None, [], v
        if len(tokens) == 2 and "-" in v:
            return tokens[0][1] + " to " + tokens[1][1], [tokens[0], ("SEAM:to-connector", " to "), tokens[1]], rest
        out = []
        for t in tokens:
            if out:
                out.append(("comma", ", "))
            out.append(t)
        return "".join(x[1] for x in out), out, rest
    if field == "景别" and ("-" in v or "到" in v):
        a, b = re.split(r"-|到", v, 1)
        ta, tb = SEAM_DICT[field].get(a.strip()), SEAM_DICT[field].get(b.strip())
        if ta and tb:
            return ta + " to " + tb, [(f"SEAM:{field}:{a.strip()}", ta), ("SEAM:to-connector", " to "), (f"SEAM:{field}:{b.strip()}", tb)], None
    for zh in sorted(SEAM_DICT[field], key=len, reverse=True):
        if v.startswith(zh):
            rem = v[len(zh):].strip(" ,")
            return SEAM_DICT[field][zh], [(f"SEAM:{field}:{zh}", SEAM_DICT[field][zh])], (rem or None)
    for zh in sorted(SEAM_DICT[field], key=len, reverse=True):  # key anywhere in a free-text 运镜 cell
        if field == "运镜" and zh in v and len(zh) >= 2:
            return SEAM_DICT[field][zh], [(f"SEAM:{field}:{zh}", SEAM_DICT[field][zh])], v
    return None, [], v


def seam_cell(cell: str) -> tuple[str, str | None, str]:
    ls = [l.strip() for l in cell.strip().split("\n") if l.strip()]
    cue = ls[0].strip()
    par, i = None, 1
    if i < len(ls) and ls[i].startswith("("):
        buf = ls[i]
        while ")" not in buf and i + 1 < len(ls):
            i += 1; buf += " " + ls[i]
        par = buf[1:buf.index(")")].strip()
        i += 1
    return cue, par, " ".join(ls[i:]).strip()


def seam_intro(items: list[dict], name: str) -> str | None:
    rx = re.compile(r"\b" + re.escape(name) + r"(?: [A-Z]+)? \((?!V\.O\.|O\.S\.|CONT'D)[^)]*\)")
    for it in items:
        if it["kind"] != "action":
            continue
        text = seam_action_text(it) or ""
        m = rx.search(text)
        if not m:
            continue
        return m.group(0) if INTRO_OK.search(m.group(0)[m.group(0).find("("):]) and not INTRO_BAD.search(m.group(0)) else None
    return None


def apost(s: str) -> str:
    return norm(s.replace("’", "'").replace("‘", "'").replace("…", "...").replace("“", '"').replace("”", '"')).lower()


def build_seam(explore: bool) -> tuple[list[dict], dict]:
    filt = collections.OrderedDict()
    csv_rows, txt = {}, {}
    for f in sorted(glob.glob(str(SEAM_DIR / "director/ep*.csv"))):
        ep = int(re.search(r"ep(\d+)", f).group(1))
        raw = open(f, encoding="utf-8-sig").read()
        csv_rows[ep] = [r for r in csv.DictReader(io.StringIO(raw)) if (r.get("台词") or "").strip()]
        txt[ep] = open(SEAM_DIR / f"script/episodes/ep{ep:02d}_en.txt", encoding="utf-8").read()
    kept_eps = [ep for ep in sorted(txt) if ep not in SEAM_EXCLUDED_EPISODES]
    bios_gender = seam_bios_gender()
    corpus = {ep: apost(" ".join(seam_cell(r["台词"])[2] for e in (ep - 1, ep, ep + 1) for r in csv_rows.get(e, []))) for ep in kept_eps}
    parsed = {ep: seam_parse_episode(txt[ep], corpus[ep]) for ep in kept_eps}
    all_dlg = [(ep, k, it) for ep in kept_eps for k, it in enumerate(parsed[ep]) if it["kind"] == "dialogue"]
    filt["dialogue cues in the 23 episode .txt files"] = sum(1 for ep in sorted(txt) for it in seam_parse_episode(txt[ep]) if it["kind"] == "dialogue")
    filt["after excluding episodes 1, 2, 7, 8, 9 entirely"] = len(all_dlg)
    drops = collections.Counter()
    pool = []
    for ep, k, it in all_dlg:
        items = parsed[ep]
        cue = it["cue"]
        if re.search(r"\((V\.O\.|O\.S\.|O\.C\.|ON CARD)\)", cue):
            drops["V.O. / O.S. / on-card cue"] += 1; continue
        if not it["pars"]:
            drops["no parenthetical (no native cue)"] += 1; continue
        if it["multipart"]:
            drops["speech interrupted by a second parenthetical (line is not the whole speech)"] += 1; continue
        dlg = [cut_glue(l) for l in it["dlg"]]
        line = norm(" ".join(dlg))
        par = it["pars"][0][1:it["pars"][0].index(")")].strip()
        if len(it["pars"]) > 1:
            drops["two leading parentheticals"] += 1; continue
        n = words(line)
        if not (3 <= n <= 12):
            drops["speech outside 3-12 words"] += 1; continue
        if OFFCAMERA.search(par):
            drops["parenthetical off-camera (to himself / into phone)"] += 1; continue
        if PHONE_LINE.search(line) or re.search(r"\b(Emma\?|over phone)", line):
            drops["phone conversation line"] += 1; continue
        heading = it["heading"]
        if heading is None:
            drops["no scene heading above the cue"] += 1; continue
        # nearest action paragraph in the same scene (adjacent preferred)
        pre, adjacent = None, False
        for j in range(k - 1, -1, -1):
            if parsed[ep][j]["kind"] == "heading":
                break
            if parsed[ep][j]["kind"] == "action":
                pre = seam_action_text(parsed[ep][j]); adjacent = (j == k - 1); break
        if not pre:
            drops["no action paragraph in the scene before the cue"] += 1; continue
        if PHONE_ACTION.search(pre):
            drops["preceding action is a phone call"] += 1; continue
        if re.search(r"audio:|\"[^\"]{15,}\"|“[^”]{15,}”", pre):
            drops["preceding action carries a second spoken line (audio/quote)"] += 1; continue
        b, cue_words, src, ecls, ecue, esrc = label(par, pre)
        base_cue = re.sub(r"\s*\(CONT'D\)\s*$", "", cue).strip()
        # director CSV row for this line (shot grammar + Chinese line); fuzzy match on parenthetical + line
        best, best_r, best_ep = None, 0.0, None
        for ep_c in (ep, ep + 1, ep - 1):
          for r in csv_rows.get(ep_c, []):
            ccue, cpar, cline = seam_cell(r["台词"])
            if re.sub(r"\s*\(CONT'D\)\s*$", "", ccue).strip() != base_cue:
                continue
            a = apost(("(" + (cpar or "") + ") " + cline))
            bb = apost("(" + par + ") " + line)
            ratio = difflib.SequenceMatcher(None, a, bb).ratio()
            ratio2 = difflib.SequenceMatcher(None, apost(cline), apost(line)[:len(apost(cline)) + 4]).ratio()
            ratio = max(ratio, ratio2)
            if ratio > best_r:
                best, best_r, best_ep = r, ratio, ep_c
        row = best if best_r >= 0.6 else None
        csv_ep = best_ep if row else None
        intro_full = seam_intro(items, base_cue.split()[0])
        intro = None if (intro_full and intro_full in pre) else intro_full
        if base_cue.split()[0] in bios_gender:
            gender, gev = bios_gender[base_cue.split()[0]]
        else:
            gender, gev = gender_of(base_cue, base_cue.title(), norm(txt[ep]), intro_full)
            if gender == "unknown":
                for ep_i in kept_eps:
                    gender, gev = gender_of(base_cue, base_cue.title(), norm(txt[ep_i]), intro_full)
                    if gender != "unknown":
                        gev += f" (ep{ep_i:02d})"; break
        problem = cue_problems(par, pre, None, cue_words, ecue, src, esrc, base_cue, set(SEAM_CAST.upper().split("|")) - set(base_cue.split()), gender)
        if problem:
            drops[problem] += 1
            if explore:
                print(f"  [dropped: {problem}] ep{ep:02d} {cue} ({par}) {cue_words}/{ecue} | {line} | pre: {pre[:120]}")
            continue
        if row and re.search(r"二人|两人|双人", row["景别"]):
            drops["director 景别 is a two-shot (二人/两人)"] += 1; continue
        sc, sc_segs, sc_rest = seam_translate("景别", row["景别"]) if row else (None, [], None)
        mv, mv_segs, mv_rest = seam_translate("运镜", row["运镜"]) if row else (None, [], None)
        an, an_segs, an_rest = seam_translate("拍摄角度", row["拍摄角度"]) if row else (None, [], None)
        sfx_sent, sfx_hit = sfx_sentence(pre)
        csv_line = seam_cell(row["台词"])[2] if row else None
        shot = dict(ep=ep, csv_ep=csv_ep, shot_no=(row["分镜号"] if row else None), cue=cue, base_cue=base_cue, parenthetical=par, line=line,
                    line_zh=((row.get("中文台词") or "").strip() if row else None), heading=heading, pre=pre, adjacent=adjacent, intro=intro,
                    gender=gender, gender_evidence=gev, bin=b, intensity_cue=cue_words, intensity_src=src, emotion_class=ecls, emotion_cue=ecue,
                    emotion_src=esrc, jingbie=(row["景别"] if row else None), jiaodu=(row["拍摄角度"] if row else None), yunjing=(row["运镜"] if row else None),
                    scale=sc, scale_segs=sc_segs, scale_rest=sc_rest, move=mv, move_segs=mv_segs, move_rest=mv_rest, angle=an, angle_segs=an_segs,
                    angle_rest=an_rest, sfx_sent=sfx_sent, sfx_hit=sfx_hit, match_ratio=round(best_r, 2), csv_line=csv_line, multi_class=emotion_classes_in(par),
                    csv_par=(seam_cell(row["台词"])[1] if row else None), dlg_lines=it["dlg"])
        p, _ = render_seam(shot)
        nw = words(p.text())
        if not (WORD_RANGE[0] <= nw <= WORD_RANGE[1]):
            drops[f"rendered prompt outside {WORD_RANGE[0]}-{WORD_RANGE[1]} words"] += 1; continue
        shot["nwords"] = nw
        pool.append(shot)
    for kk, v in drops.items():
        filt[f"drop: {kk}"] = v
    filt["eligible pool"] = len(pool)
    binned = [s for s in pool if s["bin"] in BINS]
    filt["eligible with a native intensity bin"] = len(binned)
    filt["eligible with bin AND emotion class"] = sum(1 for s in binned if s["emotion_class"])
    filt["eligible with a matching director CSV row (shot grammar)"] = sum(1 for s in pool if s["shot_no"])
    stats = dict(filters=filt, pool_bins=collections.Counter(s["bin"] for s in pool),
                 pool_bin_emotion=collections.Counter((s["bin"], s["emotion_class"]) for s in pool))
    if explore:
        print("SEAM-Bench filters:")
        for kk, v in filt.items():
            print(f"  {kk}: {v}")
        for s in pool:
            print(f"  ep{s['ep']:02d} (csv ep{s['csv_ep']}#{s['shot_no']}) {s['cue']} ({s['parenthetical']}) [{s['bin']}/{s['emotion_class']}] csv r={s['match_ratio']} adj={s['adjacent']} | {s['line']} | pre: {s['pre'][:100]}")
    rng = random.Random(SEED)
    order = list(range(len(pool))); rng.shuffle(order)
    pool = [pool[i] for i in order]

    def clarity(s):
        return (2 if s["bin"] in BINS else 0) + (1 if s["emotion_class"] else 0) + (1 if s["bin"] in BINS and s["intensity_src"] == "parenthetical" else 0)

    chosen, ep_count, spk_count = [], collections.Counter(), collections.Counter()
    caps = (SEAM_MAX_PER_EPISODE, SEAM_MAX_PER_SPEAKER)
    for caps in ((SEAM_MAX_PER_EPISODE, SEAM_MAX_PER_SPEAKER), (3, 8), (99, 99)):
        for s in sorted(pool, key=lambda s: (-clarity(s), 0 if s["shot_no"] else 1, 0 if s["adjacent"] else 1)):
            if len(chosen) >= TARGETS["SEAM-Bench"]:
                break
            if s in chosen or s["bin"] not in BINS or not s["emotion_class"]:
                continue
            if ep_count[s["ep"]] >= caps[0] or spk_count[s["base_cue"]] >= caps[1]:
                continue
            chosen.append(s); ep_count[s["ep"]] += 1; spk_count[s["base_cue"]] += 1
        if len(chosen) >= TARGETS["SEAM-Bench"]:
            break
    stats["caps_relaxed"] = caps
    stats["selected"] = len(chosen)
    return chosen, stats


def render_seam(shot: dict) -> tuple[Prompt, dict]:
    p = Prompt()
    p.glue("HEADER")
    if shot["scale_segs"]:
        for key, text in shot["scale_segs"]:
            p.segs.append(("glue", text, key))
    else:
        p.glue("SCALE_DEFAULT")
    p.glue("comma")
    cam_segs = []
    if shot["move_segs"]:
        cam_segs += shot["move_segs"]
    if shot["angle_segs"]:
        if cam_segs:
            cam_segs.append(("comma", ", "))
        cam_segs += shot["angle_segs"]
    if cam_segs:
        for key, text in cam_segs:
            p.segs.append(("glue", text, key))
    else:
        p.glue("CAMERA_DEFAULT")
    p.glue("period").glue("newline")
    p.src(shot["heading"], "txt").glue("period").glue("space")
    if shot["intro"]:
        p.src(shot["intro"], "txt")
        if not shot["intro"].endswith("."):
            p.glue("period")
        p.glue("space")
    p.src(shot["pre"], "txt").glue("space")
    cue = rendered_cue(shot["cue"])
    speech_segment(p, cue, shot["parenthetical"], shot["line"], "txt")
    if shot["sfx_sent"]:
        p.glue("space").glue("SFX_LEAD").src(shot["sfx_sent"], "txt")
    p.glue("newline").glue("FOOTER")
    return p, dict(role=cue, name_substitution=None)


def seam_raw(shot: dict) -> list[str]:
    return raw_lines(shot["heading"], shot["intro"], shot["pre"], rendered_cue(shot["cue"]), shot["parenthetical"], shot["line"])


# ----------------------------------------------------------------------------------------------
# FilmBench
# ----------------------------------------------------------------------------------------------
FB_SCALE = re.compile(r"\b(extreme close-up|big close-up|medium close-up|medium-close shot|medium close shot|partial extreme close-up|chest-up close shot|facial close-up|tight close-up|close-up|close shot|medium shot|medium long shot|medium-long shot|medium full shot|full shot|long shot|wide shot|extreme long shot)\b", re.I)
FB_CAMERA = re.compile(r"\b((?:static|fixed|locked-off|eye-level|low-angle|high-angle|handheld|slow|fast|rapid|slight)(?:[\w-]*)(?: (?:static|fixed|locked-off|eye-level|low-angle|high-angle|handheld|slow|fast|rapid|slight|over-the-shoulder|side|straight-on|upward-looking|dynamic|steadicam|lateral|rear-view|dolly|tracking))*"
                       r" (?:camera(?: position)?|shot|push-in|push in|pull-back|dolly-in|dolly|pan|tilt|tracking|zoom|move|movement))\b", re.I)
FB_CAMERA_CLAUSE = re.compile(r"\b(camera|shot|frame|composition|image|lens|push-in|pushes in|pushing in|push in|tracks?|tracking|pans?|panning|tilts?|tilting|dolly|zoom|orbit\w*|angle|close-up|"
                              r"close shot|medium shot|long shot|wide shot|rule-of-thirds|rule of thirds|depth of field|depth-of-field|atmosphere|lighting|the light is|light is|tone|tones|saturation|slow motion|locked-off|static|fixed)\b", re.I)
FB_GROUP = re.compile(r"\b(those around|the others|everyone|the crowd|crowd|soldiers|brothers|companions|the men|the group|the team|the family|the audience|people|opposite (him|her)|facing the (?!camera)|"
                      r"the other (man|woman|person)|two |both |together|voiceover|voice-over|off-camera voice)\b", re.I)
FB_NO_FACE = re.compile(r"\b((?:close-up|close shot) (?:of|on|focusing on) (?:a pair of |the |his |her |[A-Za-z' ]{0,25})?hands?\b|focusing on (?:a pair of )?hands|only (?:his|her) hands|back to the camera|from behind|silhouette)\b", re.I)
FB_FACES_CAMERA = re.compile(r"\b(face the camera|faces the camera|facing the camera|turns? (to|toward|towards) the camera)\b", re.I)
FB_PERSON = re.compile(r"\b((?:(?:young|old|elderly|middle-aged|little|tall|short|thin|slim|bald|muscular|gray-haired|grey-haired|white-haired|bearded|slender|stocky|handsome|beautiful|wealthy|poor|fat|white|black|asian|chinese|japanese|female|male)[\w-]* ){0,3}"
                       r"(?:man|woman|boy|girl|lady|gentleman|villager|coach|musician|minister|officer|prisoner|soldier|student|teacher|doctor|nurse|guard|king|queen|prince|princess|"
                       r"analyst|supervisor|conservator|speculator|superintendent|policeman|boxer|patient|intern|journalist|pianist|violinist|poet|sculptor|miner|laborer|dentist|attorney|prosecutor|"
                       r"commoner|programmer|housewife|peasant|citizen|townsman|clerk|cashier|bartender|"
                       r"defendant|juror|governor|diplomat|ambassador|duke|duchess|baron|noble|aristocrat|trader|peddler|pedestrian|chauffeur|commander|ranger|scout|climber|hiker|swimmer|runner|"
                       r"wrestler|fighter|champion|rival|opponent|teammate|employee|employer|grandson|granddaughter|nephew|niece|cousin|adult|senior|worker|guide|farmer|"
                       r"emperor|empress|general|captain|detective|waiter|waitress|chef|monk|priest|farmer|worker|driver|rider|clerk|cashier|manager|boss|businessman|businesswoman|"
                       r"lawyer|judge|policeman|cop|teenager|child|kid|grandmother|grandfather|mother|father|son|daughter|wife|husband|bride|groom|warrior|knight|servant|maid|"
                       r"butler|nobleman|noblewoman|scholar|official|merchant|beggar|thief|gangster|boxer|athlete|player|singer|actor|actress|dancer|painter|writer|reporter|"
                       r"host|anchor|pilot|sailor|fisherman|hunter|shepherd|cowboy|bandit|outlaw|sheriff|mayor|senator|president|chairman|executive|secretary|assistant|intern|"
                       r"apprentice|master|mistress|governess|nanny|tutor|professor|scientist|engineer|mechanic|technician|pharmacist|surgeon|patient|inmate|convict|suspect|"
                       r"witness|victim|customer|client|guest|visitor|tourist|passenger|stranger|neighbor|neighbour|friend|colleague|partner|lover|sweetheart|widow|widower|orphan|"
                       r"heir|heiress|tycoon|billionaire|millionaire|landlord|tenant|owner|shopkeeper|vendor|tailor|barber|dealer|banker|investor|broker|agent|spy|assassin|"
                       r"mercenary|pirate|samurai|ninja|swordsman|archer|rebel|revolutionary|protester|activist|monk|nun|abbot|disciple|elder|chief|leader|commander|lieutenant|"
                       r"sergeant|corporal|private|recruit|cadet|veteran|hero|heroine|villain|figure|person|individual|youth|adolescent|toddler|infant|baby))\b", re.I)


def build_filmbench(explore: bool) -> tuple[list[dict], dict]:
    segs = [json.loads(l) for l in open(FB_SEGS, encoding="utf-8")]
    raw = FB_RAW.read_text(encoding="utf-8")
    filt = collections.OrderedDict()
    filt["one-quote segments in filmbench_single_speaker_segments.jsonl"] = len(segs)
    s1 = [s for s in segs if s["single_speaker_strict"]]
    filt["single_speaker_strict"] = len(s1)
    s2 = [s for s in s1 if not re.search(r"Animation|Sci-Fi|Fantasy", s["genre"])]
    filt["+ live-action, non-sci-fi/fantasy genre"] = len(s2)
    s3 = [s for s in s2 if 3 <= s["quote_words"] <= 12]
    filt["+ quote 3-12 words"] = len(s3)
    s4 = [s for s in s3 if s["intensity_words"]]
    filt["+ intensity cue word present"] = len(s4)
    drops = collections.Counter()
    pool = []
    for s in s4:
        t = s["text"]
        if "@" in t:
            drops["reference tag (@scene/@character) in text"] += 1; continue
        if t not in raw:
            drops["segment text not verbatim in filmbench_prompts_en.csv"] += 1; continue
        q = s["quote"]
        qi = t.find('"' + q + '"')
        if qi < 0:
            qi = t.find(q)
        before, after = t[:qi].strip(), t[qi + len(q) + (2 if t[qi] == '"' else 0):].strip()
        body = t.replace(q, " ")
        persons, keys = [], []
        for m in FB_PERSON.finditer(body):
            ph = re.sub(r"^(the|a|an) ", "", m.group(1).lower())
            if ph in ("person", "figure") and re.search(r"\b(off-camera|off camera|offscreen|off-screen)\b", body, re.I):
                continue
            if ph == "figure" and re.search(r"\b(his|her) figure\b", body, re.I):
                continue
            qual = re.match(r"\s+(in|with|wearing|holding|who) (?:\w+ ){0,3}", body[m.end():])
            key = ph + ((" " + qual.group(0).strip()) if qual else "")
            same = [x for x in persons if ph == x or ph.endswith(" " + x) or x.endswith(" " + ph)]
            if same and (not qual or key in keys):
                continue  # same person described twice (young general / general)
            persons.append(ph); keys.append(key)
        if len(persons) >= 2 or len(keys) >= 2:
            drops["two person nouns in the segment (second person in frame)"] += 1; continue
        if re.search(r"\btimbre\b", body, re.I):
            drops["reference-voice note ('X's timbre') in text"] += 1; continue
        if re.search(r"\b(encased|helmet|mask|masked|visor|hooded|hood)\b", body, re.I):
            drops["face covered (helmet / mask / encased)"] += 1; continue
        if re.search(r"\b(distant view|in the distance|far away|appearing small|small in the frame)\b", body, re.I):
            drops["subject distant in frame"] += 1; continue
        if re.search(r"\b(phone|telephone|receiver|cell phone|on the line)\b", body, re.I):
            drops["phone conversation"] += 1; continue
        if FB_GROUP.search(body):
            drops["group / second person wording (those around him, facing the, beside him, two, both)"] += 1; continue
        if FB_NO_FACE.search(body) and not FB_FACES_CAMERA.search(body):
            drops["face not in frame (hands close-up, back to camera, silhouette)"] += 1; continue
        # cues: performance clauses only (camera / composition / atmosphere / lighting clauses removed), ambiguous words off
        perf = ", ".join(cl for cl in re.split(r"[;.,]\s*", body) if cl.strip() and not FB_CAMERA_CLAUSE.search(cl))
        b, cue_words, src, ecls, ecue, esrc = label("", perf)
        if b not in BINS:
            drops["no native intensity bin in the performance clauses (shared lexicon, ambiguous words off)"] += 1; continue
        if not ecls:
            drops["no native emotion class in the performance clauses (shared lexicon, ambiguous words off)"] += 1; continue
        scales = FB_SCALE.findall(t)
        cams = FB_CAMERA.findall(t)
        scale = scales[-1] if scales else None
        cam = cams[-1] if cams else None
        if cam and scale and cam.lower().find(scale.lower()) >= 0:
            cam = None
        person = None
        for m in FB_PERSON.finditer(before):
            if re.sub(r"^(the|a|an) ", "", m.group(1).lower()) not in ("person", "figure"):
                person = m
        gender = "unknown"
        f = len(re.findall(r"\b(she|her|hers|herself|woman|girl|lady|female)\b", t, re.I))
        m = len(re.findall(r"\b(he|his|him|himself|man|boy|gentleman|male)\b", t, re.I))
        if f > m: gender = "female"
        elif m > f: gender = "male"
        sfx_sent, sfx_hit = sfx_sentence(t.replace(q, " "))
        shot = dict(uid=s["uid"], shot_no=s["shot_no"], genre=s["genre"], task=s["task"], text=t, quote=q, before=before, after=after,
                    bin=b, intensity_cue=cue_words, intensity_src=src, emotion_class=ecls, emotion_cue=ecue, emotion_src=esrc,
                    scale=scale, cam=cam, person=person.group(0) if person else None, gender=gender, gender_evidence=f"pronoun/noun count {f}f/{m}m",
                    sfx_sent=sfx_sent, sfx_hit=sfx_hit, quote_words=s["quote_words"], perf=perf, multi_class=emotion_classes_in(perf))
        p, _ = render_fb(shot)
        n = words(p.text())
        if not (WORD_RANGE[0] <= n <= WORD_RANGE[1]):
            drops[f"rendered prompt outside {WORD_RANGE[0]}-{WORD_RANGE[1]} words"] += 1; continue
        shot["nwords"] = n
        pool.append(shot)
    for k, v in drops.items():
        filt[f"drop: {k}"] = v
    filt["eligible pool"] = len(pool)
    stats = dict(filters=filt, pool_bin_emotion=collections.Counter((s["bin"], s["emotion_class"]) for s in pool),
                 pool_genres=collections.Counter(s["genre"] for s in pool))
    if explore:
        print("FilmBench filters:")
        for k, v in filt.items():
            print(f"  {k}: {v}")
        print("  pool bin x emotion:", dict(stats["pool_bin_emotion"]))
        print("  pool genres:", dict(stats["pool_genres"]))
    rng = random.Random(SEED)
    order = list(range(len(pool))); rng.shuffle(order)
    pool = [pool[i] for i in order]
    supply = collections.Counter((s["bin"], s["emotion_class"]) for s in pool)
    # targets: exaggerated as available (<=1), the rest split calm/strong, classes water-filled
    targets = collections.Counter()
    n_exag = min(1, sum(v for (b, e), v in supply.items() if b == "exaggerated"))
    for _ in range(n_exag):
        e = max(EMOTIONS, key=lambda e: supply[("exaggerated", e)]); targets[("exaggerated", e)] += 1
    for _ in range(TARGETS["FilmBench"] - n_exag):
        opts = [(b, e) for b in ("calm", "strong") for e in EMOTIONS if supply[(b, e)] > targets[(b, e)]]
        if not opts:
            break
        bin_tot = {b: sum(v for (bb, e), v in targets.items() if bb == b) for b in ("calm", "strong")}
        emo_tot = {e: sum(v for (b, ee), v in targets.items() if ee == e) for e in EMOTIONS}
        b, e = min(opts, key=lambda be: (emo_tot[be[1]], bin_tot[be[0]], EMOTIONS.index(be[1]), be[0]))
        targets[(b, e)] += 1
    chosen, used_uid, genre_count = [], set(), collections.Counter()
    shortfall = collections.Counter()
    for cell, n in targets.items():
        for _ in range(n):
            best = None
            for s in pool:
                if (s["bin"], s["emotion_class"]) != cell or s["uid"] in used_uid or genre_count[s["genre"]] >= FB_MAX_PER_GENRE:
                    continue
                best = s; break
            if best is None:
                shortfall[cell] += 1; continue
            chosen.append(best); used_uid.add(best["uid"]); genre_count[best["genre"]] += 1
    for cap in (FB_MAX_PER_GENRE, FB_MAX_PER_GENRE + 1):
        while len(chosen) < TARGETS["FilmBench"]:
            fill = next((s for s in pool if s["uid"] not in used_uid and genre_count[s["genre"]] < cap), None)
            if fill is None:
                break
            chosen.append(fill); used_uid.add(fill["uid"]); genre_count[fill["genre"]] += 1
    stats.update(targets=dict(targets), shortfall=dict(shortfall))
    return chosen, stats


def render_fb(shot: dict) -> tuple[Prompt, dict]:
    p = Prompt()
    scale = ("source", shot["scale"], "csv") if shot["scale"] else ("glue", SCALE_DEFAULT, "SCALE_DEFAULT")
    cam = ("source", shot["cam"], "csv") if shot["cam"] else ("glue", CAMERA_DEFAULT, "CAMERA_DEFAULT")
    header_segment(p, scale, cam)
    p.src(shot["text"], "csv")
    p.glue("newline").glue("FOOTER")
    return p, dict(role=shot["person"], name_substitution=None)


def fb_raw(shot: dict) -> list[str]:
    return [shot["text"]]


def seam_excerpt(raw: str, shot: dict, limit: int = 400) -> str:
    """Raw .txt window (wrapped lines as in the file) that ends with the speech and contains the line's words."""
    first = shot["dlg_lines"][0]
    i = raw.find(shot["cue"] + " \n") if raw.find(shot["cue"] + " \n") >= 0 else raw.find(shot["cue"] + "\n")
    pos = raw.find(first, i if i >= 0 else 0)
    assert pos >= 0, (shot["ep"], first)
    end = pos
    for l in shot["dlg_lines"]:
        end = raw.find(l, end) + len(l)
    start = max(0, end - limit)
    window = raw[start:end]
    if start > 0 and "\n" in window:
        window = window.split("\n", 1)[1]
    window = window.strip("\n")
    assert window in raw and len(window) <= limit and apost(shot["line"]) in apost(window), shot["line"]
    return window


# ----------------------------------------------------------------------------------------------
# Validation
# ----------------------------------------------------------------------------------------------
def validate(prompt_text: str, segs: list[tuple[str, str, str]], sources: dict[str, str], shot_id: str) -> list[str]:
    errs = []
    if "".join(t for _, t, _ in segs) != prompt_text:
        errs.append("segments do not concatenate to the prompt")
    for kind, text, key in segs:
        if kind == "source":
            if norm(text) not in sources[key]:
                errs.append(f"source span not in {key}: {text[:80]!r}")
        elif kind == "glue":
            if text not in WHITELIST:
                errs.append(f"glue not in whitelist: {text!r}")
        else:
            errs.append(f"unknown segment kind {kind!r}: {text[:60]!r}")
    # independent residue check: strip source spans, tokenise the rest against the whitelist
    residue = prompt_text
    for kind, text, _ in segs:
        if kind == "source":
            i = residue.find(text)
            if i < 0:
                errs.append(f"span missing in prompt: {text[:60]!r}"); continue
            residue = residue[:i] + "\x00" + residue[i + len(text):]
    for chunk in residue.split("\x00"):
        s = chunk
        while s:
            for w in WHITELIST:
                if s.startswith(w):
                    s = s[len(w):]; break
            else:
                errs.append(f"non-whitelisted residue: {s[:60]!r}"); break
    return [f"{shot_id}: {e}" for e in errs]


def validate_raw(prompt_raw: str, raw: list[str], source: str, segs: list[tuple[str, str, str]], shot_id: str) -> list[str]:
    """prompt_raw = the source spans used in the prompt, one per line: every line is a whitespace-normalised substring of
    the source file and a span used in the prompt (the parenthetical with its parentheses); every prompt source span is
    a line of prompt_raw or inside one (the repeated `Sound:` sentence; FilmBench scale/camera inside the segment)."""
    errs = []
    if "\n".join(raw) != prompt_raw:
        errs.append("prompt_raw is not the newline join of its spans")
    spans = [t for k, t, _ in segs if k == "source"]
    for l in raw:
        if not l.strip() or "\n" in l:
            errs.append(f"prompt_raw line empty or multi-line: {l[:60]!r}")
        if norm(l) not in source:
            errs.append(f"prompt_raw line not in source: {l[:80]!r}")
        if l not in spans and not (l.startswith("(") and l.endswith(")") and l[1:-1] in spans):
            errs.append(f"prompt_raw line is not a span used in the prompt: {l[:60]!r}")
    for t in spans:
        if not any(t in l for l in raw):
            errs.append(f"prompt source span missing from prompt_raw: {t[:60]!r}")
    return [f"{shot_id}: {e}" for e in errs]


# ----------------------------------------------------------------------------------------------
# Rows + manifest
# ----------------------------------------------------------------------------------------------
def line_len_bucket(n: int) -> str:
    return "3-5" if n <= 5 else "6-8" if n <= 8 else "9-12"


def prompt_len_bucket(n: int) -> str:
    return "40-79" if n < 80 else "80-109" if n < 110 else "110-139" if n < 140 else "140-160"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--explore", action="store_true")
    ap.add_argument("--no-reallocate", action="store_true", help="keep DramaBench at 60 even if SEAM-Bench supply is short (total < 90)")
    args = ap.parse_args()

    seam_shots, seam_stats = build_seam(args.explore)
    fb_shots, fb_stats = build_filmbench(args.explore)
    short = (TARGETS["SEAM-Bench"] - len(seam_shots)) + (TARGETS["FilmBench"] - len(fb_shots))
    db_target = TARGETS["DramaBench"] + (0 if args.no_reallocate else short)
    db_shots, db_stats = build_dramabench(args.explore, db_target)
    db_stats["reallocated"] = 0 if args.no_reallocate else short
    if args.explore:
        print("selected:", len(db_shots), len(seam_shots), len(fb_shots))
        print("DB targets:", db_stats["targets"], "shortfall:", dict(db_stats["shortfall"]), "refill:", dict(db_stats["refill"]))
        print("FB targets:", fb_stats["targets"], "shortfall:", fb_stats["shortfall"])
        return

    scripts = {}
    for ln in open(DB_SCRIPTS, encoding="utf-8"):
        r = json.loads(ln); scripts[r["id"]] = r
    seam_txt_raw, seam_txt_norm = {}, {}
    for f in sorted(glob.glob(str(SEAM_DIR / "script/episodes/ep*_en.txt"))):
        ep = int(re.search(r"ep(\d+)", f).group(1))
        seam_txt_raw[ep] = open(f, encoding="utf-8").read()
        seam_txt_norm[ep] = norm(seam_txt_raw[ep])
    fb_raw_csv = FB_RAW.read_text(encoding="utf-8")

    rows, errors = [], []
    # ---- DramaBench rows ----
    db_sorted = sorted(db_shots, key=lambda s: (BINS.index(s["native_intensity_bin"]), EMOTIONS.index(s["emotion_class"]), s["script_id"]))
    for k, s in enumerate(db_sorted, 1):
        p, meta = render_db(s)
        text = p.text()
        raw = db_raw(s); raw_text = "\n".join(raw)
        fs = scripts[s["script_id"]]["full_script"]
        errors += validate(text, p.segs, {"script": norm(fs)}, f"DB-{k:02d}")
        errors += validate_raw(raw_text, raw, norm(fs), p.segs, f"DB-{k:02d}")
        trope, _ = classify_trope(scripts[s["script_id"]]["title"], scripts[s["script_id"]]["description"])
        notes = []
        if s["speaker_kind"] == "role":
            notes.append("speaker cue is a role noun: kept verbatim")
        if meta["role"] != s["cue"]:
            notes.append(f"source cue line is {s['cue']!r}: the (CONT'D) continuation marker is not rendered")
        if s["fol"]:
            notes.append("following action included (speaker's own action)")
        if not s["adjacent"]:
            notes.append("preceding action is the nearest action paragraph in the scene (dialogue intervenes)")
        if s["intensity_cue_source"] == "action":
            notes.append("intensity cue comes from the adjacent action line, not the parenthetical")
        if s["emotion_cue_source"] == "action":
            notes.append("emotion cue comes from the adjacent action line")
        if s["sfx_sent"] and s["sfx_sent"] in s["pre"]:
            notes.append("SFX sentence is part of the preceding action (repeated after 'Sound:')")
        if len(s["multi_class"]) > 1:
            notes.append(f"parenthetical has keywords of several emotion classes {s['multi_class']}; class = first keyword occurrence (review)")
        if s["native_intensity_bin"] == "exaggerated" and any(w in EXAG_GESTURE for w in s["intensity_cue"]):
            notes.append("exaggerated label rests on a performed-emotion / gesture / hysteria cue (clutching her chest, pretending, fake, overly, hysterically): confirm the comedic register")
        rows.append(dict(
            shot_id=f"DB-{k:02d}", prompt=text, prompt_raw=raw_text, prompt_framed_vs_raw_note=RAW_NOTE, line=s["line"], speaker_cue=s["cue"], speaker_role=meta["role"], speaker_gender=s["gender"],
            name_substitution=None, character_description_source=s["intro"], setting=s["setting"], preceding_action=s["pre"],
            following_action=s["fol"], parenthetical=s["parenthetical"], emotion_class=s["emotion_class"], emotion_cue=s["emotion_cue"],
            native_intensity_bin=s["native_intensity_bin"], intensity_cue=s["intensity_cue"], target_intensity_interval=INTERVALS[s["native_intensity_bin"]],
            sfx_cue=s["sfx_sent"], shot_scale=SCALE_DEFAULT, camera=CAMERA_DEFAULT, shot_scale_source="default",
            trope_category=trope or "unclassified", source_dataset="DramaBench", source_id=s["script_id"],
            source_file=SOURCE_META["DramaBench"]["file"], source_license=SOURCE_META["DramaBench"]["license"], source_url=SOURCE_META["DramaBench"]["url"],
            source_excerpt=db_excerpt(fs, s), language="en", duration_s=8, aspect_ratio="9:16", negative_prompt=NEGATIVE_PROMPT,
            prompt_sha256=sha256(text), glue_tokens_used=p.glue_keys(), notes="; ".join(notes) or None,
            _family=s["family"], _coarse_family=s["coarse_family"], _title=scripts[s["script_id"]]["title"], _sfx_hit=s["sfx_hit"],
            _gender_evidence=s["gender_evidence"], _cue_src=s["intensity_cue_source"],
        ))
    # ---- SEAM rows ----
    seam_sorted = sorted(seam_shots, key=lambda s: (s["ep"], int(s["shot_no"] or 0), s["line"]))
    for k, s in enumerate(seam_sorted, 1):
        p, meta = render_seam(s)
        text = p.text()
        raw = seam_raw(s); raw_text = "\n".join(raw)
        errors += validate(text, p.segs, {"txt": seam_txt_norm[s["ep"]]}, f"SB-{k:02d}")
        errors += validate_raw(raw_text, raw, seam_txt_norm[s["ep"]], p.segs, f"SB-{k:02d}")
        notes = [f"all spans from ep{s['ep']:02d}_en.txt (PDF-extracted: wraps joined, glued page numbers cut)"]
        if meta["role"] != s["cue"]:
            notes.append(f"source cue line is {s['cue']!r}: the (CONT'D) continuation marker is not rendered")
        if s["shot_no"]:
            notes.append(f"director CSV ep{s['csv_ep']:02d}.csv 分镜号 {s['shot_no']} matched (ratio {s['match_ratio']}) for 景别/拍摄角度/运镜 and 中文台词"
                         + (f"; director's line variant: {s['csv_line']!r}" if apost(s["csv_line"]) != apost(s["line"]) else ""))
        else:
            notes.append("no director CSV row matches this line: default shot scale / camera")
        if not s["adjacent"]:
            notes.append("preceding action is the nearest action paragraph in the scene (dialogue intervenes)")
        for fld, rest in (("景别", s["scale_rest"]), ("运镜", s["move_rest"]), ("拍摄角度", s["angle_rest"])):
            if rest:
                notes.append(f"{fld} remainder not in dictionary, not rendered: {rest!r}")
        if s["shot_no"] and s["move"] is None and (s["yunjing"] or "").strip():
            notes.append("运镜 unmapped: no movement rendered")
        if s["intensity_src"] == "action":
            notes.append("intensity cue comes from the preceding action, not the parenthetical")
        if s["emotion_src"] == "action":
            notes.append("emotion cue comes from the preceding action")
        if s["sfx_sent"] and s["sfx_sent"] in s["pre"]:
            notes.append("SFX sentence is part of the preceding action (repeated after 'Sound:')")
        if len(s["multi_class"]) > 1:
            notes.append(f"parenthetical has keywords of several emotion classes {s['multi_class']}; class = first keyword occurrence (review)")
        scale_txt = s["scale"] or SCALE_DEFAULT
        cam_txt = ", ".join(x for x in (s["move"], s["angle"]) if x) or CAMERA_DEFAULT
        src_file = f"data/sources/seambench/dramas/his-toyboy/script/episodes/ep{s['ep']:02d}_en.txt" + (
            f" (+ director/ep{s['csv_ep']:02d}.csv 分镜号 {s['shot_no']} for shot grammar)" if s["shot_no"] else "")
        rows.append(dict(
            shot_id=f"SB-{k:02d}", prompt=text, prompt_raw=raw_text, prompt_framed_vs_raw_note=RAW_NOTE, line=s["line"], speaker_cue=s["cue"], speaker_role=meta["role"], speaker_gender=s["gender"],
            name_substitution=None, character_description_source=s["intro"], setting=s["heading"], preceding_action=s["pre"],
            following_action=None, parenthetical=s["parenthetical"], emotion_class=s["emotion_class"], emotion_cue=s["emotion_cue"],
            native_intensity_bin=s["bin"], intensity_cue=s["intensity_cue"], target_intensity_interval=INTERVALS[s["bin"]],
            sfx_cue=s["sfx_sent"], shot_scale=scale_txt, camera=cam_txt,
            shot_scale_source=(f"景别={s['jingbie']}; 拍摄角度={s['jiaodu']}; 运镜={s['yunjing']}" if s["shot_no"] else "default"),
            trope_category="vertical drama (SEAM)", source_dataset="SEAM-Bench", source_id=f"his-toyboy/ep{s['ep']:02d}_en.txt {s['cue']}" + (f" (director ep{s['csv_ep']:02d}#{s['shot_no']})" if s["shot_no"] else ""),
            source_file=src_file, source_license=SOURCE_META["SEAM-Bench"]["license"], source_url=SOURCE_META["SEAM-Bench"]["url"],
            source_excerpt=seam_excerpt(seam_txt_raw[s["ep"]], s), line_zh=s["line_zh"], language="en", duration_s=8, aspect_ratio="9:16", negative_prompt=NEGATIVE_PROMPT,
            prompt_sha256=sha256(text), glue_tokens_used=p.glue_keys(), notes="; ".join(notes),
            _family=fine_family(s["heading"]), _coarse_family=setting_family(s["heading"]), _title="His Toyboy: The Billionaire's Trap", _sfx_hit=s["sfx_hit"],
            _gender_evidence=s["gender_evidence"], _cue_src=s["intensity_src"],
        ))
    # ---- FilmBench rows ----
    fb_sorted = sorted(fb_shots, key=lambda s: (BINS.index(s["bin"]), EMOTIONS.index(s["emotion_class"]), s["uid"]))
    for k, s in enumerate(fb_sorted, 1):
        p, meta = render_fb(s)
        text = p.text()
        raw = fb_raw(s); raw_text = "\n".join(raw)
        errors += validate(text, p.segs, {"csv": fb_raw_csv}, f"FB-{k:02d}")
        errors += validate_raw(raw_text, raw, fb_raw_csv, p.segs, f"FB-{k:02d}")
        notes = ["whole storyboard segment used verbatim (it carries setting, look, action, cue, line and shot grammar); no speech glue needed"]
        if not s["scale"] or not s["cam"]:
            notes.append("segment names no " + " / ".join(x for x, v in (("shot scale", s["scale"]), ("camera", s["cam"])) if not v) + ": default used in the header")
        notes.append("cues read from the performance clauses only (camera / composition / atmosphere / lighting clauses removed; ambiguous words off)")
        if len(s["multi_class"]) > 1:
            notes.append(f"performance clauses have keywords of several emotion classes {s['multi_class']}; class = first keyword occurrence (review)")
        excerpt = s["text"] if len(s["text"]) <= 400 else excerpt_around(s["text"], '"' + s["quote"] + '"' if '"' + s["quote"] + '"' in s["text"] else s["quote"], 400)
        rows.append(dict(
            shot_id=f"FB-{k:02d}", prompt=text, prompt_raw=raw_text, prompt_framed_vs_raw_note=RAW_NOTE, line=s["quote"], speaker_cue=s["person"], speaker_role=s["person"], speaker_gender=s["gender"],
            name_substitution=None, character_description_source=None, setting=None, preceding_action=s["before"] or None,
            following_action=s["after"] or None, parenthetical=None, emotion_class=s["emotion_class"], emotion_cue=s["emotion_cue"],
            native_intensity_bin=s["bin"], intensity_cue=s["intensity_cue"], target_intensity_interval=INTERVALS[s["bin"]],
            sfx_cue=s["sfx_sent"], shot_scale=s["scale"] or SCALE_DEFAULT, camera=s["cam"] or CAMERA_DEFAULT,
            shot_scale_source=(", ".join(x for x in (s["scale"], s["cam"]) if x) or "default"),
            trope_category=s["genre"], source_dataset="FilmBench", source_id=f"{s['uid']} shot {s['shot_no']}",
            source_file=SOURCE_META["FilmBench"]["file"], source_license=SOURCE_META["FilmBench"]["license"], source_url=SOURCE_META["FilmBench"]["url"],
            source_excerpt=excerpt, language="en", duration_s=8, aspect_ratio="9:16", negative_prompt=NEGATIVE_PROMPT,
            prompt_sha256=sha256(text), glue_tokens_used=p.glue_keys(), notes="; ".join(notes),
            _family="(FilmBench: no heading)", _coarse_family="(FilmBench: no heading)", _title=s["uid"], _sfx_hit=s["sfx_hit"],
            _gender_evidence=s["gender_evidence"], _cue_src=s["intensity_src"],
        ))

    # ---- global checks ----
    for r in rows:
        n = words(r["prompt"])
        if not (WORD_RANGE[0] <= n <= WORD_RANGE[1]):
            errors.append(f"{r['shot_id']}: {n} words outside {WORD_RANGE}")
        if r["line"] not in r["prompt"]:
            errors.append(f"{r['shot_id']}: line not in prompt")
        if r["line"] not in r["prompt_raw"]:
            errors.append(f"{r['shot_id']}: line not in prompt_raw")
        if r["prompt_framed_vs_raw_note"] != RAW_NOTE or r["name_substitution"] is not None:
            errors.append(f"{r['shot_id']}: fixed fields wrong")
        low = r["prompt"].lower()
        for w in (r["intensity_cue"] or []) + (r["emotion_cue"] or []):
            if w.lower() not in low:
                errors.append(f"{r['shot_id']}: cue {w!r} not in prompt")
        if r["emotion_class"] not in EMOTIONS or r["native_intensity_bin"] not in BINS:
            errors.append(f"{r['shot_id']}: missing native label")
    if len({r["line"] for r in rows}) != len(rows):
        errors.append("duplicate lines")
    if len({r["prompt"] for r in rows}) != len(rows):
        errors.append("duplicate prompts")
    db_scripts = [r["source_id"] for r in rows if r["source_dataset"] == "DramaBench"]
    if len(set(db_scripts)) != len(db_scripts):
        errors.append("DramaBench: more than one shot per script")
    fam = collections.Counter(r["_family"] for r in rows if r["source_dataset"] == "DramaBench")
    if any(v > MAX_PER_FAMILY for v in fam.values()):
        errors.append(f"DramaBench: setting family over cap: {[k for k, v in fam.items() if v > MAX_PER_FAMILY]}")
    if errors:
        print("VALIDATION FAILED")
        for e in errors:
            print("  ", e)
        sys.exit(1)
    print(f"validation OK: {len(rows)} shots, 0 violations")

    # ---- write jsonl ----
    with open(OUT_JSONL, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({k: v for k, v in r.items() if not k.startswith("_")}, ensure_ascii=False) + "\n")

    # ---- manifest ----
    def t(counter, title, order=None):
        return table(counter, title, order)
    src_order = ["DramaBench", "SEAM-Bench", "FilmBench"]
    by_src = collections.Counter(r["source_dataset"] for r in rows)
    db_rows = [r for r in rows if r["source_dataset"] == "DramaBench"]
    wc = [words(r["prompt"]) for r in rows]
    m = []
    m.append(f"# prompt_set_v2 manifest\n\nBuilt {DATE} by `scripts/build_prompt_set_v2.py` (seed {SEED}). {len(rows)} distinct single-speaker English dialogue shots, "
             f"one prompt each, no variants. Every prompt is verbatim source text inside a fixed technical frame; emotion class and intensity bin are the source's own cues.\n")
    m.append("## 1. Selection procedure\n")
    m.append(f"- Targets: DramaBench {TARGETS['DramaBench']}, SEAM-Bench {TARGETS['SEAM-Bench']}, FilmBench {TARGETS['FilmBench']} (research note `sources_deep_dive.md`, recommended mix). "
             f"Achieved: {by_src['DramaBench']} / {by_src['SEAM-Bench']} / {by_src['FilmBench']}. "
             + (f"**SEAM-Bench supply is short**: only {len(seam_shots)} lines carry both a native intensity bin and an emotion class after the filters in section 2, so the {db_stats['reallocated']} missing shots were re-allocated to DramaBench (ample supply); run with `--no-reallocate` for 60/{len(seam_shots)}/{len(fb_shots)} = {60 + len(seam_shots) + len(fb_shots)} shots instead." if db_stats["reallocated"] else "All three targets met."))
    m.append(f"- Deterministic: each eligible pool is shuffled once with `random.Random({SEED})`, then filled greedily by cell (bin x emotion) with the constraints below; ties go to the earliest shuffled candidate.")
    m.append(f"- DramaBench cells (target {db_stats['target']}): exaggerated water-filled across classes up to {EXAG_TARGET_DB} as supply allows (got {db_stats['n_exag_target']}), the remaining {db_stats['target'] - db_stats['n_exag_target']} split evenly over calm/strong x six classes "
             f"({(db_stats['target'] - db_stats['n_exag_target']) // 12} per cell, remainder to the cells with the most supply). Constraints: one shot per script; at most {MAX_PER_FAMILY} per fine setting family; "
             f"gender steered toward balance (unknown gender at most {MAX_UNKNOWN_GENDER_DB}); SFX-cued candidates preferred (+3) until {SFX_TARGET_DB} shots carry one; +1 for a first-appearance description, +1 for a parenthetical-sourced cue.")
    m.append(f"  - cell targets: {dict((f'{b}/{e}', v) for (b, e), v in db_stats['targets'].items() if v)}; shortfall: {dict((f'{b}/{e}', v) for (b, e), v in db_stats['shortfall'].items()) or 'none'}; refilled from other cells: {dict((f'{b}/{e}', v) for (b, e), v in db_stats['refill'].items()) or 'none'}.")
    m.append(f"- SEAM-Bench: only lines with both a native intensity bin and an emotion class are eligible; they are ordered by clarity score = native bin (+2) + emotion class (+1) + parenthetical-sourced cue (+1), then by 'has a matching director row' and 'adjacent action'; at most {SEAM_MAX_PER_EPISODE} per episode and {SEAM_MAX_PER_SPEAKER} per speaker, caps relaxed stepwise when supply is short (final caps used: {seam_stats['caps_relaxed']}).")
    m.append(f"- FilmBench: cells water-filled over calm/strong x six classes (exaggerated 1 if available), at most {FB_MAX_PER_GENRE} per genre, one per source row (uid). targets: {dict((f'{b}/{e}', v) for (b, e), v in fb_stats['targets'].items())}; shortfall: {fb_stats['shortfall'] or 'none'}.")
    m.append("")
    m.append("## 2. Filters and counts\n")
    for name, st in (("DramaBench", db_stats), ("SEAM-Bench", seam_stats), ("FilmBench", fb_stats)):
        m.append(f"### {name}\n\n| filter | n |\n|---|---|")
        for k, v in st["filters"].items():
            m.append(f"| {k} | {v} |")
        m.append("")
    m.append(f"DramaBench pool bin x emotion (eligible, before selection): " + ", ".join(f"{b}/{e} {db_stats['pool_bin_emotion'][(b, e)]}" for b in BINS for e in EMOTIONS) + f". Pool with usable SFX: {db_stats['pool_sfx']}; gender {dict(db_stats['pool_gender'])}; scripts {db_stats['pool_scripts']}.\n")
    m.append(f"SEAM pool bins: {dict(seam_stats['pool_bins'])}; bin x emotion: {dict((f'{b}/{e}', v) for (b, e), v in seam_stats['pool_bin_emotion'].items())}.\n")
    m.append(f"FilmBench pool bin x emotion: {dict((f'{b}/{e}', v) for (b, e), v in fb_stats['pool_bin_emotion'].items())}; genres: {dict(fb_stats['pool_genres'])}.\n")
    m.append("## 3. Final distribution\n")
    m.append(t(by_src, "source", src_order) + "\n")
    m.append(t(collections.Counter(r["native_intensity_bin"] for r in rows), "native intensity bin (all 90)", BINS) + "\n")
    m.append(cross_table(rows, "source_dataset", "native_intensity_bin", src_order, BINS) + "\n")
    m.append(t(collections.Counter(r["emotion_class"] for r in rows), "emotion class (all 90)", EMOTIONS) + "\n")
    m.append(cross_table(rows, "native_intensity_bin", "emotion_class", BINS, EMOTIONS) + "\n")
    m.append("DramaBench only:\n\n" + cross_table(db_rows, "native_intensity_bin", "emotion_class", BINS, EMOTIONS) + "\n")
    m.append(cross_table([dict(r, sfx="yes" if r["sfx_cue"] else "no") for r in rows], "source_dataset", "sfx", src_order, ["yes", "no"]) + "\n")
    m.append(cross_table(rows, "source_dataset", "speaker_gender", src_order, ["female", "male", "unknown"]) + "\n")
    m.append(t(collections.Counter(r["_coarse_family"] for r in db_rows), "DramaBench coarse setting family (v1 taxonomy)") + "\n")
    m.append(t(collections.Counter(r["_family"] for r in db_rows), "DramaBench fine setting family (cap 2)") + "\n")
    m.append(t(collections.Counter(r["_family"] for r in rows if r["source_dataset"] == "SEAM-Bench"), "SEAM-Bench setting family") + "\n")
    m.append(t(collections.Counter(r["trope_category"] for r in rows), "trope category / genre") + "\n")
    m.append(t(collections.Counter(r["shot_scale"] for r in rows), "shot scale (header)") + "\n")
    m.append(t(collections.Counter(r["camera"] for r in rows), "camera (header)") + "\n")
    m.append(t(collections.Counter(line_len_bucket(words(r["line"])) for r in rows), "line length (words)", ["3-5", "6-8", "9-12"]) + "\n")
    m.append(t(collections.Counter(prompt_len_bucket(n) for n in wc), "prompt length (words)", ["40-79", "80-109", "110-139", "140-160"]) + f"\n\nPrompt length range {min(wc)}-{max(wc)} words, median {sorted(wc)[len(wc) // 2]}.\n")
    m.append(t(collections.Counter(r["_cue_src"] for r in rows), "intensity cue source") + "\n")
    m.append(t(collections.Counter(r["_sfx_hit"].lower() for r in rows if r["_sfx_hit"]), "SFX cue strings") + "\n")
    m.append("## 4. Prompt assembly and the exact glue whitelist\n")
    m.append("Layout (DramaBench / SEAM): `HEADER {scale}, {camera}.` newline `{setting}. {first-appearance description}. {preceding action} {speaker cue} says {parenthetical}: \"{line}\"` "
             "(or `{speaker cue}, {parenthetical}, says: \"{line}\"` when the parenthetical is not an adverb phrase) `{following action if the speaker's own} Sound: {SFX sentence}` newline `FOOTER`. "
             "FilmBench: `HEADER {scale}, {camera}.` newline `{whole segment verbatim}` newline `FOOTER`. Whitespace inside multi-line source paragraphs is collapsed to single spaces; no other change.\n")
    m.append("| key | exact string |\n|---|---|")
    for k, v in GLUE.items():
        m.append(f"| `{k}` | `{json.dumps(v, ensure_ascii=False)}` |")
    m.append("\nNo name substitution: every speaker cue (personal name or role noun) is rendered verbatim as a source span, by the user's decision of 2026-11-07 (section 6); `name_substitution` is null on every row.\n")
    m.append("Validation (`validate()`): every `source` segment is a substring of its source file after whitespace normalisation (DramaBench: the record's `full_script`; SEAM: the episode .txt for every span; FilmBench: the raw CSV); "
             "every `glue` segment is one of the strings above; and, independently, the prompt with all source spans removed tokenises completely into whitelist strings. `prompt_raw` is validated the same way (`validate_raw()`, section 7). Any violation prints and fails the build.\n")
    m.append("## 5. SEAM-Bench Chinese-to-English dictionary\n")
    for fld, d in SEAM_DICT.items():
        m.append(f"- {fld}: " + ", ".join(f"{zh} = {en}" for zh, en in d.items()))
    m.append(f"- 拍摄角度 `过X关系` / `过X` (over-the-shoulder past character X) = {SEAM_OTS[0]}; compounds joined with `, ` or ` to ` (`侧面-正面` = profile to frontal). Character-name prefixes (维克多近景, 米洛近) are stripped before lookup. Untranslated remainders are recorded in `notes`, never rendered.\n")
    m.append("| shot | 景别 | 拍摄角度 | 运镜 | rendered |\n|---|---|---|---|---|")
    for r in rows:
        if r["source_dataset"] == "SEAM-Bench":
            if r["shot_scale_source"] == "default":
                m.append(f"| {r['shot_id']} | (no matching director row) | | | {r['shot_scale']}, {r['camera']} |"); continue
            parts = dict(x.split("=", 1) for x in r["shot_scale_source"].split("; "))
            m.append(f"| {r['shot_id']} | {parts['景别']} | {parts['拍摄角度']} | {parts['运镜']} | {r['shot_scale']}, {r['camera']} |")
    m.append("\n## 6. Speaker cues\n")
    m.append("Names are kept verbatim by the user's decision of 2026-11-07: no name substitution, every speaker cue (personal name or role noun) is a verbatim source span, and `name_substitution` is null on every row.")
    contd = [r for r in rows if r["source_dataset"] != "FilmBench" and r["speaker_cue"] != r["speaker_role"]]
    if contd:
        m.append("A trailing `(CONT'D)` continuation marker on the cue line is not rendered (" + ", ".join(f"{r['shot_id']} `{r['speaker_cue']}`" for r in contd) + "); the name itself is the source span (noted per row).")
    kept = [r for r in rows if r["source_dataset"] != "FilmBench"]
    m.append(f"\nSpeaker cues as rendered ({len(kept)}): " + ", ".join(f"{r['shot_id']} `{r['speaker_role']}`" for r in kept) + "\n")
    m.append("## 7. prompt_raw\n")
    m.append("Every row also carries `prompt_raw`: the verbatim source block with no header, no footer and no glue, i.e. exactly the source spans used in the prompt, in source order, one per line (single newlines): "
             "setting heading, first-appearance description (if used), preceding action, speaker cue line, parenthetical in parentheses (if any), dialogue line, following action (if used). "
             "FilmBench: the verbatim segment text. SEAM-Bench: the verbatim lines from the episode .txt (PDF wraps joined). The `Sound:` sentence is not repeated: it is a sentence of the preceding or following action already present. "
             "Validation (`validate_raw()`): every line is a whitespace-normalised substring of the source file and a span used in the prompt, and every prompt source span is a line of `prompt_raw` or inside one. "
             f"`prompt_framed_vs_raw_note` on every row = `{RAW_NOTE}`.\n")
    m.append("## 8. Licensing and attribution\n")
    m.append(f"- DramaBench (FutureMa/DramaBench, {SOURCE_META['DramaBench']['url']}): {SOURCE_META['DramaBench']['license']}. Attribution: Ma, Huang, Lin, \"DramaBench\" (arXiv 2512.19012). {by_src['DramaBench']} shots.")
    m.append(f"- SEAM-Bench (Jackyqq/SEAM-Bench, {SOURCE_META['SEAM-Bench']['url']}): CC BY-NC 4.0, \"the SEAM-Bench authors and the respective rights holders of the underlying short dramas\"; non-commercial research use only; drama \"His Toyboy: The Billionaire's Trap\" (arXiv 2608.22725). {by_src['SEAM-Bench']} shots.")
    m.append(f"- FilmBench (skylenage/FilmBench, {SOURCE_META['FilmBench']['url']}): Apache-2.0. Lines are reverse-engineered from film clips, so some are translated film dialogue. {by_src['FilmBench']} shots.")
    m.append("- Each row carries `source_dataset`, `source_id`, `source_file`, `source_license`, `source_url`, `source_excerpt` (verbatim, <= 400 chars, contains the line).\n")
    m.append("## 9. What changed versus v1\n")
    m.append("- v1: 30 shots x 3 authored intensity variants (calm / strong / comedic) = 90 prompts, with EmoTrace wording, authored voice/pace lines, wardrobe/lighting fields and a comedic tag. "
             "v2: 90 distinct shots, one prompt each, no variants, no rewriting; the only non-source text is the whitelist in section 4. Emotion and intensity are read off the source's own cues; `unbinned` lines are excluded.")
    m.append("- v1 drew DramaBench lines from the raw extractor; v2 re-cuts every span from `full_script` paragraphs (the candidate file truncates action lines at 300 chars), uses the nearest action paragraph in the scene (adjacent preferred, +2 in the pick score; non-adjacent cases are noted per shot) and includes the following action only when it is the speaker's own.")
    m.append(f"- Sources: v1 = DramaBench 24 + FilmBench 4 + AVGen-Bench 2; v2 targets DramaBench 60 + SEAM-Bench 15 + FilmBench 15 (no AVGen-Bench, no EmoTrace), achieved {by_src['DramaBench']} / {by_src['SEAM-Bench']} / {by_src['FilmBench']} (section 1).")
    m.append("- prompt_set_v1 files are untouched and remain the reference.\n")
    m.append("## 10. Sign-off list for the user\n")
    m.append("1. Exaggerated supply: DramaBench eligible exaggerated candidates are few (see section 2); the set has "
             f"{sum(1 for r in rows if r['native_intensity_bin'] == 'exaggerated')} exaggerated shots in total, none with class anger (no native supply). Acceptable?")
    m.append("2. Should `unbinned-but-emotion-cued` lines (e.g. parenthetical `smiling`, `confused`, `firmly`) be admitted later with a default interval? v2 excludes them.")
    m.append(f"3. Default shot scale for DramaBench is `{SCALE_DEFAULT}` with `{CAMERA_DEFAULT}` (no native shot grammar there). OK, or prefer `close-up`?")
    m.append("4. SEAM lines come from the episode .txt (whole speech, PDF wraps joined, glued page numbers cut). The director CSV is a different draft (about half of its lines were rewritten or added by the director and have no .txt counterpart), so it is used only for 景别/拍摄角度/运镜 and 中文台词 when a row matches the line (ratio >= 0.6); unmatched lines carry the default header. OK?")
    exag_cues = sorted({w for r in rows if r["native_intensity_bin"] == "exaggerated" for w in r["intensity_cue"]})
    m.append(f"5. The exaggerated cues in the set are {exag_cues}; rows whose cue is a performed emotion, gesture or hysteria carry a 'confirm the comedic register' note. Please confirm they fit the comedic [3,4] interval (the two `clutching her chest` rows read as physical distress, not comedy).")
    m.append(f"6. FilmBench prompts repeat the segment's own shot/camera wording in the header; the speaker-count filter is heuristic, so please eyeball the {by_src['FilmBench']} for a second person in frame. 53 r2v segments with `@scene`/`@character` reference tags were excluded; admitting them would restore the 15.")
    m.append("7. The spec's header ends `{camera} .`; the renderer writes `{camera}.` (no space before the period). Confirm.")
    m.append("8. SFX sentences that are part of the preceding action are repeated after `Sound:`; fine, or render `Sound:` only for sentences outside the action?")
    m.append(f"9. SEAM-Bench supplies only {by_src['SEAM-Bench']} shots: the shared lexicon cannot bin its compound parentheticals (`stammering, mortified`, `hollow, looking away`, `weak, raspy`, `hardening, powerless`, `dead, ruthless`, `straightening, fatal`). Admit those with a hand-assigned bin later, or keep SEAM at {by_src['SEAM-Bench']}? The shortfall was re-allocated to DramaBench (section 1); `--no-reallocate` keeps 60/{by_src['SEAM-Bench']}/{by_src['FilmBench']}.")
    m.append("10. Keyword labels are native but noisy: the class is the first keyword hit (e.g. `shouts in terror` -> anger, a winded boxer's `gasping` -> surprise, `calculated smile` -> happiness). Rows with keywords from several classes carry a 'review' note; a hand pass over emotion_class before Eval (a) is recommended.")
    m.append("11. Dropped-candidate rules added during review (section 2): negated cues, physical stage directions, cues attributed to bystanders or lighting, vanishing smiles, second spoken lines, phone calls, covered or distant faces. They are conservative; relax any that seem too strict.")
    OUT_MANIFEST.write_text("\n".join(m) + "\n", encoding="utf-8")
    print(f"wrote {OUT_JSONL} ({OUT_JSONL.stat().st_size} bytes) and {OUT_MANIFEST} ({OUT_MANIFEST.stat().st_size} bytes)")
    print("prompt words:", min(wc), "-", max(wc))


if __name__ == "__main__":
    main()
