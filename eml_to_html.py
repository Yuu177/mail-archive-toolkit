#!/usr/bin/env python3
"""Extract HTML views from archived .eml files."""

from __future__ import annotations

import argparse
import base64
import contextlib
import html
import io
import logging
import mimetypes
import re
import shutil
from pathlib import Path
from typing import Any

import mailparser

from archive_utils import convert_mail_tree, unique_child_path


logging.getLogger("mailparser.mailparser").setLevel(logging.ERROR)


def safe_file_name(name: str) -> str:
    name = html.unescape(name).strip().replace("\\", "_").replace("/", "_")
    name = re.sub(r"[^\w.@() -]+", "_", name)
    return name.strip(" .") or "file"


def cid_key(value: str) -> str:
    return html.unescape(value).strip().strip("<>").strip()


def normalize_text(content: str) -> str:
    content = content.replace("\r\n", "\n").replace("\r", "\n")
    content = re.sub(r"\n{3,}", "\n\n", content)
    return content.strip()


def format_addresses(addresses: Any) -> str:
    if not addresses:
        return ""

    formatted: list[str] = []
    for address in addresses:
        if isinstance(address, (list, tuple)) and len(address) >= 2:
            name = html.escape(str(address[0] or ""))
            email_address = html.escape(str(address[1] or ""))
            formatted.append(f"{name} &lt;{email_address}&gt;" if name else email_address)
        else:
            formatted.append(html.escape(str(address)))
    return ", ".join(formatted)


def html_body(mail: Any) -> str:
    html_parts = [part for part in mail.text_html or [] if part]
    if html_parts:
        return "\n<hr>\n".join(html_parts)

    plain_parts = [normalize_text(part) for part in mail.text_plain or [] if part]
    escaped = html.escape("\n\n".join(plain_parts))
    return f"<pre>{escaped}</pre>"


def decode_attachment_payload(attachment: dict[str, Any]) -> bytes:
    payload = attachment.get("payload", "")
    transfer_encoding = str(attachment.get("content_transfer_encoding") or "").lower()

    if isinstance(payload, bytes):
        raw = payload
    else:
        raw = str(payload).encode("utf-8")

    if attachment.get("binary") or transfer_encoding == "base64":
        return base64.b64decode(raw, validate=False)
    return raw


def attachment_filename(attachment: dict[str, Any], index: int) -> str:
    filename = str(attachment.get("filename") or "").strip()
    if filename:
        return safe_file_name(filename)

    content_type = str(attachment.get("mail_content_type") or "application/octet-stream")
    extension = mimetypes.guess_extension(content_type) or ".bin"
    return f"part-{index}{extension}"


def extract_assets(mail: Any, uid: str, output_dir: Path) -> tuple[dict[str, str], list[str]]:
    cid_to_path: dict[str, str] = {}
    attachment_links: list[str] = []
    asset_root = output_dir / "assets" / uid
    inline_dir = asset_root / "inline"
    attachment_dir = asset_root / "attachments"
    used_targets: set[Path] = set()

    for index, attachment in enumerate(mail.attachments or [], start=1):
        if not isinstance(attachment, dict):
            continue

        filename = attachment_filename(attachment, index)
        content_id = cid_key(str(attachment.get("content-id") or ""))
        content_type = str(attachment.get("mail_content_type") or "")
        is_inline = bool(content_id)
        target_dir = inline_dir if is_inline else attachment_dir
        target_dir.mkdir(parents=True, exist_ok=True)
        target = unique_child_path(target_dir, filename, used_targets)
        used_targets.add(target)

        target.write_bytes(decode_attachment_payload(attachment))

        relative = target.relative_to(output_dir).as_posix()
        if content_id:
            cid_to_path[content_id] = relative
        if not is_inline or content_type:
            attachment_links.append(relative)

    return cid_to_path, attachment_links


def replace_cid_references(content: str, cid_to_path: dict[str, str]) -> str:
    def replace_attr(match: re.Match[str]) -> str:
        attr = match.group(1)
        quote = match.group(2)
        key = cid_key(match.group(3))
        replacement = cid_to_path.get(key)
        if not replacement:
            return match.group(0)
        return f"{attr}={quote}{html.escape(replacement, quote=True)}{quote}"

    def replace_url(match: re.Match[str]) -> str:
        quote = match.group(1) or ""
        key = cid_key(match.group(2))
        replacement = cid_to_path.get(key)
        if not replacement:
            return match.group(0)
        return f"url({quote}{replacement}{quote})"

    content = re.sub(r'(?i)\b(src|href)=(["\'])cid:([^"\']+)\2', replace_attr, content)
    return re.sub(r"(?i)url\((['\"]?)cid:([^)'\"]+)\1\)", replace_url, content)


def attachment_block(attachment_links: list[str]) -> str:
    if not attachment_links:
        return ""

    items = "\n".join(
        f'      <li><a href="{html.escape(path, quote=True)}">{html.escape(path)}</a></li>'
        for path in attachment_links
    )
    return f"""
  <div class="attachments">
    <div class="label">Attachments</div>
    <ul>
{items}
    </ul>
  </div>
"""


def render_html(mail: Any, source: Path, cid_to_path: dict[str, str], attachment_links: list[str]) -> str:
    subject = html.escape(mail.subject or "")
    body = replace_cid_references(html_body(mail), cid_to_path)
    return f"""<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8">
  <title>{subject}</title>
  <style>
    body {{
      margin: 24px;
      color: #111;
      background: #fff;
      font-family: Arial, "Microsoft YaHei", sans-serif;
      line-height: 1.5;
    }}
    .meta {{
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #ddd;
      font-size: 14px;
      color: #333;
    }}
    .meta div {{ margin: 4px 0; }}
    .label {{ color: #666; display: inline-block; min-width: 80px; }}
    .attachments {{
      margin-bottom: 24px;
      padding-bottom: 16px;
      border-bottom: 1px solid #ddd;
      font-size: 14px;
    }}
    .attachments ul {{ margin: 8px 0 0 0; padding-left: 20px; }}
    img {{ max-width: 100%; height: auto; }}
    pre {{ white-space: pre-wrap; word-break: break-word; }}
  </style>
</head>
<body>
  <div class="meta">
    <div><span class="label">Source</span>{html.escape(str(source))}</div>
    <div><span class="label">Date</span>{html.escape(str(mail.date or ""))}</div>
    <div><span class="label">From</span>{format_addresses(mail.from_)}</div>
    <div><span class="label">To</span>{format_addresses(mail.to)}</div>
    <div><span class="label">Subject</span>{subject}</div>
  </div>
{attachment_block(attachment_links)}
  <div class="body">
{body}
  </div>
</body>
</html>
"""


def convert_file(source: Path, output_dir: Path) -> None:
    target = output_dir / f"{source.stem}.html"
    asset_root = output_dir / "assets" / source.stem

    with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
        mail = mailparser.parse_from_file(str(source))

    output_dir.mkdir(parents=True, exist_ok=True)
    if asset_root.exists():
        shutil.rmtree(asset_root)
    cid_to_path, attachment_links = extract_assets(mail, source.stem, output_dir)
    target.write_text(render_html(mail, source, cid_to_path, attachment_links), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Convert archived .eml files to HTML files.")
    parser.add_argument(
        "--input",
        required=True,
        type=Path,
        help="Root directory containing mailbox subdirectories.",
    )
    parser.add_argument(
        "--output",
        required=True,
        type=Path,
        help="Root directory for generated HTML mailbox subdirectories.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    print("Starting EML to HTML conversion")
    print(f"  input: {args.input}")
    print(f"  output: {args.output}")
    return convert_mail_tree(args.input, args.output, "*.eml", convert_file)


if __name__ == "__main__":
    raise SystemExit(main())
