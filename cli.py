import re
from datetime import datetime

import click
from rich.console import Console
from rich.table import Table

from db_utils import get_session, init_db, get_unsorted_liked_tracks, get_top_artists
from spotify_api import get_spotify_client, create_playlist, add_tracks_to_playlist
from sync import sync_all, sync_liked_tracks, sync_playlists

console = Console()


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
    type=click.Choice(["popularity", "date", "release", "random"]),
    default="popularity",
    help="Sort method (popularity, date added, release date, random)",
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

    # Sort the tracks
    if sort == "popular":
        sorted_tracks = sorted(
            unsorted_tracks, key=lambda t: t.liked_at or 0, reverse=True
        )  # type: ignore
        sorted_tracks = sorted(
            sorted_tracks[:count], key=lambda t: t.popularity or 0, reverse=True
        )
    if sort == "unpopular":
        sorted_tracks = sorted(
            unsorted_tracks, key=lambda t: t.liked_at or 0, reverse=True
        )  # type: ignore
        sorted_tracks = sorted(
            sorted_tracks[:count], key=lambda t: t.popularity or 0, reverse=False
        )
    elif sort == "date":
        sorted_tracks = sorted(
            unsorted_tracks, key=lambda t: t.liked_at or datetime.min, reverse=True
        )  # type: ignore
    elif sort == "release":
        sorted_tracks = sorted(
            unsorted_tracks, key=lambda t: t.release_date or "", reverse=True
        )  # type: ignore
    else:  # random
        import random

        sorted_tracks = list(unsorted_tracks)
        random.shuffle(sorted_tracks)

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
def show_playlist(name):
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
    for playlist in matching_playlists:
        click.echo(f"\n=== {playlist['name']} ===")
        click.echo(f"ID: {playlist['id']}")
        click.echo(f"Owner: {playlist['owner']['display_name']}")
        click.echo(f"Public: {playlist['public']}")
        click.echo(f"Tracks: {playlist['tracks']['total']}")

        # Get first 5 tracks as a preview
        tracks = spotify.playlist_tracks(playlist["id"], limit=5)["items"]  # type: ignore
        if tracks:
            click.echo("\nPreview of tracks:")
            for i, item in enumerate(tracks, 1):
                track = item["track"]
                artists = ", ".join([artist["name"] for artist in track["artists"]])
                click.echo(f"{i}. {track['name']} by {artists}")


if __name__ == "__main__":
    cli()
