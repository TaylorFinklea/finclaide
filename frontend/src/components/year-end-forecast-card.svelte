<script lang="ts">
  import { TrendingUp } from 'lucide-svelte'

  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import type { YearEndProjection } from '$lib/api'
  import { formatMoney } from '$lib/format'

  type Props = {
    projection?: YearEndProjection
    isLoading?: boolean
    isError?: boolean
  }
  let { projection, isLoading = false, isError = false }: Props = $props()

  // Top categories sorted by projected variance (worst overshoots first).
  // Filter to only meaningful overages — anything projected to come in
  // ≤ planned is kept off the card.
  const FORECAST_NOISE_THRESHOLD = 50_000

  let topMovers = $derived(() => {
    if (!projection) return []
    return [...projection.categories]
      .filter((c) => c.projected_variance_milliunits >= FORECAST_NOISE_THRESHOLD)
      .sort(
        (a, b) =>
          b.projected_variance_milliunits - a.projected_variance_milliunits,
      )
      .slice(0, 3)
  })

  let totalsHasData = $derived(() => {
    if (!projection) return false
    return 'planned_annual_milliunits' in (projection.totals as Record<string, number>)
  })
</script>

<Card class="border-border/40 bg-card">
  <CardHeader>
    <CardTitle>
      <span class="inline-flex items-center gap-2">
        <TrendingUp class="h-4 w-4 text-muted-foreground" aria-hidden="true" />
        Year-end forecast
      </span>
    </CardTitle>
  </CardHeader>
  <CardContent class="space-y-3">
    {#if isLoading}
      <Skeleton class="h-24 rounded" />
    {:else if isError}
      <p class="text-sm text-rose-300">Could not load year-end forecast.</p>
    {:else if !projection || projection.plan_year === null}
      <p class="text-sm text-muted-foreground">
        Import a budget to see year-end forecasts.
      </p>
    {:else if topMovers().length === 0}
      <p class="text-sm text-muted-foreground">
        No categories projected to bust their annual target.
      </p>
    {:else}
      <ul class="space-y-2 text-sm">
        {#each topMovers() as row}
          <li class="flex items-center justify-between gap-3">
            <div class="min-w-0">
              <div class="truncate font-medium text-foreground">{row.category_name}</div>
              <div class="text-[11px] text-muted-foreground">{row.group_name}</div>
            </div>
            <div class="text-right font-mono text-xs">
              <div class="text-rose-300">+{formatMoney(row.projected_variance_milliunits)}</div>
              <div class="text-muted-foreground">
                {formatMoney(row.projected_annual_milliunits)} / {formatMoney(row.planned_annual_milliunits)}
              </div>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
    {#if projection && totalsHasData()}
      {@const totals = projection.totals as { planned_annual_milliunits: number; projected_annual_milliunits: number; projected_variance_milliunits: number }}
      <div class="flex items-center justify-between border-t border-border/30 pt-3 text-xs">
        <span class="text-muted-foreground">
          Year-end projected {formatMoney(totals.projected_annual_milliunits)}
        </span>
        <span
          class={`font-mono ${totals.projected_variance_milliunits > 0 ? 'text-rose-300' : 'text-emerald-300'}`}
        >
          {totals.projected_variance_milliunits > 0 ? '+' : ''}
          {formatMoney(totals.projected_variance_milliunits)} vs plan
        </span>
      </div>
    {/if}
  </CardContent>
</Card>
