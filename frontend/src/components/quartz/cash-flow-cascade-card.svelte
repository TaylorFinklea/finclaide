<script lang="ts">
  import type { ActivePlanResponse } from '$lib/api'
  import { formatMoney } from '$lib/format'

  import SectionHeading from './section-heading.svelte'

  type BlockKey = 'monthly' | 'annual' | 'one_time' | 'stipends' | 'savings'

  const BLOCK_ORDER: BlockKey[] = ['monthly', 'annual', 'one_time', 'stipends', 'savings']
  const BLOCK_LABELS: Record<BlockKey, string> = {
    monthly: 'Monthly',
    annual: 'Annual',
    one_time: 'One-time',
    stipends: 'Stipends',
    savings: 'Savings',
  }

  let { plan }: { plan: ActivePlanResponse | undefined } = $props()

  type CascadeStep = { block: BlockKey; outflow: number; remaining_after: number }
  type Cascade = { inflow: number; steps: CascadeStep[]; leftover: number }

  let cascade = $derived.by<Cascade | null>(() => {
    if (!plan) return null
    let inflow = 0
    const outflowByBlock: Record<BlockKey, number> = {
      monthly: 0, annual: 0, one_time: 0, stipends: 0, savings: 0,
    }
    for (const block of BLOCK_ORDER) {
      for (const cat of plan.blocks[block]) {
        if (cat.kind === 'inflow') inflow += cat.planned_milliunits
        else outflowByBlock[block] += cat.planned_milliunits
      }
    }
    const steps: CascadeStep[] = []
    let running = inflow
    for (const block of BLOCK_ORDER) {
      running -= outflowByBlock[block]
      steps.push({ block, outflow: outflowByBlock[block], remaining_after: running })
    }
    return { inflow, steps, leftover: running }
  })
</script>

<div class="rounded-xl border border-border bg-card p-[18px]">
  <SectionHeading title="Cash flow cascade" meta="Where income lands each month" />
  {#if !cascade}
    <div class="py-3 text-xs text-muted-foreground">No active plan to cascade.</div>
  {:else}
    <div class="flex flex-col gap-1 text-sm">
      <div class="flex items-baseline justify-between rounded-md px-2 py-1.5">
        <span class="font-medium">Income</span>
        <span class="font-mono tabular-nums text-[#2F8A57]">
          +{formatMoney(cascade.inflow).replace('.00', '')} / mo
        </span>
      </div>
      {#each cascade.steps as step (step.block)}
        <div
          class="flex items-baseline justify-between rounded-md px-2 py-1.5"
          class:bg-secondary={step.outflow > 0}
        >
          <span class="text-muted-foreground">− {BLOCK_LABELS[step.block]}</span>
          <span class="font-mono tabular-nums">
            {step.outflow > 0
              ? `−${formatMoney(step.outflow).replace('.00', '')}`
              : '—'}
            <span class="ml-2 text-muted-foreground">
              {formatMoney(step.remaining_after).replace('.00', '')} left
            </span>
          </span>
        </div>
      {/each}
      <div
        class="mt-2 flex items-baseline justify-between rounded-md border-t border-border px-2 pt-2.5"
      >
        <span class="font-medium">Leftover</span>
        <span
          class="font-mono font-semibold tabular-nums {cascade.leftover < 0
            ? 'text-[#D14444]'
            : 'text-foreground'}"
        >
          {formatMoney(cascade.leftover).replace('.00', '')} / mo
        </span>
      </div>
      {#if cascade.leftover < 0}
        <p class="mt-1 text-[11px] text-[#D14444]">
          The plan spends more than it brings in — adjust on the Plan editor.
        </p>
      {/if}
    </div>
  {/if}
</div>
