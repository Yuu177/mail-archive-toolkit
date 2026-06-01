from __future__ import annotations

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


def mailbox_relative_path(name: str) -> Path:
    if Path(name).is_absolute():
        raise ValueError(f"Mailbox name must be relative: {name!r}")

    parts = name.split("/")
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise ValueError(f"Mailbox name contains an unsafe path segment: {name!r}")

    return Path(*parts)


def subdirs(root: Path) -> list[Path]:
    return sorted([path for path in root.iterdir() if path.is_dir()], key=lambda path: path.name)


def files_by_name(input_dir: Path, pattern: str) -> list[Path]:
    return sorted(input_dir.glob(pattern), key=numeric_name_key)


def mailbox_dirs(root: Path, pattern: str, skip_assets: bool = False) -> list[Path]:
    directories: list[Path] = []
    for path in sorted(root.rglob(pattern), key=lambda path: path.relative_to(root).as_posix()):
        if skip_assets and is_generated_asset(path, root, pattern):
            continue
        parent = path.parent
        if parent not in directories:
            directories.append(parent)
    return directories


def is_generated_asset(path: Path, root: Path, pattern: str) -> bool:
    relative_parts = path.relative_to(root).parts
    for index, part in enumerate(relative_parts):
        if part != "assets" or index == 0:
            continue
        asset_root = root.joinpath(*relative_parts[: index + 1])
        mailbox_dir = asset_root.parent
        if any(child.is_file() for child in mailbox_dir.glob(pattern)):
            return True
    return False


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
    display_name: str,
) -> ConversionStats:
    stats = ConversionStats()
    files = files_by_name(input_dir, pattern)

    print(f"Converting mailbox: {display_name}")
    progress = tqdm(files, desc=display_name, unit="mail")
    for source in progress:
        try:
            convert_file(source, output_dir)
            stats.converted += 1
        except Exception as exc:
            stats.failed += 1
            tqdm.write(f"failed {display_name}/{source.name}: {exc}", file=sys.stderr)
        progress.set_postfix(converted=stats.converted, failed=stats.failed)

    return stats


def convert_mail_tree(
    input_root: Path,
    output_root: Path,
    pattern: str,
    convert_file: Callable[[Path, Path], None],
    skip_assets: bool = False,
) -> int:
    if not input_root.is_dir():
        raise SystemExit(f"Input root directory not found: {input_root}")

    totals = ConversionStats()
    for input_dir in mailbox_dirs(input_root, pattern, skip_assets=skip_assets):
        relative_dir = input_dir.relative_to(input_root)
        output_dir = output_root / relative_dir
        stats = convert_mailbox_dir(input_dir, output_dir, pattern, convert_file, relative_dir.as_posix())
        totals.add(stats)

    tqdm.write(f"Done. converted={totals.converted}, failed={totals.failed}, output={output_root}")
    return totals.exit_code()
