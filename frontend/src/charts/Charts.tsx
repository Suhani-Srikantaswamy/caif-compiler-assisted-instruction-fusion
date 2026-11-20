import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

// Validated categorical slots (dataviz reference palette, DARK mode, checked against the #0f172a card surface),
// assigned in fixed order.
export const SERIES = ['#3987e5', '#d95926', '#199e70', '#c98500']
const SURFACE = '#0f172a'
const AXIS = { fontSize: 11, fill: '#94a3b8' }
const GRID = '#1e293b'

interface SeriesDef { key: string; name: string }

export function GroupedBars({ data, xKey, series, height = 280, yLabel, stacked = false }: {
  data: Record<string, unknown>[]; xKey: string; series: SeriesDef[]; height?: number; yLabel?: string; stacked?: boolean
}) {
  return (
    <ResponsiveContainer width="100%" height={height}>
      <BarChart data={data} margin={{ top: 8, right: 8, left: 0, bottom: 4 }} barGap={2} barCategoryGap="22%">
        <CartesianGrid stroke={GRID} vertical={false} />
        <XAxis dataKey={xKey} tick={AXIS} tickLine={false} axisLine={{ stroke: GRID }} interval={0} />
        <YAxis tick={AXIS} tickLine={false} axisLine={false} allowDecimals={false} width={44}
          label={yLabel ? { value: yLabel, angle: -90, position: 'insideLeft', style: { ...AXIS, textAnchor: 'middle' } } : undefined} />
        <Tooltip cursor={{ fill: 'rgba(148,163,184,0.10)' }}
          contentStyle={{ fontSize: 12, borderRadius: 8, background: '#020617', borderColor: '#334155', color: '#e2e8f0' }}
          labelStyle={{ color: '#f8fafc', fontWeight: 600 }} itemStyle={{ color: '#cbd5e1' }} />
        <Legend wrapperStyle={{ fontSize: 12, color: '#cbd5e1' }} iconType="square" />
        {series.map((s, i) => (
          <Bar key={s.key} dataKey={s.key} name={s.name} fill={SERIES[i]} stackId={stacked ? 'a' : undefined}
            radius={stacked ? (i === series.length - 1 ? [4, 4, 0, 0] : [0, 0, 0, 0]) : [4, 4, 0, 0]}
            maxBarSize={28} stroke={SURFACE} strokeWidth={stacked ? 1 : 0} />
        ))}
      </BarChart>
    </ResponsiveContainer>
  )
}
