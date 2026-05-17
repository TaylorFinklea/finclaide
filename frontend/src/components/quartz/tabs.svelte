<script lang="ts" generics="T extends string">
  type Tab = { value: T; label: string }

  let {
    tabs,
    value = $bindable(),
  }: {
    tabs: readonly Tab[]
    value: T
  } = $props()
</script>

<div
  class="inline-flex gap-1 rounded-lg border border-border bg-background p-1"
  role="tablist"
>
  {#each tabs as tab (tab.value)}
    {@const active = tab.value === value}
    <button
      type="button"
      role="tab"
      aria-selected={active}
      class="rounded-md px-3.5 py-[5px] text-[12.5px] font-medium transition-colors
        {active
          ? 'bg-card text-foreground shadow-[0_1px_2px_rgba(0,0,0,0.04)]'
          : 'text-muted-foreground hover:text-foreground'}"
      onclick={() => (value = tab.value)}
    >
      {tab.label}
    </button>
  {/each}
</div>
