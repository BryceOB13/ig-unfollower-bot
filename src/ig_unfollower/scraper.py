"""Instagram scraper module for extracting follower/following data."""

import logging
import re
import time
from collections import deque
from typing import TYPE_CHECKING, Any, Callable

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


class AdaptiveDelayCalculator:
    """Calculates optimal scroll delays based on content loading performance.
    
    Requirements: 1.1, 1.2, 1.3, 1.4, 6.2, 6.3
    """
    
    def __init__(self, min_delay: float = 0.2, max_delay: float = 2.0):
        """Initialize with delay bounds.
        
        Args:
            min_delay: Minimum delay in seconds (floor).
            max_delay: Maximum delay in seconds (ceiling).
        """
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.recent_loads: deque[float] = deque(maxlen=5)  # Rolling window of 5
    
    def record_load(self, items_loaded: int, duration: float) -> None:
        """Record a load measurement for adaptive calculation.
        
        Args:
            items_loaded: Number of items loaded in this iteration.
            duration: Time taken in seconds.
        """
        if duration > 0 and items_loaded >= 0:
            # Calculate load rate (items per second)
            load_rate = items_loaded / duration if items_loaded > 0 else 0.1
            self.recent_loads.append(load_rate)
    
    def get_next_delay(self) -> float:
        """Return optimal delay based on recent load performance.
        
        Returns:
            Delay in seconds, bounded by min_delay and max_delay.
        """
        if not self.recent_loads:
            return self.max_delay  # Conservative start
        
        # Calculate average load rate from recent measurements
        avg_rate = sum(self.recent_loads) / len(self.recent_loads)
        
        # Map load rate to delay:
        # Fast loading (>10 items/sec) -> min delay
        # Slow loading (<2 items/sec) -> max delay
        if avg_rate > 10:
            delay = self.min_delay
        elif avg_rate > 5:
            delay = self.min_delay + (self.max_delay - self.min_delay) * 0.25
        elif avg_rate > 2:
            delay = self.min_delay + (self.max_delay - self.min_delay) * 0.5
        else:
            delay = self.max_delay
        
        # Enforce bounds
        return max(self.min_delay, min(self.max_delay, delay))


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

    def _scroll_and_extract_unified(
        self, modal: WebElement, seen_usernames: set[str]
    ) -> dict[str, Any]:
        """Single JS call for scroll + extract + end detection.
        
        Requirements: 2.1, 2.2, 2.3
        
        Args:
            modal: The modal WebElement.
            seen_usernames: Set of usernames already collected (lowercase).
        
        Returns:
            Dict with keys: success, scrolled, at_end, new_usernames, scroll_info
        """
        seen_list = list(seen_usernames)
        
        result = self.driver.execute_script("""
            const modal = arguments[0];
            const seenUsernames = new Set(arguments[1].map(u => u.toLowerCase()));
            
            // Find scrollable element
            function findScrollableElement(modal) {
                const divs = modal.querySelectorAll('div');
                for (const div of divs) {
                    const style = div.getAttribute('style') || '';
                    const computed = window.getComputedStyle(div);
                    const isScrollable = (
                        style.includes('overflow: hidden auto') || 
                        style.includes('overflow-y: auto') ||
                        style.includes('overflow: auto') ||
                        computed.overflowY === 'auto' || 
                        computed.overflowY === 'scroll'
                    );
                    if (isScrollable && div.scrollHeight > div.clientHeight) {
                        return div;
                    }
                }
                return null;
            }
            
            // Extract usernames from current DOM
            function extractNewUsernames(modal, seenUsernames) {
                const excludedPaths = new Set([
                    'explore', 'direct', 'accounts', 'p', 'reel', 
                    'stories', 'reels', 'tv', 'live', 'tags', 'locations',
                    'followers', 'following', ''
                ]);
                const newUsernames = [];
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
                        !seenUsernames.has(username.toLowerCase())) {
                        seenUsernames.add(username.toLowerCase());
                        newUsernames.push(username);
                    }
                }
                return newUsernames;
            }
            
            const scrollable = findScrollableElement(modal);
            if (!scrollable) {
                return { success: false, error: 'No scrollable element found', 
                         scrolled: false, at_end: true, new_usernames: [] };
            }
            
            // Record scroll position before
            const beforeScroll = scrollable.scrollTop;
            const scrollHeight = scrollable.scrollHeight;
            const clientHeight = scrollable.clientHeight;
            
            // Perform scroll
            scrollable.scrollTop = scrollHeight;
            scrollable.scrollBy(0, 3000);
            
            // Check if we actually scrolled
            const afterScroll = scrollable.scrollTop;
            const scrolled = afterScroll > beforeScroll;
            const atEnd = (afterScroll + clientHeight >= scrollHeight - 50);
            
            // Extract usernames from current state
            const newUsernames = extractNewUsernames(modal, seenUsernames);
            
            return {
                success: true,
                scrolled: scrolled,
                at_end: atEnd,
                new_usernames: newUsernames,
                scroll_info: {
                    before: beforeScroll,
                    after: afterScroll,
                    height: scrollHeight,
                    client: clientHeight
                }
            };
        """, modal, seen_list)
        
        return result

    def _scroll_modal_to_end(
        self, 
        modal: WebElement, 
        expected_count: int = 0,
        progress_callback: Callable[[int, int], None] | None = None
    ) -> list[str]:
        """Scroll modal and extract usernames incrementally with adaptive timing.
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 4.1, 4.2, 4.3, 5.1
        
        Args:
            modal: The modal WebElement containing the scrollable list.
            expected_count: Expected number of users to load (from profile display).
            progress_callback: Optional callback for progress updates (current, total).
        
        Returns:
            List of all extracted usernames.
        """
        logger.info(f"Starting optimized modal scroll (expecting ~{expected_count} users)")
        
        # Wait for initial content to load - need enough time for Instagram
        time.sleep(2)
        
        # Initialize state
        all_usernames: set[str] = set()
        delay_calc = AdaptiveDelayCalculator(
            min_delay=getattr(self.config, 'min_scroll_delay', 0.5),  # Increased min
            max_delay=getattr(self.config, 'max_scroll_delay', 2.0)
        )
        
        no_new_content_count = 0
        max_no_new_content = 40  # Stop after 40 consecutive scrolls with no new content
        target_reached_count = 0
        scroll_iteration = 0
        max_iterations = 600
        termination_reason = "unknown"
        stall_detected = False  # Track if we've hit a stall
        
        # Diagnostic tracking
        scroll_positions: list[int] = []
        items_per_iteration: list[int] = []
        
        # Use slower scroll delay to avoid rate limiting
        base_scroll_delay = self.config.scroll_delay
        
        while no_new_content_count < max_no_new_content and scroll_iteration < max_iterations:
            scroll_iteration += 1
            start_time = time.time()
            
            try:
                # Requirement 2.1: Single consolidated JS call
                result = self._scroll_and_extract_unified(modal, all_usernames)
                
                if not result.get('success', False):
                    logger.warning(f"Scroll failed: {result.get('error', 'Unknown error')}")
                    time.sleep(1)
                    continue
                
                # Track scroll position for diagnostics
                scroll_info = result.get('scroll_info', {})
                current_scroll_pos = scroll_info.get('after', 0)
                scroll_positions.append(current_scroll_pos)
                
                # Requirement 3.1, 3.2: Incremental collection with deduplication
                new_usernames = result.get('new_usernames', [])
                before_count = len(all_usernames)
                for username in new_usernames:
                    all_usernames.add(username.lower())
                items_loaded = len(all_usernames) - before_count
                items_per_iteration.append(items_loaded)
                
                # Record performance for adaptive delay
                duration = time.time() - start_time
                delay_calc.record_load(items_loaded, duration)
                
                # Requirement 5.1: Progress callback
                if progress_callback:
                    progress_callback(len(all_usernames), expected_count)
                
                # Log progress every 5 iterations with diagnostics
                if scroll_iteration % 5 == 0:
                    logger.info(
                        f"Scroll #{scroll_iteration}: {len(all_usernames)}/{expected_count} users | "
                        f"no_new={no_new_content_count} | scroll_pos={current_scroll_pos} | "
                        f"new_this_iter={items_loaded}"
                    )
                
                # Track no new content - this is the main termination condition
                if items_loaded == 0:
                    no_new_content_count += 1
                    # Every 10 failed attempts, try aggressive scroll jiggle
                    if no_new_content_count % 10 == 0:
                        logger.info(f"Scroll jiggle attempt (no_new_content={no_new_content_count})")
                        # Try scrolling to different positions to trigger lazy loading
                        for jiggle_pos in [0, 0.25, 0.5, 0.75, 1.0]:
                            self.driver.execute_script("""
                                const modal = arguments[0];
                                const ratio = arguments[1];
                                const divs = modal.querySelectorAll('div');
                                for (const div of divs) {
                                    if (div.scrollHeight > div.clientHeight) {
                                        div.scrollTop = div.scrollHeight * ratio;
                                    }
                                }
                            """, modal, jiggle_pos)
                            time.sleep(0.5)
                            # Extract at each position
                            jiggle_result = self._scroll_and_extract_unified(modal, all_usernames)
                            if jiggle_result.get('success'):
                                jiggle_new = jiggle_result.get('new_usernames', [])
                                for username in jiggle_new:
                                    all_usernames.add(username.lower())
                                if jiggle_new:
                                    logger.info(f"Jiggle found {len(jiggle_new)} users at {jiggle_pos*100:.0f}%")
                                    no_new_content_count = 0  # Reset if we found something
                        # Final scroll back to bottom
                        self.driver.execute_script("""
                            const modal = arguments[0];
                            const divs = modal.querySelectorAll('div');
                            for (const div of divs) {
                                if (div.scrollHeight > div.clientHeight) {
                                    div.scrollTop = div.scrollHeight;
                                }
                            }
                        """, modal)
                        time.sleep(1)
                else:
                    no_new_content_count = 0  # Reset on any new content
                    stall_detected = False  # Reset stall flag
                
                # Early termination only if we have 100% of expected
                if expected_count > 0 and len(all_usernames) >= expected_count:
                    target_reached_count += 1
                    if target_reached_count >= 5:
                        termination_reason = f"target_reached ({len(all_usernames)} >= {expected_count})"
                        break
                else:
                    target_reached_count = 0
                
                # Progressive delay - slower when stalling to avoid rate limits
                if no_new_content_count > 5:
                    stall_detected = True
                    # Use progressively longer delays when stalling
                    delay = base_scroll_delay * (1 + no_new_content_count * 0.1)
                    delay = min(delay, 5.0)  # Cap at 5 seconds
                else:
                    delay = base_scroll_delay
                
                time.sleep(delay)
                
            except StaleElementReferenceException:
                logger.warning("Modal became stale during scroll")
                termination_reason = "stale_element"
                break
            except Exception as e:
                logger.warning(f"Scroll error: {e}")
                time.sleep(0.5)
                continue
        
        # Determine termination reason if not already set
        if termination_reason == "unknown":
            if no_new_content_count >= max_no_new_content:
                termination_reason = f"no_new_content ({no_new_content_count} consecutive)"
            elif scroll_iteration >= max_iterations:
                termination_reason = f"max_iterations ({max_iterations})"
        
        # SWEEP PHASE: If we didn't get enough users, do a slow scroll back up to catch missed ones
        completeness = (len(all_usernames) / expected_count * 100) if expected_count > 0 else 100
        if completeness < 95 and expected_count > 0:
            logger.info(f"Starting SWEEP phase - only {completeness:.1f}% complete, looking for missed users...")
            sweep_found = self._sweep_for_missed_users(modal, all_usernames, expected_count)
            logger.info(f"Sweep found {sweep_found} additional users")
            completeness = (len(all_usernames) / expected_count * 100) if expected_count > 0 else 100
        
        # Generate diagnostic report
        logger.info("=" * 60)
        logger.info("SCROLL TERMINATION REPORT")
        logger.info("=" * 60)
        logger.info(f"Termination reason: {termination_reason}")
        logger.info(f"Total iterations: {scroll_iteration}")
        logger.info(f"Users collected: {len(all_usernames)}/{expected_count} ({completeness:.1f}%)")
        logger.info(f"Final no_new_content_count: {no_new_content_count}")
        if scroll_positions:
            logger.info(f"Final scroll position: {scroll_positions[-1]}")
            if len(scroll_positions) >= 10:
                last_10_positions = scroll_positions[-10:]
                if len(set(last_10_positions)) == 1:
                    logger.info("WARNING: Scroll position unchanged for last 10 iterations!")
        if items_per_iteration:
            recent_items = items_per_iteration[-20:] if len(items_per_iteration) >= 20 else items_per_iteration
            logger.info(f"Items loaded in last {len(recent_items)} iterations: {recent_items}")
        logger.info("=" * 60)
        
        # Remove own username if present
        all_usernames.discard(self.username.lower())
        
        final_usernames = list(all_usernames)
        logger.info(f"Optimized scroll complete: {len(final_usernames)} users in {scroll_iteration} iterations")
        
        return final_usernames
    
    def _sweep_for_missed_users(
        self, 
        modal: WebElement, 
        all_usernames: set[str], 
        expected_count: int
    ) -> int:
        """Slowly scroll back through the list to catch any missed users.
        
        Instagram's virtual scrolling can skip elements when scrolling fast.
        This method scrolls slowly in both directions to catch missed users.
        
        Args:
            modal: The modal WebElement.
            all_usernames: Set of already collected usernames (will be modified).
            expected_count: Expected total count.
        
        Returns:
            Number of new users found during sweep.
        """
        initial_count = len(all_usernames)
        
        try:
            # First, scroll to top
            logger.info("Sweep: Scrolling to top...")
            self.driver.execute_script("""
                const modal = arguments[0];
                const divs = modal.querySelectorAll('div');
                for (const div of divs) {
                    if (div.scrollHeight > div.clientHeight) {
                        div.scrollTop = 0;
                    }
                }
            """, modal)
            time.sleep(2)
            
            # Extract any users visible at top
            result = self._scroll_and_extract_unified(modal, all_usernames)
            if result.get('success'):
                for username in result.get('new_usernames', []):
                    all_usernames.add(username.lower())
            
            # Get scroll height for calculating increments
            scroll_info = self.driver.execute_script("""
                const modal = arguments[0];
                const divs = modal.querySelectorAll('div');
                for (const div of divs) {
                    if (div.scrollHeight > div.clientHeight) {
                        return { height: div.scrollHeight, client: div.clientHeight };
                    }
                }
                return { height: 0, client: 0 };
            """, modal)
            
            scroll_height = scroll_info.get('height', 0)
            client_height = scroll_info.get('client', 400)
            
            if scroll_height == 0:
                return len(all_usernames) - initial_count
            
            # Sweep down slowly - smaller increments than normal scrolling
            increment = client_height // 2  # Half a screen at a time
            current_pos = 0
            sweep_iterations = 0
            max_sweep_iterations = 100
            
            logger.info(f"Sweep: Scrolling down slowly (increment={increment}px)...")
            
            while current_pos < scroll_height and sweep_iterations < max_sweep_iterations:
                sweep_iterations += 1
                current_pos += increment
                
                self.driver.execute_script("""
                    const modal = arguments[0];
                    const targetPos = arguments[1];
                    const divs = modal.querySelectorAll('div');
                    for (const div of divs) {
                        if (div.scrollHeight > div.clientHeight) {
                            div.scrollTop = targetPos;
                        }
                    }
                """, modal, current_pos)
                
                # Longer delay to let content render
                time.sleep(0.8)
                
                # Extract users at this position
                result = self._scroll_and_extract_unified(modal, all_usernames)
                if result.get('success'):
                    new_users = result.get('new_usernames', [])
                    for username in new_users:
                        all_usernames.add(username.lower())
                    if new_users:
                        logger.debug(f"Sweep found {len(new_users)} new users at position {current_pos}")
                
                # Check if we've reached target
                if len(all_usernames) >= expected_count:
                    logger.info(f"Sweep: Reached target count {len(all_usernames)}>={expected_count}")
                    break
            
            # One more sweep back up with different cadence
            if len(all_usernames) < expected_count * 0.98:
                logger.info("Sweep: Second pass scrolling up...")
                current_pos = scroll_height
                
                while current_pos > 0 and sweep_iterations < max_sweep_iterations * 2:
                    sweep_iterations += 1
                    current_pos -= int(increment * 1.5)  # Different cadence going up
                    current_pos = max(0, current_pos)
                    
                    self.driver.execute_script("""
                        const modal = arguments[0];
                        const targetPos = arguments[1];
                        const divs = modal.querySelectorAll('div');
                        for (const div of divs) {
                            if (div.scrollHeight > div.clientHeight) {
                                div.scrollTop = targetPos;
                            }
                        }
                    """, modal, current_pos)
                    
                    time.sleep(0.6)
                    
                    result = self._scroll_and_extract_unified(modal, all_usernames)
                    if result.get('success'):
                        for username in result.get('new_usernames', []):
                            all_usernames.add(username.lower())
                    
                    if len(all_usernames) >= expected_count:
                        break
            
        except Exception as e:
            logger.warning(f"Sweep error: {e}")
        
        found = len(all_usernames) - initial_count
        logger.info(f"Sweep complete: found {found} additional users")
        return found
    
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
    def scrape_followers(
        self, 
        progress_callback: Callable[[int, int], None] | None = None
    ) -> list[str]:
        """Open followers modal, scroll to load all, extract usernames.
        
        Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 5.1, 7.1
        
        Args:
            progress_callback: Optional callback for progress updates (current, total).
        
        Returns:
            List of follower usernames.
        
        Raises:
            RuntimeError: If modal cannot be opened or scraping fails.
        """
        logger.info(f"Starting optimized followers scrape for {self.username}")
        
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
            # Requirement 3.4: Scroll and extract incrementally, return directly
            usernames = self._scroll_modal_to_end(
                modal, 
                expected_count=followers_count,
                progress_callback=progress_callback
            )
            
            logger.info(f"Scraped {len(usernames)} followers (expected {followers_count})")
            return usernames
            
        finally:
            # Requirement 2.5: Close the modal
            self._close_modal()
    
    @retry_with_backoff(max_retries=3)
    def scrape_following(
        self, 
        progress_callback: Callable[[int, int], None] | None = None
    ) -> list[str]:
        """Open following modal, scroll to load all, extract usernames.
        
        Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 5.1, 7.2
        
        Args:
            progress_callback: Optional callback for progress updates (current, total).
        
        Returns:
            List of following usernames.
        
        Raises:
            RuntimeError: If modal cannot be opened or scraping fails.
        """
        logger.info(f"Starting optimized following scrape for {self.username}")
        
        # Ensure we're on the profile page
        if self.username not in self.driver.current_url:
            self.navigate_to_profile()
        
        # Get expected count from profile
        _, following_count = self.get_profile_counts()
        
        all_usernames: set[str] = set()
        max_attempts = 3
        
        for attempt in range(max_attempts):
            # Requirement 3.1: Click following count to open modal
            modal = self._open_modal(self.FOLLOWING_LINK_SELECTOR, "Following")
            if modal is None:
                raise RuntimeError("Failed to open following modal")
            
            try:
                # Requirement 3.4: Scroll and extract incrementally
                usernames = self._scroll_modal_to_end(
                    modal, 
                    expected_count=following_count,
                    progress_callback=progress_callback
                )
                
                # Add to cumulative set
                for u in usernames:
                    all_usernames.add(u.lower())
                
                completeness = len(all_usernames) / following_count * 100 if following_count > 0 else 100
                logger.info(f"Attempt {attempt + 1}: {len(all_usernames)}/{following_count} ({completeness:.1f}%)")
                
                # If we got enough, stop
                if len(all_usernames) >= following_count * 0.95:
                    break
                    
                # Otherwise, close modal and try again
                if attempt < max_attempts - 1:
                    logger.info(f"Only {completeness:.1f}% complete, reopening modal for another pass...")
                    self._close_modal()
                    time.sleep(2)
                    # Refresh the page to reset Instagram's state
                    self.navigate_to_profile()
                    time.sleep(1)
                    
            finally:
                if attempt == max_attempts - 1 or len(all_usernames) >= following_count * 0.95:
                    self._close_modal()
        
        final_usernames = list(all_usernames)
        logger.info(f"Scraped {len(final_usernames)} following (expected {following_count})")
        return final_usernames
