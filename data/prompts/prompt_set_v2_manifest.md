# prompt_set_v2 manifest

Built 2026-11-07 by `scripts/build_prompt_set_v2.py` (seed 20261103). 90 distinct single-speaker English dialogue shots, one prompt each, no variants. Every prompt is verbatim source text inside a fixed technical frame; emotion class and intensity bin are the source's own cues.

## 1. Selection procedure

- Targets: DramaBench 60, SEAM-Bench 15, FilmBench 15 (research note `sources_deep_dive.md`, recommended mix). Achieved: 69 / 7 / 14. **SEAM-Bench supply is short**: only 7 lines carry both a native intensity bin and an emotion class after the filters in section 2, so the 9 missing shots were re-allocated to DramaBench (ample supply); run with `--no-reallocate` for 60/7/14 = 81 shots instead.
- Deterministic: each eligible pool is shuffled once with `random.Random(20261103)`, then filled greedily by cell (bin x emotion) with the constraints below; ties go to the earliest shuffled candidate.
- DramaBench cells (target 69): exaggerated water-filled across classes up to 12 as supply allows (got 10), the remaining 59 split evenly over calm/strong x six classes (4 per cell, remainder to the cells with the most supply). Constraints: one shot per script; at most 2 per fine setting family; gender steered toward balance (unknown gender at most 4); SFX-cued candidates preferred (+3) until 30 shots carry one; +1 for a first-appearance description, +1 for a parenthetical-sourced cue.
  - cell targets: {'exaggerated/sadness': 2, 'exaggerated/surprise': 1, 'exaggerated/happiness': 5, 'exaggerated/contempt': 2, 'calm/anger': 4, 'calm/sadness': 4, 'calm/fear': 4, 'calm/surprise': 4, 'calm/happiness': 5, 'calm/contempt': 5, 'strong/anger': 5, 'strong/sadness': 5, 'strong/fear': 5, 'strong/surprise': 5, 'strong/happiness': 4, 'strong/contempt': 4}; shortfall: {'strong/contempt': 1}; refilled from other cells: {'calm/anger': 1, 'calm/sadness': 1, 'calm/fear': 1, 'calm/surprise': 1, 'calm/happiness': 1, 'calm/contempt': 1}.
- SEAM-Bench: only lines with both a native intensity bin and an emotion class are eligible; they are ordered by clarity score = native bin (+2) + emotion class (+1) + parenthetical-sourced cue (+1), then by 'has a matching director row' and 'adjacent action'; at most 2 per episode and 6 per speaker, caps relaxed stepwise when supply is short (final caps used: (99, 99)).
- FilmBench: cells water-filled over calm/strong x six classes (exaggerated 1 if available), at most 3 per genre, one per source row (uid). targets: {'strong/anger': 2, 'calm/sadness': 4, 'calm/fear': 1, 'strong/surprise': 1, 'calm/happiness': 1, 'calm/contempt': 2, 'strong/fear': 3, 'strong/happiness': 1}; shortfall: {('calm', 'sadness'): 1, ('strong', 'fear'): 1}.

## 2. Filters and counts

### DramaBench

| filter | n |
|---|---|
| candidates in dramabench_candidates_native.jsonl | 5948 |
| native intensity bin (calm/strong/exaggerated) | 2774 |
| + native emotion class | 1773 |
| + line 3-12 words | 1773 |
| drop: native cue not inside the rendered spans (came from a non-adjacent / unused action line) | 185 |
| drop: personal-name speaker whose gender the script does not state | 136 |
| drop: speaker cue off-camera (V.O./O.S.) | 41 |
| drop: action-line cue belongs to bystanders (children, crowd, guests) | 21 |
| drop: parenthetical is off-camera stage business (V.O., into phone, in unison, to himself...) | 47 |
| drop: action-line cue belongs to another character | 202 |
| drop: dialogue block has more than one line (line is not the whole speech) | 7 |
| drop: action-line cue is withdrawn by the next verb (smile fades / grin vanishes) | 14 |
| drop: parenthetical is beat/pause/reading | 10 |
| drop: phone conversation (action/line) | 11 |
| drop: intensity cue is a physical stage direction, not delivery (head snaps, shaking off) | 12 |
| drop: preceding action carries a second spoken line (audio/quote) | 23 |
| drop: negated cue (e.g. 'not panicked') | 11 |
| drop: group / voice speaker cue | 4 |
| drop: action-line cue describes lighting / environment, not the speaker (warm candlelight) | 4 |
| drop: no action paragraph in the scene before the cue | 12 |
| drop: action-line cue sentence has another subject (a BABY cries, the gallery murmurs) | 7 |
| drop: role-noun cue with (CONT'D) (would render verbatim) | 1 |
| eligible pool | 1025 |

### SEAM-Bench

| filter | n |
|---|---|
| dialogue cues in the 23 episode .txt files | 132 |
| after excluding episodes 1, 2, 7, 8, 9 entirely | 97 |
| drop: V.O. / O.S. / on-card cue | 32 |
| drop: action-line cue describes lighting / environment, not the speaker (warm candlelight) | 1 |
| drop: no parenthetical (no native cue) | 16 |
| drop: speech outside 3-12 words | 22 |
| drop: director 景别 is a two-shot (二人/两人) | 2 |
| drop: action-line cue belongs to another character | 2 |
| drop: parenthetical off-camera (to himself / into phone) | 1 |
| drop: phone conversation line | 1 |
| drop: preceding action carries a second spoken line (audio/quote) | 1 |
| eligible pool | 19 |
| eligible with a native intensity bin | 9 |
| eligible with bin AND emotion class | 7 |
| eligible with a matching director CSV row (shot grammar) | 18 |

### FilmBench

| filter | n |
|---|---|
| one-quote segments in filmbench_single_speaker_segments.jsonl | 1869 |
| single_speaker_strict | 628 |
| + live-action, non-sci-fi/fantasy genre | 261 |
| + quote 3-12 words | 170 |
| + intensity cue word present | 134 |
| drop: face not in frame (hands close-up, back to camera, silhouette) | 3 |
| drop: no native intensity bin in the performance clauses (shared lexicon, ambiguous words off) | 19 |
| drop: subject distant in frame | 2 |
| drop: two person nouns in the segment (second person in frame) | 21 |
| drop: no native emotion class in the performance clauses (shared lexicon, ambiguous words off) | 10 |
| drop: phone conversation | 3 |
| drop: face covered (helmet / mask / encased) | 4 |
| drop: group / second person wording (those around him, facing the, beside him, two, both) | 1 |
| drop: reference tag (@scene/@character) in text | 53 |
| drop: reference-voice note ('X's timbre') in text | 1 |
| eligible pool | 17 |

DramaBench pool bin x emotion (eligible, before selection): calm/anger 19, calm/sadness 27, calm/fear 45, calm/surprise 18, calm/happiness 45, calm/contempt 104, strong/anger 182, strong/sadness 185, strong/fear 254, strong/surprise 112, strong/happiness 20, strong/contempt 4, exaggerated/anger 0, exaggerated/sadness 2, exaggerated/fear 0, exaggerated/surprise 1, exaggerated/happiness 5, exaggerated/contempt 2. Pool with usable SFX: 100; gender {'female': 586, 'male': 420, 'unknown': 19}; scripts 554.

SEAM pool bins: {'unbinned': 10, 'calm': 4, 'exaggerated': 1, 'strong': 4}; bin x emotion: {'unbinned/fear': 1, 'unbinned/happiness': 2, 'unbinned/None': 5, 'calm/surprise': 1, 'calm/contempt': 2, 'unbinned/anger': 1, 'exaggerated/contempt': 1, 'unbinned/contempt': 1, 'strong/None': 2, 'strong/fear': 1, 'calm/happiness': 1, 'strong/happiness': 1}.

FilmBench pool bin x emotion: {'calm/sadness': 4, 'strong/surprise': 1, 'calm/contempt': 2, 'strong/fear': 3, 'strong/anger': 2, 'calm/happiness': 1, 'calm/fear': 3, 'strong/happiness': 1}; genres: {'Chinese Comedy': 5, 'International Historical': 1, 'Chinese Action': 1, 'Chinese Romance': 1, 'Chinese Mystery': 1, 'International Thriller': 1, 'International Romance': 2, 'Chinese Family': 2, 'International Biographical': 1, 'International Sports': 1, 'International Action': 1}.

## 3. Final distribution

| source | n |
|---|---|
| DramaBench | 69 |
| SEAM-Bench | 7 |
| FilmBench | 14 |

| native intensity bin (all 90) | n |
|---|---|
| calm | 44 |
| strong | 35 |
| exaggerated | 11 |

| source_dataset \ native_intensity_bin | calm | strong | exaggerated | total |
|---|---|---|---|---|
| DramaBench | 32 | 27 | 10 | 69 |
| SEAM-Bench | 4 | 2 | 1 | 7 |
| FilmBench | 8 | 6 | 0 | 14 |
| total | 44 | 35 | 11 | 90 |

| emotion class (all 90) | n |
|---|---|
| anger | 12 |
| sadness | 15 |
| fear | 15 |
| surprise | 13 |
| happiness | 19 |
| contempt | 16 |

| native_intensity_bin \ emotion_class | anger | sadness | fear | surprise | happiness | contempt | total |
|---|---|---|---|---|---|---|---|
| calm | 5 | 8 | 7 | 6 | 8 | 10 | 44 |
| strong | 7 | 5 | 8 | 6 | 6 | 3 | 35 |
| exaggerated | 0 | 2 | 0 | 1 | 5 | 3 | 11 |
| total | 12 | 15 | 15 | 13 | 19 | 16 | 90 |

DramaBench only:

| native_intensity_bin \ emotion_class | anger | sadness | fear | surprise | happiness | contempt | total |
|---|---|---|---|---|---|---|---|
| calm | 5 | 5 | 5 | 5 | 6 | 6 | 32 |
| strong | 5 | 5 | 5 | 5 | 4 | 3 | 27 |
| exaggerated | 0 | 2 | 0 | 1 | 5 | 2 | 10 |
| total | 10 | 12 | 10 | 11 | 15 | 11 | 69 |

| source_dataset \ sfx | yes | no | total |
|---|---|---|---|
| DramaBench | 30 | 39 | 69 |
| SEAM-Bench | 1 | 6 | 7 |
| FilmBench | 1 | 13 | 14 |
| total | 32 | 58 | 90 |

| source_dataset \ speaker_gender | female | male | unknown | total |
|---|---|---|---|---|
| DramaBench | 34 | 34 | 1 | 69 |
| SEAM-Bench | 2 | 5 | 0 | 7 |
| FilmBench | 6 | 8 | 0 | 14 |
| total | 42 | 47 | 1 | 90 |

| DramaBench coarse setting family (v1 taxonomy) | n |
|---|---|
| bedroom | 2 |
| home | 15 |
| hospital | 6 |
| hotel | 4 |
| industrial | 1 |
| nature | 2 |
| office | 3 |
| other | 11 |
| palace | 7 |
| public_building | 4 |
| restaurant | 7 |
| street | 4 |
| vehicle | 1 |
| wedding | 2 |

| DramaBench fine setting family (cap 2) | n |
|---|---|
| ancestral hall | 1 |
| antique shop | 1 |
| apartment | 1 |
| balcony | 1 |
| banquet hall | 1 |
| bar | 1 |
| bathhouse | 1 |
| bedroom | 2 |
| brothel | 1 |
| building stairwell | 1 |
| caf  | 1 |
| cafeteria | 1 |
| cemetery | 1 |
| clearing | 1 |
| courtyard | 2 |
| delivery room | 1 |
| den | 1 |
| doorway | 1 |
| dungeon | 1 |
| factory | 1 |
| farmhouse courtyard | 1 |
| floor area | 1 |
| funeral shop | 1 |
| hospital | 1 |
| hospital corridor | 1 |
| hospital room | 1 |
| hospital ward | 1 |
| hotel | 1 |
| hotel lobby | 1 |
| hotel room | 1 |
| house entrance | 1 |
| infusion room | 1 |
| kitchen | 1 |
| living room | 2 |
| lottery shop | 1 |
| lounge | 1 |
| manor courtyard | 1 |
| mansion | 1 |
| mansion staircase | 1 |
| market | 1 |
| modern office | 1 |
| mourning hall | 1 |
| night road | 1 |
| office | 2 |
| party | 1 |
| plaza | 1 |
| pool | 1 |
| private room | 1 |
| residence | 1 |
| restaurant | 1 |
| roadside | 1 |
| room | 2 |
| rural courtyard | 1 |
| space | 2 |
| stone | 1 |
| street | 1 |
| train car | 1 |
| venue | 2 |
| villa | 1 |
| village | 1 |
| warehouse | 1 |
| wasteland | 1 |

| SEAM-Bench setting family | n |
|---|---|
| canyon | 1 |
| capital | 1 |
| estate | 1 |
| highway | 1 |
| penthouse | 3 |

| trope category / genre | n |
|---|---|
| Ancient Court Intrigue | 7 |
| Chinese Action | 1 |
| Chinese Comedy | 3 |
| Chinese Family | 1 |
| Chinese Mystery | 1 |
| Chinese Romance | 1 |
| Corporate & Business War | 6 |
| International Action | 1 |
| International Biographical | 1 |
| International Historical | 1 |
| International Romance | 2 |
| International Sports | 1 |
| International Thriller | 1 |
| Social Realism | 16 |
| Suspense & Thriller | 10 |
| Sweet Romance | 6 |
| Time Travel & Rebirth | 9 |
| Underdog Comeback | 13 |
| unclassified | 2 |
| vertical drama (SEAM) | 7 |

| shot scale (header) | n |
|---|---|
| chest-up close shot | 1 |
| close shot | 5 |
| close-up | 2 |
| medium close-up | 77 |
| medium close-up to medium shot | 1 |
| medium shot | 4 |

| camera (header) | n |
|---|---|
| eye-level locked-off camera | 3 |
| eye-level locked-off shot | 2 |
| eye-level static shot | 1 |
| high-angle locked-off shot | 1 |
| locked-off eye-level camera | 1 |
| rapid pan | 1 |
| slow pull-back, eye level | 1 |
| slow push-in | 1 |
| slow push-in, over-the-shoulder | 2 |
| slow tilt | 1 |
| static camera | 2 |
| static camera, eye level | 73 |
| static camera, slight high angle | 1 |

| line length (words) | n |
|---|---|
| 3-5 | 39 |
| 6-8 | 25 |
| 9-12 | 26 |

| prompt length (words) | n |
|---|---|
| 40-79 | 71 |
| 80-109 | 15 |
| 110-139 | 4 |
| 140-160 | 0 |

Prompt length range 49-120 words, median 71.

| intensity cue source | n |
|---|---|
| action | 22 |
| parenthetical | 68 |

| SFX cue strings | n |
|---|---|
| bang | 1 |
| beeping | 1 |
| clattering | 1 |
| clatters | 1 |
| clink | 1 |
| commotion | 2 |
| crashing | 1 |
| door bursts open | 1 |
| door slams | 1 |
| glass shatters | 1 |
| pounds on | 1 |
| rain | 4 |
| rip | 1 |
| rips | 1 |
| screeches | 1 |
| shatters | 2 |
| slams down | 1 |
| slams her | 1 |
| slams the | 1 |
| slapping | 1 |
| slaps | 3 |
| smashes | 1 |
| splash | 1 |
| splashing | 1 |
| thud | 1 |

## 4. Prompt assembly and the exact glue whitelist

Layout (DramaBench / SEAM): `HEADER {scale}, {camera}.` newline `{setting}. {first-appearance description}. {preceding action} {speaker cue} says {parenthetical}: "{line}"` (or `{speaker cue}, {parenthetical}, says: "{line}"` when the parenthetical is not an adverb phrase) `{following action if the speaker's own} Sound: {SFX sentence}` newline `FOOTER`. FilmBench: `HEADER {scale}, {camera}.` newline `{whole segment verbatim}` newline `FOOTER`. Whitespace inside multi-line source paragraphs is collapsed to single spaces; no other change.

| key | exact string |
|---|---|
| `HEADER` | `"Vertical 9:16 framing, head and shoulders fill the frame, subject centred. "` |
| `SCALE_DEFAULT` | `"medium close-up"` |
| `CAMERA_DEFAULT` | `"static camera, eye level"` |
| `FOOTER` | `"Live-action short-drama look. Audio on; the line is spoken on camera."` |
| `SFX_LEAD` | `"Sound: "` |
| `says` | `" says: \""` |
| `says {parenthetical}` | `" says "` |
| `{parenthetical}, says` | `", "` |
| `colon-quote` | `": \""` |
| `close-quote` | `"\""` |
| `comma` | `", "` |
| `period` | `"."` |
| `space` | `" "` |
| `newline` | `"\n"` |
| `SEAM:景别:大特写` | `"extreme close-up"` |
| `SEAM:景别:特写` | `"close-up"` |
| `SEAM:景别:近景` | `"medium close-up"` |
| `SEAM:景别:近` | `"medium close-up"` |
| `SEAM:景别:中近景` | `"medium close-up"` |
| `SEAM:景别:中近` | `"medium close-up"` |
| `SEAM:景别:中景` | `"medium shot"` |
| `SEAM:景别:中` | `"medium shot"` |
| `SEAM:景别:小全` | `"medium long shot"` |
| `SEAM:景别:小全景` | `"medium long shot"` |
| `SEAM:景别:全景` | `"wide shot"` |
| `SEAM:景别:全` | `"wide shot"` |
| `SEAM:拍摄角度:平视` | `"eye level"` |
| `SEAM:拍摄角度:微微仰视` | `"slight low angle"` |
| `SEAM:拍摄角度:仰视` | `"low angle"` |
| `SEAM:拍摄角度:微微俯视` | `"slight high angle"` |
| `SEAM:拍摄角度:俯视` | `"high angle"` |
| `SEAM:拍摄角度:俯拍` | `"high angle"` |
| `SEAM:拍摄角度:微微俯拍` | `"slight high angle"` |
| `SEAM:拍摄角度:仰拍` | `"low angle"` |
| `SEAM:拍摄角度:侧面` | `"profile"` |
| `SEAM:拍摄角度:微微侧面` | `"slight profile"` |
| `SEAM:拍摄角度:正面` | `"frontal"` |
| `SEAM:拍摄角度:微微倾斜` | `"slight Dutch tilt"` |
| `SEAM:拍摄角度:过肩` | `"over-the-shoulder"` |
| `SEAM:拍摄角度:过手机拍` | `"framed past the phone"` |
| `SEAM:拍摄角度:过手机` | `"framed past the phone"` |
| `SEAM:拍摄角度:过窗户` | `"through the window"` |
| `SEAM:运镜:固定镜头` | `"static camera"` |
| `SEAM:运镜:固定` | `"static camera"` |
| `SEAM:运镜:缓推` | `"slow push-in"` |
| `SEAM:运镜:缓拉` | `"slow pull-back"` |
| `SEAM:运镜:缓慢横移` | `"slow lateral tracking"` |
| `SEAM:运镜:横移` | `"lateral tracking"` |
| `SEAM:运镜:微微晃动` | `"slight handheld shake"` |
| `SEAM:运镜:跟摇` | `"tracking pan"` |
| `SEAM:运镜:跟` | `"tracking shot"` |
| `SEAM:运镜:升格` | `"slow motion"` |
| `SEAM:运镜:缓慢移` | `"slow camera move"` |
| `SEAM:运镜:快推` | `"fast push-in"` |
| `SEAM:运镜:推` | `"push-in"` |
| `SEAM:运镜:拉` | `"pull-back"` |
| `SEAM:运镜:摇` | `"pan"` |
| `SEAM:运镜:环绕` | `"orbit"` |
| `SEAM:拍摄角度:过X关系` | `"over-the-shoulder"` |
| `SEAM:to-connector` | `" to "` |
| `says-verb` | `"says: \""` |

No name substitution: every speaker cue (personal name or role noun) is rendered verbatim as a source span, by the user's decision of 2026-11-07 (section 6); `name_substitution` is null on every row.

Validation (`validate()`): every `source` segment is a substring of its source file after whitespace normalisation (DramaBench: the record's `full_script`; SEAM: the episode .txt for every span; FilmBench: the raw CSV); every `glue` segment is one of the strings above; and, independently, the prompt with all source spans removed tokenises completely into whitelist strings. `prompt_raw` is validated the same way (`validate_raw()`, section 7). Any violation prints and fails the build.

## 5. SEAM-Bench Chinese-to-English dictionary

- 景别: 大特写 = extreme close-up, 特写 = close-up, 近景 = medium close-up, 近 = medium close-up, 中近景 = medium close-up, 中近 = medium close-up, 中景 = medium shot, 中 = medium shot, 小全 = medium long shot, 小全景 = medium long shot, 全景 = wide shot, 全 = wide shot
- 拍摄角度: 平视 = eye level, 微微仰视 = slight low angle, 仰视 = low angle, 微微俯视 = slight high angle, 俯视 = high angle, 俯拍 = high angle, 微微俯拍 = slight high angle, 仰拍 = low angle, 侧面 = profile, 微微侧面 = slight profile, 正面 = frontal, 微微倾斜 = slight Dutch tilt, 过肩 = over-the-shoulder, 过手机拍 = framed past the phone, 过手机 = framed past the phone, 过窗户 = through the window
- 运镜: 固定镜头 = static camera, 固定 = static camera, 缓推 = slow push-in, 缓拉 = slow pull-back, 缓慢横移 = slow lateral tracking, 横移 = lateral tracking, 微微晃动 = slight handheld shake, 跟摇 = tracking pan, 跟 = tracking shot, 升格 = slow motion, 缓慢移 = slow camera move, 快推 = fast push-in, 推 = push-in, 拉 = pull-back, 摇 = pan, 环绕 = orbit
- 拍摄角度 `过X关系` / `过X` (over-the-shoulder past character X) = over-the-shoulder; compounds joined with `, ` or ` to ` (`侧面-正面` = profile to frontal). Character-name prefixes (维克多近景, 米洛近) are stripped before lookup. Untranslated remainders are recorded in `notes`, never rendered.

| shot | 景别 | 拍摄角度 | 运镜 | rendered |
|---|---|---|---|---|
| SB-01 | 近景 | 微微俯视 | 固定 | medium close-up, static camera, slight high angle |
| SB-02 | 近景 | 平视 | 固定 | medium close-up, static camera, eye level |
| SB-03 | 近 | 微俯视 | 固定 | medium close-up, static camera |
| SB-04 | 近 | 过米洛 | 缓推 | medium close-up, slow push-in, over-the-shoulder |
| SB-05 | 近-中景 | 平视 | 缓拉 | medium close-up to medium shot, slow pull-back, eye level |
| SB-06 | 近 | 过哈珀 | 缓推 | medium close-up, slow push-in, over-the-shoulder |
| SB-07 | (no matching director row) | | | medium close-up, static camera, eye level |

## 6. Speaker cues

Names are kept verbatim by the user's decision of 2026-11-07: no name substitution, every speaker cue (personal name or role noun) is a verbatim source span, and `name_substitution` is null on every row.
A trailing `(CONT'D)` continuation marker on the cue line is not rendered (SB-03 `SERENA (CONT'D)`, SB-05 `VICTOR (CONT'D)`, SB-07 `JULIAN (CONT'D)`); the name itself is the source span (noted per row).

Speaker cues as rendered (76): DB-01 `PEI SHANGYU`, DB-02 `YAO QINGQING`, DB-03 `YI SHUQIN`, DB-04 `LIU YUEYING`, DB-05 `XIA YAO`, DB-06 `OFFICE WORKER`, DB-07 `HU DING'AN`, DB-08 `WANG XUCHEN`, DB-09 `LIN FEI`, DB-10 `LING YUE`, DB-11 `YE LIN`, DB-12 `LIU PIAOXUE`, DB-13 `CHEN LIE`, DB-14 `LIU ZHI`, DB-15 `HOSPITAL MAN`, DB-16 `XU ZHIYI`, DB-17 `LU BOYAN`, DB-18 `FU ZHOUCHENG`, DB-19 `LOTTERY SHOP OWNER`, DB-20 `JIANG SICHEN`, DB-21 `LU HUAIXING`, DB-22 `SHEN MENGYAN`, DB-23 `BOSS ZHOU`, DB-24 `ZHUANG LI`, DB-25 `YOUNG ZHAO QIN`, DB-26 `CHU YANG`, DB-27 `MING HAO`, DB-28 `DA EN`, DB-29 `SONG CI`, DB-30 `YE LINGTIAN`, DB-31 `UNCLE`, DB-32 `LING TIAN`, DB-33 `LI WUJIANG`, DB-34 `NALAN YANRAN`, DB-35 `HE XI`, DB-36 `MOTHER-IN-LAW`, DB-37 `RED-ROBED WOMAN`, DB-38 `HAITONG`, DB-39 `XIAO YU`, DB-40 `YE CHEN`, DB-41 `RULONG`, DB-42 `YOUNG CHEN MING`, DB-43 `MADAM`, DB-44 `SONG QINGHUA`, DB-45 `SHEN SHULI`, DB-46 `CHEN XIAOTING`, DB-47 `WU SHUANGHUA`, DB-48 `ELDEST DAUGHTER OF THE YE FAMILY`, DB-49 `ZHOU LINGSHAN`, DB-50 `FEMALE EMPLOYEE 1`, DB-51 `CHEN XIAOYING`, DB-52 `CHU TIAN`, DB-53 `LIU HANYAN`, DB-54 `SHENG CANGLANG`, DB-55 `SU LIANG`, DB-56 `ZHAO HAI`, DB-57 `SCARFACE`, DB-58 `JIANG XU`, DB-59 `YE TIAN`, DB-60 `RUAN NINGXIA`, DB-61 `SONG WAN`, DB-62 `LIN XINLAN`, DB-63 `DEMON MONK WUXIN`, DB-64 `GU YUTING`, DB-65 `THUG`, DB-66 `YE HUANG`, DB-67 `CHEN YUZHEN`, DB-68 `LIN DALI`, DB-69 `LI YUE`, SB-01 `JULIAN`, SB-02 `SERENA`, SB-03 `SERENA`, SB-04 `VICTOR`, SB-05 `VICTOR`, SB-06 `JULIAN`, SB-07 `JULIAN`

## 7. prompt_raw

Every row also carries `prompt_raw`: the verbatim source block with no header, no footer and no glue, i.e. exactly the source spans used in the prompt, in source order, one per line (single newlines): setting heading, first-appearance description (if used), preceding action, speaker cue line, parenthetical in parentheses (if any), dialogue line, following action (if used). FilmBench: the verbatim segment text. SEAM-Bench: the verbatim lines from the episode .txt (PDF wraps joined). The `Sound:` sentence is not repeated: it is a sentence of the preceding or following action already present. Validation (`validate_raw()`): every line is a whitespace-normalised substring of the source file and a span used in the prompt, and every prompt source span is a line of `prompt_raw` or inside one. `prompt_framed_vs_raw_note` on every row = `prompt = header + source spans + whitelist glue + footer; prompt_raw = source spans only`.

## 8. Licensing and attribution

- DramaBench (FutureMa/DramaBench, https://huggingface.co/datasets/FutureMa/DramaBench): MIT (HF README; provenance caveat: paper says scripts come from an 'english_short_drama_scripts_dataset' whose license is never named). Attribution: Ma, Huang, Lin, "DramaBench" (arXiv 2512.19012). 69 shots.
- SEAM-Bench (Jackyqq/SEAM-Bench, https://huggingface.co/datasets/Jackyqq/SEAM-Bench): CC BY-NC 4.0, "the SEAM-Bench authors and the respective rights holders of the underlying short dramas"; non-commercial research use only; drama "His Toyboy: The Billionaire's Trap" (arXiv 2608.22725). 7 shots.
- FilmBench (skylenage/FilmBench, https://huggingface.co/datasets/skylenage/FilmBench): Apache-2.0. Lines are reverse-engineered from film clips, so some are translated film dialogue. 14 shots.
- Each row carries `source_dataset`, `source_id`, `source_file`, `source_license`, `source_url`, `source_excerpt` (verbatim, <= 400 chars, contains the line).

## 9. What changed versus v1

- v1: 30 shots x 3 authored intensity variants (calm / strong / comedic) = 90 prompts, with EmoTrace wording, authored voice/pace lines, wardrobe/lighting fields and a comedic tag. v2: 90 distinct shots, one prompt each, no variants, no rewriting; the only non-source text is the whitelist in section 4. Emotion and intensity are read off the source's own cues; `unbinned` lines are excluded.
- v1 drew DramaBench lines from the raw extractor; v2 re-cuts every span from `full_script` paragraphs (the candidate file truncates action lines at 300 chars), uses the nearest action paragraph in the scene (adjacent preferred, +2 in the pick score; non-adjacent cases are noted per shot) and includes the following action only when it is the speaker's own.
- Sources: v1 = DramaBench 24 + FilmBench 4 + AVGen-Bench 2; v2 targets DramaBench 60 + SEAM-Bench 15 + FilmBench 15 (no AVGen-Bench, no EmoTrace), achieved 69 / 7 / 14 (section 1).
- prompt_set_v1 files are untouched and remain the reference.

## 10. Sign-off list for the user

1. Exaggerated supply: DramaBench eligible exaggerated candidates are few (see section 2); the set has 11 exaggerated shots in total, none with class anger (no native supply). Acceptable?
2. Should `unbinned-but-emotion-cued` lines (e.g. parenthetical `smiling`, `confused`, `firmly`) be admitted later with a default interval? v2 excludes them.
3. Default shot scale for DramaBench is `medium close-up` with `static camera, eye level` (no native shot grammar there). OK, or prefer `close-up`?
4. SEAM lines come from the episode .txt (whole speech, PDF wraps joined, glued page numbers cut). The director CSV is a different draft (about half of its lines were rewritten or added by the director and have no .txt counterpart), so it is used only for 景别/拍摄角度/运镜 and 中文台词 when a row matches the line (ratio >= 0.6); unmatched lines carry the default header. OK?
5. The exaggerated cues in the set are ['clutching her chest', 'fake', 'hysterically', 'laughing maniacally', 'maniacal', 'maniacally', 'mock surprise', 'pretending', 'sickly sweet']; rows whose cue is a performed emotion, gesture or hysteria carry a 'confirm the comedic register' note. Please confirm they fit the comedic [3,4] interval (the two `clutching her chest` rows read as physical distress, not comedy).
6. FilmBench prompts repeat the segment's own shot/camera wording in the header; the speaker-count filter is heuristic, so please eyeball the 14 for a second person in frame. 53 r2v segments with `@scene`/`@character` reference tags were excluded; admitting them would restore the 15.
7. The spec's header ends `{camera} .`; the renderer writes `{camera}.` (no space before the period). Confirm.
8. SFX sentences that are part of the preceding action are repeated after `Sound:`; fine, or render `Sound:` only for sentences outside the action?
9. SEAM-Bench supplies only 7 shots: the shared lexicon cannot bin its compound parentheticals (`stammering, mortified`, `hollow, looking away`, `weak, raspy`, `hardening, powerless`, `dead, ruthless`, `straightening, fatal`). Admit those with a hand-assigned bin later, or keep SEAM at 7? The shortfall was re-allocated to DramaBench (section 1); `--no-reallocate` keeps 60/7/14.
10. Keyword labels are native but noisy: the class is the first keyword hit (e.g. `shouts in terror` -> anger, a winded boxer's `gasping` -> surprise, `calculated smile` -> happiness). Rows with keywords from several classes carry a 'review' note; a hand pass over emotion_class before Eval (a) is recommended.
11. Dropped-candidate rules added during review (section 2): negated cues, physical stage directions, cues attributed to bystanders or lighting, vanishing smiles, second spoken lines, phone calls, covered or distant faces. They are conservative; relax any that seem too strict.
