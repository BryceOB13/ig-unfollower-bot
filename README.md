# IG Unfollower Bot

A tool to track Instagram followers/following and identify accounts that don't follow you back.

## Setup

1. Install dependencies:
```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

2. Copy example files:
```bash
cp config.json.example config.json
cp run.sh.example run.sh
chmod +x run.sh
```

3. Edit `run.sh` with your Instagram credentials

## Usage

### Compare Mode (default)
Scrapes followers/following and compares with previous snapshot:
```bash
./run.sh compare
```

### Unfollow Mode
Auto-unfollow accounts that don't follow back:
```bash
./run.sh unfollow
```

Dry run (no actual unfollows):
```bash
./run.sh unfollow --dry_run
```

## Output

Results are saved to the `snapshots/` directory:
- `snapshot_*.json` - Raw follower/following data
- `comparison_*.json` - Comparison results
- `latest_comparison.json` - Most recent comparison

## Configuration

Edit `config.json` to customize:
- `scroll_delay` - Delay between scrolls (seconds)
- `action_delay_min/max` - Delay range between actions
- `skip_verified` - Skip verified accounts when unfollowing
- `skip_follower_threshold` - Skip accounts with more than N followers
