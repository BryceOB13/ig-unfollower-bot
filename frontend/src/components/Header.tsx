import { Settings } from 'lucide-react';
import { StatusIndicator } from './StatusIndicator';
import { useAppStore } from '../stores/appStore';
import { timeAgo } from '../lib/utils';
import type { LastOperation } from '../types';

interface HeaderProps {
  username?: string;
  lastOperation?: LastOperation | null;
}

export function Header({ username, lastOperation }: HeaderProps) {
  const { browserConnected, loggedIn, setSettingsOpen } = useAppStore();

  const getStatusLabel = () => {
    if (!browserConnected) return 'Browser Offline';
    if (!loggedIn) return 'Not Logged In';
    return 'Ready';
  };

  const getStatus = () => {
    if (!browserConnected) return 'disconnected';
    if (!loggedIn) return 'connecting';
    return 'connected';
  };

  return (
    <header className="h-14 border-b border-[#2a2a2d] bg-[#0a0a0b] px-4 flex items-center justify-between">
      <div className="flex items-center gap-6">
        <h1 className="font-mono font-bold text-lg tracking-tight text-cyan-400">
          IG UNFLW
        </h1>

        <div className="flex items-center gap-2 text-sm text-zinc-400">
          {username && (
            <>
              <span className="font-mono">@{username}</span>
              <span className="text-zinc-600">·</span>
            </>
          )}
          {lastOperation && (
            <span className="text-zinc-500">
              Last sync: {timeAgo(lastOperation.timestamp)}
            </span>
          )}
        </div>
      </div>

      <div className="flex items-center gap-4">
        <StatusIndicator status={getStatus()} label={getStatusLabel()} />

        <button
          onClick={() => setSettingsOpen(true)}
          className="p-2 hover:bg-[#1c1c1f] rounded transition-colors"
        >
          <Settings className="w-5 h-5 text-zinc-400" />
        </button>
      </div>
    </header>
  );
}
