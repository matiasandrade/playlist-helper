import os
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from sqlalchemy import create_engine, select, func, text
from sqlalchemy.orm import sessionmaker, Session

from db_models import Base, Track, Artist, Album, Playlist, SyncLog, trackartist_association, playlisttrack_association

def get_db_path() -> str:
    """Get the path to the SQLite database file."""
    db_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    os.makedirs(db_dir, exist_ok=True)
    return os.path.join(db_dir, "spotify.db")

def get_engine():
    """Create an SQLAlchemy engine connected to the SQLite database."""
    db_path = get_db_path()
    return create_engine(f"sqlite:///{db_path}")

def get_session() -> Session:
    """Get a new SQLAlchemy session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()

def init_db():
    """Initialize the database by creating all tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    print(f"Initialized database at {get_db_path()}")

def get_last_sync(session: Session, sync_type: str) -> Optional[SyncLog]:
    """Get the most recent successful sync log for a given type."""
    return session.query(SyncLog).filter(
        SyncLog.sync_type == sync_type,
        SyncLog.success == 1
    ).order_by(SyncLog.completed_at.desc()).first()

def log_sync_start(session: Session, sync_type: str) -> SyncLog:
    """Create a new sync log entry."""
    sync_log = SyncLog(sync_type=sync_type, started_at=datetime.utcnow())
    session.add(sync_log)
    session.commit()
    return sync_log

def log_sync_complete(session: Session, sync_log: SyncLog, 
                     items_synced: int, success: bool = True,
                     error_message: Optional[str] = None,
                     cursor: Optional[str] = None):
    """Update a sync log entry when the sync is complete."""
    sync_log.completed_at = datetime.utcnow()
    sync_log.items_synced = items_synced
    sync_log.success = 1 if success else 0
    sync_log.error_message = error_message
    sync_log.cursor = cursor
    session.commit()

def save_artist(session: Session, artist_data: Dict[str, Any]) -> Artist:
    """Save an artist to the database."""
    artist = session.query(Artist).get(artist_data["id"])
    if not artist:
        artist = Artist(id=artist_data["id"])
    
    artist.name = artist_data["name"]
    if "popularity" in artist_data:
        artist.popularity = artist_data["popularity"]
    if "genres" in artist_data and artist_data["genres"]:
        artist.genres = ",".join(artist_data["genres"])
    if "images" in artist_data and artist_data["images"]:
        artist.image_url = artist_data["images"][0]["url"]
    
    artist.last_updated = datetime.utcnow()
    session.add(artist)
    return artist

def save_album(session: Session, album_data: Dict[str, Any]) -> Album:
    """Save an album to the database."""
    album = session.query(Album).get(album_data["id"])
    if not album:
        album = Album(id=album_data["id"])
    
    album.name = album_data["name"]
    if "album_type" in album_data:
        album.album_type = album_data["album_type"]
    if "release_date" in album_data:
        album.release_date = album_data["release_date"]
    if "total_tracks" in album_data:
        album.total_tracks = album_data["total_tracks"]
    if "images" in album_data and album_data["images"]:
        album.image_url = album_data["images"][0]["url"]
    
    album.last_updated = datetime.utcnow()
    session.add(album)
    return album

def save_track(session: Session, track_data: Dict[str, Any], 
               album: Optional[Album] = None, 
               artists: Optional[List[Artist]] = None,
               is_liked: bool = False,
               liked_at: Optional[datetime] = None) -> Track:
    """Save a track to the database."""
    track = session.query(Track).get(track_data["id"])
    if not track:
        track = Track(id=track_data["id"])
    
    track.name = track_data["name"]
    track.duration_ms = track_data.get("duration_ms")
    track.explicit = 1 if track_data.get("explicit") else 0
    track.popularity = track_data.get("popularity")
    track.preview_url = track_data.get("preview_url")
    track.track_number = track_data.get("track_number")
    
    if is_liked:
        track.is_liked = 1
        track.liked_at = liked_at
    
    if album:
        track.album = album
        # Copy release date from album for easier filtering/sorting
        if album.release_date:
            track.release_date = album.release_date
    
    if artists:
        track.artists = artists
    
    track.last_updated = datetime.utcnow()
    session.add(track)
    return track


def save_playlist(session: Session, playlist_data: Dict[str, Any]) -> Playlist:
    """Save a playlist to the database."""
    playlist = session.query(Playlist).get(playlist_data["id"])
    if not playlist:
        playlist = Playlist(id=playlist_data["id"])
    
    playlist.name = playlist_data["name"]
    playlist.description = playlist_data.get("description")
    playlist.public = 1 if playlist_data.get("public") else 0
    playlist.collaborative = 1 if playlist_data.get("collaborative") else 0
    playlist.owner_id = playlist_data.get("owner", {}).get("id")
    playlist.total_tracks = playlist_data.get("tracks", {}).get("total")
    
    if "images" in playlist_data and playlist_data["images"]:
        playlist.image_url = playlist_data["images"][0]["url"]
    
    playlist.last_updated = datetime.utcnow()
    session.add(playlist)
    return playlist

def add_track_to_playlist(session: Session, playlist: Playlist, track: Track, 
                         position: int, added_at: Optional[datetime] = None):
    """Add a track to a playlist with position and added_at information."""
    # SQLAlchemy doesn't directly support adding data to the association table
    # with additional columns, so we use raw SQL
    session.execute(
        text("""
            INSERT OR REPLACE INTO playlist_track 
            (playlist_id, track_id, position, added_at) 
            VALUES (:playlist_id, :track_id, :position, :added_at)
        """),
        {
            "playlist_id": playlist.id,
            "track_id": track.id,
            "position": position,
            "added_at": added_at or datetime.utcnow()
        }
    )

# Analytics queries
def get_top_artists(session: Session, limit: int = 10, 
                   playlist_pattern: Optional[str] = None,
                   liked_only: bool = False) -> List[Tuple[Artist, int]]:
    """Get top artists by track count."""
    query = (
        session.query(Artist, func.count(Track.id).label("track_count"))
        .join(trackartist_association, Artist.id == trackartist_association.c.artist_id)
        .join(Track, Track.id == trackartist_association.c.track_id)
    )
    
    if playlist_pattern:
        query = query.join(playlisttrack_association, Track.id == playlisttrack_association.c.track_id)
        query = query.join(Playlist, Playlist.id == playlisttrack_association.c.playlist_id)
        query = query.filter(Playlist.name.like(f"%{playlist_pattern}%"))
    
    if liked_only:
        query = query.filter(Track.is_liked == 1)
    
    return query.group_by(Artist.id).order_by(text("track_count DESC")).limit(limit).all()

def get_unsorted_liked_tracks(session: Session, playlist_pattern: str) -> List[Track]:
    """Get tracks that are liked but not in any playlist matching the pattern."""
    return (
        session.query(Track)
        .filter(Track.is_liked == 1)
        .outerjoin(
            playlisttrack_association, 
            Track.id == playlisttrack_association.c.track_id
        )
        .outerjoin(
            Playlist, 
            (Playlist.id == playlisttrack_association.c.playlist_id) & 
            (Playlist.name.like(f"%{playlist_pattern}%"))
        )
        .filter(Playlist.id == None)
        .all()
    )