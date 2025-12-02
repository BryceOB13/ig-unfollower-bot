# IG Unfollower — Frontend UI Specification for Kiro

## Project Context

Build a production-ready React dashboard for an Instagram unfollower management tool. The backend is a Python CLI application using Selenium for browser automation. The frontend will communicate with a FastAPI wrapper we'll add around the existing functionality.

**Tech Stack:**
- React 18+ with TypeScript
- shadcn/ui components (NOT the default theme — customize aggressively)
- Tailwind CSS
- Tanstack Query for data fetching
- Zustand for client state
- Framer Motion for animations
- Recharts for data visualization

---

## Design Direction: "Command Center"

**Aesthetic:** Industrial precision meets cyberpunk utility. Think Bloomberg Terminal meets Figma's polish. Dark mode primary with high-contrast data visualization.

**Core Principles:**
1. **Information density without clutter** — operators want data at a glance
2. **Status always visible** — browser state, login state, operation progress
3. **One-click actions** — minimize friction for common operations
4. **Real-time feedback** — WebSocket updates during scraping operations

**Typography:**
- Display/Headers: `JetBrains Mono` or `IBM Plex Mono` (monospace reinforces the "tool" feeling)
- Body: `IBM Plex Sans` or `Geist Sans`
- Data/Numbers: `Tabular figures` enabled, monospace for counts

**Color Palette:**
```css
--bg-primary: #0a0a0b;      /* Near black */
--bg-secondary: #141416;    /* Card backgrounds */
--bg-tertiary: #1c1c1f;     /* Hover states */
--border: #2a2a2d;          /* Subtle borders */
--text-primary: #fafafa;
--text-secondary: #71717a;
--accent-cyan: #22d3ee;     /* Primary actions */
--accent-emerald: #10b981;  /* Success states */
--accent-amber: #f59e0b;    /* Warnings */
--accent-rose: #f43f5e;     /* Destructive/unfollowers */
--accent-violet: #8b5cf6;   /* New followers */
```

**Visual Details:**
- Subtle 1px borders with low opacity
- No rounded corners larger than 6px (sharp, utilitarian)
- Subtle noise texture overlay on backgrounds (2-3% opacity)
- Glow effects on interactive elements (box-shadow with accent colors)
- Status indicators use pulsing animations

---

## Layout Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  HEADER BAR (h-14)                                                          │
│  ┌──────────┐  ┌─────────────────────────────────┐  ┌────────┐ ┌──────────┐ │
│  │ IG UNFLW │  │ @username · Last sync: 2m ago   │  │ Status │ │ Settings │ │
│  └──────────┘  └─────────────────────────────────┘  └────────┘ └──────────┘ │
├─────────────────────────────────────────────────────────────────────────────┤
│  MAIN CONTENT                                                               │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ METRICS ROW                                                             ││
│  │ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌─────────────┐ ││
│  │ │ Followers │ │ Following │ │ Unfollwrs │ │ Not Back  │ │ New Follwrs │ ││
│  │ │   1,247   │ │    892    │ │    -12    │ │    156    │ │     +8      │ ││
│  │ │  +3 today │ │  -2 today │ │  ▼ trend  │ │ actionabl │ │   ▲ trend   │ ││
│  │ └───────────┘ └───────────┘ └───────────┘ └───────────┘ └─────────────┘ ││
│  └─────────────────────────────────────────────────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────┐ ┌─────────────────────────────┐│
│  │ QUICK ACTIONS                           │ │ OPERATION STATUS            ││
│  │                                         │ │                             ││
│  │  ┌─────────────┐  ┌─────────────┐       │ │  Browser: ● Connected       ││
│  │  │   Compare   │  │   Unfollow  │       │ │  Session: ● Authenticated   ││
│  │  │   & Sync    │  │    Mode     │       │ │  Last Op: Compare 2m ago    ││
│  │  └─────────────┘  └─────────────┘       │ │                             ││
│  │                                         │ │  ┌─────────────────────────┐││
│  │  ○ Dry Run Mode                         │ │  │ Progress Bar (if active)│││
│  │  Max unfollows: [___50___]              │ │  │ ████████░░░░ 67% 134/200│││
│  │                                         │ │  └─────────────────────────┘││
│  └─────────────────────────────────────────┘ └─────────────────────────────┘│
│                                                                              │
│  ┌─────────────────────────────────────────────────────────────────────────┐│
│  │ TABS: [ Not Following Back ] [ Unfollowers ] [ New Followers ] [ Skip ] ││
│  ├─────────────────────────────────────────────────────────────────────────┤│
│  │ ┌──────┐ ┌────────────────────────────────────────────────────┐ ┌─────┐ ││
│  │ │ [ ] │ │ @username1                                          │ │ ... │ ││
│  │ └──────┘ │ user1 · 1.2K followers · Not following back: 45d   │ └─────┘ ││
│  │ ┌──────┐ ┌────────────────────────────────────────────────────┐ ┌─────┐ ││
│  │ │ [✓] │ │ @username2                                          │ │ ... │ ││
│  │ └──────┘ │ user2 · 890 followers · Not following back: 12d    │ └─────┘ ││
│  │          ...                                                            ││
│  │ ┌───────────────────────────────────────────────────────────────────┐   ││
│  │ │ BULK ACTIONS: [ Select All ] [ Add to Skip ] [ Unfollow Selected ]│   ││
│  │ └───────────────────────────────────────────────────────────────────┘   ││
│  └─────────────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Header Bar (`components/Header.tsx`)
- Logo/brand mark (stylized "IG UNFLW" in monospace)
- Current username display with avatar placeholder
- Last sync timestamp (relative time: "2m ago")
- Global status indicator (dot + text)
- Settings gear icon → opens settings drawer

### 2. Metrics Row (`components/MetricsRow.tsx`)
Five metric cards in a grid:

| Metric | Description | Visual Treatment |
|--------|-------------|------------------|
| Followers | Current count | Neutral, show delta |
| Following | Current count | Neutral, show delta |
| Unfollowers | Lost since last snapshot | Rose/red accent, down arrow |
| Not Following Back | Actionable targets | Amber accent, shows count |
| New Followers | Gained since last snapshot | Violet accent, up arrow |

Each card has:
- Large number (tabular figures)
- Label
- Trend indicator (sparkline or delta badge)
- Subtle hover lift animation

### 3. Quick Actions Panel (`components/QuickActions.tsx`)
Two primary action buttons:

**Compare & Sync Button:**
- Primary cyan accent
- Opens confirmation modal with options
- Shows "Syncing..." state with spinner during operation

**Unfollow Mode Button:**
- Destructive rose accent (but not alarming)
- Requires confirmation
- Shows current target count in badge

Additional controls:
- Dry Run toggle switch
- Max unfollows number input (with quick presets: 10, 25, 50, 100)

### 4. Operation Status Panel (`components/OperationStatus.tsx`)
Live status display:
- Browser connection indicator (green dot = connected, amber = connecting, gray = disconnected)
- Session/auth indicator (green = logged in, red = needs login)
- Current operation name + timestamp
- Progress bar (only visible during active operations)
  - Shows: percentage, current/total count, ETA
  - Animated fill with subtle shimmer

### 5. Data Tabs (`components/DataTabs.tsx`)
Four tabs using shadcn Tabs component:

**Tab: Not Following Back**
- Primary actionable list
- Columns: checkbox, avatar, username, display name, follower count, days since detected
- Row actions: Add to Skip, Unfollow, View Profile (external link)
- Bulk action bar at bottom

**Tab: Unfollowers**
- Historical record of users who unfollowed
- Columns: avatar, username, detected date, follower count at time
- No actions (informational only)

**Tab: New Followers**
- Recent new followers
- Columns: avatar, username, detected date
- Action: Add to Skip (protect from future unfollow consideration)

**Tab: Skip List**
- Managed exclusion list
- Columns: username, date added, reason (optional)
- Actions: Remove from list
- Add manually via input

### 6. Settings Drawer (`components/SettingsDrawer.tsx`)
Slide-in from right:
- **Account Section:**
  - Username input
  - Login button (triggers manual login flow)
  - Logout button

- **Timing Section:**
  - Action delay range (min/max sliders)
  - Scroll delay
  - Element timeout

- **Filters Section:**
  - Skip verified accounts toggle
  - Skip accounts over X followers threshold

- **Data Section:**
  - Export snapshot button
  - Import snapshot button
  - Clear history button (with confirmation)

---

## Backend Integration Architecture

### FastAPI Wrapper (`api/main.py`)

Create a FastAPI application that wraps the existing CLI functionality:

```python
# Endpoints to implement:

GET  /api/status
# Returns: { browser_connected: bool, logged_in: bool, last_operation: {...} }

POST /api/auth/login
# Body: { manual: bool }
# Returns: { success: bool, message: str }
# Triggers browser login flow

POST /api/compare
# Triggers compare mode, returns immediately with operation_id
# Returns: { operation_id: str, status: "started" }

GET  /api/compare/{operation_id}
# Returns operation progress and results when complete

POST /api/unfollow
# Body: { targets: string[], dry_run: bool, max_unfollows: int }
# Returns: { operation_id: str, status: "started" }

GET  /api/unfollow/{operation_id}
# Returns operation progress and results

GET  /api/snapshot/latest
# Returns: { followers: [...], following: [...], timestamp: str, counts: {...} }

GET  /api/comparison/latest
# Returns: { unfollowers: [...], not_following_back: [...], new_followers: [...] }

GET  /api/skip-list
# Returns: { usernames: [...] }

POST /api/skip-list
# Body: { username: str }
# Adds to skip list

DELETE /api/skip-list/{username}
# Removes from skip list

GET  /api/history
# Returns: { unfollowed: { username: timestamp, ... } }

GET  /api/config
# Returns current configuration

PUT  /api/config
# Updates configuration
```

### WebSocket for Real-time Updates

```python
WS /api/ws
# Emits events:
# - { type: "progress", current: int, total: int, message: str }
# - { type: "status_change", browser: bool, logged_in: bool }
# - { type: "operation_complete", operation_id: str, result: {...} }
```

### Frontend API Client (`lib/api.ts`)

```typescript
// Use Tanstack Query for data fetching
// Use native WebSocket or socket.io-client for real-time

export const api = {
  getStatus: () => fetch('/api/status').then(r => r.json()),
  login: (manual: boolean) => fetch('/api/auth/login', { method: 'POST', body: JSON.stringify({ manual }) }),
  startCompare: () => fetch('/api/compare', { method: 'POST' }),
  startUnfollow: (opts: UnfollowOptions) => fetch('/api/unfollow', { method: 'POST', body: JSON.stringify(opts) }),
  getLatestSnapshot: () => fetch('/api/snapshot/latest').then(r => r.json()),
  getLatestComparison: () => fetch('/api/comparison/latest').then(r => r.json()),
  // ... etc
}
```

### State Management (`stores/appStore.ts`)

```typescript
interface AppState {
  // Connection status
  browserConnected: boolean;
  loggedIn: boolean;
  
  // Current operation
  activeOperation: {
    id: string;
    type: 'compare' | 'unfollow';
    progress: number;
    total: number;
    message: string;
  } | null;
  
  // UI state
  selectedUsers: Set<string>;
  activeTab: 'not-following-back' | 'unfollowers' | 'new-followers' | 'skip-list';
  settingsOpen: boolean;
  
  // Actions
  setActiveOperation: (op: Operation | null) => void;
  toggleUserSelection: (username: string) => void;
  // ... etc
}
```

---

## File Structure

```
src/
├── components/
│   ├── ui/                    # shadcn components (customized)
│   ├── Header.tsx
│   ├── MetricsRow.tsx
│   ├── MetricCard.tsx
│   ├── QuickActions.tsx
│   ├── OperationStatus.tsx
│   ├── ProgressBar.tsx
│   ├── DataTabs.tsx
│   ├── UserTable.tsx
│   ├── UserRow.tsx
│   ├── BulkActions.tsx
│   ├── SettingsDrawer.tsx
│   └── StatusIndicator.tsx
├── lib/
│   ├── api.ts                 # API client
│   ├── websocket.ts           # WebSocket connection manager
│   └── utils.ts               # Helpers (formatNumber, timeAgo, etc.)
├── stores/
│   └── appStore.ts            # Zustand store
├── hooks/
│   ├── useStatus.ts           # Query hook for status
│   ├── useSnapshot.ts         # Query hook for snapshot data
│   ├── useComparison.ts       # Query hook for comparison data
│   └── useWebSocket.ts        # WebSocket hook
├── types/
│   └── index.ts               # TypeScript interfaces
├── styles/
│   └── globals.css            # Tailwind + custom CSS
├── App.tsx
└── main.tsx
```

---

## Animation Guidelines

**Page Load:**
- Metrics cards stagger in from bottom (50ms delay each)
- Header fades in
- Main content area fades in after metrics

**Interactions:**
- Buttons: scale(0.98) on press, subtle glow on hover
- Cards: translateY(-2px) + shadow increase on hover
- Tabs: underline slides to active tab
- Checkboxes: satisfying checkmark animation
- Progress bar: shimmer effect across fill

**Status Changes:**
- Pulsing glow on status indicators
- Number counters animate when values change (count up/down)
- Toast notifications slide in from top-right

**Loading States:**
- Skeleton loaders match exact content dimensions
- Subtle pulse animation on skeletons
- Spinner uses accent color

---

## Key Implementation Notes

1. **No generic shadcn defaults** — Override every component's styling. The default shadcn look is recognizable; we want this to feel custom-built.

2. **Monospace for data** — All usernames, counts, and timestamps should use monospace font for that "terminal" feel.

3. **Dense but scannable** — Pack information tight but use clear visual hierarchy. Operators should find what they need in <1 second.

4. **Optimistic UI** — When adding to skip list or selecting users, update UI immediately before API confirms.

5. **Error states** — Every async operation needs loading, success, and error states. Use toast notifications for transient feedback.

6. **Keyboard navigation** — Support arrow keys in tables, Enter to confirm, Escape to cancel.

7. **Responsive but desktop-first** — Primary use is desktop. Mobile should work but optimize for 1200px+ viewports.

---

## Example Component: MetricCard

```tsx
// This shows the level of detail expected

interface MetricCardProps {
  label: string;
  value: number;
  delta?: number;
  accent?: 'default' | 'rose' | 'amber' | 'emerald' | 'violet';
  trend?: number[]; // Last 7 values for sparkline
}

export function MetricCard({ label, value, delta, accent = 'default', trend }: MetricCardProps) {
  const accentColors = {
    default: 'text-zinc-100',
    rose: 'text-rose-400',
    amber: 'text-amber-400',
    emerald: 'text-emerald-400',
    violet: 'text-violet-400',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      className="bg-zinc-900/50 border border-zinc-800 p-4 relative overflow-hidden group"
    >
      {/* Subtle glow on hover */}
      <div className={cn(
        "absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity",
        "bg-gradient-to-br from-cyan-500/5 to-transparent"
      )} />
      
      <p className="text-xs text-zinc-500 uppercase tracking-wider font-mono mb-1">
        {label}
      </p>
      
      <div className="flex items-baseline gap-2">
        <AnimatedNumber 
          value={value} 
          className={cn("text-2xl font-mono font-bold tabular-nums", accentColors[accent])}
        />
        
        {delta !== undefined && (
          <span className={cn(
            "text-sm font-mono",
            delta > 0 ? "text-emerald-400" : delta < 0 ? "text-rose-400" : "text-zinc-500"
          )}>
            {delta > 0 ? '+' : ''}{delta}
          </span>
        )}
      </div>
      
      {trend && (
        <Sparkline data={trend} className="mt-2 h-8" color={accent} />
      )}
    </motion.div>
  );
}
```

---

## Deliverables Checklist

- [ ] Full React application with routing (single page, no router needed)
- [ ] All components listed above
- [ ] Custom shadcn theme matching color palette
- [ ] API client with all endpoints
- [ ] WebSocket integration for real-time updates
- [ ] Zustand store for global state
- [ ] Loading and error states for all async operations
- [ ] Responsive layout (desktop-optimized)
- [ ] Keyboard accessibility
- [ ] Entrance animations
- [ ] Dark mode only (no light mode toggle needed)

---

## Backend Implementation Notes

After the frontend is generated, we'll need to create `api/main.py` that:

1. Imports and wraps the existing modules from `src/ig_unfollower/`
2. Manages a single browser instance across requests
3. Uses background tasks for long-running operations (compare, unfollow)
4. Broadcasts progress via WebSocket
5. Stores operation state in memory (or Redis for production)

The existing code already has clean separation:
- `BrowserManager` — reuse for browser lifecycle
- `InstagramScraper` — reuse for data extraction  
- `SnapshotManager` — reuse for persistence
- `SnapshotComparator` — reuse for diff logic
- `UnfollowExecutor` — reuse for unfollow actions
- `SkipListManager` — reuse for skip list CRUD
- `HistoryManager` — reuse for history tracking

The API layer just needs to orchestrate these and expose HTTP endpoints.
