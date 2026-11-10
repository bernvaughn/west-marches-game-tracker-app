# User Stories (draft 2)

Your stories come first, as you wrote them, with two edits: "gm" is spelled "game master", and each story is tagged with the Django apps it touches. Stories from the first draft that still apply follow after them. No code is implied by anything here.

Roles and permissions:

- **Site admin**: runs the whole site (you). Sees every club and sets up the donate button.
- Inside each club, **admin** and **game master (GM)** are two separate permissions on an account. A club's admins are expected to be the same people as its game masters, but one account can hold either permission or both.
  - **Club admin**: manages the club's email whitelist, shops, items, and content.
  - **Game master (GM)**: runs a game; awards loot and keeps track of what players use up.
- **Player**: owns one or more characters and spends their coins. Anyone in a club without those permissions is a player.

In the stories below, "admin" means a club admin, except U11 (donate button) and C7 and C8 (backup and cost), which I assumed are the site admin's. Correct me if that is wrong.

A **club** is a group of people and its data (players, characters, shops, items). Data in one club is never visible to another.

Apps (names tentative; see the README): `accounts`, `player_characters`, `items`, `shops`, `map`, `lore`, `quests`.

## Stories

**U1 Whitelist emails.** As an admin, I want to whitelist email addresses to be used for accounts, and assign those email addresses to player characters for the players to access. *(accounts, player_characters)*

**U2 Log in and keep notes.** As a player, I want to be able to log in and add details to my character, so I can keep notes and stats and etc. *(accounts, player_characters)*

**U3 Loot.** As a player, I want my game master to award me loot (coins, items) that I can sell and buy with to available shops. *(player_characters, shops)*

**U4 Fresh shops.** As an admin, I want to change up the shops and items available between sessions, so players have fresh things to buy. *(shops, items)*

**U5 Always-open shops.** As an admin, I want there to be some shops that carry fixed generally-available inventory like torches and ropes that players can have available to buy. *(shops)*

**U6 Printable items.** As a player, I want to be able to print out items that I purchased so I have a reference while actually playing. *(player_characters, shops)*

**U7 Consume items.** As a game master, I want to be able to mark players' items as consumed or spent, if they spend or use something in game (potion or coins, etc). *(player_characters)*

**U8 Coin denominations.** As a player, I want to have different denominations of coins, but have it auto-exchange when buying things so I can see my coins split out but do not need to suffer when buying. *(player_characters, shops)*

**U9 Unlimited or limited stock.** As an admin, I want some items to be unlimited and some to have limited quantities at a given shop, so players can or cannot buy as many as they want. *(shops)*

**U10 Fun shops.** As an admin, I want to have a fun interface with rotating memorable shops, selling mixes of useful and not-useful items, because I want this app to be entertaining to players to entice them to use it more. *(shops)*

**U11 Donate.** As an admin, I want to set up a donate button to help me pay for all this. *(site-wide)*

**U12 Clubs.** As an admin, I want data segregated between groups (I like the term "club") so I can eventually have other people use this app too, or I could have multiple "club"s going at once, and keep the players and items and etc separated between the clubs. *(all apps)*

## Carried over from the first draft

These still apply and are not covered above. Keep, change, or drop them.

**C1 Browse items.** As a player, I want to see the items a shop currently has, with prices and any remaining quantity, so that I can decide what to buy. *(shops)*

**C2 Buy an item.** As a player, I want to buy an item for one of my characters so that the price comes out of that character's coins. *(shops, player_characters)*
- The purchase fails with a clear message if the character cannot afford it.
- A purchase is all or nothing: no half-finished purchases.

**C3 Last one wins.** As a player, I want a clear "already sold" message when someone else buys the last unit first. *(shops)*
- Two players buying the last unit at the same moment never both succeed.

**C4 Live shop.** As a player, I want sold-out items to disappear from my screen within a few seconds, without reloading. *(shops)*
- The shop refreshes about every 5 seconds while the page is visible, and not while the tab is hidden.

**C5 Balance and history.** As a player, I want to see each of my characters' coins and a list of everything that changed them (loot, purchases, sales), newest first. *(player_characters)*

**C6 Correct a mistake.** As a game master, I want to subtract coins with a reason so that I can fix an award I got wrong without erasing history. *(player_characters)*
- Corrections are new entries; existing entries are never edited or deleted.

**C7 Nightly backup.** As an admin, I want a nightly copy of the database stored outside the server so that a server or account problem does not lose a club's data. *(site-wide)*

**C8 Predictable cost.** As an admin, I want the hosting bill to stay at the fixed monthly price so that I am never surprised by a charge. *(site-wide)*

## Items: proposed story

**I1 Homebrew items.** As a club admin, I want to add my own items to my club's catalogue (name, description, price) so that my club can use homebrew items that other clubs never see. *(items)*

## Map: constraints and proposed stories

Decided: maps stay very basic. No art. A club can have several hex maps (for example one per world). Storage is kept simple, and tiles are drawn with plain colors and symbols marking locations.

Proposed stories, from your description of the map app (cut or change freely):

**M1 Several maps.** As a game master, I want to create more than one hex map for my club so that each world gets its own map. *(map)*

**M2 Mark tiles.** As a game master, I want to give a tile a color, a symbol, and a note about an encounter or location so that the map shows what is there at a glance. *(map)*

**M3 Track visits.** As a game master, I want to record which players have been to which tiles. *(map)*

## Apps with no stories yet

You described these apps but have not written stories for them.

- **lore**: the world and its details; the contents of the `dnd-world-keeper` repo move here so they are more available.
- **quests**: small side quests, such as gathering items during a session and trading them in for a special reward or more money.

## Open questions

Decided so far: the site admin is separate from club permissions; club admin and game master are separate permissions that one account can hold together; each club has its own item catalogue so clubs can add their own homebrew items, the `items` app owns the catalogue while `shops` holds inventories that point at it and handles buying and selling, and a shop holds a stock amount of items from its own club's catalogue only; coins are stored as copper and shown split into denominations; hex maps are basic, with no art.

Still open:

- **Permissions.** Which stories need the site admin and which a club admin? I assumed the donate button and the backup and cost stories are site-wide and the rest are club-level; does that match? Is the email whitelist (U1) site-wide or per club?
- **Denominations.** Which coins, and at what exchange rates (the 5th-edition set is copper, silver, electrum, gold, platinum)?
- **Map visibility.** Do players see the whole map, or only the tiles they have visited?
- **Selling.** U3 says players can sell loot to shops. Do shops buy items back, and at what share of the price?
- **Rotation.** Do shop inventories rotate by hand between sessions, or on a schedule or at random?
- **Whitelist.** Can a player have characters in more than one club, and can a character move from one email to another?
- **Printing.** What should a printout contain: item name, description, quantity, and which character?
- **Lore visibility.** Is all lore visible to every player in the club, or can some of it be game-master-only?
- **Donate.** Which service will the donate button point to?
