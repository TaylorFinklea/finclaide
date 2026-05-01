<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { createQuery } from '@tanstack/svelte-query'
  import { ArrowLeft, AlertTriangle } from 'lucide-svelte'
  import { writable } from 'svelte/store'

  import Sparkline from '$components/sparkline.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    getActivePlan,
    getAnomalies,
    getSpendingTrends,
    getTransactions,
    type CategoryAnomaly,
    type TransactionAnomaly,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'
  import { withBasePath } from '$lib/runtime'

  let categoryId = $derived(Number($page.params.category_id))

  const planQuery = createQuery({
    queryKey: ['plan-active'],
    queryFn: () => getActivePlan(),
    enabled: browser,
  })

  let category = $derived(() => {
    const plan = $planQuery.data
    if (!plan) return null
    const all = [
      ...(plan.blocks.monthly ?? []),
      ...(plan.blocks.annual ?? []),
      ...(plan.blocks.one_time ?? []),
      ...(plan.blocks.stipends ?? []),
      ...(plan.blocks.savings ?? []),
    ]
    return all.find((c) => c.id === categoryId) ?? null
  })

  // Trends + anomalies + transactions key on the categoryId; wired to
  // writable opts that the $effect updates so they refire when the user
  // navigates between detail pages.
  const trendsFn = async () => {
    const cat = category()
    if (!cat) return null
    return getSpendingTrends({
      months: 12,
      group: cat.group_name,
      category: cat.category_name,
    })
  }
  const txnFn = async () => {
    const cat = category()
    if (!cat) return null
    return getTransactions({
      group: cat.group_name,
      category: cat.category_name,
      limit: 30,
      offset: 0,
    })
  }
  const trendsOpts = writable({
    queryKey: ['analytics-trends-12-cat', 0] as readonly unknown[],
    queryFn: trendsFn,
    enabled: false,
  })
  const txnOpts = writable({
    queryKey: ['transactions-cat', 0] as readonly unknown[],
    queryFn: txnFn,
    enabled: false,
  })
  $effect(() => {
    const id = categoryId
    trendsOpts.set({
      queryKey: ['analytics-trends-12-cat', id],
      queryFn: trendsFn,
      enabled: browser,
    })
    txnOpts.set({
      queryKey: ['transactions-cat', id],
      queryFn: txnFn,
      enabled: browser,
    })
  })
  const trendsQuery = createQuery(trendsOpts)
  const anomaliesQuery = createQuery({
    queryKey: ['analytics-anomalies-12'],
    queryFn: () => getAnomalies({ months: 12, threshold: 1.5 }),
    enabled: browser,
  })
  const txnQuery = createQuery(txnOpts)

  let trendCategory = $derived(() => $trendsQuery.data?.categories?.[0] ?? null)
  let monthlySeries = $derived(
    () => trendCategory()?.monthly_spend ?? [],
  )

  let categoryAnomalies = $derived((): CategoryAnomaly[] => {
    const cat = category()
    const data = $anomaliesQuery.data
    if (!cat || !data) return []
    return data.category_anomalies.filter(
      (a) => a.group_name === cat.group_name && a.category_name === cat.category_name,
    )
  })
  let transactionAnomalies = $derived((): TransactionAnomaly[] => {
    const cat = category()
    const data = $anomaliesQuery.data
    if (!cat || !data) return []
    return data.transaction_anomalies.filter(
      (a) => a.group_name === cat.group_name && a.category_name === cat.category_name,
    )
  })

  // Build chart polyline. Width 600, height 80; max value drives Y normalization.
  let chartPath = $derived(() => {
    const series = monthlySeries()
    if (series.length === 0) return ''
    const max = Math.max(...series.map((m) => m.spend_milliunits), 1)
    const stepX = 600 / Math.max(1, series.length - 1)
    return series
      .map((m, i) => {
        const x = i * stepX
        const y = 80 - (m.spend_milliunits / max) * 80
        return `${x.toFixed(1)},${y.toFixed(1)}`
      })
      .join(' ')
  })
</script>

<div class="space-y-6">
  <a
    href={withBasePath('/insights')}
    class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
  >
    <ArrowLeft class="h-3.5 w-3.5" aria-hidden="true" />
    Back to Insights
  </a>

  {#if $planQuery.isLoading}
    <Skeleton class="h-32 rounded" />
  {:else if !category()}
    <Card class="border-border/40 bg-card">
      <CardContent>
        <p class="py-8 text-center text-sm text-muted-foreground">
          Category not found in the active plan.
        </p>
      </CardContent>
    </Card>
  {:else}
    {@const cat = category()!}
    <Card class="border-border/40 bg-card">
      <CardHeader>
        <CardTitle>{cat.category_name}</CardTitle>
        <p class="text-sm text-muted-foreground">
          {cat.group_name} · {cat.block} · planned {formatMoney(cat.planned_milliunits)}
        </p>
      </CardHeader>
      <CardContent class="space-y-4">
        {#if monthlySeries().length === 0}
          <p class="text-sm text-muted-foreground">No spending in the last 12 months.</p>
        {:else}
          <div class="rounded-md bg-muted/15 p-4">
            <div class="text-[11px] uppercase tracking-wide text-muted-foreground">
              12-month spending
            </div>
            <svg
              viewBox="0 0 600 80"
              class="mt-2 h-20 w-full text-foreground"
              role="img"
              aria-label={`${cat.category_name} 12-month timeline`}
            >
              <polyline
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                points={chartPath()}
              />
            </svg>
            <div class="mt-2 flex justify-between text-[10px] text-muted-foreground">
              {#each monthlySeries() as m, idx (m.month)}
                {#if idx === 0 || idx === monthlySeries().length - 1 || idx === Math.floor(monthlySeries().length / 2)}
                  <span>{m.month}</span>
                {/if}
              {/each}
            </div>
          </div>
          <div class="grid gap-3 md:grid-cols-3 text-sm">
            <div class="rounded-md bg-muted/15 p-3">
              <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Average</div>
              <div class="mt-1 font-mono">
                {formatMoney(trendCategory()?.average_milliunits ?? 0)}
              </div>
            </div>
            <div class="rounded-md bg-muted/15 p-3">
              <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Trend</div>
              <div class="mt-1 capitalize">{trendCategory()?.trend_direction ?? '—'}</div>
            </div>
            <div class="rounded-md bg-muted/15 p-3">
              <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Volatility (CV)</div>
              <div class="mt-1 font-mono">
                {((trendCategory()?.coefficient_of_variation ?? 0) * 100).toFixed(0)}%
              </div>
            </div>
          </div>
        {/if}
      </CardContent>
    </Card>

    {#if categoryAnomalies().length > 0 || transactionAnomalies().length > 0}
      <Card class="border-border/40 bg-card">
        <CardHeader>
          <CardTitle>
            <span class="inline-flex items-center gap-2">
              <AlertTriangle class="h-4 w-4 text-amber-300" aria-hidden="true" />
              Anomalies
            </span>
          </CardTitle>
        </CardHeader>
        <CardContent class="space-y-3 text-sm">
          {#each categoryAnomalies() as anomaly (anomaly.month)}
            <div class="rounded-md bg-muted/15 p-3">
              <div class="font-medium text-foreground">
                {anomaly.narrative?.headline ?? `${anomaly.month} spending was unusual`}
              </div>
              {#if anomaly.narrative?.context}
                <div class="mt-1 text-xs text-muted-foreground">{anomaly.narrative.context}</div>
              {/if}
            </div>
          {/each}
          {#each transactionAnomalies() as anomaly (anomaly.id)}
            <div class="rounded-md bg-muted/15 p-3">
              <div class="font-medium text-foreground">
                {anomaly.narrative?.headline ?? `${anomaly.payee_name ?? 'Transaction'} on ${anomaly.date}`}
              </div>
              <div class="mt-1 text-xs text-muted-foreground">
                {anomaly.date} · {anomaly.payee_name ?? '—'}
              </div>
            </div>
          {/each}
        </CardContent>
      </Card>
    {/if}

    <Card class="border-border/40 bg-card">
      <CardHeader>
        <CardTitle>Recent transactions</CardTitle>
      </CardHeader>
      <CardContent>
        {#if $txnQuery.isLoading}
          <Skeleton class="h-32 rounded" />
        {:else if !$txnQuery.data || $txnQuery.data.transactions.length === 0}
          <p class="text-sm text-muted-foreground">No transactions found for this category.</p>
        {:else}
          <table class="w-full text-sm">
            <thead>
              <tr class="text-left text-[11px] uppercase tracking-wide text-muted-foreground">
                <th class="py-2 pr-3">Date</th>
                <th class="py-2 pr-3">Payee</th>
                <th class="py-2 pr-3 text-right">Amount</th>
              </tr>
            </thead>
            <tbody>
              {#each $txnQuery.data.transactions as txn (txn.id)}
                <tr class="border-t border-border/30">
                  <td class="py-2 pr-3 font-mono text-xs">{txn.date}</td>
                  <td class="py-2 pr-3">{txn.payee_name ?? '—'}</td>
                  <td class="py-2 pr-3 text-right font-mono text-xs">
                    {formatMoney(txn.amount_milliunits)}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        {/if}
      </CardContent>
    </Card>
  {/if}
</div>
