import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

import type { SummaryGroup } from '@/lib/api'
import { formatCompactMoney, formatMoney } from '@/lib/format'

type GroupChartProps = {
  groups: SummaryGroup[]
}

const BAR_COLORS = {
  planned: 'oklch(0.72 0.14 145)',
  actual: 'oklch(0.67 0.18 28)',
}

export function GroupChart({ groups }: GroupChartProps) {
  const chartData = groups.map((group) => ({
    group_name: group.group_name,
    planned: group.planned_milliunits,
    actual: group.actual_milliunits,
  }))

  return (
    <div className="h-[320px] min-w-0">
      <ResponsiveContainer
        width="100%"
        height="100%"
        minHeight={320}
        initialDimension={{ width: 720, height: 320 }}
      >
        <BarChart data={chartData} barGap={8}>
          <CartesianGrid vertical={false} stroke="rgba(255,255,255,0.08)" />
          <XAxis
            dataKey="group_name"
            tick={{ fill: 'rgba(255,255,255,0.72)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
          />
          <YAxis
            tickFormatter={(value) => formatCompactMoney(value)}
            tick={{ fill: 'rgba(255,255,255,0.72)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={88}
          />
          <Tooltip
            cursor={{ fill: 'rgba(255,255,255,0.04)' }}
            contentStyle={{
              backgroundColor: 'rgba(16, 22, 36, 0.95)',
              borderColor: 'rgba(255,255,255,0.08)',
              borderRadius: '12px',
            }}
            formatter={(value: ValueType | undefined, name: NameType | undefined) => [
              formatMoney(Number(value ?? 0)),
              name === 'planned' ? 'Planned' : 'Actual',
            ]}
          />
          <Bar dataKey="planned" radius={[6, 6, 0, 0]}>
            {chartData.map((entry) => (
              <Cell key={`${entry.group_name}-planned`} fill={BAR_COLORS.planned} />
            ))}
          </Bar>
          <Bar dataKey="actual" radius={[6, 6, 0, 0]}>
            {chartData.map((entry) => (
              <Cell key={`${entry.group_name}-actual`} fill={BAR_COLORS.actual} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
