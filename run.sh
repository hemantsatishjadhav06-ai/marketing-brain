#!/usr/bin/env bash
# One-command local run
set -e
cd "$(dirname "$0")"
python3 -m pip install -r requirements.txt -q
python3 -m uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
