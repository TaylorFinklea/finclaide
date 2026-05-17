<script lang="ts">
  import { Sparkles, ArrowUp } from 'lucide-svelte'

  let {
    contextLabel = 'Finclaide',
    placeholder = 'Ask Finclaide anything…',
    available = false,
  }: {
    contextLabel?: string
    placeholder?: string
    available?: boolean
  } = $props()

  let prompt = $state('')

  function onSubmit(event: SubmitEvent): void {
    event.preventDefault()
    // Wired in task #17. Until then the rail renders a quiet input that
    // signals presence without firing anything.
    prompt = ''
  }
</script>

<aside
  class="grid h-screen w-[360px] shrink-0 grid-rows-[auto_auto_1fr_auto] overflow-hidden border-l border-border bg-card"
>
  <div class="flex items-center justify-between border-b border-border px-5 py-4">
    <div class="flex items-center gap-2 text-sm font-semibold">
      <span
        class="inline-block h-[22px] w-[22px] rounded-md bg-gradient-to-br from-[#4E46E5] to-[#6E64FF]"
        aria-hidden="true"
      ></span>
      Finclaide
    </div>
    <div class="text-[11px] text-muted-foreground">Haiku 4.5</div>
  </div>

  <div class="flex flex-col gap-1 border-b border-border bg-secondary/60 px-5 py-3">
    <div class="flex justify-between text-xs text-muted-foreground">
      <span>Context</span>
      <span class="text-foreground">{contextLabel}</span>
    </div>
    <div class="flex justify-between text-xs text-muted-foreground">
      <span>Rail</span>
      <span class={available ? 'text-foreground' : 'text-[#C68A21]'}>
        {available ? 'Ready' : 'Awaiting key'}
      </span>
    </div>
  </div>

  <div class="overflow-y-auto px-5 py-5">
    {#if available}
      <div class="text-sm text-muted-foreground">
        <Sparkles class="mb-2 inline h-4 w-4 text-[#4E46E5]" />
        <p>
          Ask about your plan, your spend, your runway. I can compare months,
          surface what changed, and suggest rebalances. I cannot edit the plan
          or sync YNAB — use the Plan and Operate screens for those.
        </p>
      </div>
    {:else}
      <div class="rounded-lg border border-[#FBF1DC] bg-[#FBF1DC]/40 p-4 text-xs text-[#C68A21]">
        Set <code class="rounded bg-background px-1 py-0.5 font-mono text-[11px] text-foreground">ANTHROPIC_API_KEY</code>
        in <code class="rounded bg-background px-1 py-0.5 font-mono text-[11px] text-foreground">.env</code>
        to enable the rail. The rest of the dashboard works without it.
      </div>
    {/if}
  </div>

  <form class="border-t border-border px-4 py-3" onsubmit={onSubmit}>
    <div class="flex items-center gap-2 rounded-xl border border-border bg-secondary/60 px-3 py-2">
      <input
        type="text"
        class="flex-1 bg-transparent text-sm outline-none placeholder:text-muted-foreground"
        {placeholder}
        bind:value={prompt}
        disabled={!available}
      />
      <button
        type="submit"
        class="grid h-6 w-6 place-items-center rounded-md bg-[#4E46E5] text-white disabled:opacity-30"
        disabled={!available || prompt.length === 0}
        aria-label="Send"
      >
        <ArrowUp class="h-3 w-3" />
      </button>
    </div>
    <div class="mt-1.5 text-[11px] text-muted-foreground">
      Try: <b class="text-foreground/80">compare lifestyle to last quarter</b>,
      <b class="text-foreground/80">why is therapy 0</b>
    </div>
  </form>
</aside>
