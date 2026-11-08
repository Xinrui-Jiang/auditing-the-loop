# DB-16: hand-off at round 4

Rounds: 5. Total cost: $2.93. Take: `runs/loop/DB-16/rounds/4/take.mp4`.

## Final take: feedback sheet

| item | status | severity | uncertainty | fixability | note |
|---|---|---|---|---|---|
| A1.1 | pass | info | confident | prompt_fixable |  |
| A2.1 | pass | info | confident | retry_fixable |  |
| A2.2 | fail | error | confident | backend_limited | BLOCKING |
| A2.3 | pass | info | confident | retry_fixable |  |
| A3.1 | pass | info | confident | prompt_fixable |  |
| A3.2 | pass | info | confident | prompt_fixable |  |
| A4.1 | pass | info | confident | prompt_fixable |  |
| A4.2 | pass | info | confident | prompt_fixable |  |
| A4.3 | pass | info | confident | prompt_fixable |  |
| A5.1 | uncertain | info | uncertain | prompt_fixable |  |
| A6.1 | pass | info | confident | prompt_fixable |  |
| B1.1 | pass | info | confident | retry_fixable |  |
| B2.1 | pass | info | confident | retry_fixable |  |
| B3.1 | pass | info | confident | retry_fixable |  |
| B4.1 | pass | info | confident | retry_fixable |  |
| B5.1 | pass | info | confident | backend_limited |  |
| B6.1 | pass | info | confident | backend_limited |  |
| B7.1 | pass | info | confident | prompt_fixable |  |
| C1.1 | fail | error | confident | backend_limited | BLOCKING |
| C2.1 | fail | warning | uncertain | retry_fixable |  |
| C4.1 | pass | info | confident | prompt_fixable |  |

Errors that did not block (backend-limited) and warnings are listed above; the checklist text per item:

- A2.2: A brief memory of falling snow, a different door, and a different betrayal must be conveyed across XU ZHIYI's face.
- C1.1: The emotion is surprise (cues: blinks).
- C2.1: Face and voice intensity within [0, 1] on the 0-4 scale (calm).

## Rounds

### Round 0
Blocking after this round: A2.2, A2.3, C1.1, C2.1. Cost $0.59.

Prompt:

```
Vertical 9:16 framing, head and shoulders fill the frame, subject centred. medium close-up, static camera, eye level.
EXT. SHEN YUNAN'S HOUSE ENTRANCE - DAY. XU ZHIYI (28, exhausted but determined). She stares at the door. A flicker of memory crosses her face—falling snow, a different door, a different betrayal. She blinks it away. XU ZHIYI says quietly: "He won't help us. Not after what I did."
Live-action short-drama look. Audio on; the line is spoken on camera.
```

### Round 1 (branched from round 0)
Blocking after this round: A2.1, A2.2, C1.1, C2.1. Cost $0.59.

Analyser: Branch from round 0 because it already passed the framing, present-day entrance, visible door, solo cast, continuity, exact line, lip sync, and quiet delivery. The failed memory items need explicit staging as a brief face-only impression followed by a visible blink, while the emotion must shift from anxiety to a subtle, calm surprise. The prompt preserves the continuous present-day shot and adds safeguards against introducing a second location, person, voice, or dramatic intensity.

Targets: A2.2, A2.3, C1.1, C2.1

Prompt:

```
Vertical 9:16 framing, medium close-up, static camera, eye level, 480p, 8 seconds, XU ZHIYI centred. Keep the shot continuous at the exterior house entrance in daylight, with the door clearly visible beside her. Only XU ZHIYI is on screen and only she speaks; nobody enters, and do not cut to another place. Preserve the same face, voice, clothing, anatomy, and identity throughout. No subtitles, captions, watermarks, or text.

EXT. SHEN YUNAN'S HOUSE ENTRANCE - DAY
XU ZHIYI (28, exhausted but determined)
She stares at the door. A flicker of memory crosses her face—falling snow, a different door, a different betrayal. She blinks it away.
XU ZHIYI
quietly
He won't help us. Not after what I did.

Stage the memory as only a very brief, subtle visual impression conveyed through XU ZHIYI's face while the camera remains at the present-day house entrance: her eyes and expression momentarily register falling snow, a different door, and a different betrayal, without showing a separate location or adding anyone else. Then she visibly blinks once, clearly ending the memory, and returns to calmly staring at the present door. Make the emotion a restrained flicker of surprise, with a visible blink but low facial and vocal intensity, remaining calm rather than anxious or dramatic. Speak the complete line exactly in English, softly and quietly, with accurate on-camera lip sync. Keep all movement natural and physically plausible, with no unintended cuts, freezes, jumps, loops, morphing, or extra voices. Audio must be present.
```

### Round 2 (branched from round 0)
Blocking after this round: A2.1, A2.2, A2.3, C1.1, C2.1. Cost $0.59.

Analyser: Branch from round 0 because it already passed the direct door stare, entrance setting and door visibility, solo cast, continuity, exact English line, lip sync, quiet delivery, and technical framing. Round 1 improved the blink but lost the direct door stare and still failed to make the memory readable; its wording also led to sadness/resignation rather than surprise. This revision restores the simpler direct-gaze instruction from round 0, makes the three memory elements visibly legible through a brief face-only reaction, requires a distinct blink to end it, and specifies restrained low-intensity surprise without introducing a cutaway, extra person, or dramatic anxiety.

Targets: A2.1, A2.2, C1.1, C2.1

Prompt:

```
Vertical 9:16, 480p, 8-second live-action short-drama take with audio. Medium close-up, static camera, eye level, XU ZHIYI centred. Keep one continuous shot at the exterior house entrance in daylight. The house door must be clearly visible, and XU ZHIYI must aim her gaze directly at the door itself, visibly staring at it rather than past it or to the side. Only XU ZHIYI appears on screen and only she speaks. No one enters, no cutaway or location change, no subtitles, captions, watermarks, or text. Preserve the same face, voice, clothing, identity, and anatomy throughout.

EXT. SHEN YUNAN'S HOUSE ENTRANCE - DAY
XU ZHIYI (28, exhausted but determined)
She stares at the door. A flicker of memory crosses her face—falling snow, a different door, a different betrayal. She blinks it away.
XU ZHIYI
quietly
He won't help us. Not after what I did.

Keep the camera and background at the present-day house entrance for the entire take. While XU ZHIYI continues staring directly at the visible door, create a clearly readable but brief face-only memory impression lasting about half a second: her eyes briefly widen and catch the cold visual suggestion of falling snow, her expression registers a different door and the shock of a different betrayal. Convey all three memory elements through her eyes and facial reaction only; do not show another location, another door, actual snowfall, or any other person. The memory must be an impression across her face, not a cutaway or scene change. Immediately end it with one unmistakable visible blink, then return to the same direct stare at the present door. Make the emotion restrained surprise, not sadness, resignation, anxiety, or determination: a small eyebrow lift, slight eye widening, and brief alertness, with facial and vocal intensity kept very low, around 0.5 on a 0-4 scale. Speak the complete line exactly in English, quietly and softly, after the blink, with accurate on-camera lip sync. Keep all motion natural and physically plausible, with no unintended cuts, freezes, jumps, loops, morphing, extra voices, or garbled text.
```

### Round 3 (branched from round 0)
Blocking after this round: A2.2, A2.3, A5.1, C1.1. Cost $0.58.

Analyser: Branch from round 0 because it preserved the direct stare at the door, entrance setting, visible door, solo cast, continuity, exact line, framing, and quiet delivery. Round 1 and round 2 added stronger memory instructions but caused the gaze to drift away from the door or toward the camera, and neither produced a readable memory. This revision keeps round 0's simpler gaze behavior, protects the already-passing constraints, and adds a short explicit facial sequence: internalized impressions of snow, a different door, and betrayal, followed immediately by one deliberate blink. It also specifies restrained surprise rather than sadness or distress while keeping intensity calm and low.

Targets: A2.2, A2.3, C1.1, C2.1

Prompt:

```
Vertical 9:16, 480p, 8-second live-action short-drama take with audio. Medium close-up, static camera, eye level, XU ZHIYI centred. Keep one continuous shot at the exterior house entrance in daylight, with the real house door clearly visible beside her. XU ZHIYI keeps her eyes directed at and visibly staring at the door itself, never at the camera or past the doorway. Only XU ZHIYI appears on screen and only she speaks. Nobody enters, there is no cutaway or location change. Preserve the same face, voice, clothing, identity, and anatomy throughout. No subtitles, captions, watermarks, or text.

EXT. SHEN YUNAN'S HOUSE ENTRANCE - DAY
XU ZHIYI (28, exhausted but determined)
She stares at the door. A flicker of memory crosses her face—falling snow, a different door, a different betrayal. She blinks it away.
XU ZHIYI
quietly
He won't help us. Not after what I did.

Stage the facial acting in a clear sequence while the camera, background, door, and present-day location remain unchanged. First, XU ZHIYI stares directly at the visible present-day door. Then, for a brief half-second, her face visibly registers an internal memory: a tiny lift of the brows and slight widening of the eyes suggest falling snow, then her expression briefly recognizes a different door and the shock of a different betrayal. These three elements must be readable as a fleeting emotional impression across her face, without showing snow, another door, another place, or any other person. Keep her gaze aimed toward the present-day door rather than the camera even during the memory. Immediately after the memory impression, she makes one deliberate, unmistakable blink that visibly ends it, then resumes the same direct stare at the door. The reaction is restrained surprise—brief alert eyes and a small eyebrow lift—not sadness, worry, resignation, anxiety, or determination. Keep facial and vocal intensity very low and calm, within 0 to 1 on the 0-4 scale. After the blink, she speaks the complete line exactly in English, softly and quietly, with accurate on-camera lip sync. Keep all motion natural and physically plausible, with no unintended cuts, freezes, jumps, loops, morphing, extra voices, or garbled text. Audio must be present.
```

### Round 4 (branched from round 3)
Blocking after this round: A2.2, C1.1. Cost $0.59.

Analyser: Branch from round 3 because it preserved the direct stare at the door, the entrance setting, solo cast, continuity, exact dialogue, quiet delivery, and calm intensity. Round 3's weakness was that the memory remained too abstract and the blink looked ordinary because no visible memory sequence preceded it. This revision keeps its successful gaze instruction but adds explicit timing and a concrete face-only sequence: a restrained startled-surprise reaction that successively suggests snow, a different door, and betrayal, followed by a held, deliberate blink that clearly ends the memory. The present-day door and gaze remain fixed throughout, protecting A2.1 and all previously passing constraints.

Targets: A2.2, A2.3, C1.1

Prompt:

```
Vertical 9:16, 480p, 8-second live-action short-drama take with audio. Medium close-up, static camera, eye level, XU ZHIYI centred. Keep one continuous shot at the exterior house entrance in daylight, with the real house door clearly visible beside her. XU ZHIYI keeps her eyes directed at and visibly staring at the door itself, never at the camera or past the doorway. Only XU ZHIYI appears on screen and only she speaks. Nobody enters, there is no cutaway or location change. Preserve the same face, voice, clothing, identity, and anatomy throughout. No subtitles, captions, watermarks, or text.

EXT. SHEN YUNAN'S HOUSE ENTRANCE - DAY
XU ZHIYI (28, exhausted but determined)
She stares at the door. A flicker of memory crosses her face—falling snow, a different door, a different betrayal. She blinks it away.
XU ZHIYI
quietly
He won't help us. Not after what I did.

Use a clearly ordered facial-action sequence while the camera, background, visible door, and present-day entrance remain unchanged. From approximately 00:00 to 00:02, XU ZHIYI visibly stares directly at the present-day door. From approximately 00:02 to 00:03, do not blink: show a brief, readable memory impression only through her face while her gaze remains aimed at the door. First give her a small startled-surprise reaction with a slight eyebrow lift, eyes widening, and a fleeting upward glint suggesting falling snow; then let her eyes and expression briefly register recognition of a different door and the shock of a different betrayal. This must be an unmistakable internal memory reaction, not ordinary worry, sadness, resignation, or determination, but do not show snow, another door, another location, another person, or any overlay. Immediately after that facial memory impression, at approximately 00:03, close both eyes fully in one deliberate, unmistakable blink, hold the closure for a brief moment, then reopen them and visibly return to the same direct stare at the present door. The blink must clearly end the preceding memory, not occur at the beginning and not look like a routine blink. After reopening her eyes, speak the complete line exactly in English, softly and quietly, with accurate on-camera lip sync. Keep the surprise brief and restrained, with low facial and vocal intensity within 0 to 1 on the 0-4 scale. Keep all motion natural and physically plausible, with no unintended cuts, freezes, jumps, loops, morphing, extra voices, or garbled text. Audio must be present.
```
