<script lang="ts">
  let {
    name,
    subtitle,
    accent,
    planned,
    actual,
    formatMoney,
  }: {
    name: string
    subtitle?: string
    accent: string
    planned: number
    actual: number
    formatMoney: (cents: number, opts?: { signed?: boolean }) => string
  } = $props()

  let variance = $derived(actual - planned)
  let pct = $derived(planned > 0 ? Math.round((actual / planned) * 100) : 0)
  let max = $derived(Math.max(planned, actual))
  let actualPct = $derived(max > 0 ? (actual / max / 1.05) * 100 : 0)
  let plannedPct = $derived(max > 0 ? (planned / max / 1.05) * 100 : 0)
  let fillColor = $derived(variance > 0 ? 'rgba(209,68,68,0.7)' : accent)
</script>

<div
  class="grid items-center gap-3 border-b border-border py-[9px] text-sm last:border-b-0"
  style="grid-template-columns: 24px 130px 1fr 90px 80px"
>
  <span class="block h-2.5 w-2.5 rounded-[3px]" style="background:{accent}" aria-hidden="true"></span>
  <div>
    <div class="font-medium text-foreground">{name}</div>
    {#if subtitle}
      <div class="text-[11px] text-muted-foreground">{subtitle}</div>
    {/if}
  </div>
  <div class="relative h-2 overflow-hidden rounded-full bg-secondary">
    <div
      class="absolute inset-y-0 left-0 rounded-full"
      style="width:{actualPct}%; background:{fillColor}"
    ></div>
    <div
      class="absolute -top-[3px] -bottom-[3px] w-[2px] rounded-[1px] bg-muted-foreground"
      style="left:{plannedPct}%"
      aria-label="planned target"
    ></div>
  </div>
  <div class="text-right text-sm tabular-nums">{formatMoney(actual)}</div>
  <div
    class="text-right text-xs tabular-nums {variance > 0 ? 'text-[#D14444]' : 'text-[#2F8A57]'}"
  >
    {formatMoney(variance, { signed: true })}
    <span class="text-muted-foreground">· {pct}%</span>
  </div>
</div>
