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

Apps (names tentative; see the README): `accounts`, `player_characters`, `items`, `shops`, `ledger`, `map`, `quests`. Lore is out of scope for now (see Later).

## Stories

**U1 Whitelist emails.** As an admin, I want to whitelist email addresses to be used for accounts, and assign those email addresses to player characters for the players to access. *(accounts, player_characters)*
- The whitelist belongs to a club; the same email can be whitelisted in more than one club.

**U2 Log in and keep notes.** As a player, I want to be able to log in and add details to my character, so I can keep notes and stats and etc. *(accounts, player_characters)*

**U3 Loot.** As a player, I want my game master to award me loot (coins, items) that I can sell and buy with to available shops. *(player_characters, shops)*

**U4 Fresh shops.** As an admin, I want to change up the shops and items available between sessions, so players have fresh things to buy. *(shops, items)*

**U5 Always-open shops.** As an admin, I want there to be some shops that carry fixed generally-available inventory like torches and ropes that players can have available to buy. These are shops in a rotation with no close date. *(shops)*

**U6 Printable items.** As a player, I want to be able to print out items that I purchased so I have a reference while actually playing. *(player_characters, items)*
- A printout shows each item's name, description, traits, and other details. It is a cheat sheet for using the item in play, not a record of who owns it.

**U7 Consume items.** As a game master, I want to be able to mark players' items as consumed or spent, if they spend or use something in game (potion or coins, etc). *(player_characters)*

**U8 Coin denominations.** As a player, I want to have different denominations of coins, but have it auto-exchange when buying things so I can see my coins split out but do not need to suffer when buying. *(player_characters, shops)*
- The denominations are copper, silver, gold, and platinum, and amounts are stored in copper.
- The rates are 10 copper = 1 silver, 10 silver = 1 gold, 10 gold = 1 platinum.

**U9 Unlimited or limited stock.** As an admin, I want some items to be unlimited and some to have limited quantities at a given shop, so players can or cannot buy as many as they want. *(shops)*

**U10 Fun shops.** As an admin, I want to have a fun interface with rotating memorable shops, selling mixes of useful and not-useful items, because I want this app to be entertaining to players to entice them to use it more. *(shops)*

**U11 Donate.** As an admin, I want to set up a donate button to help me pay for all this. *(site-wide)*

**U12 Clubs.** As an admin, I want data segregated between groups (I like the term "club") so I can eventually have other people use this app too, or I could have multiple "club"s going at once, and keep the players and items and etc separated between the clubs. *(all apps)*

**U13 Ask for a fix.** As a player, I want to be able to message the club admins to manually evaluate and give me items, so if I remember something my character gathered but the game master forgot to add to my online inventory, a club admin can fix it. *(accounts, player_characters, items)*
- Messages are mostly free text; the sender can pick which of their characters the message is about.

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

Decided: maps stay very basic. No art. A club can have several hex maps (for example one per world). Storage is kept simple, and tiles are drawn with plain colors and symbols. A map grows without limit in every direction. Its first tile, "safe town", sits at position 0,0, and other tiles are placed by their position relative to it. A tile with nothing defined on it shows blank. Game masters see the whole map; players see only what their characters have visited.

**M1 Several maps.** As a game master, I want to create more than one hex map for my club so that each world gets its own map. *(map)*

**M2 Unlimited growth.** As a club admin, I want maps to grow in size indefinitely, with "safe town" at 0,0 and locations added at any other position, so that exploration is never boxed in. Tiles with no location or encounter appear blank. *(map)*

**M3 Several locations per tile.** As a game master, I want more than one location on a tile (for example a town and some nearby ruins), and I want each tile to show how many locations it holds. *(map)*

**M4 Mark locations.** As a game master, I want to give a location a name, a color, and a symbol so the map shows what is there at a glance. *(map)*

**M5 Player notes and GM notes.** As a game master, I want separate player notes and GM notes on every location, so I can leave tips for other game masters while players whose characters have visited the tile see only the player notes. *(map)*

**M6 Record encounters.** As a game master, I want to add encounters to a location during play and afterwards, noting what the players ran into and what they did, so the map is a record of places players could return to. Players whose characters have visited the tile see its locations and their encounters, with no separate hidden or visible setting. *(map)*

**M7 Track visits.** As a game master, I want to record which characters have been to which tiles, picking several characters at once for a party. *(map, player_characters)*

**M8 Player map.** As a player, I want to look at the digital map for my club and choose some or all of my own characters to see where they have been, so I can look back and find where something happened. *(map, player_characters)*

**M9 Print the map.** As a game master or player, I want to print the map I can see, to bring to the table. A player prints the view for the characters they selected in M8. *(map)*

**M10 Two views for game masters.** As a game master, I want to see and print one copy of the map with everything visible and another copy showing only what my players can see, so I can check what they know and put the right map on the table. For the players' copy I pick the group of characters that make up the party, the same way a player picks theirs in M8. *(map, player_characters)*

**M11 Target level.** As a game master, I want to set a target level on a location, in bands of two challenge ratings (CR 1-2 up to CR 19-20), so players and game masters know roughly how strong it is and how much XP to award the party for discovering it and for exploring it. The app shows the XP amounts; it does not track anyone's XP. *(map)*

**M12 Ask for credit.** As a player, I want to ask for a tile to be marked visited, or for a location to be marked discovered or explored, by one of my characters (or several at once), based on how a session went. The game master or club admin approves or declines, much like an item request, and approving records it. A request for "explored" on a location that is already explored by another party is declined automatically with that reason. *(map, player_characters)*

**M14 Discovered or explored.** As a game master, I want to record, for each character in a party, whether a location has been discovered or fully explored, so the XP for each is clear. Recording either also marks the tile as visited. Many parties can discover the same location, but only one party gets explored credit: the characters I record when the location is explored are the credited group, and later parties who visit are not added to it. I can correct the credited group if I made a mistake. *(map, player_characters)*

**M15 Where to go back.** As a player, I want the map to clearly mark locations my characters have discovered but not yet explored, and to show each location's target level, so we can see which places to return to once we are stronger. A location that another party has already explored shows as explored, with the credited characters visible to players who have visited. *(map)*

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

## Later

- **lore**: out of scope for now. The world notes in the [dnd-world-keeper](https://github.com/bernvaughn/dnd-world-keeper) repo should eventually live in this app instead of that separate repo, so they are more available. When it comes up, decide whether some lore can be game-master-only.
- **Donate button**: which service it points to is still to be decided; dig into it later.

## Decisions so far

- **Permissions.** The site admin is separate from club permissions. Club admin and game master are separate permissions that one account can hold together. The donate button and the backup and cost stories are the site admin's; everything else is club-level.
- **Clubs.** Each club's data is separate, and the email whitelist belongs to a club. A person can have characters in several clubs; a character never moves between clubs. Game masters can own characters and play when they are not running a session, and club admins can hand a character from one player to another (U18).
- **Items.** Each club has its own item catalogue (the `items` app), so clubs can add their own homebrew items. The `shops` app holds inventories that point at the catalogue, with a stock amount per item, and handles buying and selling. A shop only sees its own club's items.
- **Shop prices.** Each item has a value. Each shop has a default sell percentage and a separate default buy percentage of that value, which can be overridden item by item within the shop (S1).
- **Rotations.** A rotation only sets when its shops open and close, and a shop can be in several rotations. A shop's inventory is an ongoing list that carries over between rotations, with stock quantities kept per shop (S2).
- **Coins.** Stored as copper and shown as copper, silver, gold, and platinum (10 copper = 1 silver, 10 silver = 1 gold, 10 gold = 1 platinum).
- **Ledger.** The `ledger` app records every gain or loss of items or coins for a character, with a note and a date.
- **Trades.** The `player_characters` app owns trades. The rules are in U16: players edit their own side until they approve, either player can decline or cancel at any time, trades never expire, offered items are locked and offered coins are held, and held items and coins cannot be offered twice.
- **Who sees what.** A character's inventory and coins are visible to its owner, game masters, and club admins, and game masters keep that view even while they play a character of their own. A player's email is visible to club admins only. On the map, game masters see everything and players see only the tiles their characters have visited.
- **Quests.** Players turn in items themselves, with a quantity, and only once they have everything the quest asks for (no partial turn-ins); turned-in items are always used up; coins cannot be turned in; rewards can be coins, items, or both; quests have start and end dates.
- **Message content.** Mostly free text, with an optional choice of which of the sender's characters it is about. They live in `accounts` for now; a separate messaging app may make sense later.
- **Printing.** A printout is a cheat sheet of item name, description, traits, and other details, not a record of ownership.
- **Buying and selling.** A shop can buy items it does not sell, but an item is purchasable only if the shop already sells it (bought items do not become stock on their own).
- **Always-open shops.** A rotation with no close date.
- **One-of-a-kind items.** There are none as a special kind. A unique item is an ordinary club catalogue item that a shop stocks one of, or that a game master gives out once.
- **Messages.** Admins can mark a message handled or closed. There are no in-app replies; the admin talks to the player at the next session.
- **Map visits.** Recorded per character, not per player.
- **Map shape.** Maps grow without limit. Safe town is at 0,0. Empty tiles are blank. A tile can hold several locations and shows how many. Locations have separate player and GM notes, and encounters belong to locations and are added during play or afterwards. Players see the locations and encounters on tiles their characters visited, with no hidden-or-visible split (M2-M6).
- **Target level and XP.** A location has a target level band; the XP table is editable per club and shown for reference (M11, M13). Each character's progress on a location is recorded as discovered or explored, and the map marks discovered-but-unexplored places (M14, M15). Players can ask for visits, discovered, or explored credit, which a game master or club admin grants (M12). Only one party gets explored credit for a location; many can discover it.
- **Left for later.** Lore and the donate service.

## Still open

Nothing right now. Lore and the donate service are left for later (see Later).
