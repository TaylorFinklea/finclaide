<script lang="ts">
  import { browser } from '$app/environment'
  import { createQuery } from '@tanstack/svelte-query'
  import { Lightbulb } from 'lucide-svelte'
  import { writable } from 'svelte/store'

  import Sparkline from '$components/sparkline.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    getActivePlan,
    getMonthPace,
    getSpendingTrends,
    type PaceCategory,
    type TrendCategory,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'
  import { withBasePath } from '$lib/runtime'
  import { monthStore } from '$lib/stores/month.svelte'

  let month = $derived(monthStore.value)

  const planQuery = createQuery({
    queryKey: ['plan-active'],
    queryFn: () => getActivePlan(),
    enabled: browser,
  })
  const trendsQuery = createQuery({
    queryKey: ['analytics-trends-12'],
    queryFn: () => getSpendingTrends({ months: 12 }),
    enabled: browser,
  })
  // Pace query needs to refire when monthStore changes — reactive options.
  const paceOpts = writable({
    queryKey: ['analytics-pace', monthStore.value] as readonly unknown[],
    queryFn: () => getMonthPace(monthStore.value),
    enabled: browser,
  })
  $effect(() => {
    paceOpts.set({
      queryKey: ['analytics-pace', month],
      queryFn: () => getMonthPace(month),
      enabled: browser,
    })
  })
  const paceQuery = createQuery(paceOpts)

  type Row = {
    category_id: number
    group_name: string
    category_name: string
    block: string
    planned_milliunits: number
    sparkline_values: number[]
    pace?: PaceCategory
    trend?: TrendCategory
  }

  let rows = $derived((): Row[] => {
    const plan = $planQuery.data
    const trends = $trendsQuery.data
    const pace = $paceQuery.data
    if (!plan) return []
    const trendByKey = new Map<string, TrendCategory>()
    if (trends) {
      for (const cat of trends.categories) {
        trendByKey.set(`${cat.group_name}|${cat.category_name}`, cat)
      }
    }
    const paceByKey = new Map<string, PaceCategory>()
    if (pace) {
      for (const cat of pace.categories) {
        paceByKey.set(`${cat.group_name}|${cat.category_name}`, cat)
      }
    }
    const out: Row[] = []
    const eligible = [
      ...(plan.blocks.monthly ?? []),
      ...(plan.blocks.stipends ?? []),
    ]
    for (const cat of eligible) {
      const key = `${cat.group_name}|${cat.category_name}`
      const trend = trendByKey.get(key)
      const sparklineValues = trend
        ? trend.monthly_spend.map((m) => m.spend_milliunits)
        : []
      out.push({
        category_id: cat.id,
        group_name: cat.group_name,
        category_name: cat.category_name,
        block: cat.block,
        planned_milliunits: cat.planned_milliunits,
        sparkline_values: sparklineValues,
        pace: paceByKey.get(key),
        trend,
      })
    }
    out.sort((a, b) => {
      const aOver = a.pace?.projected_overage_milliunits ?? 0
      const bOver = b.pace?.projected_overage_milliunits ?? 0
      if (aOver !== bOver) return bOver - aOver
      return a.category_name.localeCompare(b.category_name)
    })
    return out
  })

  const STATUS_LABELS: Record<string, string> = {
    no_spend_yet: 'No spend yet',
    unplanned: 'Unplanned',
    under_pace: 'Under pace',
    on_pace: 'On pace',
    over_pace: 'Over pace',
    at_risk: 'At risk',
    blowout: 'Blowout',
  }

  const STATUS_STYLES: Record<string, string> = {
    no_spend_yet: 'bg-muted/30 text-muted-foreground',
    unplanned: 'bg-rose-500/10 text-rose-300 ring-1 ring-rose-500/30',
    under_pace: 'bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30',
    on_pace: 'bg-muted/40 text-muted-foreground',
    over_pace: 'bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/30',
    at_risk: 'bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/40',
    blowout: 'bg-rose-500/25 text-rose-200 ring-1 ring-rose-500/60',
  }

  const TREND_ARROWS: Record<string, string> = {
    rising: '↑',
    falling: '↓',
    stable: '→',
  }
</script>

<div class="space-y-6">
  <Card class="border-border/40 bg-card">
    <CardHeader>
      <CardTitle>
        <span class="inline-flex items-center gap-2">
          <Lightbulb class="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          Insights
        </span>
      </CardTitle>
      <p class="text-sm text-muted-foreground">
        Per-category trends across the last 12 months. Click a row to see the full timeline,
        anomalies, and recent transactions.
      </p>
    </CardHeader>
    <CardContent>
      {#if $planQuery.isLoading || $trendsQuery.isLoading}
        <Skeleton class="h-64 rounded" />
      {:else if rows().length === 0}
        <p class="text-sm text-muted-foreground">No active plan yet.</p>
      {:else}
        <div class="overflow-x-auto">
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th class="py-2 pr-3">Category</th>
                <th class="py-2 pr-3">12-month spend</th>
                <th class="py-2 pr-3 text-right">Avg</th>
                <th class="py-2 pr-3 text-center">Trend</th>
                <th class="py-2 pr-3 text-right">Mid-month pace</th>
                <th class="py-2 pr-1"></th>
              </tr>
            </thead>
            <tbody>
              {#each rows() as row (row.category_id)}
                <tr class="border-t border-border/30">
                  <td class="py-2 pr-3">
                    <a
                      class="block hover:text-foreground"
                      href={withBasePath(`/insights/${row.category_id}`)}
                    >
                      <div class="font-medium text-foreground">{row.category_name}</div>
                      <div class="text-[11px] text-muted-foreground">{row.group_name}</div>
                    </a>
                  </td>
                  <td class="py-2 pr-3">
                    {#if row.sparkline_values.length > 0}
                      <Sparkline
                        values={row.sparkline_values}
                        title={`${row.category_name} 12-month trend`}
                      />
                    {:else}
                      <span class="text-[11px] text-muted-foreground">—</span>
                    {/if}
                  </td>
                  <td class="py-2 pr-3 text-right font-mono text-xs text-muted-foreground">
                    {row.trend ? formatMoney(row.trend.average_milliunits) : '—'}
                  </td>
                  <td class="py-2 pr-3 text-center text-xs">
                    {row.trend ? TREND_ARROWS[row.trend.trend_direction] ?? '—' : '—'}
                  </td>
                  <td class="py-2 pr-3 text-right">
                    {#if row.pace}
                      <span class={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[row.pace.pace_status] ?? ''}`}>
                        {STATUS_LABELS[row.pace.pace_status] ?? row.pace.pace_status}
                      </span>
                    {:else}
                      <span class="text-[11px] text-muted-foreground">—</span>
                    {/if}
                  </td>
                  <td class="py-2 pr-1 text-right text-[11px]">
                    <a
                      class="text-muted-foreground hover:text-foreground"
                      href={withBasePath(`/insights/${row.category_id}`)}
                    >
                      Open →
                    </a>
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
      {/if}
    </CardContent>
  </Card>
</div>
