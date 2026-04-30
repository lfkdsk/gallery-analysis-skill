# Gallery Animal Index

> 中文 / English bilingual usage guide.
> See [SKILL.md](SKILL.md) for the full agent specification.

---

## English

### What this skill does

`gallery-animal-index` lets an agent (Claude Code or Codex) walk through a photo repository, identify real animals in the images, and maintain three artifacts under `.analysis/`:

| Artifact | Purpose |
| --- | --- |
| `animal_index.json` | Bilingual species → image-paths map. Machine-readable. |
| `animal_index_guide.md` | Human-readable narrative: per-folder summaries, notes. |
| `animal_scan_results/<folder>.json` | Per-folder cache of every image already processed. The source of truth for incremental runs. |

### When to invoke it

Trigger it whenever you want an agent to:

- Build an animal index for a gallery repo from scratch.
- Re-run after adding new photos — the agent only processes the new files.
- Audit or correct species assignments in an existing index.

### Prerequisites

- The target repo is a git repository containing image folders (`.webp`, `.jpg`, `.jpeg`, `.png`).
- (Optional but recommended) A `thumbnail` branch (or `origin/thumbnail`) carrying downscaled versions. The skill uses thumbnails to drastically cut token cost.
- Python 3 with `Pillow` available, for generating contact sheets.

### Quick start

In an agent session pointing at the target gallery repo, ask in plain language, e.g.:

```text
Use the gallery-animal-index skill to scan this repo.
```

The agent will:

1. Read `.analysis/animal_index.json`, `animal_index_guide.md`, and any caches under `animal_scan_results/`.
2. Diff the cache against the current image files, per folder.
3. Add a thumbnail worktree if available, build temporary contact sheets covering only the new images.
4. Identify species, write back the index / guide / cache, validate, and clean up temp files.

### Re-auditing a folder

If you want a folder fully re-checked (e.g. you suspect mis-identifications):

```text
Re-audit the `yakushima` folder, ignore the existing scan cache for it.
```

The agent will rescan everything in that folder and overwrite its cache file on completion.

### Output formats at a glance

`animal_index.json`:

```json
{
  "_meta": { "generated": "2026-04-30", "...": "..." },
  "屋久鹿（屋久岛梅花鹿亚种）/ Yakushima Sika Deer (Cervus nippon yakushimae)": [
    "yakushima/IMG_0001.webp"
  ]
}
```

`animal_scan_results/yakushima.json`:

```json
{
  "_meta": { "folder": "yakushima", "last_scan": "2026-04-30", "thumbnail_source": "origin/thumbnail" },
  "processed": ["yakushima/IMG_0001.webp", "yakushima/IMG_0002.webp"]
}
```

### Validation

After every run the agent runs:

- `python3 -m json.tool .analysis/animal_index.json` to check JSON validity.
- A path-existence check confirming every indexed path exists in the main tree.

If you want to verify manually, the snippet lives at the bottom of [SKILL.md](SKILL.md#validation).

---

## 中文

### 这个 skill 做什么

`gallery-animal-index` 让 agent（Claude Code 或 Codex）扫描一个图片仓库，识别其中的**真实动物**，并在 `.analysis/` 下维护三份产物：

| 产物 | 作用 |
| --- | --- |
| `animal_index.json` | 双语物种 → 图片路径映射，机器可读。 |
| `animal_index_guide.md` | 人读的概览：按目录汇总、备注。 |
| `animal_scan_results/<folder>.json` | 每个目录已扫描图片的缓存。增量扫描的真值来源。 |

### 什么时候用

需要 agent 做以下事情时触发：

- 从零给一个相册仓库建立动物索引。
- 加了新照片之后再跑一次——agent 只处理新增图片。
- 审计或修正已有索引里的物种归类。

### 前置条件

- 目标仓库是 git 仓库，里面有图片目录（`.webp` / `.jpg` / `.jpeg` / `.png`）。
- （可选但强烈推荐）有 `thumbnail` 分支（或 `origin/thumbnail`）放缩略图。skill 会用缩略图来**大幅降低 token 消耗**。
- Python 3，并装好 `Pillow`，用于生成联系底片（contact sheet）。

### 快速使用

在 agent 会话里指向目标仓库，自然语言一句话即可：

```text
用 gallery-animal-index skill 扫描这个仓库。
```

agent 会：

1. 读取 `.analysis/animal_index.json`、`animal_index_guide.md` 以及 `animal_scan_results/` 下的缓存。
2. 对每个目录，把缓存的 `processed` 列表和当前文件 diff，得出"新图"。
3. 如果有缩略图分支就 add 个 worktree，给新图生成临时 contact sheet。
4. 识别物种，回写 index / guide / cache，校验，清理临时文件。

### 重新审计某个目录

如果怀疑某目录识别有误，想完整重扫：

```text
重新审计 `yakushima` 目录，忽略它的扫描缓存。
```

agent 会忽略该目录的 cache，重新走一遍流程，跑完再覆盖写回。

### 产物速览

`animal_index.json`：

```json
{
  "_meta": { "generated": "2026-04-30", "...": "..." },
  "屋久鹿（屋久岛梅花鹿亚种）/ Yakushima Sika Deer (Cervus nippon yakushimae)": [
    "yakushima/IMG_0001.webp"
  ]
}
```

`animal_scan_results/yakushima.json`：

```json
{
  "_meta": { "folder": "yakushima", "last_scan": "2026-04-30", "thumbnail_source": "origin/thumbnail" },
  "processed": ["yakushima/IMG_0001.webp", "yakushima/IMG_0002.webp"]
}
```

### 校验

每次跑完，agent 会执行：

- `python3 -m json.tool .analysis/animal_index.json` 检查 JSON 合法性。
- 路径存在性检查：保证 index 里每个路径在主仓库都能找到。

需要手动复核时，可以直接复制 [SKILL.md](SKILL.md#validation) 末尾的脚本。
