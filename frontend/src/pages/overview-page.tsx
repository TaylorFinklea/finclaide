import { useMemo } from 'react'

import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, ArrowDownUp, RefreshCcw, ShieldCheck } from 'lucide-react'

import { MetricCard } from '@/components/metric-card'
import { StatusChip } from '@/components/status-chip'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { getStatus, getSummary, getWeeklyReview, type ReviewItem } from '@/lib/api'
import { formatCompactMoney, formatDay, formatMoney, formatMonthLabel, formatRunAt } from '@/lib/format'
import { useAppMonth } from '@/app/month-context'
import { GroupChart } from '@/components/group-chart'

export function OverviewPage() {
  const { month } = useAppMonth()
  const summaryQuery = useQuery({ queryKey: ['summary', month], queryFn: () => getSummary(month) })
  const statusQuery = useQuery({ queryKey: ['status'], queryFn: getStatus })
  const reviewQuery = useQuery({ queryKey: ['review', month], queryFn: () => getWeeklyReview(month) })

  const annualCategories = useMemo(
    () =>
      summaryQuery.data?.groups.flatMap((group) =>
        group.categories
          .filter((category) => category.due_month !== null)
          .map((category) => ({ ...category, group_name: group.group_name })),
      ) ?? [],
    [summaryQuery.data],
  )

  if (summaryQuery.isLoading || statusQuery.isLoading || reviewQuery.isLoading) {
    return <OverviewSkeleton />
  }

  const summary = summaryQuery.data
  const status = statusQuery.data
  const review = reviewQuery.data
  if (!summary || !status || !review) {
    return null
  }

  const priorityItems =
    review.blockers.length > 0
      ? review.blockers.slice(0, 3)
      : [...review.overages, ...review.changes, ...review.anomalies].slice(0, 3)
  const attentionItems = [...review.blockers, ...review.overages, ...review.anomalies].slice(0, 3)
  const actionItems = review.recommendations.slice(0, 3)

  return (
    <div className="space-y-8">
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

      <Card className="border-border/40 bg-card">
        <CardHeader className="space-y-4">
          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
            <div>
              <CardTitle>Weekly Review</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                {review.headline}
              </p>
            </div>
            <div className="flex items-center gap-3">
              <StatusChip status={review.overall_status} />
              <div className="text-right text-sm text-muted-foreground">
                <div>{review.supporting_metrics.blocker_count} blockers</div>
                <div>{review.supporting_metrics.recommendation_count} suggested actions</div>
              </div>
            </div>
          </div>

          {priorityItems.length ? (
            <div className="grid gap-3 xl:grid-cols-3">
              {priorityItems.map((item) => (
                <div
                  key={`${item.kind}-${item.group_name ?? 'none'}-${item.category_name ?? 'none'}-${item.title}`}
                  className="rounded-lg bg-muted/30 p-4"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="text-sm font-medium text-foreground">{item.title}</div>
                    <StatusChip status={item.severity} />
                  </div>
                  <p className="mt-2 text-sm text-muted-foreground">{item.why_it_matters}</p>
                </div>
              ))}
            </div>
          ) : null}

          {review.blockers.length ? (
            <div className="rounded-lg bg-rose-500/[0.08] p-4 ring-1 ring-inset ring-rose-500/20">
              <div className="flex items-center gap-2 text-sm font-medium text-rose-100">
                <AlertTriangle className="h-4 w-4" />
                Review confidence is reduced until these blockers are resolved.
              </div>
              <div className="mt-3 space-y-2">
                {review.blockers.slice(0, 3).map((item) => (
                  <div key={item.title} className="text-sm text-rose-50/90">
                    <span className="font-medium">{item.title}</span>
                    <span className="text-rose-100/70"> — {item.recommended_action ?? item.why_it_matters}</span>
                  </div>
                ))}
              </div>
            </div>
          ) : null}
        </CardHeader>
        <CardContent className="grid gap-4 xl:grid-cols-3">
          <ReviewColumn
            title="What Changed"
            subtitle="Month-over-month shifts worth sanity-checking."
            items={review.changes}
            empty="No material month-over-month changes crossed the review thresholds."
          />
          <ReviewColumn
            title="Needs Attention"
            subtitle="Current blockers, overages, and unusual spend."
            items={attentionItems}
            empty="Nothing urgent is crowding the current review window."
          />
          <ReviewColumn
            title="Recommended Actions"
            subtitle="Suggested next steps grounded in the latest plan and actuals."
            items={actionItems}
            empty="No budget changes are being recommended right now."
            showAction
          />
        </CardContent>
      </Card>

      <Card className="border-border/40 bg-card">
        <CardHeader className="flex flex-row items-center justify-between gap-4">
          <div>
            <CardTitle>Automation Health</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              Scheduled import, YNAB sync, and reconcile state.
            </p>
          </div>
          <StatusChip status={automationHealthStatus(status)} />
        </CardHeader>
        <CardContent className="grid gap-4 md:grid-cols-3">
          <div className="rounded-lg bg-muted/30 p-4">
            <div className="text-label-upper">Scheduler</div>
            <div className="mt-2 text-foreground">{automationHealthHeadline(status)}</div>
            <div className="mt-1 text-sm text-muted-foreground">{automationHealthDetail(status)}</div>
          </div>
          <div className="rounded-lg bg-muted/30 p-4">
            <div className="text-label-upper">Plan Freshness</div>
            <div className="mt-2 text-foreground">{status.plan_freshness.status}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              Last import {formatRunAt(status.plan_freshness.last_updated_at)}
            </div>
          </div>
          <div className="rounded-lg bg-muted/30 p-4">
            <div className="text-label-upper">YNAB Freshness</div>
            <div className="mt-2 text-foreground">{status.actuals_freshness.status}</div>
            <div className="mt-1 text-sm text-muted-foreground">
              Last sync {formatRunAt(status.actuals_freshness.last_updated_at)}
            </div>
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Card className="border-border/40 bg-card">
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

        <div className="space-y-6">
          <Card className="border-border/40 bg-card">
            <CardHeader className="space-y-3">
              <div className="flex items-center justify-between gap-3">
                <CardTitle>Overage Watch</CardTitle>
                <div className="text-label">
                  {summary.overage_watch.categories.length} watched
                </div>
              </div>
              <p className="text-sm text-muted-foreground">
                {formatOverageWatchWindow(
                  summary.overage_watch.analysis_start_month,
                  summary.overage_watch.analysis_end_month,
                )}
              </p>
            </CardHeader>
            <CardContent className="space-y-3">
              {summary.overage_watch.categories.length ? (
                summary.overage_watch.categories.map((category) => (
                  <div
                    key={`${category.group_name}-${category.category_name}`}
                    className="grid gap-3 rounded-lg bg-muted/30 p-3"
                  >
                    <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="font-medium text-foreground">
                          {category.group_name} / {category.category_name}
                        </div>
                        <div className="mt-1 text-sm text-muted-foreground">
                          {category.watch_kind === 'unplanned' ? 'Needs a sinking fund' : 'Current target is lagging actual run rate'}
                        </div>
                      </div>
                      <div className="flex items-center gap-2">
                        <StatusChip status={category.watch_level} />
                        <div className="text-label">
                          {category.over_months}/{category.analysis_month_count} months over
                        </div>
                      </div>
                    </div>

                    <div className="grid gap-3 text-sm text-muted-foreground md:grid-cols-3">
                      <div className="rounded-lg bg-muted/30 p-3">
                        <div className="text-label-upper">Target</div>
                        <div className="mt-2 font-mono text-base text-foreground">
                          {formatMoney(category.planned_milliunits)}
                        </div>
                        <div className="mt-1 font-mono text-xs">
                          Suggested floor {formatMoney(category.suggested_monthly_milliunits)}
                        </div>
                      </div>
                      <div className="rounded-lg bg-muted/30 p-3">
                        <div className="text-label-upper">Historical Run Rate</div>
                        <div className="mt-2 font-mono text-base text-foreground">
                          {formatMoney(category.average_spend_milliunits)}
                        </div>
                        <div className="mt-1 font-mono text-xs">
                          Active avg {formatMoney(category.active_average_spend_milliunits)}
                        </div>
                      </div>
                      <div className="rounded-lg bg-muted/30 p-3">
                        <div className="text-label-upper">Exposure</div>
                        <div className="mt-2 font-mono text-base text-foreground">
                          {formatMoney(category.shortfall_milliunits)}
                        </div>
                        <div className="mt-1 font-mono text-xs">
                          Peak {formatMoney(category.max_spend_milliunits)} in {formatMonthLabel(category.peak_month)}
                        </div>
                      </div>
                    </div>

                    <div className="flex flex-col gap-2 text-xs text-muted-foreground md:flex-row md:items-center md:justify-between">
                      <div>Current balance {formatMoney(category.current_balance_milliunits)}</div>
                      <div>{category.active_months} active months in the watch window</div>
                    </div>
                  </div>
                ))
              ) : (
                <div className="rounded-lg bg-emerald-500/[0.06] p-4 text-sm text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
                  No repeat overages are breaching the watch thresholds in the completed-month history.
                </div>
              )}
            </CardContent>
          </Card>

          <Card className="border-border/40 bg-card">
            <CardHeader>
              <CardTitle>Mismatch Status</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              {summary.mismatches.length ? (
                summary.mismatches.map((mismatch) => (
                  <div key={`${mismatch.group_name}-${mismatch.category_name}`} className="rounded-lg bg-amber-500/[0.06] p-3 ring-1 ring-inset ring-amber-500/15">
                    <div className="font-medium text-foreground">
                      {mismatch.group_name} / {mismatch.category_name}
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">{mismatch.reason}</div>
                  </div>
                ))
              ) : (
                <div className="rounded-lg bg-emerald-500/[0.06] p-4 text-sm text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
                  Reconciliation is clean. All imported sheet categories have an exact YNAB match.
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>

      <div className="grid gap-6 xl:grid-cols-[1.15fr_1fr]">
        <Card className="border-border/40 bg-card">
          <CardHeader>
            <CardTitle>Annual Funding Status</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {annualCategories.length ? (
              annualCategories.map((category) => (
                <div
                  key={`${category.group_name}-${category.category_name}`}
                  className="grid gap-2 rounded-lg p-3 transition-colors duration-100 hover:bg-muted/30 md:grid-cols-[1.3fr_1fr_auto]"
                >
                  <div>
                    <div className="font-medium text-foreground">
                      {category.group_name} / {category.category_name}
                    </div>
                    <div className="mt-1 text-sm text-muted-foreground">
                      Due month {category.due_month ?? '-'} &middot; Balance {formatMoney(category.current_balance_milliunits)}
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

        <Card className="border-border/40 bg-card">
          <CardHeader>
            <CardTitle>Recent Transactions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3">
            {summary.recent_transactions.length ? (
              summary.recent_transactions.map((transaction) => (
                <div
                  key={transaction.id}
                  className="grid gap-2 rounded-lg p-3 transition-colors duration-100 hover:bg-muted/30 md:grid-cols-[96px_1fr_auto]"
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

function automationHealthStatus(status: Awaited<ReturnType<typeof getStatus>>) {
  const schedule = status.scheduled_refresh
  if (!schedule.enabled) {
    return 'missing'
  }
  if (schedule.last_status === 'failed') {
    return 'critical'
  }
  if (schedule.last_status === 'skipped') {
    return 'warning'
  }
  if (status.actuals_freshness.status === 'critical' || status.plan_freshness.status === 'missing') {
    return 'warning'
  }
  return schedule.last_status ?? 'fresh'
}

function automationHealthHeadline(status: Awaited<ReturnType<typeof getStatus>>) {
  const schedule = status.scheduled_refresh
  if (!schedule.enabled) {
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

function automationHealthDetail(status: Awaited<ReturnType<typeof getStatus>>) {
  const schedule = status.scheduled_refresh
  if (!schedule.enabled) {
    return 'Automatic refresh can keep the workbook import, YNAB sync, and reconcile flow current without manual runs.'
  }
  if (schedule.last_error) {
    return schedule.last_error
  }
  return `Runs every ${schedule.interval_minutes ?? '—'} minutes. Next run ${formatRunAt(schedule.next_run_at)}.`
}

function formatOverageWatchWindow(startMonth: string | null, endMonth: string | null) {
  if (!startMonth || !endMonth) {
    return 'Waiting for enough completed-month history to score repeat overages.'
  }
  if (startMonth === endMonth) {
    return `Completed history through ${formatMonthLabel(endMonth)}`
  }
  return `Completed months from ${formatMonthLabel(startMonth)} through ${formatMonthLabel(endMonth)}`
}

function OverviewSkeleton() {
  return (
    <div className="space-y-8">
      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }, (_, index) => (
          <Skeleton key={index} className="h-32 rounded-xl" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
        <Skeleton className="h-[480px] rounded-xl" />
        <Skeleton className="h-[480px] rounded-xl" />
      </div>
      <div className="grid gap-6 xl:grid-cols-[1.15fr_1fr]">
        <Skeleton className="h-[420px] rounded-xl" />
        <Skeleton className="h-[420px] rounded-xl" />
      </div>
    </div>
  )
}

function ReviewColumn({
  title,
  subtitle,
  items,
  empty,
  showAction = false,
}: {
  title: string
  subtitle: string
  items: ReviewItem[]
  empty: string
  showAction?: boolean
}) {
  return (
    <div className="rounded-lg bg-muted/20 p-4">
      <div className="text-base font-medium text-foreground">{title}</div>
      <p className="mt-1 text-sm text-muted-foreground">{subtitle}</p>
      <div className="mt-4 space-y-3">
        {items.length ? (
          items.map((item) => (
            <div
              key={`${item.kind}-${item.group_name ?? 'none'}-${item.category_name ?? 'none'}-${item.title}`}
              className="rounded-lg bg-muted/30 p-3"
            >
              <div className="flex items-start justify-between gap-3">
                <div className="text-sm font-medium text-foreground">{item.title}</div>
                <StatusChip status={item.severity} />
              </div>
              <div className="mt-2 text-sm text-muted-foreground">{item.why_it_matters}</div>
              {showAction && item.recommended_action ? (
                <div className="mt-3 text-sm text-foreground/90">{item.recommended_action}</div>
              ) : null}
            </div>
          ))
        ) : (
          <div className="rounded-lg bg-emerald-500/[0.06] p-4 text-sm text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
            {empty}
          </div>
        )}
      </div>
    </div>
  )
}
