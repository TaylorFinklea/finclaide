import { Bar, BarChart, CartesianGrid, Legend, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import type { NameType, ValueType } from 'recharts/types/component/DefaultTooltipContent'

import type { SummaryGroup } from '@/lib/api'
import { formatCompactMoney, formatMoney } from '@/lib/format'

type GroupChartProps = {
  groups: SummaryGroup[]
}

const BAR_COLORS = {
  planned: 'oklch(0.68 0.12 245)',
  actual: 'oklch(0.72 0.14 160)',
}

export function GroupChart({ groups }: GroupChartProps) {
  const chartData = groups.map((group) => ({
    group_name: group.group_name,
    planned: group.planned_milliunits,
    actual: group.actual_milliunits,
  }))

  return (
    <div className="h-[420px] min-w-0">
      <ResponsiveContainer
        width="100%"
        height="100%"
        minHeight={420}
        initialDimension={{ width: 720, height: 420 }}
      >
        <BarChart data={chartData} barGap={4} barCategoryGap="20%">
          <CartesianGrid vertical={false} stroke="oklch(0.25 0.015 250 / 0.5)" strokeDasharray="3 3" />
          <XAxis
            dataKey="group_name"
            tick={{ fill: 'oklch(0.65 0.02 250)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            dy={8}
          />
          <YAxis
            tickFormatter={(value) => formatCompactMoney(value)}
            tick={{ fill: 'oklch(0.65 0.02 250)', fontSize: 12 }}
            axisLine={false}
            tickLine={false}
            width={80}
          />
          <Tooltip
            cursor={{ fill: 'oklch(0.20 0.015 250 / 0.6)' }}
            contentStyle={{
              backgroundColor: 'oklch(0.16 0.015 250)',
              borderColor: 'oklch(0.28 0.015 250)',
              borderRadius: '8px',
              padding: '12px 16px',
              boxShadow: '0 8px 24px oklch(0 0 0 / 0.4)',
            }}
            itemStyle={{ color: 'oklch(0.88 0.01 250)', fontSize: '13px' }}
            labelStyle={{ color: 'oklch(0.65 0.02 250)', fontSize: '11px', marginBottom: '4px' }}
            formatter={(value: ValueType | undefined, name: NameType | undefined) => [
              formatMoney(Number(value ?? 0)),
              name === 'planned' ? 'Planned' : 'Actual',
            ]}
          />
          <Legend
            wrapperStyle={{ paddingTop: '16px' }}
            formatter={(value) => (
              <span style={{ color: 'oklch(0.75 0.02 250)', fontSize: '12px' }}>
                {value === 'planned' ? 'Planned' : 'Actual'}
              </span>
            )}
          />
          <Bar dataKey="planned" radius={[4, 4, 0, 0]} fill={BAR_COLORS.planned} />
          <Bar dataKey="actual" radius={[4, 4, 0, 0]} fill={BAR_COLORS.actual} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
