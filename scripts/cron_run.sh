#!/usr/bin/env bash
set -euo pipefail
# Load .env if present (simple loader)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

python3 src/generate_and_publish.py --action generate --outdir posts --site_dir site
