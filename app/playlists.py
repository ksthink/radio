"""
Playlist manager for persisting saved playlists.
"""
import json
import os
from datetime import datetime
from typing import List, Dict, Any

class PlaylistManager:
    def __init__(self, data_dir: str = "data"):
        self.data_dir = data_dir
        self.playlists_file = os.path.join(data_dir, "playlists.json")
        self.playlists = []
        self._next_id = 1
        self.load()

    def load(self):
        """Load playlists from file."""
        if os.path.exists(self.playlists_file):
            try:
                with open(self.playlists_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    self.playlists = data.get('playlists', [])
                    if self.playlists:
                        self._next_id = max(p['id'] for p in self.playlists) + 1
            except Exception as e:
                print(f"Failed to load playlists: {e}")
                self.playlists = []
        else:
            self.playlists = []

    def save(self):
        """Save playlists to file."""
        os.makedirs(self.data_dir, exist_ok=True)
        try:
            with open(self.playlists_file, 'w', encoding='utf-8') as f:
                json.dump({'playlists': self.playlists}, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Failed to save playlists: {e}")

    def add_playlist(self, title: str, url: str) -> Dict[str, Any]:
        """Add a new playlist."""
        playlist = {
            'id': self._next_id,
            'title': title,
            'url': url,
            'created_at': datetime.now().isoformat()
        }
        self._next_id += 1
        self.playlists.append(playlist)
        self.save()
        return playlist

    def get_playlists(self) -> List[Dict[str, Any]]:
        """Get all playlists."""
        return self.playlists

    def remove_playlist(self, playlist_id: int) -> bool:
        """Remove a playlist by ID."""
        original_len = len(self.playlists)
        self.playlists = [p for p in self.playlists if p['id'] != playlist_id]
        if len(self.playlists) < original_len:
            self.save()
            return True
        return False

    def get_playlist(self, playlist_id: int) -> Dict[str, Any] | None:
        """Get a single playlist by ID."""
        for p in self.playlists:
            if p['id'] == playlist_id:
                return p
        return None
