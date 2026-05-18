<script lang="ts">
  import SectionHeading from './section-heading.svelte'

  export type PlanHistoryEntry = {
    label: string
    note: string
    who: string
    when: string
    active?: boolean
  }

  let {
    entries,
    onOpen,
  }: {
    entries: PlanHistoryEntry[]
    onOpen?: () => void
  } = $props()
</script>

<div class="rounded-xl border border-border bg-card p-[18px]">
  <SectionHeading title="Plan history">
    {#snippet actions()}
      {#if onOpen}
        <button
          type="button"
          class="text-[11px] underline hover:text-foreground"
          onclick={onOpen}
        >
          Open timeline
        </button>
      {/if}
    {/snippet}
  </SectionHeading>
  <div class="flex flex-col gap-1.5">
    {#if entries.length === 0}
      <div class="text-xs text-muted-foreground">No history yet.</div>
    {/if}
    {#each entries as entry (entry.label)}
      <div
        class="grid items-baseline gap-2 rounded-lg px-2.5 py-2"
        class:border={entry.active}
        style="
          grid-template-columns: 60px 1fr auto;
          {entry.active ? 'background: #EDEBFF; border-color: #4E46E5;' : ''}
        "
      >
        <span
          class="font-semibold tabular-nums"
          style="color:{entry.active ? '#4E46E5' : 'inherit'}"
        >
          {entry.label}
        </span>
        <span class="text-xs text-foreground/80">
          {entry.note}
          <span class="text-muted-foreground"> · {entry.who}</span>
        </span>
        <span class="text-[11px] text-muted-foreground">{entry.when}</span>
      </div>
    {/each}
  </div>
</div>
