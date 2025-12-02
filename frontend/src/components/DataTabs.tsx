import { useState } from 'react';
import { cn } from '../lib/utils';
import { UserRow } from './UserRow';
import { useAppStore } from '../stores/appStore';
import type { Comparison } from '../types';

interface DataTabsProps {
  comparison?: Comparison | null;
  skipList: string[];
  onAddToSkip: (username: string) => void;
  onRemoveFromSkip: (username: string) => void;
  onUnfollow: (username: string) => void;
}

type TabId = 'not-following-back' | 'unfollowers' | 'new-followers' | 'skip-list';

const tabs: { id: TabId; label: string }[] = [
  { id: 'not-following-back', label: 'Not Following Back' },
  { id: 'unfollowers', label: 'Unfollowers' },
  { id: 'new-followers', label: 'New Followers' },
  { id: 'skip-list', label: 'Skip List' },
];

export function DataTabs({
  comparison,
  skipList,
  onAddToSkip,
  onRemoveFromSkip,
  onUnfollow,
}: DataTabsProps) {
  const { activeTab, setActiveTab, selectedUsers, selectAllUsers, clearSelection } = useAppStore();

  const getTabData = (): string[] => {
    switch (activeTab) {
      case 'not-following-back':
        return comparison?.not_following_back ?? [];
      case 'unfollowers':
        return comparison?.unfollowers ?? [];
      case 'new-followers':
        return comparison?.new_followers ?? [];
      case 'skip-list':
        return skipList;
      default:
        return [];
    }
  };

  const data = getTabData();

  const handleSelectAll = () => {
    if (selectedUsers.size === data.length) {
      clearSelection();
    } else {
      selectAllUsers(data);
    }
  };

  return (
    <div className="bg-[#141416] border border-[#2a2a2d] flex flex-col h-[400px]">
      {/* Tab headers */}
      <div className="flex border-b border-[#2a2a2d]">
        {tabs.map((tab) => (
          <button
            key={tab.id}
            onClick={() => setActiveTab(tab.id)}
            className={cn(
              'px-4 py-3 text-sm font-mono transition-colors relative',
              activeTab === tab.id
                ? 'text-cyan-400'
                : 'text-zinc-500 hover:text-zinc-300'
            )}
          >
            {tab.label}
            {activeTab === tab.id && (
              <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-cyan-400" />
            )}
          </button>
        ))}
      </div>

      {/* Tab content */}
      <div className="flex-1 overflow-y-auto">
        {data.length === 0 ? (
          <div className="flex items-center justify-center h-full text-zinc-500 text-sm">
            No data available
          </div>
        ) : (
          data.map((username) => (
            <UserRow
              key={username}
              username={username}
              showCheckbox={activeTab === 'not-following-back'}
              showActions={activeTab !== 'skip-list'}
              onAddToSkip={activeTab !== 'skip-list' ? onAddToSkip : undefined}
              onUnfollow={activeTab === 'not-following-back' ? onUnfollow : undefined}
            />
          ))
        )}
      </div>

      {/* Bulk actions */}
      {activeTab === 'not-following-back' && data.length > 0 && (
        <div className="border-t border-[#2a2a2d] px-4 py-3 flex items-center gap-3">
          <button
            onClick={handleSelectAll}
            className="px-3 py-1.5 text-xs font-mono text-zinc-400 hover:text-zinc-200 border border-[#2a2a2d] hover:border-zinc-600 transition-colors"
          >
            {selectedUsers.size === data.length ? 'Deselect All' : 'Select All'}
          </button>
          <span className="text-xs text-zinc-500">
            {selectedUsers.size} selected
          </span>
        </div>
      )}

      {/* Skip list actions */}
      {activeTab === 'skip-list' && (
        <div className="border-t border-[#2a2a2d] px-4 py-3">
          <SkipListInput onAdd={onAddToSkip} />
        </div>
      )}
    </div>
  );
}

function SkipListInput({ onAdd }: { onAdd: (username: string) => void }) {
  const [value, setValue] = useState('');

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (value.trim()) {
      onAdd(value.trim().replace('@', ''));
      setValue('');
    }
  };

  return (
    <form onSubmit={handleSubmit} className="flex gap-2">
      <input
        type="text"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        placeholder="Add username..."
        className="flex-1 px-3 py-1.5 bg-[#1c1c1f] border border-[#2a2a2d] text-zinc-200 font-mono text-sm placeholder:text-zinc-600"
      />
      <button
        type="submit"
        className="px-3 py-1.5 text-xs font-mono text-cyan-400 border border-cyan-500/30 hover:bg-cyan-500/10 transition-colors"
      >
        Add
      </button>
    </form>
  );
}
