import { cn } from '@/lib/utils'

interface LatencyPoint {
  latency_ms: number
  sharpe: number
  avg_net_spread_bps: number
  win_rate: number
  total_net_pnl: number
  trade_count: number
}

interface Props {
  data: LatencyPoint[]
}

function fmtPnl(v: number) {
  const abs = Math.abs(v)
  const sign = v < 0 ? '-' : ''
  if (abs >= 1_000_000) return `${sign}$${(abs / 1_000_000).toFixed(2)}M`
  if (abs >= 1_000) return `${sign}$${(abs / 1_000).toFixed(1)}k`
  return `${sign}$${abs.toFixed(0)}`
}

export function LatencyTable({ data }: Props) {
  const maxSharpe = Math.max(...data.map(d => d.sharpe))

  return (
    <div className="overflow-x-auto rounded-lg border border-border">
      <table className="w-full text-xs font-mono text-left">
        <thead>
          <tr className="border-b border-border bg-surface-2">
            {['Latency', 'Sharpe', 'Net bps', 'Win %', 'Net PnL', 'Trades'].map(h => (
              <th key={h} className="px-3 py-2 text-muted-foreground tracking-wider uppercase text-[10px]">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map((row, i) => {
            const isMax = row.sharpe === maxSharpe
            const profitable = row.total_net_pnl >= 0
            return (
              <tr
                key={i}
                className={cn(
                  'border-b border-border/50 transition-colors hover:bg-surface-2',
                  isMax && 'bg-cyan/5',
                )}
              >
                <td className="px-3 py-2 text-muted-foreground">{row.latency_ms}ms</td>
                <td className={cn('px-3 py-2 tabular-nums font-semibold', isMax ? 'text-cyan' : 'text-foreground')}>
                  {row.sharpe.toFixed(2)}
                </td>
                <td className="px-3 py-2 tabular-nums text-amber">{row.avg_net_spread_bps.toFixed(2)}</td>
                <td className="px-3 py-2 tabular-nums">{row.win_rate.toFixed(1)}%</td>
                <td className={cn('px-3 py-2 tabular-nums', profitable ? 'text-gain' : 'text-loss')}>
                  {fmtPnl(row.total_net_pnl)}
                </td>
                <td className="px-3 py-2 tabular-nums text-muted-foreground">{row.trade_count.toLocaleString()}</td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </div>
  )
}
