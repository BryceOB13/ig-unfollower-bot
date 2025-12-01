"""Custom Hypothesis strategies for property-based testing."""

from hypothesis import strategies as st
from datetime import datetime, timezone

# Generate valid Instagram usernames (1-30 chars, alphanumeric + underscore + period)
# Rules: cannot start/end with period, no consecutive periods
username_strategy = st.text(
    alphabet=st.sampled_from("abcdefghijklmnopqrstuvwxyz0123456789_."),
    min_size=1,
    max_size=30
).filter(
    lambda x: (
        not x.startswith('.') and 
        not x.endswith('.') and 
        '..' not in x and
        len(x) > 0
    )
)

# Generate list of unique usernames
username_list_strategy = st.lists(
    username_strategy, 
    unique=True, 
    min_size=0, 
    max_size=100
)

# Generate set of unique usernames
username_set_strategy = st.frozensets(
    username_strategy,
    min_size=0,
    max_size=100
).map(set)


# Generate ISO 8601 timestamps
def _format_timestamp(dt: datetime) -> str:
    """Format datetime as ISO 8601 with Z suffix."""
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


timestamp_strategy = st.datetimes(
    min_value=datetime(2020, 1, 1),
    max_value=datetime(2030, 12, 31)
).map(_format_timestamp)


# Generate valid Snapshot objects (lazy import to avoid circular deps)
def snapshot_strategy():
    """Strategy for generating valid Snapshot objects."""
    from ig_unfollower.snapshot import Snapshot
    
    return st.builds(
        Snapshot,
        timestamp=timestamp_strategy,
        followers=username_list_strategy,
        following=username_list_strategy,
        followers_count=st.just(0),  # Will be set by __post_init__
        following_count=st.just(0)   # Will be set by __post_init__
    )
