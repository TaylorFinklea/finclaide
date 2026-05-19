<script lang="ts">
  import { ArrowUp, PanelRightClose, Sparkles, Wrench, AlertTriangle } from 'lucide-svelte'

  import { AIUnavailableError, streamChat, type AIChatMessage } from '$lib/ai/ai-client'
  import { monthStore } from '$lib/stores/month.svelte'

  let {
    contextLabel = 'Finclaide',
    placeholder = 'Ask Finclaide anything…',
    available = $bindable(true),
    onClose,
  }: {
    contextLabel?: string
    placeholder?: string
    available?: boolean
    onClose?: () => void
  } = $props()

  type ToolCall = {
    id: string
    name: string
    input: Record<string, unknown>
    result?: unknown
    isError?: boolean
    pending: boolean
  }

  type Turn = {
    role: 'user' | 'assistant'
    text: string
    tools: ToolCall[]
  }

  let turns = $state<Turn[]>([])
  let prompt = $state('')
  let busy = $state(false)
  let errorBanner = $state<string | null>(null)

  function buildChatMessages(): AIChatMessage[] {
    const out: AIChatMessage[] = []
    for (const turn of turns) {
      if (turn.role === 'user') {
        out.push({ role: 'user', content: turn.text })
        continue
      }
      const blocks: Array<Record<string, unknown>> = []
      if (turn.text) blocks.push({ type: 'text', text: turn.text })
      for (const tool of turn.tools) {
        blocks.push({ type: 'tool_use', id: tool.id, name: tool.name, input: tool.input })
      }
      if (blocks.length > 0) {
        out.push({ role: 'assistant', content: blocks })
      }
      const toolResults = turn.tools
        .filter((t) => t.result !== undefined)
        .map((t) => ({
          type: 'tool_result',
          tool_use_id: t.id,
          content: JSON.stringify(t.result),
          is_error: !!t.isError,
        }))
      if (toolResults.length > 0) {
        out.push({ role: 'user', content: toolResults })
      }
    }
    return out
  }

  async function onSubmit(event: SubmitEvent): Promise<void> {
    event.preventDefault()
    const trimmed = prompt.trim()
    if (!trimmed || busy) return
    errorBanner = null
    prompt = ''
    turns.push({ role: 'user', text: trimmed, tools: [] })
    const messages = buildChatMessages()
    const assistant: Turn = { role: 'assistant', text: '', tools: [] }
    turns.push(assistant)
    busy = true

    try {
      for await (const event_ of streamChat(messages, { month: monthStore.value })) {
        if (event_.type === 'text_delta') {
          assistant.text += event_.delta
        } else if (event_.type === 'tool_use') {
          assistant.tools.push({
            id: event_.id,
            name: event_.name,
            input: event_.input,
            pending: true,
          })
        } else if (event_.type === 'tool_result') {
          const tool = assistant.tools.find((t) => t.id === event_.id)
          if (tool) {
            tool.result = event_.result
            tool.isError = event_.is_error
            tool.pending = false
          }
        } else if (event_.type === 'error') {
          errorBanner = event_.message
          break
        } else if (event_.type === 'done') {
          break
        }
      }
    } catch (err) {
      if (err instanceof AIUnavailableError) {
        available = false
        errorBanner = err.message
      } else {
        errorBanner = err instanceof Error ? err.message : 'AI request failed'
      }
    } finally {
      busy = false
    }
  }

  function summariseToolResult(value: unknown, depth = 0): string {
    if (value == null) return 'no data'
    if (typeof value !== 'object') return String(value)
    const entries = Object.entries(value as Record<string, unknown>)
    if (entries.length === 0) return '∅'
    if (depth >= 2) return `${entries.length} fields`
    return entries
      .slice(0, 3)
      .map(([k, v]) => `${k}: ${summariseToolResult(v, depth + 1)}`)
      .join(' · ')
  }

  let canSubmit = $derived(available && !busy && prompt.trim().length > 0)
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
    <div class="flex items-center gap-2">
      <span class="text-[11px] text-muted-foreground">Haiku 4.5</span>
      {#if onClose}
        <button
          type="button"
          class="grid h-6 w-6 place-items-center rounded-md text-muted-foreground transition-colors hover:bg-secondary hover:text-foreground"
          aria-label="Close AI rail"
          title="Close AI rail"
          onclick={onClose}
        >
          <PanelRightClose class="h-3.5 w-3.5" />
        </button>
      {/if}
    </div>
  </div>

  <div class="flex flex-col gap-1 border-b border-border bg-secondary/60 px-5 py-3">
    <div class="flex justify-between text-xs text-muted-foreground">
      <span>Context</span>
      <span class="text-foreground">{contextLabel}</span>
    </div>
    <div class="flex justify-between text-xs text-muted-foreground">
      <span>Rail</span>
      <span class={available ? 'text-foreground' : 'text-[#C68A21]'}>
        {available ? (busy ? 'Streaming…' : 'Ready') : 'Awaiting key'}
      </span>
    </div>
  </div>

  <div class="overflow-y-auto px-5 py-5">
    {#if !available}
      <div class="rounded-lg border border-[#FBF1DC] bg-[#FBF1DC]/40 p-4 text-xs text-[#C68A21]">
        Set <code class="rounded bg-background px-1 py-0.5 font-mono text-[11px] text-foreground">ANTHROPIC_API_KEY</code>
        in <code class="rounded bg-background px-1 py-0.5 font-mono text-[11px] text-foreground">.env</code>
        to enable the rail. The rest of the dashboard works without it.
      </div>
    {:else if turns.length === 0}
      <div class="text-sm text-muted-foreground">
        <Sparkles class="mb-2 inline h-4 w-4 text-[#4E46E5]" />
        <p>
          Ask about your plan, your spend, or what changed. I can compare
          months, surface what's drifted, and suggest rebalances. I'm
          read-only — use Plan and Operate for edits.
        </p>
      </div>
    {:else}
      <div class="flex flex-col gap-4">
        {#each turns as turn, i (i)}
          <div class={turn.role === 'user' ? 'self-end' : ''}>
            <div class="mb-1 text-[11px] font-medium tracking-wide {turn.role === 'assistant' ? 'text-[#4E46E5]' : 'text-muted-foreground'}">
              {turn.role === 'user' ? 'You' : 'Finclaide'}
            </div>
            {#if turn.role === 'user'}
              <div class="rounded-xl bg-secondary px-3 py-2 text-[13.5px] leading-snug">
                {turn.text}
              </div>
            {:else}
              {#if turn.text}
                <div class="whitespace-pre-wrap text-[13.5px] leading-snug">{turn.text}</div>
              {/if}
              {#each turn.tools as tool (tool.id)}
                <div class="mt-2 rounded-lg border border-border bg-secondary/60 p-2 text-[11px] text-foreground/80">
                  <div class="flex items-center gap-1.5 font-medium">
                    <Wrench class="h-3 w-3" />
                    {tool.name}
                    {#if tool.pending}<span class="text-muted-foreground">…</span>{/if}
                  </div>
                  {#if tool.result !== undefined}
                    <div class="mt-1 line-clamp-2 text-muted-foreground">
                      {tool.isError ? '⚠ ' : ''}{summariseToolResult(tool.result)}
                    </div>
                  {/if}
                </div>
              {/each}
            {/if}
          </div>
        {/each}
        {#if errorBanner}
          <div class="flex items-start gap-2 rounded-lg border border-[#FBECEC] bg-[#FBECEC]/40 p-3 text-[11.5px] text-[#D14444]">
            <AlertTriangle class="mt-0.5 h-3.5 w-3.5 shrink-0" />
            <span>{errorBanner}</span>
          </div>
        {/if}
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
        disabled={!available || busy}
      />
      <button
        type="submit"
        class="grid h-6 w-6 place-items-center rounded-md bg-[#4E46E5] text-white disabled:opacity-30"
        disabled={!canSubmit}
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
