'use client'

import {
  ComposedChart,
  Line,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

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

export function LatencyChart({ data }: Props) {
  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <ComposedChart data={data} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.012 255)" />
          <XAxis
            dataKey="latency_ms"
            tickFormatter={(v: number) => `${v}ms`}
            tick={{ fontSize: 10, fill: 'oklch(0.58 0.01 240)', fontFamily: 'monospace' }}
            tickLine={false}
            axisLine={{ stroke: 'oklch(0.28 0.012 255)' }}
          />
          <YAxis
            yAxisId="left"
            tick={{ fontSize: 10, fill: 'oklch(0.78 0.18 198)', fontFamily: 'monospace' }}
            tickLine={false}
            axisLine={false}
            width={36}
            label={{ value: 'Sharpe', angle: -90, position: 'insideLeft', fontSize: 10, fill: 'oklch(0.78 0.18 198)', dx: -4 }}
          />
          <YAxis
            yAxisId="right"
            orientation="right"
            tick={{ fontSize: 10, fill: 'oklch(0.78 0.16 85)', fontFamily: 'monospace' }}
            tickLine={false}
            axisLine={false}
            width={44}
            tickFormatter={(v: number) => `${v.toFixed(1)}`}
            label={{ value: 'Net bps', angle: 90, position: 'insideRight', fontSize: 10, fill: 'oklch(0.78 0.16 85)', dx: 8 }}
          />
          <Tooltip
            contentStyle={{
              background: 'oklch(0.155 0.015 255)',
              border: '1px solid oklch(0.28 0.012 255)',
              borderRadius: '6px',
              fontSize: '11px',
              fontFamily: 'monospace',
              color: 'oklch(0.92 0.005 240)',
            }}
            labelFormatter={(v) => `Latency: ${v}ms`}
            formatter={(v) => [typeof v === 'number' ? v.toFixed(2) : String(v), '']}
          />
          <Legend wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }} />
          <Bar
            yAxisId="right"
            dataKey="avg_net_spread_bps"
            name="Avg net spread (bps)"
            fill="oklch(0.78 0.16 85 / 0.35)"
            stroke="oklch(0.78 0.16 85)"
            strokeWidth={1}
            radius={[3, 3, 0, 0]}
          />
          <Line
            yAxisId="left"
            type="monotone"
            dataKey="sharpe"
            name="Sharpe ratio"
            stroke="oklch(0.78 0.18 198)"
            dot={{ fill: 'oklch(0.78 0.18 198)', r: 4 }}
            strokeWidth={2}
          />
        </ComposedChart>
      </ResponsiveContainer>
    </div>
  )
}
