# User Stories (draft 2)

Your stories come first, as you wrote them, with small edits: "gm" is spelled "game master", a few awkward phrases are smoothed, and each story is tagged with the Django apps it touches. Stories from the first draft that still apply follow after them. No code is implied by anything here.

Roles and permissions:

- **Site admin**: runs the whole site (you). Sees every club and sets up the donate button.
- Inside each club, **admin** and **game master (GM)** are two separate permissions on an account. A club's admins are expected to be the same people as its game masters, but one account can hold either permission or both.
  - **Club admin**: manages the club's email whitelist, shops, items, and content.
  - **Game master (GM)**: runs a game; awards loot and keeps track of what players use up.
- **Player**: owns one or more characters and spends their coins. Anyone in a club without those permissions is a player. Game masters can also own characters and play as players when they are not running a session. A person can have characters in more than one club, but a character never moves between clubs.

In the stories below, "admin" means a club admin, except U11 (donate button) and C7 and C8 (backup and cost), which are the site admin's.

A **club** is a group of people and its data (players, characters, shops, items). Data in one club is never visible to another.

Apps (names tentative; see the README): `accounts`, `player_characters`, `items`, `shops`, `ledger`, `map`, `quests`, `agent_access`. Lore is out of scope for now (see Later).

## Stories

**U1 Whitelist emails.** As an admin, I want to whitelist email addresses to be used for accounts, and assign those email addresses to player characters for the players to access. *(accounts, player_characters)*
- The whitelist belongs to a club; the same email can be whitelisted in more than one club.
- Whitelisting an email creates the account and shows the admin a temporary password to pass on (U20). If that email already has an account, from another club, it only adds the person to this club.

**U2 Log in and keep notes.** As a player, I want to be able to log in and add details to my character, so I can keep notes and stats and etc. *(accounts, player_characters)*

**U20 Create accounts without email.** As an admin, I want to create accounts for my club's players and game masters myself and hand them a temporary password, so the app never has to send email. On first sign-in the person must choose their own password. The temporary password is shown once. *(accounts)*

**U21 Reset passwords.** As an admin, I want to reset the password of a player or game master in my club, which gives them a new temporary password to choose a new one from and signs them out everywhere, so people who forget a password are not locked out. Because a password belongs to the person's account, I can do this only if I am an admin of every club they belong to; otherwise the site admin does it. The site admin can reset any account, including a club admin's. *(accounts)*

**U22 Change my password.** As a player, I want to change my own password while signed in. *(accounts)*

**U3 Loot.** As a player, I want my game master to award me loot (coins, items) that I can sell and buy with to available shops. *(player_characters, shops)*

**U4 Fresh shops.** As an admin, I want to change up the shops and items available between sessions, so players have fresh things to buy. *(shops, items)*

**U5 Always-open shops.** As an admin, I want there to be some shops that carry fixed generally-available inventory like torches and ropes that players can have available to buy. These are shops in a rotation with no close date. *(shops)*

**U6 Printable items.** As a player, I want to be able to print out items that I purchased so I have a reference while actually playing. *(player_characters, items)*
- A printout shows each item's name, description, traits, and other details. It is a cheat sheet for using the item in play, not a record of who owns it.

**U7 Consume items.** As a game master, I want to be able to mark players' items as consumed or spent, if they spend or use something in game (potion or coins, etc). *(player_characters)*

**U8 Coin denominations.** As a player, I want to have different denominations of coins, but have it auto-exchange when buying things so I can see my coins split out but do not need to suffer when buying. *(player_characters, shops)*
- The denominations are copper, silver, gold, and platinum, and amounts are stored in copper.
- The rates are 10 copper = 1 silver, 10 silver = 1 gold, 10 gold = 1 platinum.
- How amounts are shown follows U32: no platinum under 10,000 gp, and colour-coded denominations (U31).

**U9 Unlimited or limited stock.** As an admin, I want some items to be unlimited and some to have limited quantities at a given shop, so players can or cannot buy as many as they want. *(shops)*

**U10 Fun shops.** As an admin, I want to have a fun interface with rotating memorable shops, selling mixes of useful and not-useful items, because I want this app to be entertaining to players to entice them to use it more. *(shops)*

**U11 Donate.** As an admin, I want to set up a donate button to help me pay for all this. *(site-wide)*

**U12 Clubs.** As an admin, I want data segregated between groups (I like the term "club") so I can eventually have other people use this app too, or I could have multiple "club"s going at once, and keep the players and items and etc separated between the clubs. *(all apps)*

**U13 Ask for a fix.** As a player, I want to be able to message the club admins to manually evaluate and give me items, so if I remember something my character gathered but the game master forgot to add to my online inventory, a club admin can fix it. *(accounts, player_characters, items)*
- Messages are mostly free text, and are about the sender's selected character (U24, U27).

**U14 Manual adjustments.** As a club admin or game master, I want to be able to give and take items and money to and from players, so I can manually adjust their loot as needed. I need to be able to tag the give and take actions with notes and dates. *(player_characters, items)*
- Adjustments are recorded as new entries with a note and a date; earlier entries are never edited or deleted.
- The date defaults to the current date and can be changed to any date.

**U15 Move items between my characters.** As a player, I want to be able to send items from one character to another, if both characters are mine, so I can transfer items between my characters. This stays within the same club. *(player_characters, items)*

**U16 Trades.** As a player, I want to be able to propose trades to other players' characters (within the same club), so we can exchange items easily. *(player_characters, items, shops)*

How a trade works:
1. Player 1, on character 1a, sends a trade request to character 2a, which is owned by player 2.
2. The request lists the items player 1 is offering and a note, such as "can you give me your cool axe for these?". Coins are allowed as part of the trade too.
3. Player 2 sees the request, accepts it, adds the items (and any coins) they will give, and approves it.
4. Either player may change their own side of the trade after the request is accepted and before they approve. Whenever items or coins are added or removed, all approvals are cleared.
5. Player 1 approves. Once both approvals are on the trade, the items and coins transfer between the characters.

Rules:
- Items in an open trade or trade request are locked: they cannot be sold, transferred to another character, turned in to a quest, or marked consumed.
- Coins offered in an open trade or trade request are held aside and cannot be spent in a shop.
- Either player can decline or cancel the trade at any time.
- A character that sends trade requests can have only one accepted trade at a time. The limit starts once a request is accepted and applies to the sending player's character.
- Players cannot see the inventories of characters they do not own; they see only what is in the trade.
- A trade stays open until someone cancels or declines it; it does not expire.
- Items and coins held for one trade request cannot be offered in another request at the same time.
- Both characters must be in the same club.

**U17 Private email.** As a player, I want my email address to only be visible to club admins, so other players cannot contact me via email without my permission. *(accounts)*

**U18 Hand over a character.** As a club admin, I want to transfer a character from one player to another, if needed, for example when a character turned evil and was handed over to the game master. *(player_characters)*
- Game masters can own characters too, so a character can be handed to a game master.
- A character stays in its club; it cannot move to another club.

**U19 Private inventories.** As a player, I want only the game masters, the club admins, and me to be able to see my characters' inventories, so other players cannot see what my characters are carrying. *(player_characters)*

## Look and navigation: stories from the first look (2026-11-11)

From the first run of a local build. M8, M12, M15 and M16 in the map section also came from it.

**U23 A finished look.** As anyone using the app, I want every page, starting with the sign-in page, to use one consistent, compact look based on the Bootswatch Journal theme for Bootstrap 5, so the app feels finished and does not waste screen space. *(site-wide)*
- The sign-in, first-password, and password-change pages are styled like the rest of the site.
- Pages are denser: less empty space, and tables and lists that fit more on screen, while staying usable on a phone.
- The theme is Bootswatch Journal (MIT license), chosen for its serif, storybook feel. Its files are served from the app itself so pages do not depend on a third-party site.
- Journal is roomier than admin themes, so dense pages (inventories, ledgers, shop stock, approval lists) use Bootstrap's compact table and form sizes to keep them tight.

**U24 Act as a character.** As a player, I want to pick one of my characters to act as from a dropdown in the top bar, so shops, buying and selling, trades, moving items, quests, and requests use that character without me choosing it on every page. *(player_characters, accounts, shops, quests, map)*
- The dropdown appears only if I have more than one character in the current club. With one character, that character is always selected. With none, the top bar says so and pages that need a character tell me I don't have one.
- My selection is remembered per club across pages and sign-ins, and switching clubs switches to my selection for that club.
- Pages that act as one of my characters always use the selected one, with no character field of their own: buying, selling, proposing and answering trades, quest turn-ins, and messages to the admins (U13). To act as another character, I switch it in the top bar (round 2, U27).
- Where a page involves a second character of mine (moving items, U15), the selected character is the "from" side and I pick the other.
- Pages where I can pick several characters keep their picker and start with the selected character: the map (M8) and map requests (M12).
- If my selected character is handed to someone else (U18), my selection falls back to another of my characters.
- Game masters and club admins who own characters get the same dropdown. Selecting a character never limits their game master or club admin views.

**U25 Who I am.** As anyone signed in, I want the top bar to show my name and, if I have one, the character I am acting as (U24), so I always know who I am acting as. *(accounts, player_characters)*

**U26 Approvals waiting.** As a game master or club admin, I want an indicator in the top bar showing how many things in the current club are waiting for me to act on, so I notice them without checking each page. *(accounts, agent_access, map, items)*
- It counts what I am allowed to act on: proposed agent batches (A4), proposed catalogue items (A5), map requests for visits and discovered or explored credit (M12), and, for club admins, open messages (U13).
- Clicking it lists each waiting thing, grouped by kind, with a link to where I approve, decline, or handle it.
- The count disappears when nothing is waiting. Players never see it.
- It updates when I load a page; it does not need to be live.

## Round 2: stories from the second look (2026-11-11)

From using the build after the first-look stories landed.

**U27 One character everywhere.** As a player, I want every page that acts as one of my characters to use the character in the top bar, with no character choice of its own, so I never act as the wrong character by mistake. *(shops, player_characters, quests, accounts)*
- This replaces the per-page character field that U24 first kept. It covers selling to a shop, buying, trades, quest turn-ins, and messages to the admins.
- Each of these pages names the character it is acting as, near the top or on the action button, for example "Sell as Aria Windrunner".
- Pages where I can pick several characters keep their picker, starting with the selected character: the map (M8) and map requests (M12).
- Game master and club admin pages that act on other people's characters (awards, adjustments, visits, credit, found marks) keep their character pickers. The top bar never limits them.

**U28 Club cards.** As anyone signed in, I want the "Your clubs" page to show each club as a card with useful details, so it is inviting and I can see at a glance what each club is. *(accounts, player_characters)*
- Each card shows the club name, my role there (player, game master, club admin), the game masters' names, the number of players, and my characters in that club.
- The whole card links to the club. Cards sit in a grid that becomes one column on a phone.
- A card shows only what any member of that club may see: no emails and no inventories.

**U29 Grouped navigation.** As anyone in a club, I want the navigation under the top bar grouped into a few menus, with the pages players use most kept as plain links, so I can find things without scanning a long row of links. *(site-wide)*
- Plain links: Character, Shops, and Quests.
- "More" menu for everyone: Map, Trades, Ledger, and Message the admins.
- "Game master" menu, for game masters and club admins: awards and adjustments, map editing, map requests, agent batches, proposed items, and agent connections.
- "Club admin" menu, for club admins only: members, inbox, item catalogue, shops and stock, rotations, and the XP table.
- A menu shows only the links the person may use, and a menu with no links is hidden.

**U30 Handle requests from the inbox.** As a club admin, I want to grant items, coins, and map credit from a modal on the inbox, so I can handle a player's request without leaving the inbox. *(accounts, player_characters, ledger, map)*
- Each message has a "Grant" button that opens a modal for the message's character. I can pick a different character in the same club.
- The modal can give coins, give items from the catalogue with a quantity, and record a visit, discovered credit, explored credit, or a found mark on a location.
- Grants go through the same rules and ledger as manual adjustments (U14) and map credit (M14, M16). Each has a note, which starts as a reference to the message, and a date, which starts as today.
- After granting, I can mark the message handled in the same step. The message shows what was granted from it.
- The inbox stays for club admins only (U13). Game masters keep using the award and map pages.

**U31 Colour-coded coins.** As anyone, I want each coin denomination shown in its own colour everywhere amounts appear, so I can read amounts at a glance. *(site-wide)*
- Copper is copper-brown, silver is grey, gold is gold, and platinum is a pale blue-white. Each colour has enough contrast to read on the theme background.
- The denomination label (cp, sp, gp, pp) always stays next to the number, so colour is never the only cue.
- The colours apply to balances, prices, values, sell offers, the ledger, trades, quest rewards, agent batches, and coin inputs. Printouts can stay black and white.

**U32 Gold first.** As a player, I want amounts shown in gold up to 9,999 gp, and mostly in platinum above that, because that is how my table talks about money. *(site-wide)*
- Under 10,000 gp in total, no platinum is shown, for example "9,999 gp 5 sp".
- From 10,000 gp up, the whole amount uses the normal split, for example "1,000 pp" for 10,000 gp and "1,234 pp 5 gp 6 sp" for 12,345 gp 6 sp.
- The rates do not change (1 pp = 10 gp), amounts stay stored in copper (U8), and copper and silver show as usual.
- The rule applies to every amount the app shows: balances, item values, shop prices, sell offers, the ledger, trades, quest rewards, and agent batches.

**U33 Buy with a confirm modal.** As a player, I want the Buy button to open a confirm modal instead of a new page, so buying is quick. *(shops)*
- The modal shows the item, the price, the quantity, the character buying (U27), and that character's coins before and after.
- Confirming buys the item and updates the shop page in place. "Already sold" (C3) and "can't afford" (C2) messages show in the modal.
- Without JavaScript, the Buy button still works through the buy page.

**U34 Top bar on narrow screens.** As anyone on a phone or narrow window, I want the club name, my name, my selected character, the approvals indicator, and log out to stay visible at every width, so I always know where I am and who I am acting as. *(site-wide)*
- Only the navigation links and menus (U29) collapse into the hamburger menu.
- On very narrow screens, the always-visible items may shrink (for example, initials or icons with labels for screen readers), but they never move into the hamburger menu.

**U35 A nicer-looking app.** As anyone using the app, I want every page to look polished and consistent, so the app is pleasant to use. I am not a designer; I want it to look nice. *(site-wide)*
- Every page uses the same building blocks: a page header with the title and main action, cards for grouped details, compact tables for lists, badges for statuses, clear empty states, and consistent spacing and buttons.
- The agent batch review page (A4) gets a cleanup first: one card per batch with its status and source notes, a clear table of lines, and the edit, confirm, and reverse actions grouped.
- A component reference page, visible only to the site admin, shows every building block, so new pages stay consistent.
- Each change is checked by screenshots of the pages at desktop and phone width, attached to the work for review.

**M17 Tile details in a modal.** As anyone looking at a map, I want clicking a tile to open its details in a modal over the map, instead of a new page, so I keep my place on the map. *(map)*
- The modal shows what the tile page shows today, with the same visibility rules (M16) and the same actions (requests, and game master editing links).
- The tile page keeps working at its own address, for links, printing, and use without JavaScript.
- Closing the modal returns to the same map position and character filter.

## Quests

**Q1 Item quests.** As a club admin, I want to make quests where players can turn in items to get rewards, so we can inspire players to collect interesting items. *(quests, items, player_characters)*
- Players turn items in themselves; no admin has to approve it.
- Turned-in items can be used up, and the player specifies a quantity.
- Only items can be turned in, not coins; coins are for buying things.
- Rewards can be coins, items, or both.

**Q2 Effective dates.** As a club admin, I want effective dates for quests, so some quests will time out without being completed. *(quests)*
- A quest has a start date and an end date, so quests can be made before they go live.

**Q3 Completion limits.** As a club admin, I want to set limits on how many total times a quest can be completed at the club level and how many times a single character can complete it. *(quests)*

**Q4 Quests per club.** As a site admin, I want quests to be defined at the club level, so different clubs' quests do not bleed into each other. *(quests)*

## Shops: stories from your answers

**S1 Shop pricing.** As a club admin, I want each item to have a value, and each shop to have a default sell percentage (what players pay) and a separate default buy percentage (what the shop pays players) of that value, which I can override item by item within a shop, so that a shop can sell most items at 100% of their value but sell rope at 50%. *(shops, items)*
- Players can sell items to a shop at that shop's buy percentage of the item's value, unless the item has an override in that shop.
- An override applies only within the shop it is set in.

**S2 Shop rotations.** As a club admin, I want shop rotations with start and end dates, where a shop can appear in more than one rotation, so that I can set rotations up before they go live. *(shops)*
- A rotation only sets when its shops open and close.
- A shop's inventory is an ongoing list that carries over between rotations, and stock quantities are kept per shop, not per rotation.

## Carried over from the first draft

These still apply and are not covered above. Keep, change, or drop them. C6 (correct a mistake) was merged into U14.

**C1 Browse items.** As a player, I want to see the items a shop currently has, with prices and any remaining quantity, so that I can decide what to buy. *(shops)*

**C2 Buy an item.** As a player, I want to buy an item for one of my characters so that the price comes out of that character's coins. *(shops, player_characters)*
- The purchase fails with a clear message if the character cannot afford it.
- A purchase is all or nothing: no half-finished purchases.

**C3 Last one wins.** As a player, I want a clear "already sold" message when someone else buys the last unit first. *(shops)*
- Two players buying the last unit at the same moment never both succeed.

**C4 Live shop.** As a player, I want sold-out items to disappear from my screen within a few seconds, without reloading. *(shops)*
- The shop refreshes about every 5 seconds while the page is visible, and not while the tab is hidden.

**C5 Ledger.** As a player, I want to see a history of every time each of my characters gained or lost items or coins, newest first, with a note on what happened (for example `traded to <character name>` or `awarded by game master <name>`), so I can see where things came from and went. *(player_characters)*

**C7 Nightly backup.** As an admin, I want a nightly copy of the database stored outside the server so that a server or account problem does not lose a club's data. *(site-wide)*

**C8 Predictable cost.** As an admin, I want the hosting bill to stay at the fixed monthly price so that I am never surprised by a charge. *(site-wide)*

## Items: proposed story

**I1 Homebrew items.** As a club admin, I want to add my own items to my club's catalogue (name, description, traits and other details, price) so that my club can use homebrew items that other clubs never see. *(items)*

## Map: decisions and stories

Decided: maps stay very basic. No art. A club can have several hex maps (for example one per world). Storage is kept simple, and tiles are drawn with plain colors and symbols. A map grows without limit in every direction. Its first tile, "safe town", sits at position 0,0, and other tiles are placed by their position relative to it. A tile with nothing defined on it shows blank. Game masters see the whole map; players see only the tiles their characters have visited and the locations they have found (M16).

**M1 Several maps.** As a game master, I want to create more than one hex map for my club so that each world gets its own map. *(map)*

**M2 Unlimited growth.** As a club admin, I want maps to grow in size indefinitely, with "safe town" at 0,0 and locations added at any other position, so that exploration is never boxed in. Tiles with no location or encounter appear blank. *(map)*

**M3 Several locations per tile.** As a game master, I want more than one location on a tile (for example a town and some nearby ruins), and I want each tile to show how many locations it holds. *(map)*

**M4 Mark locations.** As a game master, I want to give a location a name, a color, and a symbol so the map shows what is there at a glance. *(map)*

**M5 Player notes and GM notes.** As a game master, I want separate player notes and GM notes on every location, so I can leave tips for other game masters while players who can see the location (M16) see only the player notes. *(map)*

**M6 Record encounters.** As a game master, I want to add encounters to a location during play and afterwards, noting what the players ran into and what they did, so the map is a record of places players could return to. Players see a location and its encounters only once a character they are viewing the map as has found it (M16); visiting the tile is not enough. *(map)*

**M7 Track visits.** As a game master, I want to record which characters have been to which tiles, picking several characters at once for a party. *(map, player_characters)*

**M8 Player map.** As a player, I want to look at the digital map for my club and choose some or all of my own characters to see where they have been, so I can look back and find where something happened. *(map, player_characters)*
- The map starts filtered to the character selected in the top bar (U24).
- I can change the filter to any of my characters, one or several. This overrides the top-bar selection on the map only; it does not change the character I act as elsewhere.
- With several characters picked, I see every tile any of them visited and every location any of them found.
- Game masters and club admins who own characters can filter the same way, alongside the views in M10.

**M9 Print the map.** As a game master or player, I want to print the map I can see, to bring to the table. A player prints the view for the characters they selected in M8. *(map)*

**M10 Two views for game masters.** As a game master, I want to see and print one copy of the map with everything visible and another copy showing only what my players can see, so I can check what they know and put the right map on the table. For the players' copy I pick the group of characters that make up the party, the same way a player picks theirs in M8. *(map, player_characters)*

**M11 Target level.** As a game master, I want to set a target level on a location, in bands of two challenge ratings (CR 1-2 up to CR 19-20), so players and game masters know roughly how strong it is and how much XP to award the party for discovering it and for exploring it. The app shows the XP amounts; it does not track anyone's XP. *(map)*

**M12 Ask for credit.** As a player, I want to ask for a tile to be marked visited, or for a location to be marked discovered, explored, or found (M16), by one or several of my characters, based on how a session went. The game master or club admin approves or declines, much like an item request. Nothing is declined automatically, so a character left out of a credited group by mistake can be added by asking. *(map, player_characters)*
- A player can ask about an unfound location shown as "?" on a visited tile (M16) by picking that placeholder, without learning anything more about it. The usual ask is a found mark or explored credit; discovered credit is for a character left out of the first group by mistake.
- Players cannot ask for first discovery. A location nobody has discovered yet does not appear at all, and only a game master or club admin records its first discovery (M14). A player who thinks it was missed tells the game master, for example through a message (U13).

**M14 Discovered or explored.** As a game master, I want to record which characters discovered a location and which explored it, so the XP for each is clear. Only the first group to discover a location gets discovery credit, and only one group gets explored credit, which can be a different group that comes later if the first failed or avoided it. Later characters who visit are not added to either. A game master or club admin can correct either credited group, adding or removing characters. Recording either also marks the tile as visited for those characters. *(map, player_characters)*

**Parties.** A "party" is not a record. It just means the list of characters I pick for a given day or action (M7, M10, M14). We do not track sessions or who played in them, though that may change later.

**M15 Where to go back.** As a player, I want the map to clearly mark locations my characters have found that nobody has explored yet, and to show each location's target level, so we can see which places to return to once we are stronger. Everyone who can see a location sees the characters credited with discovering and exploring it. *(map)*

**M16 Hidden until found.** As a game master, I want a location to stay hidden from players until a character they are viewing the map as has found it, even when that character has visited the tile, so the map does not give away what is still out there. *(map, player_characters)*
- A character has found a location if it is credited with discovering or exploring it (M14), or if it has a found mark. A game master or club admin can give one or several characters a found mark on a location. It gives no XP and does not change either credited group; it only lets those characters see the location. This covers characters who arrive after another party already discovered or explored it. Found marks can be removed to correct mistakes.
- On a tile the viewer's characters have visited, a location that someone has discovered (any character, from any player, holds discovery credit) but that the viewer's characters have not found shows as an unnamed "?" placeholder. It reveals only that something is there: no name, symbol, notes, encounters, target level, or credited characters. Players can ask for credit on it (M12).
- A location that nobody has discovered yet is left out completely, with no placeholder.
- A tile's location count (M3) counts the found locations and the "?" placeholders the viewer can see, never undiscovered ones. A visited tile whose locations are all undiscovered looks like an empty visited tile.
- Game masters and club admins see every location in their full view, and their players' view (M10) follows this same rule for the characters they pick.
- Printing (M9) follows the same rule as the screen, placeholders included.

**M13 XP table.** As a club admin, I want the XP amounts for each target level to be editable for my club, starting from the West Marches table, so a club can use its own numbers. *(map)*

The default table, as you gave it:

| Target level | Discovering | Exploring |
|---|---|---|
| CR 1-2 | 75 | 225 |
| CR 3-4 | 200 | 400 |
| CR 5-6 | 2,825 | 8,475 |
| CR 7-8 | 5,000 | 15,000 |
| CR 9-10 | 7,500 | 22,500 |
| CR 11-12 | 9,000 | 27,000 |
| CR 13-14 | 10,000 | 30,000 |
| CR 15-16 | 13,750 | 41,250 |
| CR 17-18 | 17,500 | 52,000 |
| CR 19-20 | 22,500 | 67,500 |

Worth checking against your source: CR 5-6 jumps from 400 to 2,825, and most rows are exactly 3 times discovering (CR 3-4 is 2 times, CR 17-18 is 52,000 rather than 52,500). Because M13 makes the table editable, a typo is easy to fix later.

Still to settle for the map:

- **Tile grid.** Positions will be hex coordinates; the exact scheme is a design detail for later, not a story.

## Agent access (MCP): proposed stories

MCP (Model Context Protocol) is a standard way for an AI agent to call a list of named actions on another program. The app would publish a small set of actions, and a game master's agent connects to them and uses them on the GM's behalf. These stories are drafts for you to cut or change.

Design principles:

- The agent acts as the game master who connected it, with that GM's permissions in one club and nothing more.
- The agent **proposes**; the game master **confirms** on the site. Nothing changes a balance or an inventory until the GM confirms. Agents misread notes, and the ledger is append-only, so a mistake is cheaper to catch before it lands.
- **Everything is propose-then-confirm** in the first version; no change applies directly.
- Applied changes go through the same rules and ledger as anything a GM does by hand, and are marked as recorded through an agent.

**A1 Connect my agent.** As a game master, I want to connect my agent by signing in to the app with my own account, choosing one club, and approving the connection, so I do not have to copy secrets around. I can see my connected agents, when each was last used, and revoke any of them. For agent software that can only use a fixed token, I can create a personal token for one club instead, which I can also revoke. *(agent_access, accounts)*

**A2 Look things up.** As a game master's agent, I want to list the club's characters and search its item catalogue, so I can match names in session and loot notes to real records. It cannot see player emails, messages, or other clubs. *(agent_access)*

**A3 Propose awards from notes.** As a game master, I want my agent to turn my session and loot notes into a proposed batch of awards (coins or items for named characters, each with a note and a date), so I do not type them in by hand. Nothing is applied yet. Sending the same batch twice does not create two. *(agent_access, ledger)*

**A4 Review and confirm.** As a game master, I want to see the proposed batch on the site, fix or remove lines, and confirm it, so that the awards are applied to the ledger with my name and the note "recorded through an agent". *(agent_access, ledger, player_characters)*

**A5 Propose new items.** As a game master, I want my agent to propose a new catalogue item (name, description, traits, value) when loot is not in the catalogue, instead of guessing a match, and I or a club admin approve it before it can be awarded or stocked. *(agent_access, items)*

**A6 Undo a batch.** As a game master, I want to reverse a confirmed batch in one step, which adds reversing ledger entries and leaves the history intact. *(agent_access, ledger)*

**A7 Map updates from notes (coming soon).** As a game master, I want my agent to propose visits, discovered or explored credit, and encounters from my session notes, reviewed and confirmed the same way (M7, M12, M14). This is planned for soon after the first version, not part of it. *(agent_access, map)*

Not included: players' agents, spending a player's coins, trades, and anything outside the connecting GM's club.

## Later

- **lore**: out of scope for now. The world notes in the [dnd-world-keeper](https://github.com/bernvaughn/dnd-world-keeper) repo should eventually live in this app instead of that separate repo, so they are more available. When it comes up, decide whether some lore can be game-master-only.
- **Donate button**: which service it points to is still to be decided; dig into it later.

## Decisions so far

- **Permissions.** The site admin is separate from club permissions. Club admin and game master are separate permissions that one account can hold together. The donate button and the backup and cost stories are the site admin's; everything else is club-level.
- **Login without email.** The app never sends email. Admins create accounts and hand out one-time temporary passwords, people choose their own on first sign-in, and admins reset passwords for members of their club when they administer every club that person belongs to, and the site admin handles the rest (U20-U22). Email addresses identify accounts and are never mailed.
- **Agent access.** A game master's agent connects through MCP, proposes batches of awards and new items from notes, and the game master confirms them on the site before anything changes (A1-A6). Map updates from notes (A7) are coming soon, not in the first version. Some GMs use Claude and some use Meta's Muse.
- **Clubs.** Each club's data is separate, and the email whitelist belongs to a club. A person can have characters in several clubs; a character never moves between clubs. Game masters can own characters and play when they are not running a session, and club admins can hand a character from one player to another (U18).
- **Items.** Each club has its own item catalogue (the `items` app), so clubs can add their own homebrew items. The `shops` app holds inventories that point at the catalogue, with a stock amount per item, and handles buying and selling. A shop only sees its own club's items.
- **Shop prices.** Each item has a value. Each shop has a default sell percentage and a separate default buy percentage of that value, which can be overridden item by item within the shop (S1).
- **Rotations.** A rotation only sets when its shops open and close, and a shop can be in several rotations. A shop's inventory is an ongoing list that carries over between rotations, with stock quantities kept per shop (S2).
- **Coins.** Stored as copper and shown as copper, silver, gold, and platinum (10 copper = 1 silver, 10 silver = 1 gold, 10 gold = 1 platinum). No platinum is shown under 10,000 gp; from 10,000 gp up the normal split is used (U32). Each denomination has its own colour, always with its label (U31).
- **Ledger.** The `ledger` app records every gain or loss of items or coins for a character, with a note and a date.
- **Trades.** The `player_characters` app owns trades. The rules are in U16: players edit their own side until they approve, either player can decline or cancel at any time, trades never expire, offered items are locked and offered coins are held, and held items and coins cannot be offered twice.
- **Who sees what.** A character's inventory and coins are visible to its owner, game masters, and club admins, and game masters keep that view even while they play a character of their own. A player's email is visible to club admins only. On the map, game masters and club admins see everything; players see only the tiles their characters have visited and only the locations those characters have found (M16).
- **Quests.** Players turn in items themselves, with a quantity, and only once they have everything the quest asks for (no partial turn-ins); turned-in items are always used up; coins cannot be turned in; rewards can be coins, items, or both; quests have start and end dates.
- **Message content.** Mostly free text, with an optional choice of which of the sender's characters it is about. They live in `accounts` for now; a separate messaging app may make sense later.
- **Printing.** A printout is a cheat sheet of item name, description, traits, and other details, not a record of ownership.
- **Buying and selling.** A shop can buy items it does not sell, but an item is purchasable only if the shop already sells it (bought items do not become stock on their own).
- **Always-open shops.** A rotation with no close date.
- **One-of-a-kind items.** There are none as a special kind. A unique item is an ordinary club catalogue item that a shop stocks one of, or that a game master gives out once.
- **Messages.** Admins can mark a message handled or closed. There are no in-app replies; the admin talks to the player at the next session.
- **Map visits.** Recorded per character, not per player.
- **Map shape.** Maps grow without limit. Safe town is at 0,0. Empty tiles are blank. A tile can hold several locations and shows how many. Locations have separate player and GM notes, and encounters belong to locations and are added during play or afterwards. Players see a location and its encounters only once a character they are viewing the map as has found it; visiting the tile is not enough (M2-M6, M16).
- **Acting as a character.** A player picks one character to act as from the top bar, remembered per club. Pages that act as one character always use it, with no per-page choice. Pages that pick several characters (the map, map requests) start with it, and picking others there does not change the top-bar selection (U24, U27, M8).
- **Found locations.** A character has found a location if it is credited with discovering or exploring it, or has a found mark from a game master or club admin. A found mark gives no XP and only makes the location visible; players can ask for one like other map credit (M12, M16). On visited tiles, players see an unnamed "?" for each location someone has discovered but their characters have not found, and can ask for credit on it. Undiscovered locations show nothing, and only a game master or club admin records first discovery.
- **Look.** The Bootswatch Journal theme (MIT) for Bootstrap 5 across the whole site, served by the app, with compact tables and forms on dense pages (U23).
- **Navigation.** Character, Shops, and Quests are plain links; everything else sits in a "More", a "Game master", or a "Club admin" menu, showing only links the person may use. The club name, the person's name, the selected character, approvals, and log out never collapse into the hamburger menu (U29, U34).
- **Modals.** Buying (U33), map tiles (M17), and inbox grants (U30) open in modals. Each still has a plain page that works without JavaScript.
- **Inbox grants.** Club admins can grant coins, items, and map credit from a message, through the same rules and ledger as manual adjustments and map credit, and mark the message handled in the same step (U30).
- **Target level and XP.** A location has a target level band; the XP table is editable per club and shown for reference (M11, M13). Each location has one credited discovery group (the first) and one credited explored group (which may differ). Game masters and club admins can correct them, and everyone who sees the location sees the credited characters (M14, M15). Players can ask for visits, discovered, or explored credit, which a game master or club admin grants, with no automatic declines (M12). A party is only a list of characters picked at the time, not a stored record.
- **Left for later.** Lore and the donate service.

## Still open

Nothing right now. Lore and the donate service are left for later (see Later).
