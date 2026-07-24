import { cn } from '@/lib/utils'

interface MetricCardProps {
  label: string
  value: string
  sub?: string
  highlight?: 'cyan' | 'gain' | 'loss' | 'amber' | 'muted'
  className?: string
}

const highlightClass: Record<string, string> = {
  cyan: 'text-cyan',
  gain: 'text-gain',
  loss: 'text-loss',
  amber: 'text-amber',
  muted: 'text-muted-foreground',
}

export function MetricCard({ label, value, sub, highlight = 'cyan', className }: MetricCardProps) {
  return (
    <div
      className={cn(
        'flex flex-col gap-1 rounded-lg border border-border bg-card px-4 py-4',
        className,
      )}
    >
      <span className="text-xs font-mono tracking-widest text-muted-foreground uppercase">
        {label}
      </span>
      <span
        className={cn(
          'text-2xl font-mono font-semibold leading-tight tabular-nums',
          highlightClass[highlight],
        )}
      >
        {value}
      </span>
      {sub && (
        <span className="text-xs text-muted-foreground font-mono">{sub}</span>
      )}
    </div>
  )
}
