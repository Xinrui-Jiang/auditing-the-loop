# prompt_set_v2_30 — automatic subset selection (2026-11-07)

Weights: {'checkability': 0.3, 'feasibility': 0.25, 'asr': 0.2, 'cue_clarity': 0.15, 'length': 0.1}. Quotas: sources {'DramaBench': (20, 22), 'SEAM-Bench': (3, 4), 'FilmBench': (5, 6)}, bins {'calm': (12, 13), 'strong': (12, 13), 'exaggerated': (4, 5)}, sfx (13, 16), gender (12, 18), min per emotion 3, max 2 per fine setting family and 3 per coarse family, one shot per source script/episode/uid. Greedy by total score with minimum-fill repair (fills may exceed the setting-family caps; the greedy pass respects them). Deterministic.


**Source**

| value | n |
|---|---|
| DramaBench | 22 |
| FilmBench | 5 |
| SEAM-Bench | 3 |


**Native intensity bin**

| value | n |
|---|---|
| calm | 14 |
| strong | 12 |
| exaggerated | 4 |


**Emotion class**

| value | n |
|---|---|
| fear | 6 |
| happiness | 6 |
| sadness | 6 |
| surprise | 5 |
| anger | 4 |
| contempt | 3 |


**Coarse setting family**

| value | n |
|---|---|
| other | 16 |
| home | 5 |
| hospital | 3 |
| office | 2 |
| street | 2 |
| nature | 1 |
| public | 1 |


**Speaker gender**

| value | n |
|---|---|
| female | 18 |
| male | 12 |


SFX present: 14 / 30


## Selected shots

| rank | shot_id | source | bin | emotion | sfx | score | atoms |
|---|---|---|---|---|---|---|---|
| 1 | DB-16 | DramaBench | calm | surprise | no | 1.0 | 4 |
| 2 | DB-35 | DramaBench | strong | anger | yes | 1.0 | 5 |
| 3 | DB-38 | DramaBench | strong | sadness | yes | 1.0 | 4 |
| 4 | SB-01 | SEAM-Bench | calm | surprise | no | 1.0 | 4 |
| 5 | DB-03 | DramaBench | calm | anger | no | 0.97 | 4 |
| 6 | DB-11 | DramaBench | calm | fear | no | 0.97 | 5 |
| 7 | DB-19 | DramaBench | calm | surprise | no | 0.97 | 4 |
| 8 | DB-21 | DramaBench | calm | happiness | no | 0.97 | 4 |
| 9 | DB-22 | DramaBench | calm | happiness | no | 0.97 | 4 |
| 10 | DB-39 | DramaBench | strong | sadness | yes | 0.97 | 5 |
| 11 | DB-60 | DramaBench | exaggerated | sadness | no | 0.97 | 5 |
| 12 | SB-07 | SEAM-Bench | strong | happiness | yes | 0.97 | 4 |
| 13 | DB-43 | DramaBench | strong | fear | yes | 0.945 | 5 |
| 14 | DB-06 | DramaBench | calm | sadness | yes | 0.94 | 5 |
| 15 | DB-10 | DramaBench | calm | sadness | yes | 0.94 | 4 |
| 16 | DB-33 | DramaBench | strong | anger | yes | 0.94 | 5 |
| 17 | DB-37 | DramaBench | strong | anger | yes | 0.94 | 4 |
| 18 | DB-52 | DramaBench | strong | surprise | yes | 0.94 | 4 |
| 19 | DB-48 | DramaBench | strong | surprise | yes | 0.9325 | 5 |
| 20 | FB-12 | FilmBench | strong | fear | no | 0.85 | 3 |
| 21 | SB-04 | SEAM-Bench | strong | fear | no | 0.94 | 4 |
| 22 | FB-04 | FilmBench | calm | fear | no | 0.85 | 3 |
| 23 | FB-08 | FilmBench | calm | contempt | no | 0.85 | 3 |
| 24 | FB-14 | FilmBench | strong | happiness | no | 0.85 | 3 |
| 25 | FB-05 | FilmBench | calm | fear | yes | 0.82 | 3 |
| 26 | DB-61 | DramaBench | exaggerated | sadness | no | 0.94 | 4 |
| 27 | DB-64 | DramaBench | exaggerated | happiness | no | 0.85 | 3 |
| 28 | DB-63 | DramaBench | exaggerated | happiness | no | 0.82 | 2 |
| 29 | DB-27 | DramaBench | calm | contempt | yes | 0.94 | 3 |
| 30 | DB-28 | DramaBench | calm | contempt | yes | 0.94 | 5 |

## Runner-ups (swap candidates)

| shot_id | source | bin | emotion | score | why not selected |
|---|---|---|---|---|---|
| DB-42 | DramaBench | strong | sadness | 0.97 | coarse setting family 'home' at cap |
| DB-51 | DramaBench | strong | surprise | 0.97 | coarse setting family 'home' at cap |
| DB-02 | DramaBench | calm | anger | 0.9533 | removed to satisfy minimum emo=contempt |
| DB-46 | DramaBench | strong | fear | 0.95 | coarse setting family 'hospital' at cap |
| DB-05 | DramaBench | calm | anger | 0.94 | coarse setting family 'home' at cap |
| DB-07 | DramaBench | calm | sadness | 0.94 | removed to satisfy minimum bin=exaggerated |
| DB-13 | DramaBench | calm | fear | 0.94 | removed to satisfy minimum bin=exaggerated |
| DB-14 | DramaBench | calm | fear | 0.94 | removed to satisfy minimum bin=exaggerated |
| DB-31 | DramaBench | calm | contempt | 0.94 | intensity-bin quota reached |
| DB-49 | DramaBench | strong | surprise | 0.94 | coarse setting family 'home' at cap |
