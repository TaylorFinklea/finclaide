<script lang="ts">
  type Confidence = 'low' | 'medium' | 'high'

  let {
    title,
    why,
    confidence = 'medium',
    onStage,
    onDismiss,
  }: {
    title: string
    why?: string
    confidence?: Confidence
    onStage?: () => void
    onDismiss?: () => void
  } = $props()

  const chip = {
    high: 'bg-[#E7F2EC] text-[#2F8A57]',
    medium: 'bg-[#E8F0FC] text-[#2A6FDB]',
    low: 'bg-[#FBF1DC] text-[#C68A21]',
  } as const
</script>

<div
  class="grid items-baseline gap-y-1 gap-x-2.5 rounded-xl border border-border bg-card p-3"
  style="grid-template-columns: 1fr auto"
>
  <div class="font-medium text-foreground">{title}</div>
  <div class="rounded-full px-2 py-0.5 text-[10px] font-medium uppercase tracking-wide {chip[confidence]}">
    {confidence}
  </div>
  {#if why}
    <div class="col-span-2 text-[12.5px] text-foreground/80">{why}</div>
  {/if}
  <div class="col-span-2 mt-1 flex gap-1.5">
    <button
      type="button"
      class="rounded-md bg-[#4E46E5] px-2.5 py-1 text-[11px] font-medium text-white transition-opacity hover:opacity-90 disabled:opacity-40"
      onclick={onStage}
      disabled={!onStage}
    >
      Stage in sandbox
    </button>
    <button
      type="button"
      class="rounded-md border border-border bg-card px-2.5 py-1 text-[11px] font-medium text-foreground transition-colors hover:bg-secondary disabled:opacity-40"
      onclick={onDismiss}
      disabled={!onDismiss}
    >
      Dismiss
    </button>
  </div>
</div>
