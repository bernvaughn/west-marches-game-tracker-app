# User Stories (draft 2)

Your stories come first, as you wrote them, with small edits: "gm" is spelled "game master", a few awkward phrases are smoothed, and each story is tagged with the Django apps it touches. Stories from the first draft that still apply follow after them. No code is implied by anything here.

Roles and permissions:

- **Site admin**: runs the whole site (you). Sees every club and sets up the donate button.
- Inside each club, **admin** and **game master (GM)** are two separate permissions on an account. A club's admins are expected to be the same people as its game masters, but one account can hold either permission or both.
  - **Club admin**: manages the club's email whitelist, shops, items, content, starting equipment templates, and magic item starting options.
  - **Game master (GM)**: runs a game; awards loot, keeps track of what players use up, and approves or declines magic starting item requests via the inbox.
- **Player**: owns one or more characters and spends their coins. Anyone in a club without those permissions is a player. Game masters can also own characters and play as players when they are not running a session. A person can have characters in more than one club, but a character never moves between clubs.

In the stories below, "admin" means a club admin, except U11 (donate button) and C7 and C8 (backup and cost), which are the site admin's.

A **club** is a group of people and its data (players, characters, shops, items). Data in one club is never visible to another.

Apps (names tentative; see the README): `accounts`, `player_characters`, `items`, `shops`, `ledger`, `map`, `quests`, `agent_access`, `starting_equipment`, and a planned `sessions` app (round 19). Lore is out of scope for now (see Later).

## Stories

**U1 Whitelist emails.** As an admin, I want to whitelist email addresses to be used for accounts, and assign those email addresses to player characters for the players to access. *(accounts, player_characters)*
- The whitelist belongs to a club; the same email can be whitelisted in more than one club.
- Whitelisting an email creates the account and shows the admin a temporary password to pass on (U18). If that email already has an account, from another club, it only adds the person to this club.

**U2 Log in and keep notes.** As a player, I want to be able to log in and add details to my character, so I can keep notes and stats and etc. *(accounts, player_characters)*

**U18 Create accounts without email.** As an admin, I want to create accounts for my club's players and game masters myself and hand them a temporary password, so the app never has to send email. On first sign-in the person must choose their own password. The temporary password is shown once. *(accounts)*

**U19 Reset passwords.** As an admin, I want to reset the password of a player or game master in my club, which gives them a new temporary password to choose a new one from and signs them out everywhere, so people who forget a password are not locked out. Because a password belongs to the person's account, I can do this only if I am an admin of every club they belong to; otherwise the site admin does it. The site admin can reset any account, including a club admin's. *(accounts)*

**U20 Change my password.** As a player, I want to change my own password while signed in. *(accounts)*

**U3 Loot.** As a player, I want my game master to award me loot (coins, items) that I can sell and buy with to available shops. *(player_characters, shops)*

**U4 Fresh shops.** As an admin, I want to change up the shops and items available between sessions, so players have fresh things to buy. *(shops, items)*

**U5 Always-open shops.** As an admin, I want there to be some shops that carry fixed generally-available inventory like torches and ropes that players can have available to buy. These are shops in a rotation with no close date. *(shops)*

**U6 Printable items.** As a player, I want to be able to print out items that I purchased so I have a reference while actually playing. *(player_characters, items)*
- A printout shows each item's name, description, traits, and other details. It is a cheat sheet for using the item in play, not a record of who owns it.

**U7 Consume items.** As a game master, I want to be able to mark players' items as consumed or spent, if they spend or use something in game (potion or coins, etc). *(player_characters)*

**U8 Coin denominations.** As a player, I want to have different denominations of coins, but have it auto-exchange when buying things so I can see my coins split out but do not need to suffer when buying. *(player_characters, shops)*
- The denominations are copper, silver, gold, and platinum, and amounts are stored in copper.
- The rates are 10 copper = 1 silver, 10 silver = 1 gold, 10 gold = 1 platinum.
- How amounts are shown follows U30: no platinum under 10,000 gp, and colour-coded denominations (U29).

**U9 Unlimited or limited stock.** As an admin, I want some items to be unlimited and some to have limited quantities at a given shop, so players can or cannot buy as many as they want. *(shops)*

**U10 Fun shops.** As an admin, I want to have a fun interface with rotating memorable shops, selling mixes of useful and not-useful items, because I want this app to be entertaining to players to entice them to use it more. *(shops)*

**U11 Donate.** As an admin, I want to set up a donate button to help me pay for all this. *(site-wide)*

**U12 Clubs.** As an admin, I want data segregated between groups (I like the term "club") so I can eventually have other people use this app too, or I could have multiple "club"s going at once, and keep the players and items and etc separated between the clubs. *(all apps)*

**U13 Ask for a fix.** As a player, I want to be able to message the club admins to manually evaluate and give me items, so if I remember something my character gathered but the game master forgot to add to my online inventory, a club admin can fix it. *(accounts, player_characters, items)*
- Messages are mostly free text, and are about the sender's selected character (U22, U25).

**U14 Manual adjustments.** As a club admin or game master, I want to be able to give and take items and money to and from players, so I can manually adjust their loot as needed. I need to be able to tag the give and take actions with notes and dates. *(player_characters, items)*
- Adjustments are recorded as new entries with a note and a date; earlier entries are never edited or deleted.
- The date defaults to the current date and can be changed to any date.

**U15 Private email.** As a player, I want my email address to only be visible to club admins, so other players cannot contact me via email without my permission. *(accounts)*

**U16 Hand over a character.** As a club admin, I want to transfer a character from one player to another, if needed, for example when a character turned evil and was handed over to the game master. *(player_characters)*
- Game masters can own characters too, so a character can be handed to a game master.
- A character stays in its club; it cannot move to another club.

**U17 Private inventories.** As a player, I want only the game masters, the club admins, and me to be able to see my characters' inventories, so other players cannot see what my characters are carrying. *(player_characters)*

## Look and navigation: stories from the first look (2026-11-11)

From the first run of a local build. M8, M12, M15 and M16 in the map section also came from it.

**U21 A finished look.** As anyone using the app, I want every page, starting with the sign-in page, to use one consistent, compact look based on the Bootswatch Journal theme for Bootstrap 5, so the app feels finished and does not waste screen space. *(site-wide)*
- The sign-in, first-password, and password-change pages are styled like the rest of the site.
- Pages are denser: less empty space, and tables and lists that fit more on screen, while staying usable on a phone.
- The theme is Bootswatch Journal (MIT license), chosen for its serif, storybook feel. Its files are served from the app itself so pages do not depend on a third-party site.
- Journal is roomier than admin themes, so dense pages (inventories, ledgers, shop stock, approval lists) use Bootstrap's compact table and form sizes to keep them tight.

**U22 Act as a character.** As a player, I want to pick one of my characters to act as from a dropdown in the top bar, so shops, buying and selling, moving items, quests, and requests use that character without me choosing it on every page. *(player_characters, accounts, shops, quests, map)*
- The dropdown appears only if I have more than one character in the current club. With one character, that character is always selected. With none, the top bar says so and pages that need a character tell me I don't have one.
- My selection is remembered per club across pages and sign-ins, and switching clubs switches to my selection for that club.
- Pages that act as one of my characters always use the selected one, with no character field of their own: buying, selling, quest turn-ins, and messages to the admins (U13). To act as another character, I switch it in the top bar (round 2, U25).
- Where a page involves a second character of mine, the selected character is the "from" side and I pick the other.
- Pages where I can pick several characters keep their picker and start with the selected character: the map (M8) and map requests (M12).
- If my selected character is handed to someone else (U16), my selection falls back to another of my characters.
- Game masters and club admins who own characters get the same dropdown. Selecting a character never limits their game master or club admin views.

**U23 Who I am.** As anyone signed in, I want the top bar to show my name and, if I have one, the character I am acting as (U22), so I always know who I am acting as. *(accounts, player_characters)*

**U24 Approvals waiting.** As a game master or club admin, I want an indicator in the top bar showing how many things in the current club are waiting for me to act on, so I notice them without checking each page. *(accounts, agent_access, map, items)*
- It counts what I am allowed to act on: proposed agent batches (A4), proposed catalogue items (A5), map requests for visits and discovered or explored credit (M12), and, for club admins, open messages (U13).
- Clicking it lists each waiting thing, grouped by kind, with a link to where I approve, decline, or handle it.
- The count disappears when nothing is waiting. Players never see it.
- It updates when I load a page; it does not need to be live.

## Round 2: stories from the second look (2026-11-11)

From using the build after the first-look stories landed.

**U25 One character everywhere.** As a player, I want every page that acts as one of my characters to use the character in the top bar, with no character choice of its own, so I never act as the wrong character by mistake. *(shops, player_characters, quests, accounts)*
- This replaces the per-page character field that U22 first kept. It covers selling to a shop, buying, quest turn-ins, and messages to the admins.
- Each of these pages names the character it is acting as, near the top or on the action button, for example "Sell as Aria Windrunner".
- Pages where I can pick several characters keep their picker, starting with the selected character: the map (M8) and map requests (M12).
- Game master and club admin pages that act on other people's characters (awards, adjustments, visits, credit, found marks) keep their character pickers. The top bar never limits them.

**U26 Club cards.** As anyone signed in, I want the "Your clubs" page to show each club as a card with useful details, so it is inviting and I can see at a glance what each club is. *(accounts, player_characters)*
- Each card shows the club name, my role there (player, game master, club admin), the game masters' names, the number of players, and my characters in that club.
- The whole card links to the club. Cards sit in a grid that becomes one column on a phone.
- A card shows only what any member of that club may see: no emails and no inventories.

**U27 Grouped navigation.** As anyone in a club, I want the navigation under the top bar grouped into a few menus, with the pages players use most kept as plain links, so I can find things without scanning a long row of links. *(site-wide)*
- Plain links: Character, Shops, and Quests. Character opens the selected character's sheet. A basic "Character directory" is in the More menu, and the full list is "All characters" in the Game master menu (U39).
- "More" menu for everyone: Map, Ledger, and Message the admins.
- "Game master" menu, for game masters and club admins: awards and adjustments, map editing, map requests, agent batches, proposed items, and agent connections.
- "Club admin" menu, for club admins only: members, inbox, item catalogue, shops and stock, rotations, and the XP table.
- A menu shows only the links the person may use, and a menu with no links is hidden.

**U28 Handle requests from the inbox.** As a club admin, I want to grant items, coins, and map credit from a modal on the inbox, so I can handle a player's request without leaving the inbox. *(accounts, player_characters, ledger, map)*
- Each message has a "Grant" button that opens a modal for the message's character. I can pick a different character in the same club.
- The modal can give coins, give items from the catalogue with a quantity, and record a visit, discovered credit, explored credit, or a found mark on a location.
- Grants go through the same rules and ledger as manual adjustments (U14) and map credit (M14, M16). Each has a note, which starts as a reference to the message, and a date, which starts as today.
- After granting, I can mark the message handled in the same step. The message shows what was granted from it.
- U36 splits this modal into separate buttons and confirm modals.
- The inbox stays for club admins only (U13). Game masters keep using the award and map pages.

**U29 Colour-coded coins.** As anyone, I want each coin denomination shown in its own colour everywhere amounts appear, so I can read amounts at a glance. *(site-wide)*
- Copper is copper-brown, silver is grey, gold is gold, and platinum is a pale blue-white. Each colour has enough contrast to read on the theme background.
- The denomination label (cp, sp, gp, pp) always stays next to the number, so colour is never the only cue.
- The colours apply to balances, prices, values, sell offers, the ledger, quest rewards, agent batches, and coin inputs. Printouts can stay black and white.

**U30 Gold first.** As a player, I want amounts shown in gold up to 9,999 gp, and mostly in platinum above that, because that is how my table talks about money. *(site-wide)*
- Under 10,000 gp in total, no platinum is shown, for example "9,999 gp 5 sp".
- From 10,000 gp up, the whole amount uses the normal split, for example "1,000 pp" for 10,000 gp and "1,234 pp 5 gp 6 sp" for 12,345 gp 6 sp.
- The rates do not change (1 pp = 10 gp), amounts stay stored in copper (U8), and copper and silver show as usual.
- The rule applies to every amount the app shows: balances, item values, shop prices, sell offers, the ledger, quest rewards, and agent batches.

**U31 Buy with a confirm modal.** As a player, I want the Buy button to open a confirm modal instead of a new page, so buying is quick. *(shops)*
- The modal shows the item, the price, the quantity, the character buying (U25), and that character's coins before and after.
- Confirming buys the item and updates the shop page in place. "Already sold" (C3) and "can't afford" (C2) messages show in the modal.
- Without JavaScript, the Buy button still works through the buy page.

**U32 Top bar on narrow screens.** As anyone on a phone or narrow window, I want the club name, my name, my selected character, the approvals indicator, and log out to stay visible at every width, so I always know where I am and who I am acting as. *(site-wide)*
- Only the navigation links and menus (U27) collapse into the hamburger menu.
- On very narrow screens, the always-visible items may shrink (for example, initials or icons with labels for screen readers), but they never move into the hamburger menu.

**U33 A nicer-looking app.** As anyone using the app, I want every page to look polished and consistent, so the app is pleasant to use. I am not a designer; I want it to look nice. *(site-wide)*
- Every page uses the same building blocks: a page header with the title and main action, cards for grouped details, compact tables for lists, badges for statuses, clear empty states, and consistent spacing and buttons.
- The agent batch review page (A4) gets a cleanup first: one card per batch with its status and source notes, a clear table of lines, and the edit, confirm, and reverse actions grouped.
- A component reference page, visible only to the site admin, shows every building block, so new pages stay consistent.
- Each change is checked by screenshots of the pages at desktop and phone width, attached to the work for review.

**M17 Tile details in a modal.** As anyone looking at a map, I want clicking a tile to open its details in a modal over the map, instead of a new page, so I keep my place on the map. *(map)*
- The modal shows what the tile page shows today, with the same visibility rules (M16) and the same actions (requests, and game master editing links).
- The tile page keeps working at its own address, for links, printing, and use without JavaScript.
- Closing the modal returns to the same map position and character filter.

**U34 The shopkeeper's counter.** As a player, I want each shop page to feel like walking up to a shopkeeper's counter, so shopping is memorable and fun (U10). *(shops)*
- From top to bottom: the shop name, centred, as the page title; a full-width banner in the shop's colour with the shopkeeper's silhouette in the middle and their name over it; a coin button labelled "Sell to <keeper name>" just above the items; then the table of items to buy.
- The table starts at the bottom edge of the banner, and its top looks like the shopkeeper's counter, for example a wood-toned counter-top band. It then continues down the page as a normal table. Buy opens the confirm modal (U31).
- The shop and keeper descriptions show below the table.
- A club admin picks the shop's colour from the existing presets and its silhouette from a set of preset generic silhouettes, both on the shop's edit form, with a preview of each silhouette. There is no free colour picker.
- The app ships 8 to 10 original, generic silhouettes that suit a fantasy shop (for example a hooded trader, dwarf smith, robed mage, halfling grocer, or goblin peddler), each readable on every preset colour.
- On a phone, the banner and silhouette shrink and the table stays readable with no sideways scroll.
- U37 moves the silhouette to the left of the banner and redraws the presets.

**U35 A printable character sheet.** As a player, I want my character's page to look like a stylised character sheet that I could print and bring to the table. *(player_characters, ledger)*
- A header box with the character's name in large serif, the owner, and the club, like the top of a paper character sheet.
- Below it, bordered and titled boxes: coins (colour-coded, U29), inventory, notes and stats (U2), and recent ledger entries with a link to the full ledger (C5).
- Actions (edit, and the game master and club admin adjustments) sit together outside the sheet, so the sheet stays clean.
- A "Print sheet" button prints the sheet in black and white without the navigation or actions, on one Letter or A4 page where possible.
- The sheet is compact, with little white space. At desktop width, the boxes sit in a multi-column grid, each only as wide as its content needs. A typical character fits on one screen with little or no scrolling.
- Coins show once, with held and available on one line, and zero denominations are never listed. Empty boxes are hidden or show a one-line empty state. The inventory table is narrow, with small right-aligned number columns.
- On a phone, the boxes stack in one column. Privacy is unchanged (U17).
- Item cards print all at once in a nine-per-page grid, or one at a time (U38).

## Round 3: stories from the third look (2026-11-12)

From using the build after the design overhaul (U25–U35, M17) landed. Kept as built, because they work well: the colour-coded coins (U29), the character sheet layout (U35), and the "Sell to <keeper>" button's place on the shop page (U34). Shop emoji render correctly in a normal browser. Only club admins can edit the XP table (M13); players can view it. That is how it works today and stays that way.

**U36 Inbox actions as buttons.** As a club admin, I want each inbox action to be its own button that opens a confirm modal, instead of a dropdown plus a "Set" button, so handling a message is one clear click and a confirm. *(accounts, player_characters, ledger, map)*
- Status actions are separate buttons that show only when they apply: "Mark handled" and "Close" on an open message, and "Reopen" on a handled or closed one. Each opens a short confirm modal that names the message's sender and subject.
- Granting is split into separate buttons: "Give coins", "Give items", and "Give map credit". Each opens its own modal with only the fields for that grant, then a confirm step that summarises exactly what will be given and to which character. This replaces the one grant modal with a map-kind dropdown (U28).
- Inside "Give map credit", the kind of credit (visit, discovered, explored, found mark) is a row of buttons or radio choices, not a dropdown.
- Each grant modal keeps U28's rules: the character starts as the message's character, the note starts as a reference to the message, the date starts as today, and "mark handled" is offered in the same step.
- The demo data includes an inbox message about a character, so the grant modals open with a character already picked.

**M18 Found-mark requests keep the secret.** As a player, I want the request page for a location my characters haven't found to say "Unknown location" and show where it is, so the request doesn't give away the name and I can tell which "?" I'm asking about. *(map)*
- A found-mark request always shows "Unknown location" to a player, never the location's name, even when another of their characters has already found it. Credit requests on a location that none of the picked characters has found do the same.
- The page shows the map name and the tile's coordinates (column and row, as on the map), for example "Map: Westlands. Tile: 0, -2. Location: Unknown location".
- Game masters and club admins still see the real name. The request queue (M12) shows the same coordinates beside each map request.

**U37 Shopkeeper beside the counter, with better silhouettes.** As a player, I want the shopkeeper's silhouette to stand off to the left of the shop banner, drawn well, so the shop looks like a real storefront and not a placeholder. *(shops)*
- The silhouette sits on the left side of the banner instead of centred, with the keeper's name beside or just below it. The space to its right can hold the shop's short description or stay as plain banner colour. The "Sell to <keeper name>" button keeps its current place.
- The 10 preset silhouettes are redrawn to look finished: clear, recognisable outlines (hood, beard, hat, apron, pack, and so on), one consistent style, and readable at banner size on every preset colour. None should look like a generic blob or a chess piece.
- The silhouette picker on the shop form shows the new drawings. Existing shops keep their chosen silhouette.
- On a phone, the silhouette shrinks and stays on the left, and nothing scrolls sideways.
- This changes the silhouette placement in U34.
- U43 moves the name above the silhouette and the description into the banner.

**U38 Print item cards, one or all.** As a player, I want to print all my item cards on card sheets, or print a single card, so I print only what I need to bring to the table. *(player_characters, items)*
- "Print item cards" stays on the character sheet and prints every item's card in a 3 by 3 grid, nine cards per portrait Letter or A4 page, like a nine-pocket card sheet. Extra cards continue on more pages.
- Each item in the inventory also has a "Print card" action. It asks for one of two layouts: "Full page", with the card enlarged to fill a portrait page, or "Grid spot", with the card in the top-left spot of the same 3 by 3 grid and the rest of the page left blank, so it fits the same card sheets.
- Cards print in black and white without the navigation. A card in the grid is the same size whether it is printed alone or with the others.
- Privacy is unchanged (U17).
- U42 adds an icon, the value, and an owner and print-date footer.

**U39 "Character" means my character.** As a player, I want the Character link to open the sheet of the character selected in the top bar, so it goes straight to the character I am playing. *(player_characters, site-wide)*
- For a player with a selected character, Character opens that character's sheet (U35). A player with no character in the club sees a short empty state with "Create a character".
- Everyone gets a read-only "Character directory" in the More menu (U27). It lists every character in the club with only basic details: name and player name. It has no inventories, coins, ledgers, or emails, and each name links to the same basic view, not the sheet, unless the viewer may see that sheet (U17). Players use it to check spelling or to look up who plays whom. We may add more to it later.
- Game masters and club admins also get "All characters" in the Game master menu: today's full list, with links to each character's full sheet.
- A game master or club admin who also plays a character gets all three: Character opens their own selected character, Character directory is the basic list, and All characters is the full list.
- This changes the Character link in U27.

**U40 Switching character follows the page.** As a player, I want switching characters in the top bar to show the same page for the new character, so I'm never left looking at the character I just switched away from. *(player_characters, accounts)*
- On a page about one of my characters (its sheet, its ledger, its edit page, its printouts), switching goes to the same page for the newly selected character. Edit pages go to the new character's sheet instead, so an unsaved form is never pre-filled for the wrong character.
- On any other page (shops, quests, map, and so on), switching stays on the page and reloads it for the new character.
- The "Acting as <name>" success message is dropped, because the top bar already shows the new character.

**U41 Only show what I can use.** As anyone in a club, I want the club home and lists to show only the tiles, links and columns I may use, so I don't run into pages or headings meant for someone else. *(accounts, site-wide)*
- The club home shows a tile only when the person may open the page it links to. For example, Agent access shows only to game masters and club admins, and admin-only tiles show only to club admins.
- The People page hides the Email column, header included, from anyone who can't see emails (U17 allows club admins only).
- A player's XP table tile opens the read-only table; only club admins see edit controls.

## Round 4: stories from the fourth look (2026-11-12)

From using the build after round 3 (U36–U41, M18) landed.

**U42 Item cards worth keeping.** As a player, I want each printed item card to show the item's icon, value, owner and print date, so a card is useful at the table on its own. *(player_characters, items)*
- Each catalogue item gets an optional emoji icon, picked by a club admin on the item form, like a shop's symbol. The card shows it next to the item name. The icon also shows next to the item name in inventories, shop tables and the catalogue.
- The card shows the item's base value (U8, U30), even when it is zero.
- The card has a footer with the character who owned the item when it was printed and the print date, for example "Aria Windrunner · printed 2026-11-12".
- The card never overlaps the browser's own print header and footer, in any layout (all cards, full page, or one grid spot). The print pages leave room for them, or remove them where the browser allows, and the 3 by 3 grid of 2.5 in by 3.5 in cards still fits on a portrait Letter or A4 page.
- This adds to U38.

**U43 Shopkeeper name and description in the banner.** As a player, I want the shopkeeper's name above their silhouette and the shop's description on request inside the banner, so the banner reads like a storefront and the table stays near the top. *(shops)*
- The keeper's name label sits above the silhouette instead of below it.
- A "Show description" button sits just above the "Sell to <keeper name>" button. It shows the shop and keeper descriptions in a box in the middle of the banner, next to the silhouette. The box is centred in the banner; the text inside it is left-aligned. Pressing the button again ("Hide description") hides the box.
- The descriptions no longer show below the table. Without JavaScript, the description stays visible in the banner.
- On a phone, the box shows below the silhouette, inside the banner, and nothing scrolls sideways.
- This changes U37.

**U44 Your character on the shop page.** As a player, I want my selected character's coins and inventory always visible on a shop page, so I know what I can afford and what I could sell without opening Buy. *(shops, player_characters)*
- A "Your inventory" card below the table of items to buy shows the selected character's name, coins (held and available, as on the sheet), and a compact list of their items with quantities and what this shop would pay for each.
- The card shows the junk total and what this shop would pay for the junk (U45).
- With no selected character, the card says so and links to create one. Game masters and club admins see their own selected character here, like any player.

**U45 Junk to sell.** As a player, I want to mark items in my character's inventory as junk and sell them quickly, so I can clear out loot I don't want without selling items one by one. *(player_characters, shops, quests, ledger)*
- On the character sheet, each inventory item can be marked as junk with a quantity, from one up to the number owned. Marking and unmarking needs no approval and never changes the ledger. Only the character's owner, game masters and club admins can mark junk.
- If the character later owns fewer of an item than are marked, the junk quantity drops to match.
- Wherever the character's coins show (sheet, shop "Your inventory" card, buy modal), a junk line shows the total base value of the junk next to them, for example "Junk: 42 gp".
- On a shop page, the junk line also shows what this shop would pay for all the junk, using the shop's buy prices (S1).
- A "Sell junk" button on the shop page opens a modal listing every junk item with its quantity and this shop's price. All are ticked. The player can untick items or lower a quantity to keep them for another shopkeeper who pays more. Confirming sells the ticked items through the normal sell rules and ledger, and shows the total received.
- A junk item that an open quest (Q1, Q2, Q3) asks for, and that this character can still complete, shows a warning, for example "Needed for quest: Wolf hunt". The warning shows on the sheet and in the Sell junk modal, and that item starts unticked in the modal.

**U46 Quest notice board.** As a player, I want the quest pages to feel like a notice board in a town square, so quests feel like jobs posted for adventurers, not another shop. *(quests)*
- The quest list is a board, for example a wood or cork background, with each open quest pinned to it as a paper notice: title, short description, reward (coins and items), what to bring, and the end date if there is one.
- A notice shows whether the selected character can turn it in now, for example a "Ready to turn in" stamp, and whether this character has already completed it as many times as allowed.
- Ended or full quests are left off the board, or shown faded in a separate "Taken down" section.
- The quest page looks like the same notice, enlarged, with the turn-in action below it. Game master and club admin edit actions sit outside the notice.
- It uses the design system and works on a phone, with notices in one column.

**U47 Shop street.** As a player, I want the shops page to show a little town street with a building for each open shop, so visiting a shop feels like walking into town. *(shops)*
- The shops page draws a simple street with one building per open shop. Each building shows the shop's name on a sign and its symbol, in the shop's colour. Clicking a building opens the shop.
- The street is deterministic: the same shops always appear in the same order and look, with no randomness on reload. A club admin can set each shop's position on the street.
- A club admin picks each shop's building shape from a set of preset shapes on the shop form, with a preview, like the keeper silhouette (U34). The app ships 8 to 10 original, generic building shapes, for example a timber inn, a stone smithy, a mage's tower, a market stall, and a tent.
- On a phone, the street wraps into several rows of buildings, with no sideways scroll.
- Screen readers and keyboards get the same links in a plain list. Closed shops are not drawn.

**U48 Club ledger.** As a game master or club admin, I want one ledger for the whole club, with filters, so I can see what happened across all characters without going through each character's history. *(ledger)*
- The Ledger page, for game masters and club admins, shows every ledger entry in the club, newest first, with date, character, player, what changed (coins and items), kind (award, purchase, sale, player shop, quest turn-in, quest reward, consumed, adjustment, reversal), note and who recorded it.
- Filters for character, player, kind, item, who recorded it, and a date range. Filters combine and stay in the page address, so a filtered view can be shared or bookmarked. The list is paged.
- Each entry links to the character's sheet and to the entry's source where there is one (quest, batch, message).
- A character's own history page stays for players (C5). Its back link returns to where the person came from: the club ledger, or the character sheet.
- Players do not see the club ledger. Their Ledger link opens their selected character's history.

**U50 Character level.** As a player, game master or club admin, I want to record a character's level, so everyone can see roughly how experienced a character is. *(player_characters)*
- Each character has an optional level, a whole number from 1 up. It is not tied to XP (M11, M13) or anything else in the app.
- The character's owner, game masters and club admins can set it on the character's edit form.
- The level shows in the character directory, in All characters, and in the character sheet header.

**U51 Small fixes from round 3.** *(map, player_characters)*
- The map request page shows "Map: … Tile: … Location: …" once, not in both the page header and the card header.
- In the character directory, names that link to a sheet look like links; names without a link look like plain text.

## Round 5: stories from the fifth look (2026-11-12)

From using the build after round 4 (U42–U51) landed. Kept as built: the keeper's name placement in the shop banner (U43) and the quest notice board style (U46).

**U52 A full street.** As a player, I want the shop street to fill the width of the page with buildings, so it looks like a real town street and not two houses on an empty road. *(shops)*
- Each street row has a fixed number of building lots for the screen width, for example 8 at desktop width and 4 on a phone. Every lot holds either a real shop or a filler building.
- Filler buildings are plain dark silhouettes, using the same building shapes, with no sign, no symbol and no link. Screen readers skip them.
- A shop's street position (U47) picks its lot, so gaps between positions become filler. For example, shops at positions 1 and 4 leave filler in lots 0, 2 and 3. Shops without a distinct position fill the next free lots in name order.
- Filler is deterministic: the same shops always give the same street, with the same filler shapes, on every load.
- When the open shops need more lots than one row holds, the street continues on another row, and that row is filled with filler to the full width too.
- On a phone, rows have fewer lots, and nothing scrolls sideways.

**U53 A blocky turn-in section.** As a player, I want the turn-in part of a quest page to be a solid card, like "Your inventory" on a shop page, so it is clear what my character has and what it still needs. *(quests)*
- Below the enlarged notice, a "Turn in" card names the selected character and lists each item the quest asks for, with its icon, how many are needed, and how many the character has, marking what is missing.
- The card shows whether the character can turn in now. The "Turn in" button sits at the bottom of the card and is disabled, with the reason, when it can't (missing items, quest full, or the character's limit reached).
- With no selected character, the card says so.
- Quest notices on the board and the quest page show item icons (U42) next to item names.

**U55 Leave the shop.** As a player, I want a "Leave" button on the shop page, next to "Sell to <keeper name>", so I can walk back to the street. *(shops)*
- "Leave" goes back to the shop street (U47). It is a secondary button, so Sell stays the main action.

**U56 Confirm before selling a keeper.** As a player, I want to confirm before selling an item I haven't marked as junk, so I don't sell something I meant to keep by mistake. *(shops)*
- Selling an item that isn't marked as junk (U45) opens a confirm modal: the item, quantity, price, the character, and a note that the item isn't marked as junk. Confirming sells it; cancelling sells nothing.
- Selling an item that is marked as junk, up to its junk quantity, needs no extra confirm. Selling more than the junk quantity asks for confirmation, like a non-junk item.
- The "Sell junk" modal (U45) already confirms, so it is unchanged.
- Without JavaScript, the confirm step is a plain page.

**U57 Compact inventory actions.** As a player, I want the actions on each inventory row to sit side by side as small icon buttons, so the inventory stays compact and easy to scan. *(player_characters)*
- On the character sheet's inventory, the row actions ("Junk" and "Print card") sit side by side on one line, never stacked.
- Each is a small icon button: for example a trash-can or tag icon for Junk, and a printer icon for Print card, from the app's existing icon set. Print card keeps its menu for "Full page" and "Grid spot".
- Each button has a tooltip on hover and keyboard focus ("Mark as junk", "Print card"), and the same text as its accessible name for screen readers.
- Any future row actions follow the same pattern.

**U58 A tighter top bar with icon links.** As anyone in a club, I want the top bar to stay compact at every width, with my most-used pages as icon links that are always visible, so I can move around without opening a menu. *(site-wide)*
- Character, Shops, Quests and Map are icon links in the top bar, each with its icon, a tooltip, and its name as the accessible name. At wide widths each shows its icon and its label; as the bar narrows, the labels drop first and the icons stay.
- These links stay visible at every width and only move into the hamburger menu if they physically do not fit, for example on a very narrow phone.
- The More menu becomes a "Menu" with every player page, grouped under headings. The icon links are shortcuts: each of them also appears in its group in the Menu, so the Menu is the full list. The groups:
  - **Character:** My character, Character directory, New character, and Ledger (my character's history).
  - **Town:** Shops and Quests.
  - **Map:** Map, Map requests, and XP table.
  - **Club:** People, Items, and Message the admins.
  - **Account:** Log out, last, below a divider.
- At desktop width, the Menu opens as one wide dropdown with the groups in columns. On narrow screens, the same groups show as headed sections inside the hamburger menu. A group with no links the person may use is hidden.
- The Game master and Club admin menus stay separate menus, as today. "Agent access" moves from More into the Game master menu, since only game masters and club admins can use it.
- When the bar wraps to two rows, the rows sit tight together: no empty band beside the brand or the hamburger button, small even padding, and the hamburger button lines up with the other controls instead of sitting tall on its own. The whole bar is as short as it can be at each width.
- Log out moves into the Menu's Account group. The other always-visible items from U32 (club, user, character, approvals) stay visible, and nothing scrolls sideways.
- This changes U27 and U32.

## Round 6: stories from the sixth look (2026-11-12)

From using the build after round 5 (U52–U58) landed. Kept as built: a phone street whose second row is all filler buildings is fine (U52).

**U59 A one-row top bar with a side menu.** As anyone in a club, I want the top bar to always be one row, with a hamburger button on the far left that opens a menu from the side, so the bar never wastes space and every page is one tap away. *(site-wide)*
- The top bar is always one row, at every width.
- The hamburger button is always shown, on the far left. It replaces the "Menu" dropdown (U58). It opens a panel that slides in from the left side of the screen, holding the same groups as the Menu: Character, Town, Map, Club and Account, plus the Game master and Club admin groups for those roles.
- The "West Marches" brand is removed from the top bar. The current club's name takes its place, next to the hamburger button, and still opens the club switcher. The app name can stay in the page title and in the side panel's header.
- As the bar gets narrower, items leave the bar in a fixed order and are reached through the side panel instead, which always lists every page. The order: shortcut labels first (icons stay), then the shortcut icons from the right (Map, Quests, Shops, Character), then the user's name shrinks to their initials chip. The hamburger button, the club name (shortened with an ellipsis if needed), the selected character and the approvals indicator stay in the bar at every width.
- The Game master and Club admin dropdowns leave the top bar; their links live in the side panel.
- This changes U27, U32 and U58.

**U60 Short gaps on the street.** As a player, I want at most two empty buildings between shops, so a big gap in street positions doesn't leave a long empty street. *(shops)*
- Between two shops in a row, and before the first shop, at most two filler buildings appear, however far apart their street positions are. Shops keep their order by position. U65 turns the two into a club setting, with a minimum as well.
- Filler after the last shop still fills the rest of the row (U52), and a second row that is all filler is fine.
- Ties in street position are broken by shop name, then by shopkeeper name (U62).
- This changes how U52 places shops.

**U61 A simpler shop page.** As a player, I want to sell from my inventory card right on the shop page and keep the banner tidy, so shopping is one page and the banner is all about the shopkeeper. *(shops)*
- The shop's symbol sits at the far left of the title row; the shop name stays centred on the page.
- The "Sell to <keeper name>" button and the separate sell page are removed. Each item in the "Your inventory" card (U44) gets its own Sell button, with the price this shop pays, using the same confirm rule as U56: items not marked as junk, or more than the junk quantity, ask to confirm. "Sell junk" (U45) stays on the card.
- "Show description" and "Leave" become icon buttons, each with a tooltip ("Shop description", "Leave the shop") and the same text as its accessible name.
- The shopkeeper's name label (U43) becomes a button. Pressing it shows the keeper's description. The description icon button shows only the shop's description.
- Both open a box in the same spot in the middle of the banner (U43). Only one box shows at a time: opening one closes the other, and pressing the same button again closes it.
- Without JavaScript, both descriptions show in the banner.
- This changes U34, U43, U44, U55 and U56.

**U62 Shop tie-break order.** As a club admin, I want shops with the same street position listed in a predictable order, so the street and shop lists don't depend on hidden details. *(shops)*
- When shops tie, order them by shop name, then by shopkeeper name. Use the same order everywhere shops are listed in order: the street, the shop list for admins, and rotations.
- The shop's internal id is used only as a last resort when name and shopkeeper name are both the same.

**S3 Create an item while adding stock.** As a club admin, I want to create a new catalogue item while I'm adding stock to a shop, so I don't have to leave the stock page to make the item first. *(shops, items)*
- On the add-stock form, next to the item picker, a "New item" button opens a modal with the item form (U42 fields, including the icon). Saving creates the item in the club's catalogue and selects it in the stock form, with nothing else on the form lost.
- The modal follows the same rules as creating an item from the catalogue page. Only club admins can use it.
- Without JavaScript, the button links to the new item page and returns to the stock form after saving.

## Round 7: new features (2026-11-12)

Ideas from the owner while round 6 was being built.

**U63 The app is called Downtime Market.** As a club admin, I want the app to have its own memorable name that says what it is for, D&D clubs whose players spend their loot between sessions, so it is easy to recommend and doesn't clash with names others already use. *(site-wide)*
- Everywhere the app names itself, it says "Downtime Market" instead of "West Marches": the browser tab title, the side menu's header (U59), the sign-in, signed-out and password pages, the design reference page, the MCP server's instructions and OAuth names (A1), the project description, and the README.
- "West Marches" stays where it means the style of campaign, not the app, for example "the West Marches XP table" (M13).
- The sign-in page has a one-line tagline under the name, for example "Spend your loot between sessions."
- The repository, folders and code names do not change.

**U64 Player shops.** As a player, I want my character to sell its junk from its own shop on the street, so other players can buy what I don't need while I'm away. *(player_characters, shops, ledger)*
- A player shop belongs to a character. On the character sheet, the owner, a game master or a club admin can switch "Sell my junk in my shop" on or off. It starts off.
- When it is on, the shop lists every item the character has marked as junk (U45), at the junk quantity.
- A character's shop shows on the street (U47) only while its switch is on and at least one item is listed.
- Another character buys an item at its base value (U8), and the whole price goes to the seller. The sale is instant: coins and the item move straight away, with no approval, and both characters' ledgers show it. The seller's junk mark drops by the quantity sold. The usual buy confirm (U31) and "can't afford" rules apply.
- A player can open their own characters' shops to see what is listed, but can't buy from them.
- Player shops have no rotations or open dates; they are open whenever they show on the street.

**U65 Player shops on the street.** As a player, I want player shops to look different from the club's shops and sit at the end of the street, so I can tell a player's stall from a real shopkeeper. *(shops)*
- Player shops come after all of the club's own shops on the street, ordered by character name. Filler then pads the row as usual (U52).
- A club admin sets three street settings for the club, each a whole number from 0 up:
  - **Minimum empty buildings between shops**, starting at 0: the fewest empty buildings between any two neighbouring shops, of any type.
  - **Maximum empty buildings between shops**, starting at 2: the most empty buildings between any two neighbouring shops, of any type, and before the first shop. This replaces the fixed two in U60. It can't be lower than the minimum; the form says so.
  - **Minimum empty buildings before player stalls**, starting at 1: the fewest empty buildings between the last club shop and the first player stall. Where this is higher than the maximum, it wins for that one gap.
- Between club shops, the empty buildings come from their street positions (U60), then are raised to the minimum or lowered to the maximum. Player stalls have no street positions, so neighbouring stalls get the minimum.
- Each player shop has its own look that is clearly not a club shop: for example a market stall with a striped awning, in one shared colour. The sign shows "<character name>'s stall".
- A player shop's page has no shopkeeper silhouette and no keeper name. Its banner shows the character's name and the stall look, then the table of listed items with Buy buttons, and the buyer's Your inventory card (U44) below.
- A player looking at their own character's shop sees "This is your shop", no Buy buttons, and a link to the character sheet to change what is listed.

## Round 8: stories from the seventh look and new features (2026-11-13)

From using the build after round 7 (U63–U66) and new ideas from the owner.

### Characters

**U67 A fuller character sheet.** As a player, I want my character sheet to hold the details my table uses, so the app can stand in for a paper sheet between sessions. *(player_characters)*
- New fields, all optional: the six ability scores (Strength, Dexterity, Constitution, Intelligence, Wisdom, Charisma), each its own whole-number field; class; species; alignment; pronouns; description; XP; AC; and Perception bonus.
- XP and AC are conveniences that players type. They are not tied to level (U50), the XP table (M13) or equipment.
- Passive Perception shows as 10 + the Perception bonus, with the formula, for example "Passive Perception 13 (10 + 3)". This follows D&D 5e (2014 and 2024): passive checks are 10 + the check's bonus.
- The app says "species", the D&D 2024 term, never "race".
- The Notes, Details and old free-text Stats fields are removed, and their text is dropped. The app hasn't launched, so there is nothing to keep.
- The sheet (U35) shows the new fields in sheet-style boxes: a header with name, level, class, species, pronouns and player; an abilities box with each score and its modifier; a box with AC, passive Perception and XP; and a description box.
- The edit character page looks like the sheet, with the same boxes holding the inputs.
- The edit form shows the saved value of every field beside its input, so a change is clear before saving. Each ability score shows its modifier, and a blank field shows an em dash.
- The character directory (U39, U49) shows class and species to everyone.

**U68 Character slips for drawing tables.** As a game master or club admin, I want to pick the characters at a session and print slips to cut out and draw, so we can make parties at random. *(player_characters)*
- A "Character slips" page for game masters and club admins lists every character in the club with a tick box, then prints a slip for each ticked character.
- Each slip shows the player's name, the character's name, pronouns, passive Perception, level, class and species.
- 12 slips fit on one portrait Letter or A4 page, in 2 columns and 6 rows, with cut lines. More characters continue on more pages.
- Players can print slips for their own characters from the sheet or the slips page.

**U69 Character page tooltips.** As a player, I want every button on the character page to explain what it's for, so I know which one to use. *(player_characters)*
- Each button has a tooltip on hover and keyboard focus, using this wording:
  - Edit: "Change this character's details: name, level, class, ability scores and more."
  - History and Full ledger: "See every change to this character's coins and items."
  - Print item cards: "Print cards for all items, nine to a page, to bring to the table."
  - Print sheet: "Print this character sheet in black and white."
  - Adjust: "Add or remove coins and items, for example loot from a session or a correction."
  - Consume: "Mark items as lost or used up, based on what happened during the session."
  - Hand over: "Give this character to another player."
  - Mark as junk: "Set aside items to sell later, in shops or your own stall."
  - Print card: "Print this one item's card, as a full page or in one spot of a card sheet."
  - Sell my junk in my shop: "List your junk in your own stall on the street for other players to buy."
- New buttons added later get a tooltip in the same style.

### Downtime

**D1 Downtime action points.** As a game master or club admin, I want to award characters downtime action points, so players have something to spend between adventures. *(player_characters, ledger)*
- Game masters and club admins award or remove points for one or several characters, with a note and a date, like coin awards (U14).
- Each character's points show on its sheet. Every award, removal and spend is recorded in the character's history and the club ledger (U48).

**D2 Downtime actions and reward tables.** As a club admin, I want to set up downtime actions, each with a table of weighted rewards, so spending a point gives a fun, varied outcome. *(new downtime area, items, ledger)*
- A downtime action has a name, a description, a cost in points (usually 1), and a table of entries. Example: "Work at a bakery" with 10 entries.
- Each entry has a label, a weight (a whole number from 1 up) and a reward: coins, one or more catalogue items, or nothing. An entry's chance is its weight divided by the table's total weight, and the form shows each entry's chance as a percentage.
- A player chooses an available action for their selected character (U25) and spends a point. The app picks an entry at random by weight, gives the reward straight away, and records it in the ledger.
- A character with too few points can't spend. Only club admins manage actions and tables.
- Downtime is a top-bar shortcut (U58, U59), with its own icon, placed before Map: Character, Shops, Quests, Downtime, Map. It also appears in the side menu's Town group. As the bar narrows, shortcut icons still leave from the right: Map, Downtime, Quests, Shops, Character.

**D3 The spinning wheel.** As a player, I want picking my downtime reward to be a little game, so spending a point feels exciting. *(downtime)*
- Spending a point shows a wheel with one slice per table entry, each slice sized by its weight and labelled. The wheel spins and stops on the entry the server already picked; the reward then shows.
- The result is decided on the server before the wheel spins, so the animation can't change it.
- With reduced motion turned on, or without JavaScript, the result shows straight away with no spin.

**D4 Requesting downtime action points.** As a player, I want to ask for downtime action points if my game master forgets to award them, so I don't miss out. *(downtime, player_characters)*
- A player asks for a number of points for one or several of their characters, with a note, like map credit requests (M12).
- A game master or club admin approves or declines. Approving awards the points (D1). Pending requests count in the approvals indicator (U24).

**U70 One agenda for rotations.** As a club admin, I want one agenda to plan which quests, shops and downtime actions are available on which dates, so I can see and change a season at a glance. *(shops, quests, downtime)*
- A club admin page shows a calendar-style agenda of what is available when: shop rotations (S2), quest start and end dates (Q2), and downtime action availability.
- Downtime actions have availability dates like quests: a start date and an optional end date. Only actions available today can be spent on (D2).
- From the agenda, an admin can add or change a rotation, a quest's dates, or a downtime action's dates, in a modal, without leaving the agenda.
- The existing rotations pages keep working; the agenda is the main way in.

### Items

**U71 Item rarity with suggested values.** As a club admin, I want to give each catalogue item a rarity and see a suggested value for it, so prices stay consistent. *(items)*
- The item form has a Rarity dropdown: Common, Uncommon, Rare, Very rare, Legendary. It is optional.
- Choosing a rarity shows its suggested value range from the 2014 Dungeon Master's Guide: Common 50–100 gp, Uncommon 101–500 gp, Rare 501–5,000 gp, Very rare 5,001–50,000 gp, Legendary 50,001 gp and up. It is a hint only; any value can be saved.
- Rarity shows in the catalogue and on the item page.

**U72 How many characters own each item.** As a club admin or game master, I want to see how many characters own each item, so I can spot items nobody uses. *(items)*
- Each row of the admin item catalogue shows how many characters in the club own at least one, and the total quantity they hold. Retired items show their counts too.
- It counts characters, not players. Players' read-only item list doesn't show the counts (U17).

**U73 Where can I buy this item?** As a player, I want to see where an item is for sale, so I can seek out what I need. *(items, shops)*
- In both item lists (the admin catalogue and the players' item list), an item for sale right now shows a shop icon button with a tooltip.
- "For sale" means in stock at a club shop that is open today (S2), or listed in a player's stall (U64).
- The button opens a modal listing each shop and stall that has it, with the shop's symbol and name, the price there (the shop's sell price, or the base value at a stall), the quantity available, and a link to the shop. The player's own stall is marked "your stall".

**U74 Stock requests.** As a player, I want to ask the club admins to make something available to buy, so the shops can grow with what players want. *(accounts)*
- From the Club group in the menu, a player sends a free-text stock request as their selected character (U25), for example "I want to be able to buy some super cool armor!"
- It arrives in the admins' inbox labelled "Stock request", and the inbox can be filtered by it. Admins can mark it handled or closed. It has no Give buttons, since nothing is granted. It counts in the approvals indicator (U24).
- Club admins only, like the rest of the inbox (U13).

### Shops

**U75 Shop tidy-ups.** As anyone using shops, I want the shop pages and admin list to be easier to read. *(shops)*
- On the street, each sign sits below its building at every width, for club shops and player stalls alike. This changes U52's wide-screen layout.
- The Manage shops list shows street position, shopkeeper name, sell percentage and buy percentage as columns, so shops can be compared.
- The "Your inventory" card shows item icons (U42), and its Sell buttons are outline buttons, lighter than the red Buy buttons.
- A shop with no shop description shows no description button (as today), and the demo shops all have descriptions so the button can be tried.

### Site-wide

**U77 Small site fixes.** *(site-wide)*
- In the side menu (U59), Log out is pinned to the bottom of the panel like a footer and stays visible while the groups above scroll.
- On the character sheet, the Recent ledger entries box has a little more space above it, and Print sheet leaves the ledger out.
- On the character sheet, the single-card print menu (U57) opens over the page instead of being clipped inside the inventory table.
- Static CSS and JavaScript URLs carry a version or content hash, so browsers load new styles after every update without a hard refresh.
- The app has a favicon that fits Downtime Market, so browsers stop asking for a missing `/favicon.ico`.

## Round 9: stories from the eighth look (2026-11-13)

From using the build after round 8 (U67–U77, D1–D4). Kept as built: the spinning wheel (D3), and "Request downtime points" showing only to players (game masters and club admins award points themselves).

### Characters

**U78 Character sheet layout and centred pages.** As anyone, I want pages to use wide screens well, so nothing is squished or scrolls sideways. *(player_characters, site-wide)*
- On the character sheet at desktop width, Combat and Description sit side by side in one row, and Inventory goes below them at full width, with no sideways scroll bar.
- On wide screens, page content is centred, with even space on both sides, instead of sitting against the left edge. This applies to every page.
- The character directory's columns are, in order: name, species, class, level, player.

**U79 Nicer character slips.** As a game master, I want the character slips (U68) to look as good as they work, so drawing tables feels like part of the game. *(player_characters)*
- Less white space and bigger text: the character's name is large, and the other details are easy to read from arm's length. Still 12 per page in 2 columns and 6 rows.
- A touch of visual flair that suits Downtime Market, for example a thin decorative border, a small emblem or the hourglass mark, and a parchment-style frame that still prints well in black and white.
- "Print slip" from a character sheet leads back to that character sheet, not to the slips page. From the slips page, it leads back to the slips page.

**U80 Track item uses on paper and in the app.** As a player, I want to tick off uses of an item on its printed card and then record them in the app, so potions and other consumables stay accurate. *(player_characters, items, ledger)*
- A printed item card for an item with a quantity above one has a "Used" section: one circle per item, for example five circles for five healing potions, to tick with a pen.
- Players get a "Consume" icon button in the sheet's inventory table, beside Mark as junk and Print card, with the tooltip "Mark items as lost or used up, based on what happened during the session." Players can consume their own characters' items without game master or admin approval. The button opens a confirm modal, for example "Are you sure you want to consume 1 Healing potion?", with a quantity and an optional note. Confirming records it in the ledger as a consume by that player.
- When anyone consumes or adjusts a character's items or coins (Consume, Adjust, or the player's Consume), the form shows that character's recent consumes and adjustments, from the last 30 days, by anyone, with date, who, what and note. This helps avoid recording the same use twice.

### Items

**U81 Pricing guide for everyday goods, and reference items.** As a club admin or game master, I want rarity bands for non-magical goods and nearby prices to compare against, so I price everything fairly. *(items)*
- The rarity dropdown (U71) has two groups. **Magic items**, from the 2014 Dungeon Master's Guide: Common 50–100 gp, Uncommon 101–500 gp, Rare 501–5,000 gp, Very rare 5,001–50,000 gp, Legendary 50,001 gp and up. **Everyday goods**, for non-magical items: Trivial 1–9 cp (a loaf of bread, a torch), Cheap 1–9 sp (a day's rations, a waterskin), Standard 1–10 gp (rope, a shovel), Fine 11–100 gp (a longsword, a riding horse), Luxury 101–1,000 gp (a fine carriage, a small boat), Exotic 1,001 gp and up (plate armour, a warship). A third group, **Special**, is for things that are hard to value, such as deeds, heirlooms and titles; it shows no suggested range.
- Choosing a band shows its suggested range, as today, with its examples.
- The item form shows reference items from the club's catalogue with their prices: items in the same band, and the items closest in value to the value being typed, up to about ten, updating as the value or band changes. There is also a quick search, so a game master can look up "bread" and "bacon" before pricing a sandwich.

### Downtime

**D5 Easier downtime points.** As a player, game master or club admin, I want requesting and awarding downtime points to be quick, so it happens right after a session. *(downtime, player_characters)*
- On the character sheet, next to the downtime points line, the character's owner sees a "Request points" link with the line "Earned downtime during a session? Ask your game master for the points." It opens the request form (D4) with that character picked. Game masters and club admins don't see it.
- Game masters and club admins award points to many characters at once: a list of every character in the club with tick boxes, like the character slips page (U68), with select all and clear, plus the number of points, a note and a date. One click awards them all. This replaces or reworks the D1 award page.

**D6 A themed Downtime page.** As a player, I want the Downtime page to have its own look, as distinct as the shop street (U47) and the quest board (U46), so choosing how to spend my time feels like part of the town. *(downtime)*
- The page looks like a tavern chalkboard of odd jobs: a dark slate board in a wooden frame, with each available downtime action chalked on it, its cost, a short description and its possible rewards. It must feel clearly different from the quest board's pinned parchment notices.
- Each action has a "Take the job" button (spending a point, D2), which opens the spinning wheel (D3) as today. The hourglass from the top-bar icon can appear as a small chalk motif.
- Text stays readable (light chalk text on dark slate with enough contrast), it works on a phone with one job per row, and it prints plainly.

**D7 Downtime rewards in the ledger.** As anyone reading a ledger, I want rewards from downtime to name the action, so I can see where an item or coins came from. *(downtime, ledger)*
- In a character's history and the club ledger (U48), an entry from a downtime reward reads, for example, "Downtime: Work at a bakery", and links to the result.
- The club ledger can be filtered to downtime entries.

### Branding

**U83 A Downtime Market wordmark.** As anyone, I want the app's name to have its own distinctive look everywhere it appears, so Downtime Market feels like a brand. *(site-wide, player_characters)*
- "Downtime Market" uses one distinctive display font, chosen by the owner: IM Fell English SC, an open-licence (SIL OFL) font with the look of an old printed book. It is self-hosted with the app's other fonts, not loaded from a third-party site.
- It is used wherever the name appears: the side menu header (U59), the sign-in, signed-out and password pages (U63), and the item cards. Page text and headings keep their current fonts.
- Each printed item card (U42, U80) has a small "Downtime Market" header at the top in the wordmark font, above the item's icon and name, and it prints well in black and white.

### Initiative

**U82 A UI consistency pass.** As anyone using the app, I want every screen and workflow to look and behave consistently, so the app feels finished. *(site-wide)*
- A separate initiative, like the design overhaul (U33), that goes through every screen and workflow for players, game masters and club admins, at desktop and phone widths: layouts, page widths and centring, spacing, buttons, tables, modals, empty states, tooltips and wording.
- It starts with an audit, with screenshots, of every page and the main workflows (buying, selling, junk, quest turn-ins, downtime, inbox, awards, agenda), and lists the problems found, ranked.
- It fixes them in small pieces, each with before and after screenshots, and keeps the console-error sweep clean.
- It doesn't add features or change how things work, only how they look and read.

## Round 10: stories from the ninth look and new features (2026-11-13)

From using the build after round 9, plus new print designs and public pages. Story numbers continue from U83, D7 and M18. The UI consistency pass (U82) audit did not cover the modal scrolling or the reward table, so U84 and D8 stand.

### Fixes

**U84 Tall modals scroll.** As anyone, I want a modal taller than my window to scroll, so I can reach every field and the Save button. *(site-wide)*
- The shared modal scrolls its body when the content is taller than the window, with the header and footer staying visible (for example Bootstrap's `modal-dialog-scrollable`).
- Checked on every modal that can get tall: agenda event edits (for example the quest "Pelts for the Tanner"), quest and rotation forms, downtime action tables, gives, and sell junk, at desktop and phone widths.

**D8 A clearer reward table when editing downtime actions.** As a club admin, I want each entry in a downtime action's reward table to stand apart, so I can pick out one entry from the next. *(downtime)*
- Each entry is its own bordered block, with its label, weight and chance, and its rewards (coins and items) grouped inside it.

**D9 Downtime ledger entries have no link.** As anyone reading a ledger, I want a downtime entry to just name the action and the result, because the result page spins the wheel again. *(downtime, ledger)*
- This replaces the link in D7. The entry reads, for example, "Downtime: Work at a bakery: Baker's thanks (+5 gp)", with no link. The club ledger filter for downtime entries stays.
- If a result page is still needed anywhere, it shows the stored result without spinning.

**D10 Tabular reward lists on the Downtime page.** As a player, I want each action's possible rewards on the Downtime page (D6) as a small table, so they are easy to read through. *(downtime)*
- Columns: outcome text, reward, and chance. This also shortens the long lists noted in the audit.

### Map

**M19 The map fits on one screen, with coordinates on tiles.** As anyone looking at a map, I want to see the whole map at once and read tile positions at a glance. *(map)*
- At its default zoom, the whole map fits in the window without scrolling, at desktop and phone widths, scaling tiles down as needed.
- Each tile shows its coordinates (column, row) in small text.

### Characters

**U85 A tidy printed character sheet.** As a player, I want the printed sheet to be as tidy as the screen, so it is usable at the table. *(player_characters)*
- The print layout keeps the same box grid, aligned columns and readable text sizes, on one page where possible.
- Tooltips, such as "Print this character sheet in black and white.", and anything else interactive never print. This applies to every printed page.

**U86 Max HP.** As a player, game master or club admin, I want to record a character's maximum hit points, so the sheet holds it with AC. *(player_characters)*
- An optional whole number from 1 up, editable on the sheet-style edit page (U67) by the owner, game masters and club admins.
- Shown in the sheet's Combat box with AC, passive Perception and XP. Current HP is not tracked.

**U87 Character slips as fantasy tickets.** As a game master, I want the slips (U68, U79) redesigned as adventurer's passes, still 12 per page (2 × 6, about 4.25 × 1.8 in each). *(player_characters)*
- Double border and notched corners, with no tear-off stub. A dashed, notched divider splits the slip.
- Main part: "✦ adventurer's pass ✦" across the top; the character's name large in the wordmark font (U83); pronouns; "played by <player>" with the player's name in bold; two centred rows of labelled pills, row 1 Species, Class, Level and row 2 AC, Passive Perc., Max HP (U86); a blank field's pill is left out; "Downtime Market" small at the bottom.
- Right-hand panel: the six ability scores as blocks in a 2 × 3 grid (label, score, modifier).
- Prints in black and white with readable text sizes at 12 to a page.

**U88 Item cards in the slips' style, with separate copies.** As a player, I want printed item cards (U42, U80, U83) to match the slips, and to print one card per item when I want to hand them out. *(player_characters, items)*
- Same size, 2.5 × 3.5 in, and 3 × 3 sheet as today. Double border and notched corners; "✦ downtime market ✦" across the top in the wordmark font; the item's icon, then its name large in the wordmark font; labelled pills for Rarity, Value and Qty (a blank pill is left out); a dashed line, then the description, traits and details; a dashed line, then the "Used" circles (U80, one per item when the quantity is above one); a footer with the owner and print date.
- Players choose "One card per item type" (one card with the full quantity and that many Used circles) or "One card per item" (one card per item owned, each with Qty 1 and a single Used circle). The choice is offered for Print item cards (all) and for a single item's Print card, beside the Full page and Grid spot layouts. Cards fill 3 × 3 sheets, continuing onto more pages.

**U89 Base value in Your inventory.** As a player, I want the "Your inventory" card on a shop page (U44, U61) to show base value, so I can compare it with the price this shop pays. *(shops, items)*
- A "Base value" column (U8, U30) after the item name and before the quantity.

### Items

**U90 Print loot cards.** As a game master or club admin, I want to print a batch of item cards from the catalogue to hand out as loot. *(items)*
- A "Print loot cards" action on the catalogue opens a picker listing catalogue items, each with a quantity box (0 by default) and a search filter.
- The same "One card per item type" or "One card per item" choice as U88, with the U88 card design. The footer says "Loot" and the print date, not an owner.
- Nothing changes in anyone's inventory; the loot is recorded later as usual (awards, gives or agent batches). 3 × 3 per page, continuing onto more pages. Game masters and club admins only.

**U91 Magic item type.** As a club admin or game master, I want each catalogue item to have a magic item type, so wondrous items and the other kinds can be told apart. *(items)*
- An optional field: Armor, Potion, Ring, Rod, Scroll, Staff, Wand, Weapon, Wondrous item, or none for non-magical items. Treasure themes from the 2024 rules are left for later.
- Shown on the item page and the item card (U88) as a pill, and filterable on the catalogue.

### Public pages

**U92 About and Plans pages.** As a visitor, I want pages that explain what Downtime Market is and what it costs, so I can decide whether to use it. *(site-wide)*
- Public pages, outside any club: "About" says what the app is; "Plans" describes a free plan for limited use and a paid subscription for heavier use, to pay for servers and compensate the owner.
- The limits and prices are still to be decided, so they live in one place that is easy to change. No payment processing yet.

**U93 "Built with CodeHerder" footer.** As the owner, I want a small "Built with CodeHerder" note in the footer of the public pages, not club pages. *(site-wide)*
- Easy to remove if the CodeHerder team would rather not be advertised this way.

## Round 11: stories from the tenth look (2026-11-15)

Story numbers continue from U93. U94 replaces the public-only note in U93.

### Site-wide

**U94 A small footer on every page.** As the owner, I want a small footer on every page with copyright and credits, so the app carries its attribution everywhere. *(site-wide)*
- Every page, including club pages, has a small footer: "© 2026 Vaughn Bernard" and "Designed by Vaughn Bernard, built by CodeHerder". On desktop the copyright sits on the left and the credit on the right; on a phone they stack and centre. It stays small (about 12 px, muted text, a hairline rule above).
- "CodeHerder" links to https://codeherder.com/, with a self-hosted copy of the CodeHerder favicon as a small icon beside it (no request to a third-party site). The link text carries the name; the icon is decorative.
- The footer never prints: hidden on printed sheets, slips, item cards, loot cards and the map print.
- The copyright, credit, link and icon live in one footer partial, so they are easy to change or remove. Before release, the owner confirms the CodeHerder team is okay with the credit, link and favicon.
- This replaces the "Built with CodeHerder" note on public pages (U93).

### Items

**U95 Item details in a modal.** As anyone, I want to open an item's details from a small "i" icon beside its name, wherever the name appears, so I can check what an item does without leaving the page. *(items, site-wide)*
- The icon sits beside the item name in the shared item-name partial, so it appears in shops and stock, Your inventory, the character sheet, quests, downtime rewards, the ledger, consume, junk and sell confirms, the catalogue and the print pickers. The name itself is not a link.
- The modal shows the item's icon, name, rarity, magic item type (U91), value, description, traits and details, and for game masters and club admins the GM-only details (U96). It opens in the shared modal, and the item page is its plain fallback without JavaScript.
- The icon has a label such as "Details for Healing potion", is reachable by keyboard, and opening it does not trigger the row's other actions (for example selecting or buying).

**U96 GM-only item details.** As a game master or club admin, I want a private section on an item for secrets, such as a curse, so players only see what their characters know. *(items, agent_access)*
- An optional "GM-only details" text field on each catalogue item, edited on the item form.
- Only game masters and club admins see it: on the item page, in the item modal (U95), the edit form and the catalogue. Players never see it anywhere, including the modal, printed item cards and loot cards, shop and inventory pages, and responses to players.
- A game master's agent can read and propose the field like other item fields (A5). Everything else about an item is visible to players.

## Round 12: Starting Equipment Player Stories

Stories for the player experience of starting equipment: automatic grants on character creation, background field, coin animation, and magic item requests.

**U97 Automatic Starting Equipment.** As a player, I want my new character to receive starting equipment and coins automatically based on their class, background, and level, so I don't need to ask an admin for basic gear. *(player_characters, starting_equipment, ledger)*
- Matching uses the character's class-option and background-option FKs against the active template's entries (case-insensitive by club-scoped name).
- Starting coins come from the level coins table per the configured template.
- Approved magic item requests are granted as part of the starting equipment.
- Applying starting equipment returns additive reason codes (`no_template`, `empty_template`, `class_missing`, `class_custom`, `class_no_entry`, `class_level_not_covered`, `background_missing`, `background_custom`, `background_no_entry`). Unmatched or custom values surface as warnings instead of blocking a grant.
- When the active template has choice groups for the character's class/background, the player is sent to the choices page to pick one option per group before the single "Starting equipment" ledger entry is granted. Templates without choice groups grant the default pick immediately.

**U98 Background Choice.** As a player, I want my character's background to be a club-defined option during creation, so my starting equipment includes background-appropriate gear. *(player_characters)*
- The Character model links `background` to a `Background` option (FK, optional) for starting-equipment matching; the free-text `background` CharField remains only as a display fallback.

**U99 Coin Animation.** As a player, I want to see a fun coin animation when I first view my new character, so the starting gold feels rewarding. *(player_characters)*
- The animation is triggered by the `?starting_equipment=1` query param.
- It respects `prefers-reduced-motion` and shows the result straight away when reduced motion is on.

**U100 Request Magic Starting Item.** As a player, I want to request a magic item as starting equipment, so I can start with a special item if my admin allows it. *(player_characters, starting_equipment)*
- A modal item picker lists only items flagged as `MagicItemStartingOption`.
- Requesting creates a `StartingEquipmentRequest` with `PENDING` status.
- The request appears in the club admins' and game masters' inbox for approval.

**U101 Magic Request Status.** As a player, I want to see the status of my magic item request on my character sheet, so I know if it was approved or declined. *(player_characters, starting_equipment)*
- The status is rendered via an HTMX partial (`_status_row.html`).
- It shows `PENDING`, `APPROVED`, or `DECLINED` with the admin's decision note.

### Technical Decisions (Clarifying Stories)

**D1 Background field on Character.** As a developer, I want the Character model to keep a free-text `background` CharField (max 60, optional) as a display fallback, while starting-equipment matching uses the `background_option` FK to a club-scoped `Background`. *(player_characters)*
- Field: `background = models.CharField(max_length=60, blank=True)`
- Matching for gear grants uses `background_option` against `StartingEquipmentBackgroundEntry.background_option`; the free-text field is no longer used for matching.

**D2 Case-insensitive class matching.** As a developer, I want class matching for starting equipment to be case-insensitive by club-scoped name, so player-entered class names match admin templates reliably. *(starting_equipment, player_characters)*
- Matching uses `class_option` FK to a club-scoped `CharacterClass`; names are unique per club case-insensitively.
- Players can type class names freely; admin templates use canonical names.

**D3 Choice groups in data model.** As a developer, I want the data model to support choice groups (e.g., "Weapon A or Weapon B"), so the 2024 PHB equipment choices can be implemented. *(starting_equipment, items)*
- `StartingEquipmentClassLine` and `StartingEquipmentBackgroundLine` have `is_choice` and `choice_group` fields
- `get_choice_groups()` returns the groups a player must pick from; `apply_starting_equipment(picks=...)` grants one picked option per group.
- The player-facing choice UI is implemented: after character creation, the player picks one option per group on the `starting_equipment:choices` page before gear is granted.

**D4 Level-based coins table.** As a club admin, I want level-based starting coins to follow the 2024 DMG "Starting Equipment at Higher Levels" table, configurable per template, so higher-level characters start with correct wealth. *(starting_equipment)*
- Separate `StartingEquipmentLevelCoins` model with `level` (2-20) and `coins_cp` fields
- Seeded from DMG 2024 table; admins can customise per template
- Applied when character level > 1 during starting equipment grant

**D5 Player shops unchanged.** As anyone, I want player shops (U64/U65) to remain unchanged by starting equipment changes, so the safe player-to-player economy continues to work as before. *(shops, player_characters, starting_equipment)*
- Player shops continue to use fixed base value pricing (S1).
- Starting equipment changes do not affect player shop inventory, pricing, or street placement.
- Player shops remain the safe alternative for player-to-player trading.

## Round 13: Starting Equipment Admin/GM Stories

Stories for club admins and game masters to manage starting equipment templates and approve magic item requests.

**U102 Manage Starting Equipment Templates.** As a club admin, I want to create and manage starting equipment templates for my club, so I can customize what gear new characters receive. *(starting_equipment)*
- Admins create, edit, and delete templates for their club.

**U103 Configure Class-Based Equipment.** As a club admin, I want to configure class-based starting equipment (items, coins, choice groups) for each class and level range, so characters get class-appropriate gear. *(starting_equipment, items)*
- One class entry per class and level range; lines list items, quantities, coins, and choice groups. Class matching is case-insensitive (US4).

**U104 Configure Background-Based Equipment.** As a club admin, I want to configure background-based starting equipment, so characters get background-appropriate gear. *(starting_equipment, items)*
- One background entry per club-scoped Background option per template; entries link by FK only (no free-text snapshot).

**U105 Configure Level-Based Coins.** As a club admin, I want to configure level-based starting coins per the 2024 DMG table, so higher-level characters start with appropriate wealth. *(starting_equipment)*
- LevelCoins table per template, levels 2-20, from the 2024 DMG "Starting Equipment at Higher Levels" table.

**U106 Mark Magic Starting Options.** As a club admin, I want to mark specific magic items as available for starting equipment requests, so players can request them. *(starting_equipment, items)*
- MagicItemStartingOption flags catalogue items; feeds the player request picker (U100).

**U107 Approve or Decline Magic Requests.** As a club admin or GM, I want to approve or decline magic starting item requests from the inbox, so I control which magic items enter play. *(starting_equipment, accounts, ledger)*
- Pending requests appear in the club inbox (U28). Decisions set status and decision note; approved items grant with starting equipment (U97).

**U108 Set Active Template.** As a club admin, I want to set one template as active per club, so there's a single source of truth for starting equipment. *(starting_equipment)*
- Exactly one template per club is active; activating a template clears the active flag on the club's other templates.

**U112 Template Highlights Missing Class/Background Entries.** As a club admin, I want the template detail page to warn which active class and background options in my club lack a template entry, so I can prepare an inactive template before switching. *(starting_equipment)*
- The template detail lists active classes and backgrounds with no entry for this template.
- Archived class/background options are not warned about.
- The warning names the template so an admin can stage gear on an inactive template first.

**U113 Character Sheet Explains Missing Gear.** As a player, I want my character sheet to explain why some starting gear was not granted (custom class/background, no entry for the option, level not covered), so I know what to ask an admin about. *(player_characters, starting_equipment)*
- Creating or claiming starting equipment flashes each applicable reason code as a warning.
- The character sheet lists the missing-gear reasons when any apply; it omits the section when nothing is missing.


### Containers

**U109 Open a pack like a loot box.** As a player, I want to open a container item (such as a Diplomat's Pack) from my inventory and see a random set of items added to my inventory, so packs feel like loot boxes. *(items, player_characters, ledger)*
- Only the owner, a game master, or a club admin can open a container. The container is consumed (quantity −1).
- The server rolls the container's slots: each slot has a chance (1–100%), then a weighted "pick one" from its options, then a quantity in the option's range.
- One `opened` ledger entry is written: container −1, each rolled item +qty (merged by item). A `ContainerOpening` record stores the per-slot result for replay.
- A second open on the same container instance fails (no quantity left). Concurrency is handled by row locking.
- Nested containers are allowed (max depth 3, no cycles). A rolled container lands in inventory unopened.

**U110 Preview container contents with unknowns masked.** As a player, I want to see what might come out of a container before I open or buy it, with surprises shown as `???`, so I can decide whether it's worth it. *(items, shops, quests, starting_equipment)*
- The preview shows one row per slot: fixed items, ranges (1–4), percentage chances, and "One of" tables with weights.
- Slots flagged `unknown` show `???` with no item name, quantity, or options to players. Game masters and club admins see the real contents.
- The preview is used on the item details modal, inventory, shop buy cards, quest rewards, starting equipment, and award forms.
- All player-facing previews go through `loot_preview(viewer_can_see_unknown=False)`. Code never reads slots directly for players.

**U111 Configure container contents (admin).** As a club admin, I want to add, edit, and remove slots and options on an item, so I can model packs, treasure chests, and mystery boxes. *(items)*
- Only club admins can toggle `is_container` and manage slots.
- Form validates: chance 1–100, qty_min ≤ qty_max, weight ≥ 1, at least one slot, at least one option per slot, no cycles, max nesting depth 3, no retired items in options.
- Slots are ordered by `position`; options within a slot are weighted.

**U112 Seed 5e packs as containers.** As a club admin, I want a management command to turn existing 5e packs (Diplomat's Pack, Explorer's Pack, etc.) into containers with fixed slots, so characters who already own them can open them. *(items)*
- `manage.py seed_pack_containers --club <slug> [--dry-run]` is idempotent: a second run adds nothing.
- Only configures packs already in the club's catalogue; never creates pack items.
- Reuses content items by case-insensitive name; creates missing ones with 2024 PHB values.
- Skips packs that already have slots (admin edits preserved). Touches only the named club.
- No ledger writes, no inventory changes. `--dry-run` rolls back.
- Every seeded pack passes `validate_container_config`.

**U113 Agent sees container loot with unknowns masked.** As a game master's agent, I want `search_items` to return `is_container` and, for containers, `loot` rows from `loot_preview(..., False)`, so the agent can describe containers without leaking secrets. *(agent_access, items)*
- Container rows include `is_container: true` and `loot` array with masked unknowns (`???`, `unknown: true`, no item id or name).
- Non-container rows have `is_container: false` and no `loot` key.
- Other clubs' containers never appear.

**U114 Report bugs and suggest features.** As a player, I want to report bugs and suggest features for the app itself, so the people who run the app can hear about problems and ideas. *(accounts, site-wide)*
- Any logged-in user can send a bug report or feature request from any page, via a link in the footer.
- The report goes to the site admins, not to the player's club admins. Messages to club admins stay on the Message model.
- The form says plainly that it is for app problems and feature ideas, not for asking club admins for loot, corrections, or rulings.
- Reports are recorded with the page they came from and can be triaged (open, handled, closed) on the site-admin list at /site/feedback/.
- Sending is rate limited per user.

## Round 14: stories for features that were built without one (2026-11-20)

These features shipped in the week of 2026-11-13 to 2026-11-20 without a written story. Each story below describes what the build does today, so the next round can check it and change it.

### Character sheet

**U115 See my XP progress and when I can level up.** As a player, I want my character sheet to show how far my XP is toward the next level, and tell me when I have enough XP to level up, so I know when to update my character. *(player_characters)*
- Under XP the sheet shows slim progress, for example "6,500 / 14,000 XP to level 6", using the standard 5e XP thresholds.
- At level 20, or at the top XP threshold, it shows "Max level" instead.
- When the saved level is lower than the level the XP earns, a "Level up ready" badge appears and links to the edit form. The sheet never changes the level by itself.
- When XP is blank, nothing new shows.
- The progress bar and the badge link do not print.

**U116 New characters start with 10 in every ability.** As a player, I want the six ability scores to start at 10 on the new-character form, so I only change the ones that differ. *(player_characters)*
- The new-character form pre-fills Strength, Dexterity, Constitution, Intelligence, Wisdom and Charisma with 10. This is the same for players and for game masters or club admins creating a character for someone else.
- Players can change any score or clear it. A blank score still shows "—" on the sheet, the edit form and the slips.
- Characters made before this change keep their saved values, including blanks.

**U117 Sell junk from the character sheet.** As a player, I want a "Sell junk" button on my character sheet that asks which shop to sell in, so I can clear junk without walking the street first. *(player_characters, shops)*
- The button acts for the selected character. It opens a modal that lists the club's open shops in street order. Picking one continues into that shop's junk selling modal from U45.
- If only one shop is open, it goes straight to that shop's junk selling modal. If no shop is open, the modal says "No shops are open right now."
- Everything else follows U45 and U56: nothing sells until the player confirms.
- The button only shows when the character has at least one item marked as junk.

### Club home

**U118 A session desk for game masters and club admins.** As a game master or club admin, I want my club home page to show what is waiting for me and what to do after a session, so I do not have to open each page to find out. *(accounts)*
- The club home page shows a desk with three sections: "Waiting for you", "After the session" and "My character dashboard".
- "Waiting for you" uses the same pending approvals as the rest of the app, so the counts match the approvals page.
- Players without a game master or admin role see their player dashboard as before.
- A game master or club admin who has no character of their own is sent to the desk instead of an empty player dashboard.
- The layout works on a phone first.

### Shops

**S13 Closing soon ribbons.** As a player, I want shops that are about to leave the street to say so, so I can buy before they close. *(shops)*
- A shop leaves the street on the latest close date of its open rotations. If any open rotation has no close date, the shop never leaves.
- "Closing soon" means the leave date is within 3 days, counting the leave date itself.
- A club shop on the street shows a "Closing soon" ribbon. Player shops never show it.
- The shop page shows "Leaves the street on <date>" under the Closed badge area while the shop is open and closing soon.
- Dates use the house format, for example 24 Nov 2026.

**S14 Switch shops from the shop banner.** As a player, I want a shop picker in the shop banner, so I can move to another open shop without going back to the street. *(shops)*
- The picker sits next to "Leave" and lists the club's open shops in street order. The current shop is marked.
- Picking a shop swaps the page in place and keeps the scroll position. The acting character does not change.
- Each choice is a real link, so the picker also works without JavaScript. Back and Forward restore the shops visited.

**S15 Compare the price before I buy.** As a player, I want the buy confirmation to show how the price compares with the item's base value, so I can judge the deal. *(shops)*
- The modal shows the base value, the shop's sell percentage, and the price I pay.
- The percentage is the stock's own override when it has one, and the shop's default otherwise. The price is base value × percentage ÷ 100.
- It also shows the difference from base, for example "vs base: -2 gp" or "+5 gp".

**S16 A General Store on every new street.** As a player, I want every new club to start with a General Store run by Mabel Packwell, so I can buy and sell basic gear on day one. *(shops, items)*
- Keeper: Mabel Packwell (a halfling grocer).
- Sells at 100% of base value, buys back at 75%.
- Stocks every item from the 2024 PHB Adventuring Gear table plus ammunition (Arrows, Crossbow Bolts, Firearm Bullets, Sling Bullets, Needles), with unlimited quantity.
- Does not stock weapons, armor, tools, or magic items (Potion of Healing, Spell Scrolls are excluded).
- All stock rows have no quantity limit and no price overrides.
- The shop sits in an "Always open" rotation, so it shows on the street.
- Uses the general store building, the halfling grocer silhouette, and street position 0 (first on the street).
- The demo club has the same General Store beside its other shops.
- A management command `seed_general_store --club <slug>` adds the shop to an existing club.
- The command is idempotent and only runs when asked; a shop an admin deleted never returns on its own.
- Items a club already has (e.g., Ink (1 oz), Parchment (10 sheets)) are not changed, and no duplicate by name appears.
- If a shop named "General Store" already exists, the seeder skips it entirely.

### Quests

**Q5 Turn-in feedback and a preview of the reward.** As a player, I want to see what a quest pays before I turn it in, and to get a clear result after, so I know it was worth it and that it worked. *(quests)*
- The turn-in card lists the quest's reward (coins and items) under the requirements. It is hidden when the quest has no reward.
- After a turn-in, the player returns to the quest board, which refreshes by itself. A toast names the character, the quest and the reward.
- Without JavaScript, the player goes to the quest page and sees the usual message.

### Downtime

**D11 Replay the wheel, with some extra flair.** As a player, I want to watch my downtime result again and feel the near misses, so the spin is fun without changing the result. *(downtime)*
- The result modal has a "Spin again" button. It replays the wheel animation with the same stored result. It never rolls again.
- Slices the wheel nearly landed on glow briefly. Particles burst from the wheel's center when it stops.
- A sound toggle is off by default. The page remembers the choice in the browser.
- With no JavaScript, or with reduced motion, the result shows straight away.

### Site-wide

**U119 Support link in the footer.** As a visitor or player, I want a small link in the footer to support the app, so I can chip in if I want to. *(accounts, site-wide)*
- The standard footer, on public, club and sign-in pages, has a "Buy me a coffee" link to ko-fi.com.
- It is a plain link with an inline icon. It does not load the Ko-fi widget, because the content security policy blocks that script and image.
- The link is fixed in the page template, on purpose. The site admin does not set the address or turn it off. This is the donate button U11 asks for.

### Agent access

**A8 Agent tokens expire, and every use is logged.** As a game master, I want my agent's access token to expire, and as a site admin I want a log of what happened to each token, so a lost token stops working and I can see how it was used. *(agent_access)*
- A new token expires after `AGENT_TOKEN_EXPIRY_DAYS` days. The default is 365, and the setting can be changed.
- An expired token is refused and the refusal is logged.
- A log records each token's creation, use, revocation and expiry.
- The connections list shows an "Expires" column and an Active or Expired badge.
- The site admin can search and filter the log in Django admin.

### Site admin

**U120 Create a club with its first admin.** As the site admin, I want to create a new club and its first club admin in one step, so a new group can sign in and start using the app on day one. *(accounts, character_options, starting_equipment, shops, map)*
- Only the site admin sees the "New club" form. It asks for the club name, an optional slug, the first admin's email, and an optional display name for them.
- If the slug is left blank it comes from the name. A slug that another club already uses is refused with an error on the form.
- The new club is seeded with the XP table, the species, classes and backgrounds, the default item catalogue, an active "2024 D&D Default" starting equipment template, and a General Store run by Mabel Packwell. It gets no characters, quests, maps, downtime actions or messages. The game master creates those.
- The first admin is the email address typed, saved in lower case and matched without regard to case. Their email is also whitelisted for the club, so they can sign in.
- If no account has that email, the app creates one with a random temporary password. The "Club created" page shows the password once and the page is never cached. The app sends no email, so the site admin hands the password over. On first sign-in the person must choose their own password (U18).
- If an account with that email already exists, for example from another club, the form first says "This email already has an account." It explains that the person will become an admin of the new club and that their password will not change. Nothing is created yet. The site admin can change the email, or press "Create club" again to go ahead.
- After the site admin goes ahead, that account is not changed and no password is shown. The "Club created" page says "Existing user. Their password is unchanged." The person becomes a club admin of the new club and signs in as before.
- The club, the seed data and the admin are created together. If anything fails, none of it is kept.
- A lost temporary password is reset the same way as any other (U19).

**U121 Dashboard button in the top bar.** As a player, I want a Dashboard shortcut in the top bar that takes me back to my club's dashboard, so I can always reach it without opening a menu. *(accounts, site-wide)*
- The Dashboard button sits first among the icon shortcuts, before Character, Shops, Quests, Downtime, and Map.
- It shows for every signed-in club member, in the top bar and in the side menu's Character group.
- It is marked as the current page when the player is on the dashboard, and also for game masters and club admins on the club home page (which they see instead of the dashboard when they have no selected character).
- At wide widths it shows its icon and label. As the bar narrows, the labels drop first. Then the icons leave from the right: Map, Downtime, Quests, Shops, Character. Below 400 px only the Dashboard icon shows. The Dashboard icon never leaves.
- The character picker cuts a long character name short with an ellipsis. On a phone the club name is cut short, not hidden. The top bar never scrolls sideways, from 320 px to wide screens.
- Every shortcut keeps its tooltip and aria-label.
- This changes U32 (the club name, player name, character picker and approvals indicator must stay visible at 390 px) and U61 (the top bar is one row, never wraps).

## Round 15: item notes (2026-11-20)

### Character sheet

**U122 Notes on my inventory items.** As a player, I want to record my own notes on the items in my character's inventory, so I can add my own info to items I have gathered and remind myself about things concerning them. *(player_characters, items)*
- Each row in the sheet's inventory table has a "Notes" icon button, beside Consume, Mark as junk, and Print card. It opens a small form with one text box, a Save button, and a Cancel button. A row that already has a note shows a filled icon, and the note's first line appears on hover.
- A note belongs to one character and one item, like a junk mark (U45). A stack of three potions has one note, not three.
- Only the owner of the character can add, change, or clear a note. A game master or club admin who is not the owner sees the note on the sheet but cannot edit it. This matches who can see the inventory (U19).
- Saving an empty box clears the note. A note can hold up to 1,000 characters of plain text. The app shows line breaks and never runs HTML in a note.
- Notes are the player's own text. They never touch the ledger or the item catalogue, and no other character or club ever sees them.
- Buying, selling, consuming, or moving items does not change a note. If the character no longer has the item, the note is hidden. If the character gets that item again, the note comes back.
- The form works as a plain page without JavaScript, like the other inventory actions.

**U132 Choose Starting Equipment.** As a player, I want to pick one option for each starting equipment choice group when my character is created, so I get the gear I want for my class and background. *(player_characters, starting_equipment, ledger)*
- After saving a character whose active template has choice groups, the player is sent to the choices page and must pick one option per group before any gear is granted.
- Templates without choice groups skip the step and grant the default pick immediately.
- The picks, fixed items, and coins arrive in one ledger entry noted "Starting equipment".
- Reloading or resubmitting cannot grant gear twice; `starting_equipment_claimed` tracks the grant.
- A player who leaves can finish later from the character sheet via the "Choose starting equipment" link.
- Only the character owner, a game master, or a club admin can submit the choices.
- On success the player is sent to the gear reveal (`characters:starting_reveal`).

**U124 See my starting gear revealed.** As a player, I want to see my starting equipment revealed item by item with my starting coins counting up before my sheet opens, so claiming gear feels rewarding. *(player_characters, starting_equipment, ledger)*
- After the choices step (or straight after creation when there are no choices), the player lands on the gear reveal page (`characters:starting_reveal`).
- The reveal shows each granted item one at a time from the saved "Starting equipment" ledger entry, then counts the starting coins up from zero.
- It never rolls or changes anything: it only shows the stored entry, so reloading changes nothing.
- With `prefers-reduced-motion` on, everything shows at once and there is no auto-advance.
- A Skip link jumps straight to the sheet, a Replay button re-plays the reveal, and a screen reader hears the result in an aria-live region.
- When the reveal ends, the character sheet opens.

## Round 16: stacked items (2026-11-20)

A **stacked item** is sold in bundles but owned and used one unit at a time: parchment by the sheet, rope by the foot, arrows by the arrow. Each character holds one pool of units per stacked item. A stacked item is not a container: it never opens into other items.

Rules for every story in this round:

- Units are whole numbers, at least 1. Using the last unit removes the item from the inventory.
- A character has one inventory row per stacked item. Two stacks of the same item are one stack, so combining is automatic and there is no split or combine button.
- Every consume, sell, and set-aside action takes a unit count, up to the number owned.
- There are no trades or transfers between characters (see Decisions), so units never move from one character to another.

### Items

**U123 Define a stacked item.** As a club admin, I want to mark a catalogue item as stacked, with a unit name (sheet, ft, arrow), a value, and the number of units that value covers, so one item can be sold in different bundle sizes. *(items)*
- Example: "Parchment" has the unit "sheet" and a value of 1 gp for 10 sheets. "Rope" has the unit "ft" and a value of 1 gp for 50 ft. "Arrows" has the unit "arrow" and a value of 1 gp for 20 arrows.
- An item is either a container (U109-U112) or stacked, never both.
- Changing the value or the unit count changes future prices only. Nobody's unit count changes.

**U124 Turn an existing item into a stacked item.** As a club admin, I want to convert an existing catalogue item to a stacked one, so I do not have to recreate parchment and rope. *(items, player_characters)*
- Characters who own the item keep their quantity, now counted in units. The admin enters how many units one old item is worth, and the quantities are multiplied once, in one step.
- The conversion adds one ledger entry per affected character, with a note, and is refused if it would fail for any of them.

### Shops

**U125 Sell stacked items in bundles.** As a club admin, I want to stock a stacked item in a shop as one or more bundle lines, each with its own bundle size, stock, and optional price override, so a shop can sell arrows in bundles of 5 and bundles of 100. *(shops)*
- Each bundle line is its own shop line with its own stock count or "unlimited" (U9).
- The default price for a bundle is the item's value scaled to the bundle size, times the shop's sell percentage (S1), rounded up to whole copper in the shop's favor. A price override on the line still wins.
- Two bundle lines of the same item in one shop must have different bundle sizes.
- A shop line shows the bundle, for example "bundle of 100 arrows".

**U126 Buy a bundle and get its units.** As a player, I want buying one bundle to add all its units to my character's inventory, in the same row as any units I already have, so my arrows are one pile. *(shops, player_characters, ledger)*
- Buying a bundle of 5 and then a bundle of 100 gives 105 arrows in one row.
- Players buy whole bundles only, not part of a bundle (C2, C3 still apply to bundle stock).
- The ledger entry says the units bought, for example "bought 100 arrows".

### Characters

**U127 See units.** As a player, I want inventories, shops, ledger lines, and cards to show units with the unit name, for example "40 ft Rope", so I always know how much I have. *(player_characters, shops, ledger, items)*
- A printed item card shows the total units the character holds (U6).
- The note on an inventory row (U122) belongs to the item, not to a unit.

**U128 Use up units.** As a player, I want to consume any number of units of a stacked item, with a note, so my inventory matches what happened in play. A game master can do the same (U7). *(player_characters, ledger)*
- Example: consume 10 ft of a character's 50 ft of rope. The character keeps 40 ft.
- The player cannot consume more units than the character has.
- Consuming the last unit removes the item from the inventory. Its note hides and comes back if the character gets the item again (U122).

**U129 Sell and set aside units.** As a player, I want to set aside and sell any number of units, so someone with 500 ft of rope can sell 400 ft they do not need. *(shops, player_characters)*
- Setting aside uses the junk mark (U45) with a unit count. It is capped at the units owned.
- A shop that buys the item pays `floor(value × units sold × buy percentage ÷ the units the value covers)`, worked out once from the total units sold, never per unit. Selling in pieces never pays more than selling all at once.
- The confirm modal shows the units and the exact coins (S15).
- A player stall (U64) can list a number of units. Units sold from a stall leave the character's stack, and bought units join the buyer's stack.
- A bundle bought at a shop and sold straight back never earns a profit, as long as the shop's sell percentage is at least its buy percentage.

**U130 Award and adjust in units.** As a game master or club admin, I want to give and take units in manual adjustments, and have container drops, quest rewards, and agent batches use units too, so a character can find 3 more sheets of parchment in play without a whole bundle. *(player_characters, ledger, quests, agent_access)*
- Adjustments (U14) and awards record the unit count and a note, as new ledger entries.
- A container slot or quest reward can give any whole number of units, for example "2 sheets".
- The agent's item search shows each stacked item's unit name and the units its value covers (A2).

**U131 Quests take units.** As a player, I want a quest to ask for a number of units, such as "20 sheets of parchment", so stacked items work with quests like any other item. *(quests)*
- A turn-in uses up the units (the quest rules in Decisions still apply: all or nothing, only once the character holds everything).

## Round 17: club admins and game masters on the People page (2026-11-21)

Today a club admin can tick "Game master" when adding a person, but there is no "Club admin" box, and the People page shows roles without letting anyone change them. A new club starts with one admin, and adding a second one means using Django admin. These stories fix that.

Rules for both stories:

- Club admin and game master stay two separate permissions in a club (see Roles and permissions). A person can hold neither (a player), either, or both.
- Roles belong to one club. Changing them in one club never changes another.
- Only a club admin of that club can add people or change roles there. The site admin can do both in any club.
- The app still sends no email (round 20 changes this).

**U133 Add a club admin.** As a club admin, I want to tick "Club admin" as well as "Game master" when I add a person, so a co-organiser can manage the club from their first sign-in, without the site admin or Django admin. *(accounts)*
- The add-person form (U1) gets a "Club admin" checkbox next to "Game master". Both can be ticked together. With neither ticked the person is a player.
- Short help text under each box says what the role does: a club admin manages members, items, shops, and the inbox; a game master runs games and awards loot.
- Everything else about adding a person stays the same: a new account gets a one-time temporary password (U18), an existing account is only added to this club, and an email already in the club gets the "already a member" notice.
- The People page already shows a badge for each role, so a person with both roles shows both badges.

**U134 Change someone's roles.** As a club admin, I want to turn "Club admin" and "Game master" on or off for a member on the People page, so a player can be promoted later and one person can hold both roles. *(accounts)*
- Each member's row gets a "Roles" action that opens a modal with the two checkboxes and a Save button. It uses the same modal style as the other row actions (U19).
- A club must always have at least one club admin. Unticking the last club admin is refused with a clear message, so the last admin cannot demote themselves or be demoted.
- Changes apply on the person's next page load. They are not signed out.
- Removing a role never removes a person's characters, items, or ledger. Only what they are allowed to do changes.
- The password reset rules (U19) do not change.
- Each role change shows a confirmation message to the admin who made it.

## Round 18: player progress and quest hints (2026-11-21)

**U135 See my level progress and latest awards on the dashboard.** As a player, I want my dashboard to show my XP progress and the last things my game master gave me, so I know when to level up and what I got. *(accounts, player_characters)*
- The header shows slim XP progress, for example "6,500 / 14,000 XP to level 6", or "Max level", using the same rules as U115. A "Level up ready" badge links to the edit form. Blank XP shows nothing new. XP stays a tracker the player edits; no game master page changes it.
- A "Latest awards" card lists up to 5 recent awards (coins, items, downtime points), newest first, with date and note. It is hidden when there are none. Nothing here prints.

**U136 See my quest progress on the board.** As a player, I want each quest notice to show how many of each required item my selected character has, so I know what is left without opening every quest. *(quests)*
- Each requirement shows "have of need", for example "2 of 3 Wolf pelt". A short quest shows "1 more" and a slim bar. A ready quest keeps its "Ready to turn in" stamp.
- Without a selected character, no progress shows. Print Session Pack output does not change.

**U137 Warn before selling an item a quest needs.** As a player, I want a warning when I sell an item that a live quest still needs, so I do not sell quest items by mistake. *(shops, quests)*
- In the shop "Your inventory" table and in the sell confirm modal, an item needed by a live quest that the selected character has not finished shows "Needed for: <quest name>". The confirm modal adds a warning line.
- Selling still works. The warning never blocks it.

## Round 19: play sessions, character death and archiving (2026-11-21)

Two new epics. The first adds play sessions to the club. The second lets a character die or be archived without losing its history.

Rules for every story in this round:

- Everything belongs to one club (U12). Nothing here sends email.
- Attendance and death are recorded per character, not per player, like map visits (see Decisions).
- Nothing is deleted. Dying and archiving never remove a character's items, coins, ledger lines, or map credit.

### Play sessions

A **play session** is one scheduled game night run by a game master. The club keeps a calendar of them and a record of who came.

**P1 Schedule a session.** As a game master or club admin, I want to add a play session to the club calendar with a date, a start time, an optional end time, a title, and notes, so players know when we play. *(sessions)*
- A session also has a game master (defaulting to me) and an optional location (a table, a Discord channel, a link).
- I can change or cancel a session. A cancelled session stays on the calendar, marked cancelled, so nobody turns up.
- A session in the past can still be edited, to fix its record.
- Dates and times are entered and shown in the club's time zone (P11).

**P2 Repeat sessions.** As a game master or club admin, I want to make a session repeat weekly or every two weeks, so I do not add every Friday by hand. *(sessions)*
- Repeating makes a set of ordinary sessions. Changing or cancelling one does not change the others, and I can cancel the rest of a set in one step.

**P3 The session calendar.** As a player, game master, or club admin, I want a calendar page showing the club's sessions by month, with an upcoming list on phones, so I can see when we play next. *(sessions)*
- Each day shows its sessions: title, time, game master, and how many characters said yes.
- The club home page shows the next session (P4).
- The page offers a link that adds the club's sessions to a phone or desktop calendar app, read-only, that works without signing in to this site. Anyone holding the link can read the schedule, so an admin can reset it.
- This calendar is separate from the availability agenda (U70), which plans shops, quests, and downtime actions. The agenda may later show sessions too.

**P4 Say I'm coming.** As a player, I want to say yes, maybe, or no to a session with one of my characters, so my game master knows who to plan for. *(sessions, player_characters)*
- I answer for a character, because attendance is per character. If I do not pick one, the selected character is used (U25).
- I can change my answer until the session starts. After that only a game master or club admin can.
- Sessions have no seat cap. Every "yes" counts.
- I see my own answers on my dashboard and my sheet.

**P5 Who is coming.** As a game master, I want to see each session's answers, with the players who have not answered, so I know the table before we start. *(sessions)*
- The list shows each character's name, level and class, with the player's name.
- A GM or club admin can answer for someone, so a player who tells me at the table counts.

**P6 Take attendance.** As a game master, I want to record who actually played, character by character, so the club has a true record. *(sessions, player_characters)*
- The attendance page starts from the "yes" answers and I can tick or untick anyone, including characters who never answered.
- A character is either "played" or not. Only characters that played count in P7 and P8.
- Attendance can be corrected afterwards. Each correction is recorded with who changed it and when.
- A dead or archived character (U138-U147) is never offered for new attendance.

**P7 Attendance history.** As a player, I want my character's sheet to list the sessions it played, with dates, so I can see its adventures. *(sessions, player_characters)*
- The list shows date, title, and game master. It links to nothing private.
- A club admin or game master sees the same list for any character.

**P8 Attendance report.** As a club admin, I want a report of how many sessions each character and each player has played in a date range, so I can see who is active and who has drifted. *(sessions)*
- Players are counted across all their characters. A player who brought two characters to one session counts as one session of attendance for the player.
- The report exports as a CSV.

**P9 Downtime points for attending.** As a club admin, I want to choose whether finishing attendance awards downtime action points (D1), and how many, so showing up is rewarded without extra work. *(sessions, downtime, ledger)*
- A club setting: no award (the default), or a number of points per character that played.
- Confirming attendance for the first time awards the points, once, with a note naming the session. Correcting attendance later adds or removes only the difference.
- Awards use the same ledger as D1, so they show in the character's history.

**P10 Session notes.** As a game master, I want to write a short recap on a session after it happens, so the club has a record. *(sessions)*
- Players see the recap on the session page. A separate GM-only note never shows to players, like location notes on the map.

**P11 Club time zone.** As a club admin, I want to set my club's time zone, so session times mean the same thing to everyone, wherever they are. *(accounts, sessions)*
- A club has one time zone, chosen from the standard list. A new club starts with the site's default, and the site admin's "new club" form can set it.
- Sessions (P1) store an exact moment and show it in the club's time zone, including daylight saving changes. The calendar feed (P3) carries the same moment, so a phone shows it in the viewer's own time.
- Changing the time zone later keeps each session's moment, so sessions can shift on the clock. The form warns about this before saving.
- Other dates in the app (ledger, awards) are unchanged.

### Characters: death and archiving

A character can be **dead**, which is part of its story and keeps it visible. A character can be **archived**, which only tucks it out of the way. They are separate: a dead character is not archived unless someone also archives it, and an archived character is not dead.

**U138 Mark a character dead.** As a player, I want to mark my character as dead, with the date it died and an optional note on how, so the club and its shops know. *(player_characters)*
- The date defaults to today and can be set to an earlier session date (P1). It cannot be in the future.
- A game master or club admin can mark any character dead and set the same fields.
- The note is shown to anyone who can see the character.
- Marking dead writes one history entry with who did it and when, so it is never a silent change.

**U139 Take it back.** As a game master or club admin, I want to undo a death, so a mistaken click or a resurrection in the story puts the character back in play. *(player_characters)*
- Players can undo only a death they marked themselves, and only within one day, to fix a slip. Otherwise a game master or club admin does it.
- Undoing clears the date and note, and is recorded in history. It does not give anything back that happened while the character was dead.

**U140 A dead character cannot buy.** As a club admin, I want a dead character to be unable to buy, so the dead do not shop. *(shops, player_characters, ledger)*
- A dead character cannot buy at a club shop or at a player stall (U64), cannot spend downtime points (D2), and cannot turn in items to a quest (Q1).
- The buy button is replaced by a short reason, for example "Aria Windrunner died on 2026-11-14".
- The server refuses these actions even if someone sends the request by hand, and nothing changes.
- A game master or club admin can still give and take items and coins by manual adjustment (U14), for example to settle an estate.

**U141 A dead character can still sell.** As a player, I want my dead character to keep selling its junk, so its things still earn coins for the club's economy. *(shops, player_characters)*
- A dead character can set items aside as junk (U45), sell junk to club shops, and keep its player stall open (U64), including receiving payment when others buy.
- A dead character's coins and items stay on its sheet and in reports.
- Coins that a dead character earns, from junk sales or from its stall, keep going to that character. They collect on its sheet and cannot be spent, because a dead character cannot buy (U140). A game master or club admin can still adjust them (U14).
- A dead character cannot make new claims, such as starting equipment or map credit requests (M12), and cannot be sent into a party for a new session (P6).

**U142 Show the death on the shop.** As a player browsing the street, I want a dead character's stall to show clearly that its owner has died, so I understand why it is still there. *(shops, player_characters)*
- The stall's banner shows a marker such as a tombstone, "In memory of <name>", and the date it died. The shopkeeper silhouette gets a sombre look.
- The stall otherwise works as before for buyers (U64, U65).
- The marker shows wherever the stall appears: the street, the shop page, and any list of player shops.

**U143 Show the death on the sheet.** As a player, I want a dead character's sheet and list entries to show a clear "Died <date>" badge and the note, so nobody mistakes it for a living one. *(player_characters)*
- The badge shows on the character sheet, the character list, the top-bar character picker, and printouts (U35).
- Dead characters sort after living ones in pickers, but stay selectable (U25), so the owner can still reach them to sell junk.
- A club admin can filter the character list to "living", "dead", or "all".

**U144 Archive a character.** As a player, I want to archive a character I am done with, so it stops cluttering my lists. *(player_characters)*
- An archived character disappears from the character list, the top-bar picker, the street, party pickers, the map, and attendance (P6). Its player stall closes and leaves the street.
- A game master or club admin can archive any character. A player can archive only their own.
- Archiving is allowed for living or dead characters. If the selected character is archived, the app chooses another of mine, or none.
- Archiving writes a history entry. Nothing else changes: items, coins, ledger lines, and map credit stay as they are.
- Archived characters never act. No buying, selling, spending, turning in, or awards, until they are unarchived. Manual adjustments by a game master or club admin are still possible, with a visible warning.

**U145 The archive screen.** As a player, I want one screen listing my archived characters, so I can find one and bring it back. *(player_characters)*
- It shows each character's name, class and level, the date it was archived, and whether it died (and when).
- Each row has an "Unarchive" button. Unarchiving returns the character to every list. A character that was dead stays dead.
- If the character was shopping, its stall comes back closed, not open, so a reopened stall is a deliberate choice.
- Game masters and club admins see every archived character in the club, with the owner's name and a filter by owner.
- The archive screen is linked from the "More" menu and the character list, so it is findable but out of the way.

**U146 Archive and death for agents and approvals.** As a game master, I want my agent and the approvals inbox to respect dead and archived characters, so a batch of awards is not applied to a character that cannot receive it. *(agent_access, ledger)*
- Agent character lookup marks each character as living, dead, or archived. Archived characters are left out of searches unless asked for.
- A proposed batch (A3) that names an archived character is held back with a clear warning on the review page until I fix or confirm the line (A4). A dead character can still receive awards through a game master's confirmation.
- Pending requests (D4, M12, U13) from a character that is later archived stay visible to approvers, marked archived, and can still be answered.

**U147 Death and archive in the history and reports.** As a club admin, I want deaths, archives, and unarchives to show in the club's history and in a "Fallen" list, so the club has a record. *(player_characters, ledger)*
- Every change (U138, U139, U144, U145) is one history entry with who, when, and the note.
- A "Fallen" page lists dead characters with the date, owner, and note, newest first, including archived ones. Players can see it too.
- The Fallen page can show each character's sessions played (P7), once sessions exist.

## Round 20: email (2026-11-21)

Until now the app sent no email (see Decisions). This round adds email through Resend, a transactional email service reached over HTTPS, because DigitalOcean blocks the usual mail ports. The club has about 20 players and plays about once a month, so volume is tiny: a few dozen emails a month.

Rules for every story in this round:

- The app never runs a mail server. It sends through the Resend HTTPS API only.
- Email is a convenience, never a requirement. Every flow that works today (an admin hands out a temporary password, an admin resets a password) keeps working when email is off or fails.
- Emails are plain, short, and work as text. No tracking pixels and no tracked links.
- An email never contains a password in clear text. It carries a one-time link instead (E2, E3).
- Everything is per club where it makes sense (U12). A person in two clubs gets each club's emails separately, marked with the club's name.
- The Resend key lives only in the server's environment, never in the code, the database, or the logs.

### Foundation

**E1 Send email.** As a site admin, I want the app to send email through Resend, so the other stories can use it. *(core, config)*
- Settings come from the server environment: the Resend API key, and the "from" address. The reply-to is set per club by the app (E10), never by the server environment. With no key set, the app logs emails to the console as it does today and never fails because of it.
- The "from" address is on a domain verified in Resend, for example `Downtime Market <noreply@mail.downtimemarket.com>`. The site admin does the DNS setup once, and the README says how.
- Every email goes through one place in the code. It sends in the background, so a slow or failing Resend never makes a page slow or fail. A failed send is retried a few times, then marked failed.
- A site admin command sends a test email to an address, and says plainly whether the key and domain work.
- Tests use no network.

**E2 See what was sent.** As a club admin, I want a page listing emails the app sent for my club, with who, what kind, when, and whether it was delivered, failed, or bounced, so I know when someone did not get theirs. *(core, accounts)*
- Each row shows the recipient, the kind (welcome, password reset, session reminder), the time, and the status. It never shows the body or any link.
- A failed or bounced row has a "Show them the link instead" button where it makes sense (E3, E4), so the admin can hand it over by hand.
- Resend tells the app about delivery, bounces, and complaints through a signed webhook. The app checks the signature and ignores anything else.
- Addresses that bounce hard or mark an email as spam get a "do not email" flag, so the app stops sending to them. A club admin can clear the flag.
- Old rows are dropped after 90 days.

### Accounts

**E3 Welcome email with a sign-in link.** As a club admin, I want the person I add to get an email with a one-time link to set their own password, so I do not have to message them a password. *(accounts)*
- The add-person form (U1, U18) gets an "Email them a sign-in link" checkbox, ticked by default when email is on.
- With it ticked, the app emails a link that opens a "choose your password" page. The link works once, expires after 7 days, and is useless after the password is set.
- With it unticked, or when email is off, nothing changes: the admin sees the temporary password once (U18) and hands it over.
- The email says the club's name, who added them, and the site address. An existing account that is only added to a new club gets a short "you were added to <club>" email with no link.
- If the send fails, the admin sees it right away and can still show the temporary password.
- An admin can resend the link from the People page. Resending cancels the older link.

**E4 Forgot my password.** As a player, I want a "Forgot password?" link on the sign-in page that emails me a reset link, so I can get back in without asking an admin. *(accounts)*
- The page asks for an email address. The answer is always the same message ("If that address has an account, we sent a link"), so nobody can find out who has an account.
- The link works once, expires after 1 hour, and opens a "choose a new password" page that follows the password rules (U20). Setting a password signs the person out everywhere else.
- Requests are rate limited per address and per visitor. People with no email on file, or flagged "do not email" (E2), get nothing.
- An email also goes to the account's address after any password change, saying "your password was changed", with no link.
- The admin reset (U19) is unchanged.

### Sessions

These stories need play sessions (P1-P4, round 19).

**E5 Session reminder.** As a player, I want an email a few days before a play session, with the date, time, and place, so I do not forget. *(play_sessions, core)*
- A club admin chooses when reminders go, from a short list: for example 7 days and 2 days before. The default is one reminder, 3 days before.
- The email says the session's title, date, and time in the club's time zone (P11), the game master, and the location. It goes to every member who has a character that has not said "no" to the session.
- A cancelled session sends a short "cancelled" email to people who were sent a reminder or said "yes". A changed date or time sends one "changed" email.
- Reminders go out once, even if the job runs twice. A session that is already past never sends one.
- The server runs the job on a schedule. A site admin can see when it last ran.

**E6 Answer from the email.** As a player, I want to say "yes", "maybe", or "no" from the reminder email with one click, so I do not have to sign in to RSVP. *(play_sessions)*
- The email has three buttons per character the person owns, for example "Aria: Yes / Maybe / No". Each link answers that one session for that one character (P4).
- A link opens a small page that shows the answer and asks the person to press "Confirm". Nothing changes on a plain page load, so mail scanners that open links cannot answer for people.
- Links expire when the session starts. They work only for that person and that character, and a signed-in person who follows a link for someone else gets nothing.
- The page shows the current answer and lets the person change it.
- A player can answer more than once; the latest answer wins and is recorded like any RSVP.

**E7 A digest for the game master.** As a game master, I want one email the day before a session, listing who said yes, maybe, no, and who has not answered, so I know the table. *(play_sessions)*
- It goes to the session's game master only, and only if they opt in (E8).
- It lists characters with the player's name, like the "Who is coming" page (P5).

### Preferences

**E8 My email settings.** As a player, I want to choose which emails I get, so I only get the ones I want. *(accounts)*
- A "My email" page lists the optional kinds: session reminders (E5), cancel and change notices, and the game master digest (E7, game masters only). Each can be turned on or off per club.
- Welcome and password emails (E3, E4) are not optional, because they are things the person asked for. The page says so.
- Every optional email has a one-click "unsubscribe" link at the bottom. It opens a confirm page and turns off that kind only, with no sign-in needed.
- Players with no email address on file see a short note that email is off for them.

**E9 Add an email address later.** As a player, I want to add or change my own email address, so I can start getting email after being added without one. *(accounts)*
- Changing the address sends a confirmation link to the new address. The old address stays in use until the link is opened, and the old address gets a notice.
- An address is already used by another account: the page gives the same neutral answer as E4.
- Whitelisted addresses (U1) are unchanged by this. A club admin can still add people by email.

**E10 Club contact email.** As a club admin, I want to set an optional contact email for my club, so replies to the club's emails reach me or my game masters and not nobody. *(accounts, core)*
- The club settings page gets an optional "Contact email" field. It must be a valid address and is shown to club admins only.
- When it is set, every email the app sends for that club (E3, E4, E5, E7) carries it as the reply-to. The "from" address stays the site's address, so delivery is unchanged.
- When it is blank, those emails have no reply-to. The email footer says replies are not read and names the club.
- Emails about an account that is not tied to one club, such as a password reset (E4) for a person in several clubs, have no reply-to.
- The contact email is never shown to players, other clubs, or agents. It is only used as the reply-to header.
- The "new club" form (site admin) can set it, but does not need to.

**E11 Send a test email.** As a club admin, I want to send a test email from my club's settings to myself or another admin, so I can check that sending works and see what my club's emails look like. *(accounts, core)*
- The club settings page gets a "Send a test email" button next to the contact email (E10). It asks which kind to send: a plain test, a sample welcome email (E3), or a sample session reminder (E5). The first version needs only the plain test.
- The test goes to the signed-in admin's own address by default. The admin can pick another admin of the same club from a list, but cannot type any other address, so the button cannot be used to send mail to strangers.
- The test email looks like a real one for this club: same "from" address, the club's contact email as reply-to (E10), the club's name, and a clear "This is a test" line. Samples use made-up names, and contain no working links.
- The page says what happened: queued, sent, or failed, with the plain reason when Resend refuses (no key, domain not verified, address flagged "do not email"). The result also shows in the email log (E2) as kind "test".
- Each club can send a few tests per hour. More are refused with a clear message.
- Only club admins can send tests. When email is off for the site, the button is disabled and says why.
- The email is built in one place from the club's settings, so later club customisation (for example a footer or a signature) shows up in the test without extra work.

## Round 21: clearer item names and choices (2026-11-21)

Some seeded items are named in ways that mix several things into one, or read the wrong way round. This round fixes the names, makes the Diplomat's Pack roll a choice, and gives existing clubs a safe way to catch up.

Rules for every story in this round:

- A variant name puts the specific thing first and the kind in brackets: "Drum (Musical Instrument)", not "Musical Instrument (Drum)". The kind stays in the name, so searching for "Musical Instrument" still finds every instrument.
- Renaming keeps the same item record, so shop lines, quests, starting equipment lines, containers, and every character's inventory keep pointing at it. Nobody's items or coins change.
- Items a club admin made or renamed themselves are never touched.

**U148 Separate Map Case and Scroll Case.** As a player, I want the General Store to sell a Map Case and a Scroll Case as two items, so I buy the one I mean. *(items, shops)*
- The "Case, Map or Scroll" item is replaced by "Map Case" and "Scroll Case". Each costs 1 gp, with its own icon and description.
- Inside packs and elsewhere, the old "Map or Scroll Case" is the same item as the store's, so a club never has two near-duplicates.
- A character who already owns the old item keeps it as a "Map Case". A game master or club admin can change it to a "Scroll Case" by a manual adjustment (U14).

**U149 The Diplomat's Pack picks its cases.** As a player, I want the Diplomat's Pack to hold two cases that are each a map case or a scroll case, so every pack opened is a little different. *(items)*
- The pack holds two slots that always drop something. Each slot is a weighted choice between Map Case and Scroll Case, equal weights, one of the chosen item.
- This replaces the single fixed line of 2 "Map or Scroll Case". Everything else in the pack stays as it is.
- Opening and the loot preview follow the container rules (U109-U112). A pack opened before the change keeps what it gave.
- Existing clubs get the change when they run the catch-up command (U152). New clubs get it from the start.

**U150 Name variants "Variant (Kind)".** As a player, I want variant items named with the specific thing first, so lists sort and read naturally, like "Drum (Musical Instrument)". *(items, starting_equipment, shops)*
- These seeded families are renamed: Musical Instrument (Lute, Flute, Lyre, Horn, Drum), Arcane Focus (Crystal, Orb, Rod, Staff, Wand), Druidic Focus (Sprig of Mistletoe, Staff, Yew Wand), Holy Symbol (Amulet, Emblem, Reliquary), Artisan's Tools (ten trades), and Gaming Set (Dice, Dragonchess, Playing Cards).
- Example: "Crystal (Arcane Focus)", "Amulet (Holy Symbol)", "Brewer's Supplies (Artisan's Tools)", "Dice (Gaming Set)".
- Starting equipment choice groups (the lists a player picks from when claiming) are unchanged. Only the names change.
- Names with a comma or a unit, like "Bottle, Glass", "Lantern, Hooded", "Oil (flask)" and "Ink (1 oz)", stay as they are.
- Item cards, printouts, the agent's item search (A2), and shop lines show the new names.

**U151 One item per instrument.** As a club admin, I want a Lute to be one item wherever it appears, so inventories and shops do not hold two Lutes. *(items, starting_equipment)*
- The Bard's plain "Lute", "Flute", "Lyre" and "Horn", the Entertainer background's instruments, and the "Instrument (lute)" in the Entertainer's Pack are all the same item per instrument, named "Lute (Musical Instrument)" and so on.
- Where a club has more than one record for the same instrument, they are merged into one (U152). Every holder's quantity is added together, with one ledger entry per holder saying so.

**U152 Catch up existing clubs.** As a site admin, I want one command that brings an existing club's items up to the new names and choices, so I can run it on the server like the stacked-bundle conversion. *(items, starting_equipment, shops)*
- `manage.py rename_seeded_items --club <slug>` is a dry run by default. It lists every rename, every merge, and every refusal, and rolls everything back. `--apply` makes the changes in one transaction. Running it twice changes nothing.
- It renames seeded items in place (U150), splits "Case, Map or Scroll" (U148), merges duplicates (U151), and updates the Diplomat's Pack slots (U149).
- It only touches items whose names match the seeded ones. If a club admin has renamed or edited a seeded item, it is skipped and listed as "left alone".
- A merge that would leave a character with a negative total is refused and writes nothing. A holder whose net total is exactly zero is skipped, as in the stacked-bundle command.
- Item records keep their ids, so shop lines, quests, starting equipment lines, containers, and notes stay linked. Ledger history keeps its old text.
- The docs say when to run it (after the release that carries it), like the bundle conversion.

**U153 Seeding and tests use the new names.** As a developer, I want the seed data, tests and docs to use the new names, so new clubs start correct and nothing breaks silently. *(items, starting_equipment, shops)*
- Seeded clubs get the new names from the start. The seeded item count test is updated to the new count, and a test pins the renamed families and the Diplomat's Pack slots.
- The starting equipment claim still grants the same things as before (an instrument choice still lets a Bard pick one of the five).
- The demo club (`seed_demo`) uses the new names.

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

**S12 Shop street position editor.** As a club admin, I want a drag-and-drop grid showing each lot on my club's street (club shops, player stalls, and filler buildings), so that I can set the shops' street positions visually instead of editing numbers on a form. *(shops)*
- Only club shops are reorderable; player stalls are shown as context and cannot be dragged.
- Dragging a shop onto another shop reorders the shop sequence.
- Saving writes street_position to each of the club's shops in the new order, starting at 0, and redirects back with a success message.
- Player stalls and shops of other clubs are not changed by saving.

## Carried over from the first draft

These still apply and are not covered above. Keep, change, or drop them. C6 (correct a mistake) was merged into U14.

**C1 Browse items.** As a player, I want to see the items a shop currently has, with prices and any remaining quantity, so that I can decide what to buy. *(shops)*

**C2 Buy an item.** As a player, I want to buy an item for one of my characters so that the price comes out of that character's coins. *(shops, player_characters)*
- The purchase fails with a clear message if the character cannot afford it.
- A purchase is all or nothing: no half-finished purchases.

**C3 Last one wins.** As a player, I want a clear "already sold" message when someone else buys the last unit first. *(shops)*
- Two players buying the last unit at the same moment never both succeed.

**C4 Live shop.** As a player, I want the shop screen to reflect what I have just bought or sold, without me having to reload. *(shops)*
- The shop updates when the page loads and after the player's own purchase or sale.
- It does not refresh on a timer while the page sits open, so an expanded "Preview contents" stays open until the player closes it.

**C6 Price changed.** As a player, if an item's price changes between when I open the "Buy" modal and when I confirm, I want to be told the new price and asked to confirm again, rather than being charged a price I did not agree to. *(shops)*
- The buy modal shows the price the player was shown.
- Submitting with a stale price re-opens the modal at the new price with a warning; no purchase happens until the player confirms at the new price.

**C5 Ledger.** As a player, I want to see a history of every time each of my characters gained or lost items or coins, newest first, with a note on what happened (for example `sold to <shop name>` or `awarded by game master <name>`), so I can see where things came from and went. *(player_characters)*

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
- The map starts filtered to the character selected in the top bar (U22).
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

Not included: players' agents, spending a player's coins, and anything outside the connecting GM's club.

## Later

- **lore**: out of scope for now. The world notes in the [dnd-world-keeper](https://github.com/bernvaughn/dnd-world-keeper) repo should eventually live in this app instead of that separate repo, so they are more available. When it comes up, decide whether some lore can be game-master-only.
- **Donate button**: which service it points to is still to be decided; dig into it later.

## Decisions so far

- **Permissions.** The site admin is separate from club permissions. Club admin and game master are separate permissions that one account can hold together. The donate button and the backup and cost stories are the site admin's; everything else is club-level.
- **Login without email.** The app never sends email. Admins create accounts and hand out one-time temporary passwords, people choose their own on first sign-in, and admins reset passwords for members of their club when they administer every club that person belongs to, and the site admin handles the rest (U18-U20). Email addresses identify accounts and are never mailed.
- **Agent access.** A game master's agent connects through MCP, proposes batches of awards and new items from notes, and the game master confirms them on the site before anything changes (A1-A6). Map updates from notes (A7) are coming soon, not in the first version. Some GMs use Claude and some use Meta's Muse.
- **Clubs.** Each club's data is separate, and the email whitelist belongs to a club. A person can have characters in several clubs; a character never moves between clubs. Game masters can own characters and play when they are not running a session, and club admins can hand a character from one player to another (U16).
- **Items.** Each club has its own item catalogue (the `items` app), so clubs can add their own homebrew items. The `shops` app holds inventories that point at the catalogue, with a stock amount per item, and handles buying and selling. A shop only sees its own club's items.
- **Shop prices.** Each item has a value. Each shop has a default sell percentage and a separate default buy percentage of that value, which can be overridden item by item within the shop (S1).
- **Rotations.** A rotation only sets when its shops open and close, and a shop can be in several rotations. A shop's inventory is an ongoing list that carries over between rotations, with stock quantities kept per shop (S2).
- **Coins.** Stored as copper and shown as copper, silver, gold, and platinum (10 copper = 1 silver, 10 silver = 1 gold, 10 gold = 1 platinum). No platinum is shown under 10,000 gp; from 10,000 gp up the normal split is used (U30). Each denomination has its own colour, always with its label (U29).
- **Ledger.** The `ledger` app records every gain or loss of items or coins for a character, with a note and a date.
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
- **Acting as a character.** A player picks one character to act as from the top bar, remembered per club. Pages that act as one character always use it, with no per-page choice. Pages that pick several characters (the map, map requests) start with it, and picking others there does not change the top-bar selection (U22, U25, M8).
- **Found locations.** A character has found a location if it is credited with discovering or exploring it, or has a found mark from a game master or club admin. A found mark gives no XP and only makes the location visible; players can ask for one like other map credit (M12, M16). On visited tiles, players see an unnamed "?" for each location someone has discovered but their characters have not found, and can ask for credit on it. Undiscovered locations show nothing, and only a game master or club admin records first discovery.
- **Shop and character pages.** A shop page is a banner in the shop's preset colour with a preset shopkeeper silhouette over a counter-style item table (U34). A character page is a printable character sheet (U35).
- **Look.** The Bootswatch Journal theme (MIT) for Bootstrap 5 across the whole site, served by the app, with compact tables and forms on dense pages (U21).
- **Navigation.** Dashboard, Character, Shops, and Quests are plain links; everything else sits in a "More", a "Game master", or a "Club admin" menu, showing only links the person may use. The club name, the person's name, the selected character, approvals, and log out never collapse into the hamburger menu (U27, U32, U121).
- **Modals.** Buying (U31), map tiles (M17), and inbox grants (U28) open in modals. Each still has a plain page that works without JavaScript.
- **Inbox grants.** Club admins can grant coins, items, and map credit from a message, through the same rules and ledger as manual adjustments and map credit, and mark the message handled in the same step (U28).
- **Target level and XP.** A location has a target level band; the XP table is editable per club and shown for reference (M11, M13). Each location has one credited discovery group (the first) and one credited explored group (which may differ). Game masters and club admins can correct them, and everyone who sees the location sees the credited characters (M14, M15). Players can ask for visits, discovered, or explored credit, which a game master or club admin grants, with no automatic declines (M12). A party is only a list of characters picked at the time, not a stored record.
- **Magic item type.** Catalogue items carry an optional magic item type (Armor, Potion, Ring, Rod, Scroll, Staff, Wand, Weapon, Wondrous item) instead of a yes/no wondrous tag; treasure themes come later (U91).
- **Slips and cards.** Slips and item cards share the adventurer's-pass look: double border, notched corners, wordmark font. Players can print one card per item type or one per item (U87, U88, U90).
- **Footer and item details.** Every page has a small footer with copyright and credits, never printed (U94). Item details open from an "i" icon beside the name; items have a GM-only details field that players never see (U95, U96).
- **Containers.** Any item can be a container (`is_container`). Slots have chance, weighted options, quantity ranges, and unknown flags. Opening writes an `opened` ledger entry and a `ContainerOpening`. Previews go through `loot_preview()`; unknowns are masked to `???` for players and agents. Nesting allowed (max depth 3, no cycles). Existing packs migrated by idempotent `seed_pack_containers` command. Agent `search_items` returns `is_container` and masked `loot`. Residual: an unknown slot's content item is a normal catalogue item; its name may appear elsewhere without revealing it is in a box.
- **Death and archive (U138-U147).** Dead and archived are separate states on a character. Players can mark their own characters dead. Dead characters cannot buy, spend, or turn in, but can sell junk and keep a stall, which shows a memorial. Coins from the stall keep going to the dead character and just collect there, unusable for now; a way to use them may come later. A replacement character may claim starting equipment as usual. Archived characters are hidden everywhere and cannot act until unarchived. Neither removes any data.
- **Play sessions (P1-P11).** Sessions are club-scoped calendar entries in the club's time zone, with no seat cap. RSVPs and attendance are per character. Attendance can optionally award downtime points once (P9).
- **Email (E1-E11).** Email goes through Resend's HTTPS API only. It never replaces a flow that works without it: admins can still hand out temporary passwords and reset passwords. Emails carry one-time links, never passwords. Required emails are the welcome link and password resets; session reminders and notices are optional per person and club. Round 20 supersedes the earlier "no email for now" decision.
- **Item names (U148-U153).** A variant item is named "Variant (Kind)", for example "Drum (Musical Instrument)". Renames keep the same item record, so nothing a player owns changes. The store sells "Map Case" and "Scroll Case" separately, and the Diplomat's Pack rolls each of its two cases between them. Existing clubs catch up with a dry-run-by-default command.
- **Left for later.** Lore and the donate service.

## Database and feature notes

- **Trade/Transfer models removed from database.** The `Trade` and `TradeLine` models were dropped (player_characters migration 0010) and `LedgerEntry.Kind.TRADE`/`TRANSFER` were dropped (ledger migration 0004). `JunkMark` remains. Old ledger notes stay as text.
- **No trades or transfers between characters.** Players cannot give or send items or coins to another character, including their own. Otherwise a player could make many characters, feed everything to one, and sell it all for unlimited coins. Game masters and club admins can still give and take items by manual adjustment (U14).
- **Stacked items (U123-U131).** One pool of whole units per character and item. Bundle size lives on the shop line, not on the item, so a shop can sell the same item in several bundle sizes, each with its own stock. Combining is automatic, and every action takes a unit count, so there is no split or combine feature. Sale prices come from the total units sold.
- **Player shops (U64/U65) remain unchanged** and continue to provide the safe player-to-player economy via fixed-price buying and selling.

## Still open

Nothing right now. Lore and the donate service are left for later (see Later).
