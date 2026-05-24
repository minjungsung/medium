#!/usr/bin/env bash
set -euo pipefail
# Load .env if present (simple loader)
if [ -f .env ]; then
  export $(grep -v '^#' .env | xargs)
fi

python src/generate_and_publish.py --action generate_and_publish --topic "Daily development insight - $(date +%F)" --publish_status draft --tags "programming,dev"
