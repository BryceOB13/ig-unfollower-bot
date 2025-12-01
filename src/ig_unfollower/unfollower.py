"""Unfollow executor module for automated unfollow actions."""

import logging
import random
import time
from dataclasses import dataclass, field

from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    NoSuchElementException,
    WebDriverException,
)

from .browser import BrowserManager, retry_operation
from .config import Config, ConfigManager
from .history import HistoryManager


logger = logging.getLogger(__name__)


@dataclass
class UnfollowResult:
    """Result summary of an unfollow execution run."""
    
    successful: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    failed: list[str] = field(default_factory=list)
    dry_run: bool = False


class UnfollowExecutor:
    """Handles automated unfollow actions with skip list filtering.
    
    Executes unfollow operations on target accounts while respecting
    skip lists, history, and rate limiting constraints.
    """
    
    PROFILE_URL_TEMPLATE = "https://www.instagram.com/{username}/"
    
    def __init__(
        self,
        browser: BrowserManager,
        skip_list: set[str],
        dry_run: bool = False,
        config: Config | None = None,
        history_manager: HistoryManager | None = None,
    ):
        """Initialize with browser, skip list, and dry run flag.
        
        Args:
            browser: BrowserManager instance for browser automation.
            skip_list: Set of usernames to skip during unfollow.
            dry_run: If True, simulate actions without executing.
            config: Configuration object. If None, loads from default.
            history_manager: HistoryManager for tracking unfollows.
        """
        self.browser = browser
        self.skip_list = skip_list
        self.dry_run = dry_run
        self.config = config or ConfigManager().load()
        self.history_manager = history_manager or HistoryManager()

    def _random_delay(self) -> float:
        """Wait a random delay between actions within configured bounds.
        
        The delay is between action_delay_min and action_delay_max seconds
        (default 3-10 seconds) to mimic human behavior and avoid rate limiting.
        
        Returns:
            The actual delay time in seconds.
        """
        delay = random.uniform(
            self.config.action_delay_min,
            self.config.action_delay_max
        )
        time.sleep(delay)
        return delay
    
    def _click_following_button(self) -> bool:
        """Click the 'Following' button on a user's profile page.
        
        Returns:
            True if button was clicked successfully, False otherwise.
        """
        if self.browser.driver is None:
            return False
        
        try:
            # Look for the "Following" button on the profile
            # Instagram uses various selectors for this button
            following_button_selectors = [
                (By.XPATH, "//button[.//div[text()='Following']]"),
                (By.XPATH, "//button[contains(@class, '_acan') and .//div[text()='Following']]"),
                (By.XPATH, "//div[text()='Following']/ancestor::button"),
                (By.CSS_SELECTOR, "button[type='button'] div:has-text('Following')"),
            ]
            
            for selector in following_button_selectors:
                try:
                    button = WebDriverWait(self.browser.driver, 5).until(
                        EC.element_to_be_clickable(selector)
                    )
                    button.click()
                    return True
                except (TimeoutException, NoSuchElementException):
                    continue
            
            logger.warning("Could not find Following button")
            return False
            
        except WebDriverException as e:
            logger.error(f"Error clicking Following button: {e}")
            return False
    
    def _confirm_unfollow(self) -> bool:
        """Confirm unfollow action in the popup dialog.
        
        Returns:
            True if unfollow was confirmed successfully, False otherwise.
        """
        if self.browser.driver is None:
            return False
        
        try:
            # Look for the "Unfollow" confirmation button in the dialog
            unfollow_confirm_selectors = [
                (By.XPATH, "//button[text()='Unfollow']"),
                (By.XPATH, "//span[text()='Unfollow']/ancestor::button"),
                (By.XPATH, "//div[@role='dialog']//button[contains(text(), 'Unfollow')]"),
                (By.CSS_SELECTOR, "button._a9--._ap36._a9_1"),
            ]
            
            for selector in unfollow_confirm_selectors:
                try:
                    confirm_button = WebDriverWait(self.browser.driver, 5).until(
                        EC.element_to_be_clickable(selector)
                    )
                    confirm_button.click()
                    return True
                except (TimeoutException, NoSuchElementException):
                    continue
            
            logger.warning("Could not find Unfollow confirmation button")
            return False
            
        except WebDriverException as e:
            logger.error(f"Error confirming unfollow: {e}")
            return False

    def _navigate_to_profile(self, username: str) -> bool:
        """Navigate to a user's profile page.
        
        Args:
            username: Instagram username to navigate to.
            
        Returns:
            True if navigation successful, False otherwise.
        """
        if self.browser.driver is None:
            return False
        
        try:
            profile_url = self.PROFILE_URL_TEMPLATE.format(username=username)
            self.browser.driver.get(profile_url)
            time.sleep(2)  # Allow page to load
            
            # Verify we're on the profile page
            # Check for profile-specific elements
            try:
                WebDriverWait(self.browser.driver, 10).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "header section"))
                )
                return True
            except TimeoutException:
                logger.warning(f"Profile page for {username} did not load properly")
                return False
                
        except WebDriverException as e:
            logger.error(f"Error navigating to profile {username}: {e}")
            return False
    
    def unfollow_user(self, username: str) -> bool:
        """Navigate to user profile and execute unfollow action.
        
        In dry run mode, simulates the action without executing.
        Uses retry logic for error handling.
        
        Args:
            username: Instagram username to unfollow.
            
        Returns:
            True if unfollow was successful (or simulated in dry run),
            False otherwise.
        """
        logger.info(f"{'[DRY RUN] ' if self.dry_run else ''}Processing unfollow for: {username}")
        
        if self.dry_run:
            # Simulate the action - log what would happen
            logger.info(f"[DRY RUN] Would navigate to {username}'s profile")
            logger.info(f"[DRY RUN] Would click Following button")
            logger.info(f"[DRY RUN] Would confirm unfollow")
            return True
        
        # Use retry logic for the actual unfollow operation
        max_retries = self.config.max_retries
        
        for attempt in range(max_retries):
            try:
                # Navigate to user's profile
                if not self._navigate_to_profile(username):
                    if attempt < max_retries - 1:
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for {username}")
                        time.sleep(2 ** attempt)  # Exponential backoff
                        continue
                    return False
                
                # Click the Following button
                if not self._click_following_button():
                    if attempt < max_retries - 1:
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for {username}")
                        time.sleep(2 ** attempt)
                        continue
                    return False
                
                time.sleep(1)  # Wait for dialog to appear
                
                # Confirm the unfollow action
                if not self._confirm_unfollow():
                    if attempt < max_retries - 1:
                        logger.warning(f"Retry {attempt + 1}/{max_retries} for {username}")
                        time.sleep(2 ** attempt)
                        continue
                    return False
                
                logger.info(f"Successfully unfollowed: {username}")
                return True
                
            except WebDriverException as e:
                logger.error(f"Error unfollowing {username}: {e}")
                if attempt < max_retries - 1:
                    logger.warning(f"Retry {attempt + 1}/{max_retries} for {username}")
                    time.sleep(2 ** attempt)
                    continue
                return False
        
        return False

    def execute(self, targets: list[str], max_unfollows: int = 50) -> UnfollowResult:
        """Execute unfollows on target list up to max limit.
        
        Filters targets through skip list and history before processing.
        Records successful unfollows to history (unless in dry run mode).
        
        Args:
            targets: List of usernames to potentially unfollow.
            max_unfollows: Maximum number of unfollow actions to perform.
            
        Returns:
            UnfollowResult with successful, skipped, and failed lists.
        """
        result = UnfollowResult(dry_run=self.dry_run)
        processed_count = 0
        
        logger.info(f"Starting unfollow execution (dry_run={self.dry_run}, max={max_unfollows})")
        logger.info(f"Total targets: {len(targets)}, Skip list size: {len(self.skip_list)}")
        
        for username in targets:
            # Check if we've reached the max unfollows limit
            if processed_count >= max_unfollows:
                logger.info(f"Reached max unfollows limit ({max_unfollows})")
                break
            
            # Filter: Skip if in skip list
            if username in self.skip_list:
                logger.info(f"Skipping {username}: in skip list")
                result.skipped.append(username)
                continue
            
            # Filter: Skip if previously unfollowed
            if self.history_manager.was_unfollowed(username):
                logger.info(f"Skipping {username}: previously unfollowed")
                result.skipped.append(username)
                continue
            
            # Execute unfollow
            success = self.unfollow_user(username)
            
            if success:
                result.successful.append(username)
                processed_count += 1
                
                # Record to history (only if not dry run)
                if not self.dry_run:
                    self.history_manager.record_unfollow(username)
                
                # Add random delay between actions
                if processed_count < max_unfollows and processed_count < len(targets):
                    delay = self._random_delay()
                    logger.debug(f"Waiting {delay:.1f}s before next action")
            else:
                result.failed.append(username)
                logger.warning(f"Failed to unfollow: {username}")
        
        # Log summary
        logger.info(
            f"Unfollow execution complete: "
            f"{len(result.successful)} successful, "
            f"{len(result.skipped)} skipped, "
            f"{len(result.failed)} failed"
        )
        
        return result
