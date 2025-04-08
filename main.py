import os
from functools import partial
from typing import List, Dict
import spotipy
from spotipy.oauth2 import SpotifyOAuth
from dotenv import load_dotenv

def get_spotify_client() -> spotipy.Spotify:
    load_dotenv()
    return spotipy.Spotify(auth_manager=SpotifyOAuth(
        client_id=os.getenv('CLIENT_ID'),
        client_secret=os.getenv('CLIENT_SECRET'),
        redirect_uri='http://localhost:8888/callback',
        scope='playlist-read-private'
    ))

def get_all_playlists(spotify: spotipy.Spotify) -> List[Dict]:
    results = spotify.current_user_playlists()
    return results['items']

def get_track_from_playlist(spotify: spotipy.Spotify, playlist_id: str) -> Dict:
    results = spotify.playlist_tracks(playlist_id, limit=1)
    if results['items']:
        return results['items'][0]['track']
    return {}

def print_track_info(track: Dict) -> None:
    print(f"Track name: {track['name']}")
    print(f"Artists: {', '.join([artist['name'] for artist in track['artists']])}")
    print(f"Album: {track['album']['name']}")
    print(f"Duration: {track['duration_ms']/1000:.2f} seconds")
    print(f"Popularity: {track['popularity']}")
    print(f"External URL: {track['external_urls']['spotify']}")
    print(f"Preview URL: {track['preview_url']}")

def format_playlist(playlist: Dict) -> str:
    return f"Name: {playlist['name']}, ID: {playlist['id']}, Tracks: {playlist['tracks']['total']}"

def print_playlists(playlists: List[Dict]) -> None:
    playlist_strings = map(format_playlist, playlists)
    for playlist in playlist_strings:
        print(playlist)

def main():
    spotify = get_spotify_client()
    playlists = get_all_playlists(spotify)
    if playlists:
        # Get first track from first playlist
        track = get_track_from_playlist(spotify, playlists[0]['id'])
        if track:
            print_track_info(track)

if __name__ == '__main__':
    main()
