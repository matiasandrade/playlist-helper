# TODO & Future Features

## Sorting Enhancements

### Two-Stage Sorting (Filter then Sort)

**Status**: Planned
**Priority**: Medium

**Problem**:
Current multi-sort implementation uses hierarchical/tuple-based sorting. This means you cannot "filter by one criterion, then re-sort by another."

**Example Use Case**:
User wants to get the 150 most recently added tracks, then sort those 150 by popularity (highest to lowest).

**Current Limitations**:
- `--sort date --count 150` → Gets 150 recent tracks, but sorted by date
- `--sort popularity,date --count 150` → Gets 150 most popular tracks overall (not recent ones)
- `--sort date,popularity --count 150` → Gets recent tracks, popularity only used as tiebreaker

**Proposed Solutions**:

1. **Option A**: Syntax with count in sort string
   ```bash
   uv run main.py create-unsorted "house" --sort date:150,popularity
   # Meaning: Get top 150 by date, then re-sort those by popularity
   ```

2. **Option B**: Add separate pre-sort option
   ```bash
   uv run main.py create-unsorted "house" --pre-sort date --count 150 --sort popularity
   # More explicit but verbose
   ```

3. **Option C**: SQL-level implementation
   ```python
   # Modify get_unsorted_liked_tracks to accept pre_sort parameter
   # Returns: SELECT * FROM (SELECT * FROM tracks ORDER BY liked_at DESC LIMIT 150) ORDER BY popularity DESC
   ```

**Implementation Notes**:
- See `cli.py:apply_multi_sort()` docstring for detailed explanation
- May need to modify both `create_unsorted` and `show_playlist` commands
- Consider SQL-level optimization for large datasets

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
