"""Snapshot management module for persisting follower data."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
from typing import Optional


@dataclass
class Snapshot:
    """Point-in-time capture of followers and following lists.
    
    Attributes:
        timestamp: ISO 8601 formatted timestamp of when snapshot was taken
        followers: List of follower usernames
        following: List of following usernames
        followers_count: Number of followers
        following_count: Number of following
    """
    timestamp: str
    followers: list[str] = field(default_factory=list)
    following: list[str] = field(default_factory=list)
    followers_count: int = 0
    following_count: int = 0
    
    def __post_init__(self):
        """Validate and set counts if not provided."""
        if self.followers_count == 0 and self.followers:
            self.followers_count = len(self.followers)
        if self.following_count == 0 and self.following:
            self.following_count = len(self.following)


class SnapshotManager:
    """Handles persistence and retrieval of follower data snapshots."""
    
    LATEST_POINTER_FILE = "latest.json"
    
    def __init__(self, data_dir: str = "snapshots"):
        """Initialize with data directory path.
        
        Args:
            data_dir: Directory path for storing snapshot files
        """
        self.data_dir = Path(data_dir)
    
    def _ensure_data_dir(self) -> None:
        """Create data directory if it doesn't exist."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
    
    def to_json(self, snapshot: Snapshot) -> str:
        """Serialize snapshot to JSON string.
        
        Args:
            snapshot: Snapshot object to serialize
            
        Returns:
            JSON string representation of the snapshot
        """
        data = {
            "timestamp": snapshot.timestamp,
            "followers": snapshot.followers,
            "following": snapshot.following,
            "followers_count": snapshot.followers_count,
            "following_count": snapshot.following_count
        }
        return json.dumps(data, indent=2)
    
    def from_json(self, json_str: str) -> Snapshot:
        """Deserialize JSON string to Snapshot.
        
        Args:
            json_str: JSON string to deserialize
            
        Returns:
            Snapshot object reconstructed from JSON
        """
        data = json.loads(json_str)
        return Snapshot(
            timestamp=data["timestamp"],
            followers=data["followers"],
            following=data["following"],
            followers_count=data["followers_count"],
            following_count=data["following_count"]
        )

    def save(self, snapshot: Snapshot) -> str:
        """Save snapshot to JSON file with timestamp-based filename.
        
        Updates the latest pointer file to reference this snapshot.
        
        Args:
            snapshot: Snapshot object to save
            
        Returns:
            Filepath of the saved snapshot
        """
        self._ensure_data_dir()
        
        # Create timestamp-based filename
        # Parse the ISO timestamp and create a safe filename
        safe_timestamp = snapshot.timestamp.replace(":", "-").replace(".", "-")
        filename = f"snapshot_{safe_timestamp}.json"
        filepath = self.data_dir / filename
        
        # Write snapshot to file
        json_content = self.to_json(snapshot)
        filepath.write_text(json_content, encoding="utf-8")
        
        # Update latest pointer
        self._update_latest_pointer(str(filename))
        
        return str(filepath)
    
    def _update_latest_pointer(self, filename: str) -> None:
        """Update the latest pointer file to reference the given snapshot.
        
        Args:
            filename: Filename of the latest snapshot
        """
        pointer_path = self.data_dir / self.LATEST_POINTER_FILE
        pointer_data = {"latest": filename}
        pointer_path.write_text(json.dumps(pointer_data, indent=2), encoding="utf-8")
    
    def load_latest(self) -> Optional[Snapshot]:
        """Load most recent snapshot from latest pointer.
        
        Returns:
            Most recent Snapshot object, or None if no snapshots exist
        """
        pointer_path = self.data_dir / self.LATEST_POINTER_FILE
        
        if not pointer_path.exists():
            return None
        
        try:
            pointer_data = json.loads(pointer_path.read_text(encoding="utf-8"))
            latest_filename = pointer_data.get("latest")
            
            if not latest_filename:
                return None
            
            return self.load(str(self.data_dir / latest_filename))
        except (json.JSONDecodeError, KeyError, FileNotFoundError):
            return None
    
    def load(self, filepath: str) -> Snapshot:
        """Load specific snapshot from file.
        
        Args:
            filepath: Path to the snapshot file
            
        Returns:
            Snapshot object loaded from file
            
        Raises:
            FileNotFoundError: If the snapshot file doesn't exist
            json.JSONDecodeError: If the file contains invalid JSON
        """
        path = Path(filepath)
        json_content = path.read_text(encoding="utf-8")
        return self.from_json(json_content)
