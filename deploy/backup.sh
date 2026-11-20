#!/usr/bin/env bash
# Back up the downtime SQLite database with SQLite's own .backup command.
#
# Settings come from the environment with these defaults:
#   DB_PATH    source database file   (default: /var/lib/downtime/db.sqlite3)
#   BACKUP_DIR folder for backup copies (default: /var/backups/downtime)
#   KEEP_DAYS  days to keep backups   (default: 14)
#
set -euo pipefail

DB_PATH="${DB_PATH:-/var/lib/downtime/db.sqlite3}"
BACKUP_DIR="${BACKUP_DIR:-/var/backups/downtime}"
KEEP_DAYS="${KEEP_DAYS:-14}"

# The sqlite `.backup '$tmp'` command quotes the destination with single quotes,
# so a single quote anywhere in BACKUP_DIR would break it.
case "$BACKUP_DIR" in
    *\'*)
        echo "error: BACKUP_DIR '$BACKUP_DIR' contains a single quote; refusing to back up" >&2
        exit 1
        ;;
esac

# KEEP_DAYS must be a non-negative integer.
case "$KEEP_DAYS" in
    ''|*[!0-9]*)
        echo "error: KEEP_DAYS must be a non-negative integer, got '$KEEP_DAYS'" >&2
        exit 1
        ;;
esac

# First deploy: there is no database yet. Nothing to back up, and we must not
# even create BACKUP_DIR here.
if [ ! -e "$DB_PATH" ]; then
    echo "no database yet, nothing to back up"
    exit 0
fi

mkdir -p "$BACKUP_DIR"

# Temp file in BACKUP_DIR. Its name does NOT match db-*.sqlite3, so pruning and
# a crashed run never confuse it with a real backup.
tmp=$(mktemp "$BACKUP_DIR/.db-tmp.XXXXXX")
rm -f "$tmp"
trap 'rm -f "$tmp"' EXIT

# Copy with SQLite's own backup command (safe while the app writes).
if ! sqlite3 "$DB_PATH" ".backup '$tmp'" >/dev/null 2>&1; then
    echo "error: sqlite backup of '$DB_PATH' failed" >&2
    exit 1
fi

# Verify the copy.
check=$(sqlite3 "$tmp" "PRAGMA integrity_check;" 2>/dev/null || true)
if [ "$check" != "ok" ]; then
    echo "error: integrity check on '$tmp' failed: $check" >&2
    exit 1
fi

# Publish the backup atomically and restrict it to the deploy user.
final="$BACKUP_DIR/db-$(date -u +%Y%m%dT%H%M%SZ).sqlite3"
chmod 600 "$tmp"
mv -f "$tmp" "$final"
trap - EXIT

# Prune only backups that match the pattern, and only after this backup succeeded.
find "$BACKUP_DIR" -maxdepth 1 -type f -name 'db-*.sqlite3' -mtime +"$KEEP_DAYS" -delete

echo "$final"
