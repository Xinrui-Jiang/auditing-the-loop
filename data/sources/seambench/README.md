---
license: cc-by-nc-4.0
language:
  - zh
  - en
pretty_name: "SEAM-Bench: Continuity Storyboarding Benchmark"
tags:
  - storyboarding
  - short-drama
  - visual-continuity
  - multimodal
  - film-generation
size_categories:
  - n<1K
---

# SEAM-Bench

**A double-blind continuity storyboarding benchmark for industrial short-drama generation.**

SEAM-Bench standardizes the evaluation of *visual continuity* in AI short-drama
storyboarding and supports reproducible assessment at both the **prompt layer**
(storyboard text) and the **image layer** (rendered keyframes). It is the
benchmark released alongside **SEAM** (Shot Entity-Attribute Memory), a
training-free, model-agnostic memory graph that repairs cross-shot and
cross-episode continuity at the storyboard prompt-text layer, deployed as a stage
of the **SEAM-Agent** multi-agent storyboarding pipeline.

> SEAM-Bench 是面向工业级短剧生成的**双盲连续性分镜基准**，用于在提示词层
> （分镜文本）与图像层（渲染关键帧）上可复现地评测视觉连续性。

---

## Contents

The benchmark covers **three produced short dramas, 68 episodes in total**.

| Drama (dir) | Title | Episodes | Human storyboards | Reference images |
|---|---|---:|---:|---:|
| `beyond-the-wall` | Beyond the Wall | 20 | 659 | 31 (26 char + 5 scene) |
| `his-toyboy` | His Toyboy: The Billionaire's Trap | 23 | 754 | 15 (8 char + 7 scene) |
| `werewolf` | You Are My Cure, My Undoing | 25 | 826 | 12 (12 char) |
| **Total** | | **68** | **2,239** | **58** |

*Human-storyboard counts follow the aligned, annotated shot totals reported in
the paper; raw CSV row counts run higher because a single shot cell may span
multiple text lines.*

Two kinds of material are released:

1. **Original scripts** — per-episode screenplays, a tiered outline, and
   character bios. These form the pipeline input.
2. **Reference images** — character and scene visual anchors, semantically
   renamed and deduplicated into a shared pool. They serve as the fixed keyframe
   input and as the image-layer consistency gold standard. For distribution the
   images are resized to a 1536px long edge (PNG containers preserved); this is
   ample for their use as reference anchors.

---

## Directory layout

```
dramas/
  <drama>/
    script/                     # pipeline input (screenplays + metadata)
      index.json                # title, logline, per-episode scene/character index
      tiered_outline.txt        # multi-level story outline
      character_bios.txt        # character descriptions
      camera_grammar.json       # per-character shot-grammar rules (his-toyboy only)
      episodes/
        epNN_cn.txt             # Chinese screenplay for episode NN
        epNN_en.txt             # English screenplay (his-toyboy only)
    director/                   # human-director storyboards, one CSV per episode
      epNN.csv
    character/                  # character reference images
      _pool/                    # deduplicated unique images
      reference_index.json      # role/state -> image mapping, per episode
    scene/                      # scene reference images (absent for werewolf)
      _pool/
      scene_index.json
```

### `script/index.json`

```json
{
  "title": "His toyboy: The Billionaire's Trap",
  "logline": "...",
  "num_episodes": 23,
  "volumes": ["第一卷：...", "..."],
  "episodes": {
    "1": {
      "title": "The Mark (咬痕)",
      "summary": "...",
      "scenes_en": ["EXT. MEDICAL UNIVERSITY COMMENCEMENT - STADIUM - DAY", "..."],
      "characters_en": ["JULIAN", "VICTOR", "..."],
      "scenes_cn": ["..."], "characters_cn": ["..."],
      "num_lines_en": 72, "num_lines_cn": 69
    }
  }
}
```

### `director/epNN.csv`

Human-director storyboards. UTF-8 with BOM. Columns (Chinese headers):

| Column | 中文 | Meaning |
|---|---|---|
| 分镜号 / 集序号 | shot no. | Shot index within the episode |
| 场景 | scene | Scene / location label |
| 画面内容 | visual | Visual description of the shot |
| 景别 | shot size | e.g. 全景 / 中景 / 特写 |
| 拍摄角度 | angle | e.g. 平视 / 俯拍 / 仰拍 |
| 运镜 | movement | Camera movement |
| 角色 | characters | Characters active in the shot |
| 台词 | dialogue | On-screen dialogue |
| 中文台词 | dialogue (zh) | Chinese dialogue (where separated) |

> **Reading the CSVs:** cells may contain embedded newlines and commas, so parse
> with a proper CSV reader (e.g. Python `csv`, `pandas.read_csv`) rather than
> splitting on commas. Files are UTF-8 with a BOM — read with `encoding="utf-8-sig"`.

### `character/reference_index.json` and `scene/scene_index.json`

Map each per-episode reference to a deduplicated image in `_pool/`:

```json
{
  "drama": "his-toyboy",
  "pool_dir": "_pool",
  "unique_images": 8,
  "episodes": {
    "ep01": [
      {
        "role": "朱利安",
        "state": "julian_毕业典礼",
        "image": "_pool/julian_毕业典礼.png",
        "description": "朱利安，26岁，惊人漂亮但脸色苍白，毕业典礼上的毕业袍形象"
      }
    ]
  }
}
```

---

## Quick start

```python
import csv, json
from pathlib import Path

drama = Path("dramas/his-toyboy")

# 1. Story metadata
index = json.loads((drama / "script/index.json").read_text(encoding="utf-8"))
print(index["title"], index["num_episodes"])

# 2. A human-director storyboard (BOM-safe, multiline-cell-safe)
with open(drama / "director/ep01.csv", encoding="utf-8-sig", newline="") as f:
    shots = list(csv.DictReader(f))
print(len(shots), "shots in episode 1")

# 3. Resolve a character reference image
refs = json.loads((drama / "character/reference_index.json").read_text(encoding="utf-8"))
for r in refs["episodes"]["ep01"]:
    print(r["role"], "->", drama / r["image"])
```

---

## Notes and known gaps

Coverage is not uniform across the three dramas; the benchmark reflects the
material as produced.

- **English screenplays** (`episodes/*_en.txt`) exist only for `his-toyboy`;
  `beyond-the-wall` and `werewolf` ship the Chinese screenplays only.
- **Scene reference pool** is absent for `werewolf` (no `scene/` directory).
- **`camera_grammar.json`** (per-character shot-grammar rules) is provided only
  for `his-toyboy`.
- `werewolf/director/` additionally contains an aggregated
  `... - 人类分镜总表.csv` (all-episode master table) alongside the per-episode
  CSVs.
- Reference images (`character/_pool/`, `scene/_pool/`) are stored via Git LFS
  on the Hugging Face Hub.

---

## Download

The benchmark is hosted as a Hugging Face dataset. Clone with `git` (LFS-backed)
or pull via the `huggingface_hub` client:

```bash
# Option A: git clone (install git-lfs first)
git lfs install
git clone https://huggingface.co/datasets/Jackyqq/SEAM-Bench

# Option B: Python client
pip install huggingface_hub
python -c "from huggingface_hub import snapshot_download; \
snapshot_download('Jackyqq/SEAM-Bench', repo_type='dataset', local_dir='SEAM-Bench')"
```

---

## Copyright and intended use

The screenplays, human-director storyboards, and reference images in this
benchmark originate from produced commercial short dramas and are released **for
non-commercial research on storyboard continuity evaluation only**. They remain
the property of their respective rights holders. Do not redistribute for
commercial purposes or use them to train generative models for commercial
release. If you are a rights holder and have concerns about any material here,
please open an issue.

> 本基准中的剧本、人类导演分镜表与参考图源自已制作的商业短剧，**仅供分镜连续性
> 评测的非商业研究使用**，版权归各自权利人所有。

---

## Citation

If you use SEAM-Bench, please cite the accompanying paper:

```bibtex
@inproceedings{seam2027,
  title     = {SEAM: Shot Entity-Attribute Memory for Consistent Short-Drama Storyboarding},
  author    = {},
  booktitle = {Proceedings of the ACM SIGKDD Conference on Knowledge Discovery and Data Mining (KDD)},
  year      = {2027}
}
```
