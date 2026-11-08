# DB-35: hand-off at round 2

Rounds: 3. Total cost: $1.77. Take: `runs/loop/DB-35/rounds/2/take.mp4`.

## Final take: feedback sheet

| item | status | severity | uncertainty | fixability | note |
|---|---|---|---|---|---|
| A1.1 | fail | error | uncertain | backend_limited | BLOCKING |
| A2.1 | pass | info | confident | retry_fixable |  |
| A2.2 | uncertain | info | uncertain | prompt_fixable |  |
| A3.1 | pass | info | confident | prompt_fixable |  |
| A3.2 | pass | info | uncertain | prompt_fixable |  |
| A3.3 | pass | info | confident | prompt_fixable |  |
| A4.1 | pass | info | confident | prompt_fixable |  |
| A4.2 | pass | info | confident | retry_fixable |  |
| A4.3 | pass | info | confident | prompt_fixable |  |
| A5.1 | pass | info | confident | prompt_fixable |  |
| A6.1 | fail | warning | confident | backend_limited |  |
| B1.1 | pass | info | confident | retry_fixable |  |
| B2.1 | pass | info | uncertain | retry_fixable |  |
| B3.1 | pass | info | confident | retry_fixable |  |
| B4.1 | pass | info | confident | retry_fixable |  |
| B5.1 | pass | info | confident | backend_limited |  |
| B6.1 | pass | info | confident | backend_limited |  |
| B7.1 | pass | info | confident | prompt_fixable |  |
| C1.1 | fail | warning | uncertain | backend_limited |  |
| C2.1 | pass | info | confident | retry_fixable |  |
| C4.1 | pass | info | confident | prompt_fixable |  |

Errors that did not block (backend-limited) and warnings are listed above; the checklist text per item:

- A1.1: The line "Doctor! My mistress—she's breech!" is spoken in English, complete and verbatim.
- A6.1: medium close-up, static camera, eye level, vertical 9:16, HE XI centred.
- C1.1: The emotion is anger (cues: shouting).

## Rounds

### Round 0
Blocking after this round: A1.1, A2.1. Cost $0.59.

Prompt:

```
Vertical 9:16 framing, head and shoulders fill the frame, subject centred. medium close-up, static camera, eye level.
INT. VILLAGE HOSPITAL - NIGHT. Rain lashes a dark window. HE XI runs beside her HUSBAND as he pushes a hospital bed. On it, ZHAO WANRU, 25, writhes in advanced labor. HE XI, shouting, says: "Doctor! My mistress—she's breech!" Sound: Rain lashes a dark window.
Live-action short-drama look. Audio on; the line is spoken on camera.
```

### Round 1 (branched from round 0)
Blocking after this round: A1.1, C1.1. Cost $0.59.

Analyser: Branch from round 0 because it is the only prior take and the main failures are prompt-fixable. The revised prompt explicitly assigns the exact line to HE XI, makes HUSBAND silent, and requires HE XI to visibly run beside the husband while he pushes the bed. It preserves the passing hospital setting, rain, bed action, continuity, duration/audio, and no-overlay requirements, while also guarding against the observed cut, camera shake, anatomy uncertainty, and weakly verified anger.

Targets: A1.1, A2.1, A2.2, A4.2, A6.1, B2.1, B4.1, C1.1, C2.1

Prompt:

```
Create an 8-second live-action short-drama take in vertical 9:16, 480p, with audio. Use one continuous unbroken shot: no cuts, freezes, jumps, loops, or camera shake. Static camera at eye level, medium close-up composition with HE XI centred; keep HUSBAND pushing the hospital bed and ZHAO WANRU visibly on the bed within the same frame or immediately beside HE XI throughout the action. Preserve consistent faces, voices, clothing, anatomy, and object motion.

INT. VILLAGE HOSPITAL - NIGHT
Rain lashes a dark window. HE XI runs beside her HUSBAND as he pushes a hospital bed. On it, ZHAO WANRU, 25, writhes in advanced labor.
HE XI
shouting
Doctor! My mistress—she's breech!

HE XI is the only person who speaks or produces any voice. HUSBAND remains completely silent while pushing the bed. ZHAO WANRU remains silent and visibly writhes in advanced labor. HE XI clearly speaks the complete line exactly as written, including “breech!”, with accurate lip sync; do not paraphrase, omit, reorder, or assign any part of the line to another character. HE XI performs angry, forceful shouting with strong face and voice intensity, level 2–3. Show only HE XI, HUSBAND, and ZHAO WANRU; nobody else appears, enters, or is heard. Keep the setting visibly a village hospital at night, with rain audibly lashing a dark window. No subtitles, captions, watermarks, or text overlays.
```

### Round 2 (branched from round 1)
Blocking after this round: A1.1. Cost $0.59.

Analyser: Continue from round 1 because it fixed the major cast, action, setting, rain, bed, continuity, anatomy, and single-speaker constraints, while branching back would risk losing those passes. The remaining blocking failures are the exact line being assigned to ZHAO WANRU and the delivery reading as panic instead of anger. The new prompt repeatedly identifies HE XI as the sole visible speaker, requires her lips and voice to produce the complete verbatim line, and makes ZHAO WANRU silent. It also gives concrete angry-performance cues while explicitly excluding panic. The failed static-camera requirement is reinforced with locked-off staging, while the already-passing running, bed-pushing, labor, setting, rain, continuity, and no-extra-cast conditions are preserved.

Targets: A1.1, C1.1, A6.1

Prompt:

```
Create an 8-second live-action short-drama take in 480p, vertical 9:16, with a present audio track. Use one single continuous unbroken take with no cuts, transitions, freezes, jumps, loops, or camera movement. The camera is completely locked off and static at eye level; it must not track, pan, tilt, zoom, shake, or move backward. Use a medium close-up composition with HE XI centred while keeping HUSBAND, the hospital bed, and ZHAO WANRU visibly present in the same frame as much as possible. Preserve the same faces, voices, clothing, anatomy, and plausible object motion throughout.

INT. VILLAGE HOSPITAL - NIGHT
Rain lashes a dark window. HE XI runs beside her HUSBAND as he pushes a hospital bed. On it, ZHAO WANRU, 25, writhes in advanced labor.
HE XI
shouting
Doctor! My mistress—she's breech!

HE XI must be the only visible speaker. Show HE XI's face clearly while she visibly articulates the entire line, and make the voice unmistakably come from HE XI. HE XI alone says the complete line exactly as written, including the em dash and the final word “breech!”; do not paraphrase, omit, reorder, shorten, or assign any word to HUSBAND or ZHAO WANRU. HUSBAND is completely silent. ZHAO WANRU is completely silent and does not scream, speak, or produce dialogue; she only visibly writhes on the bed in advanced labor. Do not let any other character vocalize.

The delivery is an angry, forceful shout directed at the doctor: furrowed brow, tense jaw, assertive facial expression, and strong voice intensity between 2 and 3. It must read as anger rather than panic, fear, crying, or distress. Keep HE XI visibly running beside HUSBAND as he pushes the bed, with ZHAO WANRU visibly writhing on it. Stage the movement through the locked-off frame; never move the camera to follow them. Show only HE XI, HUSBAND, and ZHAO WANRU. Nobody else appears, enters, or is heard. Keep the village hospital at night clearly visible, including the dark window and audible rain lashing it. No subtitles, captions, watermarks, or text overlays.
```
