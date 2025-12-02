import { StatusIndicator } from './StatusIndicator';
import { ProgressBar } from './ProgressBar';
import { useAppStore } from '../stores/appStore';
import { timeAgo } from '../lib/utils';
import type { LastOperation } from '../types';

interface OperationStatusProps {
  lastOperation?: LastOperation | null;
}

export function OperationStatus({ lastOperation }: OperationStatusProps) {
  const { browserConnected, loggedIn, activeOperation } = useAppStore();

  return (
    <div className="bg-[#141416] border border-[#2a2a2d] p-4 space-y-4">
      <h3 className="text-xs text-zinc-500 uppercase tracking-wider font-mono">
        Operation Status
      </h3>

      <div className="space-y-2">
        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-400">Browser</span>
          <StatusIndicator
            status={browserConnected ? 'connected' : 'disconnected'}
            label={browserConnected ? 'Connected' : 'Disconnected'}
          />
        </div>

        <div className="flex items-center justify-between">
          <span className="text-sm text-zinc-400">Session</span>
          <StatusIndicator
            status={loggedIn ? 'connected' : 'error'}
            label={loggedIn ? 'Authenticated' : 'Not Logged In'}
          />
        </div>

        {lastOperation && (
          <div className="flex items-center justify-between">
            <span className="text-sm text-zinc-400">Last Op</span>
            <span className="text-sm text-zinc-300 font-mono">
              {lastOperation.type} {timeAgo(lastOperation.timestamp)}
            </span>
          </div>
        )}
      </div>

      {activeOperation && (
        <ProgressBar
          progress={activeOperation.progress}
          total={activeOperation.total}
          message={activeOperation.message}
          className="pt-2"
        />
      )}
    </div>
  );
}
