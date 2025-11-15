import re
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from db_utils import get_session, init_db, get_unsorted_liked_tracks, get_top_artists
from spotify_api import get_spotify_client, create_playlist, add_tracks_to_playlist
from sync import sync_all, sync_liked_tracks, sync_playlists

console = Console()


def apply_multi_sort(tracks, sort_string):
    """Apply multiple sort criteria to tracks using tuple keys for proper multi-sort.

    Args:
        tracks: List of track objects to sort
        sort_string: Comma-separated sort methods (e.g., "rarity,date")
                    Available methods:
                    - popularity: high to low (most popular first)
                    - rarity: low to high (least popular = rarest first)
                    - date: most recent liked_at first
                    - release: newest release_date first
                    - oldest: oldest release_date first (vintage tracks)

    Returns:
        Sorted list of tracks

    Example:
        "rarity,date" -> Sort by rarity (least popular first),
                         then by date added (most recent first) for ties
        This means: among the rarest tracks, show the most recently added ones first

        "oldest,date" -> Sort by oldest releases first,
                         then by most recently liked for ties
        This finds vintage tracks you've recently discovered

    LIMITATION - Two-Stage Sorting Not Supported:
        The current implementation uses hierarchical/tuple-based sorting.
        It does NOT support "filter by X, then sort by Y" workflows.

        For example, you CANNOT currently do:
        - "Get the 150 most recently added tracks, then sort by popularity"
        - This would require: --sort date:150,popularity (NOT IMPLEMENTED)

        Current workarounds:
        - Use --sort date --count 150 (gets recent tracks, sorted by date)
        - Use --sort popularity,date (gets popular tracks, date as tiebreaker)

        Future enhancement: Implement two-stage sorting with syntax like:
        - --sort date:150,popularity (filter top 150 by date, then re-sort by popularity)
        - Or add --pre-sort option: --pre-sort date --count 150 --sort popularity
    """
    if not sort_string:
        return tracks

    # Parse sort methods
    sort_methods = [s.strip() for s in sort_string.split(",")]

    # Special case for random
    if "random" in sort_methods:
        import random

        sorted_tracks = list(tracks)
        random.shuffle(sorted_tracks)
        return sorted_tracks

    # Build a tuple key function for multi-sort
    # Python's sort is stable and sorts tuples element-by-element
    def make_sort_key(track):
        key_parts = []
        for sort_method in sort_methods:
            if sort_method == "popularity":
                # Higher popularity first -> negate for ascending sort
                # None values get -1, which becomes 1 after negation (sorted last)
                key_parts.append(
                    -(track.popularity if track.popularity is not None else -1)
                )
            elif sort_method == "rarity":
                # Lower popularity first (rarest)
                # None values get 999 (sorted last)
                key_parts.append(
                    track.popularity if track.popularity is not None else 999
                )
            elif sort_method == "date":
                # Most recent liked_at first -> negate timestamp
                # None values get 0 (sorted last)
                if track.liked_at:
                    key_parts.append(-track.liked_at.timestamp())
                else:
                    key_parts.append(0)
            elif sort_method == "release":
                # Newest release first -> invert the string for comparison
                # Release dates are in YYYY-MM-DD format
                # We invert by subtracting each char from 'z' to reverse string ordering
                release = track.release_date if track.release_date else ""
                if release:
                    # Invert the string for descending order
                    # YYYY-MM-DD strings naturally sort ascending, so we invert
                    inverted = "".join(
                        chr(ord("z") - ord(c) + ord("0")) if c.isdigit() else c
                        for c in release
                    )
                    key_parts.append(inverted)
                else:
                    key_parts.append("z" * 10)  # Sort empty dates last
            elif sort_method == "oldest":
                # Oldest release first -> use string directly (ascending order)
                # Release dates in YYYY-MM-DD format naturally sort oldest first
                release = track.release_date if track.release_date else ""
                if release:
                    key_parts.append(release)
                else:
                    # Empty dates go last
                    key_parts.append("z" * 10)

        return tuple(key_parts)

    sorted_tracks = sorted(tracks, key=make_sort_key)
    return sorted_tracks


@click.group()
def cli():
    """Spotify playlist helper for organizing and analyzing your music library."""
    pass


@cli.command()
@click.option("--init", is_flag=True, help="Initialize the database")
def setup(init):
    """Set up the database and environment."""
    if init:
        init_db()
    else:
        click.echo("No actions specified. Use --init to initialize the database.")


@cli.command()
@click.option("--playlists", is_flag=True, help="Sync playlists only")
@click.option("--liked", is_flag=True, help="Sync liked tracks only")
def sync(playlists, liked):
    """Sync data from Spotify to the local database."""
    spotify = get_spotify_client()
    session = get_session()

    try:
        if playlists and not liked:
            # Sync playlists only
            count = sync_playlists(spotify, session)
            click.echo(f"Synced {count} playlists")
        elif liked and not playlists:
            # Sync liked tracks only
            count = sync_liked_tracks(spotify, session)
            click.echo(f"Synced {count} liked tracks")
        else:
            # Sync everything
            results = sync_all(spotify, session)
            click.echo(
                f"Synced {results['liked_tracks']} liked tracks and {results['playlists']} playlists"
            )
    except Exception as e:
        click.echo(f"Error during sync: {str(e)}", err=True)


@cli.command()
@click.argument("pattern", required=True)
@click.option("--limit", "-l", default=10, help="Number of records to show")
@click.option("--liked-only", is_flag=True, help="Only include liked tracks")
def top_artists(pattern, limit, liked_only):
    """Show top artists in playlists matching the pattern."""
    session = get_session()

    # Get top artists
    results = get_top_artists(
        session=session, limit=limit, playlist_pattern=pattern, liked_only=liked_only
    )

    if not results:
        click.echo(f"No artists found for playlists matching '{pattern}'")
        return

    # Create a rich table
    table = Table(title=f"Top Artists in '{pattern}' Playlists")
    table.add_column("Rank", style="dim")
    table.add_column("Artist")
    table.add_column("Track Count")
    table.add_column("Genres")

    # Add rows
    for i, (artist, count) in enumerate(results, 1):
        genres = artist.genres.split(",")[:3] if artist.genres else []  # type: ignore
        genres_display = ", ".join(genres) if genres else "N/A"
        table.add_row(str(i), artist.name, str(count), genres_display)  # type: ignore

    # Print the table
    console.print(table)


@cli.command()
@click.argument("pattern", required=True)
@click.option("--count", "-c", default=20, help="Number of tracks to include")
@click.option(
    "--sort",
    "-s",
    default="popularity",
    help="Sort method(s) - comma-separated for multiple: popularity, rarity, date, release, oldest, random",
)
@click.option(
    "--name", "-n", help="Name of the new playlist (defaults to a generated name)"
)
def create_unsorted(pattern, count, sort, name):
    """Create a playlist with liked tracks not in any matching playlists."""
    session = get_session()
    spotify = get_spotify_client()

    # Get unsorted tracks
    unsorted_tracks = get_unsorted_liked_tracks(session, pattern)

    if not unsorted_tracks:
        click.echo(f"No unsorted liked tracks found for pattern '{pattern}'")
        return

    click.echo(f"Found {len(unsorted_tracks)} unsorted liked tracks")

    # Sort the tracks using the multi-sort function
    sorted_tracks = apply_multi_sort(unsorted_tracks, sort)

    # Limit to requested count
    tracks_to_add = sorted_tracks[:count]

    # Create playlist name if not provided
    if not name:
        volume = 1
        # Find the highest volume number in existing playlists matching the pattern
        all_playlists = spotify.current_user_playlists()["items"]  # type: ignore
        for playlist in all_playlists:
            # Look for playlists with the format "pattern - vol. X" or "pattern - vol X"
            match = re.search(
                rf"{pattern}.*vol\.?\s*(\d+)", playlist["name"], re.IGNORECASE
            )
            if match:
                volume = max(volume, int(match.group(1)) + 1)

        # Format the new playlist name
        name = f"{pattern} - vol. {volume:02d}"

    # Create the new playlist
    click.echo(f"Creating playlist '{name}' with {len(tracks_to_add)} tracks")
    playlist = create_playlist(
        spotify=spotify,
        name=name,
        description=f"Unsorted tracks from liked songs for {pattern}. Created on {datetime.now().strftime('%Y-%m-%d')}",
        public=False,
    )

    # Add tracks to the playlist
    track_ids = [track.id for track in tracks_to_add]
    add_tracks_to_playlist(spotify, playlist["id"], track_ids)  # type: ignore

    click.echo(
        f"Successfully created playlist '{name}' with {len(tracks_to_add)} tracks"
    )


@cli.command()
def api_info():
    """Display information about the data available from the Spotify API."""
    spotify = get_spotify_client()

    # Get sample data from the API
    me = spotify.me()
    sample_playlists = spotify.current_user_playlists(limit=1)

    if sample_playlists["items"]:  # type: ignore
        sample_playlist_id = sample_playlists["items"][1]["id"]  # type: ignore
        sample_tracks = spotify.playlist_tracks(sample_playlist_id, limit=1)
        if sample_tracks["items"]:  # type: ignore
            sample_track = sample_tracks["items"][0]["track"]  # type: ignore
        else:
            sample_track = None
    else:
        sample_track = None

    # Display user information
    click.echo("\n=== User Information ===")
    click.echo(f"ID: {me['id']}")  # type: ignore
    click.echo(f"Name: {me['display_name']}")  # type: ignore
    click.echo(f"Email: {me.get('email', 'N/A')}")  # type: ignore
    click.echo(f"Country: {me.get('country', 'N/A')}")  # type: ignore
    click.echo(f"Product: {me.get('product', 'N/A')}")  # type: ignore
    click.echo(f"Followers: {me.get('followers', {}).get('total', 'N/A')}")  # type: ignore

    # Display track information if available
    if sample_track:
        click.echo("\n=== Sample Track Information ===")
        for key, value in sample_track.items():
            if isinstance(value, dict) or isinstance(value, list):
                click.echo(f"{key}: [complex data]")
            else:
                click.echo(f"{key}: {value}")


@cli.command()
@click.argument("name", required=True)
@click.option(
    "--sort",
    "-s",
    default="popularity",
    help="Sort method(s) - comma-separated for multiple: popularity, rarity, date, release, oldest, random",
)
def show_playlist(name, sort):
    """Show details of a playlist by name (partial match)."""
    spotify = get_spotify_client()

    # Get all playlists
    playlists = spotify.current_user_playlists()["items"]  # type: ignore

    # Find matching playlists
    matching_playlists = [p for p in playlists if name.lower() in p["name"].lower()]

    if not matching_playlists:
        click.echo(f"No playlists found matching '{name}'")
        return

    # Show all matching playlists
    # TODO: [ ] I don't really want this, probably just search through a single playlist
    for playlist in matching_playlists:
        click.echo(f"\n=== {playlist['name']} ===")
        click.echo(f"ID: {playlist['id']}")
        click.echo(f"Owner: {playlist['owner']['display_name']}")
        click.echo(f"Public: {playlist['public']}")
        click.echo(f"Tracks: {playlist['tracks']['total']}")

        # Get all tracks for sorting (if sort is specified)
        all_items = []
        if sort and sort != "popularity":
            # Fetch all tracks for sorting
            results = spotify.playlist_tracks(playlist["id"])
            all_items = results["items"]
            while results["next"]:  # type: ignore
                results = spotify.next(results)  # type: ignore
                all_items.extend(results["items"])
        else:
            # Just get first 5 for preview
            all_items = spotify.playlist_tracks(playlist["id"], limit=5)["items"]

        # Apply sorting if needed
        if sort and len(all_items) > 0:
            # Parse sort methods
            sort_methods = [s.strip() for s in sort.split(",")]

            # Special case for random
            if "random" in sort_methods:
                import random

                random.shuffle(all_items)
            else:
                # Apply sorts in reverse order
                for sort_method in reversed(sort_methods):
                    if sort_method == "popularity":
                        all_items = sorted(
                            all_items,
                            key=lambda item: item["track"].get("popularity", 0)
                            if item["track"]
                            else 0,
                            reverse=True,
                        )
                    elif sort_method == "rarity":
                        all_items = sorted(
                            all_items,
                            key=lambda item: item["track"].get("popularity", 0)
                            if item["track"]
                            else 0,
                            reverse=False,
                        )
                    elif sort_method == "date":
                        all_items = sorted(
                            all_items,
                            key=lambda item: item.get("added_at", ""),
                            reverse=True,
                        )
                    elif sort_method == "release":
                        all_items = sorted(
                            all_items,
                            key=lambda item: item["track"]
                            .get("album", {})
                            .get("release_date", "")
                            if item["track"]
                            else "",
                            reverse=True,
                        )
                    elif sort_method == "oldest":
                        all_items = sorted(
                            all_items,
                            key=lambda item: item["track"]
                            .get("album", {})
                            .get("release_date", "")
                            if item["track"]
                            else "",
                            reverse=False,
                        )

        # Show top 5 tracks
        tracks_to_show = all_items[:5]
        if tracks_to_show:
            click.echo("\nPreview of tracks:")
            for i, item in enumerate(tracks_to_show, 1):
                track = item["track"]
                if track:
                    artists = ", ".join([artist["name"] for artist in track["artists"]])
                    popularity = track.get("popularity", "N/A")
                    release_date = track.get("album", {}).get("release_date", "N/A")
                    click.echo(
                        f"{i}. {track['name']} by {artists} (pop: {popularity}, release: {release_date})"
                    )


if __name__ == "__main__":
    cli()
