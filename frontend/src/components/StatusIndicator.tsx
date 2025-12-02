import { cn } from '../lib/utils';

interface StatusIndicatorProps {
  status: 'connected' | 'connecting' | 'disconnected' | 'error';
  label?: string;
  className?: string;
}

export function StatusIndicator({ status, label, className }: StatusIndicatorProps) {
  const colors = {
    connected: 'bg-emerald-500',
    connecting: 'bg-amber-500',
    disconnected: 'bg-zinc-500',
    error: 'bg-rose-500',
  };

  return (
    <div className={cn('flex items-center gap-2', className)}>
      <span
        className={cn(
          'w-2 h-2 rounded-full',
          colors[status],
          status === 'connecting' && 'animate-pulse'
        )}
      />
      {label && (
        <span className="text-sm text-zinc-400 font-mono">{label}</span>
      )}
    </div>
  );
}
