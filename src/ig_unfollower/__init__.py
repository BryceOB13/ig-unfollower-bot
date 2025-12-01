"""IG Unfollower - Instagram follower monitoring and management tool."""

__version__ = "0.1.0"

from .browser import BrowserManager, retry_with_backoff, retry_operation
from .config import Config, ConfigManager

__all__ = [
    "BrowserManager",
    "retry_with_backoff",
    "retry_operation",
    "Config",
    "ConfigManager",
]
