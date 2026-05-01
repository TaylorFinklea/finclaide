<script lang="ts">
  import { Activity } from 'lucide-svelte'

  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import type { MonthPace, PaceCategory } from '$lib/api'
  import { formatMoney } from '$lib/format'

  type Props = {
    pace?: MonthPace
    isLoading?: boolean
    isError?: boolean
  }
  let { pace, isLoading = false, isError = false }: Props = $props()

  let showAll = $state(false)

  const STATUS_STYLES: Record<PaceCategory['pace_status'], string> = {
    no_spend_yet: 'bg-muted/30 text-muted-foreground',
    unplanned: 'bg-rose-500/10 text-rose-300 ring-1 ring-rose-500/30',
    under_pace: 'bg-emerald-500/10 text-emerald-300 ring-1 ring-emerald-500/30',
    on_pace: 'bg-muted/40 text-muted-foreground',
    over_pace: 'bg-amber-500/10 text-amber-300 ring-1 ring-amber-500/30',
    at_risk: 'bg-rose-500/15 text-rose-300 ring-1 ring-rose-500/40',
    blowout: 'bg-rose-500/25 text-rose-200 ring-1 ring-rose-500/60',
  }

  const STATUS_LABELS: Record<PaceCategory['pace_status'], string> = {
    no_spend_yet: 'No spend yet',
    unplanned: 'Unplanned',
    under_pace: 'Under pace',
    on_pace: 'On pace',
    over_pace: 'Over pace',
    at_risk: 'At risk',
    blowout: 'Blowout',
  }

  // Surface filter — drop tiny projected overages so the card doesn't
  // get noisy from $5 categories.
  const NOISE_THRESHOLD_MILLIUNITS = 25_000

  let surfaced = $derived(() => {
    if (!pace) return []
    return pace.categories.filter(
      (c) =>
        c.pace_status === 'unplanned' ||
        c.pace_status === 'blowout' ||
        c.pace_status === 'at_risk' ||
        c.projected_overage_milliunits >= NOISE_THRESHOLD_MILLIUNITS,
    )
  })
  let visible = $derived(showAll ? surfaced() : surfaced().slice(0, 5))

  function formatPaceFactor(factor: number): string {
    if (factor < 0) return '—'
    if (factor === 0) return '0×'
    return `${factor.toFixed(2)}×`
  }
</script>

<Card class="border-border/40 bg-card">
  <CardHeader>
    <div class="flex items-center justify-between gap-3">
      <CardTitle>
        <span class="inline-flex items-center gap-2">
          <Activity class="h-4 w-4 text-muted-foreground" aria-hidden="true" />
          Mid-month pace
        </span>
      </CardTitle>
      {#if pace}
        <span class="text-xs text-muted-foreground">
          {pace.month} · day {pace.days_elapsed} of {pace.days_total} · {pace.days_remaining} remaining
        </span>
      {/if}
    </div>
  </CardHeader>
  <CardContent class="space-y-3">
    {#if isLoading}
      <Skeleton class="h-32 rounded" />
    {:else if isError}
      <p class="text-sm text-rose-300">Could not load mid-month pace.</p>
    {:else if !pace}
      <p class="text-sm text-muted-foreground">No pace data yet.</p>
    {:else if pace.warming_up}
      <p class="text-sm text-muted-foreground">
        Pace data warming up — at least 3 days of activity needed.
      </p>
    {:else if visible.length === 0}
      <p class="text-sm text-muted-foreground">
        Every monthly + stipends category is on pace or under-pace.
      </p>
    {:else}
      <table class="w-full text-sm">
        <thead>
          <tr class="text-left text-[11px] uppercase tracking-wide text-muted-foreground">
            <th class="py-2 pr-3">Category</th>
            <th class="py-2 pr-3 text-right">Spent / planned</th>
            <th class="py-2 pr-3 text-right">Pace</th>
            <th class="py-2 pr-3 text-right">Projected overage</th>
            <th class="py-2 pr-1 text-right">Status</th>
          </tr>
        </thead>
        <tbody>
          {#each visible as row (row.category_id)}
            <tr class="border-t border-border/30">
              <td class="py-2 pr-3">
                <div class="font-medium text-foreground">{row.category_name}</div>
                <div class="text-[11px] text-muted-foreground">{row.group_name}</div>
              </td>
              <td class="py-2 pr-3 text-right font-mono text-xs">
                {formatMoney(row.actual_milliunits)} / {formatMoney(row.planned_milliunits)}
              </td>
              <td class="py-2 pr-3 text-right font-mono text-xs">
                {formatPaceFactor(row.pace_factor)}
              </td>
              <td class="py-2 pr-3 text-right font-mono text-xs">
                {row.projected_overage_milliunits > 0
                  ? `+${formatMoney(row.projected_overage_milliunits)}`
                  : formatMoney(row.projected_overage_milliunits)}
              </td>
              <td class="py-2 pr-1 text-right">
                <span class={`inline-block rounded-md px-2 py-0.5 text-[11px] font-medium ${STATUS_STYLES[row.pace_status]}`}>
                  {STATUS_LABELS[row.pace_status]}
                </span>
              </td>
            </tr>
          {/each}
        </tbody>
      </table>
      {#if !showAll && surfaced().length > 5}
        <button
          type="button"
          class="text-xs text-muted-foreground underline-offset-2 hover:underline"
          onclick={() => (showAll = true)}
        >
          Show all {surfaced().length}
        </button>
      {/if}
    {/if}
  </CardContent>
</Card>
