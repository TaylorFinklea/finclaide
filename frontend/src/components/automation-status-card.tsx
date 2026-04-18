import { CalendarClock, PauseCircle } from 'lucide-react'

import { StatusChip } from '@/components/status-chip'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { StatusResponse } from '@/lib/api'
import { formatRunAt } from '@/lib/format'

type AutomationStatusCardProps = {
  status: StatusResponse | undefined
}

export function AutomationStatusCard({ status }: AutomationStatusCardProps) {
  if (!status) return null
  const schedule = status.scheduled_refresh

  if (!schedule.enabled) {
    return (
      <Card className="border-border/40 bg-card">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <PauseCircle className="h-4 w-4 text-muted-foreground" />
            Scheduled refresh — disabled
          </CardTitle>
          <p className="mt-2 text-sm text-muted-foreground">
            Set <code className="font-mono text-xs">FINCLAIDE_SCHEDULED_REFRESH_ENABLED=true</code> to run import,
            sync, and reconcile automatically.
          </p>
        </CardHeader>
      </Card>
    )
  }

  const lastStatus = schedule.last_status ?? 'unknown'
  const tone = headerTone(lastStatus)

  return (
    <Card className={`border bg-card ${tone}`}>
      <CardHeader>
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2">
              <CalendarClock className="h-4 w-4 text-muted-foreground" />
              Scheduled refresh
            </CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              Runs every {schedule.interval_minutes ?? '—'} minutes. Last status drives the chip below.
            </p>
          </div>
          <StatusChip status={lastStatus} />
        </div>
      </CardHeader>
      <CardContent className="grid gap-3 md:grid-cols-3">
        <Field
          label="Next run"
          value={formatRunAt(schedule.next_run_at)}
          detail={
            schedule.next_run_at
              ? `In ${formatRelativeMinutes(schedule.next_run_at)}`
              : 'No run scheduled'
          }
        />
        <Field
          label="Last finished"
          value={formatRunAt(schedule.last_finished_at)}
          detail={
            schedule.last_started_at
              ? `Started ${formatRunAt(schedule.last_started_at)}`
              : 'Never run yet'
          }
        />
        <Field
          label="Last status"
          value={describeLastStatus(lastStatus)}
          detail={schedule.last_error ?? 'No error reported'}
        />
      </CardContent>
    </Card>
  )
}

function Field({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg bg-muted/30 p-4">
      <div className="text-label-upper">{label}</div>
      <div className="mt-2 text-foreground">{value}</div>
      <div className="mt-1 text-sm text-muted-foreground">{detail}</div>
    </div>
  )
}

function headerTone(lastStatus: string): string {
  if (lastStatus === 'failed') return 'border-rose-500/30'
  if (lastStatus === 'skipped') return 'border-amber-500/30'
  if (lastStatus === 'success') return 'border-emerald-500/30'
  return 'border-border/40'
}

function describeLastStatus(lastStatus: string): string {
  switch (lastStatus) {
    case 'success':
      return 'Succeeded'
    case 'failed':
      return 'Failed'
    case 'skipped':
      return 'Skipped (operation already running)'
    case 'unknown':
      return 'No run history yet'
    default:
      return lastStatus
  }
}

function formatRelativeMinutes(isoTimestamp: string): string {
  const target = new Date(isoTimestamp).getTime()
  const now = Date.now()
  const diffMinutes = Math.round((target - now) / 60_000)
  if (diffMinutes < 0) {
    return `${Math.abs(diffMinutes)} min overdue`
  }
  if (diffMinutes < 1) {
    return 'less than a minute'
  }
  if (diffMinutes < 60) {
    return `${diffMinutes} min`
  }
  const hours = Math.round(diffMinutes / 60)
  return `${hours}h`
}
