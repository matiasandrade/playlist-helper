# Spotify Playlist Helper

A command-line tool to manage and analyze your Spotify music library. This tool helps you organize your liked songs into playlists and provides analytics on your music library.

## Features

- Sync your Spotify liked songs and playlists to a local SQLite database
- Find liked songs that aren't in any of your categorized playlists
- Create new playlists with unsorted tracks
- Get insights about your top artists, genres, and listening habits
- Sort tracks by popularity, date added, release date, or randomly
- Maintain a local database to reduce API calls and enable offline analysis

## Installation

1. Clone this repository
2. Install dependencies with `uv sync`
3. Copy `env_example` to `.env` and add your Spotify API credentials
4. Initialize the database with `python main.py setup --init`

## Setup

1. Create a Spotify App in the [Spotify Developer Dashboard](https://developer.spotify.com/dashboard/)
2. Set the redirect URI to `http://localhost:8888/callback`
3. Copy your Client ID and Client Secret to the `.env` file

## Usage

### Sync your data

```bash
# Sync everything (playlists and liked songs)
uv run main.py sync

# Sync only playlists
uv run main.py sync --playlists

# Sync only liked songs
uv run main.py sync --liked
```

### Create playlists with unsorted tracks

```bash
# Create a playlist with liked songs not in any "house.deep" or "house.tech" playlists
uv run main.py create-unsorted "house"

# Limit to 10 songs, sorted by date added
uv run main.py create-unsorted "house" --count 10 --sort date

# Sort by release date
uv run main.py create-unsorted "house" --count 15 --sort release

# Specify a custom name
uv run main.py create-unsorted "house" --name "House tracks to sort"
```

### Analyze your library

```bash
# Show top artists in "house" playlists
uv run main.py top-artists "house.deep"

# Show top artists in liked songs
uv run main.py top-artists "" --liked-only
```

### Explore the API

```bash
# Show sample data structure from Spotify API
uv run main.py api-info

# Show details of a specific playlist
uv run main.py show-playlist "Discover Weekly"
```

## Database Structure

The tool uses a SQLite database with the following main tables:

- `tracks`: Spotify tracks with metadata
- `artists`: Artist information
- `albums`: Album information
- `playlists`: Playlist information
- `audio_features`: Audio features of tracks (tempo, key, etc.)
- `sync_log`: Records of sync operations

The database schema is managed by Alembic for easy migration.

## Development

Generate a new migration when the database schema changes:

```bash
uvx alembic revision --autogenerate -m "Description of change"
```

Apply migrations:

```bash
uvx alembic upgrade head
```
