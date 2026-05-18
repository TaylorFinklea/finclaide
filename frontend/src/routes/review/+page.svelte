<script lang="ts">
  import { browser } from '$app/environment'
  import { createQuery } from '@tanstack/svelte-query'
  import { ChevronRight } from 'lucide-svelte'

  import AttentionItem from '$components/quartz/attention-item.svelte'
  import HighlightTile from '$components/quartz/highlight-tile.svelte'
  import PlanVsActualRow from '$components/quartz/plan-vs-actual-row.svelte'
  import RecommendationItem from '$components/quartz/recommendation-item.svelte'
  import SectionHeading from '$components/quartz/section-heading.svelte'
  import Tabs from '$components/quartz/tabs.svelte'
  import {
    getCashflowTimeline,
    getStatus,
    getSummary,
    getWeeklyReview,
    getYearEndProjection,
  } from '$lib/api'
  import { accentForGroup } from '$lib/design/tokens'
  import { formatCompactMoney, formatMoney, formatMonthLabel } from '$lib/format'
  import { monthStore } from '$lib/stores/month.svelte'

  type Tab = 'review' | 'pa' | 'cash' | 'transactions'
  let tab = $state<Tab>('review')

  const tabs = [
    { value: 'review' as const, label: 'Weekly review' },
    { value: 'pa' as const, label: 'Plan vs actual' },
    { value: 'cash' as const, label: 'Cash flow' },
    { value: 'transactions' as const, label: 'Transactions' },
  ]

  const month = monthStore.value

  const reviewQuery = createQuery({
    queryKey: ['weekly-review', month],
    queryFn: () => getWeeklyReview(month),
    enabled: browser && !!month,
  })
  const summaryQuery = createQuery({
    queryKey: ['summary', month],
    queryFn: () => getSummary(month),
    enabled: browser && !!month,
  })
  const statusQuery = createQuery({
    queryKey: ['status'],
    queryFn: getStatus,
    enabled: browser,
  })
  const projectionQuery = createQuery({
    queryKey: ['projection', month],
    queryFn: () => getYearEndProjection(month),
    enabled: browser && !!month,
  })
  const cashflowQuery = createQuery({
    queryKey: ['cashflow', month],
    queryFn: () => getCashflowTimeline({ months: 12, as_of_month: month }),
    enabled: browser && !!month,
  })

  function dayInfo(): { dayOfMonth: number; daysInMonth: number; weekday: string; weekNumber: number } {
    const now = new Date()
    const dayOfMonth = now.getDate()
    const daysInMonth = new Date(now.getFullYear(), now.getMonth() + 1, 0).getDate()
    const weekday = now.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' })
    return { dayOfMonth, daysInMonth, weekday, weekNumber: Math.ceil(dayOfMonth / 7) }
  }
  const { dayOfMonth, daysInMonth, weekday, weekNumber } = dayInfo()

  let planned = $derived<number>(
    ($reviewQuery.data?.supporting_metrics?.planned_total_milliunits as number | undefined) ?? 0,
  )
  let actual = $derived<number>(
    ($reviewQuery.data?.supporting_metrics?.actual_total_milliunits as number | undefined) ?? 0,
  )
  let pctOfPlan = $derived(planned > 0 ? ((actual / planned) * 100).toFixed(1) : '—')
  let monthProgressPct = $derived(Math.round((dayOfMonth / daysInMonth) * 100))
  let paceDelta = $derived(planned > 0 ? Math.round((actual / planned - dayOfMonth / daysInMonth) * 100) : 0)

  let projectedClose = $derived<number>(
    ($projectionQuery.data?.totals?.projected_annual_milliunits as number | undefined) ?? 0,
  )
  let projectedVariance = $derived<number>(
    ($projectionQuery.data?.totals?.projected_variance_milliunits as number | undefined) ?? 0,
  )

  let cashflowMonths = $derived($cashflowQuery.data?.months ?? [])
  let netThisMonth = $derived.by<number>(() => {
    const m = cashflowMonths.find((row: any) => row.month === month) as any
    return m ? m.inflow_milliunits - m.outflow_milliunits : 0
  })
  let netPrevMonth = $derived.by<number>(() => {
    if (cashflowMonths.length < 2) return 0
    const idx = cashflowMonths.findIndex((row: any) => row.month === month)
    if (idx < 1) return 0
    const p = cashflowMonths[idx - 1] as any
    return p.inflow_milliunits - p.outflow_milliunits
  })
  let netMoMPct = $derived(
    netPrevMonth !== 0
      ? Math.round(((netThisMonth - netPrevMonth) / Math.abs(netPrevMonth)) * 100)
      : 0,
  )

  function chip(sev: string): 'crit' | 'warn' | 'info' | 'good' {
    if (sev === 'critical' || sev === 'crit') return 'crit'
    if (sev === 'warning' || sev === 'warn') return 'warn'
    if (sev === 'good' || sev === 'success') return 'good'
    return 'info'
  }

  function ynabStale(): { stale: boolean; hours: number } {
    const hrs = $statusQuery.data?.actuals_freshness?.hours_stale ?? 0
    return { stale: hrs > 24, hours: Math.round(hrs) }
  }
</script>

<svelte:head>
  <title>Review · Finclaide</title>
</svelte:head>

<section class="flex flex-col gap-5 px-7 py-6">
  <header class="flex items-center justify-between">
    <div>
      <div class="mb-2 inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs text-foreground/70">
        <span class="h-1.5 w-1.5 rounded-full bg-[#2F8A57]"></span>
        Review · Week {weekNumber}
      </div>
      <h1 class="flex items-baseline gap-3 text-[22px] font-semibold tracking-[-0.015em]">
        {formatMonthLabel(month)}
        <span class="text-sm font-normal text-muted-foreground">
          {weekday} · day {dayOfMonth} of {daysInMonth}
        </span>
      </h1>
    </div>
    <div class="flex items-center gap-2">
      {#if ynabStale().stale}
        <div class="inline-flex items-center gap-1.5 rounded-full border border-[#C68A21]/30 bg-[#FBF1DC] px-2.5 py-1 text-xs text-[#C68A21]">
          <span class="h-1.5 w-1.5 rounded-full bg-[#C68A21]"></span>
          YNAB stale {ynabStale().hours}h
        </div>
      {/if}
      <a
        href="/operate"
        class="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-secondary"
      >
        View runs
      </a>
    </div>
  </header>

  <Tabs {tabs} bind:value={tab} />

  {#if tab === 'review'}
    <div class="grid gap-3" style="grid-template-columns: 1.4fr 1fr 1fr 1fr">
      <HighlightTile
        title="Month so far"
        value={formatMoney(actual).replace('.00', '')}
        unit={`/ ${formatMoney(planned).replace('.00', '')}`}
        sub={`${pctOfPlan}% of plan · day ${dayOfMonth}/${daysInMonth} (${monthProgressPct}%)`}
        subtone={paceDelta > 5 ? 'warn' : paceDelta < -5 ? 'pos' : 'muted'}
      />
      <HighlightTile
        title="Projected close"
        value={projectedClose > 0 ? formatCompactMoney(projectedClose) : '—'}
        sub={projectedVariance > 0
          ? `+${formatMoney(projectedVariance).replace('.00', '')} over plan`
          : projectedVariance < 0
            ? `${formatMoney(projectedVariance).replace('.00', '')} under plan`
            : 'on plan'}
        subtone={projectedVariance > 0 ? 'warn' : 'pos'}
      />
      <HighlightTile
        title="Net cash flow"
        value={(netThisMonth >= 0 ? '+' : '') + formatMoney(netThisMonth).replace('.00', '')}
        sub={netPrevMonth !== 0 ? `${netMoMPct > 0 ? '+' : ''}${netMoMPct}% MoM` : '—'}
        subtone={netMoMPct >= 0 ? 'pos' : 'neg'}
      />
      <HighlightTile
        title="Runway"
        value="—"
        unit="mo"
        sub="cash · burn not yet wired"
        subtone="muted"
      />
    </div>

    <div class="grid gap-4" style="grid-template-columns: 1.4fr 1fr">
      <div class="flex flex-col gap-4">
        <div class="rounded-xl border border-border bg-card p-[18px]">
          <SectionHeading title="Plan vs actual · by group" meta="Open detail" />
          {#if $summaryQuery.data?.groups}
            {#each $summaryQuery.data.groups as group (group.group_name)}
              {@const groupActual = group.categories.reduce((s: number, c: any) => s + c.actual_milliunits, 0)}
              {@const groupPlanned = group.categories.reduce((s: number, c: any) => s + c.planned_milliunits, 0)}
              <PlanVsActualRow
                name={group.group_name}
                subtitle={`${group.categories.length} categories`}
                accent={accentForGroup(group.group_name)}
                planned={groupPlanned}
                actual={groupActual}
                {formatMoney}
              />
            {/each}
          {:else}
            <div class="py-6 text-center text-sm text-muted-foreground">Loading plan…</div>
          {/if}
        </div>

        <div class="rounded-xl border border-border bg-card p-[18px]">
          <SectionHeading title="What changed" meta="Month over month · 15% drift threshold" />
          <div class="flex flex-col gap-2.5">
            {#each $reviewQuery.data?.changes ?? [] as item, i (i)}
              <AttentionItem
                title={item.title}
                why={item.why_it_matters}
                severity={chip(item.severity)}
              />
            {/each}
            {#if ($reviewQuery.data?.changes?.length ?? 0) === 0}
              <div class="rounded-xl border border-border bg-secondary/40 p-3 text-xs text-muted-foreground">
                No notable month-over-month changes.
              </div>
            {/if}
          </div>
        </div>
      </div>

      <div class="flex flex-col gap-4">
        <div class="rounded-xl border border-border bg-card p-[18px]">
          <SectionHeading
            title="Needs attention"
            meta={`${$reviewQuery.data?.blockers?.length ?? 0} blocker${($reviewQuery.data?.blockers?.length ?? 0) === 1 ? '' : 's'} · ${$reviewQuery.data?.overages?.length ?? 0} overages`}
          />
          <div class="flex flex-col gap-2.5">
            {#each $reviewQuery.data?.blockers ?? [] as item, i (`b-${i}`)}
              <AttentionItem
                title={item.title}
                why={item.why_it_matters}
                severity="crit"
                highlight
              >
                <ChevronRight class="h-3 w-3" />
                <span class="font-medium">{item.recommended_action ?? 'Resolve in Operate.'}</span>
              </AttentionItem>
            {/each}
            {#each $reviewQuery.data?.overages ?? [] as item, i (`o-${i}`)}
              <AttentionItem
                title={item.title}
                why={item.why_it_matters}
                severity={chip(item.severity)}
              />
            {/each}
            {#if ($reviewQuery.data?.blockers?.length ?? 0) === 0 && ($reviewQuery.data?.overages?.length ?? 0) === 0}
              <div class="rounded-xl border border-border bg-secondary/40 p-3 text-xs text-muted-foreground">
                Nothing needs attention right now.
              </div>
            {/if}
          </div>
        </div>

        <div class="rounded-xl border border-border bg-card p-[18px]">
          <SectionHeading title="Recommended actions" meta="Suggested by Finclaide" />
          <div class="flex flex-col gap-2.5">
            {#each $reviewQuery.data?.recommendations ?? [] as item, i (`r-${i}`)}
              <RecommendationItem
                title={item.title}
                why={item.why_it_matters}
                confidence="medium"
              />
            {/each}
            {#if ($reviewQuery.data?.recommendations?.length ?? 0) === 0}
              <div class="rounded-xl border border-border bg-secondary/40 p-3 text-xs text-muted-foreground">
                No recommendations yet — Finclaide will surface them as patterns emerge.
              </div>
            {/if}
          </div>
        </div>
      </div>
    </div>
  {:else}
    <div class="rounded-xl border border-border bg-card p-8 text-center text-sm text-muted-foreground">
      This view is coming as part of the Quartz redesign rollout.
    </div>
  {/if}
</section>
