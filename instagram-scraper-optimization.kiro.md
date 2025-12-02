# Instagram Scraper Optimization Spec

## Goal
Optimize the Instagram follower/following scraping in `src/ig_unfollower/scraper.py` to improve both **speed** (reduce total scrape time) and **completeness** (achieve 100% of displayed follower/following counts).

## Current State Analysis

### Pain Points
1. **Excessive wait times**: Fixed `time.sleep()` calls (2s, 3s) regardless of content loading state
2. **Inefficient scroll detection**: Polling-based approach with up to 40 no-change iterations before termination
3. **Redundant JS execution**: Multiple separate `execute_script` calls per scroll iteration
4. **No parallel extraction**: Username extraction happens after scrolling completes, not during
5. **Conservative scroll delays**: `scroll_delay` config (default 1.0s) may be too slow for fast connections

### Current Performance Characteristics
- Modal scroll loop can run 600+ iterations
- Each iteration: 1+ JS calls + `scroll_delay` wait + potential retry waits
- Total scrape time scales linearly with follower count (no batching)

## Requirements

### R1: Adaptive Scroll Timing
- [ ] Replace fixed `time.sleep()` with dynamic waits based on network activity detection
- [ ] Implement scroll velocity tracking - reduce delay when content loads fast, increase when slow
- [ ] Use `MutationObserver` in JS to detect when new content has actually rendered
- [ ] Target: Reduce average scroll delay from 1.0s to 0.3-0.5s when network is fast

### R2: Consolidated JavaScript Execution  
- [ ] Combine scroll + count + extraction into single `execute_script` call per iteration
- [ ] Return structured object: `{scrolled: bool, count: int, usernames: string[], atEnd: bool}`
- [ ] Detect scroll end via `scrollTop + clientHeight >= scrollHeight - threshold`
- [ ] Target: Reduce JS calls from 3-5 per iteration to 1

### R3: Incremental Username Collection
- [ ] Extract usernames during scroll, not just at end
- [ ] Maintain running `Set` of usernames in Python, updated each iteration
- [ ] Early termination when `len(usernames) >= expected_count` for 3 consecutive iterations
- [ ] Target: Eliminate post-scroll extraction phase entirely

### R4: Smarter End-of-List Detection
- [ ] Track scroll position delta - if scrollTop doesn't change after scroll command, we're at end
- [ ] Implement "confirmation scrolls" - only 3-5 extra scrolls after hitting end, not 40
- [ ] Use exponential backoff only when genuinely waiting for slow load, not as default
- [ ] Target: Reduce max no-change iterations from 40 to 5

### R5: Request Interception (Optional/Advanced)
- [ ] Intercept Instagram's GraphQL API responses via Chrome DevTools Protocol
- [ ] Extract usernames directly from API responses (bypasses DOM entirely)
- [ ] Fall back to DOM scraping if CDP interception fails
- [ ] Target: 10x speed improvement for large follower counts (5k+)

### R6: Progress Callbacks
- [ ] Add optional `progress_callback: Callable[[int, int], None]` parameter
- [ ] Call with `(current_count, expected_count)` each iteration
- [ ] Enable real-time progress reporting for CLI output
- [ ] Target: User sees "Scraped 245/575 followers..." updates

## Implementation Tasks

### Task 1: Unified Scroll-Extract Script
Create a single JavaScript function that handles scroll, extraction, and state detection:

```javascript
// Pseudocode for consolidated script
function scrollAndExtract(seenUsernames) {
    const modal = document.querySelector('div[role="dialog"]');
    const scrollable = findScrollableElement(modal);
    
    const beforeScroll = scrollable.scrollTop;
    scrollable.scrollTop = scrollable.scrollHeight;
    const afterScroll = scrollable.scrollTop;
    
    const usernames = extractUsernames(modal, seenUsernames);
    
    return {
        scrolled: afterScroll > beforeScroll,
        atEnd: afterScroll === beforeScroll,
        newUsernames: usernames,
        totalLoaded: seenUsernames.size + usernames.length
    };
}
```

### Task 2: Adaptive Delay Calculator
```python
class AdaptiveDelayCalculator:
    def __init__(self, min_delay=0.2, max_delay=2.0):
        self.min_delay = min_delay
        self.max_delay = max_delay
        self.recent_load_times = []  # Last N load durations
    
    def record_load(self, items_loaded: int, duration: float):
        """Track how fast content is loading."""
        pass
    
    def get_next_delay(self) -> float:
        """Return optimal delay based on recent load performance."""
        pass
```

### Task 3: Refactored `_scroll_modal_to_end`
```python
def _scroll_modal_to_end(self, modal: WebElement, expected_count: int = 0) -> list[str]:
    """Scroll and extract usernames incrementally with adaptive timing.
    
    Returns:
        List of all extracted usernames (collected during scroll).
    """
    all_usernames = set()
    delay_calc = AdaptiveDelayCalculator()
    at_end_count = 0
    
    while at_end_count < 5:  # Only 5 confirmation scrolls
        start = time.time()
        result = self._scroll_and_extract(modal, all_usernames)
        duration = time.time() - start
        
        all_usernames.update(result['newUsernames'])
        delay_calc.record_load(len(result['newUsernames']), duration)
        
        if result['atEnd']:
            at_end_count += 1
        else:
            at_end_count = 0
        
        if len(all_usernames) >= expected_count:
            break
            
        time.sleep(delay_calc.get_next_delay())
    
    return list(all_usernames)
```

### Task 4: Update Public API
- Modify `scrape_followers()` and `scrape_following()` to use refactored scroll method
- Return usernames directly from scroll method (no separate extraction call)
- Add optional `progress_callback` parameter

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| Time to scrape 500 followers | ~90s | <30s |
| Time to scrape 2000 followers | ~6min | <90s |
| Completeness (% of displayed count) | 95-99% | 99.5%+ |
| JS calls per 100 users loaded | ~300 | <100 |
| Max scroll iterations for 500 users | 200+ | <80 |

## Testing Strategy

1. **Unit tests**: Mock WebDriver, verify JS consolidation reduces call count
2. **Integration tests**: Scrape test account with known follower count, verify 100% extraction
3. **Performance benchmarks**: Time scrapes at 100, 500, 1000, 5000 follower counts
4. **Regression tests**: Ensure skip list and comparison logic still work with new scraper output

## Risks & Mitigations

| Risk | Mitigation |
|------|------------|
| Too-fast scrolling triggers rate limit | Implement rate limit detection (429 response or "try again later" text), auto-backoff |
| Instagram DOM structure changes | Maintain fallback selectors, log warnings on selector failures |
| CDP interception blocked by Instagram | CDP is optional enhancement, DOM scraping remains primary |
| Adaptive delay too aggressive | Floor delay at 0.2s minimum, cap at original 1.0s for safety |

## Files to Modify

- `src/ig_unfollower/scraper.py` - Main optimization target
- `src/ig_unfollower/config.py` - Add new config options (`adaptive_delay`, `min_scroll_delay`, etc.)
- `tests/test_scraper.py` - Add performance and completeness tests

## Out of Scope

- GraphQL API direct access (requires auth token extraction, higher ban risk)
- Multi-account parallel scraping
- Headless mode optimization (current requirement is non-headless)
