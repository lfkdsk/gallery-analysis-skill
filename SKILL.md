---
name: gallery-animal-index
description: Create or update animal indexes for gallery-style image repositories. Use when Codex needs to scan folders of photos for real animals, generate or maintain `.analysis/animal_index.json` and `.analysis/animal_index_guide.md`, use a thumbnail branch/worktree to reduce token cost, skip folders already marked complete in an existing index/guide, or audit and correct animal species assignments.
---

# Gallery Animal Index

## Outputs

Write analysis artifacts under `.analysis/` in the target gallery repository:

- `.analysis/animal_index.json`: grouped by bilingual animal species key, with values as repository-relative image paths.
- `.analysis/animal_index_guide.md`: scan status, species summaries, workflow notes, and validation guidance.

Do not save contact sheets unless the user explicitly asks. Generate them in a temporary directory and delete them before finishing.

## Workflow

1. Inspect the target repository structure and existing `.analysis/animal_index.json` / `.analysis/animal_index_guide.md`.
2. If an existing guide marks a folder complete, skip that folder unless the user asks to audit or correct it.
3. If an existing index already contains paths for a folder but the guide lacks status, infer likely completion conservatively and prefer auditing only new or unindexed folders.
4. Use a thumbnail branch or worktree when available, usually `thumbnail` or `origin/thumbnail`, to avoid loading full-resolution images.
5. Generate temporary contact sheets from thumbnails for batches of folders.
6. Read contact sheets first; open individual images only for ambiguous or species-critical cases.
7. Write/update the index and guide. Validate JSON and that every indexed path exists in the main gallery tree.
8. Remove temporary contact sheets unless explicitly requested to preserve them.

## Thumbnail Worktree

Prefer a temporary worktree outside the repo:

```bash
git -C "$GALLERY_ROOT" fetch --all --prune
git -C "$GALLERY_ROOT" worktree add "$THUMB_ROOT" origin/thumbnail
```

If `origin/thumbnail` is unavailable, try local `thumbnail`. If no thumbnail branch exists, use the main gallery images and keep batches small.

Never write index paths from the thumbnail worktree blindly. Always resolve the corresponding file in the main gallery tree and write the main-tree relative path.

## Temporary Contact Sheets

Generate contact sheets in a temp location such as `mktemp -d`, not in `.analysis/`, unless the user asks to keep them.

```bash
python3 - <<'PY'
from PIL import Image, ImageDraw, ImageFont
import os, math

thumb_root = os.environ['THUMB_ROOT']
out_dir = os.environ['CONTACT_OUT']
folders = os.environ['FOLDERS'].split(':')
exts = ('.webp', '.jpg', '.jpeg', '.png', '.JPG', '.JPEG', '.PNG')
os.makedirs(out_dir, exist_ok=True)

try:
    font = ImageFont.truetype(os.environ['FONT_PATH'], 15)
except Exception:
    font = ImageFont.load_default()

for folder in folders:
    dirp = os.path.join(thumb_root, folder) if folder else thumb_root
    files = sorted(f for f in os.listdir(dirp) if f.endswith(exts))
    if not files:
        continue
    tw, th, lh, cols = 180, 135, 40, 5
    rows = math.ceil(len(files) / cols) or 1
    sheet = Image.new('RGB', (cols * tw, rows * (th + lh)), 'white')
    draw = ImageDraw.Draw(sheet)
    for i, name in enumerate(files):
        im = Image.open(os.path.join(dirp, name)).convert('RGB')
        im.thumbnail((tw, th), Image.Resampling.LANCZOS)
        x = (i % cols) * tw + (tw - im.width) // 2
        y = (i // cols) * (th + lh)
        sheet.paste(im, (x, y))
        draw.text(((i % cols) * tw + 4, y + th + 2), f'{i + 1}. {name}'[:35], fill=(0, 0, 0), font=font)
    safe = folder.replace('/', '__') if folder else '_root'
    sheet.save(os.path.join(out_dir, safe + '_contact.jpg'), quality=90)
PY
```

Typical setup:

```bash
export GALLERY_ROOT=/path/to/gallery-repo
export THUMB_ROOT=/tmp/gallery-thumbnail
export CONTACT_OUT="$(mktemp -d)"
export FOLDERS="cat:yakushima:others"
```

After final validation:

```bash
rm -rf "$CONTACT_OUT"
```

## Animal Inclusion Rules

Include:

- Real, living animals photographed directly.
- Zoo/aquarium animals if they are real animals.
- Multiple species in one image by listing the same path under multiple species keys.

Exclude:

- Sculptures, toys, plushies, models, anime/cartoon figures, paintings, signage, logos, and decorative motifs.
- Animals only appearing inside a framed photo or screen unless the repository image itself is intended as a photo of that animal.
- Food or animal products.
- Tiny or blurry animals that cannot be identified with reasonable confidence.

When uncertain, use a conservative broader key such as `海鸥（属） / Gull sp. (Larus sp.)` rather than over-identifying.

## Species Key Format

Use:

```text
中文种名·颜色变体 / English Species (Scientific Name)
```

Examples:

- `中华田园猫·纯白 / Chinese Domestic Cat (Solid White)`
- `屋久鹿（屋久岛梅花鹿亚种）/ Yakushima Sika Deer (Cervus nippon yakushimae)`
- `日本猕猴 / Japanese Macaque (Macaca fuscata)`

For cats, split by visible color pattern when useful. For wildlife, identify as precisely as the image supports.

## Index Update Rules

Use JSON like:

```json
{
  "_meta": {
    "description": "动物图片索引 — 按动物种类归档，值为文件路径列表",
    "format": "folder/filename.ext",
    "generated": "YYYY-MM-DD",
    "status": "..."
  },
  "物种 key": [
    "folder/file.webp"
  ]
}
```

Before writing a path:

1. Match thumbnail basename to the main gallery tree.
2. Preserve the main tree's actual extension.
3. Skip orphan thumbnails that do not exist in the main tree.
4. Deduplicate paths within each species key.

## Guide Update Rules

Keep `.analysis/animal_index_guide.md` current:

- List scanned folders and status.
- Summarize animals found per folder.
- List remaining unscanned folders, if any.
- Remove stale “partial” or “todo” statements once completed.
- Do not hard-code machine-specific absolute paths.
- Mention that future runs may skip folders already marked complete in the guide/index.

## Validation

Always run:

```bash
python3 -m json.tool "$GALLERY_ROOT/.analysis/animal_index.json" >/dev/null
```

Then verify indexed paths exist:

```bash
python3 - <<'PY'
import json, os, collections
root = os.environ['GALLERY_ROOT']
index = json.load(open(os.path.join(root, '.analysis/animal_index.json'), encoding='utf-8'))
missing = []
dups = []
for key, paths in index.items():
    if key == '_meta':
        continue
    counts = collections.Counter(paths)
    dups.extend((key, p, n) for p, n in counts.items() if n > 1)
    missing.extend(p for p in paths if not os.path.exists(os.path.join(root, p)))
print('missing', len(missing))
print('duplicates', len(dups))
if missing:
    print('\\n'.join(missing))
PY
```

Report any skipped folders, ambiguous species, orphan thumbnails, and validation failures in the final response.
