# Deploying Downtime Market

Plain-English runbook for the one-Droplet deployment at https://app.downtimemarket.com.
Every fenced block holds exactly one command. Copy and paste.

## 1. What runs where

Browser → Caddy (HTTPS, serves `/static/*` from disk) → gunicorn on `127.0.0.1:8000` → Django → one SQLite file in WAL mode.

```text
Browser
  |
  v
Caddy (HTTPS, static files from /srv/app/staticfiles)
  |
  v
gunicorn 127.0.0.1:8000
  |
  v
Django
  |
  v
SQLite (/var/lib/downtime/db.sqlite3, WAL mode)
```

The server already exists: Ubuntu 24.04, Caddy installed, a Linux user `deploy` who owns `/srv/app`, `/var/lib/downtime`, and `/var/backups/downtime`, and `/etc/downtime.env` holding the production settings. DNS is a Cloudflare A record for `app.downtimemarket.com`.

Deploy flow (4 lines):
1. Publish a GitHub release with a tag such as `v0.1.0`.
2. The workflow streams `deploy/deploy.sh` from that tag onto the Droplet over SSH.
3. The script backs up the database, checks out the tag, migrates, collects static files, restarts gunicorn, and polls `/healthz`.
4. If the health check fails, the script prints the previous tag; re-run the script with that tag to roll back.

## 2. One-time server setup

What already exists on the server (do not recreate it):
- Ubuntu 24.04 Droplet, UFW allows 22, 80, 443
- Caddy (official apt package), config at `/etc/caddy/Caddyfile`
- User `deploy` owning `/srv/app`, `/var/lib/downtime`, `/var/backups/downtime`
- `uv` at `/home/deploy/.local/bin/uv`; `sqlite3`, `git`, `curl`, `fail2ban` installed
- `/etc/downtime.env` (root:deploy, 640) with `DJANGO_SECRET_KEY`, `DJANGO_ALLOWED_HOSTS`, `DATABASE_PATH`, `RATELIMIT_TRUST_XFF`, `TIME_ZONE`

Do the setup in this order:
1. Run the first deploy (section 3, first command). It clones the repo into `/srv/app`, installs `/srv/app/.venv`, migrates, and collects static files.
2. That first deploy then fails at its "restart service" step, because the unit file is not installed yet. This is expected. The health check does not run.
3. Install the files below from `/srv/app/deploy/`. All paths are absolute, so the working directory does not matter.
4. Re-run the same deploy command. It now restarts the service, passes the health check, and records the tag.

`deploy` can only run `sudo systemctl restart downtime`. So run the install steps as the owner's admin account, with `sudo`.

Log in to the server as the admin account:
```bash
ssh <admin-user>@<host>
```

Install the unit file:
```bash
sudo cp /srv/app/deploy/downtime.service /etc/systemd/system/downtime.service
```
```bash
sudo systemctl daemon-reload
```
```bash
sudo systemctl enable --now downtime
```

Install the Caddyfile:
```bash
sudo cp /srv/app/deploy/Caddyfile /etc/caddy/Caddyfile
```
```bash
caddy validate --config /etc/caddy/Caddyfile
```
```bash
sudo systemctl reload caddy
```

Install the cron file and the backup log file:
```bash
sudo install -m 644 -o root -g root /srv/app/deploy/downtime-backup.cron /etc/cron.d/downtime-backup
```
```bash
sudo install -m 640 -o deploy -g deploy /dev/null /var/log/downtime-backup.log
```

Install the mail timer unit and timer:
```bash
sudo cp /srv/app/deploy/downtime-mail.service /etc/systemd/system/downtime-mail.service
```
```bash
sudo cp /srv/app/deploy/downtime-mail.timer /etc/systemd/system/downtime-mail.timer
```
```bash
sudo systemctl daemon-reload
```
```bash
sudo systemctl enable --now downtime-mail.timer
```

## 3. First deploy and first admin

Run this from your own clone of the repo, on your PC. It streams your local `deploy/deploy.sh` onto the Droplet and deploys tag `v0.1.0`:
```bash
ssh deploy@<host> 'bash -s -- v0.1.0' < deploy/deploy.sh
```

On the very first run this fails at the restart step. Install the files as section 2 says, then run the same command again.

Then create the first site admin. The app uses `email` as the username field, so `createsuperuser` asks for an email. Password must be 12+ chars with upper, lower, digit, and special character:
```bash
ssh deploy@<host>
```
```bash
cd /srv/app
```
```bash
set -a && . /etc/downtime.env && set +a
```
```bash
.venv/bin/python manage.py createsuperuser
```
```bash
exit
```

Log in to the site admin and use the "new club" form to create the first club; it seeds the XP table, options, items, starting equipment, and a General Store. The `seed_*` commands (`seed_starting_equipment`, `seed_pack_containers`, `seed_general_store`, each with `--club <slug>`) are for existing clubs only.

**Never run `seed_demo` in production.** It creates a known login (`admin@example.com` / `demo-password`) and a known agent token (`wm_demo_local_token_change_me`). It is for local use only and must never exist on a hosted site.

## 4. Release flow

Publish a GitHub release with a tag such as `v0.1.0`. The workflow `.github/workflows/deploy.yml` (owned by the owner) connects to the Droplet as `deploy` and runs the same command, streaming the release's own `deploy/deploy.sh`:

```bash
ssh deploy@<host> 'bash -s -- <tag>' < deploy/deploy.sh
```

The deploy writes the tag to `/srv/app/VERSION`, and the footer shows it after the service restarts.

Do not change the workflow internals here; that file is the owner's.

After deploying the stacked-ammunition release, run this once per existing club on the server (it is a dry run until you add `--apply`, and safe to run twice):
```bash
cd /srv/app && set -a && . /etc/downtime.env && set +a && .venv/bin/python manage.py convert_seeded_bundles --club <slug> --apply
```

After deploying the renamed-items release, run this once per existing club on the server (dry run first, then add `--apply` to write):
```bash
ssh dm "sudo -u deploy bash -c 'cd /srv/app && set -a && . /etc/downtime.env && set +a && .venv/bin/python manage.py rename_seeded_items --club <slug>'"
```

## 5. Rollback

Re-run the deploy command with the previous tag:

```bash
ssh deploy@<host> 'bash -s -- <previous-tag>' < deploy/deploy.sh
```

The previous tag is printed by a failed deploy, and it is also stored in `/var/lib/downtime/last-deployed-tag` before the next deploy.

Code rollback is safe only for migrations that add things (new tables, columns, or rows). For any other migration, restore the pre-deploy backup instead (section 6). The script takes a backup before every deploy, so that backup is the real safety net.

## 6. Backups and restore

`deploy/backup.sh` runs nightly at 03:15 UTC via cron and writes to `/var/backups/downtime/db-<UTC timestamp>.sqlite3`, mode 600, keeping 14 days. It uses SQLite's own `.backup` command (safe while the app writes) and checks each copy with `PRAGMA integrity_check`. Output goes to `/var/log/downtime-backup.log`.

To restore, use the owner's admin account. `deploy` cannot stop or start the service, and the backup files are mode 600. So every step uses `sudo`.

List the backups and pick one:
```bash
sudo ls -l /var/backups/downtime
```

Stop the service:
```bash
sudo systemctl stop downtime
```

Copy the backup over the database. Replace `<timestamp>` with the one you picked:
```bash
sudo cp /var/backups/downtime/db-<timestamp>.sqlite3 /var/lib/downtime/db.sqlite3
```

Give the file back to `deploy`:
```bash
sudo chown deploy:deploy /var/lib/downtime/db.sqlite3
```

Remove the old write-ahead files, which belong to the replaced database:
```bash
sudo rm -f /var/lib/downtime/db.sqlite3-wal /var/lib/downtime/db.sqlite3-shm
```

Start the service:
```bash
sudo systemctl start downtime
```

To test a restore without touching production, copy a backup to a scratch path and check it there.

Make the scratch copy:
```bash
sudo cp /var/backups/downtime/db-<timestamp>.sqlite3 /tmp/restore-test.sqlite3
```

Check that the file is sound. The output must be `ok`:
```bash
sudo sqlite3 /tmp/restore-test.sqlite3 "PRAGMA integrity_check;"
```

Check that it holds real data. The count must be more than zero:
```bash
sudo sqlite3 /tmp/restore-test.sqlite3 "SELECT count(*) FROM django_migrations;"
```

Delete the scratch copy:
```bash
sudo rm -f /tmp/restore-test.sqlite3
```

Never run the restore commands against the live `/var/lib/downtime/db.sqlite3` unless you intend to replace production data.

## 7. Offsite copy

The owner's PC pulls `/var/backups/downtime` with `rsync`, using a read-only SSH key. The script is `deploy/pull-backups.sh`, which runs inside WSL on the owner's PC; read its header comments for its settings.

## 8. Troubleshooting

```bash
journalctl -u downtime
```
```bash
journalctl -u downtime-mail
```
```bash
systemctl list-timers | grep downtime
```
```bash
systemctl status caddy
```
```bash
caddy validate --config /etc/caddy/Caddyfile
```
```bash
tail -n 50 /var/log/downtime-backup.log
```

- 400 Bad Request: `DJANGO_ALLOWED_HOSTS` does not match the host name (check `/etc/downtime.env`).
- Redirect loop: the proxy header is missing — Caddy must set `X-Forwarded-Proto: https` (Django trusts it and redirects plain HTTP to HTTPS).
- If gunicorn will not start, check `/etc/downtime.env` and `sudo systemctl status downtime`.
