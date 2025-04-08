import os
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple, Iterator
import time

import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

def get_spotify_client() -> spotipy.Spotify:
    """
    Get an authenticated Spotify client.
    
    Returns:
        spotipy.Spotify: Authenticated Spotify client
    """
    load_dotenv()
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv('CLIENT_ID'),
        client_secret=os.getenv('CLIENT_SECRET'),
        redirect_uri='http://localhost:8888/callback',
        scope='user-library-read playlist-read-private playlist-read-collaborative playlist-modify-private playlist-modify-public'
    ))

def get_all_items(spotify: spotipy.Spotify, method_name: str, 
                 method_args: Dict[str, Any] = None, 
                 limit: int = 50) -> Iterator[Dict[str, Any]]:
    """
    Generic pagination method for Spotify API.
    
    Args:
        spotify: Authenticated Spotify client
        method_name: Name of the Spotify method to call
        method_args: Arguments to pass to the method
        limit: Limit per page
        
    Yields:
        Individual items from the paginated results
    """
    if method_args is None:
        method_args = {}
    
    # Make sure limit is in method_args
    method_args['limit'] = limit
    
    # Call the specified method on the spotify object
    method = getattr(spotify, method_name)
    
    # Initial request
    results = method(**method_args)
    
    # Check for items or track attribute in results
    if 'items' in results:
        items_key = 'items'
    elif 'tracks' in results and 'items' in results['tracks']:
        items_key = 'tracks.items'
    else:
        raise ValueError(f"Unexpected response format from {method_name}")
    
    # Get the items from the results
    items = results
    for key in items_key.split('.'):
        items = items[key]
    
    # Yield items from the first request
    for item in items:
        yield item
    
    # Continue pagination if needed
    while results['next']:
        # Rate limiting
        time.sleep(0.2)
        
        # Get next page
        results = spotify.next(results)
        
        # Get the items from the results
        items = results
        for key in items_key.split('.'):
            items = items[key]
        
        # Yield items from subsequent requests
        for item in items:
            yield item

def get_all_playlists(spotify: spotipy.Spotify) -> List[Dict]:
    """
    Get all playlists for the current user.
    
    Args:
        spotify: Authenticated Spotify client
        
    Returns:
        List of playlist objects
    """
    return list(get_all_items(spotify, 'current_user_playlists'))

def get_playlist_tracks(spotify: spotipy.Spotify, playlist_id: str) -> List[Dict]:
    """
    Get all tracks in a playlist.
    
    Args:
        spotify: Authenticated Spotify client
        playlist_id: Spotify playlist ID
        
    Returns:
        List of track objects with added_at information
    """
    return list(get_all_items(spotify, 'playlist_tracks', {'playlist_id': playlist_id}))

def get_liked_tracks(spotify: spotipy.Spotify) -> List[Dict]:
    """
    Get all liked tracks.
    
    Args:
        spotify: Authenticated Spotify client
        
    Returns:
        List of saved track objects
    """
    return list(get_all_items(spotify, 'current_user_saved_tracks'))


def get_artists(spotify: spotipy.Spotify, artist_ids: List[str]) -> List[Dict]:
    """
    Get full artist information.
    
    Args:
        spotify: Authenticated Spotify client
        artist_ids: List of artist IDs
        
    Returns:
        List of artist objects
    """
    # Process in chunks of 50 (Spotify API limit)
    results = []
    for i in range(0, len(artist_ids), 50):
        chunk = artist_ids[i:i+50]
        # Rate limiting
        time.sleep(0.2)
        artists = spotify.artists(chunk)['artists']
        results.extend(artists)
    
    return results

def create_playlist(spotify: spotipy.Spotify, name: str, 
                   description: Optional[str] = None, 
                   public: bool = False) -> Dict:
    """
    Create a new playlist.
    
    Args:
        spotify: Authenticated Spotify client
        name: Playlist name
        description: Playlist description
        public: Whether the playlist should be public
        
    Returns:
        Created playlist object
    """
    user_id = spotify.me()['id']
    return spotify.user_playlist_create(
        user=user_id,
        name=name,
        public=public,
        description=description
    )

def add_tracks_to_playlist(spotify: spotipy.Spotify, playlist_id: str, track_ids: List[str]) -> None:
    """
    Add tracks to a playlist.
    
    Args:
        spotify: Authenticated Spotify client
        playlist_id: Playlist ID
        track_ids: List of track IDs to add
    """
    # Process in chunks of 100 (Spotify API limit)
    for i in range(0, len(track_ids), 100):
        chunk = track_ids[i:i+100]
        # Rate limiting
        time.sleep(0.2)
        spotify.playlist_add_items(playlist_id, chunk)