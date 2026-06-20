#!/usr/bin/env bash
# preflight.sh — Validate API connectivity and credits before dispatching
# Usage: make preflight (or ./scripts/preflight.sh)
#
# Checks:
#   1. Which environment is active (test/production)
#   2. Pings the active provider API with a minimal request
#   3. Verifies the API key has sufficient credits for at least one agent turn
#   4. Reports PASS/FAIL with actionable guidance

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
ENV_FILE="$PROJECT_DIR/shared/environment.yml"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
CYAN='\033[0;36m'
NC='\033[0m'

echo ""
echo -e "${CYAN}━━━ Preflight Check ━━━${NC}"
echo ""

# 1. Detect active environment
ACTIVE_ENV=$(grep '^active:' "$ENV_FILE" | awk '{print $2}')
echo -e "  Environment:  ${CYAN}${ACTIVE_ENV}${NC}"

# 2. Read provider from translator config (source of truth)
TRANSLATOR_CONFIG="$PROJECT_DIR/profiles/translator/config.yaml"
PROVIDER=$(grep '^\s*provider:' "$TRANSLATOR_CONFIG" | head -1 | awk '{print $2}')
MODEL=$(grep '^\s*default:' "$TRANSLATOR_CONFIG" | head -1 | awk '{print $2}')
echo -e "  Provider:     ${CYAN}${PROVIDER}${NC}"
echo -e "  Model:        ${CYAN}${MODEL}${NC}"
echo ""

# 3. Load API keys — check multiple sources (Hermes stores keys in various places)
for envfile in "$HOME/.hermes/.env" "$HOME/.hermes/profiles/translator/.env" "$PROJECT_DIR/profiles/translator/.env"; do
    [[ -f "$envfile" ]] && source "$envfile" 2>/dev/null
done

PASS=true

# 4. Test API connectivity using hermes doctor (authoritative source)
echo -n "  Testing $PROVIDER API... "
DOCTOR_OUTPUT=$(hermes doctor 2>&1)

if [[ "$PROVIDER" == "anthropic" ]]; then
    if echo "$DOCTOR_OUTPUT" | grep -q "✓ Anthropic API"; then
        # Hermes sees the key — read it from env (loaded from .env files above)
        API_KEY="${ANTHROPIC_API_KEY:-}"
        if [[ -n "$API_KEY" ]]; then
            HTTP_CODE=$(curl -s -o /tmp/preflight_response.json -w "%{http_code}" \
                https://api.anthropic.com/v1/messages \
                -H "x-api-key: $API_KEY" \
                -H "anthropic-version: 2023-06-01" \
                -H "content-type: application/json" \
                -d '{"model":"claude-sonnet-4-20250514","max_tokens":5,"messages":[{"role":"user","content":"ping"}]}' 2>/dev/null)

            if [[ "$HTTP_CODE" == "200" ]]; then
                echo -e "${GREEN}PASS${NC}  (credits OK)"
            elif [[ "$HTTP_CODE" == "400" || "$HTTP_CODE" == "429" ]]; then
                ERROR_MSG=$(python3 -c "import json; print(json.load(open('/tmp/preflight_response.json')).get('error',{}).get('message','unknown'))" 2>/dev/null || echo "HTTP $HTTP_CODE")
                echo -e "${RED}FAIL${NC}  ($ERROR_MSG)"
                echo -e "         ${YELLOW}→ https://console.anthropic.com/settings/billing${NC}"
                PASS=false
            else
                echo -e "${YELLOW}WARN${NC}  (HTTP $HTTP_CODE — unexpected)"
            fi
            rm -f /tmp/preflight_response.json
        else
            echo -e "${YELLOW}WARN${NC}  (key detected but could not extract for credit check)"
        fi
    else
        echo -e "${RED}FAIL${NC}  (hermes doctor: Anthropic API not configured)"
        PASS=false
    fi

elif [[ "$PROVIDER" == "zai" ]]; then
    if echo "$DOCTOR_OUTPUT" | grep -q "✓ Z.AI"; then
        # Hermes sees Z.AI — do a credit check with actual model
        API_KEY="${ZAI_API_KEY:-${GLM_API_KEY:-}}"
        # If not in env, try to extract from hermes internals
        if [[ -z "$API_KEY" ]]; then
            API_KEY=$(python3 -c "
import yaml
with open('$HOME/.hermes/config.yaml') as f:
    cfg = yaml.safe_load(f)
# Check known locations for zai key
import os
for k in ['ZAI_API_KEY','GLM_API_KEY']:
    v = os.environ.get(k,'')
    if v: print(v); break
" 2>/dev/null)
        fi

        if [[ -n "$API_KEY" ]]; then
            HTTP_CODE=$(curl -s -o /tmp/preflight_response.json -w "%{http_code}" \
                https://open.bigmodel.cn/api/paas/v4/chat/completions \
                -H "Authorization: Bearer $API_KEY" \
                -H "Content-Type: application/json" \
                -d "{\"model\":\"$MODEL\",\"max_tokens\":5,\"messages\":[{\"role\":\"user\",\"content\":\"ping\"}]}" 2>/dev/null)

            if [[ "$HTTP_CODE" == "200" ]]; then
                echo -e "${GREEN}PASS${NC}  (credits OK)"
            elif [[ "$HTTP_CODE" == "429" || "$HTTP_CODE" == "400" ]]; then
                ERROR_MSG=$(python3 -c "import json; d=json.load(open('/tmp/preflight_response.json')); print(d.get('error',{}).get('message',d.get('message','unknown')))" 2>/dev/null || echo "HTTP $HTTP_CODE")
                echo -e "${RED}FAIL${NC}  ($ERROR_MSG)"
                echo -e "         ${YELLOW}→ https://open.bigmodel.cn${NC}"
                PASS=false
            else
                echo -e "${YELLOW}WARN${NC}  (HTTP $HTTP_CODE — unexpected)"
            fi
            rm -f /tmp/preflight_response.json
        else
            echo -e "${YELLOW}WARN${NC}  (hermes sees Z.AI but API key not in env — credit check skipped)"
        fi
    else
        echo -e "${RED}FAIL${NC}  (hermes doctor: Z.AI API not configured)"
        PASS=false
    fi
else
    echo -e "${RED}FAIL${NC}  Unknown provider: $PROVIDER"
    PASS=false
fi

# 5. Check Kanban board health
echo -n "  Testing Kanban DB... "
BOARD_CHECK=$(hermes kanban list 2>&1)
if echo "$BOARD_CHECK" | grep -q "corrupt\|error\|could not"; then
    echo -e "${RED}FAIL${NC}  (DB corrupt — run: rm ~/.hermes/kanban/boards/translation/kanban.db)"
    PASS=false
else
    echo -e "${GREEN}PASS${NC}"
fi

# 6. Verdict
echo ""
if [[ "$PASS" == true ]]; then
    echo -e "  ${GREEN}━━━ PREFLIGHT PASSED ━━━${NC}"
    echo -e "  Ready to dispatch."
else
    echo -e "  ${RED}━━━ PREFLIGHT FAILED ━━━${NC}"
    echo -e "  Fix the issues above before dispatching."
    exit 1
fi
echo ""
