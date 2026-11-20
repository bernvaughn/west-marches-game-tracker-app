#!/usr/bin/env bash
# Pull the Droplet's nightly database backups to this machine.
#
# Runs on the owner's PC (inside WSL), not on the server.
# Copies new files only and never deletes anything on the server.
# Local copies older than KEEP_DAYS are removed (default 90), matching db-*.sqlite3 only.
#
# Needs a read-only SSH key. See docs/DEPLOY.md and the notes in the owner's setup steps.
set -euo pipefail

HOST="${DOWNTIME_HOST:-app.downtimemarket.com}"
REMOTE_USER="${DOWNTIME_BACKUP_USER:-deploy}"
KEY="${DOWNTIME_BACKUP_KEY:-$HOME/.ssh/downtime_backup_pull}"
DEST="${DOWNTIME_BACKUP_DEST:-/mnt/e/downtimemarket/backups}"
KEEP_DAYS="${DOWNTIME_BACKUP_KEEP_DAYS:-90}"

log() { printf '%s %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" "$*"; }

# Do not write into WSL's own disk if the E: drive is not mounted.
case "$DEST" in
  /mnt/?/*)
    mount_point="/mnt/$(printf '%s' "${DEST#/mnt/}" | cut -d/ -f1)"
    if ! findmnt -rn "$mount_point" >/dev/null 2>&1; then
      log "ERROR: $mount_point is not mounted. Nothing copied."
      exit 1
    fi
    ;;
esac

[ -r "$KEY" ] || { log "ERROR: key not found or unreadable: $KEY"; exit 1; }
mkdir -p "$DEST"

log "Pulling backups from $REMOTE_USER@$HOST to $DEST"
# The server side is locked to a read-only rsync of the backup folder (rrsync -ro),
# so the source path is the root of that folder.
rsync -a --partial \
  --include='db-*.sqlite3' --exclude='*' \
  -e "ssh -i $KEY -o IdentitiesOnly=yes -o StrictHostKeyChecking=yes -o ConnectTimeout=20" \
  "$REMOTE_USER@$HOST:/" "$DEST/"

newest="$(ls -1t "$DEST"/db-*.sqlite3 2>/dev/null | head -n1 || true)"
if [ -z "$newest" ]; then
  log "No backup files yet. The server has not made one."
  exit 0
fi

if command -v sqlite3 >/dev/null 2>&1; then
  result="$(sqlite3 "$newest" 'PRAGMA integrity_check;' 2>&1 || true)"
  if [ "$result" != "ok" ]; then
    log "ERROR: newest backup failed the integrity check: $newest ($result)"
    exit 1
  fi
fi

find "$DEST" -maxdepth 1 -type f -name 'db-*.sqlite3' -mtime +"$KEEP_DAYS" -delete

log "OK. Newest backup: $(basename "$newest")"
