from __future__ import annotations

import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional, Set, Tuple, Union

from tqdm import tqdm


SortKey = Union[Tuple[int, int], Tuple[int, str]]
ASSET_ROOT_NAME = ".mail-archive-assets"


@dataclass(frozen=True)
class ConversionContext:
    input_root: Path
    output_root: Path
    input_dir: Path
    output_dir: Path
    relative_dir: Path
    force: bool


ConvertFile = Callable[[Path, ConversionContext], bool]


@dataclass
class ConversionStats:
    converted: int = 0
    skipped: int = 0
    failed: int = 0

    def add(self, other: "ConversionStats") -> None:
        self.converted += other.converted
        self.skipped += other.skipped
        self.failed += other.failed

    def exit_code(self) -> int:
        return 1 if self.failed else 0

    def progress_postfix(self) -> OrderedDict[str, int]:
        return OrderedDict(
            [
                ("converted", self.converted),
                ("skipped", self.skipped),
                ("failed", self.failed),
            ]
        )


def numeric_name_key(path: Path) -> SortKey:
    if path.stem.isdigit():
        return (0, int(path.stem))
    return (1, path.stem)


def mailbox_relative_path(name: str) -> Path:
    if Path(name).is_absolute():
        raise ValueError(f"Mailbox name must be relative: {name!r}")

    parts = name.split("/")
    unsafe = {"", ".", "..", ASSET_ROOT_NAME}
    if not parts or any(part in unsafe for part in parts):
        raise ValueError(f"Mailbox name contains an unsafe path segment: {name!r}")

    return Path(*parts)


def files_by_name(input_dir: Path, pattern: str) -> list[Path]:
    return sorted(input_dir.glob(pattern), key=numeric_name_key)


def mailbox_dirs(root: Path, pattern: str, skip_generated_assets: bool = False) -> list[Path]:
    directories: list[Path] = []
    seen: set[Path] = set()
    for path in sorted(root.rglob(pattern), key=lambda path: path.relative_to(root).as_posix()):
        if skip_generated_assets and is_generated_asset_file(path, root):
            continue
        parent = path.parent
        if parent not in seen:
            seen.add(parent)
            directories.append(parent)
    return directories


def is_generated_asset_file(path: Path, root: Path) -> bool:
    relative_parts = path.relative_to(root).parts
    return bool(relative_parts and relative_parts[0] == ASSET_ROOT_NAME)


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
    pattern: str,
    convert_file: ConvertFile,
    display_name: str,
    context: ConversionContext,
) -> ConversionStats:
    stats = ConversionStats()
    files = files_by_name(input_dir, pattern)

    print(f"Converting mailbox: {display_name}")
    progress = tqdm(files, desc=display_name, unit="mail")
    for source in progress:
        try:
            if convert_file(source, context):
                stats.converted += 1
            else:
                stats.skipped += 1
        except Exception as exc:
            stats.failed += 1
            tqdm.write(f"failed {display_name}/{source.name}: {exc}", file=sys.stderr)
        progress.set_postfix(stats.progress_postfix(), refresh=False)

    return stats


def convert_mail_tree(
    input_root: Path,
    output_root: Path,
    pattern: str,
    convert_file: ConvertFile,
    skip_generated_assets: bool = False,
    force: bool = False,
) -> int:
    if not input_root.is_dir():
        raise SystemExit(f"Input root directory not found: {input_root}")

    totals = ConversionStats()
    for input_dir in mailbox_dirs(
        input_root,
        pattern,
        skip_generated_assets=skip_generated_assets,
    ):
        relative_dir = input_dir.relative_to(input_root)
        output_dir = output_root / relative_dir
        context = ConversionContext(
            input_root=input_root,
            output_root=output_root,
            input_dir=input_dir,
            output_dir=output_dir,
            relative_dir=relative_dir,
            force=force,
        )
        stats = convert_mailbox_dir(
            input_dir,
            pattern,
            convert_file,
            relative_dir.as_posix(),
            context,
        )
        totals.add(stats)

    tqdm.write(
        f"Done. converted={totals.converted}, skipped={totals.skipped}, "
        f"failed={totals.failed}, output={output_root}"
    )
    return totals.exit_code()
