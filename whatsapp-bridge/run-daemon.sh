#!/usr/bin/env bash
# run-daemon.sh - pid-tracking launcher for the whatsapp-bridge launchd job
#
# Root cause: whatsapp-bridge is a long-running (KeepAlive) daemon with no
# SIGHUP log-reopen support, so newsyslog cannot rotate its StandardOutPath
# by renaming alone - the process keeps its original file descriptor open
# and would keep appending to the renamed file forever, growing unbounded
# regardless of rotation. newsyslog's pid_file + signal mechanism needs a
# stable pidfile to send SIGTERM to, which launchd does not provide on its
# own. This wrapper writes its own PID (preserved across exec) to that
# pidfile immediately before exec'ing the real binary, so newsyslog can
# terminate it on rotation and let launchd's KeepAlive restart it with a
# fresh log handle. See PointyTooling issue #3127.
set -euo pipefail

INSTALL_DIR="${HOME}/Library/Application Support/whatsapp-bridge-daemon"
BINARY="${INSTALL_DIR}/whatsapp-bridge"
PID_FILE="${INSTALL_DIR}/whatsapp-bridge.pid"

echo $$ > "${PID_FILE}"
exec "${BINARY}"
