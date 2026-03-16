import type { ReactNode } from 'react'

import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { cn } from '@/lib/utils'

type MetricCardProps = {
  label: string
  value: string
  detail?: string
  tone?: 'neutral' | 'good' | 'warn'
  icon?: ReactNode
}

const TONE_STYLES = {
  neutral: 'border-border/70 bg-card/90',
  good: 'border-emerald-500/20 bg-emerald-500/10',
  warn: 'border-amber-500/20 bg-amber-500/10',
}

export function MetricCard({ label, value, detail, tone = 'neutral', icon }: MetricCardProps) {
  return (
    <Card className={cn('backdrop-blur-sm', TONE_STYLES[tone])}>
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-3">
        <CardTitle className="text-xs uppercase tracking-[0.24em] text-muted-foreground">
          {label}
        </CardTitle>
        {icon}
      </CardHeader>
      <CardContent className="space-y-1">
        <div className="font-mono text-2xl text-foreground">{value}</div>
        {detail ? <p className="text-sm text-muted-foreground">{detail}</p> : null}
      </CardContent>
    </Card>
  )
}
