import type { ReactNode } from 'react'

import { cn } from '@/lib/utils'

type MetricCardProps = {
  label: string
  value: string
  detail?: string
  tone?: 'neutral' | 'good' | 'warn'
  icon?: ReactNode
}

const TONE_STYLES = {
  neutral: 'bg-card',
  good: 'bg-emerald-500/[0.06] ring-1 ring-inset ring-emerald-500/15',
  warn: 'bg-amber-500/[0.06] ring-1 ring-inset ring-amber-500/15',
}

export function MetricCard({ label, value, detail, tone = 'neutral', icon }: MetricCardProps) {
  return (
    <div
      className={cn(
        'rounded-xl p-5 transition-colors duration-150 hover:bg-card-elevated',
        TONE_STYLES[tone],
      )}
    >
      <div className="flex items-center justify-between">
        <span className="text-label">{label}</span>
        {icon}
      </div>
      <div className="mt-3 font-mono text-2xl font-semibold tracking-tight text-foreground">
        {value}
      </div>
      {detail ? (
        <p className="mt-1.5 text-sm text-muted-foreground">{detail}</p>
      ) : null}
    </div>
  )
}
