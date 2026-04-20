<script lang="ts">
  import { browser } from '$app/environment'
  import { createQuery } from '@tanstack/svelte-query'
  import { writable } from 'svelte/store'
  import { AlertTriangle, ArrowDownUp, RefreshCcw, ShieldCheck } from 'lucide-svelte'

  import FailureCauseCard from '$components/failure-cause-card.svelte'
  import GroupChart from '$components/group-chart.svelte'
  import MetricCard from '$components/metric-card.svelte'
  import StatusChip from '$components/status-chip.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import { getStatus, getSummary, getWeeklyReview, type ReviewItem, type StatusResponse } from '$lib/api'
  import { formatCompactMoney, formatDay, formatMoney, formatMonthLabel, formatRunAt } from '$lib/format'
  import { monthStore } from '$lib/stores/month.svelte'

  let month = $derived(monthStore.value)

  const statusQuery = createQuery({ queryKey: ['status'], queryFn: getStatus, enabled: browser })

  const summaryOpts = writable({
    queryKey: ['summary', monthStore.value],
    queryFn: () => getSummary(monthStore.value),
    enabled: browser,
  })
  const reviewOpts = writable({
    queryKey: ['review', monthStore.value],
    queryFn: () => getWeeklyReview(monthStore.value),
    enabled: browser,
  })
  $effect(() => {
    summaryOpts.set({
      queryKey: ['summary', month],
      queryFn: () => getSummary(month),
      enabled: browser,
    })
    reviewOpts.set({
      queryKey: ['review', month],
      queryFn: () => getWeeklyReview(month),
      enabled: browser,
    })
  })
  const summaryQuery = createQuery(summaryOpts)
  const reviewQuery = createQuery(reviewOpts)

  let summary = $derived($summaryQuery.data)
  let status = $derived($statusQuery.data)
  let review = $derived($reviewQuery.data)

  let annualCategories = $derived(
    summary?.groups.flatMap((group) =>
      group.categories
        .filter((category) => category.due_month !== null)
        .map((category) => ({ ...category, group_name: group.group_name })),
    ) ?? [],
  )

  let priorityItems = $derived(
    review
      ? review.blockers.length > 0
        ? review.blockers.slice(0, 3)
        : [...review.overages, ...review.changes, ...review.anomalies].slice(0, 3)
      : [],
  )
  let attentionItems = $derived(
    review ? [...review.blockers, ...review.overages, ...review.anomalies].slice(0, 3) : [],
  )
  let actionItems = $derived(review?.recommendations.slice(0, 3) ?? [])

  function automationHealthStatus(s: StatusResponse) {
    const schedule = s.scheduled_refresh
    if (!schedule.enabled) return 'missing'
    if (schedule.last_status === 'failed') return 'critical'
    if (schedule.last_status === 'skipped') return 'warning'
    if (s.actuals_freshness.status === 'critical' || s.plan_freshness.status === 'missing') return 'warning'
    return schedule.last_status ?? 'fresh'
  }

  function automationHealthHeadline(s: StatusResponse) {
    const schedule = s.scheduled_refresh
    if (!schedule.enabled) return 'Automatic refresh is disabled'
    if (schedule.last_status === 'success') return `Last run succeeded ${formatRunAt(schedule.last_finished_at)}`
    if (schedule.last_status === 'failed') return `Last run failed ${formatRunAt(schedule.last_finished_at)}`
    if (schedule.last_status === 'skipped') return `Last run skipped ${formatRunAt(schedule.last_finished_at)}`
    return `Next run ${formatRunAt(schedule.next_run_at)}`
  }

  function automationHealthDetail(s: StatusResponse) {
    const schedule = s.scheduled_refresh
    if (!schedule.enabled)
      return 'Automatic refresh can keep the workbook import, YNAB sync, and reconcile flow current without manual runs.'
    if (schedule.last_error) return schedule.last_error
    return `Runs every ${schedule.interval_minutes ?? '—'} minutes. Next run ${formatRunAt(schedule.next_run_at)}.`
  }

  function formatOverageWatchWindow(startMonth: string | null, endMonth: string | null) {
    if (!startMonth || !endMonth) return 'Waiting for enough completed-month history to score repeat overages.'
    if (startMonth === endMonth) return `Completed history through ${formatMonthLabel(endMonth)}`
    return `Completed months from ${formatMonthLabel(startMonth)} through ${formatMonthLabel(endMonth)}`
  }
</script>

{#if $summaryQuery.isLoading || $statusQuery.isLoading || $reviewQuery.isLoading}
  <div class="space-y-8">
    <div class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      {#each Array(4) as _, i (i)}
        <Skeleton class="h-32 rounded-xl" />
      {/each}
    </div>
    <Skeleton class="h-[480px] rounded-xl" />
  </div>
{:else if summary && status && review}
  <div class="space-y-8">
    <FailureCauseCard {status} />

    <section class="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
      <MetricCard label="Budget Import" value={formatRunAt(status.last_budget_import_at)} detail={`Sheet: ${status.budget_sheet}`}>
        {#snippet icon()}<RefreshCcw class="h-4 w-4 text-muted-foreground" />{/snippet}
      </MetricCard>
      <MetricCard
        label="YNAB Sync"
        value={formatRunAt(status.last_ynab_sync_at)}
        detail={status.last_server_knowledge !== null ? `Server knowledge ${status.last_server_knowledge}` : 'Not synced'}
      >
        {#snippet icon()}<ArrowDownUp class="h-4 w-4 text-muted-foreground" />{/snippet}
      </MetricCard>
      <MetricCard
        label="Reconcile"
        value={status.last_reconcile_status ?? 'Not run'}
        detail={formatRunAt(status.last_reconcile_at)}
        tone={status.last_reconcile_status === 'success' ? 'good' : 'warn'}
      >
        {#snippet icon()}<ShieldCheck class="h-4 w-4 text-muted-foreground" />{/snippet}
      </MetricCard>
      <MetricCard
        label="Mismatch Count"
        value={String(summary.mismatches.length)}
        detail={status.busy ? `Busy: ${status.current_operation}` : 'Ready'}
        tone={summary.mismatches.length ? 'warn' : 'good'}
      >
        {#snippet icon()}<AlertTriangle class="h-4 w-4 text-muted-foreground" />{/snippet}
      </MetricCard>
    </section>

    <Card class="border-border/40 bg-card">
      <CardHeader class="space-y-4">
        <div class="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
          <div>
            <CardTitle>Weekly Review</CardTitle>
            <p class="mt-2 text-sm text-muted-foreground">{review.headline}</p>
          </div>
          <div class="flex items-center gap-3">
            <StatusChip status={review.overall_status} />
            <div class="text-right text-sm text-muted-foreground">
              <div>{review.supporting_metrics.blocker_count} blockers</div>
              <div>{review.supporting_metrics.recommendation_count} suggested actions</div>
            </div>
          </div>
        </div>

        {#if priorityItems.length}
          <div class="grid gap-3 xl:grid-cols-3">
            {#each priorityItems as item, idx (`${item.kind}-${item.title}-${idx}`)}
              <div class="rounded-lg bg-muted/30 p-4">
                <div class="flex items-start justify-between gap-3">
                  <div class="text-sm font-medium text-foreground">{item.title}</div>
                  <StatusChip status={item.severity} />
                </div>
                <p class="mt-2 text-sm text-muted-foreground">{item.why_it_matters}</p>
              </div>
            {/each}
          </div>
        {/if}

        {#if review.blockers.length}
          <div class="rounded-lg bg-rose-500/[0.08] p-4 ring-1 ring-inset ring-rose-500/20">
            <div class="flex items-center gap-2 text-sm font-medium text-rose-100">
              <AlertTriangle class="h-4 w-4" />
              Review confidence is reduced until these blockers are resolved.
            </div>
            <div class="mt-3 space-y-2">
              {#each review.blockers.slice(0, 3) as item (item.title)}
                <div class="text-sm text-rose-50/90">
                  <span class="font-medium">{item.title}</span>
                  <span class="text-rose-100/70"> — {item.recommended_action ?? item.why_it_matters}</span>
                </div>
              {/each}
            </div>
          </div>
        {/if}
      </CardHeader>
      <CardContent class="grid gap-4 xl:grid-cols-3">
        {@render reviewColumn('What Changed', 'Month-over-month shifts worth sanity-checking.', review.changes, 'No material month-over-month changes crossed the review thresholds.', false)}
        {@render reviewColumn('Needs Attention', 'Current blockers, overages, and unusual spend.', attentionItems, 'Nothing urgent is crowding the current review window.', false)}
        {@render reviewColumn('Recommended Actions', 'Suggested next steps grounded in the latest plan and actuals.', actionItems, 'No budget changes are being recommended right now.', true)}
      </CardContent>
    </Card>

    <Card class="border-border/40 bg-card">
      <CardHeader class="flex flex-row items-center justify-between gap-4">
        <div>
          <CardTitle>Automation Health</CardTitle>
          <p class="mt-2 text-sm text-muted-foreground">Scheduled import, YNAB sync, and reconcile state.</p>
        </div>
        <StatusChip status={automationHealthStatus(status)} />
      </CardHeader>
      <CardContent class="grid gap-4 md:grid-cols-3">
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Scheduler</div>
          <div class="mt-2 text-foreground">{automationHealthHeadline(status)}</div>
          <div class="mt-1 text-sm text-muted-foreground">{automationHealthDetail(status)}</div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">Plan Freshness</div>
          <div class="mt-2 text-foreground">{status.plan_freshness.status}</div>
          <div class="mt-1 text-sm text-muted-foreground">Last import {formatRunAt(status.plan_freshness.last_updated_at)}</div>
        </div>
        <div class="rounded-lg bg-muted/30 p-4">
          <div class="text-label-upper">YNAB Freshness</div>
          <div class="mt-2 text-foreground">{status.actuals_freshness.status}</div>
          <div class="mt-1 text-sm text-muted-foreground">Last sync {formatRunAt(status.actuals_freshness.last_updated_at)}</div>
        </div>
      </CardContent>
    </Card>

    <div class="grid gap-6 xl:grid-cols-[1.6fr_1fr]">
      <Card class="border-border/40 bg-card">
        <CardHeader class="flex flex-row items-center justify-between">
          <div>
            <CardTitle>Plan vs Actual by Group</CardTitle>
            <p class="mt-2 text-sm text-muted-foreground">
              {formatMonthLabel(summary.month)} across {summary.groups.length} groups
            </p>
          </div>
          <div class="text-right text-sm text-muted-foreground">
            <div>Planned {formatCompactMoney(summary.groups.reduce((sum, group) => sum + group.planned_milliunits, 0))}</div>
            <div>Actual {formatCompactMoney(summary.groups.reduce((sum, group) => sum + group.actual_milliunits, 0))}</div>
          </div>
        </CardHeader>
        <CardContent>
          <GroupChart groups={summary.groups} />
        </CardContent>
      </Card>

      <div class="space-y-6">
        <Card class="border-border/40 bg-card">
          <CardHeader class="space-y-3">
            <div class="flex items-center justify-between gap-3">
              <CardTitle>Overage Watch</CardTitle>
              <div class="text-label">{summary.overage_watch.categories.length} watched</div>
            </div>
            <p class="text-sm text-muted-foreground">
              {formatOverageWatchWindow(summary.overage_watch.analysis_start_month, summary.overage_watch.analysis_end_month)}
            </p>
          </CardHeader>
          <CardContent class="space-y-3">
            {#if summary.overage_watch.categories.length}
              {#each summary.overage_watch.categories as category (`${category.group_name}-${category.category_name}`)}
                <div class="grid gap-3 rounded-lg bg-muted/30 p-3">
                  <div class="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <div class="font-medium text-foreground">{category.group_name} / {category.category_name}</div>
                      <div class="mt-1 text-sm text-muted-foreground">
                        {category.watch_kind === 'unplanned' ? 'Needs a sinking fund' : 'Current target is lagging actual run rate'}
                      </div>
                    </div>
                    <div class="flex items-center gap-2">
                      <StatusChip status={category.watch_level} />
                      <div class="text-label">{category.over_months}/{category.analysis_month_count} months over</div>
                    </div>
                  </div>
                </div>
              {/each}
            {:else}
              <div class="rounded-lg bg-emerald-500/[0.06] p-4 text-sm text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
                No repeat overages are breaching the watch thresholds in the completed-month history.
              </div>
            {/if}
          </CardContent>
        </Card>

        <Card class="border-border/40 bg-card">
          <CardHeader>
            <CardTitle>Mismatch Status</CardTitle>
          </CardHeader>
          <CardContent class="space-y-3">
            {#if summary.mismatches.length}
              {#each summary.mismatches as mismatch (`${mismatch.group_name}-${mismatch.category_name}`)}
                <div class="rounded-lg bg-amber-500/[0.06] p-3 ring-1 ring-inset ring-amber-500/15">
                  <div class="font-medium text-foreground">{mismatch.group_name} / {mismatch.category_name}</div>
                  <div class="mt-1 text-sm text-muted-foreground">{mismatch.reason}</div>
                </div>
              {/each}
            {:else}
              <div class="rounded-lg bg-emerald-500/[0.06] p-4 text-sm text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
                Reconciliation is clean. All imported sheet categories have an exact YNAB match.
              </div>
            {/if}
          </CardContent>
        </Card>
      </div>
    </div>

    <div class="grid gap-6 xl:grid-cols-[1.15fr_1fr]">
      <Card class="border-border/40 bg-card">
        <CardHeader><CardTitle>Annual Funding Status</CardTitle></CardHeader>
        <CardContent class="space-y-3">
          {#if annualCategories.length}
            {#each annualCategories as category (`${category.group_name}-${category.category_name}`)}
              <div class="grid gap-2 rounded-lg p-3 transition-colors duration-100 hover:bg-muted/30 md:grid-cols-[1.3fr_1fr_auto]">
                <div>
                  <div class="font-medium text-foreground">{category.group_name} / {category.category_name}</div>
                  <div class="mt-1 text-sm text-muted-foreground">
                    Due month {category.due_month ?? '-'} &middot; Balance {formatMoney(category.current_balance_milliunits)}
                  </div>
                </div>
                <div class="font-mono text-sm text-muted-foreground">Monthly target {formatMoney(category.planned_milliunits)}</div>
                <StatusChip status={category.status} />
              </div>
            {/each}
          {:else}
            <p class="text-sm text-muted-foreground">No annual categories available.</p>
          {/if}
        </CardContent>
      </Card>

      <Card class="border-border/40 bg-card">
        <CardHeader><CardTitle>Recent Transactions</CardTitle></CardHeader>
        <CardContent class="space-y-3">
          {#if summary.recent_transactions.length}
            {#each summary.recent_transactions as transaction (transaction.id)}
              <div class="grid gap-2 rounded-lg p-3 transition-colors duration-100 hover:bg-muted/30 md:grid-cols-[96px_1fr_auto]">
                <div class="font-mono text-xs text-muted-foreground">{formatDay(transaction.date)}</div>
                <div>
                  <div class="font-medium text-foreground">{transaction.payee_name ?? 'Uncategorized payee'}</div>
                  <div class="mt-1 text-sm text-muted-foreground">
                    {transaction.group_name ?? 'No group'} / {transaction.category_name ?? 'No category'}
                  </div>
                </div>
                <div class="space-y-1 text-right">
                  <div class="font-mono text-sm text-foreground">{formatMoney(transaction.amount_milliunits)}</div>
                  {#if transaction.memo}
                    <div class="max-w-48 text-xs text-muted-foreground">{transaction.memo}</div>
                  {/if}
                </div>
              </div>
            {/each}
          {:else}
            <p class="text-sm text-muted-foreground">No transactions synced yet.</p>
          {/if}
        </CardContent>
      </Card>
    </div>
  </div>
{/if}

{#snippet reviewColumn(title: string, subtitle: string, items: ReviewItem[], empty: string, showAction: boolean)}
  <div class="rounded-lg bg-muted/20 p-4">
    <div class="text-base font-medium text-foreground">{title}</div>
    <p class="mt-1 text-sm text-muted-foreground">{subtitle}</p>
    <div class="mt-4 space-y-3">
      {#if items.length}
        {#each items as item, idx (`${item.kind}-${item.title}-${idx}`)}
          <div class="rounded-lg bg-muted/30 p-3">
            <div class="flex items-start justify-between gap-3">
              <div class="text-sm font-medium text-foreground">{item.title}</div>
              <StatusChip status={item.severity} />
            </div>
            <div class="mt-2 text-sm text-muted-foreground">{item.why_it_matters}</div>
            {#if showAction && item.recommended_action}
              <div class="mt-3 text-sm text-foreground/90">{item.recommended_action}</div>
            {/if}
          </div>
        {/each}
      {:else}
        <div class="rounded-lg bg-emerald-500/[0.06] p-4 text-sm text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
          {empty}
        </div>
      {/if}
    </div>
  </div>
{/snippet}
