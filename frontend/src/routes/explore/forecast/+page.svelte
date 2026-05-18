<script lang="ts">
  import { browser } from '$app/environment'
  import { createQuery } from '@tanstack/svelte-query'
  import { AlertTriangle, TrendingUp } from 'lucide-svelte'

  import ForecastRecommendationsCard from '$components/forecast-recommendations-card.svelte'
  import CashFlowCascadeCard from '$components/quartz/cash-flow-cascade-card.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    getActivePlan,
    getCashflowRecommendations,
    getCashflowTimeline,
    type CashflowMonth,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'
  import { withBasePath } from '$lib/runtime'

  const cashflowQuery = createQuery({
    queryKey: ['analytics-cashflow-12'],
    queryFn: () => getCashflowTimeline({ months: 12 }),
    enabled: browser,
  })
  const recommendationsQuery = createQuery({
    queryKey: ['analytics-cashflow-recommendations'],
    queryFn: () => getCashflowRecommendations({ months: 12 }),
    enabled: browser,
  })
  // Cascade restored from the old planning surface: how monthly income
  // distributes across the five cadence blocks, ending in the leftover.
  const planQuery = createQuery({
    queryKey: ['plan', 'active'],
    queryFn: () => getActivePlan(),
    enabled: browser,
  })

  let selectedMonth: CashflowMonth | null = $state(null)

  // -- chart geometry -----------------------------------------------------

  const CHART_WIDTH = 920
  const CHART_HEIGHT = 240
  const CHART_PAD_TOP = 20
  const CHART_PAD_BOTTOM = 32
  const CHART_PAD_LEFT = 60
  const CHART_PAD_RIGHT = 16

  let chart = $derived(() => {
    const data = $cashflowQuery.data
    if (!data) return null
    const months = data.months
    if (months.length === 0) return null

    // Y axis spans from min(0, lowest_balance) to max(0, max_balance)
    // with 10% padding on top and bottom.
    const balances = months.map((m) => m.ending_balance_milliunits)
    const lowest = Math.min(0, ...balances)
    const highest = Math.max(0, ...balances)
    const range = Math.max(1, highest - lowest)
    const yPad = range * 0.1
    const yMin = lowest - yPad
    const yMax = highest + yPad
    const ySpan = yMax - yMin
    const innerW = CHART_WIDTH - CHART_PAD_LEFT - CHART_PAD_RIGHT
    const innerH = CHART_HEIGHT - CHART_PAD_TOP - CHART_PAD_BOTTOM
    const stepX = innerW / months.length
    const barWidth = stepX * 0.7

    // Bars (net per month) — scaled relative to the same Y axis so the
    // bar zero line aligns with the balance-line zero crossing.
    function yFor(value: number): number {
      return CHART_PAD_TOP + ((yMax - value) / ySpan) * innerH
    }
    const zeroY = yFor(0)
    const bars = months.map((m, i) => {
      const x = CHART_PAD_LEFT + i * stepX + (stepX - barWidth) / 2
      const top = yFor(Math.max(m.net_milliunits, 0))
      const bottom = yFor(Math.min(m.net_milliunits, 0))
      const height = Math.max(1, bottom - top)
      return {
        month: m,
        x,
        y: top,
        width: barWidth,
        height,
        positive: m.net_milliunits >= 0,
      }
    })

    // Balance line — points at the center of each month.
    const points = months.map((m, i) => {
      const x = CHART_PAD_LEFT + i * stepX + stepX / 2
      const y = yFor(m.ending_balance_milliunits)
      return { x, y, balance: m.ending_balance_milliunits, month: m.month }
    })

    return {
      months,
      bars,
      points,
      polyline: points.map((p) => `${p.x.toFixed(1)},${p.y.toFixed(1)}`).join(' '),
      zeroY,
      yMin,
      yMax,
      stepX,
    }
  })

  function shortMonth(month: string): string {
    const [y, m] = month.split('-')
    const names = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return `${names[Number(m)]} ${y.slice(2)}`
  }

  const BASIS_LABELS = {
    plan: 'plan',
    run_rate: '6mo run-rate',
    lump: 'obligation',
  } as const

  import ScreenHeader from '$components/quartz/screen-header.svelte'
</script>

<section class="space-y-5 px-7 py-6">
  <ScreenHeader pill="Explore · Forecast" title="Cash flow forecast" subtitle="Twelve-month outlook + rebalance prompts" tone="explore" />

  <CashFlowCascadeCard plan={$planQuery.data} />

  <Card class="border-border bg-card">
    <CardHeader>
      <CardTitle>
        <span class="inline-flex items-center gap-2">
          <TrendingUp class="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          Forecast — 12-month cash flow
        </span>
      </CardTitle>
      <p class="text-sm text-muted-foreground">
        Hybrid model: fixed groups (Bills, Payments, Stipends, Savings) project from
        plan; everything else uses 6-month run-rate. Annual obligations land in
        their <code class="font-mono text-[11px]">due_month</code>.
      </p>
    </CardHeader>
    <CardContent class="space-y-4">
      {#if $cashflowQuery.isLoading}
        <Skeleton class="h-48 rounded" />
      {:else if $cashflowQuery.isError}
        <p class="text-sm text-rose-300">Could not load forecast.</p>
      {:else if $cashflowQuery.data}
        {@const data = $cashflowQuery.data}
        <div class="grid gap-3 md:grid-cols-3">
          <div class="rounded-md bg-muted/15 p-3">
            <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Cash on hand</div>
            <div class="mt-1 font-mono text-xl">{formatMoney(data.starting_balance_milliunits)}</div>
          </div>
          <div class="rounded-md bg-muted/15 p-3">
            <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Lowest projected</div>
            <div class={`mt-1 font-mono text-xl ${data.lowest_balance.balance_milliunits < 0 ? 'text-rose-300' : ''}`}>
              {formatMoney(data.lowest_balance.balance_milliunits)}
            </div>
            <div class="text-[11px] text-muted-foreground">in {shortMonth(data.lowest_balance.month)}</div>
          </div>
          <div class={`rounded-md p-3 ${data.first_negative_month ? 'bg-rose-500/15 ring-1 ring-rose-500/40' : 'bg-emerald-500/[0.06] ring-1 ring-emerald-500/15'}`}>
            <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Plan goes negative?</div>
            {#if data.first_negative_month}
              <div class="mt-1 inline-flex items-center gap-1 font-medium text-rose-200">
                <AlertTriangle class="h-3.5 w-3.5" />
                Yes — {shortMonth(data.first_negative_month)}
              </div>
            {:else}
              <div class="mt-1 font-medium text-emerald-200">No — stays positive 12 months</div>
            {/if}
          </div>
        </div>

        {@const c = chart()}
        {#if c}
          <div class="overflow-x-auto">
            <svg
              viewBox={`0 0 ${CHART_WIDTH} ${CHART_HEIGHT}`}
              class="w-full"
              role="img"
              aria-label="12-month cash flow forecast"
            >
              <!-- zero line -->
              <line
                x1={CHART_PAD_LEFT}
                x2={CHART_WIDTH - CHART_PAD_RIGHT}
                y1={c.zeroY}
                y2={c.zeroY}
                stroke="currentColor"
                stroke-opacity="0.2"
                stroke-dasharray="3 3"
                class="text-muted-foreground"
              />
              <!-- bars (monthly net) -->
              {#each c.bars as bar (bar.month.month)}
                <rect
                  x={bar.x}
                  y={bar.y}
                  width={bar.width}
                  height={bar.height}
                  class={bar.positive ? 'fill-emerald-500/40 hover:fill-emerald-500/60' : 'fill-rose-500/50 hover:fill-rose-500/70'}
                  onclick={() => (selectedMonth = bar.month)}
                  onkeydown={(e: KeyboardEvent) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      selectedMonth = bar.month
                    }
                  }}
                  role="button"
                  tabindex="0"
                  aria-label={`${shortMonth(bar.month.month)}: net ${bar.month.net_milliunits / 1000}`}
                ><title>
                  {shortMonth(bar.month.month)}: net {formatMoney(bar.month.net_milliunits)}
                </title></rect>
              {/each}
              <!-- balance polyline -->
              <polyline
                fill="none"
                stroke="currentColor"
                stroke-width="1.5"
                points={c.polyline}
                class="text-foreground"
              />
              <!-- balance dots -->
              {#each c.points as point (point.month)}
                <circle
                  cx={point.x}
                  cy={point.y}
                  r="3"
                  class={point.balance < 0 ? 'fill-rose-300' : 'fill-foreground'}
                ><title>
                  {shortMonth(point.month)} balance: {formatMoney(point.balance)}
                </title></circle>
              {/each}
              <!-- month labels -->
              {#each c.bars as bar, i (bar.month.month)}
                {#if i % 2 === 0 || i === c.bars.length - 1}
                  <text
                    x={bar.x + bar.width / 2}
                    y={CHART_HEIGHT - 8}
                    text-anchor="middle"
                    class="fill-muted-foreground text-[10px] font-mono"
                  >{shortMonth(bar.month.month)}</text>
                {/if}
              {/each}
            </svg>
          </div>
        {/if}

        <!-- Selected-month detail or hint -->
        {#if selectedMonth}
          {@const sm = selectedMonth}
          <div class="rounded-md bg-muted/15 p-4 space-y-3 text-sm">
            <div class="flex items-center justify-between gap-3">
              <div class="font-medium text-foreground">{shortMonth(sm.month)}</div>
              <button
                type="button"
                class="text-[11px] text-muted-foreground hover:text-foreground"
                onclick={() => (selectedMonth = null)}
              >clear</button>
            </div>
            <div class="grid gap-2 md:grid-cols-3 text-xs">
              <div>
                <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Inflows</div>
                <div class="mt-1 font-mono text-emerald-300">+{formatMoney(sm.inflows_milliunits)}</div>
              </div>
              <div>
                <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Outflows</div>
                <div class="mt-1 font-mono text-rose-300">−{formatMoney(sm.outflows_milliunits)}</div>
              </div>
              <div>
                <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Net</div>
                <div class={`mt-1 font-mono ${sm.net_milliunits >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                  {sm.net_milliunits >= 0 ? '+' : '−'}{formatMoney(Math.abs(sm.net_milliunits))}
                </div>
              </div>
            </div>
            {#if sm.obligation_lumps.length > 0}
              <div>
                <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Obligations</div>
                <ul class="mt-1 space-y-0.5">
                  {#each sm.obligation_lumps as lump (lump.group_name + '/' + lump.category_name)}
                    <li class="font-mono text-[11px]">
                      {lump.group_name} / {lump.category_name}: {formatMoney(lump.milliunits)}
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
            {#if sm.top_outflow_categories.length > 0}
              <div>
                <div class="text-[11px] uppercase tracking-wide text-muted-foreground">Top outflows</div>
                <ul class="mt-1 space-y-0.5">
                  {#each sm.top_outflow_categories as cat (cat.group_name + '/' + cat.category_name)}
                    <li class="font-mono text-[11px]">
                      {cat.group_name} / {cat.category_name}: {formatMoney(cat.milliunits)}
                      <span class="text-muted-foreground">({BASIS_LABELS[cat.basis]})</span>
                    </li>
                  {/each}
                </ul>
              </div>
            {/if}
          </div>
        {:else}
          <p class="text-xs text-muted-foreground">Click a bar to drill into a month's inflows, outflows, and obligations.</p>
        {/if}
      {/if}
    </CardContent>
  </Card>

  <ForecastRecommendationsCard
    recommendations={$recommendationsQuery.data}
    isLoading={$recommendationsQuery.isLoading}
    isError={$recommendationsQuery.isError}
  />

  {#if $cashflowQuery.data?.first_negative_month && $cashflowQuery.data.shortfall_drivers}
    <Card class="border-rose-500/30 bg-rose-500/[0.05]">
      <CardHeader>
        <CardTitle class="flex items-center gap-2 text-rose-100">
          <AlertTriangle class="h-4 w-4" aria-hidden="true" />
          Top shortfall drivers through {shortMonth($cashflowQuery.data.first_negative_month)}
        </CardTitle>
      </CardHeader>
      <CardContent>
        <ul class="space-y-2 text-sm">
          {#each $cashflowQuery.data.shortfall_drivers as driver (driver.group_name + '/' + driver.category_name)}
            <li class="flex items-center justify-between gap-3 rounded-md bg-muted/30 px-3 py-2">
              <div>
                <div class="font-medium text-foreground">{driver.category_name}</div>
                <div class="text-[11px] text-muted-foreground">{driver.group_name}</div>
              </div>
              <div class="flex items-center gap-3">
                <span class="font-mono text-rose-300">{formatMoney(driver.total_milliunits)}</span>
                <a
                  href={withBasePath(`/insights`)}
                  class="text-[11px] text-muted-foreground hover:text-foreground"
                >
                  View →
                </a>
              </div>
            </li>
          {/each}
        </ul>
      </CardContent>
    </Card>
  {/if}
</section>
