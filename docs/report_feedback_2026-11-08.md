# Corrections for the midway report (Overleaf "329z midway report", Midway_Report.tex)

Checked against the experiments as built and run: `docs/DESIGN.md`, `docs/PLAN.md`, `docs/report_tables.md`, `runs/loop/*/report.md`. Where the report and these files disagree, the files are right.

## Naming
1. [Title, §1, Fig. 1] The body calls the system "Auditing the Loop" while Fig. 1 says "Auditing the Loop". Use one name for the system everywhere. The GitHub repository and package follow the report's name.
2. [§1, §3.4] "trajectory-aware planner", "tri-factor diagnostic space", "empirical uncertainty", "strict dollar budgets". Use the terms of the implementation: the Analyser; the three labels severity, uncertainty state and fixability; a round cap K = 8. Cost is recorded per round but no dollar cap is enforced.

## Section 2.1, models
3. "GPT-5.6-Luna as the text Analyser, Gemini 3.5 Flash-Lite alongside Qwen3.8-Omni-Flash as verifiers" is the configuration that produced the reported runs on 2026-11-07. The code now defaults to one google/gemini-4-argon call per checklist family and gemini-4-argon as the Analyser; that configuration has not been run end to end. Say which configuration the results come from.

## Section 2.2, data
4. [§2.2, Table 1, §4] "a validated 90-shot evaluation suite": 90 is the number of framed candidates. The prompt set used in all experiments is 30 shots: DramaBench 22, SEAM-Bench 3, FilmBench 5; intensity bins calm 14, strong 12, exaggerated 4. Suggested: "From the framed candidates we selected the 30-shot prompt set used in all experiments." Drop the 90-shot column from Table 1.
5. "32 explicit sound-effect cues": 14 of the 30 shots carry a sound cue.
6. Selection "maximises checkability, ASR feasibility, and genre coverage": the score is 0.30 checkability + 0.25 feasibility + 0.20 ASR-friendliness + 0.15 cue clarity + 0.10 length, with quotas on source, intensity bin, sound cue, speaker gender and emotion class, and at most one shot per source script.
7. Add licences and exclusions: DramaBench MIT on Hugging Face with the upstream licence unnamed; SEAM-Bench CC BY-NC 4.0 with episodes 1, 2, 7, 8 and 9 excluded; FilmBench Apache-2.0. None of the three is peer-reviewed as of 2026-11-07.

## Section 2.3 and §4, evaluation claims
8. Human labels on 60 takes, Cohen's kappa, the ten-checklist audit, baselines B0/B1/B2, the held-out evaluator, the priming ablation and regression statistics have not been run. They are the plan. Write them in future tense. What exists: five end-to-end loop runs and one prototype-versus-panel comparison on a pilot take.
9. "Gemini 4 Argon, certified for audio-video fidelity" as held-out evaluator: there is no such certification, and gemini-4-argon is now the in-loop verifier, so the held-out judge must come from a different model family.

## Section 3, method
10. [§3.1] "the Analyser decomposes the source prompt into atomic requirements": rules write the dialogue item, the setting and sound items, the cast item from the script, the framing item, all rendering items and the emotion items; the model extracts actions, props, other people present and premise facts, each tied to a span copied from the script. The 30 checklists have 18 to 23 items, mean 20.5.
11. [§3.2] "verification budget ≤ $0.05 per take": measured $0.02 to $0.03 per take with 19 to 25 calls. Say target and measured.
12. [§3.3 Eq. 1, Fig. 1 caption, §3.4] The stop rule: a blocking item is an error with uncertainty state confident or uncertain, regardless of fixability. No blocking item: release. At least one blocking item that is prompt- or retry-fixable: next round. Every blocking item backend-limited: hand off, never release. Hand-off also at K = 8. Remove the fixability term from the blocking set; four of the five runs were handed off at rounds 2 to 4, none at the cap.
13. [§3.3] "at most three reinspections": one re-inspect per uncertain item, no cap of three.
14. [§3.3] "Priors are calibrated within training folds": the fixability prior is a hand-written table per check, to be revised once after the pilot. No fold calibration was done.

## Section 4, progress and results
15. "a Python verification prototype, avharness verify, 39 passing unit tests": the system is the current package with `run --shot <id>`, about 1,400 lines in 9 modules and 38 offline tests. avharness is the earlier prototype, kept as reference.
16. Add the results. Five shots, K = 8: DB-38 released after 2 takes; DB-16 handed off after 5 takes, DB-35, DB-60 and SB-01 after 3, each because the remaining errors had become backend-limited. Mean 3.2 takes and $1.88 per shot, $9.40 in all. The Analyser branched to an earlier round in 3 of 16 revisions. After the first take the most frequent blocking checks were A2 scripted actions, 8 of 16 items. On the DB-38 pilot take the prototype accepted with 0 of 6 items failed; the panel failed 6 of 23, five confirmed frame by frame. For DB-35 and DB-60 the final takes are English but not verbatim: "breech" came out as "brieche", the name "Chen" was dropped; DB-60's first two takes were not English. Do not write that the final takes are Chinese.
17. Tables ready to paste are in `docs/report_tables.md`; figures in `docs/figures/` (`fig_source_by_bin`, `fig_emotion_by_bin`, `fig_filter_funnel`, `fig_lengths`, `fig_loop_results`, and the DB-35 before/after figure).
