<script lang="ts">
  import type { CompareResponse } from '$lib/api'
  import { formatMoney } from '$lib/format'

  import SectionHeading from './section-heading.svelte'

  let {
    compare,
    fromLabel,
    toLabel,
  }: {
    compare: CompareResponse | undefined
    fromLabel: string
    toLabel: string
  } = $props()

  // Only rows where the scenario actually moved the plan are real diffs.
  let diffRows = $derived(
    (compare?.rows ?? []).filter((r) => r.vs_active_milliunits !== 0),
  )
  let net = $derived(compare?.totals.vs_active_milliunits ?? 0)
</script>

<div class="rounded-xl border border-border bg-card p-[18px]">
  <SectionHeading title="Diff" meta={`${fromLabel} → ${toLabel}`} />
  {#if !compare}
    <div class="py-3 text-xs text-muted-foreground">No draft to compare.</div>
  {:else if diffRows.length === 0}
    <div class="py-3 text-xs text-muted-foreground">No changes staged yet.</div>
  {:else}
    <div class="text-sm">
      {#each diffRows as row (row.category_id)}
        {@const positive = row.vs_active_milliunits > 0}
        <div
          class="grid items-baseline gap-2 border-b border-dashed border-border py-2.5 last:border-b-0"
          style="grid-template-columns: 16px 1fr auto"
        >
          <span class="text-base font-semibold" style="color:{positive ? '#2F8A57' : '#D14444'}">
            {positive ? '+' : '−'}
          </span>
          <span class="truncate">
            <span class="text-muted-foreground">{row.group} /</span>
            {row.name}
          </span>
          <span class="tabular-nums" style="color:{positive ? '#2F8A57' : '#D14444'}">
            {formatMoney(row.planned_active_milliunits).replace('.00', '')}
            <span class="text-muted-foreground"> &rarr; </span>
            {formatMoney(row.planned_scenario_milliunits).replace('.00', '')}
          </span>
        </div>
      {/each}
      <div
        class="mt-2 grid items-baseline gap-2 pt-2"
        style="grid-template-columns: 16px 1fr auto"
      >
        <span class="text-muted-foreground">=</span>
        <span class="text-foreground/80">Net monthly</span>
        <span class="font-semibold tabular-nums {net === 0 ? '' : net > 0 ? 'text-[#D14444]' : 'text-[#2F8A57]'}">
          {net === 0 ? '$0' : (net > 0 ? '+' : '') + formatMoney(net).replace('.00', '')}
        </span>
      </div>
    </div>
  {/if}
</div>
