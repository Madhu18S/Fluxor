'use client'

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
} from 'recharts'

interface EquityPoint {
  ts: number
  naive: number
  friction: number
}

interface Props {
  data: EquityPoint[]
}

function fmtTs(ts: number) {
  const d = new Date(ts)
  return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })
}

function fmtDollars(v: number) {
  if (Math.abs(v) >= 1_000_000) return `$${(v / 1_000_000).toFixed(2)}M`
  if (Math.abs(v) >= 1_000) return `$${(v / 1_000).toFixed(1)}k`
  return `$${v.toFixed(0)}`
}

export function EquityCurveChart({ data }: Props) {
  return (
    <div className="w-full h-64">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={data} margin={{ top: 4, right: 16, left: 8, bottom: 4 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="oklch(0.28 0.012 255)" />
          <XAxis
            dataKey="ts"
            tickFormatter={fmtTs}
            tick={{ fontSize: 10, fill: 'oklch(0.58 0.01 240)', fontFamily: 'monospace' }}
            tickLine={false}
            axisLine={{ stroke: 'oklch(0.28 0.012 255)' }}
            minTickGap={60}
          />
          <YAxis
            tickFormatter={fmtDollars}
            tick={{ fontSize: 10, fill: 'oklch(0.58 0.01 240)', fontFamily: 'monospace' }}
            tickLine={false}
            axisLine={false}
            width={56}
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
            formatter={(v) => [fmtDollars(Number(v)), '']}
            labelFormatter={(ts) => new Date(Number(ts)).toISOString().slice(0, 16).replace('T', ' ')}
          />
          <Legend
            wrapperStyle={{ fontSize: '11px', fontFamily: 'monospace' }}
          />
          <Line
            type="monotone"
            dataKey="naive"
            name="Naive (no friction)"
            stroke="oklch(0.78 0.18 198)"
            dot={false}
            strokeWidth={1.5}
          />
          <Line
            type="monotone"
            dataKey="friction"
            name="Friction-adjusted"
            stroke="oklch(0.72 0.17 145)"
            dot={false}
            strokeWidth={1.5}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  )
}
