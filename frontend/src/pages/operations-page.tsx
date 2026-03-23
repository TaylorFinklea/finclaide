import { useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LoaderCircle, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { useAppMonth } from '@/app/month-context'
import { StatusChip } from '@/components/status-chip'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { StatusResponse } from '@/lib/api'
import { getErrorMessage, getStatus, getSummary, importBudget, reconcile, refreshAll, syncYnab } from '@/lib/api'
import { formatMonthLabel, formatRunAt } from '@/lib/format'

type OperationKind = 'budget-import' | 'ynab-sync' | 'reconcile' | 'refresh-all'
type LatestRun = NonNullable<StatusResponse['latest_runs']>[string]

export function OperationsPage() {
  const { month } = useAppMonth()
  const queryClient = useQueryClient()
  const [latestPayload, setLatestPayload] = useState<Record<string, unknown> | null>(null)
  const statusQuery = useQuery({ queryKey: ['status'], queryFn: getStatus })
  const summaryQuery = useQuery({ queryKey: ['summary', month], queryFn: () => getSummary(month) })

  const invalidateAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['status'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
      queryClient.invalidateQueries({ queryKey: ['transactions'] }),
    ])
  }

  const importMutation = useMutation({
    mutationKey: ['budget-import'],
    mutationFn: importBudget,
    onSuccess: async (payload) => {
      setLatestPayload(payload)
      toast.success(`${labelFor('budget-import')} completed`)
      await invalidateAll()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error))
    },
  })
  const syncMutation = useMutation({
    mutationKey: ['ynab-sync'],
    mutationFn: syncYnab,
    onSuccess: async (payload) => {
      setLatestPayload(payload)
      toast.success(`${labelFor('ynab-sync')} completed`)
      await invalidateAll()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error))
    },
  })
  const reconcileMutation = useMutation({
    mutationKey: ['reconcile'],
    mutationFn: reconcile,
    onSuccess: async (payload) => {
      setLatestPayload(payload)
      toast.success(`${labelFor('reconcile')} completed`)
      await invalidateAll()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error))
    },
  })
  const refreshMutation = useMutation({
    mutationKey: ['refresh-all', month],
    mutationFn: () => refreshAll(month),
    onSuccess: async (payload) => {
      setLatestPayload(payload)
      toast.success(`${labelFor('refresh-all')} completed`)
      await invalidateAll()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error))
    },
  })

  const busy = importMutation.isPending || syncMutation.isPending || reconcileMutation.isPending || refreshMutation.isPending
  const latestRuns = useMemo(() => statusQuery.data?.latest_runs ?? {}, [statusQuery.data])

  return (
    <div className="space-y-6">
      <Card className="border-border/40 bg-card">
        <CardHeader>
          <CardTitle>Operations</CardTitle>
          <p className="text-sm text-muted-foreground">
            Trigger data refreshes and reconciliation for {formatMonthLabel(month)}.
          </p>
        </CardHeader>
        <CardContent className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <OperationButton
            label="Import Budget"
            description="Reload the current workbook export into SQLite."
            disabled={busy}
            pending={importMutation.isPending}
            onClick={() => importMutation.mutate()}
          />
          <OperationButton
            label="Sync YNAB"
            description="Pull new accounts, categories, and transaction deltas."
            disabled={busy}
            pending={syncMutation.isPending}
            onClick={() => syncMutation.mutate()}
          />
          <OperationButton
            label="Reconcile"
            description="Verify imported sheet categories still match YNAB exactly."
            disabled={busy}
            pending={reconcileMutation.isPending}
            onClick={() => reconcileMutation.mutate()}
          />
          <OperationButton
            label="Refresh All"
            description="Run import, sync, and reconcile sequentially."
            disabled={busy}
            pending={refreshMutation.isPending}
            onClick={() => refreshMutation.mutate()}
          />
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.1fr_1fr]">
        <Card className="border-border/40 bg-card">
          <CardHeader>
            <CardTitle>Latest Runs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {Object.entries(latestRuns).length ? (
              Object.entries(latestRuns).map(([source, details]) => (
                <div key={source} className="rounded-lg bg-muted/30 p-4">
                  <div className="text-label-upper">{source}</div>
                  <div className="mt-2 flex items-center justify-between gap-4">
                    <div className="font-medium text-foreground">{details.status}</div>
                    <div className="text-sm text-muted-foreground">{formatRunAt(details.finished_at)}</div>
                  </div>
                  <div className="mt-2 text-sm text-muted-foreground">
                    {describeRun(source, details)}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No operation history yet.</p>
            )}
          </CardContent>
        </Card>

        <Card className="border-border/40 bg-card">
          <CardHeader>
            <CardTitle>Current Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4 text-sm text-muted-foreground">
            <div className="rounded-lg bg-muted/30 p-4">
              <div className="text-label-upper">Busy State</div>
              <div className="mt-2 text-foreground">
                {statusQuery.data?.busy
                  ? `Running ${statusQuery.data.current_operation ?? 'operation'}`
                  : 'Idle'}
              </div>
            </div>
            <StatusDetailCard
              label="Plan Data"
              value={describeFreshness(statusQuery.data?.plan_freshness.status)}
              detail={`Last import ${formatRunAt(statusQuery.data?.plan_freshness.last_updated_at)}`}
            />
            <StatusDetailCard
              label="YNAB Data"
              value={describeFreshness(statusQuery.data?.actuals_freshness.status)}
              detail={describeActualsFreshness(statusQuery.data)}
            />
            <div className="rounded-lg bg-muted/30 p-4">
              <div className="flex items-center justify-between gap-3">
                <div className="text-label-upper">Scheduled Refresh</div>
                <StatusChip status={describeScheduleStatus(statusQuery.data)} />
              </div>
              <div className="mt-2 text-foreground">{describeScheduleHeadline(statusQuery.data)}</div>
              <div className="mt-1 text-sm text-muted-foreground">{describeScheduleDetail(statusQuery.data)}</div>
            </div>
            <div className="rounded-lg bg-muted/30 p-4">
              <div className="text-label-upper">Mismatch Count</div>
              <div className="mt-2 text-foreground">{summaryQuery.data?.mismatches.length ?? 0}</div>
            </div>
            <div className="rounded-lg bg-muted/30 p-4">
              <div className="text-label-upper">Budget Import ID</div>
              <div className="mt-2 font-mono text-foreground">
                {statusQuery.data?.last_budget_import_id ?? '—'}
              </div>
            </div>
            <StatusDetailCard
              label="Plan Source"
              value={basename(statusQuery.data?.plan_provenance.workbook_path ?? statusQuery.data?.budget_sheet)}
              detail={`Sheet ${statusQuery.data?.plan_provenance.sheet_name ?? '—'}`}
            />
          </CardContent>
        </Card>
      </div>

      <Card className="border-border/40 bg-card">
        <CardHeader>
          <CardTitle>Latest Operation Payload</CardTitle>
        </CardHeader>
        <CardContent>
          <pre className="overflow-x-auto rounded-lg bg-muted/25 p-4 font-mono text-xs text-slate-100 ring-1 ring-inset ring-border/30">
            {JSON.stringify(latestPayload ?? { message: 'No operation triggered in this session.' }, null, 2)}
          </pre>
        </CardContent>
      </Card>
    </div>
  )
}

function OperationButton({
  label,
  description,
  pending,
  disabled,
  onClick,
}: {
  label: string
  description: string
  pending: boolean
  disabled: boolean
  onClick: () => void
}) {
  return (
    <div className="rounded-xl bg-muted/30 p-5 transition-colors duration-150 hover:bg-muted/50">
      <div className="text-base font-medium text-foreground">{label}</div>
      <p className="mt-2 min-h-12 text-sm text-muted-foreground">{description}</p>
      <Button className="mt-4 w-full" disabled={disabled} onClick={onClick}>
        {pending ? <LoaderCircle className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
        {label}
      </Button>
    </div>
  )
}

function labelFor(kind: OperationKind) {
  switch (kind) {
    case 'budget-import':
      return 'Budget import'
    case 'ynab-sync':
      return 'YNAB sync'
    case 'reconcile':
      return 'Reconcile'
    case 'refresh-all':
      return 'Refresh all'
  }
}

function describeRun(source: string, run: LatestRun) {
  if ('error' in run.details && typeof run.details.error === 'string') {
    return run.details.error
  }
  if (source === 'budget_import' && typeof run.details.row_count === 'number') {
    return `Imported ${run.details.row_count} planned rows`
  }
  if (source === 'ynab_sync' && typeof run.details.transaction_count === 'number') {
    return `Synced ${run.details.transaction_count} transactions`
  }
  if (source === 'reconcile' && typeof run.details.mismatch_count === 'number') {
    return run.details.mismatch_count === 0
      ? 'No mismatches found'
      : `${run.details.mismatch_count} mismatches detected`
  }
  if (source === 'scheduled_refresh') {
    if ('reconcile_error' in run.details && typeof run.details.reconcile_error === 'string') {
      return run.details.reconcile_error
    }
    if (
      'budget_import' in run.details &&
      typeof run.details.budget_import === 'object' &&
      run.details.budget_import !== null &&
      'row_count' in run.details.budget_import &&
      typeof run.details.budget_import.row_count === 'number'
    ) {
      return `Imported ${run.details.budget_import.row_count} planned rows in scheduled refresh`
    }
  }
  return 'No additional details'
}

function describeFreshness(status: string | undefined) {
  switch (status) {
    case 'fresh':
      return 'Fresh'
    case 'warning':
      return 'Warning'
    case 'critical':
      return 'Critical'
    case 'missing':
      return 'Missing'
    default:
      return 'Unknown'
  }
}

function describeActualsFreshness(status: StatusResponse | undefined) {
  const freshness = status?.actuals_freshness
  if (!freshness) {
    return 'No sync state available'
  }
  if (freshness.status === 'missing') {
    return 'YNAB has not been synced yet'
  }
  if (typeof freshness.hours_stale === 'number') {
    return `${freshness.hours_stale.toFixed(1)} hours stale`
  }
  return `Last sync ${formatRunAt(freshness.last_updated_at)}`
}

function describeScheduleStatus(status: StatusResponse | undefined) {
  const schedule = status?.scheduled_refresh
  if (!schedule?.enabled) {
    return 'missing'
  }
  return schedule.last_status ?? 'warning'
}

function describeScheduleHeadline(status: StatusResponse | undefined) {
  const schedule = status?.scheduled_refresh
  if (!schedule?.enabled) {
    return 'Automatic refresh is disabled'
  }
  if (schedule.last_status === 'success') {
    return `Last run succeeded ${formatRunAt(schedule.last_finished_at)}`
  }
  if (schedule.last_status === 'failed') {
    return `Last run failed ${formatRunAt(schedule.last_finished_at)}`
  }
  if (schedule.last_status === 'skipped') {
    return `Last run skipped ${formatRunAt(schedule.last_finished_at)}`
  }
  return `Next run ${formatRunAt(schedule.next_run_at)}`
}

function describeScheduleDetail(status: StatusResponse | undefined) {
  const schedule = status?.scheduled_refresh
  if (!schedule?.enabled) {
    return 'Set FINCLAIDE_SCHEDULED_REFRESH_ENABLED to turn on automatic import, sync, and reconcile.'
  }
  if (schedule.last_error) {
    return schedule.last_error
  }
  if (typeof schedule.interval_minutes === 'number') {
    return `Runs every ${schedule.interval_minutes} minutes. Next run ${formatRunAt(schedule.next_run_at)}.`
  }
  return 'No scheduler details available'
}

function StatusDetailCard({ label, value, detail }: { label: string; value: string; detail: string }) {
  return (
    <div className="rounded-lg bg-muted/30 p-4">
      <div className="text-label-upper">{label}</div>
      <div className="mt-2 text-foreground">{value}</div>
      <div className="mt-1 text-sm text-muted-foreground">{detail}</div>
    </div>
  )
}

function basename(value: string | undefined) {
  if (!value) {
    return 'Budget.xlsx'
  }
  const parts = value.split(/[\\/]/)
  return parts[parts.length - 1] || value
}
