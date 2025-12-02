import { motion } from 'framer-motion';
import { cn, formatNumber } from '../lib/utils';

interface MetricCardProps {
  label: string;
  value: number;
  delta?: number;
  accent?: 'default' | 'rose' | 'amber' | 'emerald' | 'violet';
}

export function MetricCard({ label, value, delta, accent = 'default' }: MetricCardProps) {
  const accentColors = {
    default: 'text-zinc-100',
    rose: 'text-rose-400',
    amber: 'text-amber-400',
    emerald: 'text-emerald-400',
    violet: 'text-violet-400',
  };

  const glowColors = {
    default: 'from-cyan-500/5',
    rose: 'from-rose-500/5',
    amber: 'from-amber-500/5',
    emerald: 'from-emerald-500/5',
    violet: 'from-violet-500/5',
  };

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      whileHover={{ y: -2 }}
      className="bg-[#141416] border border-[#2a2a2d] p-4 relative overflow-hidden group"
    >
      <div
        className={cn(
          'absolute inset-0 opacity-0 group-hover:opacity-100 transition-opacity',
          'bg-gradient-to-br to-transparent',
          glowColors[accent]
        )}
      />

      <p className="text-xs text-zinc-500 uppercase tracking-wider font-mono mb-1">
        {label}
      </p>

      <div className="flex items-baseline gap-2">
        <span
          className={cn(
            'text-2xl font-mono font-bold tabular-nums',
            accentColors[accent]
          )}
        >
          {formatNumber(value)}
        </span>

        {delta !== undefined && delta !== 0 && (
          <span
            className={cn(
              'text-sm font-mono',
              delta > 0 ? 'text-emerald-400' : 'text-rose-400'
            )}
          >
            {delta > 0 ? '+' : ''}
            {delta}
          </span>
        )}
      </div>
    </motion.div>
  );
}
