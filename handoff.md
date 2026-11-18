# Hand-off: Extract Map Credit Logic to Service

## Task
Move the complex map credit logic from `MapDashboardProvider._get_uncredited_data()` in `accounts/dashboard_providers.py` to a dedicated service function `get_uncredited_tiles()` in `map/services.py`.

## What Was Done (Plan Stage)
1. **Explored the codebase** - Read the relevant files:
   - `accounts/dashboard_providers.py` - Contains `MapDashboardProvider` with `_get_uncredited_data()` method
   - `map/services.py` - Existing map services (where new function will be added)
   - `map/models.py` - Map-related models (TileVisit, HexMap, Location, LocationCredit, FoundMark)
   - `accounts/tests/test_dashboard_map_provider.py` - Existing tests for the provider

2. **Created implementation plan** - Saved to `plan.md`

3. **Set acceptance criteria** - 11 items covering:
   - New service function in `map/services.py` returning structured data (dataclass)
   - Updated `MapDashboardProvider` to use the service
   - Tests for the new service function

## Key Decisions
- Use a **dataclass** `UncreditedTilesResult` for type-safe return value
- The service function will be `get_uncredited_tiles(club, character)` 
- It returns: maps_data (list of dicts with map and uncredited_count), total_uncredited, first_map (HexMap), first_map_uncredited_tiles (set of (q,r))
- This matches the exact data structure the provider needs for template context

## What the Next Agent (Code Stage) Should Do First
1. **Add the service function to `map/services.py`**:
   - Import required models (TileVisit, HexMap, Location, LocationCredit, FoundMark)
   - Create `UncreditedTilesResult` dataclass
   - Implement `get_uncredited_tiles(club, character)` with the logic from `_get_uncredited_data()`
   - Handle all edge cases: no visits, no locations, full credit, partial credit

2. **Update `accounts/dashboard_providers.py`**:
   - Import `get_uncredited_tiles` from `map.services`
   - Remove `_get_uncredited_data()` method from `MapDashboardProvider`
   - Update `get_context()` and `should_show()` to call the service

3. **Create tests in `map/tests/test_map_services.py`**:
   - Port existing provider test cases to directly test the service
   - Ensure all existing provider tests still pass

## Files to Modify
- `map/services.py` - Add new function
- `accounts/dashboard_providers.py` - Update MapDashboardProvider
- `map/tests/test_map_services.py` - New test file (create)

## Dependencies
- Upstream task "Unified Dashboard Provider System" (01a1e68f-ddc8-79f7-9df1-6ef168482fef) is done
- No other blockers