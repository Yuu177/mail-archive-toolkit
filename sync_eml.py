#!/usr/bin/env python3
"""Archive IMAP messages as raw .eml files."""

from __future__ import annotations

import argparse
import json
import sys
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Optional

from imapclient import IMAPClient
from imapclient.exceptions import IMAPClientError
from imapclient import imap_utf7
from tqdm import tqdm

from archive_utils import mailbox_relative_path


DEFAULT_CONFIG = Path("config.json")


@dataclass(frozen=True)
class Config:
    email: str
    password: str
    imap_host: str
    imap_port: int
    mailboxes: list[str]
    output_dir: Path


@dataclass
class SyncStats:
    downloaded: int = 0
    skipped: int = 0
    failed: int = 0

    def add(self, other: "SyncStats") -> None:
        self.downloaded += other.downloaded
        self.skipped += other.skipped
        self.failed += other.failed

    def exit_code(self) -> int:
        return 1 if self.failed else 0

    def progress_postfix(self) -> OrderedDict[str, int]:
        return OrderedDict(
            [
                ("downloaded", self.downloaded),
                ("skipped", self.skipped),
                ("failed", self.failed),
            ]
        )


def load_config(path: Path) -> Config:
    if not path.exists():
        raise SystemExit(
            f"Config file not found: {path}\n"
            f"Create {path} from config.example.json and fill in your account."
        )

    try:
        raw: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise SystemExit(f"Invalid JSON in {path}: {exc}") from exc

    mailboxes = raw.get("mailboxes")
    if not isinstance(mailboxes, list):
        raise SystemExit("Config value 'mailboxes' must be a list of mailbox names.")
    mailboxes = [str(mailbox).strip() for mailbox in mailboxes if str(mailbox).strip()]
    if not mailboxes:
        raise SystemExit("Config value 'mailboxes' must contain at least one mailbox name.")

    try:
        imap_port = int(raw.get("imap_port", 993))
    except (TypeError, ValueError) as exc:
        raise SystemExit("Config value 'imap_port' must be an integer.") from exc

    config = Config(
        email=str(raw.get("email", "")).strip(),
        password=str(raw.get("password", "")),
        imap_host=str(raw.get("imap_host", "imap.exmail.qq.com")).strip(),
        imap_port=imap_port,
        mailboxes=mailboxes,
        output_dir=Path(str(raw.get("output_dir", "mail_archive/raw"))),
    )

    missing = []
    if not config.email or config.email == "your.name@example.com":
        missing.append("email")
    if not config.password or config.password == "your-client-password":
        missing.append("password")
    if not config.imap_host:
        missing.append("imap_host")
    if config.imap_port <= 0:
        raise SystemExit("Config value 'imap_port' must be greater than 0.")
    if missing:
        raise SystemExit(f"Fill these config values before running: {', '.join(missing)}")

    return config


def connect(config: Config) -> IMAPClient:
    print(f"Connecting to {config.imap_host}:{config.imap_port}...")
    client = IMAPClient(config.imap_host, port=config.imap_port, use_uid=True, ssl=True)
    try:
        print("Logging in...")
        client.login(config.email, config.password)
    except Exception:
        try:
            client.logout()
        except Exception:
            pass
        raise
    return client


def mailbox_name(raw_name: Any) -> str:
    if isinstance(raw_name, bytes):
        return imap_utf7.decode(raw_name)
    return str(raw_name)


def print_mailbox_summary(client: IMAPClient) -> None:
    print("Mailboxes:")
    folders = client.list_folders()
    for _flags, _delimiter, raw_name in folders:
        name = mailbox_name(raw_name)
        try:
            folder_status = client.select_folder(name, readonly=True)
            message_count = int(folder_status.get(b"EXISTS", 0))
            print(f"  {name}: {message_count}")
        except Exception as exc:
            print(f"  {name}: unavailable ({exc})")


def list_target_uids(client: IMAPClient, mailbox: str, limit: Optional[int]) -> list[int]:
    print(f"Selecting mailbox {mailbox}...")
    folder_status = client.select_folder(mailbox, readonly=True)
    message_count = int(folder_status.get(b"EXISTS", 0))
    if message_count <= 0:
        return []

    print(f"Mailbox has {message_count} message(s); searching UID list...")
    uids = [int(uid) for uid in client.search("ALL")]
    sorted_uids = sorted(uids)
    if limit is None:
        return sorted_uids
    return sorted_uids[-limit:]


def fetch_raw_message(client: IMAPClient, uid: int) -> bytes:
    response = client.fetch([uid], ["RFC822"])
    data = response.get(uid)
    if not data or b"RFC822" not in data:
        raise RuntimeError(f"IMAP fetch returned no message bytes for UID {uid}.")
    return data[b"RFC822"]


def write_eml(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = path.with_suffix(path.suffix + ".tmp")
    tmp_path.write_bytes(content)
    tmp_path.replace(path)


def sync_mailbox(
    client: IMAPClient,
    config: Config,
    mailbox: str,
    limit: Optional[int],
) -> SyncStats:
    mailbox_path = mailbox_relative_path(mailbox)
    mailbox_dir = config.output_dir / mailbox_path
    stats = SyncStats()

    uids = list_target_uids(client, mailbox, limit)
    print(f"Found {len(uids)} UID(s) in {mailbox} for this run.")

    progress = tqdm(uids, desc=str(mailbox_path), unit="mail")
    for uid in progress:
        target = mailbox_dir / f"{uid}.eml"
        if target.exists():
            stats.skipped += 1
            progress.set_postfix(stats.progress_postfix(), refresh=False)
            continue

        try:
            raw_message = fetch_raw_message(client, uid)
            write_eml(target, raw_message)
            stats.downloaded += 1
        except Exception as exc:
            stats.failed += 1
            tqdm.write(f"failed {mailbox} {uid}: {exc}", file=sys.stderr)
        progress.set_postfix(stats.progress_postfix(), refresh=False)

    return stats


def sync(config: Config, limit: Optional[int]) -> SyncStats:
    client = connect(config)
    try:
        print_mailbox_summary(client)
        totals = SyncStats()
        for mailbox in config.mailboxes:
            print(f"\nSyncing mailbox: {mailbox}")
            totals.add(sync_mailbox(client, config, mailbox, limit))
    finally:
        client.logout()

    return totals


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download IMAP messages as .eml files."
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG,
        help="Path to JSON config file. Defaults to config.json.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Only scan the latest N messages from each configured mailbox. Omit to scan all messages.",
    )
    return parser.parse_args()


def print_run_summary(config_path: Path, config: Config, limit: Optional[int]) -> None:
    limit_text = "all" if limit is None else str(limit)
    print("Starting EML sync")
    print(f"  config: {config_path}")
    print(f"  mailboxes: {', '.join(config.mailboxes)}")
    print(f"  limit: {limit_text}")
    print(f"  output: {config.output_dir}")


def main() -> int:
    args = parse_args()
    config = load_config(args.config)
    limit = args.limit
    if args.limit is not None:
        if args.limit <= 0:
            raise SystemExit("--limit must be greater than 0.")

    print_run_summary(args.config, config, limit)

    try:
        stats = sync(config, limit)
    except IMAPClientError as exc:
        print(f"IMAP error: {exc}", file=sys.stderr)
        print(
            "Login or IMAP access was rejected by the mail server. Check that "
            "IMAP is enabled and that config.json uses the client "
            "password/authorization code.",
            file=sys.stderr,
        )
        return 1

    print(
        f"Done. downloaded={stats.downloaded}, skipped={stats.skipped}, failed={stats.failed}, "
        f"output={config.output_dir}"
    )
    return stats.exit_code()


if __name__ == "__main__":
    raise SystemExit(main())
