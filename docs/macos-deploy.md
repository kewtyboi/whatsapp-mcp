# macOS Deployment Guide

## Quick start

```bash
cd whatsapp-bridge
chmod +x deploy-mac.sh
./deploy-mac.sh
```

The script builds the binary, applies an ad-hoc code signature, installs it, restarts the launchd service, and verifies `/api/health` returns `status: healthy`.

## Prerequisites

- Go toolchain installed (`go build` works)
- Plist installed at `~/Library/LaunchAgents/com.liam.whatsapp-bridge.plist`
  (copy from `launchd/com.liam.whatsapp-bridge.plist` in this repo)
- WhatsApp session already paired (the script does not pair a new session)

## Install plist on a new machine

```bash
cp launchd/com.liam.whatsapp-bridge.plist ~/Library/LaunchAgents/
launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.liam.whatsapp-bridge.plist
```

---

## macOS SIGKILL gotcha (AMFI / WhatsApp sandbox)

### Symptom

The binary is immediately killed (exit code 137 / SIGKILL) when executed from
`~/Library/Application Support/whatsapp-bridge/` — even though the identical
binary runs fine from the dev directory, `/tmp`, or any other path.

### Root cause

The WhatsApp Mac App Store app (`net.whatsapp.WhatsApp`) applies a sandbox policy
that monitors `~/Library/Application Support/whatsapp-bridge/`. Any binary executed
from that exact directory path receives SIGKILL instantly via the macOS sandbox
framework, regardless of code signature, quarantine xattr, or Gatekeeper status.

This is anti-automation protection by the WhatsApp macOS app — it assumes any binary
running from "its" App Support subdirectory is attempting impersonation or process
injection.

**Key evidence:**

```
# SIGKILL from App Support path — always dies:
~/Library/Application Support/whatsapp-bridge/whatsapp-bridge  # exit 137
spctl -a -t execute "~/Library/Application Support/whatsapp-bridge/whatsapp-bridge"
# → rejected (even though the dev binary is also "rejected" yet runs fine)

# Runs fine from any other path:
~/Library/Application Support/whatsapp-bridge-daemon/whatsapp-bridge  # OK
~/dev/whatsapp-mcp/whatsapp-bridge/whatsapp-bridge                     # OK
/tmp/whatsapp-bridge-test                                               # OK
```

The `com.apple.provenance` xattr on the directory cannot be removed permanently —
macOS re-applies it. The ACL `group:everyone deny delete` on the directory is a
side-effect, not the cause.

### Fix

Use a **different directory name** — `whatsapp-bridge-daemon` instead of
`whatsapp-bridge`. The sandbox policy is keyed to the directory name.

The canonical install path is:
```
~/Library/Application Support/whatsapp-bridge-daemon/whatsapp-bridge
```

### What does NOT fix it

| Attempted fix | Result |
|---|---|
| `xattr -dr com.apple.quarantine <binary>` | xattr reapplied; still killed |
| `xattr -d com.apple.provenance <directory>` | xattr reapplied; still killed |
| `codesign -s - --force --deep <binary>` | Signature valid; still killed |
| Moving to `~/Applications/` | Runs fine |
| Moving to `/tmp/` | Runs fine |
| Different directory name in same App Support | Runs fine |

### Session data location

The WhatsApp session database (`store.db`) and key material live in the
`WorkingDirectory` set in the plist — currently the dev checkout path. The binary
and the session data are separate: the binary lives in the daemon install dir,
the data stays in the working directory.

If you move the session data, update `WorkingDirectory` in the plist accordingly.

---

## Manual rebuild steps

If you prefer not to use `deploy-mac.sh`:

```bash
# 1. Build
cd whatsapp-bridge
go build -o /tmp/whatsapp-bridge-new .

# 2. Clear quarantine + ad-hoc sign
xattr -cr /tmp/whatsapp-bridge-new
codesign -s - --force --deep /tmp/whatsapp-bridge-new

# 3. Install
mkdir -p ~/Library/Application\ Support/whatsapp-bridge-daemon/
cp /tmp/whatsapp-bridge-new ~/Library/Application\ Support/whatsapp-bridge-daemon/whatsapp-bridge
codesign -s - --force --deep ~/Library/Application\ Support/whatsapp-bridge-daemon/whatsapp-bridge

# 4. Restart launchd
PLIST=~/Library/LaunchAgents/com.liam.whatsapp-bridge.plist
launchctl bootout gui/$(id -u) "$PLIST"
sleep 2
launchctl bootstrap gui/$(id -u) "$PLIST"

# 5. Verify
sleep 5
curl -s http://localhost:8080/api/health
```

## Logs

```bash
# Live stdout
tail -f ~/Library/Logs/whatsapp-bridge.log

# Errors
tail -f ~/Library/Logs/whatsapp-bridge.error.log
```
