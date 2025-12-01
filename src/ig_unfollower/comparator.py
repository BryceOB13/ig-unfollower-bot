"""Comparator module for computing differences between snapshots."""

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

from .snapshot import Snapshot


@dataclass
class ComparisonResult:
    """Result of comparing two snapshots.
    
    Attributes:
        unfollowers: Users who were in old followers but not in new
        not_following_back: Users being followed who don't follow back
        new_followers: Users in new followers but not in old
        timestamp: ISO 8601 timestamp of when comparison was performed
        unfollowed_timestamps: Mapping of username to detection timestamp
    """
    unfollowers: list[str] = field(default_factory=list)
    not_following_back: list[str] = field(default_factory=list)
    new_followers: list[str] = field(default_factory=list)
    timestamp: str = ""
    unfollowed_timestamps: dict[str, str] = field(default_factory=dict)
    
    def __post_init__(self):
        """Set timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()


class SnapshotComparator:
    """Computes differences between snapshots and applies skip filtering."""
    
    def __init__(self, skip_list: Optional[set[str]] = None):
        """Initialize with optional skip list.
        
        Args:
            skip_list: Set of usernames to exclude from results
        """
        self.skip_list = skip_list or set()
    
    def compute_unfollowers(self, old_followers: set[str], new_followers: set[str]) -> set[str]:
        """Return users who unfollowed (in old but not in new).
        
        Args:
            old_followers: Set of followers from previous snapshot
            new_followers: Set of followers from current snapshot
            
        Returns:
            Set of usernames who unfollowed
        """
        return old_followers - new_followers
    
    def compute_not_following_back(self, following: set[str], followers: set[str]) -> set[str]:
        """Return users you follow who don't follow back.
        
        Args:
            following: Set of users being followed
            followers: Set of users who follow back
            
        Returns:
            Set of usernames not following back
        """
        return following - followers
    
    def apply_skip_filter(self, usernames: set[str]) -> set[str]:
        """Remove skip list accounts from results.
        
        Args:
            usernames: Set of usernames to filter
            
        Returns:
            Filtered set with skip list accounts removed
        """
        return usernames - self.skip_list
    
    def compare(self, old: Snapshot, new: Snapshot) -> ComparisonResult:
        """Compare two snapshots and return differences.
        
        Args:
            old: Previous snapshot
            new: Current snapshot
            
        Returns:
            ComparisonResult with unfollowers, not_following_back, and new_followers
        """
        old_followers_set = set(old.followers)
        new_followers_set = set(new.followers)
        new_following_set = set(new.following)
        
        # Compute raw differences
        unfollowers = self.compute_unfollowers(old_followers_set, new_followers_set)
        not_following_back = self.compute_not_following_back(new_following_set, new_followers_set)
        new_followers = new_followers_set - old_followers_set
        
        # Apply skip list filtering
        unfollowers = self.apply_skip_filter(unfollowers)
        not_following_back = self.apply_skip_filter(not_following_back)
        new_followers = self.apply_skip_filter(new_followers)
        
        # Create timestamp for detection
        current_timestamp = datetime.now(timezone.utc).isoformat()
        
        # Create unfollowed timestamps mapping
        unfollowed_timestamps = {username: current_timestamp for username in unfollowers}
        
        return ComparisonResult(
            unfollowers=sorted(list(unfollowers)),
            not_following_back=sorted(list(not_following_back)),
            new_followers=sorted(list(new_followers)),
            timestamp=current_timestamp,
            unfollowed_timestamps=unfollowed_timestamps
        )
