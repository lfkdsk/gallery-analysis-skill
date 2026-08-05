#!/usr/bin/env python3
"""Build dense annual gallery collages under .analysis/annual-summary/."""

import argparse
import json
import math
import os
import sys
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from PIL import Image, ImageOps


IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.tif', '.tiff'}
EXIF_DATETIME_TAGS = (36867, 36868, 306)  # original, digitized, generic


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('gallery_root', type=Path)
    parser.add_argument('--thumbnail-root', type=Path)
    parser.add_argument('--max-photos', type=int, default=60)
    parser.add_argument('--columns', type=int, default=10)
    parser.add_argument('--size', default='1920x1080')
    parser.add_argument('--quality', type=int, default=82)
    return parser.parse_args()


def parse_size(value):
    try:
        width, height = (int(part) for part in value.lower().split('x', 1))
    except (TypeError, ValueError):
        raise ValueError('--size must look like 1920x1080')
    if width < 1 or height < 1:
        raise ValueError('--size dimensions must be positive')
    return width, height


def read_album_years(gallery_root):
    readme = gallery_root / 'README.yml'
    if not readme.exists():
        return {}
    try:
        import yaml
    except ImportError:
        print('warning: PyYAML unavailable; skipping README.yml date fallback', file=sys.stderr)
        return {}
    try:
        payload = yaml.safe_load(readme.read_text(encoding='utf-8')) or {}
    except (OSError, ValueError, yaml.YAMLError) as error:
        print(f'warning: could not read {readme}: {error}', file=sys.stderr)
        return {}

    years = {}
    for album in payload.values() if isinstance(payload, dict) else []:
        if not isinstance(album, dict):
            continue
        album_path = str(album.get('url', '')).strip('/')
        album_date = str(album.get('date', ''))
        year = album_date[:4]
        if album_path and year.isdigit():
            years[album_path] = year
    return years


def iter_images(root):
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if not name.startswith('.')]
        for filename in filenames:
            path = Path(current_root) / filename
            if path.suffix.lower() in IMAGE_EXTENSIONS:
                yield path


def exif_datetime(path):
    try:
        with Image.open(path) as image:
            exif = image.getexif()
            for tag in EXIF_DATETIME_TAGS:
                value = exif.get(tag)
                if not value:
                    continue
                text = str(value).strip('\x00 ')
                try:
                    return datetime.strptime(text[:19], '%Y:%m:%d %H:%M:%S')
                except ValueError:
                    continue
    except (OSError, ValueError, Image.DecompressionBombError):
        pass
    return None


def image_year_and_sort_key(path, image_root, album_years):
    taken_at = exif_datetime(path)
    if taken_at:
        return str(taken_at.year), taken_at.isoformat()

    relative = path.relative_to(image_root).as_posix()
    matching_album = max(
        (album for album in album_years if relative == album or relative.startswith(album + '/')),
        key=len,
        default='',
    )
    if matching_album:
        return album_years[matching_album], relative
    return None, relative


def curated_paths(summary_dir, year, image_root):
    config_path = summary_dir / f'{year}.json'
    if not config_path.exists():
        return []
    try:
        payload = json.loads(config_path.read_text(encoding='utf-8'))
    except (OSError, ValueError) as error:
        print(f'warning: could not read {config_path}: {error}', file=sys.stderr)
        return []

    selected = []
    for month in sorted(payload) if isinstance(payload, dict) else []:
        relative = payload[month]
        if not (isinstance(month, str) and len(month) == 2 and month.isdigit()):
            continue
        if not isinstance(relative, str):
            continue
        relative_path = Path(relative.lstrip('/'))
        candidates = [image_root / relative_path]
        candidates.extend(image_root / relative_path.with_suffix(ext) for ext in ('.webp', '.jpg', '.jpeg'))
        for candidate in candidates:
            if candidate.is_file() and candidate not in selected:
                selected.append(candidate)
                break
    return selected


def even_sample(paths, count):
    if count <= 0:
        return []
    if len(paths) <= count:
        return paths
    if count == 1:
        return [paths[len(paths) // 2]]
    return [paths[round(index * (len(paths) - 1) / (count - 1))] for index in range(count)]


def readable_images(paths):
    valid = []
    for path in paths:
        try:
            with Image.open(path) as image:
                image.verify()
            valid.append(path)
        except (OSError, ValueError, Image.DecompressionBombError) as error:
            print(f'warning: skipping unreadable image {path}: {error}', file=sys.stderr)
    return valid


def create_collage(paths, output, size, max_columns, quality):
    paths = readable_images(paths)
    if not paths:
        return 0

    width, height = size
    canvas_ratio = width / height
    row_count = max(1, round(math.sqrt(len(paths) / canvas_ratio)))
    row_count = max(row_count, math.ceil(len(paths) / max_columns))
    base_count, extra_count = divmod(len(paths), row_count)
    row_sizes = [base_count + (1 if row < extra_count else 0) for row in range(row_count)]
    canvas = Image.new('RGB', size, '#000')
    image_index = 0

    for row, items_in_row in enumerate(row_sizes):
        top = round(row * height / row_count)
        bottom = round((row + 1) * height / row_count)
        for column in range(items_in_row):
            left = round(column * width / items_in_row)
            right = round((column + 1) * width / items_in_row)
            tile_size = (right - left, bottom - top)
            with Image.open(paths[image_index]) as source:
                source = ImageOps.exif_transpose(source).convert('RGB')
                source.thumbnail((tile_size[0] * 2, tile_size[1] * 2), Image.Resampling.LANCZOS)
                tile = ImageOps.fit(source, tile_size, method=Image.Resampling.LANCZOS)
                canvas.paste(tile, (left, top))
            image_index += 1

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.stem + '.tmp.webp')
    canvas.save(temporary, format='WEBP', quality=quality, method=6)
    os.replace(temporary, output)
    return len(paths)


def main():
    args = parse_args()
    gallery_root = args.gallery_root.expanduser().resolve()
    image_root = (args.thumbnail_root or gallery_root).expanduser().resolve()
    size = parse_size(args.size)
    if not gallery_root.is_dir() or not image_root.is_dir():
        raise SystemExit('gallery and thumbnail roots must be existing directories')
    if args.max_photos < 1 or args.columns < 1:
        raise SystemExit('--max-photos and --columns must be positive')

    summary_dir = gallery_root / '.analysis' / 'annual-summary'
    summary_dir.mkdir(parents=True, exist_ok=True)
    album_years = read_album_years(gallery_root)
    by_year = defaultdict(list)

    for path in iter_images(image_root):
        year, sort_key = image_year_and_sort_key(path, image_root, album_years)
        if year:
            by_year[year].append((sort_key, path))

    counts = {}
    used = {}
    for year, dated_paths in sorted(by_year.items()):
        dated_paths.sort(key=lambda item: (item[0], item[1].as_posix()))
        year_paths = list(dict.fromkeys(path for _, path in dated_paths))
        counts[year] = len(year_paths)
        selected = curated_paths(summary_dir, year, image_root)
        selected_set = set(selected)
        candidates = [path for path in year_paths if path not in selected_set]
        selected.extend(even_sample(candidates, max(0, args.max_photos - len(selected))))
        selected = selected[:args.max_photos]
        output = summary_dir / f'{year}-background.webp'
        used[year] = create_collage(selected, output, size, args.columns, args.quality)
        if used[year]:
            print(f'{year}: {used[year]} of {counts[year]} photos -> {output}')

    years = [year for year in sorted(by_year) if used.get(year)]
    index = {
        'years': years,
        'latest': years[-1] if years else None,
        'counts': {year: counts[year] for year in years},
        'used': {year: used[year] for year in years},
        'generated': date.today().isoformat(),
    }
    (summary_dir / 'index.json').write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + '\n',
        encoding='utf-8',
    )
    if not years:
        print('warning: no dated images found', file=sys.stderr)


if __name__ == '__main__':
    main()
