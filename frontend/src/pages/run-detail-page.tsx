import { useQuery } from '@tanstack/react-query'
import { ArrowLeft } from 'lucide-react'
import { Link, useParams } from 'react-router-dom'

import { StatusChip } from '@/components/status-chip'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { ApiError, getErrorMessage, getRun, type RunEntry } from '@/lib/api'
import { formatRunAt } from '@/lib/format'
import { withBasePath } from '@/lib/runtime'

const SOURCE_LABEL: Record<string, string> = {
  budget_import: 'Budget Import',
  ynab_sync: 'YNAB Sync',
  reconcile: 'Reconcile',
  scheduled_refresh: 'Scheduled Refresh',
}

export function RunDetailPage() {
  const params = useParams<{ id: string }>()
  const runId = Number.parseInt(params.id ?? '', 10)
  const isValidId = Number.isFinite(runId) && runId > 0

  const runQuery = useQuery({
    queryKey: ['run', runId],
    queryFn: () => getRun(runId),
    enabled: isValidId,
    retry: false,
  })

  if (!isValidId) {
    return <RunDetailFallback heading="Invalid run id" body="The run id in the URL is not a number." />
  }
  if (runQuery.isLoading) {
    return (
      <div className="space-y-6">
        <BackToOperations />
        <Skeleton className="h-[480px] rounded-2xl" />
      </div>
    )
  }
  if (runQuery.isError) {
    const error = runQuery.error
    if (error instanceof ApiError && error.status === 404) {
      return <RunDetailFallback heading="Run not found" body={`Run #${runId} does not exist.`} />
    }
    return (
      <RunDetailFallback heading="Could not load run" body={getErrorMessage(runQuery.error)} />
    )
  }
  const run = runQuery.data
  if (!run) {
    return <RunDetailFallback heading="Run not found" body={`Run #${runId} returned no data.`} />
  }

  return (
    <div className="space-y-6">
      <BackToOperations />

      <Card className="border-border/40 bg-card">
        <CardHeader className="space-y-3">
          <div className="flex flex-col gap-3 xl:flex-row xl:items-center xl:justify-between">
            <div>
              <div className="text-label">Run #{run.id}</div>
              <CardTitle className="mt-1">{SOURCE_LABEL[run.source] ?? run.source}</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                Started {formatRunAt(run.started_at)} · Finished {formatRunAt(run.finished_at)}
              </p>
            </div>
            <StatusChip status={run.status} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <RunOutcomeBlock run={run} />
          <RunDetailsBlock run={run} />
        </CardContent>
      </Card>
    </div>
  )
}

function RunOutcomeBlock({ run }: { run: RunEntry }) {
  const details = run.details ?? {}
  if (run.status === 'failed') {
    const message =
      (typeof details.error === 'string' && details.error) ||
      (typeof details.reconcile_error === 'string' && details.reconcile_error) ||
      'Run failed without a captured error message.'
    return (
      <div className="rounded-lg bg-rose-500/[0.08] p-4 ring-1 ring-inset ring-rose-500/20">
        <div className="text-label-upper text-rose-100">Failure</div>
        <p className="mt-2 text-sm text-rose-50">{message}</p>
      </div>
    )
  }
  if (run.status === 'skipped') {
    const message = typeof details.error === 'string' ? details.error : 'Operation was skipped.'
    return (
      <div className="rounded-lg bg-amber-500/[0.08] p-4 ring-1 ring-inset ring-amber-500/20">
        <div className="text-label-upper text-amber-100">Skipped</div>
        <p className="mt-2 text-sm text-amber-50">{message}</p>
      </div>
    )
  }
  return (
    <div className="rounded-lg bg-emerald-500/[0.06] p-4 ring-1 ring-inset ring-emerald-500/15">
      <div className="text-label-upper text-emerald-100">Succeeded</div>
      <p className="mt-2 text-sm text-emerald-50">{summarizeSuccess(run)}</p>
    </div>
  )
}

function summarizeSuccess(run: RunEntry): string {
  const details = run.details ?? {}
  if (run.source === 'budget_import' && typeof details.row_count === 'number') {
    return `Imported ${details.row_count} planned rows.`
  }
  if (run.source === 'ynab_sync' && typeof details.transaction_count === 'number') {
    return `Synced ${details.transaction_count} transactions.`
  }
  if (run.source === 'reconcile' && typeof details.mismatch_count === 'number') {
    return details.mismatch_count === 0
      ? 'Reconciliation passed with no mismatches.'
      : `Reconciliation flagged ${details.mismatch_count} mismatches.`
  }
  if (run.source === 'scheduled_refresh') {
    return 'Scheduled refresh completed.'
  }
  return 'Run completed.'
}

function RunDetailsBlock({ run }: { run: RunEntry }) {
  const entries = Object.entries(run.details ?? {})
  if (entries.length === 0) {
    return <p className="text-sm text-muted-foreground">No additional details captured for this run.</p>
  }
  return (
    <div className="space-y-3">
      <div className="text-label-upper">Details payload</div>
      <pre
        className="overflow-x-auto rounded-lg bg-muted/25 p-4 font-mono text-xs text-slate-100 ring-1 ring-inset ring-border/30"
        aria-label="Raw details payload"
      >
        {JSON.stringify(run.details, null, 2)}
      </pre>
    </div>
  )
}

function BackToOperations() {
  return (
    <Button asChild variant="outline" className="w-fit">
      <Link to={withBasePath('/operations')}>
        <ArrowLeft className="h-4 w-4" />
        Back to Operations
      </Link>
    </Button>
  )
}

function RunDetailFallback({ heading, body }: { heading: string; body: string }) {
  return (
    <div className="space-y-6">
      <BackToOperations />
      <Card className="border-border/40 bg-card">
        <CardHeader>
          <CardTitle>{heading}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm text-muted-foreground">{body}</p>
        </CardContent>
      </Card>
    </div>
  )
}
