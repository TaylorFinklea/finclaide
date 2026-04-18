import { AlertTriangle } from 'lucide-react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { withBasePath } from '@/lib/runtime'
import type { StatusResponse } from '@/lib/api'
import { formatRunAt } from '@/lib/format'

type LatestRun = NonNullable<StatusResponse['latest_runs']>[string]

type FailedRun = LatestRun & { source: string; runId: number | null }

const SOURCE_LABEL: Record<string, string> = {
  budget_import: 'Budget Import',
  ynab_sync: 'YNAB Sync',
  reconcile: 'Reconcile',
  scheduled_refresh: 'Scheduled Refresh',
}

function describeFailure(run: LatestRun): string {
  const details = run.details ?? {}
  if (typeof details.error === 'string') {
    return details.error
  }
  if (typeof details.reconcile_error === 'string') {
    return details.reconcile_error
  }
  if (typeof details.mismatch_count === 'number' && details.mismatch_count > 0) {
    return `${details.mismatch_count} reconciliation mismatches.`
  }
  return 'No detail available — open the run for full payload.'
}

function gatherFailures(status: StatusResponse): FailedRun[] {
  const latest = status.latest_runs ?? {}
  const failures: FailedRun[] = []
  for (const [source, run] of Object.entries(latest)) {
    if (run.status === 'failed') {
      const runId = typeof run.id === 'number' ? run.id : null
      failures.push({ ...run, source, runId })
    }
  }
  failures.sort((a, b) => (b.finished_at ?? '').localeCompare(a.finished_at ?? ''))
  return failures
}

type FailureCauseCardProps = {
  status: StatusResponse | undefined
  onRetry?: (source: string) => void
  retrying?: Record<string, boolean>
}

export function FailureCauseCard({ status, onRetry, retrying }: FailureCauseCardProps) {
  if (!status) {
    return null
  }
  const failures = gatherFailures(status)
  if (failures.length === 0) {
    return null
  }

  return (
    <Card
      className="border-rose-500/30 bg-rose-500/[0.06]"
      aria-label="Failure cause for the most recent operation runs"
    >
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-rose-100">
          <AlertTriangle className="h-4 w-4" />
          Failure cause
        </CardTitle>
        <p className="text-sm text-rose-100/80">
          The latest run of these operations failed. Open the run for the full payload, or retry once the
          underlying issue is fixed.
        </p>
      </CardHeader>
      <CardContent className="space-y-3">
        {failures.map((failure) => (
          <div
            key={failure.source}
            className="rounded-lg bg-rose-500/[0.08] p-4 ring-1 ring-inset ring-rose-500/20"
          >
            <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
              <div>
                <div className="text-sm font-medium text-rose-50">
                  {SOURCE_LABEL[failure.source] ?? failure.source}
                </div>
                <div className="mt-1 text-xs text-rose-100/70">
                  Failed {formatRunAt(failure.finished_at)}
                </div>
                <div className="mt-2 text-sm text-rose-50/90">{describeFailure(failure)}</div>
              </div>
              <div className="flex gap-2">
                {failure.runId !== null ? (
                  <Button asChild variant="outline" className="border-rose-200/30 text-rose-50 hover:bg-rose-500/10">
                    <Link to={withBasePath(`/operations/runs/${failure.runId}`)}>Open run</Link>
                  </Button>
                ) : null}
                {onRetry ? (
                  <Button
                    variant="outline"
                    className="border-rose-200/30 text-rose-50 hover:bg-rose-500/10"
                    disabled={retrying?.[failure.source] === true}
                    onClick={() => onRetry(failure.source)}
                  >
                    {retrying?.[failure.source] ? 'Retrying…' : 'Retry'}
                  </Button>
                ) : null}
              </div>
            </div>
          </div>
        ))}
      </CardContent>
    </Card>
  )
}

export function hasFailures(status: StatusResponse | undefined): boolean {
  if (!status) return false
  return gatherFailures(status).length > 0
}
