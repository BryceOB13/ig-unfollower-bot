"""Unfollow executor module for automated unfollow actions."""

import logging
import random
import time
from dataclasses import dataclass, field

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
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
    
    def _dismiss_any_modal(self) -> None:
        """Dismiss any open modal/dialog that might be blocking clicks."""
        if self.browser.driver is None:
            return
        
        try:
            # Try to close any open dialog by pressing Escape
            body = self.browser.driver.find_element(By.TAG_NAME, "body")
            body.send_keys(Keys.ESCAPE)
            time.sleep(0.5)
        except WebDriverException:
            pass
        
        try:
            # Try clicking the close button if a dialog is open
            close_selectors = [
                (By.XPATH, "//div[@role='dialog']//svg[@aria-label='Close']/ancestor::div[@role='button']"),
                (By.XPATH, "//svg[@aria-label='Close']/.."),
                (By.CSS_SELECTOR, "[aria-label='Close']"),
            ]
            for selector in close_selectors:
                try:
                    close_btn = self.browser.driver.find_element(*selector)
                    self.browser.driver.execute_script("arguments[0].click();", close_btn)
                    time.sleep(0.5)
                    return
                except NoSuchElementException:
                    continue
        except WebDriverException:
            pass

    def _click_following_button(self) -> bool:
        """Click the 'Following' button on a user's profile page.
        
        Returns:
            True if button was clicked successfully, False otherwise.
        """
        if self.browser.driver is None:
            return False
        
        try:
            # First, dismiss any modal that might be blocking
            self._dismiss_any_modal()
            
            # Use JavaScript to find and click the Following button - most reliable
            result = self.browser.driver.execute_script(
                """
                // Method 1: Find button with "Following" text in header
                var headerButtons = document.querySelectorAll('header button');
                for (var btn of headerButtons) {
                    if (btn.textContent.trim() === 'Following') {
                        btn.click();
                        return {success: true, method: 'header button text'};
                    }
                }
                
                // Method 2: Find button containing div with "Following" text
                var allButtons = document.querySelectorAll('button');
                for (var btn of allButtons) {
                    var divs = btn.querySelectorAll('div');
                    for (var div of divs) {
                        if (div.textContent.trim() === 'Following') {
                            btn.click();
                            return {success: true, method: 'button>div text'};
                        }
                    }
                }
                
                // Method 3: Look for the specific button class pattern
                var followingBtns = document.querySelectorAll('button[class*="_aswp"]');
                for (var btn of followingBtns) {
                    if (btn.textContent.includes('Following')) {
                        btn.click();
                        return {success: true, method: 'class _aswp'};
                    }
                }
                
                return {success: false, error: 'Following button not found'};
                """
            )
            
            if result and result.get('success'):
                logger.info(f"Clicked Following button ({result.get('method')})")
                return True
            else:
                logger.warning(f"Could not find Following button: {result.get('error') if result else 'No result'}")
                return False
            
        except WebDriverException as e:
            logger.error(f"Error clicking Following button: {e}")
            return False
    
    def _confirm_unfollow(self) -> bool:
        """Confirm unfollow action in the popup dialog/menu.
        
        Instagram shows a menu modal with options like "Add to close friends",
        "Mute", "Restrict", and "Unfollow". We need to find and click the
        Unfollow option in this menu.
        
        Returns:
            True if unfollow was confirmed successfully, False otherwise.
        """
        if self.browser.driver is None:
            return False
        
        try:
            # Wait for the dialog/menu to appear
            time.sleep(1.5)
            
            # First check if dialog exists
            try:
                dialog = self.browser.driver.find_element(By.XPATH, "//div[@role='dialog']")
                logger.debug(f"Dialog found, searching for Unfollow option...")
            except NoSuchElementException:
                logger.warning("No dialog found after clicking Following button")
                return False
            
            # Use JavaScript to find and click the Unfollow option
            # This is the most reliable method based on the HTML structure
            result = self.browser.driver.execute_script(
                """
                // Find the dialog
                var dialog = document.querySelector('[role="dialog"]');
                if (!dialog) {
                    console.log('No dialog found');
                    return {success: false, error: 'No dialog found'};
                }
                
                // Method 1: Find all clickable elements and look for Unfollow text
                var buttons = dialog.querySelectorAll('[role="button"]');
                console.log('Found ' + buttons.length + ' buttons in dialog');
                
                for (var btn of buttons) {
                    var text = btn.textContent.trim();
                    if (text === 'Unfollow') {
                        console.log('Found Unfollow button, clicking...');
                        btn.click();
                        return {success: true, method: 'role=button direct'};
                    }
                }
                
                // Method 2: Find spans with Unfollow text
                var spans = dialog.querySelectorAll('span');
                for (var span of spans) {
                    if (span.textContent.trim() === 'Unfollow') {
                        console.log('Found Unfollow span, finding clickable parent...');
                        var clickable = span.closest('[role="button"]') || span.closest('button');
                        if (clickable) {
                            clickable.click();
                            return {success: true, method: 'span parent'};
                        } else {
                            // Click the span itself
                            span.click();
                            return {success: true, method: 'span direct'};
                        }
                    }
                }
                
                // Method 3: Use TreeWalker to find text nodes
                var walker = document.createTreeWalker(
                    dialog,
                    NodeFilter.SHOW_TEXT,
                    null,
                    false
                );
                
                while (walker.nextNode()) {
                    if (walker.currentNode.textContent.trim() === 'Unfollow') {
                        var el = walker.currentNode.parentElement;
                        var clickable = el.closest('[role="button"]') || el.closest('button') || el;
                        clickable.click();
                        return {success: true, method: 'treewalker'};
                    }
                }
                
                // Debug: list all text content in dialog
                var allText = [];
                var allSpans = dialog.querySelectorAll('span');
                allSpans.forEach(function(s) {
                    var t = s.textContent.trim();
                    if (t && t.length < 50) allText.push(t);
                });
                
                return {success: false, error: 'Unfollow not found', dialogTexts: allText.slice(0, 20)};
                """
            )
            
            if result and result.get('success'):
                logger.info(f"Clicked Unfollow via JS ({result.get('method')})")
                time.sleep(0.5)
                return True
            else:
                error = result.get('error', 'Unknown') if result else 'No result'
                texts = result.get('dialogTexts', []) if result else []
                logger.warning(f"Could not find Unfollow: {error}")
                if texts:
                    logger.debug(f"Dialog contains: {texts[:10]}")
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
