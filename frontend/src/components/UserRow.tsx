import { ExternalLink, Plus, UserMinus } from 'lucide-react';
import { cn } from '../lib/utils';
import { useAppStore } from '../stores/appStore';

interface UserRowProps {
  username: string;
  showCheckbox?: boolean;
  showActions?: boolean;
  onAddToSkip?: (username: string) => void;
  onUnfollow?: (username: string) => void;
}

export function UserRow({
  username,
  showCheckbox = true,
  showActions = true,
  onAddToSkip,
  onUnfollow,
}: UserRowProps) {
  const { selectedUsers, toggleUserSelection } = useAppStore();
  const isSelected = selectedUsers.has(username);

  return (
    <div
      className={cn(
        'flex items-center gap-3 px-4 py-3 border-b border-[#2a2a2d]',
        'hover:bg-[#1c1c1f] transition-colors',
        isSelected && 'bg-cyan-500/5'
      )}
    >
      {showCheckbox && (
        <input
          type="checkbox"
          checked={isSelected}
          onChange={() => toggleUserSelection(username)}
          className="w-4 h-4 rounded border-zinc-600 bg-zinc-800 text-cyan-500 focus:ring-cyan-500"
        />
      )}

      <div className="flex-1 min-w-0">
        <span className="font-mono text-sm text-zinc-200">@{username}</span>
      </div>

      {showActions && (
        <div className="flex items-center gap-1">
          {onAddToSkip && (
            <button
              onClick={() => onAddToSkip(username)}
              className="p-1.5 hover:bg-[#2a2a2d] rounded transition-colors group relative"
              title="Add to skip list - User won't appear in unfollow suggestions"
            >
              <Plus className="w-4 h-4 text-zinc-500 hover:text-zinc-300" />
            </button>
          )}
          {onUnfollow && (
            <button
              onClick={() => onUnfollow(username)}
              className="p-1.5 hover:bg-rose-500/10 rounded transition-colors group relative"
              title="Unfollow this user"
            >
              <UserMinus className="w-4 h-4 text-zinc-500 hover:text-rose-400" />
            </button>
          )}
          <a
            href={`https://instagram.com/${username}`}
            target="_blank"
            rel="noopener noreferrer"
            className="p-1.5 hover:bg-[#2a2a2d] rounded transition-colors group relative"
            title="View Instagram profile"
          >
            <ExternalLink className="w-4 h-4 text-zinc-500 hover:text-zinc-300" />
          </a>
        </div>
      )}
    </div>
  );
}
