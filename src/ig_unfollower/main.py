"""Main entry point for the IG Unfollower tool."""

import argparse
import json
import logging
import os
import sys
from dataclasses import asdict
from datetime import datetime, timezone
from pathlib import Path

from .browser import BrowserManager
from .comparator import ComparisonResult, SnapshotComparator
from .config import Config, ConfigManager
from .history import HistoryManager
from .scraper import InstagramScraper
from .skip_list import SkipListManager
from .snapshot import Snapshot, SnapshotManager
from .unfollower import UnfollowExecutor, UnfollowResult


# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse CLI arguments including --mode, --dry_run, --max_unfollows.
    
    Environment variable fallbacks:
    - IG_USERNAME: Instagram username
    - IG_PASSWORD: Instagram password
    
    Returns:
        Parsed argument namespace.
    """
    parser = argparse.ArgumentParser(
        prog="ig-unfollower",
        description="Instagram follower monitoring and management tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  ig-unfollower --mode list --username myaccount
  ig-unfollower --mode compare --username myaccount
  ig-unfollower --mode unfollow --username myaccount --dry_run
  ig-unfollower --mode unfollow --username myaccount --max_unfollows 10
        """,
    )
    
    parser.add_argument(
        "--mode",
        type=str,
        choices=["compare", "unfollow"],
        required=True,
        help="Operation mode: compare (scrape, save, and detect changes), unfollow (auto-unfollow)",
    )
    
    parser.add_argument(
        "--username",
        type=str,
        default=os.environ.get("IG_USERNAME"),
        help="Instagram username (or set IG_USERNAME env var)",
    )
    
    parser.add_argument(
        "--dry_run",
        action="store_true",
        default=False,
        help="Simulate actions without executing (for unfollow mode)",
    )
    
    parser.add_argument(
        "--max_unfollows",
        type=int,
        default=50,
        help="Maximum number of unfollows per run (default: 50)",
    )
    
    parser.add_argument(
        "--config",
        type=str,
        default="config.json",
        help="Path to configuration file (default: config.json)",
    )
    
    parser.add_argument(
        "--data_dir",
        type=str,
        default="snapshots",
        help="Directory for storing snapshot data (default: snapshots)",
    )
    
    parser.add_argument(
        "--skip_list",
        type=str,
        default="skip_list.json",
        help="Path to skip list file (default: skip_list.json)",
    )
    
    parser.add_argument(
        "--history",
        type=str,
        default="unfollowed_history.json",
        help="Path to unfollow history file (default: unfollowed_history.json)",
    )
    
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        default=False,
        help="Enable verbose logging",
    )
    
    args = parser.parse_args()
    
    # Validate username is provided
    if not args.username:
        parser.error("Username is required. Use --username or set IG_USERNAME environment variable.")
    
    return args


def run_compare_mode(
    username: str,
    config: Config,
    data_dir: str,
    skip_list_path: str,
) -> int:
    """Run compare mode: scrape followers/following, save snapshot, and detect changes.
    
    If no previous snapshot exists, creates one and shows current state.
    
    Requirements: 6.1, 6.2, 6.3, 6.4, 6.5, 6.6
    
    Args:
        username: Instagram username to scrape.
        config: Configuration object.
        data_dir: Directory for storing snapshots.
        skip_list_path: Path to skip list file.
    
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    logger.info(f"Starting compare mode for user: {username}")
    
    # Requirement 6.2: Load previous snapshot (optional - will work without one)
    snapshot_manager = SnapshotManager(data_dir)
    old_snapshot = snapshot_manager.load_latest()
    
    if old_snapshot is None:
        logger.info("No previous snapshot found. Will create initial snapshot.")
    else:
        logger.info(f"Loaded previous snapshot from: {old_snapshot.timestamp}")
    
    browser = None
    try:
        # Initialize browser
        browser = BrowserManager(config=config)
        browser.start()
        logger.info("Browser started")
        
        # Check if already logged in, otherwise login
        if not browser.is_logged_in():
            logger.info("Not logged in, attempting login...")
            if not browser.login():
                logger.error("Login failed")
                return 1
            logger.info("Login successful")
        else:
            logger.info("Using existing session")
        
        # Initialize scraper
        scraper = InstagramScraper(browser, username, config)
        
        # Navigate to profile
        if not scraper.navigate_to_profile():
            logger.error(f"Failed to navigate to profile: {username}")
            return 1
        
        # Requirement 6.1: Scrape current followers and following lists with progress
        def progress_callback(current: int, total: int) -> None:
            """Display real-time progress during scraping."""
            if total > 0:
                percent = (current / total) * 100
                print(f"\rProgress: {current}/{total} ({percent:.1f}%)", end="", flush=True)
        
        logger.info("Scraping current followers...")
        print("Scraping followers...")
        followers = scraper.scrape_followers(progress_callback=progress_callback)
        print()  # New line after progress
        logger.info(f"Found {len(followers)} followers")
        
        logger.info("Scraping current following...")
        print("Scraping following...")
        following = scraper.scrape_following(progress_callback=progress_callback)
        print()  # New line after progress
        logger.info(f"Found {len(following)} following")
        
        # Create new snapshot
        timestamp = datetime.now(timezone.utc).isoformat()
        new_snapshot = Snapshot(
            timestamp=timestamp,
            followers=followers,
            following=following,
            followers_count=len(followers),
            following_count=len(following),
        )
        
        # Save new snapshot
        filepath = snapshot_manager.save(new_snapshot)
        logger.info(f"New snapshot saved to: {filepath}")
        
        # Load skip list
        skip_list_manager = SkipListManager(skip_list_path)
        skip_list = skip_list_manager.load()
        logger.info(f"Loaded skip list with {len(skip_list)} entries")
        
        # Requirement 6.3, 6.4: Compare snapshots with skip list filtering
        comparator = SnapshotComparator(skip_list)
        
        if old_snapshot is not None:
            result = comparator.compare(old_snapshot, new_snapshot)
        else:
            # No previous snapshot - just analyze current state
            result = comparator.compare(new_snapshot, new_snapshot)
        
        # Requirement 6.6: Output structured JSON report
        report = {
            "unfollowers": result.unfollowers if old_snapshot else [],
            "not_following_back": result.not_following_back,
            "new_followers": result.new_followers if old_snapshot else [],
            "timestamp": result.timestamp,
            "unfollowed_timestamps": result.unfollowed_timestamps,
            "summary": {
                "old_followers_count": old_snapshot.followers_count if old_snapshot else 0,
                "new_followers_count": new_snapshot.followers_count,
                "old_following_count": old_snapshot.following_count if old_snapshot else 0,
                "new_following_count": new_snapshot.following_count,
                "unfollowers_count": len(result.unfollowers) if old_snapshot else 0,
                "not_following_back_count": len(result.not_following_back),
                "new_followers_count": len(result.new_followers) if old_snapshot else 0,
            },
        }
        
        # Save comparison report
        report_path = Path(data_dir) / f"comparison_{timestamp.replace(':', '-')}.json"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        logger.info(f"Comparison report saved to: {report_path}")
        
        # Also save as latest comparison for unfollow mode
        latest_comparison_path = Path(data_dir) / "latest_comparison.json"
        with open(latest_comparison_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
        
        # Requirement 9.2: Print summary
        print("\n" + "=" * 50)
        print("COMPARE MODE SUMMARY")
        print("=" * 50)
        print(f"Username:           {username}")
        if old_snapshot:
            print(f"Previous snapshot:  {old_snapshot.timestamp}")
        else:
            print(f"Previous snapshot:  (none - initial run)")
        print(f"Current snapshot:   {timestamp}")
        print("-" * 50)
        print(f"Followers scraped:  {new_snapshot.followers_count}")
        print(f"Following scraped:  {new_snapshot.following_count}")
        if old_snapshot:
            print(f"Follower change:    {new_snapshot.followers_count - old_snapshot.followers_count:+d}")
            print("-" * 50)
            print(f"Unfollowers:        {len(result.unfollowers)}")
            if result.unfollowers:
                for u in result.unfollowers[:10]:  # Show first 10
                    print(f"  - {u}")
                if len(result.unfollowers) > 10:
                    print(f"  ... and {len(result.unfollowers) - 10} more")
        print("-" * 50)
        print(f"Not following back: {len(result.not_following_back)}")
        if result.not_following_back:
            for u in result.not_following_back[:10]:  # Show first 10
                print(f"  - {u}")
            if len(result.not_following_back) > 10:
                print(f"  ... and {len(result.not_following_back) - 10} more")
        if old_snapshot:
            print("-" * 50)
            print(f"New followers:      {len(result.new_followers)}")
            if result.new_followers:
                for u in result.new_followers[:10]:  # Show first 10
                    print(f"  + {u}")
                if len(result.new_followers) > 10:
                    print(f"  ... and {len(result.new_followers) - 10} more")
        print("-" * 50)
        print(f"Report saved to:    {report_path}")
        print("=" * 50 + "\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in compare mode: {e}", exc_info=True)
        return 1
    finally:
        if browser:
            browser.close()
            logger.info("Browser closed")


def run_unfollow_mode(
    username: str,
    config: Config,
    data_dir: str,
    skip_list_path: str,
    history_path: str,
    dry_run: bool,
    max_unfollows: int,
) -> int:
    """Run unfollow mode: automatically unfollow flagged accounts.
    
    Requirements: 10.1, 10.2, 10.3, 10.11
    
    Args:
        username: Instagram username.
        config: Configuration object.
        data_dir: Directory for storing snapshots.
        skip_list_path: Path to skip list file.
        history_path: Path to unfollow history file.
        dry_run: If True, simulate actions without executing.
        max_unfollows: Maximum number of unfollows per run.
    
    Returns:
        Exit code (0 for success, 1 for failure).
    """
    logger.info(f"Starting unfollow mode for user: {username}")
    logger.info(f"Dry run: {dry_run}, Max unfollows: {max_unfollows}")
    
    # Requirement 10.1: Load the most recent comparison results
    latest_comparison_path = Path(data_dir) / "latest_comparison.json"
    
    if not latest_comparison_path.exists():
        logger.error("No comparison results found. Run compare mode first.")
        print("Error: No comparison results found. Run with --mode compare first.")
        return 1
    
    try:
        with open(latest_comparison_path, "r", encoding="utf-8") as f:
            comparison_data = json.load(f)
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Failed to load comparison results: {e}")
        return 1
    
    # Get targets from comparison results (not following back)
    targets = comparison_data.get("not_following_back", [])
    logger.info(f"Loaded {len(targets)} potential targets from comparison")
    
    if not targets:
        logger.info("No targets to unfollow")
        print("No accounts to unfollow based on comparison results.")
        return 0
    
    # Requirement 10.2: Load skip list
    skip_list_manager = SkipListManager(skip_list_path)
    skip_list = skip_list_manager.load()
    logger.info(f"Loaded skip list with {len(skip_list)} entries")
    
    # Initialize history manager
    history_manager = HistoryManager(history_path)
    
    browser = None
    try:
        # Initialize browser
        browser = BrowserManager(config=config)
        browser.start()
        logger.info("Browser started")
        
        # Check if already logged in, otherwise login
        if not browser.is_logged_in():
            logger.info("Not logged in, attempting login...")
            if not browser.login():
                logger.error("Login failed")
                return 1
            logger.info("Login successful")
        else:
            logger.info("Using existing session")
        
        # Initialize unfollow executor
        executor = UnfollowExecutor(
            browser=browser,
            skip_list=skip_list,
            dry_run=dry_run,
            config=config,
            history_manager=history_manager,
        )
        
        # Execute unfollows
        result = executor.execute(targets, max_unfollows)
        
        # Requirement 10.11: Output summary
        print("\n" + "=" * 50)
        print("UNFOLLOW MODE SUMMARY")
        print("=" * 50)
        print(f"Username:    {username}")
        print(f"Dry run:     {dry_run}")
        print(f"Max limit:   {max_unfollows}")
        print("-" * 50)
        print(f"Successful:  {len(result.successful)}")
        if result.successful:
            for u in result.successful[:10]:
                print(f"  ✓ {u}")
            if len(result.successful) > 10:
                print(f"  ... and {len(result.successful) - 10} more")
        print("-" * 50)
        print(f"Skipped:     {len(result.skipped)}")
        if result.skipped:
            for u in result.skipped[:5]:
                print(f"  - {u}")
            if len(result.skipped) > 5:
                print(f"  ... and {len(result.skipped) - 5} more")
        print("-" * 50)
        print(f"Failed:      {len(result.failed)}")
        if result.failed:
            for u in result.failed[:5]:
                print(f"  ✗ {u}")
            if len(result.failed) > 5:
                print(f"  ... and {len(result.failed) - 5} more")
        print("=" * 50 + "\n")
        
        return 0
        
    except Exception as e:
        logger.error(f"Error in unfollow mode: {e}", exc_info=True)
        return 1
    finally:
        if browser:
            browser.close()
            logger.info("Browser closed")


def main() -> int:
    """Main entry point for the IG Unfollower tool.
    
    Wires together all components and handles top-level errors gracefully.
    
    Requirements: 9.1, 9.2, 9.3
    
    Returns:
        Exit code (0 for success, non-zero for failure).
    """
    try:
        # Parse command line arguments
        args = parse_args()
        
        # Configure logging level
        if args.verbose:
            logging.getLogger().setLevel(logging.DEBUG)
            logger.debug("Verbose logging enabled")
        
        # Requirement 9.1: Output descriptive log messages
        logger.info(f"IG Unfollower starting in {args.mode} mode")
        logger.info(f"Username: {args.username}")
        
        # Load configuration
        config_manager = ConfigManager(args.config)
        config = config_manager.load()
        logger.info(f"Configuration loaded from: {args.config}")
        
        # Route to appropriate mode handler
        if args.mode == "compare":
            return run_compare_mode(
                username=args.username,
                config=config,
                data_dir=args.data_dir,
                skip_list_path=args.skip_list,
            )
        
        elif args.mode == "unfollow":
            return run_unfollow_mode(
                username=args.username,
                config=config,
                data_dir=args.data_dir,
                skip_list_path=args.skip_list,
                history_path=args.history,
                dry_run=args.dry_run,
                max_unfollows=args.max_unfollows,
            )
        
        else:
            logger.error(f"Unknown mode: {args.mode}")
            return 1
            
    except KeyboardInterrupt:
        logger.info("Operation cancelled by user")
        print("\nOperation cancelled.")
        return 130
    except Exception as e:
        logger.error(f"Unexpected error: {e}", exc_info=True)
        print(f"\nError: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
