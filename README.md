# Downtime Market: Shopping List and Infrastructure Plan

Downtime Market is a game tracker for West Marches style D&D clubs.

Plan written 2026-11-09 and re-checked against the full scope on 2026-11-10. Prices come from DigitalOcean's own docs where noted and otherwise from third-party summaries; confirm them on the signup page.

Scope has since grown to eight Django apps (see [Django apps](#django-apps)), clubs, maps, quests, trades, printing, and a donate button. The cost and infrastructure sections below were re-checked against that scope; the plan still fits one $6 Droplet. The app sends no email (see [Sending email](#sending-email)). User stories are in [docs/USER_STORIES.md](docs/USER_STORIES.md), and a plain-language outline of the records is in [docs/DATA_MODEL.md](docs/DATA_MODEL.md).

## Run locally

```bash
uv sync
uv run python manage.py migrate
uv run python manage.py seed_demo
uv run python manage.py runserver
```

Static URLs carry `?v=<content hash>` automatically, so edited CSS and JS show up without a hard refresh. Runserver and the tests need no `collectstatic`; production runs it as usual.

Open http://127.0.0.1:8000/ and sign in with a demo login. The password for all of them is `demo-password`.

| Email | Role |
| --- | --- |
| `admin@example.com` | Site admin |
| `gm@example.com` | Club admin and game master |
| `alice@example.com` | Player (Aria Windrunner) |
| `bob@example.com` | Player (Borin Stonefist) |

Run the checks with `uv run pytest` and `uv run ruff check`.

The browser console guard is slow and needs Chromium, so `uv run pytest` skips it.
Run it with `uv run playwright install chromium` once, then `uv run pytest -m browser`.
For a list of problems per page, run `uv run python scripts/console_sweep.py`.
For the UI audit, `uv run python scripts/screenshots.py --audit --out <dir>` captures every page at 1920, 1280, 768 and 390 px (see the Method section of `docs/design/AUDIT-2.md`).

### Agent access

`seed_demo` also creates a local agent token and a pending batch, so you can try the MCP endpoint with the MCP Inspector:

1. Run `npx @modelcontextprotocol/inspector`.
2. Set the transport to **Streamable HTTP**.
3. Set the URL to `http://localhost:8000/mcp` and the connection type to **Via Proxy**.
4. Add the header `Authorization: Bearer wm_demo_local_token_change_me`.
5. Connect, then call the `whoami` tool.

The demo token is for local use only. It must never exist on a hosted site.

OAuth sign-in also works, with no secret to copy. In the Inspector pick **OAuth** and add no header. The Inspector finds the endpoints from `/.well-known/oauth-protected-resource/mcp`, registers itself, and sends you to the site. Sign in, pick one club where you are a game master, and approve. Access tokens last one hour and refresh on their own. Revoke the connection on the connections page and its tokens stop working.

## Summary

Run the app on one $6/month DigitalOcean Droplet with Django and SQLite; with backups the bill is about $7.20/month, and nothing in this plan scales on its own. The larger scope changes the bill little: storage and traffic stay tiny, and the one real gap is that DigitalOcean blocks outgoing email, so the app is designed to send no email.

The app lets game masters (GMs) assign money to player characters, and lets players spend it on shop items between sessions. The game master changes the shop's items and prices between sessions. When a limited-quantity item sells out, it disappears for every other player within a few seconds.

## What to buy

Buy one Basic Droplet with 1 GiB of RAM at $6/month, add backups if you want them, and a domain name (needed for agent access).

| Item | Cost | Needed? | Notes |
| --- | --- | --- | --- |
| DigitalOcean Droplet, Basic, 1 GiB RAM | $6/month | Yes | 1 vCPU, 25 GB SSD, about 1 TB of outbound transfer included ([plan list](https://www.temperstack.com/plans/digitalocean/)) |
| Automatic Droplet backups | about $1.20/month (20% of the Droplet price) | Optional | Weekly backups ([cost example](https://www.activepieces.com/blog/digitalocean-pricing-plans-and-real-costs-in-2026)) |
| Domain name | about $10-15/year | Yes, for agent access | Approximate, not looked up; lets Caddy get a free HTTPS certificate automatically, and agents need a public HTTPS address to connect |
| Email-sending service | $0 | No | The app sends no email for now; see [Sending email](#sending-email) |
| Django, SQLite, htmx, gunicorn, Caddy | $0 | Yes | All free, open-source software |

Total: $6/month for the server alone, or $7.20/month with backups, plus the domain. DigitalOcean's docs confirm weekly backups cost 20% of the Droplet price ([backups pricing](https://docs.digitalocean.com/products/backups/details/pricing/)). A $4 Droplet with 512 MiB RAM also exists ([price list](https://kuberns.com/blogs/digitalocean-pricing/)), but 1 GiB leaves room for gunicorn, Caddy, and the nightly backup running together, so this plan stays at $6.

Do not buy a managed database (about $15/month), a load balancer (from $12/month), or Spaces object storage (from $5/month); SQLite on the Droplet replaces all three ([add-on prices](https://diyai.io/ai-tools/hosting/digitalocean-pricing/)).

## Tentative architecture

The app is a plain Django site: game masters and players use server-rendered pages with small htmx fragments, and everything is stored in one SQLite file. The first diagram showed only the shop; the architecture is unchanged for the larger scope.

```mermaid
flowchart LR
    B["Browsers<br/>GM and players<br/>htmx, every 5s"] --> C
    subgraph D["One DigitalOcean Droplet, $6/month"]
        C["Caddy<br/>HTTPS certificates"] --> G["Django (gunicorn)<br/>all eight apps"] --> S[("SQLite<br/>one database file")]
    end
    S --> O["Offsite copy<br/>nightly backup of the file"]
```

Browsers talk only to Caddy; the one outbound copy is the nightly backup.

The records for every app are outlined in [docs/DATA_MODEL.md](docs/DATA_MODEL.md); the original sketch (character, item, transaction) has grown into clubs, catalogues, shops, a ledger, trades, quests, and maps.

How the larger scope fits this architecture:

- **Purchases and trades** stay single database transactions: check stock, holds, and balance, then write ledger rows. When two players click Buy on the last item together, the second gets an "already sold" message.
- **Live updates** use htmx polling, as before: a fragment the page re-requests every 5 seconds, skipped while the browser tab is hidden. Poll only the pages where freshness matters (shop stock, open trades); the map and character sheets can load once and refresh on demand.
- **Printing** (item cheat sheets, maps) uses ordinary web pages with a print stylesheet and the browser's own print dialog. Do not add server-side PDF generation; it needs more memory than this Droplet should spare.
- **The map** can grow forever, but only tiles with something on them are stored, so storage and rendering depend on what exists, not on how far the map extends. Show only the part of the map in view.
- **SQLite** should run in write-ahead mode so reads do not block the occasional write, which is fine at this scale: writes are short and come from a handful of people.

## Django apps

Planned split. Names are tentative; a Django app name must be a valid Python name, so `player-characters` becomes `player_characters`.

| App | What it holds |
| --- | --- |
| `accounts` | User accounts, each club's email whitelist, who holds which permission in which club, and messages to club admins (a separate messaging app may make sense later) |
| `player_characters` | The characters players play as (a player can have several; game masters can have them too): sheet details (ability scores, class, species), coins, owned items, and trades between characters |
| `items` | Each club's item catalogue: names, descriptions, traits and other details, and prices |
| `shops` | Named shops and shopkeepers, their rotating and fixed inventories (a stock amount of items from the club's catalogue), shop rotations (open and close dates only; inventory and stock stay with the shop), and buying and selling at percentages of an item's value, with per-item overrides |
| `ledger` | The history of every gain or loss of items or coins for a character, each with a note and a date |
| `map` | Basic hex maps with no art (a club can have several), drawn with plain colors and symbols; which players have visited which tiles; and encounters and locations on those tiles |
| `quests` | Small side quests, such as gathering items during a session and trading them in for a reward or more money |
| `agent_access` | An MCP endpoint so a game master's AI agent can propose awards from session notes, which the game master reviews and confirms on the site (the app is not named `mcp`, which would clash with the `mcp` Python package) |

All data belongs to a club (a group of people and their game data), and one club never sees another's. Stories exist for all eight apps. A site admin runs the whole site; inside a club, admin and game master are separate permissions that one account can hold together. Each club has its own item catalogue, so clubs can add their own homebrew items. The `items` app defines items; the `shops` app only holds inventories that point at a club's catalogue (a shop sees only its own club's items) and handles buying and selling. Loot and quests use the same catalogue. Coins are stored as copper and shown as copper, silver, gold, and platinum. The `ledger` app records every gain or loss of items or coins for a character with a note and a date, such as `traded to <character name>` or `awarded by <game master name>`.

Later: a `lore` app is out of scope for now. The world notes in the [dnd-world-keeper](https://github.com/bernvaughn/dnd-world-keeper) repo should eventually live in this app instead of that separate repo.

## Sizing check

Rough estimates for the full scope, not measurements. Nothing has been load-tested.

- **People.** Assume up to 50 people logged in at once, far more than a few game tables.
- **Traffic.** If every one of them polled the shop every 5 seconds around the clock, with a 5 KB fragment each time (an assumed size), that is about 130 GB of outbound transfer a month, around 13% of the 1 TB included. Real use, with hidden tabs skipped and sessions of a few hours, will be a small fraction of that.
- **Server load.** Those 50 people make at most about 10 requests per second. One vCPU running a few gunicorn workers should handle that when each request takes tens of milliseconds, which a small query against SQLite normally does.
- **Storage.** A ledger row is a few hundred bytes. Even 100,000 rows is tens of megabytes against the 25 GB disk, and the database file stays small enough to copy offsite nightly in seconds.
- **Backups.** Weekly Droplet backups are billed by Droplet price, not data size, so they stay at about $1.20/month.

When to look again: many clubs at once (hundreds of regular users), long-lived live updates for everyone, or a feature that serves files or images. Any of those may call for the $12 Droplet, still a fixed price.

## Sending email

DigitalOcean blocks outgoing mail on ports 25, 465, and 587 on all Droplets and recommends a third-party email service ([DigitalOcean docs](https://docs.digitalocean.com/support/why-is-smtp-blocked/)); the account's support replies say the block can't be lifted. Some providers offer another port, such as 2525, or an HTTPS API, which are not blocked ([Ghost's guide](https://docs.ghost.org/faq/digitalocean-smtp-blocked)).

**Decision: no email for now.** Club admins create accounts and hand out one-time temporary passwords; people choose their own on first sign-in; club admins reset passwords for players and game masters whose clubs they all administer; the site admin can reset anyone's (stories U20-U22). The app sends no email, so no email provider is needed. If email is wanted later (sign-in links, notifications), use a transactional provider through its HTTPS API or port 2525, with a domain for sender verification; free tiers exist at some providers but I did not check any.

Do not run your own mail server on the Droplet.

## Agent access (MCP)

Decided in outline: propose-then-confirm for everything in the first version, with map updates from notes coming soon. Stories A1 to A7 are in [docs/USER_STORIES.md](docs/USER_STORIES.md).

MCP is an open standard that lets an AI agent call named actions ("tools") on another program. The app would serve an MCP endpoint over HTTPS, and a game master's agent would connect to it with a personal token, look up characters and catalogue items, and propose a batch of awards from session notes. The game master confirms the batch on the site before anything is applied.

- **Fits the plan.** A Django library, `django-mcp-server`, serves an MCP endpoint inside an existing Django app on WSGI or ASGI and supports token authentication ([PyPI](https://pypi.org/project/django-mcp-server/)). No new server or paid service is needed. Each agent call is an ordinary short request, so the sizing in [Sizing check](#sizing-check) still holds. Avoid long-lived streaming connections, which would tie up gunicorn workers on one small CPU.
- **Spec moves quickly.** The MCP specification is dated and changes between revisions; the 2025-03-26 revision added OAuth 2.1 authorization and Streamable HTTP, and a later revision reportedly removed protocol sessions ([summary](https://www.getmaxim.ai/topics/mcp-gateway/mcp-specification)). Choose a library that tracks the current revision, and re-check before building.
- **Which agents.** Some game masters use Claude and some use Meta's Muse. Claude connects to a remote MCP server by URL as a custom connector, from Anthropic's cloud, and Claude's docs describe both OAuth sign-in and fixed request headers such as a bearer token, though one of Claude's own pages lists fixed headers as beta ([Claude custom connectors](https://claude.com/docs/connectors/custom), [Claude authentication](https://claude.com/docs/connectors/building/authentication)). Muse is less clear: Meta's documentation does not mention MCP in the consumer app, while several third-party guides show a remote server added as a custom connector over Streamable HTTP with OAuth sign-in, and Meta's coding agent supports MCP directly ([guide](https://anythingmcp.com/guides/clients/muse), [Meta Muse MCP summary](https://www.aiagentslibrary.com/blog/meta-muse-connectors/)). Treat Muse support as unconfirmed until tested with a real account.
- **Authentication.** Both can use OAuth sign-in, so the plan is OAuth with the game master's own app account as the sign-in step: they log in, pick a club, and approve. A fixed token is a fallback for agent software that cannot sign in. The Django pieces for OAuth with MCP's discovery rules have not been checked, so verify this before building.
- **A domain is now required.** Claude and Muse call the server from their own clouds, so the app needs a public HTTPS address ([Claude custom connectors](https://claude.com/docs/connectors/custom)). A bare IP address is not enough in practice; buy a domain.
- **Safety.** The agent only proposes; the game master confirms; the ledger stays append-only. The agent has the connecting game master's permissions in one club, cannot see player emails or messages, and its tool results are treated as data. Session notes and character text can contain instructions, and the confirm step is what keeps a stray instruction from changing anyone's coins.

## Cost control

The monthly bill stays at the Droplet price plus backups unless you add resources or send more than the included outbound transfer. This is a pricing structure, not a hard stop: your card stays on file, so a billing alert is the safety net.

- Droplets are billed per second but never above the monthly price ([DigitalOcean pricing summary](https://www.usagepricing.com/blueprint/digitalocean)).
- The only usage-based charge on a plain Droplet is outbound transfer beyond the allowance, at $0.01 per GiB; inbound transfer is free, and 1,000 GiB of overage would cost $10 ([DigitalOcean community](https://www.digitalocean.com/community/questions/how-is-an-account-billed-if-it-goes-over-its-monthly-bandwidth-limit)). A text-only app for a game table should stay far below the roughly 1 TB included (see [Sizing check](#sizing-check)).
- Things that would add cost: extra Droplets, snapshots ($0.06 per GB per month), block storage volumes (from $10/month), and managed databases ([add-on prices](https://diyai.io/ai-tools/hosting/digitalocean-pricing/)).
- Safeguards: run exactly one Droplet, delete any snapshots you create, set an email billing alert in DigitalOcean's billing settings (confirm the exact option there), and glance at the invoice monthly.

## Risks and mitigations

The realistic risk is a lockout or a lost server, not a surprise bill, and an offsite copy of the database covers both.

| Risk | What happens | Mitigation |
| --- | --- | --- |
| Account lockout | DigitalOcean's automated checks sometimes lock accounts; one customer's services were shut down for about 24 hours in April 2026 ([community post](https://www.digitalocean.com/community/questions/two-unexplained-account-suspensions-missing-tickets-downgraded-support-plan-and-zero-accountability-digitalocean-we-need-to-talk)), and DigitalOcean has acknowledged an anti-fraud false positive ([incident update](https://www.plushcap.com/content/digitalocean/blog/an-update-on-last-weeks-customer-shutdown-incident)) | Complete any verification right away, pay invoices on time, and open a support ticket the moment a lock appears |
| Data loss | The whole app lives in one SQLite file on one disk | Copy the database every night using SQLite's own backup command (not a plain file copy while the app is writing) to somewhere outside DigitalOcean, such as your own computer or a free cloud storage account; keep the weekly Droplet backup too |
| Downtime | One server means updates and reboots are yours to handle | Players spend money between sessions, so short outages are tolerable; tell the group where to ask if the site is down |
| Locked-out people | With no email, forgotten passwords cannot be reset by the person | Club admins reset their members' passwords (when they administer all of that person's clubs); the site admin handles the rest (see [Sending email](#sending-email)) |

## Setup checklist and open questions

- [ ] Create a DigitalOcean account, finish any verification, and add a payment method
- [ ] Set an email billing alert
- [ ] Create one Basic Droplet (1 GiB RAM) in the region nearest your players, and turn on backups if you want them
- [ ] Buy a domain and point it at the Droplet (required for agent access)
- [ ] Install Python, Caddy and the app; run Django under gunicorn behind Caddy
- [ ] Set up the nightly offsite copy of the SQLite file and test restoring it once
- [ ] Create the first club, add its game masters and players to the email whitelist, and add the first campaign's characters

Open questions:

- How many clubs and regular players will use the app? Hundreds of regular users, rather than a few tables, would justify another look at sizing.
- Which domain name should the app use? A domain is needed for agent access.
