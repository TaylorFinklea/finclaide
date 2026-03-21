import { useMemo, useState } from 'react'

import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { LoaderCircle, RefreshCw } from 'lucide-react'
import { toast } from 'sonner'

import { useAppMonth } from '@/app/month-context'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { getErrorMessage, getStatus, getSummary, importBudget, reconcile, refreshAll, syncYnab } from '@/lib/api'
import { formatMonthLabel, formatRunAt } from '@/lib/format'

type OperationKind = 'budget-import' | 'ynab-sync' | 'reconcile' | 'refresh-all'

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
