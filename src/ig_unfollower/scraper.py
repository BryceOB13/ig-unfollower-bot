"""Instagram scraper module for extracting follower/following data."""

import logging
import re
import time
from typing import TYPE_CHECKING

from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
)

from .browser import BrowserManager, retry_with_backoff
from .config import Config, ConfigManager

if TYPE_CHECKING:
    from selenium.webdriver.remote.webdriver import WebDriver


logger = logging.getLogger(__name__)


class InstagramScraper:
    """Handles navigation and data extraction from Instagram."""
    
    PROFILE_URL_TEMPLATE = "https://www.instagram.com/{username}/"
    
    # CSS selectors for Instagram elements
    FOLLOWERS_LINK_SELECTOR = "a[href*='/followers/']"
    FOLLOWING_LINK_SELECTOR = "a[href*='/following/']"
    MODAL_SELECTOR = "div[role='dialog']"
    MODAL_LIST_SELECTOR = "div[role='dialog'] div[style*='overflow']"
    USERNAME_SELECTOR = "a[role='link'] span"
    
    def __init__(self, browser: BrowserManager, username: str, config: Config | None = None):
        """Initialize scraper with browser and target username.
        
        Args:
            browser: BrowserManager instance for browser automation.
            username: Instagram username to scrape.
            config: Configuration object. If None, loads from default config file.
        """
        self.browser = browser
        self.username = username
        
        if config is None:
            config = ConfigManager().load()
        self.config = config
    
    @property
    def driver(self) -> "WebDriver":
        """Get the WebDriver instance from browser manager."""
        if self.browser.driver is None:
            raise RuntimeError("Browser not started. Call browser.start() first.")
        return self.browser.driver

    
    @retry_with_backoff(max_retries=3)
    def navigate_to_profile(self) -> bool:
        """Navigate to user's profile page.
        
        Returns:
            True if navigation successful, False otherwise.
        """
        profile_url = self.PROFILE_URL_TEMPLATE.format(username=self.username)
        logger.info(f"Navigating to profile: {profile_url}")
        
        self.driver.get(profile_url)
        time.sleep(2)  # Allow page to load
        
        # Verify we're on the profile page by checking for profile elements
        try:
            # Look for the profile header or username element
            self.browser.wait_for_element(
                (By.CSS_SELECTOR, "header section"),
                timeout=self.config.element_timeout,
                condition="presence"
            )
            logger.info(f"Successfully navigated to {self.username}'s profile")
            return True
        except TimeoutException:
            logger.error(f"Failed to load profile page for {self.username}")
            return False
    
    def get_profile_counts(self) -> tuple[int, int]:
        """Get the displayed follower and following counts from the profile page.
        
        Returns:
            Tuple of (followers_count, following_count).
        """
        followers_count = 0
        following_count = 0
        
        try:
            # Find the followers link and extract count
            followers_link = self.driver.find_element(By.CSS_SELECTOR, self.FOLLOWERS_LINK_SELECTOR)
            followers_text = followers_link.text.replace(",", "").replace(" ", "")
            # Extract number from text like "575 followers" or just "575"
            match = re.search(r"(\d+)", followers_text)
            if match:
                followers_count = int(match.group(1))
            
            # Find the following link and extract count
            following_link = self.driver.find_element(By.CSS_SELECTOR, self.FOLLOWING_LINK_SELECTOR)
            following_text = following_link.text.replace(",", "").replace(" ", "")
            match = re.search(r"(\d+)", following_text)
            if match:
                following_count = int(match.group(1))
            
            logger.info(f"Profile shows {followers_count} followers, {following_count} following")
            
        except (NoSuchElementException, ValueError) as e:
            logger.warning(f"Could not extract profile counts: {e}")
        
        return followers_count, following_count
    
    def _find_scrollable_element(self, modal: WebElement) -> WebElement:
        """Find the scrollable element within the modal using JavaScript.
        
        Args:
            modal: The modal WebElement.
            
        Returns:
            The scrollable WebElement.
        """
        scrollable = self.driver.execute_script("""
            const modal = arguments[0];
            // Instagram's modal structure: look for the div with "height: auto; overflow: hidden auto;"
            const divs = modal.querySelectorAll('div');
            for (const div of divs) {
                const style = div.getAttribute('style') || '';
                // Check for Instagram's specific overflow pattern
                if (style.includes('overflow: hidden auto') || 
                    style.includes('overflow-y: auto') ||
                    style.includes('overflow: auto')) {
                    if (div.scrollHeight > div.clientHeight) {
                        return div;
                    }
                }
            }
            // Second try: check computed styles
            for (const div of divs) {
                const computed = window.getComputedStyle(div);
                if ((computed.overflowY === 'auto' || computed.overflowY === 'scroll') && 
                    div.scrollHeight > div.clientHeight + 10) {
                    return div;
                }
            }
            return null;
        """, modal)
        
        if scrollable is None:
            logger.warning("Could not find scrollable container via JS, trying CSS selectors")
            scroll_selectors = [
                "div[style*='overflow: hidden auto']",
                "div[style*='overflow-y: auto']",
                "div._aano",
            ]
            for selector in scroll_selectors:
                try:
                    elements = modal.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        scroll_height = self.driver.execute_script("return arguments[0].scrollHeight", el)
                        client_height = self.driver.execute_script("return arguments[0].clientHeight", el)
                        if scroll_height > client_height:
                            scrollable = el
                            logger.info(f"Found scrollable via selector: {selector}")
                            break
                    if scrollable:
                        break
                except (NoSuchElementException, StaleElementReferenceException):
                    continue
        
        if scrollable is None:
            logger.warning("Could not find scrollable container, using modal itself")
            scrollable = modal
        else:
            logger.info("Found scrollable container in modal")
        
        return scrollable

    def _scroll_modal_to_end(self, modal: WebElement, expected_count: int = 0) -> None:
        """Scroll modal until all users are loaded or no new content appears.
        
        Args:
            modal: The modal WebElement containing the scrollable list.
            expected_count: Expected number of users to load (from profile display).
        """
        logger.info(f"Starting modal scroll to load all content (expecting ~{expected_count} users)")
        
        # Wait for initial content to load
        time.sleep(3)
        
        last_count = 0
        no_change_count = 0
        max_no_change = 40  # Stop after 40 consecutive scrolls with no new content
        scroll_iteration = 0
        
        # We want 100% of expected count - don't stop early
        target_count = expected_count if expected_count > 0 else 0
        
        while True:
            scroll_iteration += 1
            
            # Scroll using JavaScript directly on the modal to find and scroll the right element
            try:
                scroll_result = self.driver.execute_script("""
                    const modal = arguments[0];
                    
                    // Find ALL scrollable containers and scroll them all
                    const divs = modal.querySelectorAll('div');
                    let scrolled = false;
                    
                    for (const div of divs) {
                        const style = div.getAttribute('style') || '';
                        const computed = window.getComputedStyle(div);
                        
                        // Check if this div is scrollable
                        const isScrollable = (
                            style.includes('overflow: hidden auto') || 
                            style.includes('overflow-y: auto') ||
                            style.includes('overflow: auto') ||
                            computed.overflowY === 'auto' || 
                            computed.overflowY === 'scroll'
                        );
                        
                        if (isScrollable && div.scrollHeight > div.clientHeight) {
                            // Scroll this element
                            div.scrollTop = div.scrollHeight;
                            div.scrollBy(0, 5000);
                            scrolled = true;
                        }
                    }
                    
                    // Count unique usernames (case-insensitive)
                    const excludedPaths = new Set([
                        'explore', 'direct', 'accounts', 'p', 'reel', 
                        'stories', 'reels', 'tv', 'live', 'tags', 'locations',
                        'followers', 'following', ''
                    ]);
                    
                    const seen = new Set();
                    const links = modal.querySelectorAll('a[href^="/"]');
                    
                    for (const link of links) {
                        const href = link.getAttribute('href');
                        if (!href) continue;
                        
                        let username = href.split('?')[0].replace(/^\\//, '').split('/')[0];
                        
                        if (username && 
                            username.length > 0 && 
                            username.length <= 30 &&
                            /^[a-zA-Z0-9._]+$/.test(username) &&
                            !excludedPaths.has(username.toLowerCase()) &&
                            !seen.has(username.toLowerCase())) {
                            seen.add(username.toLowerCase());
                        }
                    }
                    
                    return { 
                        success: scrolled, 
                        count: seen.size
                    };
                """, modal)
                
                if not scroll_result.get('success', False):
                    # Try scrolling up then down to trigger loading
                    self.driver.execute_script("""
                        const modal = arguments[0];
                        const divs = modal.querySelectorAll('div');
                        for (const div of divs) {
                            if (div.scrollHeight > div.clientHeight) {
                                div.scrollTop = 0;
                            }
                        }
                    """, modal)
                    time.sleep(0.5)
                    self.driver.execute_script("""
                        const modal = arguments[0];
                        const divs = modal.querySelectorAll('div');
                        for (const div of divs) {
                            if (div.scrollHeight > div.clientHeight) {
                                div.scrollTop = div.scrollHeight;
                            }
                        }
                    """, modal)
                    
                current_count = scroll_result.get('count', 0)
                
            except StaleElementReferenceException:
                logger.warning("Modal became stale during scroll")
                break
            except Exception as e:
                logger.warning(f"Scroll error: {e}, continuing...")
                time.sleep(1)
                continue
            
            # Wait for content to load - Instagram needs time to fetch
            time.sleep(self.config.scroll_delay)
            
            # Log progress every 5 iterations
            if scroll_iteration % 5 == 0:
                logger.info(f"Scroll progress: loaded {current_count}/{expected_count} users (iteration {scroll_iteration})")
            
            # Check if we've reached the target (100%)
            if target_count > 0 and current_count >= target_count:
                logger.info(f"Reached target count: {current_count} >= {target_count}")
                # Do a few more scrolls to make sure we got everything
                for _ in range(5):
                    time.sleep(self.config.scroll_delay)
                    try:
                        self.driver.execute_script("""
                            const modal = arguments[0];
                            const divs = modal.querySelectorAll('div');
                            for (const div of divs) {
                                if (div.scrollHeight > div.clientHeight) {
                                    div.scrollTop = div.scrollHeight;
                                }
                            }
                        """, modal)
                    except:
                        pass
                break
            
            if current_count == last_count:
                no_change_count += 1
                
                # Every 10 failed attempts, try scrolling up then down to trigger loading
                if no_change_count % 10 == 0 and no_change_count < max_no_change:
                    logger.info(f"Trying scroll reset to trigger more loading...")
                    try:
                        self.driver.execute_script("""
                            const modal = arguments[0];
                            const divs = modal.querySelectorAll('div');
                            for (const div of divs) {
                                if (div.scrollHeight > div.clientHeight) {
                                    div.scrollTop = Math.max(0, div.scrollTop - 2000);
                                }
                            }
                        """, modal)
                        time.sleep(1)
                        self.driver.execute_script("""
                            const modal = arguments[0];
                            const divs = modal.querySelectorAll('div');
                            for (const div of divs) {
                                if (div.scrollHeight > div.clientHeight) {
                                    div.scrollTop = div.scrollHeight;
                                }
                            }
                        """, modal)
                    except:
                        pass
                
                if no_change_count >= max_no_change:
                    logger.info(f"No more content loading after {no_change_count} attempts (got {current_count}/{expected_count})")
                    break
            else:
                no_change_count = 0
                logger.debug(f"Loaded more users: {last_count} -> {current_count}")
            
            last_count = current_count
            
            # Safety limit to prevent infinite loops
            if scroll_iteration > 600:
                logger.warning("Reached maximum scroll iterations (600)")
                break
        
        logger.info(f"Finished scrolling modal - loaded {last_count} users (expected {expected_count})")
    
    def _extract_usernames_from_modal(self, modal: WebElement) -> list[str]:
        """Extract all usernames from modal list items.
        
        Args:
            modal: The modal WebElement containing the user list.
        
        Returns:
            List of extracted usernames (deduplicated, case-insensitive).
        """
        # Use JavaScript for more reliable extraction - avoids stale element issues
        # Case-insensitive deduplication happens in JS
        usernames = self.driver.execute_script("""
            const modal = arguments[0];
            const excludedPaths = new Set([
                'explore', 'direct', 'accounts', 'p', 'reel', 
                'stories', 'reels', 'tv', 'live', 'tags', 'locations',
                'followers', 'following', ''
            ]);
            
            // Use Map to store lowercase -> original case mapping
            const usernameMap = new Map();
            
            // Helper function to validate and add username
            function addUsername(username) {
                if (!username) return;
                username = username.trim();
                
                // Skip excluded paths
                if (excludedPaths.has(username.toLowerCase())) return;
                
                // Validate username format (alphanumeric, underscore, period, max 30 chars)
                if (username.length > 0 && 
                    username.length <= 30 &&
                    /^[a-zA-Z0-9._]+$/.test(username) &&
                    !usernameMap.has(username.toLowerCase())) {
                    usernameMap.set(username.toLowerCase(), username);
                }
            }
            
            // Method 1: Find all links with href starting with /
            const links = modal.querySelectorAll('a[href^="/"]');
            for (const link of links) {
                const href = link.getAttribute('href');
                if (!href) continue;
                
                // Extract username from href like "/username/?hl=en" or "/username/"
                let username = href.split('?')[0].replace(/^\\//, '').split('/')[0];
                addUsername(username);
            }
            
            // Method 2: Find usernames in span elements with specific Instagram classes
            const usernameSpans = modal.querySelectorAll('span._ap3a._aaco._aacw._aacx._aad7._aade');
            for (const span of usernameSpans) {
                addUsername(span.textContent);
            }
            
            // Return unique usernames (values from the map)
            return Array.from(usernameMap.values());
        """, modal)
        
        # Remove the logged-in user's own username if present (case-insensitive)
        usernames = [u for u in usernames if u.lower() != self.username.lower()]
        
        logger.info(f"Extracted {len(usernames)} unique usernames from modal")
        return usernames
    
    def _open_modal(self, link_selector: str, modal_name: str) -> WebElement | None:
        """Open a modal by clicking the specified link.
        
        Args:
            link_selector: CSS selector for the link to click.
            modal_name: Name of the modal for logging purposes.
        
        Returns:
            The modal WebElement if opened successfully, None otherwise.
        """
        try:
            # Find and click the link to open modal
            link = self.browser.wait_for_element(
                (By.CSS_SELECTOR, link_selector),
                timeout=self.config.element_timeout,
                condition="clickable"
            )
            link.click()
            logger.info(f"Clicked {modal_name} link")
            
            # Wait for modal to appear
            time.sleep(1)
            modal = self.browser.wait_for_element(
                (By.CSS_SELECTOR, self.MODAL_SELECTOR),
                timeout=self.config.element_timeout,
                condition="visible"
            )
            logger.info(f"{modal_name} modal opened")
            return modal
            
        except TimeoutException:
            logger.error(f"Failed to open {modal_name} modal")
            return None
    
    def _close_modal(self) -> None:
        """Close the currently open modal."""
        try:
            # Try clicking outside the modal or pressing Escape
            close_buttons = [
                (By.CSS_SELECTOR, "svg[aria-label='Close']"),
                (By.CSS_SELECTOR, "button[aria-label='Close']"),
                (By.CSS_SELECTOR, "div[role='dialog'] button"),
            ]
            
            for selector in close_buttons:
                try:
                    close_btn = WebDriverWait(self.driver, 2).until(
                        EC.element_to_be_clickable(selector)
                    )
                    close_btn.click()
                    logger.info("Modal closed via close button")
                    time.sleep(0.5)
                    return
                except (TimeoutException, NoSuchElementException):
                    continue
            
            # Fallback: press Escape key
            from selenium.webdriver.common.keys import Keys
            self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
            logger.info("Modal closed via Escape key")
            time.sleep(0.5)
            
        except Exception as e:
            logger.warning(f"Could not close modal: {e}")

    
    @retry_with_backoff(max_retries=3)
    def scrape_followers(self) -> list[str]:
        """Open followers modal, scroll to load all, extract usernames.
        
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5
        
        Returns:
            List of follower usernames.
        
        Raises:
            RuntimeError: If modal cannot be opened or scraping fails.
        """
        logger.info(f"Starting followers scrape for {self.username}")
        
        # Ensure we're on the profile page
        if self.username not in self.driver.current_url:
            self.navigate_to_profile()
        
        # Get expected count from profile
        followers_count, _ = self.get_profile_counts()
        
        # Requirement 2.1: Click followers count to open modal
        modal = self._open_modal(self.FOLLOWERS_LINK_SELECTOR, "Followers")
        if modal is None:
            raise RuntimeError("Failed to open followers modal")
        
        try:
            # Requirement 2.2: Scroll repeatedly until all followers are loaded
            self._scroll_modal_to_end(modal, expected_count=followers_count)
            
            # Requirement 2.3, 2.4: Extract all follower usernames
            usernames = self._extract_usernames_from_modal(modal)
            
            logger.info(f"Scraped {len(usernames)} followers (expected {followers_count})")
            return usernames
            
        finally:
            # Requirement 2.5: Close the modal
            self._close_modal()
    
    @retry_with_backoff(max_retries=3)
    def scrape_following(self) -> list[str]:
        """Open following modal, scroll to load all, extract usernames.
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5
        
        Returns:
            List of following usernames.
        
        Raises:
            RuntimeError: If modal cannot be opened or scraping fails.
        """
        logger.info(f"Starting following scrape for {self.username}")
        
        # Ensure we're on the profile page
        if self.username not in self.driver.current_url:
            self.navigate_to_profile()
        
        # Get expected count from profile
        _, following_count = self.get_profile_counts()
        
        # Requirement 3.1: Click following count to open modal
        modal = self._open_modal(self.FOLLOWING_LINK_SELECTOR, "Following")
        if modal is None:
            raise RuntimeError("Failed to open following modal")
        
        try:
            # Requirement 3.2: Scroll repeatedly until all following are loaded
            self._scroll_modal_to_end(modal, expected_count=following_count)
            
            # Requirement 3.3, 3.4: Extract all following usernames
            usernames = self._extract_usernames_from_modal(modal)
            
            logger.info(f"Scraped {len(usernames)} following (expected {following_count})")
            return usernames
            
        finally:
            # Requirement 3.5: Close the modal
            self._close_modal()
