<script lang="ts">
  import type { Snippet } from 'svelte'

  let {
    title,
    meta,
    actions,
  }: {
    title: string
    meta?: string
    actions?: Snippet
  } = $props()
</script>

<div class="mb-2.5 flex items-baseline justify-between">
  <h3 class="m-0 text-sm font-semibold tracking-[-0.01em]">{title}</h3>
  <div class="text-[11px] text-muted-foreground">
    {#if actions}{@render actions()}{:else if meta}{meta}{/if}
  </div>
</div>
