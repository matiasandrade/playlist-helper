from __future__ import annotations
from datetime import datetime

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Table
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()

# Association tables for many-to-many relationships
trackartist_association = Table(
    "track_artist",
    Base.metadata,
    Column("track_id", String, ForeignKey("tracks.id")),
    Column("artist_id", String, ForeignKey("artists.id")),
)

playlisttrack_association = Table(
    "playlist_track",
    Base.metadata,
    Column("playlist_id", String, ForeignKey("playlists.id")),
    Column("track_id", String, ForeignKey("tracks.id")),
    Column("added_at", DateTime),
    Column("position", Integer),
)


class Artist(Base):
    """Model representing a Spotify artist."""

    __tablename__ = "artists"

    # Spotify artist ID as primary key
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    popularity = Column(Integer, nullable=True)
    genres = Column(String, nullable=True)  # Stored as comma-separated string
    image_url = Column(String, nullable=True)

    # Track relationship (many-to-many)
    tracks = relationship(
        "Track", secondary=trackartist_association, back_populates="artists"
    )

    # Sync metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Album(Base):
    """Model representing a Spotify album."""

    __tablename__ = "albums"

    # Spotify album ID as primary key
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    album_type = Column(String, nullable=True)  # album, single, compilation
    release_date = Column(String, nullable=True)  # Can be YYYY, YYYY-MM, or YYYY-MM-DD
    total_tracks = Column(Integer, nullable=True)
    image_url = Column(String, nullable=True)

    # Track relationship (one-to-many)
    tracks = relationship("Track", back_populates="album")

    # Sync metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Track(Base):
    """Model representing a Spotify track."""

    __tablename__ = "tracks"

    # Spotify track ID as primary key
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    duration_ms = Column(Integer, nullable=True)
    explicit = Column(Integer, nullable=True)  # 0 for false, 1 for true
    popularity = Column(Integer, nullable=True)
    preview_url = Column(String, nullable=True)
    track_number = Column(Integer, nullable=True)
    is_liked = Column(Integer, default=0)  # 0 for false, 1 for true
    liked_at = Column(DateTime, nullable=True)
    release_date = Column(String, nullable=True)  # Added release_date from album

    # Foreign key to album
    album_id = Column(String, ForeignKey("albums.id"), nullable=True)
    album = relationship("Album", back_populates="tracks")

    # Artist relationship (many-to-many)
    artists = relationship(
        "Artist", secondary=trackartist_association, back_populates="tracks"
    )

    # Playlist relationship (many-to-many)
    playlists = relationship(
        "Playlist", secondary=playlisttrack_association, back_populates="tracks"
    )

    # Sync metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Playlist(Base):
    """Model representing a Spotify playlist."""

    __tablename__ = "playlists"

    # Spotify playlist ID as primary key
    id = Column(String, primary_key=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=True)
    public = Column(Integer, nullable=True)  # 0 for false, 1 for true
    collaborative = Column(Integer, nullable=True)  # 0 for false, 1 for true
    image_url = Column(String, nullable=True)
    owner_id = Column(String, nullable=True)
    total_tracks = Column(Integer, nullable=True)

    # Track relationship (many-to-many)
    tracks = relationship(
        "Track", secondary=playlisttrack_association, back_populates="playlists"
    )

    # Sync metadata
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class SyncLog(Base):
    """Model for tracking synchronization with Spotify API."""

    __tablename__ = "sync_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    sync_type = Column(String, nullable=False)  # liked_songs, playlists, etc.
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    items_synced = Column(Integer, default=0)
    cursor = Column(String, nullable=True)  # For pagination/continuation
    success = Column(Integer, default=0)  # 0 for false, 1 for true
    error_message = Column(String, nullable=True)
