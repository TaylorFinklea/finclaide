<script lang="ts">
  import type { Snippet } from 'svelte'

  let {
    title,
    value,
    unit,
    sub,
    subtone = 'muted',
    children,
  }: {
    title: string
    value: string
    unit?: string
    sub?: string
    subtone?: 'muted' | 'pos' | 'neg' | 'warn'
    children?: Snippet
  } = $props()

  const subToneClass = {
    muted: 'text-muted-foreground',
    pos: 'text-[#2F8A57] font-medium',
    neg: 'text-[#D14444] font-medium',
    warn: 'text-[#C68A21] font-medium',
  } as const
</script>

<div class="relative rounded-xl border border-border bg-card p-[18px]">
  <div class="text-[11px] font-medium uppercase tracking-[0.04em] text-muted-foreground">
    {title}
  </div>
  <div class="mt-1.5 text-[28px] font-semibold leading-none tracking-[-0.02em] tabular-nums">
    {value}
    {#if unit}
      <span class="text-base font-medium text-muted-foreground">{unit}</span>
    {/if}
  </div>
  {#if sub}
    <div class="mt-1.5 flex items-center gap-2 text-xs">
      <span class={subToneClass[subtone]}>{sub}</span>
    </div>
  {/if}
  {#if children}
    <div class="mt-2.5">{@render children()}</div>
  {/if}
</div>
