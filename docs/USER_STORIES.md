# User Stories (draft)

First pass drawn from the plan in the README. Edit freely. No code is implied by anything here.

Roles:

- **Player**: owns one or more characters and spends their money.
- **DM**: runs a campaign, assigns money, and manages the shop.
- **Site owner**: runs the server (the person who deploys and backs it up). Uses the Django admin.

Money is stored in copper; every change to a balance is a ledger entry, and a balance is the sum of a character's entries.

## 1. Accounts and characters

**US-1 Sign in.** As a player, I want to sign in with my own account so that I only see and spend my own characters' money.
- Signed-out visitors cannot see balances or the shop.
- A player never sees another player's characters unless they are a DM of that campaign.

**US-2 Create characters.** As a DM, I want to create a character, give it a name and a campaign, and assign it to a player so that it appears on that player's account.
- A character has an owner, a name, and a campaign.
- The new character starts with a zero balance.

**US-3 See all characters.** As a DM, I want to see every character in my campaign and their balances so that I know who has what before a session.

**US-4 Manage accounts.** As the site owner, I want to create DM and player accounts in the Django admin so that I control who can use the app.

## 2. Money

**US-5 Grant money.** As a DM, I want to give a character money with a short reason so that rewards from a session show up before players shop.
- The grant appears in the character's history with the reason and a timestamp.
- The new balance is visible to the player right away.

**US-6 See my balance.** As a player, I want to see each of my characters' current balance so that I know what I can afford.

**US-7 See my history.** As a player, I want to see a list of everything that changed my character's balance (grants and purchases) so that I can check where the money went.
- Entries are newest first, with amount, reason, and timestamp.

**US-8 Correct a mistake.** As a DM, I want to subtract money with a reason so that I can fix a grant I got wrong without erasing history.
- Corrections are new ledger entries; existing entries are never edited or deleted.

## 3. The shop

**US-9 Stock the shop.** As a DM, I want to add, edit, and remove shop items (name, price, optional quantity) so that the shop matches what is for sale in my world.
- Leaving quantity empty means the item is unlimited.

**US-10 Change the shop between sessions.** As a DM, I want to switch items on or off without deleting them so that I can change what is for sale from one session to the next.
- An item that is off does not show to players and cannot be bought.

**US-11 Browse items.** As a player, I want to see the items currently for sale with their prices and any remaining quantity so that I can decide what to buy.

**US-12 Buy an item.** As a player, I want to buy an item for one of my characters so that the cost comes out of that character's balance.
- The purchase fails with a clear message if the balance is too low.
- A successful purchase subtracts the price, reduces any limited quantity by one, and adds a history entry.
- A purchase is all or nothing: no half-finished purchases.

**US-13 Last one wins.** As a player, I want a clear "already sold" message when someone else buys the last unit first so that I understand why my purchase did not go through.
- Two players buying the last unit at the same moment never both succeed.

**US-14 Live shop.** As a player, I want sold-out items to disappear from my screen within a few seconds, without reloading, so that I do not try to buy something that is gone.
- The shop list refreshes about every 5 seconds while the page is visible.
- The page does not keep refreshing while the browser tab is hidden.

## 4. Running the app

**US-15 Nightly backup.** As the site owner, I want a nightly copy of the database stored outside the server so that a server or account problem does not lose the group's data.
- The copy has been restored successfully at least once.

**US-16 Predictable cost.** As the site owner, I want the hosting bill to stay at the fixed monthly price so that I am never surprised by a charge.
- Exactly one server; a billing alert is set.

## Proposed, not in the plan yet

These came up while writing the stories above. Keep, change, or drop them.

**US-17 Owned items.** As a player, I want a list of what my character has bought so that I do not have to reconstruct it from the history.

**US-18 Familiar coins.** As a player, I want amounts shown as gold, silver, and copper so that prices read like the game does.

**US-19 Per-campaign shops.** As a DM, I want my campaign's shop to be separate from other campaigns' shops so that different worlds can sell different things.

## Open questions

- Should purchased items be recorded on the character (US-17), or is the history enough?
- Does each campaign get its own shop (US-19), or is there one shared shop?
- Can one player own characters in more than one campaign?
- Can a player ever send money to another character, or only the DM moves money in?
- Should a DM be able to see who bought what, or only balances?
