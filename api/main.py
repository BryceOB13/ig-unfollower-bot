"""FastAPI wrapper for IG Unfollower backend."""

import asyncio
import json
import logging
import os
import sys
import uuid
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

# Add src to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from ig_unfollower.browser import BrowserManager
from ig_unfollower.comparator import ComparisonResult, SnapshotComparator
from ig_unfollower.config import ConfigManager
from ig_unfollower.history import HistoryManager
from ig_unfollower.scraper import InstagramScraper
from ig_unfollower.skip_list import SkipListManager
from ig_unfollower.snapshot import Snapshot, SnapshotManager
from ig_unfollower.unfollower import UnfollowExecutor, UnfollowResult

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Global state
class AppState:
    def __init__(self):
        self.browser: Optional[BrowserManager] = None
        self.config = ConfigManager().load()
        self.snapshot_manager = SnapshotManager()
        self.skip_list_manager = SkipListManager()
        self.history_manager = HistoryManager()
        self.active_operations: dict[str, dict] = {}
        self.websocket_clients: list[WebSocket] = []
        self.browser_connected = False
        self.logged_in = False
        self.last_operation: Optional[dict] = None


state = AppState()


# Pydantic models for API
class StatusResponse(BaseModel):
    browser_connected: bool
    logged_in: bool
    last_operation: Optional[dict] = None


class LoginRequest(BaseModel):
    manual: bool = True


class LoginResponse(BaseModel):
    success: bool
    message: str


class OperationResponse(BaseModel):
    operation_id: str
    status: str


class UnfollowRequest(BaseModel):
    targets: list[str]
    dry_run: bool = False
    max_unfollows: int = 50


class SkipListRequest(BaseModel):
    username: str


class ConfigUpdateRequest(BaseModel):
    action_delay_min: Optional[float] = None
    action_delay_max: Optional[float] = None
    scroll_delay: Optional[float] = None
    element_timeout: Optional[int] = None


class SnapshotResponse(BaseModel):
    timestamp: str
    followers: list[str]
    following: list[str]
    followers_count: int
    following_count: int


class ComparisonResponse(BaseModel):
    unfollowers: list[str]
    not_following_back: list[str]
    new_followers: list[str]
    timestamp: str


# WebSocket broadcast helper
async def broadcast(message: dict):
    """Broadcast message to all connected WebSocket clients."""
    disconnected = []
    for ws in state.websocket_clients:
        try:
            await ws.send_json(message)
        except Exception:
            disconnected.append(ws)
    for ws in disconnected:
        state.websocket_clients.remove(ws)


# Lifespan context manager
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle."""
    logger.info("Starting IG Unfollower API")
    yield
    # Cleanup on shutdown
    if state.browser:
        state.browser.quit()
        logger.info("Browser closed")


# Create FastAPI app
app = FastAPI(
    title="IG Unfollower API",
    description="API for Instagram follower management",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# API Endpoints

@app.get("/api/status", response_model=StatusResponse)
async def get_status():
    """Get current system status."""
    return StatusResponse(
        browser_connected=state.browser_connected,
        logged_in=state.logged_in,
        last_operation=state.last_operation,
    )


@app.post("/api/auth/login", response_model=LoginResponse)
async def login(request: LoginRequest):
    """Start browser and login to Instagram."""
    try:
        if state.browser is None:
            state.browser = BrowserManager(config=state.config)
        
        state.browser.start()
        state.browser_connected = True
        
        await broadcast({"type": "status_change", "browser": True, "logged_in": False})
        
        if request.manual:
            # Navigate to Instagram for manual login
            if state.browser.driver:
                state.browser.driver.get("https://www.instagram.com/")
            return LoginResponse(
                success=True,
                message="Browser started. Please login manually and call /api/auth/verify when done.",
            )
        else:
            # Auto login (if credentials available)
            success = state.browser.login()
            state.logged_in = success
            await broadcast({"type": "status_change", "browser": True, "logged_in": success})
            return LoginResponse(
                success=success,
                message="Login successful" if success else "Login failed",
            )
    except Exception as e:
        logger.error(f"Login error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/verify", response_model=LoginResponse)
async def verify_login():
    """Verify login and auto-detect username using multiple strategies."""
    if state.browser is None or state.browser.driver is None:
        raise HTTPException(status_code=400, detail="Browser not started")
    
    try:
        driver = state.browser.driver
        
        # Multi-strategy username detection
        result = driver.execute_script("""
            let detectedUsername = null;
            let detectionMethod = null;
            
            // Strategy 1: Sidebar Profile SVG (most reliable)
            try {
                const profileSvg = document.querySelector('svg[aria-label="Profile"]');
                if (profileSvg) {
                    let parent = profileSvg.parentElement;
                    while (parent && parent.tagName !== 'A') {
                        parent = parent.parentElement;
                    }
                    if (parent && parent.tagName === 'A') {
                        const href = parent.getAttribute('href') || '';
                        const match = href.match(/^\\/([a-zA-Z0-9._]+)\\/?$/);
                        if (match) {
                            detectedUsername = match[1];
                            detectionMethod = 'sidebar_profile';
                        }
                    }
                }
            } catch (e) {}
            
            // Strategy 2: Profile image alt text in navigation
            if (!detectedUsername) {
                try {
                    const navImages = document.querySelectorAll('nav img[alt*="profile picture"], header img[alt*="profile picture"]');
                    for (const img of navImages) {
                        const alt = img.getAttribute('alt') || '';
                        const match = alt.match(/^([a-zA-Z0-9._]+)'s profile picture$/i);
                        if (match) {
                            detectedUsername = match[1];
                            detectionMethod = 'nav_profile_image';
                            break;
                        }
                    }
                } catch (e) {}
            }
            
            // Strategy 3: More menu profile picture
            if (!detectedUsername) {
                try {
                    const moreImages = document.querySelectorAll('div[role="button"] img');
                    for (const img of moreImages) {
                        const alt = img.getAttribute('alt') || '';
                        if (alt.includes('profile picture')) {
                            const match = alt.match(/^([a-zA-Z0-9._]+)'s profile picture$/i);
                            if (match) {
                                detectedUsername = match[1];
                                detectionMethod = 'more_menu';
                                break;
                            }
                        }
                    }
                } catch (e) {}
            }
            
            // Strategy 4: Profile links with profile picture
            if (!detectedUsername) {
                try {
                    const currentPath = window.location.pathname;
                    const allLinks = document.querySelectorAll('a[href^="/"]');
                    for (const link of allLinks) {
                        const href = link.getAttribute('href') || '';
                        if (href === currentPath) continue;
                        if (href.match(/^\\/(explore|direct|reels|stories|p|accounts|reel)\\//)) continue;
                        if (href.match(/^\\/([a-zA-Z0-9._]+)\\/(followers|following)\\/?$/)) continue;
                        
                        const match = href.match(/^\\/([a-zA-Z0-9._]+)\\/?$/);
                        if (match && match[1].length >= 1 && match[1].length <= 30) {
                            const hasProfileImg = link.querySelector('img[alt*="profile picture"]') !== null;
                            const isInNav = link.closest('nav') !== null || 
                                           link.closest('[role="navigation"]') !== null;
                            
                            if (hasProfileImg || isInNav) {
                                detectedUsername = match[1];
                                detectionMethod = 'profile_link';
                                break;
                            }
                        }
                    }
                } catch (e) {}
            }
            
            // Check login status
            const isLoggedIn = (
                document.querySelector('svg[aria-label="Home"]') !== null ||
                document.querySelector('a[href*="/direct/inbox/"]') !== null
            ) && !window.location.href.includes('/accounts/login');
            
            return {
                isLoggedIn: isLoggedIn,
                username: detectedUsername,
                method: detectionMethod
            };
        """)
        
        is_logged_in = result.get('isLoggedIn', False)
        detected_username = result.get('username')
        method = result.get('method')
        
        state.logged_in = is_logged_in
        
        if is_logged_in and detected_username:
            logger.info(f"Username detected: {detected_username} via {method}")
            
            # Save to config
            try:
                try:
                    with open("config.json", "r") as f:
                        config_data = json.load(f)
                except FileNotFoundError:
                    config_data = {}
                
                if config_data.get("username") != detected_username:
                    config_data["username"] = detected_username
                    with open("config.json", "w") as f:
                        json.dump(config_data, f, indent=2)
                        
            except Exception as e:
                logger.warning(f"Could not save username: {e}")
            
            await broadcast({
                "type": "status_change",
                "browser": True,
                "logged_in": True,
                "username": detected_username
            })
            
            return LoginResponse(
                success=True,
                message=f"Logged in as {detected_username}",
            )
        
        elif is_logged_in:
            await broadcast({"type": "status_change", "browser": True, "logged_in": True})
            return LoginResponse(
                success=True,
                message="Logged in but could not detect username. Please set manually.",
            )
        
        else:
            await broadcast({"type": "status_change", "browser": True, "logged_in": False})
            return LoginResponse(
                success=False,
                message="Not logged in",
            )
            
    except Exception as e:
        logger.error(f"Verify error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/auth/logout")
async def logout():
    """Close browser and logout."""
    if state.browser:
        state.browser.close()
        state.browser = None
    state.browser_connected = False
    state.logged_in = False
    await broadcast({"type": "status_change", "browser": False, "logged_in": False})
    return {"success": True, "message": "Logged out"}


@app.post("/api/compare", response_model=OperationResponse)
async def start_compare():
    """Start a compare operation (scrape and compare snapshots)."""
    if not state.logged_in or state.browser is None:
        raise HTTPException(status_code=400, detail="Not logged in")
    
    operation_id = str(uuid.uuid4())
    state.active_operations[operation_id] = {
        "type": "compare",
        "status": "running",
        "progress": 0,
        "total": 100,
        "message": "Starting comparison...",
    }
    
    # Run in background
    asyncio.create_task(run_compare_operation(operation_id))
    
    return OperationResponse(operation_id=operation_id, status="started")


async def run_compare_operation(operation_id: str):
    """Background task for compare operation."""
    try:
        op = state.active_operations[operation_id]
        
        # Progress callback
        def on_progress(current: int, total: int, message: str = ""):
            op["progress"] = current
            op["total"] = total
            op["message"] = message
            asyncio.create_task(broadcast({
                "type": "progress",
                "operation_id": operation_id,
                "current": current,
                "total": total,
                "message": message,
            }))
        
        # Get the LOGGED-IN user's username - NOT the page being viewed
        # This ensures we always scrape OUR account, not someone else's
        # Get username from config.json - this is the ONLY source of truth
        # The username should be set during Verify Login
        username = None
        try:
            with open("config.json", "r") as f:
                data = json.load(f)
                username = data.get("username", "").strip()
        except Exception:
            pass
        
        if not username:
            raise ValueError("Username not configured. Please click 'Verify Login' first to detect your username.")
        
        logger.info(f"Starting compare for user: {username}")
        
        # Create scraper with username and scrape
        # The scraper will navigate to this user's profile
        scraper = InstagramScraper(state.browser, username, state.config)
        
        op["message"] = "Scraping followers..."
        await broadcast({"type": "progress", "operation_id": operation_id, "current": 0, "total": 100, "message": "Scraping followers..."})
        
        followers = scraper.scrape_followers(progress_callback=on_progress)
        
        op["message"] = "Scraping following..."
        await broadcast({"type": "progress", "operation_id": operation_id, "current": 50, "total": 100, "message": "Scraping following..."})
        
        following = scraper.scrape_following(progress_callback=on_progress)
        
        # Create and save snapshot
        timestamp = datetime.now(timezone.utc).isoformat()
        snapshot = Snapshot(
            timestamp=timestamp,
            followers=followers,
            following=following,
            username=username,
        )
        state.snapshot_manager.save(snapshot)
        
        # Compare with previous if exists
        op["message"] = "Comparing snapshots..."
        
        # Load previous snapshot for comparison
        # For now, just save the result
        skip_list = state.skip_list_manager.load()
        comparator = SnapshotComparator(skip_list)
        
        # Get previous snapshot for THIS USER
        previous = state.snapshot_manager.load_latest(username=username)
        if previous and previous.timestamp != timestamp:
            result = comparator.compare(previous, snapshot)
            # Save comparison result (account-specific)
            comparison_filename = f"latest_comparison_{username.lower()}.json"
            comparison_path = Path("snapshots") / comparison_filename
            comparison_path.write_text(json.dumps({
                "unfollowers": result.unfollowers,
                "not_following_back": result.not_following_back,
                "new_followers": result.new_followers,
                "timestamp": result.timestamp,
            }, indent=2))
            
            # Also update the generic latest_comparison.json for backward compatibility
            generic_path = Path("snapshots") / "latest_comparison.json"
            generic_path.write_text(json.dumps({
                "unfollowers": result.unfollowers,
                "not_following_back": result.not_following_back,
                "new_followers": result.new_followers,
                "timestamp": result.timestamp,
            }, indent=2))
        
        op["status"] = "completed"
        op["message"] = "Comparison complete"
        op["progress"] = 100
        
        state.last_operation = {
            "type": "compare",
            "timestamp": timestamp,
            "followers_count": len(followers),
            "following_count": len(following),
        }
        
        await broadcast({
            "type": "operation_complete",
            "operation_id": operation_id,
            "result": {
                "followers_count": len(followers),
                "following_count": len(following),
            },
        })
        
    except Exception as e:
        logger.error(f"Compare operation error: {e}")
        state.active_operations[operation_id]["status"] = "failed"
        state.active_operations[operation_id]["message"] = str(e)
        await broadcast({
            "type": "operation_complete",
            "operation_id": operation_id,
            "error": str(e),
        })


@app.get("/api/compare/{operation_id}")
async def get_compare_status(operation_id: str):
    """Get status of a compare operation."""
    if operation_id not in state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    return state.active_operations[operation_id]


@app.post("/api/unfollow", response_model=OperationResponse)
async def start_unfollow(request: UnfollowRequest):
    """Start an unfollow operation."""
    if not state.logged_in or state.browser is None:
        raise HTTPException(status_code=400, detail="Not logged in")
    
    operation_id = str(uuid.uuid4())
    state.active_operations[operation_id] = {
        "type": "unfollow",
        "status": "running",
        "progress": 0,
        "total": min(len(request.targets), request.max_unfollows),
        "message": "Starting unfollow...",
        "dry_run": request.dry_run,
    }
    
    # Run in background
    asyncio.create_task(run_unfollow_operation(
        operation_id, request.targets, request.dry_run, request.max_unfollows
    ))
    
    return OperationResponse(operation_id=operation_id, status="started")


async def run_unfollow_operation(
    operation_id: str,
    targets: list[str],
    dry_run: bool,
    max_unfollows: int,
):
    """Background task for unfollow operation."""
    try:
        op = state.active_operations[operation_id]
        skip_list = state.skip_list_manager.load()
        
        executor = UnfollowExecutor(
            browser=state.browser,
            skip_list=skip_list,
            dry_run=dry_run,
            config=state.config,
            history_manager=state.history_manager,
        )
        
        # Execute unfollows
        result = executor.execute(targets, max_unfollows)
        
        op["status"] = "completed"
        op["message"] = f"Unfollowed {len(result.successful)} users"
        op["progress"] = len(result.successful) + len(result.failed) + len(result.skipped)
        op["result"] = {
            "successful": result.successful,
            "failed": result.failed,
            "skipped": result.skipped,
        }
        
        # Remove successfully unfollowed users from the comparison data
        if result.successful and not dry_run:
            # Get current username
            username = None
            try:
                with open("config.json", "r") as f:
                    data = json.load(f)
                    username = data.get("username", "").strip()
            except Exception:
                pass
            
            unfollowed_set = {u.lower() for u in result.successful}
            
            # Update account-specific comparison if username is known
            if username:
                comparison_filename = f"latest_comparison_{username.lower()}.json"
                comparison_path = Path("snapshots") / comparison_filename
                if comparison_path.exists():
                    try:
                        comparison_data = json.loads(comparison_path.read_text())
                        comparison_data["not_following_back"] = [
                            u for u in comparison_data.get("not_following_back", [])
                            if u.lower() not in unfollowed_set
                        ]
                        comparison_path.write_text(json.dumps(comparison_data, indent=2))
                        logger.info(f"Removed {len(result.successful)} users from {username}'s not_following_back list")
                    except Exception as e:
                        logger.warning(f"Could not update account-specific comparison: {e}")
            
            # Also update generic comparison for backward compatibility
            comparison_path = Path("snapshots") / "latest_comparison.json"
            if comparison_path.exists():
                try:
                    comparison_data = json.loads(comparison_path.read_text())
                    comparison_data["not_following_back"] = [
                        u for u in comparison_data.get("not_following_back", [])
                        if u.lower() not in unfollowed_set
                    ]
                    comparison_path.write_text(json.dumps(comparison_data, indent=2))
                except Exception as e:
                    logger.warning(f"Could not update generic comparison file: {e}")
            
            # Broadcast update to frontend
            await broadcast({
                "type": "comparison_updated",
                "removed_count": len(result.successful)
            })
        
        state.last_operation = {
            "type": "unfollow",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "successful_count": len(result.successful),
            "failed_count": len(result.failed),
            "dry_run": dry_run,
        }
        
        await broadcast({
            "type": "operation_complete",
            "operation_id": operation_id,
            "result": op["result"],
        })
        
    except Exception as e:
        logger.error(f"Unfollow operation error: {e}")
        state.active_operations[operation_id]["status"] = "failed"
        state.active_operations[operation_id]["message"] = str(e)
        await broadcast({
            "type": "operation_complete",
            "operation_id": operation_id,
            "error": str(e),
        })


@app.get("/api/unfollow/{operation_id}")
async def get_unfollow_status(operation_id: str):
    """Get status of an unfollow operation."""
    if operation_id not in state.active_operations:
        raise HTTPException(status_code=404, detail="Operation not found")
    return state.active_operations[operation_id]


@app.get("/api/snapshot/latest", response_model=Optional[SnapshotResponse])
async def get_latest_snapshot():
    """Get the latest snapshot data."""
    snapshot = state.snapshot_manager.load_latest()
    if not snapshot:
        return None
    return SnapshotResponse(
        timestamp=snapshot.timestamp,
        followers=snapshot.followers,
        following=snapshot.following,
        followers_count=snapshot.followers_count,
        following_count=snapshot.following_count,
    )


@app.get("/api/comparison/latest", response_model=Optional[ComparisonResponse])
async def get_latest_comparison():
    """Get the latest comparison results for the current user."""
    # Try to get username from config
    username = None
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
            username = data.get("username", "").strip()
    except Exception:
        pass
    
    # Try account-specific comparison first
    if username:
        comparison_filename = f"latest_comparison_{username.lower()}.json"
        comparison_path = Path("snapshots") / comparison_filename
        if comparison_path.exists():
            try:
                data = json.loads(comparison_path.read_text())
                return ComparisonResponse(
                    unfollowers=data.get("unfollowers", []),
                    not_following_back=data.get("not_following_back", []),
                    new_followers=data.get("new_followers", []),
                    timestamp=data.get("timestamp", ""),
                )
            except Exception:
                pass
    
    # Fall back to generic comparison
    comparison_path = Path("snapshots") / "latest_comparison.json"
    if not comparison_path.exists():
        return None
    
    try:
        data = json.loads(comparison_path.read_text())
        return ComparisonResponse(
            unfollowers=data.get("unfollowers", []),
            not_following_back=data.get("not_following_back", []),
            new_followers=data.get("new_followers", []),
            timestamp=data.get("timestamp", ""),
        )
    except Exception:
        return None


@app.get("/api/skip-list")
async def get_skip_list():
    """Get the skip list."""
    usernames = state.skip_list_manager.load()
    return {"usernames": sorted(list(usernames))}


@app.post("/api/skip-list")
async def add_to_skip_list(request: SkipListRequest):
    """Add username to skip list."""
    state.skip_list_manager.add(request.username)
    return {"success": True, "username": request.username}


@app.delete("/api/skip-list/{username}")
async def remove_from_skip_list(username: str):
    """Remove username from skip list."""
    state.skip_list_manager.remove(username)
    return {"success": True, "username": username}


@app.get("/api/history")
async def get_history():
    """Get unfollow history."""
    history = state.history_manager.load()
    return {"unfollowed": history}


@app.get("/api/config")
async def get_config():
    """Get current configuration."""
    # Username is stored separately in config.json, not in Config dataclass
    username = None
    try:
        with open("config.json", "r") as f:
            data = json.load(f)
            username = data.get("username")
    except Exception:
        pass
    
    # Get list of accounts that have been scraped
    available_accounts = []
    try:
        pointer_path = Path("snapshots") / "latest.json"
        if pointer_path.exists():
            pointer_data = json.loads(pointer_path.read_text())
            by_user = pointer_data.get("by_user", {})
            available_accounts = sorted(list(by_user.keys()))
    except Exception:
        pass
    
    return {
        "username": username,
        "action_delay_min": state.config.action_delay_min,
        "action_delay_max": state.config.action_delay_max,
        "scroll_delay": getattr(state.config, "scroll_delay", 0.5),
        "element_timeout": state.config.element_timeout,
        "max_retries": state.config.max_retries,
        "available_accounts": available_accounts,
    }


@app.put("/api/config")
async def update_config(request: ConfigUpdateRequest):
    """Update configuration."""
    if request.action_delay_min is not None:
        state.config.action_delay_min = request.action_delay_min
    if request.action_delay_max is not None:
        state.config.action_delay_max = request.action_delay_max
    if request.element_timeout is not None:
        state.config.element_timeout = request.element_timeout
    return {"success": True}


class UsernameUpdateRequest(BaseModel):
    username: str


@app.put("/api/config/username")
async def update_username(request: UsernameUpdateRequest):
    """Update the target username for scraping."""
    try:
        with open("config.json", "r") as f:
            config_data = json.load(f)
        config_data["username"] = request.username
        with open("config.json", "w") as f:
            json.dump(config_data, f, indent=2)
        logger.info(f"Username updated to: {request.username}")
        return {"success": True, "username": request.username}
    except Exception as e:
        logger.error(f"Failed to update username: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# WebSocket endpoint
@app.websocket("/api/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket for real-time updates."""
    await websocket.accept()
    state.websocket_clients.append(websocket)
    
    try:
        # Send initial status
        await websocket.send_json({
            "type": "status_change",
            "browser": state.browser_connected,
            "logged_in": state.logged_in,
        })
        
        # Keep connection alive
        while True:
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30)
                # Handle ping/pong or other messages
                if data == "ping":
                    await websocket.send_text("pong")
            except asyncio.TimeoutError:
                # Send heartbeat
                await websocket.send_json({"type": "heartbeat"})
    except WebSocketDisconnect:
        pass
    finally:
        if websocket in state.websocket_clients:
            state.websocket_clients.remove(websocket)


# Run with: uvicorn api.main:app --reload --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
