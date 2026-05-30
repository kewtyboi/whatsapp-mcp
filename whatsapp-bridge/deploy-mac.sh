#!/usr/bin/env bash
# deploy-mac.sh — Build and install the whatsapp-bridge binary for macOS launchd
#
# Root cause context: ~/Library/Application Support/whatsapp-bridge/ is protected by
# the WhatsApp Mac App Store app (net.whatsapp.WhatsApp). Any binary executed from that
# exact path receives SIGKILL instantly from the WhatsApp sandbox. The canonical
# deployment directory is ~/Library/Application Support/whatsapp-bridge-daemon/ instead.
#
# This script is idempotent. Safe to run repeatedly.

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
INSTALL_DIR="${HOME}/Library/Application Support/whatsapp-bridge-daemon"
BINARY_NAME="whatsapp-bridge"
PLIST_LABEL="com.liam.whatsapp-bridge"
PLIST_PATH="${HOME}/Library/LaunchAgents/${PLIST_LABEL}.plist"
HEALTH_URL="http://localhost:8080/api/health"
MAX_WAIT=30

log()  { echo "[deploy-mac] $*"; }
die()  { echo "[deploy-mac] ERROR: $*" >&2; exit 1; }

# ── 1. Build ────────────────────────────────────────────────────────────────
log "Building ${BINARY_NAME} from ${SCRIPT_DIR}..."
(cd "${SCRIPT_DIR}" && go build -o /tmp/"${BINARY_NAME}-new" .) \
  || die "go build failed"
log "Build OK"

# ── 2. Strip quarantine + ad-hoc sign ───────────────────────────────────────
# macOS sometimes stamps com.apple.quarantine on binaries downloaded or copied
# across certain paths. Strip it then apply an ad-hoc signature so AMFI is happy.
xattr -cr /tmp/"${BINARY_NAME}-new"
codesign -s - --force --deep /tmp/"${BINARY_NAME}-new" \
  || die "codesign failed"
log "Ad-hoc signature applied"

# ── 3. Install to canonical daemon directory ─────────────────────────────────
mkdir -p "${INSTALL_DIR}"
cp /tmp/"${BINARY_NAME}-new" "${INSTALL_DIR}/${BINARY_NAME}"
# Re-apply signature at final path (codesign hashes are path-sensitive for ad-hoc)
codesign -s - --force --deep "${INSTALL_DIR}/${BINARY_NAME}" \
  || die "codesign at install path failed"
log "Installed to ${INSTALL_DIR}/${BINARY_NAME}"

# ── 4. Verify codesign and no quarantine ─────────────────────────────────────
codesign -dvvv "${INSTALL_DIR}/${BINARY_NAME}" 2>&1 | grep -E "^(Executable|Identifier|Signature|Format)"
if xattr "${INSTALL_DIR}/${BINARY_NAME}" | grep -q "com.apple.quarantine"; then
  die "Quarantine xattr still present after install — remove manually with: xattr -d com.apple.quarantine '${INSTALL_DIR}/${BINARY_NAME}'"
fi
log "No quarantine xattr. Codesign valid."

# ── 5. Restart launchd service ───────────────────────────────────────────────
if [ ! -f "${PLIST_PATH}" ]; then
  log "WARNING: plist not found at ${PLIST_PATH} — skipping launchd restart"
  log "Install the plist first: cp ${SCRIPT_DIR}/../launchd/${PLIST_LABEL}.plist ${PLIST_PATH}"
  log "Then: launchctl bootstrap gui/\$(id -u) ${PLIST_PATH}"
  exit 0
fi

# Verify plist points at the daemon directory (not the old whatsapp-bridge/ path)
if grep -q "whatsapp-bridge-daemon" "${PLIST_PATH}"; then
  log "Plist correctly references whatsapp-bridge-daemon path"
else
  die "Plist does NOT reference whatsapp-bridge-daemon. Edit ${PLIST_PATH} and set ProgramArguments to: ${INSTALL_DIR}/${BINARY_NAME}"
fi

log "Restarting launchd service ${PLIST_LABEL}..."
launchctl bootout "gui/$(id -u)" "${PLIST_PATH}" 2>/dev/null || true
sleep 2
launchctl bootstrap "gui/$(id -u)" "${PLIST_PATH}" \
  || die "launchctl bootstrap failed"
log "Service restarted"

# ── 6. Health check ──────────────────────────────────────────────────────────
log "Waiting for /api/health (up to ${MAX_WAIT}s)..."
elapsed=0
while [ "${elapsed}" -lt "${MAX_WAIT}" ]; do
  if curl -sf "${HEALTH_URL}" > /tmp/wb-health.json 2>/dev/null; then
    status=$(python3 -c "import json,sys; d=json.load(open('/tmp/wb-health.json')); print(d.get('status','unknown'))" 2>/dev/null || echo "unknown")
    connected=$(python3 -c "import json,sys; d=json.load(open('/tmp/wb-health.json')); print(d.get('bridge_connected','?'))" 2>/dev/null || echo "?")
    log "Health: status=${status} bridge_connected=${connected}"
    if [ "${status}" = "healthy" ]; then
      log "Deploy complete. Bridge is healthy."
      cat /tmp/wb-health.json
      echo ""
      exit 0
    fi
  fi
  sleep 2
  elapsed=$((elapsed + 2))
done

die "Bridge did not become healthy within ${MAX_WAIT}s. Check logs: tail -f ~/Library/Logs/whatsapp-bridge.error.log"
