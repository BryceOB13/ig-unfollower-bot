"""History management module for tracking unfollow actions."""

import json
from datetime import datetime, timezone
from pathlib import Path


class HistoryManager:
    """Manages the history of unfollow actions.
    
    Tracks which accounts have been unfollowed and when, to prevent
    re-processing the same accounts in future runs.
    """
    
    def __init__(self, filepath: str = "unfollowed_history.json"):
        """Initialize with history file path.
        
        Args:
            filepath: Path to the JSON file storing unfollow history.
        """
        self.filepath = Path(filepath)
        self._history: dict[str, str] | None = None
    
    def load(self) -> dict[str, str]:
        """Load history mapping username -> timestamp.
        
        Returns:
            Dictionary mapping usernames to their unfollow timestamps.
            Returns empty dict if file doesn't exist or is invalid.
        """
        if self._history is not None:
            return self._history
            
        if not self.filepath.exists():
            self._history = {}
            return self._history
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Ensure we have a dict of string -> string
                if isinstance(data, dict):
                    self._history = {str(k): str(v) for k, v in data.items()}
                else:
                    self._history = {}
        except (json.JSONDecodeError, IOError):
            self._history = {}
        
        return self._history
    
    def save(self, history: dict[str, str]) -> None:
        """Save history to JSON file.
        
        Args:
            history: Dictionary mapping usernames to timestamps.
        """
        # Ensure parent directory exists
        self.filepath.parent.mkdir(parents=True, exist_ok=True)
        
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2, ensure_ascii=False)
        
        # Update cached history
        self._history = history.copy()
    
    def record_unfollow(self, username: str) -> None:
        """Record unfollow action with current UTC timestamp.
        
        Args:
            username: The Instagram username that was unfollowed.
        """
        history = self.load()
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        history[username] = timestamp
        self.save(history)
    
    def was_unfollowed(self, username: str) -> bool:
        """Check if user was previously unfollowed.
        
        Args:
            username: The Instagram username to check.
            
        Returns:
            True if the user appears in the unfollow history.
        """
        history = self.load()
        return username in history
