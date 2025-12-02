import { cn } from '../lib/utils';

interface ProgressBarProps {
  progress: number;
  total: number;
  message?: string;
  className?: string;
}

export function ProgressBar({ progress, total, message, className }: ProgressBarProps) {
  const percentage = total > 0 ? Math.round((progress / total) * 100) : 0;

  return (
    <div className={cn('space-y-2', className)}>
      <div className="flex justify-between text-xs font-mono text-zinc-400">
        <span>{message || 'Processing...'}</span>
        <span>
          {percentage}% · {progress}/{total}
        </span>
      </div>
      <div className="h-2 bg-[#1c1c1f] rounded overflow-hidden">
        <div
          className="h-full bg-gradient-to-r from-cyan-500 to-cyan-400 transition-all duration-300 relative"
          style={{ width: `${percentage}%` }}
        >
          {/* Shimmer effect */}
          <div className="absolute inset-0 bg-gradient-to-r from-transparent via-white/20 to-transparent animate-shimmer" />
        </div>
      </div>
    </div>
  );
}
