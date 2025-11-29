#!/bin/bash
# Wrapper script to run main.py with virtual environment activated

cd "$(dirname "$0")"
source venv/bin/activate
python3 scripts/main.py "$@"


