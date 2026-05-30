from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Set, Tuple, Union

from tqdm import tqdm


SortKey = Union[Tuple[int, int], Tuple[int, str]]


@dataclass
class ConversionStats:
    converted: int = 0
    failed: int = 0

    def add(self, other: "ConversionStats") -> None:
        self.converted += other.converted
        self.failed += other.failed

    def exit_code(self) -> int:
        return 1 if self.failed else 0


def numeric_name_key(path: Path) -> SortKey:
    if path.stem.isdigit():
        return (0, int(path.stem))
    return (1, path.stem)


def safe_dir_name(name: str) -> str:
    safe = name.strip().replace("\\", "_").replace("/", "_")
    safe = re.sub(r"\s+", "_", safe)
    safe = re.sub(r"[^\w.@()-]+", "_", safe)
    return safe.strip("._") or "mailbox"


def mailbox_dir_name(name: str) -> str:
    digest = hashlib.sha1(name.encode("utf-8")).hexdigest()[:10]
    return f"{safe_dir_name(name)}__{digest}"


def subdirs(root: Path) -> list[Path]:
    return sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.name)


def files_by_name(input_dir: Path, pattern: str) -> list[Path]:
    return sorted(input_dir.glob(pattern), key=numeric_name_key)


def unique_child_path(directory: Path, filename: str, reserved: Optional[Set[Path]] = None) -> Path:
    reserved = reserved or set()
    candidate = directory / filename
    if candidate not in reserved:
        return candidate

    stem = candidate.stem
    suffix = candidate.suffix
    counter = 2
    while True:
        candidate = directory / f"{stem}-{counter}{suffix}"
        if candidate not in reserved:
            return candidate
        counter += 1


def convert_mailbox_dir(
    input_dir: Path,
    output_dir: Path,
    pattern: str,
    convert_file: Callable[[Path, Path], None],
) -> ConversionStats:
    stats = ConversionStats()
    files = files_by_name(input_dir, pattern)

    print(f"Converting mailbox: {input_dir.name}")
    progress = tqdm(files, desc=input_dir.name, unit="mail")
    for source in progress:
        try:
            convert_file(source, output_dir)
            stats.converted += 1
        except Exception as exc:
            stats.failed += 1
            tqdm.write(f"failed {input_dir.name}/{source.name}: {exc}", file=sys.stderr)
        progress.set_postfix(converted=stats.converted, failed=stats.failed)

    return stats


def convert_mail_tree(
    input_root: Path,
    output_root: Path,
    pattern: str,
    convert_file: Callable[[Path, Path], None],
) -> int:
    if not input_root.is_dir():
        raise SystemExit(f"Input root directory not found: {input_root}")

    totals = ConversionStats()
    for input_dir in subdirs(input_root):
        stats = convert_mailbox_dir(input_dir, output_root / input_dir.name, pattern, convert_file)
        totals.add(stats)

    tqdm.write(f"Done. converted={totals.converted}, failed={totals.failed}, output={output_root}")
    return totals.exit_code()
