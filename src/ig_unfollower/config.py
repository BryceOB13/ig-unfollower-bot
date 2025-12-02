"""Configuration management module."""

import json
import os
from dataclasses import dataclass, asdict
from typing import Any


@dataclass
class Config:
    """Configuration settings for the IG Unfollower tool."""
    
    chrome_profile_path: str
    action_delay_min: float  # seconds
    action_delay_max: float
    scroll_delay: float  # Legacy - used as fallback
    min_scroll_delay: float  # Minimum adaptive delay (Requirements 6.2)
    max_scroll_delay: float  # Maximum adaptive delay (Requirements 6.3)
    element_timeout: int
    max_retries: int
    skip_verified: bool
    skip_follower_threshold: int | None


class ConfigManager:
    """Handles configuration loading and validation."""
    
    # Default configuration values
    DEFAULT_CHROME_PROFILE_PATH = "~/.config/google-chrome/Default"
    DEFAULT_ACTION_DELAY_MIN = 3.0
    DEFAULT_ACTION_DELAY_MAX = 10.0
    DEFAULT_SCROLL_DELAY = 1.0
    DEFAULT_MIN_SCROLL_DELAY = 0.2  # Requirements 6.2
    DEFAULT_MAX_SCROLL_DELAY = 2.0  # Requirements 6.3
    DEFAULT_ELEMENT_TIMEOUT = 10
    DEFAULT_MAX_RETRIES = 3
    DEFAULT_SKIP_VERIFIED = True
    DEFAULT_SKIP_FOLLOWER_THRESHOLD = 1000000
    
    def __init__(self, filepath: str = "config.json"):
        """Initialize with config file path."""
        self.filepath = filepath
    
    def get_default(self) -> Config:
        """Return default configuration."""
        return Config(
            chrome_profile_path=self.DEFAULT_CHROME_PROFILE_PATH,
            action_delay_min=self.DEFAULT_ACTION_DELAY_MIN,
            action_delay_max=self.DEFAULT_ACTION_DELAY_MAX,
            scroll_delay=self.DEFAULT_SCROLL_DELAY,
            min_scroll_delay=self.DEFAULT_MIN_SCROLL_DELAY,
            max_scroll_delay=self.DEFAULT_MAX_SCROLL_DELAY,
            element_timeout=self.DEFAULT_ELEMENT_TIMEOUT,
            max_retries=self.DEFAULT_MAX_RETRIES,
            skip_verified=self.DEFAULT_SKIP_VERIFIED,
            skip_follower_threshold=self.DEFAULT_SKIP_FOLLOWER_THRESHOLD,
        )
    
    def load(self) -> Config:
        """Load and validate configuration.
        
        Returns default values for any missing fields.
        If the config file doesn't exist, returns all defaults.
        """
        defaults = self.get_default()
        
        if not os.path.exists(self.filepath):
            return defaults
        
        try:
            with open(self.filepath, "r", encoding="utf-8") as f:
                data: dict[str, Any] = json.load(f)
        except (json.JSONDecodeError, OSError):
            return defaults
        
        return Config(
            chrome_profile_path=data.get("chrome_profile_path", defaults.chrome_profile_path),
            action_delay_min=float(data.get("action_delay_min", defaults.action_delay_min)),
            action_delay_max=float(data.get("action_delay_max", defaults.action_delay_max)),
            scroll_delay=float(data.get("scroll_delay", defaults.scroll_delay)),
            min_scroll_delay=float(data.get("min_scroll_delay", defaults.min_scroll_delay)),
            max_scroll_delay=float(data.get("max_scroll_delay", defaults.max_scroll_delay)),
            element_timeout=int(data.get("element_timeout", defaults.element_timeout)),
            max_retries=int(data.get("max_retries", defaults.max_retries)),
            skip_verified=bool(data.get("skip_verified", defaults.skip_verified)),
            skip_follower_threshold=data.get("skip_follower_threshold", defaults.skip_follower_threshold),
        )
    
    def save(self, config: Config) -> None:
        """Save configuration to file."""
        with open(self.filepath, "w", encoding="utf-8") as f:
            json.dump(asdict(config), f, indent=2)
