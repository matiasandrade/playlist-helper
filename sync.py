from datetime import datetime
from typing import Dict

import spotipy
from sqlalchemy.orm import Session

from spotify_api import (
    get_all_playlists,
    get_playlist_tracks,
    get_liked_tracks,
    get_artists,
)
from db_utils import (
    get_session,
    save_artist,
    save_album,
    save_track,
    save_playlist,
    add_track_to_playlist,
    get_last_sync,
    log_sync_start,
    log_sync_complete,
)


def sync_liked_tracks(spotify: spotipy.Spotify, session: Session = None) -> int:  # type: ignore
    """
    Sync liked tracks to the database.

    Args:
        spotify: Authenticated Spotify client
        session: Optional SQLAlchemy session

    Returns:
        Number of tracks synced
    """
    if session is None:
        session = get_session()

    # Start sync log
    sync_log = log_sync_start(session, "liked_tracks")

    try:
        # Track counts for reporting
        tracks_synced = 0
        tracks_skipped = 0

        # Check when we last synced
        last_sync = get_last_sync(session, "liked_tracks")
        last_sync_time = last_sync.completed_at if last_sync else None

        # Collect artist IDs for detailed fetch
        artist_ids_for_details = set()

        # Process liked tracks
        print("Syncing liked tracks...")
        for item in get_liked_tracks(spotify):
            track_data = item["track"]
            added_at = datetime.strptime(item["added_at"], "%Y-%m-%dT%H:%M:%SZ")

            # Skip if we've already processed this track in a recent sync
            if last_sync_time and added_at < last_sync_time:  # type: ignore
                tracks_skipped += 1
                continue

            # Process album
            album = save_album(session, track_data["album"])

            # Collect artist IDs for detailed fetch later
            artists = []
            for artist_data in track_data["artists"]:
                artist = save_artist(session, artist_data)
                artists.append(artist)
                artist_ids_for_details.add(artist_data["id"])

            # Save track with liked status
            track = save_track(
                session,
                track_data,
                album=album,
                artists=artists,
                is_liked=True,
                liked_at=added_at,
            )

            # Track is now fully processed

            # Commit every 100 tracks
            if (tracks_synced + 1) % 100 == 0:
                session.commit()
                print(f"Processed {tracks_synced + 1} liked tracks...")

            tracks_synced += 1

        # Process artist details in batches
        if artist_ids_for_details:
            print("Fetching artist details...")
            artist_details = get_artists(spotify, list(artist_ids_for_details))
            for artist_data in artist_details:
                save_artist(session, artist_data)

        # Final commit
        session.commit()

        print(
            f"Liked tracks sync complete. Added/updated: {tracks_synced}, Skipped: {tracks_skipped}"
        )
        log_sync_complete(session, sync_log, tracks_synced)
        return tracks_synced

    except Exception as e:
        session.rollback()
        log_sync_complete(session, sync_log, 0, success=False, error_message=str(e))
        raise


def sync_playlists(spotify: spotipy.Spotify, session: Session = None) -> int:  # type: ignore
    """
    Sync playlists and their tracks to the database.

    Args:
        spotify: Authenticated Spotify client
        session: Optional SQLAlchemy session

    Returns:
        Number of playlists synced
    """
    if session is None:
        session = get_session()

    # Start sync log
    sync_log = log_sync_start(session, "playlists")

    try:
        # Track counts for reporting
        playlists_synced = 0
        tracks_synced = 0

        # Collect artist IDs for detailed fetch
        artist_ids_for_details = set()

        # Get all playlists
        playlists = get_all_playlists(spotify)
        print(f"Found {len(playlists)} playlists")

        # Process each playlist
        for playlist_data in playlists:
            print(f"Syncing playlist: {playlist_data['name']}")

            # Save playlist to database
            playlist = save_playlist(session, playlist_data)
            playlists_synced += 1

            # Get all tracks in the playlist
            playlist_tracks = get_playlist_tracks(spotify, playlist_data["id"])

            # Process each track
            for i, item in enumerate(playlist_tracks):
                if "track" not in item or not item["track"]:
                    continue  # Skip invalid tracks

                track_data = item["track"]
                added_at = (
                    datetime.strptime(item["added_at"], "%Y-%m-%dT%H:%M:%SZ")
                    if "added_at" in item and item["added_at"]
                    else None
                )

                # Process album
                album = save_album(session, track_data["album"])

                # Collect artist IDs for detailed fetch later
                artists = []
                for artist_data in track_data["artists"]:
                    artist = save_artist(session, artist_data)
                    artists.append(artist)
                    artist_ids_for_details.add(artist_data["id"])

                # Save track
                track = save_track(session, track_data, album=album, artists=artists)

                # Add track to playlist with position info
                add_track_to_playlist(session, playlist, track, i, added_at)

                # Track is processed

                tracks_synced += 1

            # Commit after each playlist
            session.commit()

        # Process artist details in batches
        if artist_ids_for_details:
            print("Fetching artist details...")
            artist_details = get_artists(spotify, list(artist_ids_for_details))
            for artist_data in artist_details:
                save_artist(session, artist_data)

        # Final commit
        session.commit()

        print(
            f"Playlist sync complete. Playlists: {playlists_synced}, Tracks: {tracks_synced}"
        )
        log_sync_complete(session, sync_log, playlists_synced)
        return playlists_synced

    except Exception as e:
        session.rollback()
        log_sync_complete(session, sync_log, 0, success=False, error_message=str(e))
        raise


def sync_all(spotify: spotipy.Spotify, session: Session = None) -> Dict[str, int]:  # type: ignore
    """
    Sync all data from Spotify API to the database.

    Args:
        spotify: Authenticated Spotify client
        session: Optional SQLAlchemy session

    Returns:
        Dict with counts of synced items
    """
    if session is None:
        session = get_session()

    results = {}

    # Sync liked tracks
    liked_count = sync_liked_tracks(spotify, session)
    results["liked_tracks"] = liked_count

    # Sync playlists
    playlist_count = sync_playlists(spotify, session)
    results["playlists"] = playlist_count

    return results
