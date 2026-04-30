---
name: gallery-animal-index
description: Create or update animal indexes for gallery-style image repositories. Use when an agent needs to scan folders of photos for real animals, generate or maintain `.analysis/animal_index.json`, `.analysis/animal_index_guide.md`, and the per-folder scan cache under `.analysis/animal_scan_results/`, use a thumbnail branch/worktree to reduce token cost, incrementally process only newly added images via the scan cache, or audit and correct animal species assignments.
---

# Gallery Animal Index

## Outputs

Write analysis artifacts under `.analysis/` in the target gallery repository:

- `.analysis/animal_index.json`: grouped by bilingual animal species key, with values as repository-relative image paths.
- `.analysis/animal_index_guide.md`: human-readable scan status, species summaries, and notes.
- `.analysis/animal_scan_results/<folder>.json`: per-folder scan cache recording which images have already been processed (whether or not an animal was found). Future runs diff this cache against the folder's current contents to detect newly added images.

Do not save contact sheets unless the user explicitly asks. Generate them in a temporary directory and delete them before finishing.

## Workflow

1. Inspect the target repository structure, existing `.analysis/animal_index.json`, `.analysis/animal_index_guide.md`, and the per-folder caches under `.analysis/animal_scan_results/`.
2. For each folder, diff its current image list against the cache's `processed` list to find new or never-scanned images. Process only those, plus any folders the user explicitly asks to re-audit.
3. If no cache file exists for a folder, treat every image in it as new.
4. Use a thumbnail branch or worktree when available, usually `thumbnail` or `origin/thumbnail`, to avoid loading full-resolution images.
5. Generate temporary contact sheets from thumbnails covering the new images.
6. Read contact sheets first; open individual images only for ambiguous or species-critical cases.
7. Write/update the index, guide, and scan cache. Validate JSON and that every indexed path exists in the main gallery tree.
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

## Scan Cache

Maintain per-folder scan caches under `.analysis/animal_scan_results/`. The cache is the source of truth for "what has already been processed"; the guide is just a human-readable narrative on top of it.

Filename: take the folder path relative to the gallery root, replace `/` with `__`, append `.json`. Use `_root.json` for images at the gallery root.

Format:

```json
{
  "_meta": {
    "folder": "yakushima",
    "last_scan": "YYYY-MM-DD",
    "thumbnail_source": "origin/thumbnail"
  },
  "processed": [
    "yakushima/IMG_0001.webp",
    "yakushima/IMG_0002.webp"
  ]
}
```

`processed` lists every image (gallery-root-relative path) that has been examined, regardless of whether an animal was identified. To plan an incremental run:

1. Enumerate the folder's current image files.
2. Subtract the entries in `processed`.
3. The remainder is the new work for this run.

Always update the cache when a folder's scan finishes (or partially advances). Append to `processed`, do not rewrite from scratch — except when the user explicitly asks to re-audit, in which case ignore the cache for that folder and replace it on completion.

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

Keep `.analysis/animal_index_guide.md` as a human-readable narrative. The scan cache (not the guide) decides what gets re-scanned, so the guide does not need machine-parsable status flags.

Use one section per folder with this shape:

```text
### <folder>

- Last scanned: YYYY-MM-DD
- Processed: <N> images
- Animals: <comma-separated species keys, or "none">
- Notes: <optional free-form remarks>
```

Other rules:

- Remove stale “partial” / “todo” statements once a folder is fully processed.
- Do not hard-code machine-specific absolute paths.
- Note that incremental runs only re-scan images missing from `.analysis/animal_scan_results/`; folders with newly added images will be partially re-processed automatically.

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
    print('\n'.join(missing))
PY
```

Report any skipped folders, ambiguous species, orphan thumbnails, and validation failures in the final response.
