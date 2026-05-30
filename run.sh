#!/usr/bin/env sh
set -eu

echo "[1/3] Sync EML"
python3 sync_eml.py

echo "[2/3] Convert EML to HTML"
python3 eml_to_html.py --input mail_archive/raw --output mail_archive/html

echo "[3/3] Convert HTML to text"
python3 html_to_text.py --input mail_archive/html --output mail_archive/text
