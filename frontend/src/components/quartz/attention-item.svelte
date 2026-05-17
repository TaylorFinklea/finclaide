<script lang="ts">
  import type { Snippet } from 'svelte'

  type Severity = 'crit' | 'warn' | 'info' | 'good'

  let {
    title,
    why,
    severity = 'info',
    delta,
    children,
    highlight = false,
  }: {
    title: string
    why?: string
    severity?: Severity
    delta?: string
    children?: Snippet
    highlight?: boolean
  } = $props()

  const chipClass = {
    crit: 'bg-[#FBECEC] text-[#D14444]',
    warn: 'bg-[#FBF1DC] text-[#C68A21]',
    info: 'bg-[#E8F0FC] text-[#2A6FDB]',
    good: 'bg-[#E7F2EC] text-[#2F8A57]',
  } as const
</script>

<div
  class="grid items-baseline gap-y-1 gap-x-2.5 rounded-xl border p-3 {highlight
    ? 'border-[#D14444]/20 bg-[#FBECEC]'
    : 'border-border bg-card'}"
  style="grid-template-columns: 1fr auto"
>
  <div class="font-medium text-foreground">{title}</div>
  <div
    class="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide {chipClass[severity]}"
  >
    {severity}
  </div>
  {#if why}
    <div class="col-span-2 text-[12.5px] text-foreground/80">{why}</div>
  {/if}
  {#if delta || children}
    <div class="col-span-2 mt-1 flex items-center gap-2 text-[11px] text-muted-foreground">
      {#if delta}
        <span class="font-medium text-foreground/80">{delta}</span>
      {/if}
      {#if children}{@render children()}{/if}
    </div>
  {/if}
</div>
