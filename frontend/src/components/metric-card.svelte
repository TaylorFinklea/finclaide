<script lang="ts">
  import type { Snippet } from 'svelte'

  import { cn } from '$lib/utils'

  type Tone = 'neutral' | 'good' | 'warn'
  type Props = {
    label: string
    value: string
    detail?: string
    tone?: Tone
    icon?: Snippet
  }

  let { label, value, detail, tone = 'neutral', icon }: Props = $props()

  const TONE_STYLES: Record<Tone, string> = {
    neutral: 'bg-card',
    good: 'bg-emerald-500/[0.06] ring-1 ring-inset ring-emerald-500/15',
    warn: 'bg-amber-500/[0.06] ring-1 ring-inset ring-amber-500/15',
  }
</script>

<div class={cn('rounded-xl p-5 transition-colors duration-150 hover:bg-card-elevated', TONE_STYLES[tone])}>
  <div class="flex items-center justify-between">
    <span class="text-label">{label}</span>
    {@render icon?.()}
  </div>
  <div class="mt-3 font-mono text-2xl font-semibold tracking-tight text-foreground">
    {value}
  </div>
  {#if detail}
    <p class="mt-1.5 text-sm text-muted-foreground">{detail}</p>
  {/if}
</div>
