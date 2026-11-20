#!/usr/bin/env bash
# Deploy a release tag of the downtime app.
#
# Usage:
#   bash deploy.sh <tag>
#   bash -s -- <tag> < deploy.sh   (script on stdin, e.g. streamed over SSH)
#
# Everything is an absolute path; the script does not use $0 or its own
# directory, so it works when streamed in on stdin.
#
set -euo pipefail

# Absolute constants.
APP_DIR=/srv/app
REPO_URL=https://github.com/bernvaughn/west-marches-game-tracker-app.git
ENV_FILE=/etc/downtime.env
STATE_FILE=/var/lib/downtime/last-deployed-tag
HEALTH_HOST=app.downtimemarket.com
UV=/home/deploy/.local/bin/uv
LOCK_FILE=/var/lib/downtime/deploy.lock

HEALTH_ATTEMPTS=15
HEALTH_SLEEP=2

usage() {
    echo "usage: bash deploy.sh <tag>" >&2
    echo "  or:  bash -s -- <tag> < deploy.sh" >&2
    echo "tag must match ^v[0-9][0-9A-Za-z._-]*$" >&2
}

# Validate the tag first, before the lock and before any state write, so a bad
# tag does nothing and touches nothing. The pattern is ^v[0-9][0-9A-Za-z._-]*$.
TAG="${1:-}"
if [ -z "$TAG" ]; then
    echo "error: missing tag argument" >&2
    usage
    exit 2
fi
TAG_RE='^v[0-9][0-9A-Za-z._-]*$'
if [[ ! $TAG =~ $TAG_RE ]]; then
    echo "error: invalid tag '$TAG'" >&2
    usage
    exit 2
fi

# Take a lock so two deploys cannot overlap. Fail fast (-n).
exec 9>"$LOCK_FILE"
if ! flock -n 9; then
    echo "error: another deploy is already running" >&2
    exit 1
fi

step() {
    echo "==> $*"
}

fail() {
    journalctl -u downtime -n 30 --no-pager </dev/null 2>/dev/null || true
    echo "Deploy of $TAG failed. Previous tag: ${PREV:-none}. To roll back run the deploy with that tag." >&2
    exit 1
}
trap fail ERR

# 1. Read the previous tag (may not exist).
step "read previous tag"
PREV=""
if [ -e "$STATE_FILE" ]; then
    PREV=$(cat "$STATE_FILE" 2>/dev/null || true)
fi
[ -n "$PREV" ] || PREV="none"
echo "previous tag: $PREV"

# 2. Clone the repo if it is not there yet.
step "clone repository"
if [ ! -d "$APP_DIR/.git" ]; then
    git clone "$REPO_URL" "$APP_DIR" </dev/null
fi

# 3. Back up the database before deploying. A failed backup stops the deploy.
step "backup database"
if [ ! -x "$APP_DIR/deploy/backup.sh" ]; then
    echo "skip: $APP_DIR/deploy/backup.sh is not executable; skipping backup"
else
    # Respect DATABASE_PATH from the env file for the backup target.
    if [ -e "$ENV_FILE" ]; then
        set -a
        # shellcheck source=/dev/null
        . "$ENV_FILE"
        set +a
        export DB_PATH="${DATABASE_PATH:-${DB_PATH:-/var/lib/downtime/db.sqlite3}}"
    fi
    "$APP_DIR/deploy/backup.sh" </dev/null
fi

# 4. Fetch tags and check out the requested tag.
step "fetch tags"
git -C "$APP_DIR" fetch --tags --force origin </dev/null

step "checkout tag"
if ! git -C "$APP_DIR" rev-parse -q --verify "refs/tags/$TAG^{commit}" >/dev/null 2>&1; then
    echo "error: Tag $TAG does not exist" >&2
    exit 1
fi
git -C "$APP_DIR" checkout --detach "refs/tags/$TAG" </dev/null

# 5. Install dependencies.
step "sync dependencies"
cd "$APP_DIR"
"$UV" sync --frozen --no-dev </dev/null

# 6. Migrate and collect static with the production environment loaded.
step "migrate and collect static"
if [ -e "$ENV_FILE" ]; then
    set -a
    # shellcheck source=/dev/null
    . "$ENV_FILE"
    set +a
fi
.venv/bin/python manage.py migrate --noinput </dev/null
.venv/bin/python manage.py collectstatic --noinput </dev/null

# 7. Restart the service.
step "restart service"
sudo systemctl restart downtime </dev/null

# 8. Poll the health check up to HEALTH_ATTEMPTS times, HEALTH_SLEEP seconds apart.
step "health check"
HEALTH_OK=0
attempt=0
while [ "$attempt" -lt "$HEALTH_ATTEMPTS" ]; do
    attempt=$((attempt + 1))
    body=$(curl -fsS --max-time 5 -H "Host: $HEALTH_HOST" -H "X-Forwarded-Proto: https" http://127.0.0.1:8000/healthz 2>/dev/null </dev/null || true)
    if [ "$body" = "ok" ]; then
        HEALTH_OK=1
        break
    fi
    sleep "$HEALTH_SLEEP"
done

if [ "$HEALTH_OK" != "1" ]; then
    fail
fi

# 9. Success: record the tag atomically and announce.
step "mark deployed"
tmp_state=$(mktemp "${STATE_FILE}.tmp.XXXXXX")
printf '%s' "$TAG" > "$tmp_state"
mv -f "$tmp_state" "$STATE_FILE"
echo "Deployed $TAG"
exit 0
