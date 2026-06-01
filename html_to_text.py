#!/usr/bin/env python3
"""Convert generated HTML mail views to searchable text files."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import html2text

from archive_utils import convert_mail_tree


def normalize_text(content: str) -> str:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"[ \t\f\v]+", " ", content)
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def html_to_text(content: str) -> str:
    converter = html2text.HTML2Text()
    converter.body_width = 0
    converter.ignore_images = True
    converter.ignore_links = False
    converter.ignore_tables = False
    return normalize_text(converter.handle(content))


def convert_file(source: Path, output_dir: Path, force: bool) -> bool:
    target = output_dir / f"{source.stem}.txt"
    if target.exists() and not force:
        return False

    output_dir.mkdir(parents=True, exist_ok=True)
    target.write_text(html_to_text(source.read_text(encoding="utf-8", errors="replace")), encoding="utf-8")
    return True


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert generated mail HTML files to text files.")
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Root directory containing HTML mailbox subdirectories.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Root directory for generated text mailbox subdirectories.",
    )
    parser.add_argument(
        "--force",
        action="store_true",
        help="Overwrite existing text files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Starting HTML to text conversion")
    print(f"  input: {args.input}")
    print(f"  output: {args.output}")
    print(f"  force: {args.force}")
    return convert_mail_tree(
        args.input,
        args.output,
        "*.html",
        convert_file,
        skip_assets=True,
        force=args.force,
    )


if __name__ == "__main__":
    raise SystemExit(main())
