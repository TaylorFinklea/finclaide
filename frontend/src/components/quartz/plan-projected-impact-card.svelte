<script lang="ts">
  import { formatCompactMoney, formatMoney } from '$lib/format'

  import SectionHeading from './section-heading.svelte'

  let {
    beforeMilliunits,
    afterMilliunits,
    planMilliunits,
    confidenceNote,
  }: {
    // Projected close in milliunits — before this draft and after it lands.
    beforeMilliunits: number | undefined
    afterMilliunits: number | undefined
    // Planned year-end so we can show "+$X over plan" deltas.
    planMilliunits: number | undefined
    confidenceNote?: string
  } = $props()

  function deltaVsPlan(actual: number | undefined, plan: number | undefined): string {
    if (actual == null || plan == null) return ''
    const d = actual - plan
    if (d === 0) return 'on plan'
    return `${d > 0 ? '+' : ''}${formatMoney(d).replace('.00', '')} ${d > 0 ? 'over' : 'under'} plan`
  }

  let beforeDelta = $derived(deltaVsPlan(beforeMilliunits, planMilliunits))
  let afterDelta = $derived(deltaVsPlan(afterMilliunits, planMilliunits))
  let vsBefore = $derived(
    beforeMilliunits != null && afterMilliunits != null
      ? afterMilliunits - beforeMilliunits
      : null,
  )
</script>

<div class="rounded-xl border border-border bg-card p-[18px]">
  <SectionHeading title="Projected impact" meta="vs current actual" />
  <div class="mt-1 grid gap-3" style="grid-template-columns: 1fr 1fr">
    <div class="rounded-xl border border-border p-3">
      <div class="text-[11px] uppercase tracking-[0.05em] text-muted-foreground">Before</div>
      <div class="mt-1 text-[22px] font-semibold leading-none tabular-nums">
        {beforeMilliunits != null ? formatCompactMoney(beforeMilliunits) : '—'}
      </div>
      <div class="mt-1 text-xs text-[#C68A21]">{beforeDelta || '—'}</div>
    </div>
    <div class="rounded-xl border border-[#4E46E5] bg-[#EDEBFF] p-3">
      <div class="text-[11px] uppercase tracking-[0.05em] text-[#4E46E5]">After</div>
      <div class="mt-1 text-[22px] font-semibold leading-none tabular-nums">
        {afterMilliunits != null ? formatCompactMoney(afterMilliunits) : '—'}
      </div>
      <div class="mt-1 text-xs text-[#2F8A57]">
        {afterDelta || '—'}
        {#if vsBefore != null && vsBefore !== 0}
          · {vsBefore > 0 ? '+' : ''}{formatMoney(vsBefore).replace('.00', '')} vs before
        {/if}
      </div>
    </div>
  </div>
  {#if confidenceNote}
    <p class="mt-3 text-xs text-foreground/80">{confidenceNote}</p>
  {/if}
</div>
