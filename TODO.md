# TODO & Future Features

## Sorting Enhancements

### ✅ Progressive Filtering (Filter then Sort) - IMPLEMENTED

**Status**: ✅ Implemented
**Priority**: Medium

**Implementation**:
Implemented Option A - count syntax in sort string.

**Usage**:
```bash
# Get 3000 most recently liked, then 500 oldest from those, then 150 most popular
uv run main.py create-unsorted "house" --sort date:3000,oldest:500,popularity:150

# Get 150 most recently added, then sort by popularity
uv run main.py create-unsorted "house" --sort date:150,popularity

# Traditional hierarchical sort still works
uv run main.py create-unsorted "house" --sort rarity,date
```

**How it works**:
- Parse sort string for `method:count` syntax
- Apply sorts **left-to-right** with progressive filtering
- If count is specified, limit to top N after that sort
- Subsequent sorts operate on filtered results
- Traditional multi-sort (no counts) uses tuple-based hierarchical sorting

**Examples**:
- `date:3000,oldest:500,popularity:150` → 150 tracks that are old, recently discovered, and popular
- `date:1000,popularity` → 1000 recent tracks sorted by popularity
- `rarity,date` → All tracks sorted by rarity, then date as tiebreaker

**Implementation Details**:
- See `cli.py:apply_multi_sort()` for implementation
- `_get_single_sort_key()` extracts sort key for a single method
- Progressive filtering mode activated when any count is present
- Final count from sort string takes precedence over `--count` parameter

---

## Other Potential Enhancements

### Single Playlist Search in `show_playlist`
**Status**: Noted in code
**Location**: `cli.py:265`

Current behavior shows all matching playlists. User may want to search through a single specific playlist instead.

### Additional Sort Methods
- **Tempo/BPM**: Sort by track tempo (requires audio features sync)
- **Energy**: Sort by energy level
- **Danceability**: Sort by danceability score
- **Custom**: User-defined SQL-based sorting

### Batch Playlist Operations
- Delete multiple playlists matching a pattern
- Merge playlists
- Deduplicate tracks across playlists
