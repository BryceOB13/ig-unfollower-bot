import { MetricCard } from './MetricCard';
import type { Snapshot, Comparison } from '../types';

interface MetricsRowProps {
  snapshot?: Snapshot | null;
  comparison?: Comparison | null;
}

export function MetricsRow({ snapshot, comparison }: MetricsRowProps) {
  return (
    <div className="grid grid-cols-5 gap-4">
      <MetricCard
        label="Followers"
        value={snapshot?.followers_count ?? 0}
        accent="default"
      />
      <MetricCard
        label="Following"
        value={snapshot?.following_count ?? 0}
        accent="default"
      />
      <MetricCard
        label="Unfollowers"
        value={comparison?.unfollowers.length ?? 0}
        delta={comparison?.unfollowers.length ? -comparison.unfollowers.length : undefined}
        accent="rose"
      />
      <MetricCard
        label="Not Following Back"
        value={comparison?.not_following_back.length ?? 0}
        accent="amber"
      />
      <MetricCard
        label="New Followers"
        value={comparison?.new_followers.length ?? 0}
        delta={comparison?.new_followers.length}
        accent="violet"
      />
    </div>
  );
}
