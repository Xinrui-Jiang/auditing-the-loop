# SB-01: hand-off at round 2

Rounds: 3. Total cost: $1.76. Take: `runs/loop/SB-01/rounds/2/take.mp4`.

## Final take: feedback sheet

| item | status | severity | uncertainty | fixability | note |
|---|---|---|---|---|---|
| A1.1 | pass | info | confident | prompt_fixable |  |
| A2.1 | pass | info | confident | retry_fixable |  |
| A2.2 | pass | info | confident | retry_fixable |  |
| A3.1 | pass | info | confident | prompt_fixable |  |
| A4.1 | pass | info | confident | prompt_fixable |  |
| A4.2 | pass | info | confident | prompt_fixable |  |
| A4.3 | pass | info | confident | prompt_fixable |  |
| A5.1 | pass | info | confident | prompt_fixable |  |
| A6.1 | uncertain | info | uncertain | retry_fixable |  |
| B1.1 | pass | info | confident | retry_fixable |  |
| B2.1 | pass | info | confident | retry_fixable |  |
| B3.1 | pass | info | confident | retry_fixable |  |
| B4.1 | pass | info | uncertain | retry_fixable |  |
| B5.1 | pass | info | confident | backend_limited |  |
| B6.1 | pass | info | confident | backend_limited |  |
| B7.1 | pass | info | confident | prompt_fixable |  |
| C1.1 | pass | info | confident | prompt_fixable |  |
| C2.1 | fail | error | confident | backend_limited | BLOCKING |
| C4.1 | pass | info | confident | prompt_fixable |  |

Errors that did not block (backend-limited) and warnings are listed above; the checklist text per item:

- C2.1: Face and voice intensity within [0, 1] on the 0-4 scale (calm).

## Rounds

### Round 0
Blocking after this round: A2.1, A2.2, C2.1. Cost $0.59.

Prompt:

```
Vertical 9:16 framing, head and shoulders fill the frame, subject centred. medium close-up, static camera, slight high angle.
INT. LUXURY PENTHOUSE - CONTINUOUS. Cold filtered sunlight bathes the space. Julian enters, eyes widening in shock. He walks through living room — everything unchanged from four years ago. A frozen museum, time capsule, shrine. JULIAN, whispering, says: "What… what is this?"
Live-action short-drama look. Audio on; the line is spoken on camera.
```

### Round 1 (branched from round 0)
Blocking after this round: C2.1. Cost $0.58.

Analyser: Branch from round 0 because it is the only available take and its stable visual continuity, framing, single-character composition, anatomy, lip sync, and whispering delivery should be preserved. The new guidance makes Julian visibly enter and continuously walk through the living room, which directly addresses A2.1 and A2.2. It also explicitly limits both facial and vocal intensity while retaining widened eyes and surprise, addressing C2.1 without losing the passing surprise cue C1.1. The exact script spans are retained, and the line is reinforced as complete, English, and verbatim to prevent the prior paraphrase. The background is requested to remain visible enough to support the unchanged-four-years-ago premise.

Targets: A2.1, A2.2, C2.1, A1.1, A5.1

Prompt:

```
Create an 8-second live-action short-drama take in vertical 9:16 at 480p with an audio track. Use one continuous shot with no cuts, freezes, jumps, loops, subtitles, captions, or watermarks. Keep the camera static in a slight high angle, medium close-up, with JULIAN centred. Make the penthouse background sufficiently visible to show the living room as a luxury space that appears unchanged from four years ago: a frozen museum, time capsule, shrine.

SCRIPT SPANS:
INT. LUXURY PENTHOUSE - CONTINUOUS
Cold filtered sunlight bathes the space. Julian enters, eyes widening in shock. He walks through living room — everything unchanged from four years ago. A frozen museum, time capsule, shrine.
JULIAN
whispering
What… what is this?

At the very beginning, JULIAN visibly enters the penthouse space from off-screen and then walks through the living room for the duration of the continuous take. Show clear forward walking and contact with the floor while keeping him centred in the static medium close-up. As he enters, his eyes visibly widen in surprise, but keep the facial expression and whispering voice restrained and calm, with surprise intensity within 0 to 1 on the 0-4 scale. JULIAN is the only person visible and the only voice heard. He speaks the line exactly and completely in English, verbatim as written: "What… what is this?" Do not paraphrase, add, omit, or change any words. Ensure his lip movements match the line and his voice clearly belongs to him. Preserve the same face, voice, clothing, and anatomy throughout; keep all object and liquid motion physically plausible.
```

### Round 2 (branched from round 0)
Blocking after this round: C2.1. Cost $0.59.

Analyser: Branch from round 0 because it preserved the required static medium close-up, centred composition, single-character continuity, anatomy, lip sync, and whispering delivery. Round 1 successfully added entry and walking but introduced tracking/high-medium framing and still produced an incorrect paraphrase, while its surprise intensity remained above the cap. This revision keeps the successful entry and walking requirements while explicitly restoring a locked static camera and medium close-up, protects the unchanged penthouse background and all continuity passes, and sharply limits the surprise to subtle eye widening with a calm whisper. The exact script spans are retained verbatim and the spoken line is reinforced with explicit prohibitions against alternate wording.

Targets: C2.1, A1.1, A6.1, A2.1, A2.2

Prompt:

```
Create an 8-second live-action short-drama take in 9:16 vertical format at 480p with an audio track. Use one uninterrupted continuous shot: no cuts, freezes, jumps, loops, subtitles, captions, or watermarks. Keep the camera completely static in a slight high angle, medium close-up, with JULIAN centred once he enters; do not pan, track, zoom, or reframe. Keep enough of the luxury penthouse living room visible to show cold filtered sunlight and a space that appears exactly unchanged from four years ago: a frozen museum, time capsule, shrine.

SCRIPT SPANS:
INT. LUXURY PENTHOUSE - CONTINUOUS
Cold filtered sunlight bathes the space. Julian enters, eyes widening in shock. He walks through living room — everything unchanged from four years ago. A frozen museum, time capsule, shrine.
JULIAN
whispering
What… what is this?

At the start of the shot, JULIAN visibly enters from just off-screen into the penthouse, then takes clear, natural walking steps through the living room while remaining in the static medium close-up and returning to the centre of frame. Show his feet or body-floor contact only as naturally as the framing allows; do not replace the walk with standing still. As he enters, use a restrained, subtle surprise cue: his eyes widen slightly and naturally, with a calm face, no exaggerated expression, no gasp, and no raised vocal energy. Keep both facial and voice intensity within 0 to 1 on the 0-4 scale. JULIAN is the only person visible and the only voice heard. He speaks exactly and completely in English, verbatim: "What… what is this?" Use the ellipsis and repeated "what" exactly; do not substitute "What?", "What exactly?", or any other wording, and do not add or omit words. Deliver it as a very quiet, controlled whisper after or during the walk, with lip movement precisely matching the line and the voice clearly belonging to JULIAN. Preserve the same face, voice, clothing, and anatomy for the entire take. Keep all object and liquid motion physically plausible.
```
