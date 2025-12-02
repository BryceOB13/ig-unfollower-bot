import { useState } from 'react';
import { RefreshCw, UserMinus } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../stores/appStore';
import { api } from '../lib/api';

interface QuickActionsProps {
  notFollowingBackCount: number;
  onCompareStart: () => void;
  onUnfollowStart: (targets: string[], dryRun: boolean, maxUnfollows: number) => void;
}

export function QuickActions({
  notFollowingBackCount,
  onCompareStart,
  onUnfollowStart,
}: QuickActionsProps) {
  const [dryRun, setDryRun] = useState(true);
  const [maxUnfollows, setMaxUnfollows] = useState(50);
  const [isComparing, setIsComparing] = useState(false);
  const { activeOperation, selectedUsers } = useAppStore();

  const handleCompare = async () => {
    setIsComparing(true);
    try {
      onCompareStart();
    } finally {
      setIsComparing(false);
    }
  };

  const handleUnfollow = () => {
    const targets = Array.from(selectedUsers);
    if (targets.length === 0) {
      alert('Select users to unfollow first');
      return;
    }
    onUnfollowStart(targets, dryRun, maxUnfollows);
  };

  const isOperationRunning = activeOperation !== null;

  return (
    <div className="bg-[#141416] border border-[#2a2a2d] p-4 space-y-4">
      <h3 className="text-xs text-zinc-500 uppercase tracking-wider font-mono">
        Quick Actions
      </h3>

      <div className="flex gap-3">
        <button
          onClick={handleCompare}
          disabled={isOperationRunning}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 px-4 py-3',
            'bg-cyan-500/10 border border-cyan-500/30 text-cyan-400',
            'hover:bg-cyan-500/20 hover:border-cyan-500/50',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-all font-mono text-sm'
          )}
        >
          <RefreshCw className={cn('w-4 h-4', isComparing && 'animate-spin')} />
          Compare & Sync
        </button>

        <button
          onClick={handleUnfollow}
          disabled={isOperationRunning || selectedUsers.size === 0}
          className={cn(
            'flex-1 flex items-center justify-center gap-2 px-4 py-3',
            'bg-rose-500/10 border border-rose-500/30 text-rose-400',
            'hover:bg-rose-500/20 hover:border-rose-500/50',
            'disabled:opacity-50 disabled:cursor-not-allowed',
            'transition-all font-mono text-sm'
          )}
        >
          <UserMinus className="w-4 h-4" />
          Unfollow ({selectedUsers.size})
        </button>
      </div>

      <div className="flex items-center gap-4 pt-2">
        <label className="flex items-center gap-2 cursor-pointer">
          <input
            type="checkbox"
            checked={dryRun}
            onChange={(e) => setDryRun(e.target.checked)}
            className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-cyan-500 focus:ring-cyan-500"
          />
          <span className="text-sm text-zinc-400">Dry Run Mode</span>
        </label>

        <div className="flex items-center gap-2">
          <span className="text-sm text-zinc-500">Max unfollows:</span>
          <input
            type="number"
            value={maxUnfollows}
            onChange={(e) => setMaxUnfollows(Number(e.target.value))}
            className="w-20 px-2 py-1 bg-[#1c1c1f] border border-[#2a2a2d] text-zinc-200 font-mono text-sm"
          />
        </div>
      </div>
    </div>
  );
}
