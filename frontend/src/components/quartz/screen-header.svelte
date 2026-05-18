<script lang="ts">
  import type { Snippet } from 'svelte'

  type Tone = 'review' | 'plan' | 'operate' | 'explore'

  let {
    pill,
    title,
    subtitle,
    tone = 'review',
    actions,
  }: {
    pill: string
    title: string
    subtitle?: string
    tone?: Tone
    actions?: Snippet
  } = $props()

  // Pill dot color cues the workflow mode at a glance.
  const TONE_DOT = {
    review: '#2F8A57',
    plan: '#4E46E5',
    operate: '#C68A21',
    explore: '#2A6FDB',
  } as const
  let dotColor = $derived(TONE_DOT[tone])
</script>

<header class="flex items-center justify-between">
  <div>
    <div
      class="mb-2 inline-flex items-center gap-1.5 rounded-full border border-border bg-card px-2.5 py-1 text-xs text-foreground/70"
    >
      <span class="h-1.5 w-1.5 rounded-full" style="background:{dotColor}"></span>
      {pill}
    </div>
    <h1 class="flex items-baseline gap-3 text-[22px] font-semibold tracking-[-0.015em]">
      {title}
      {#if subtitle}
        <span class="text-sm font-normal text-muted-foreground">{subtitle}</span>
      {/if}
    </h1>
  </div>
  {#if actions}
    <div class="flex items-center gap-2">{@render actions()}</div>
  {/if}
</header>
