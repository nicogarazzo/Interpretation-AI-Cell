#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────────
# ingest-feedback.sh — Normalize client feedback into standard JSON
#
# Usage:
#   ./scripts/ingest-feedback.sh <run_id> <input_file>
#
# Input can be:
#   - A JSON file (Tally export, manual JSON, or raw review text)
#   - A plain text file (copied from clipboard/email)
#
# Output:
#   corpus/runs/<run_id>/feedback/client_review.json
# ─────────────────────────────────────────────────────────────────
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"

if [ $# -lt 2 ]; then
  echo "Usage: $0 <run_id> <input_file>"
  echo ""
  echo "Examples:"
  echo "  $0 2026-06-02_001 ~/Downloads/tally-export.json"
  echo "  $0 2026-06-02_001 ~/Desktop/client-email.txt"
  exit 1
fi

RUN_ID="$1"
INPUT_FILE="$2"
RUN_DIR="${PROJECT_DIR}/corpus/runs/${RUN_ID}"
FEEDBACK_DIR="${RUN_DIR}/feedback"
OUTPUT="${FEEDBACK_DIR}/client_review.json"

# Validate run exists
if [ ! -d "$RUN_DIR" ]; then
  echo "ERROR: Run directory not found: ${RUN_DIR}"
  exit 1
fi

# Create feedback dir if needed
mkdir -p "$FEEDBACK_DIR"

# Validate input file exists
if [ ! -f "$INPUT_FILE" ]; then
  echo "ERROR: Input file not found: ${INPUT_FILE}"
  exit 1
fi

# Copy raw input for audit trail
cp "$INPUT_FILE" "${FEEDBACK_DIR}/raw_input$(basename "$INPUT_FILE" | sed 's/.*\(\.[^.]*\)$/\1/')"
echo "Raw input saved to: ${FEEDBACK_DIR}/"

# Detect format and normalize
FILE_TYPE=$(file -b --mime-type "$INPUT_FILE")

if echo "$FILE_TYPE" | grep -q "json\|text/plain"; then
  # Try parsing as JSON first
  if python3 -c "import json; json.load(open('$INPUT_FILE'))" 2>/dev/null; then
    echo "Detected: JSON input"
    python3 "${SCRIPT_DIR}/normalize-feedback.py" "$RUN_ID" "$INPUT_FILE" "$OUTPUT"
  else
    echo "Detected: Plain text input"
    python3 "${SCRIPT_DIR}/normalize-feedback.py" "$RUN_ID" "$INPUT_FILE" "$OUTPUT" --text
  fi
else
  echo "ERROR: Unsupported file type: ${FILE_TYPE}"
  echo "Supported: JSON (.json) or plain text (.txt)"
  exit 1
fi

echo ""
echo "Feedback ingested successfully:"
echo "  Run:    ${RUN_ID}"
echo "  Output: ${OUTPUT}"
echo ""
echo "Next step: run reconciliation"
echo "  python3 scripts/reconcile.py ${RUN_ID}"
