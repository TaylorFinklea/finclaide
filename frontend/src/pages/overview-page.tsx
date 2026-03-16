import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowDownUp, RefreshCcw, ShieldCheck } from 'lucide-react'

import { MetricCard } from '@/components/metric-card'
import { StatusChip } from '@/components/status-chip'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getStatus, getSummary } from '@/lib/api'
import { formatCompactMoney, formatDay, formatMoney, formatMonthLabel, formatRunAt } from '@/lib/format'
import { useAppMonth } from '@/app/month-context'
import { GroupChart } from '@/components/group-chart'

export function OverviewPage() {
  const { month } = useAppMonth()
  const summaryQuery = useQuery({ queryKey: ['summary', month], queryFn: () => getSummary(month) })
  const statusQuery = useQuery({ queryKey: ['status'], queryFn: getStatus })

  const annualCategories = useMemo(
    () =>
      summaryQuery.data?.groups.flatMap((group) =>
        group.categories
          .filter((category) => category.due_month !== null)
          .map((category) => ({ ...category, group_name: group.group_name })),
      ) ?? [],
    [summaryQuery.data],
  )

  if (summaryQuery.isLoading || statusQuery.isLoading) {
    return <OverviewSkeleton />
  }

  const summary = summaryQuery.data
  const status = statusQuery.data
  if (!summary || !status) {
    return null
  }

  return (
    <div className="space-y-6">
      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <MetricCard
          label="Budget Import"
          value={formatRunAt(status.last_budget_import_at)}
          detail={`Sheet: ${status.budget_sheet}`}
          icon={<RefreshCcw className="h-4 w-4 text-muted-foreground" />}
        />
        <MetricCard
          label="YNAB Sync"
          value={formatRunAt(status.last_ynab_sync_at)}
          detail={
            status.last_server_knowledge !== null
              ? `Server knowledge ${status.last_server_knowledge}`
              : 'Not synced'
          }
          icon={<ArrowDownUp className="h-4 w-4 text-muted-foreground" />}
        />
        <MetricCard
          label="Reconcile"
          value={status.last_reconcile_status ?? 'Not run'}
          detail={formatRunAt(status.last_reconcile_at)}
          tone={status.last_reconcile_status === 'success' ? 'good' : 'warn'}
          icon={<ShieldCheck className="h-4 w-4 text-muted-foreground" />}
        />
        <MetricCard
          label="Mismatch Count"
          value={String(summary.mismatches.length)}
          detail={status.busy ? `Busy: ${status.current_operation}` : 'Ready'}
          tone={summary.mismatches.length ? 'warn' : 'good'}
          icon={<AlertTriangle className="h-4 w-4 text-muted-foreground" />}
        />
      </section>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card className="border-border/70 bg-card/90 backdrop-blur-sm">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Plan vs Actual by Group</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                {formatMonthLabel(summary.month)} across {summary.groups.length} groups
              </p>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <div>Planned {formatCompactMoney(summary.groups.reduce((sum, group) => sum + group.planned_milliunits, 0))}</div>
              <div>Actual {formatCompactMoney(summary.groups.reduce((sum, group) => sum + group.actual_milliunits, 0))}</div>
            </div>
          </CardHeader>
          <CardContent>
            <GroupChart groups={summary.groups} />
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle>Mismatch Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {summary.mismatches.length ? (
              summary.mismatches.map((mismatch) => (
                <div key={`${mismatch.group_name}-${mismatch.category_name}`} className="rounded-xl border border-amber-500/20 bg-amber-500/10 p-3">
                  <div className="font-medium text-foreground">
                    {mismatch.group_name} / {mismatch.category_name}
                  </div>
                  <div className="mt-1 text-sm text-muted-foreground">{mismatch.reason}</div>
                </div>
              ))
            ) : (
              <div className="rounded-xl border border-emerald-500/20 bg-emerald-500/10 p-4 text-sm text-emerald-100">
                Reconciliation is clean. All imported sheet categories have an exact YNAB match.
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_1fr]">
        <Card className="border-border/70 bg-card/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle>Annual Funding Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {annualCategories.length ? (
              annualCategories.map((category) => (
                <div
                  key={`${category.group_name}-${category.category_name}`}
                  className="grid gap-2 rounded-xl border border-border/60 bg-background/30 p-3 md:grid-cols-[1.3fr_1fr_auto]"
                >
                  <div>
                    <div className="font-medium text-foreground">
                      {category.group_name} / {category.category_name}
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      Due month {category.due_month ?? '-'} • Balance {formatMoney(category.current_balance_milliunits)}
                    </div>
                  </div>
                  <div className="font-mono text-sm text-muted-foreground">
                    Monthly target {formatMoney(category.planned_milliunits)}
                  </div>
                  <StatusChip status={category.status} />
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No annual categories available.</p>
            )}
          </CardContent>
        </Card>

        <Card className="border-border/70 bg-card/90 backdrop-blur-sm">
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {summary.recent_transactions.length ? (
              summary.recent_transactions.map((transaction) => (
                <div
                  key={transaction.id}
                  className="grid gap-2 rounded-xl border border-border/60 bg-background/30 p-3 md:grid-cols-[96px_1fr_auto]"
                >
                  <div className="font-mono text-xs text-muted-foreground">{formatDay(transaction.date)}</div>
                  <div>
                    <div className="font-medium text-foreground">{transaction.payee_name ?? 'Uncategorized payee'}</div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      {transaction.group_name ?? 'No group'} / {transaction.category_name ?? 'No category'}
                    </div>
                  </div>
                  <div className="space-y-1 text-right">
                    <div className="font-mono text-sm text-foreground">
                      {formatMoney(transaction.amount_milliunits)}
                    </div>
                    {transaction.memo ? (
                      <div className="max-w-48 text-xs text-muted-foreground">{transaction.memo}</div>
                    ) : null}
                  </div>
                </div>
              ))
            ) : (
              <p className="text-sm text-muted-foreground">No transactions synced yet.</p>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  )
}

function OverviewSkeleton() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-32 rounded-2xl" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Skeleton className="h-[420px] rounded-2xl" />
        <Skeleton className="h-[420px] rounded-2xl" />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.15fr_1fr]">
        <Skeleton className="h-[420px] rounded-2xl" />
        <Skeleton className="h-[420px] rounded-2xl" />
      </div>
    </div>
  )
}
