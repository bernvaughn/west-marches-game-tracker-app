## code
- [x] Class match (case-insensitive): char_class__iexact used for matching
- [x] Background match (case-insensitive): background__iexact used for matching
- [x] Level coins (level > 1): StartingEquipmentLevelCoins queried for character.level > 1
- [x] Magic item requests (approved only): Filter by status=APPROVED and verify in magic_options
- [x] Empty template handling: Returns None when no lines and no coins to grant
- [x] Class entry level range: Filter by min_level <= level <= max_level
- [x] Choice groups skipped: Filter by is_choice=False for both class and background lines
- [x] Background only when set: Check character.background before querying background entries
- [x] Service uses ledger.record() with kind='award' and note='Starting equipment'
- [x] Service creates single ledger entry with all granted items and coins

## verify
- [ ] All existing tests pass
- [ ] New permission correctly rejects unauthenticated requests
- [ ] New permission correctly rejects authenticated non-admin/non-GM users
- [ ] New permission allows club admins to register clients
- [ ] New permission allows game masters to register clients
- [ ] New permission allows superusers to register clients