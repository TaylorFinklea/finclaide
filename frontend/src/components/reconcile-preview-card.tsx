import { ScanSearch } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getErrorMessage, type ReconcilePreviewResponse } from '@/lib/api'

type ReconcilePreviewCardProps = {
  preview: ReconcilePreviewResponse | undefined
  isLoading: boolean
  isError: boolean
  error: unknown
  onRefresh?: () => void
  onRetryReconcile?: () => void
  retrying?: boolean
}

export function ReconcilePreviewCard({
  preview,
  isLoading,
  isError,
  error,
  onRefresh,
  onRetryReconcile,
  retrying,
}: ReconcilePreviewCardProps) {
  return (
    <Card className="border-amber-500/30 bg-amber-500/[0.05]">
      <CardHeader className="space-y-3">
        <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle className="flex items-center gap-2 text-amber-100">
              <ScanSearch className="h-4 w-4" />
              Reconcile preview
            </CardTitle>
            <p className="mt-2 text-sm text-amber-100/80">
              Read-only diff of the imported plan against current YNAB categories. No data is changed.
            </p>
          </div>
          <div className="flex gap-2">
            {onRefresh ? (
              <Button
                variant="outline"
                className="border-amber-200/30 text-amber-50 hover:bg-amber-500/10"
                onClick={onRefresh}
              >
                Refresh preview
              </Button>
            ) : null}
            {onRetryReconcile ? (
              <Button
                variant="outline"
                className="border-amber-200/30 text-amber-50 hover:bg-amber-500/10"
                disabled={retrying}
                onClick={onRetryReconcile}
              >
                {retrying ? 'Re-running…' : 'Re-run reconcile'}
              </Button>
            ) : null}
          </div>
        </div>
      </CardHeader>
      <CardContent className="space-y-4">
        {isLoading ? (
          <Skeleton className="h-32 rounded-lg" />
        ) : isError ? (
          <div className="rounded-lg bg-rose-500/[0.08] p-4 text-sm text-rose-100 ring-1 ring-inset ring-rose-500/20">
            Could not load reconcile preview: {getErrorMessage(error)}
          </div>
        ) : preview ? (
          <>
            <div className="grid gap-3 md:grid-cols-3">
              <PreviewMetric label="Exact matches" value={preview.counts.exact} tone="ok" />
              <PreviewMetric label="Missing in YNAB" value={preview.counts.missing_in_ynab} tone="warn" />
              <PreviewMetric label="Extra in YNAB" value={preview.counts.extra_in_ynab} tone="info" />
            </div>
            <PreviewList
              title="Missing in YNAB"
              subtitle="In your plan but not present in YNAB. These are the cause of reconcile failure."
              rows={preview.missing_in_ynab}
              emptyText="No missing categories. Plan rows all map to a YNAB category."
              emptyTone="ok"
            />
            <PreviewList
              title="Extra in YNAB"
              subtitle="Present in YNAB but not in your plan. Often a renamed category or a YNAB-side addition."
              rows={preview.extra_in_ynab}
              emptyText="No extra YNAB categories outside the plan."
              emptyTone="ok"
            />
          </>
        ) : null}
      </CardContent>
    </Card>
  )
}

function PreviewMetric({
  label,
  value,
  tone,
}: {
  label: string
  value: number
  tone: 'ok' | 'warn' | 'info'
}) {
  const toneStyles =
    tone === 'ok'
      ? 'border-emerald-400/30 bg-emerald-500/[0.06] text-emerald-100'
      : tone === 'warn'
        ? 'border-rose-400/30 bg-rose-500/[0.08] text-rose-100'
        : 'border-cyan-400/30 bg-cyan-500/[0.06] text-cyan-100'
  return (
    <div className={`rounded-lg p-4 ring-1 ring-inset ${toneStyles}`}>
      <div className="text-label-upper">{label}</div>
      <div className="mt-2 font-mono text-2xl font-semibold">{value}</div>
    </div>
  )
}

function PreviewList({
  title,
  subtitle,
  rows,
  emptyText,
  emptyTone,
}: {
  title: string
  subtitle: string
  rows: { group_name: string; category_name: string }[]
  emptyText: string
  emptyTone: 'ok'
}) {
  return (
    <div className="rounded-lg bg-amber-500/[0.04] p-4">
      <div className="flex items-baseline justify-between gap-3">
        <div className="text-sm font-medium text-amber-50">{title}</div>
        <div className="text-label">{rows.length}</div>
      </div>
      <p className="mt-1 text-sm text-amber-100/70">{subtitle}</p>
      {rows.length === 0 ? (
        <div
          className={`mt-3 rounded-lg p-3 text-sm ring-1 ring-inset ${
            emptyTone === 'ok'
              ? 'bg-emerald-500/[0.06] text-emerald-100 ring-emerald-500/15'
              : 'bg-muted/30 text-muted-foreground ring-border/30'
          }`}
        >
          {emptyText}
        </div>
      ) : (
        <ul className="mt-3 space-y-1.5">
          {rows.map((row) => (
            <li
              key={`${row.group_name}/${row.category_name}`}
              className="flex items-center justify-between gap-3 rounded-md bg-muted/30 px-3 py-2 text-sm"
            >
              <span className="text-foreground">
                {row.group_name} / {row.category_name}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
