"""Browser management module for Chrome automation."""

import os
import time
from typing import Callable, TypeVar

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.remote.webelement import WebElement
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import (
    TimeoutException,
    StaleElementReferenceException,
    NoSuchElementException,
    WebDriverException,
)

from .config import Config, ConfigManager


T = TypeVar("T")


class BrowserManager:
    """Manages Chrome browser lifecycle and session handling."""
    
    INSTAGRAM_URL = "https://www.instagram.com"
    LOGIN_URL = "https://www.instagram.com/accounts/login/"
    
    def __init__(self, profile_path: str | None = None, config: Config | None = None):
        """Initialize browser with Chrome profile for session reuse.
        
        Args:
            profile_path: Path to Chrome profile directory. If None, uses config default.
            config: Configuration object. If None, loads from default config file.
        """
        if config is None:
            config = ConfigManager().load()
        
        self.config = config
        self.profile_path = profile_path or os.path.expanduser(config.chrome_profile_path)
        self.driver: webdriver.Chrome | None = None
    
    def start(self) -> webdriver.Chrome:
        """Launch Chrome browser in non-headless mode and return driver instance.
        
        Returns:
            The Chrome WebDriver instance.
        """
        options = Options()
        
        # Non-headless mode as per requirement 1.1
        options.add_argument("--start-maximized")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        
        # Use Chrome profile for session reuse (requirement 1.2)
        if self.profile_path and os.path.exists(os.path.dirname(self.profile_path)):
            options.add_argument(f"--user-data-dir={os.path.dirname(self.profile_path)}")
            options.add_argument(f"--profile-directory={os.path.basename(self.profile_path)}")
        
        self.driver = webdriver.Chrome(options=options)
        
        # Remove webdriver detection
        self.driver.execute_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        
        return self.driver

    def is_logged_in(self) -> bool:
        """Check if Instagram session is active.
        
        Returns:
            True if logged in, False otherwise.
        """
        if self.driver is None:
            return False
        
        try:
            self.driver.get(self.INSTAGRAM_URL)
            time.sleep(2)  # Allow page to load
            
            # Check for elements that indicate logged-in state
            # Profile icon or home feed elements indicate active session
            logged_in_indicators = [
                (By.CSS_SELECTOR, "svg[aria-label='Home']"),
                (By.CSS_SELECTOR, "a[href*='/direct/inbox/']"),
                (By.CSS_SELECTOR, "span[aria-label='Profile']"),
            ]
            
            for locator in logged_in_indicators:
                try:
                    self.driver.find_element(*locator)
                    return True
                except NoSuchElementException:
                    continue
            
            # Check if we're on the login page (not logged in)
            if "/accounts/login" in self.driver.current_url:
                return False
            
            return False
            
        except WebDriverException:
            return False
    
    def wait_for_element(
        self,
        locator: tuple[str, str],
        timeout: int | None = None,
        condition: str = "presence"
    ) -> WebElement:
        """Wait for element with explicit wait.
        
        Args:
            locator: Tuple of (By.*, selector) for element location.
            timeout: Wait timeout in seconds. Uses config default if None.
            condition: Wait condition - "presence", "visible", or "clickable".
        
        Returns:
            The located WebElement.
        
        Raises:
            TimeoutException: If element not found within timeout.
        """
        if self.driver is None:
            raise WebDriverException("Browser not started")
        
        if timeout is None:
            timeout = self.config.element_timeout
        
        wait = WebDriverWait(self.driver, timeout)
        
        conditions = {
            "presence": EC.presence_of_element_located(locator),
            "visible": EC.visibility_of_element_located(locator),
            "clickable": EC.element_to_be_clickable(locator),
        }
        
        return wait.until(conditions.get(condition, conditions["presence"]))
    
    def close(self) -> None:
        """Close browser and cleanup resources."""
        if self.driver is not None:
            try:
                self.driver.quit()
            except WebDriverException:
                pass  # Browser may already be closed
            finally:
                self.driver = None

    
    def login(self, username: str | None = None, password: str | None = None, manual: bool = False) -> bool:
        """Perform Instagram login with popup handling.
        
        Credentials are read from environment variables if not provided:
        - IG_USERNAME
        - IG_PASSWORD
        
        Args:
            username: Instagram username. Falls back to IG_USERNAME env var.
            password: Instagram password. Falls back to IG_PASSWORD env var.
            manual: If True, opens login page and waits for manual login.
        
        Returns:
            True if login successful, False otherwise.
        """
        if self.driver is None:
            raise WebDriverException("Browser not started")
        
        # Check for manual login mode
        manual = manual or os.environ.get("IG_MANUAL_LOGIN", "").lower() in ("1", "true", "yes")
        
        if manual:
            return self._manual_login()
        
        # Get credentials from env vars if not provided
        username = username or os.environ.get("IG_USERNAME")
        password = password or os.environ.get("IG_PASSWORD")
        
        if not username or not password:
            raise ValueError("Instagram credentials not provided. Set IG_USERNAME and IG_PASSWORD environment variables, or use IG_MANUAL_LOGIN=1 for manual login.")
        
        try:
            # Navigate to login page
            self.driver.get(self.LOGIN_URL)
            time.sleep(2)
            
            # Handle cookie consent if present
            self._dismiss_cookie_banner()
            
            # Find and fill login form
            username_input = self.wait_for_element(
                (By.CSS_SELECTOR, "input[name='username']"),
                condition="visible"
            )
            password_input = self.wait_for_element(
                (By.CSS_SELECTOR, "input[name='password']"),
                condition="visible"
            )
            
            # Clear and enter credentials
            username_input.clear()
            username_input.send_keys(username)
            time.sleep(0.5)
            
            password_input.clear()
            password_input.send_keys(password)
            time.sleep(0.5)
            
            # Click login button
            login_button = self.wait_for_element(
                (By.CSS_SELECTOR, "button[type='submit']"),
                condition="clickable"
            )
            login_button.click()
            
            # Wait for login to complete
            time.sleep(3)
            
            # Handle post-login popups
            self.handle_popups()
            
            # Verify login success
            return self._verify_login()
            
        except (TimeoutException, NoSuchElementException) as e:
            return False
    
    def _manual_login(self) -> bool:
        """Open Instagram and wait for user to manually complete login.
        
        Returns:
            True if login successful after manual intervention.
        """
        if self.driver is None:
            raise WebDriverException("Browser not started")
        
        print("\n" + "=" * 60)
        print("MANUAL LOGIN MODE")
        print("=" * 60)
        print("1. The browser will open Instagram's login page")
        print("2. Please log in manually and complete any verification")
        print("3. Once you see your Instagram feed, press ENTER here")
        print("=" * 60 + "\n")
        
        # Navigate to Instagram
        self.driver.get(self.LOGIN_URL)
        time.sleep(2)
        
        # Handle cookie consent if present
        self._dismiss_cookie_banner()
        
        # Wait for user to complete login
        input("Press ENTER after you've logged in and see your feed...")
        
        # Handle any remaining popups
        self.handle_popups()
        
        # Verify login
        if self._verify_login():
            print("Login verified successfully!")
            return True
        else:
            print("Login verification failed. Please try again.")
            return False
    
    def handle_popups(self) -> None:
        """Dismiss 'Save Login Info', 'Turn on Notifications', cookie banners, etc."""
        if self.driver is None:
            return
        
        popup_handlers = [
            self._dismiss_save_login_popup,
            self._dismiss_notifications_popup,
            self._dismiss_cookie_banner,
        ]
        
        for handler in popup_handlers:
            try:
                handler()
                time.sleep(1)
            except (TimeoutException, NoSuchElementException):
                continue  # Popup not present, continue
    
    def _dismiss_cookie_banner(self) -> None:
        """Dismiss cookie consent banner if present."""
        if self.driver is None:
            return
        
        cookie_buttons = [
            (By.XPATH, "//button[contains(text(), 'Allow')]"),
            (By.XPATH, "//button[contains(text(), 'Accept')]"),
            (By.XPATH, "//button[contains(text(), 'Decline')]"),
            (By.CSS_SELECTOR, "button[class*='cookie']"),
        ]
        
        for locator in cookie_buttons:
            try:
                button = WebDriverWait(self.driver, 2).until(
                    EC.element_to_be_clickable(locator)
                )
                button.click()
                return
            except (TimeoutException, NoSuchElementException):
                continue

    
    def _dismiss_save_login_popup(self) -> None:
        """Dismiss 'Save Login Info' popup if present."""
        if self.driver is None:
            return
        
        # Look for "Not Now" button in save login popup
        not_now_buttons = [
            (By.XPATH, "//button[contains(text(), 'Not Now')]"),
            (By.XPATH, "//div[contains(text(), 'Not Now')]"),
            (By.CSS_SELECTOR, "button._acan._acap._acaq._acas._aj1-._ap30"),
        ]
        
        for locator in not_now_buttons:
            try:
                button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable(locator)
                )
                button.click()
                return
            except (TimeoutException, NoSuchElementException):
                continue
    
    def _dismiss_notifications_popup(self) -> None:
        """Dismiss 'Turn on Notifications' popup if present."""
        if self.driver is None:
            return
        
        not_now_buttons = [
            (By.XPATH, "//button[contains(text(), 'Not Now')]"),
            (By.XPATH, "//button[text()='Not Now']"),
            (By.CSS_SELECTOR, "button._a9--._ap36._a9_1"),
        ]
        
        for locator in not_now_buttons:
            try:
                button = WebDriverWait(self.driver, 3).until(
                    EC.element_to_be_clickable(locator)
                )
                button.click()
                return
            except (TimeoutException, NoSuchElementException):
                continue
    
    def _verify_login(self) -> bool:
        """Verify login success by detecting profile/feed elements.
        
        Returns:
            True if login verified, False otherwise.
        """
        if self.driver is None:
            return False
        
        # Check for elements that indicate successful login
        success_indicators = [
            (By.CSS_SELECTOR, "svg[aria-label='Home']"),
            (By.CSS_SELECTOR, "a[href*='/direct/inbox/']"),
            (By.CSS_SELECTOR, "svg[aria-label='Search']"),
            (By.XPATH, "//span[contains(@class, 'x1lliihq')]"),
        ]
        
        for locator in success_indicators:
            try:
                WebDriverWait(self.driver, 5).until(
                    EC.presence_of_element_located(locator)
                )
                return True
            except TimeoutException:
                continue
        
        # Check we're not still on login page
        if "/accounts/login" not in self.driver.current_url:
            return True
        
        return False



def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (TimeoutException, StaleElementReferenceException, WebDriverException),
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator for retry logic with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds (doubles each retry).
        max_delay: Maximum delay cap in seconds.
        exceptions: Tuple of exception types to catch and retry.
    
    Returns:
        Decorated function with retry logic.
    
    Example:
        @retry_with_backoff(max_retries=3)
        def flaky_operation():
            ...
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        def wrapper(*args, **kwargs) -> T:
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions as e:
                    last_exception = e
                    
                    if attempt < max_retries:
                        # Calculate delay with exponential backoff
                        delay = min(base_delay * (2 ** attempt), max_delay)
                        time.sleep(delay)
                    else:
                        # Max retries reached, re-raise
                        raise
            
            # Should not reach here, but just in case
            if last_exception:
                raise last_exception
            raise RuntimeError("Unexpected retry state")
        
        return wrapper
    return decorator


def retry_operation(
    operation: Callable[..., T],
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 30.0,
    exceptions: tuple = (TimeoutException, StaleElementReferenceException, WebDriverException),
) -> T:
    """Execute an operation with retry logic and exponential backoff.
    
    This is a functional alternative to the decorator for one-off retries.
    
    Args:
        operation: Callable to execute.
        max_retries: Maximum number of retry attempts.
        base_delay: Initial delay in seconds (doubles each retry).
        max_delay: Maximum delay cap in seconds.
        exceptions: Tuple of exception types to catch and retry.
    
    Returns:
        Result of the operation.
    
    Raises:
        The last exception if all retries fail.
    
    Example:
        result = retry_operation(lambda: browser.find_element(...), max_retries=3)
    """
    last_exception = None
    
    for attempt in range(max_retries + 1):
        try:
            return operation()
        except exceptions as e:
            last_exception = e
            
            if attempt < max_retries:
                # Calculate delay with exponential backoff
                delay = min(base_delay * (2 ** attempt), max_delay)
                time.sleep(delay)
            else:
                # Max retries reached, re-raise
                raise
    
    # Should not reach here, but just in case
    if last_exception:
        raise last_exception
    raise RuntimeError("Unexpected retry state")
