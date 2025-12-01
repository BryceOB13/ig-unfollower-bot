"""Skip list management module for filtering accounts."""

import json
import os
from typing import Optional


class SkipListManager:
    """Manages the skip list for filtering accounts from reports.
    
    The skip list is stored as a JSON file containing usernames to exclude
    from unfollower and not-following-back reports.
    """
    
    def __init__(self, filepath: str = "skip_list.json"):
        """Initialize with skip list file path.
        
        Args:
            filepath: Path to the skip list JSON file
        """
        self.filepath = filepath
        self._skip_list: Optional[set[str]] = None
    
    def load(self) -> set[str]:
        """Load skip list from JSON file.
        
        Returns:
            Set of usernames in the skip list. Returns empty set if file
            doesn't exist or is invalid.
        """
        if self._skip_list is not None:
            return self._skip_list
        
        if not os.path.exists(self.filepath):
            self._skip_list = set()
            return self._skip_list
        
        try:
            with open(self.filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Handle both formats: {"usernames": [...]} or just [...]
                if isinstance(data, dict) and "usernames" in data:
                    self._skip_list = set(data["usernames"])
                elif isinstance(data, list):
                    self._skip_list = set(data)
                else:
                    self._skip_list = set()
        except (json.JSONDecodeError, IOError):
            self._skip_list = set()
        
        return self._skip_list
    
    def save(self, usernames: Optional[set[str]] = None) -> None:
        """Save skip list to JSON file.
        
        Args:
            usernames: Set of usernames to save. If None, saves the current
                      internal skip list.
        """
        if usernames is not None:
            self._skip_list = usernames
        
        if self._skip_list is None:
            self._skip_list = set()
        
        data = {"usernames": sorted(list(self._skip_list))}
        
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2)
    
    def add(self, username: str) -> None:
        """Add username to skip list.
        
        Args:
            username: Username to add to the skip list
        """
        skip_list = self.load()
        skip_list.add(username)
        self._skip_list = skip_list
        self.save()
    
    def remove(self, username: str) -> None:
        """Remove username from skip list.
        
        Args:
            username: Username to remove from the skip list
        """
        skip_list = self.load()
        skip_list.discard(username)
        self._skip_list = skip_list
        self.save()
    
    def contains(self, username: str) -> bool:
        """Check if username is in skip list.
        
        Args:
            username: Username to check
            
        Returns:
            True if username is in the skip list, False otherwise
        """
        return username in self.load()
