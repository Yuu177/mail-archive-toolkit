# Tencent Exmail EML Archive

This tool downloads Tencent Exmail messages through IMAP and saves each message
as a raw `.eml` file.

It uses `IMAPClient` for IMAP access, `mail-parser` for `.eml` parsing,
`html2text` for HTML-to-text conversion, and `tqdm` for progress bars.

## Configure

Edit `config.json`:

```json
{
  "email": "your.name@example.com",
  "password": "your-client-password",
  "imap_host": "imap.exmail.qq.com",
  "imap_port": 993,
  "mailboxes": ["INBOX"],
  "output_dir": "mail_archive/raw"
}
```

If the normal web login password does not work, use the client password or
authorization code from Tencent Exmail.

## Run

Install dependencies first:

```bash
python3 -m pip install -r requirements.txt
```

If local user packages break `pip`, use:

```bash
PYTHONNOUSERSITE=1 python3 -m pip install --user -r requirements.txt
```

```bash
python3 sync_eml.py
```

The first run downloads all messages from each configured mailbox into:

```text
mail_archive/raw/<mailbox>/
```

Mailbox directory names include a short hash suffix to avoid collisions between
similar IMAP names such as `A/B` and `A_B`.

Run it again any time. Existing `UID.eml` files are skipped.

To test with a small scan size:

```bash
python3 sync_eml.py --limit 20
```

At startup the script prints all IMAP mailboxes, message counts, and the local
directory name used for each mailbox. Use the IMAP mailbox names in
`mailboxes` in `config.json`.

Example:

```json
"mailboxes": ["INBOX", "Sent Messages", "其他文件夹/gitlab"]
```

## Convert to HTML

Convert archived `.eml` messages into `.html` files. Inline `cid:` images and
attachments are saved under `assets/`.

```bash
python3 eml_to_html.py --input mail_archive/raw --output mail_archive/html
```

The output is written to:

```text
mail_archive/html/<mailbox>/
```

It converts every mailbox directory under the input root.

## Convert to readable text

Convert `.html` files into searchable `.txt` files:

```bash
python3 html_to_text.py --input mail_archive/html --output mail_archive/text
```

The output is written to:

```text
mail_archive/text/<mailbox>/
```

Search readable text with:

```bash
rg "keyword" mail_archive/text/INBOX
```

## Recommended pipeline

```bash
python3 sync_eml.py --limit 10
python3 eml_to_html.py --input mail_archive/raw --output mail_archive/html
python3 html_to_text.py --input mail_archive/html --output mail_archive/text
```
