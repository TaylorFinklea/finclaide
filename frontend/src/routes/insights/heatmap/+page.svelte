<script lang="ts">
  import { browser } from '$app/environment'
  import { createQuery } from '@tanstack/svelte-query'
  import { ArrowLeft, Grid3x3 } from 'lucide-svelte'

  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    getActivePlan,
    getSpendingTrends,
    type PlanCategory,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'
  import { withBasePath } from '$lib/runtime'

  const planQuery = createQuery({
    queryKey: ['plan-active'],
    queryFn: () => getActivePlan(),
    enabled: browser,
  })
  const trendsQuery = createQuery({
    queryKey: ['analytics-trends-12-heatmap'],
    queryFn: () => getSpendingTrends({ months: 12 }),
    enabled: browser,
  })

  type Cell = {
    month: string
    spend_milliunits: number
    planned_milliunits: number
    variance_milliunits: number
    variance_ratio: number  // -1..+inf where 0 = on plan, +1 = double, -1 = nothing
  }

  type Row = {
    category: PlanCategory
    cells: Cell[]
    total_variance_milliunits: number
  }

  let monthLabels = $derived((): string[] => {
    const trends = $trendsQuery.data
    if (!trends) return []
    const months = new Set<string>()
    for (const cat of trends.categories) {
      for (const m of cat.months) months.add(m.month)
    }
    const list = Array.from(months).sort()
    return list.slice(-12)
  })

  let rows = $derived((): Row[] => {
    const plan = $planQuery.data
    const trends = $trendsQuery.data
    if (!plan || !trends) return []
    const months = monthLabels()
    const trendByKey = new Map<string, Map<string, number>>()
    for (const cat of trends.categories) {
      const inner = new Map<string, number>()
      for (const m of cat.months) inner.set(m.month, m.spend_milliunits)
      trendByKey.set(`${cat.group_name}|${cat.category_name}`, inner)
    }
    const eligible: PlanCategory[] = [
      ...(plan.blocks.monthly ?? []),
      ...(plan.blocks.stipends ?? []),
    ]
    const out: Row[] = []
    for (const cat of eligible) {
      const inner = trendByKey.get(`${cat.group_name}|${cat.category_name}`)
      const cells: Cell[] = months.map((month) => {
        const spend = inner?.get(month) ?? 0
        const variance = spend - cat.planned_milliunits
        const ratio = cat.planned_milliunits > 0 ? variance / cat.planned_milliunits : 0
        return {
          month,
          spend_milliunits: spend,
          planned_milliunits: cat.planned_milliunits,
          variance_milliunits: variance,
          variance_ratio: ratio,
        }
      })
      const total = cells.reduce((sum, c) => sum + c.variance_milliunits, 0)
      out.push({ category: cat, cells, total_variance_milliunits: total })
    }
    out.sort((a, b) => Math.abs(b.total_variance_milliunits) - Math.abs(a.total_variance_milliunits))
    return out
  })

  function cellStyle(cell: Cell): string {
    // Saturate at ±100% of planned. Red for over, green for under.
    if (cell.planned_milliunits === 0 && cell.spend_milliunits === 0) return 'bg-muted/10'
    if (cell.planned_milliunits === 0) {
      return 'bg-rose-500/40 text-rose-100'  // unplanned spend
    }
    const ratio = Math.max(-1, Math.min(1, cell.variance_ratio))
    if (ratio > 0.05) {
      const intensity = Math.min(1, ratio)
      const opacity = 0.15 + intensity * 0.45  // 0.15 → 0.6
      return `text-rose-100`
        + ' ' + `bg-[rgba(244,63,94,${opacity.toFixed(2)})]`
    }
    if (ratio < -0.05) {
      const intensity = Math.min(1, Math.abs(ratio))
      const opacity = 0.10 + intensity * 0.30
      return `text-emerald-100`
        + ' ' + `bg-[rgba(16,185,129,${opacity.toFixed(2)})]`
    }
    return 'bg-muted/20 text-muted-foreground'
  }

  function shortMonth(month: string): string {
    const [y, m] = month.split('-')
    const monthNames = ['', 'Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
    return `${monthNames[Number(m) ?? 0]} ${y.slice(2)}`
  }
</script>

<div class="space-y-6">
  <a
    href={withBasePath('/insights')}
    class="inline-flex items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
  >
    <ArrowLeft class="h-3.5 w-3.5" aria-hidden="true" />
    Back to Insights
  </a>

  <Card class="border-border/40 bg-card">
    <CardHeader>
      <CardTitle>
        <span class="inline-flex items-center gap-2">
          <Grid3x3 class="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          Variance heatmap
        </span>
      </CardTitle>
      <p class="text-sm text-muted-foreground">
        Per-category, per-month variance vs plan. Rose = over, emerald = under, deeper = bigger
        absolute variance. Sorted by total absolute variance.
      </p>
    </CardHeader>
    <CardContent>
      {#if $planQuery.isLoading || $trendsQuery.isLoading}
        <Skeleton class="h-64 rounded" />
      {:else if rows().length === 0}
        <p class="text-sm text-muted-foreground">No active plan or no spending in the lookback window.</p>
      {:else}
        <div class="overflow-x-auto">
          <table class="text-xs">
            <thead>
              <tr>
                <th class="sticky left-0 bg-card py-2 pr-3 text-left text-[11px] uppercase tracking-wide text-muted-foreground">Category</th>
                {#each monthLabels() as month (month)}
                  <th class="px-1 py-2 text-center font-mono text-[10px] text-muted-foreground">{shortMonth(month)}</th>
                {/each}
                <th class="px-2 py-2 text-right text-[11px] uppercase tracking-wide text-muted-foreground">Σ variance</th>
              </tr>
            </thead>
            <tbody>
              {#each rows() as row (row.category.id)}
                <tr class="border-t border-border/30">
                  <td class="sticky left-0 bg-card py-1.5 pr-3">
                    <a
                      href={withBasePath(`/insights/${row.category.id}`)}
                      class="block hover:text-foreground"
                    >
                      <div class="font-medium text-foreground">{row.category.category_name}</div>
                      <div class="text-[10px] text-muted-foreground">{row.category.group_name}</div>
                    </a>
                  </td>
                  {#each row.cells as cell (cell.month)}
                    <td
                      class={`px-1 py-1.5 text-center font-mono text-[10px] ${cellStyle(cell)}`}
                      title={`${cell.month}: ${formatMoney(cell.spend_milliunits)} vs ${formatMoney(cell.planned_milliunits)} (${cell.variance_milliunits > 0 ? '+' : ''}${formatMoney(cell.variance_milliunits)})`}
                    >
                      {cell.variance_milliunits === 0
                        ? '·'
                        : cell.variance_milliunits > 0
                          ? '+'
                          : '−'}
                    </td>
                  {/each}
                  <td class={`px-2 py-1.5 text-right font-mono text-[11px] ${row.total_variance_milliunits > 0 ? 'text-rose-300' : row.total_variance_milliunits < 0 ? 'text-emerald-300' : 'text-muted-foreground'}`}>
                    {row.total_variance_milliunits > 0 ? '+' : ''}{formatMoney(row.total_variance_milliunits)}
                  </td>
                </tr>
              {/each}
            </tbody>
          </table>
        </div>
        <div class="mt-4 flex items-center gap-4 text-[11px] text-muted-foreground">
          <span class="inline-flex items-center gap-1">
            <span class="inline-block h-3 w-3 rounded bg-emerald-500/40"></span>
            Under plan
          </span>
          <span class="inline-flex items-center gap-1">
            <span class="inline-block h-3 w-3 rounded bg-muted/20"></span>
            On plan
          </span>
          <span class="inline-flex items-center gap-1">
            <span class="inline-block h-3 w-3 rounded bg-rose-500/40"></span>
            Over plan
          </span>
        </div>
      {/if}
    </CardContent>
  </Card>
</div>
