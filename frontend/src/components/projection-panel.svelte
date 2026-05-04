<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { page } from '$app/stores'
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query'
  import { Plus, SlidersHorizontal, Trash2, Bookmark } from 'lucide-svelte'
  import { writable } from 'svelte/store'
  import { toast } from 'svelte-sonner'

  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import CompareDrawer from '$components/compare-drawer.svelte'
  import DialogContent from '$components/ui/dialog-content.svelte'
  import DialogDescription from '$components/ui/dialog-description.svelte'
  import DialogFooter from '$components/ui/dialog-footer.svelte'
  import DialogHeader from '$components/ui/dialog-header.svelte'
  import DialogTitle from '$components/ui/dialog-title.svelte'
  import Input from '$components/ui/input.svelte'
  import Slider from '$components/ui/slider.svelte'
  import {
    applyProjectionToSandbox,
    compareProjection,
    discardScenario,
    getActivePlan,
    getErrorMessage,
    listScenarios,
    saveScenario,
    type PlanCategory,
    type ProjectionAxis,
    type ProjectionNewLine,
    type ProjectionRequest,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'
  import { withBasePath } from '$lib/runtime'

  // --- local types ----------------------------------------------------------

  type AxisState = { category_id: number; percent_delta: number }
  type NewLineState = { group: string; name: string; monthly_amount: string }

  // --- state ----------------------------------------------------------------

  let axes: AxisState[] = $state([])
  let newLines: NewLineState[] = $state([])
  let showAddLine = $state(false)
  let newLineForm: NewLineState = $state({ group: '', name: '', monthly_amount: '' })
  let drawerOpen = $state(false)

  // Auto-park modal state.
  let parkingFor: 'apply' | null = $state(null)
  let parkLabel = $state('')
  let parkError: string | null = $state(null)
  let parkBusy = $state(false)

  // --- helpers --------------------------------------------------------------

  function dollarsToMilliunits(text: string): number {
    const dollars = Number(text)
    if (!Number.isFinite(dollars) || dollars < 0) return 0
    return Math.round(dollars * 1000)
  }

  function formatDelta(value: number): string {
    if (value === 0) return '—'
    const f = formatMoney(Math.abs(value))
    return value > 0 ? `+${f}` : `−${f}`
  }

  function deltaClass(value: number): string {
    if (value > 0) return 'text-rose-200'
    if (value < 0) return 'text-emerald-200'
    return 'text-muted-foreground'
  }

  function defaultParkLabel(): string {
    const now = new Date()
    const month = now.toLocaleString('en-US', { month: 'short' })
    return `Untitled scenario, ${month} ${now.getDate()}, ${now.getFullYear()}`
  }

  // --- queries --------------------------------------------------------------

  const queryClient = useQueryClient()

  const activePlanQuery = createQuery({
    queryKey: ['plan'],
    queryFn: () => getActivePlan(),
    enabled: browser,
  })

  const scenariosQuery = createQuery({
    queryKey: ['scenarios'],
    queryFn: listScenarios,
    enabled: browser,
  })

  let existingSandbox = $derived(
    $scenariosQuery.data?.scenarios.find((s) => s.label === null) ?? null,
  )

  async function getExistingSandbox() {
    // Direct fetch to ensure we have the current sandbox state regardless of
    // the reactive query's subscription status.
    const data = $scenariosQuery.data ?? (await listScenarios())
    return data.scenarios.find((s) => s.label === null) ?? null
  }

  // All monthly categories sorted by planned_milliunits desc, top-8 by default.
  const MAX_SLIDERS = 8
  let showAllSliders = $state(false)

  let allCategories = $derived((): PlanCategory[] => {
    const plan = $activePlanQuery.data
    if (!plan) return []
    const cats = [
      ...plan.blocks.monthly,
      ...plan.blocks.annual,
      ...plan.blocks.one_time,
      ...plan.blocks.stipends,
      ...plan.blocks.savings,
    ]
    cats.sort((a, b) => b.planned_milliunits - a.planned_milliunits)
    return cats
  })

  let visibleCategories = $derived((): PlanCategory[] => {
    const all = allCategories()
    return showAllSliders ? all : all.slice(0, MAX_SLIDERS)
  })

  let distinctGroups = $derived((): string[] => {
    const groups = new Set(allCategories().map((c) => c.group_name))
    return [...groups].sort()
  })

  // Phase 4 Slice 2: parse `?axes=id:pct,id:pct,...` deeplink so the
  // forecast page's "Project this change" button can pre-fill the
  // sliders. Pure session state — once consumed, the URL stays as-is
  // (we don't strip the param) so a refresh re-applies the same
  // initial state until the operator manually navigates away.
  function parseAxesFromQuery(raw: string | null): Map<number, number> {
    const out = new Map<number, number>()
    if (!raw) return out
    for (const segment of raw.split(',')) {
      const [idStr, pctStr] = segment.split(':')
      const id = Number(idStr)
      const pct = Number(pctStr)
      if (Number.isFinite(id) && Number.isFinite(pct)) {
        out.set(id, pct)
      }
    }
    return out
  }
  let initialAxesConsumed = $state(false)

  // Initialise axes when categories first load (zero-delta unless an
  // ?axes= query param sets a starting value).
  $effect(() => {
    const cats = allCategories()
    if (cats.length === 0) return
    const initial = !initialAxesConsumed
      ? parseAxesFromQuery($page.url.searchParams.get('axes'))
      : new Map<number, number>()
    if (axes.length === 0) {
      axes = cats.map((c) => ({
        category_id: c.id,
        percent_delta: initial.get(c.id) ?? 0,
      }))
      initialAxesConsumed = true
    } else {
      // Sync any new categories that weren't in axes yet.
      const known = new Set(axes.map((a) => a.category_id))
      const toAdd = cats.filter((c) => !known.has(c.id))
      if (toAdd.length > 0) {
        axes = [
          ...axes,
          ...toAdd.map((c) => ({
            category_id: c.id,
            percent_delta: initial.get(c.id) ?? 0,
          })),
        ]
      }
      initialAxesConsumed = true
    }
  })

  function getAxisPercent(category_id: number): number {
    return axes.find((a) => a.category_id === category_id)?.percent_delta ?? 0
  }

  function setAxisPercent(category_id: number, value: number) {
    axes = axes.map((a) => (a.category_id === category_id ? { ...a, percent_delta: value } : a))
  }

  // --- debounced preview query ---------------------------------------------

  let request: ProjectionRequest = $derived({
    axes: axes.filter((a) => a.percent_delta !== 0),
    new_lines: newLines
      .filter((l) => l.group && l.name && dollarsToMilliunits(l.monthly_amount) > 0)
      .map((l) => ({
        group: l.group,
        name: l.name,
        monthly_amount_milliunits: dollarsToMilliunits(l.monthly_amount),
      })) as ProjectionNewLine[],
  })

  let debouncedRequest: ProjectionRequest = $state({ axes: [], new_lines: [] })
  $effect(() => {
    const r = request
    const t = setTimeout(() => {
      debouncedRequest = r
    }, 200)
    return () => clearTimeout(t)
  })

  type PreviewOpts = {
    queryKey: readonly unknown[]
    queryFn: () => Promise<ReturnType<typeof compareProjection> extends Promise<infer T> ? T : never>
    enabled: boolean
  }
  const previewOpts = writable<PreviewOpts>({
    queryKey: ['projection', 'disabled'],
    queryFn: () => Promise.reject(new Error('disabled')) as never,
    enabled: false,
  })
  $effect(() => {
    const r = debouncedRequest
    const hasWork = r.axes.length + r.new_lines.length > 0
    if (hasWork) {
      previewOpts.set({
        queryKey: ['projection', JSON.stringify(r)],
        queryFn: () => compareProjection(r),
        enabled: true,
      })
    } else {
      previewOpts.set({
        queryKey: ['projection', 'disabled'],
        queryFn: () => Promise.reject(new Error('disabled')) as never,
        enabled: false,
      })
    }
  })
  const previewQuery = createQuery(previewOpts)

  // --- summary card --------------------------------------------------------

  let annualDeltaMilliunits = $derived((): number => {
    const data = $previewQuery.data
    if (!data) return 0
    return (data.totals.planned_scenario_milliunits - data.totals.planned_active_milliunits) * 12
  })

  let top3Movers = $derived(() => {
    const data = $previewQuery.data
    if (!data) return []
    return [...data.rows]
      .sort((a, b) => Math.abs(b.vs_active_milliunits) - Math.abs(a.vs_active_milliunits))
      .slice(0, 3)
      .filter((r) => r.vs_active_milliunits !== 0)
  })

  // --- apply mutation ------------------------------------------------------

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan'] }),
      queryClient.invalidateQueries({ queryKey: ['scenarios'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
    ])
  }

  const applyMutation = createMutation({
    mutationFn: (req: ProjectionRequest) => applyProjectionToSandbox(req),
    onSuccess: async (plan) => {
      await invalidate()
      goto(withBasePath(`/planning?scenario=${plan.plan.id}`))
    },
    onError: (error) => {
      const msg = getErrorMessage(error)
      if (/sandbox already exists/i.test(msg)) {
        parkingFor = 'apply'
        parkLabel = defaultParkLabel()
        parkError = null
        parkBusy = false
      } else {
        toast.error(`Could not apply projection: ${msg}`)
      }
    },
  })

  function handleApply() {
    $applyMutation.mutate(debouncedRequest)
  }

  // --- auto-park handlers --------------------------------------------------

  async function handleParkSaveAndApply() {
    const sandbox = await getExistingSandbox()
    if (!sandbox) return
    const label = parkLabel.trim()
    if (!label) {
      parkError = 'Name cannot be empty.'
      return
    }
    parkBusy = true
    parkError = null
    try {
      await saveScenario(sandbox.id, label)
    } catch (error) {
      parkBusy = false
      parkError = getErrorMessage(error)
      return
    }
    try {
      const plan = await applyProjectionToSandbox(debouncedRequest)
      parkingFor = null
      parkBusy = false
      await invalidate()
      goto(withBasePath(`/planning?scenario=${plan.plan.id}`))
    } catch (error) {
      parkBusy = false
      parkingFor = null
      await invalidate()
      toast.error(`Could not apply projection: ${getErrorMessage(error)}`)
    }
  }

  async function handleParkDiscardAndApply() {
    const sandbox = await getExistingSandbox()
    if (!sandbox) return
    parkBusy = true
    parkError = null
    try {
      await discardScenario(sandbox.id)
    } catch (error) {
      parkBusy = false
      parkError = getErrorMessage(error)
      return
    }
    try {
      const plan = await applyProjectionToSandbox(debouncedRequest)
      parkingFor = null
      parkBusy = false
      await invalidate()
      goto(withBasePath(`/planning?scenario=${plan.plan.id}`))
    } catch (error) {
      parkBusy = false
      parkingFor = null
      await invalidate()
      toast.error(`Could not apply projection: ${getErrorMessage(error)}`)
    }
  }

  // --- new-line form -------------------------------------------------------

  function addNewLine() {
    const amount = dollarsToMilliunits(newLineForm.monthly_amount)
    if (!newLineForm.group || !newLineForm.name || amount <= 0) return
    newLines = [...newLines, { ...newLineForm }]
    newLineForm = { group: '', name: '', monthly_amount: '' }
    showAddLine = false
  }

  function removeNewLine(index: number) {
    newLines = newLines.filter((_, i) => i !== index)
  }
</script>

<Card class="border-border/40 bg-card">
  <CardHeader>
    <CardTitle class="flex items-center gap-2">
      <SlidersHorizontal class="h-4 w-4" />
      Projection — what if…
    </CardTitle>
    <p class="text-sm text-muted-foreground">
      Tweak categories or add hypothetical lines. Apply turns these edits into
      a Sandbox you can commit later.
    </p>
  </CardHeader>
  <CardContent class="space-y-5">

    <!-- Sliders block -->
    {#if $activePlanQuery.isLoading}
      <div class="h-[200px] animate-pulse rounded bg-muted/20"></div>
    {:else if $activePlanQuery.isError}
      <div class="text-sm text-rose-200">
        Could not load categories: {getErrorMessage($activePlanQuery.error)}
      </div>
    {:else}
      <div class="space-y-3" aria-label="Projection sliders">
        {#each visibleCategories() as cat (cat.id)}
          {@const pct = getAxisPercent(cat.id)}
          <div class="flex items-center gap-3">
            <div class="w-40 min-w-0 shrink-0">
              <div class="truncate text-sm text-foreground">{cat.category_name}</div>
              <div class="text-[11px] text-muted-foreground">{cat.group_name}</div>
            </div>
            <div class="flex-1">
              <Slider
                value={pct}
                min={-100}
                max={100}
                step={5}
                onValueChange={(v) => setAxisPercent(cat.id, v)}
              />
            </div>
            <div
              class={`w-14 text-right font-mono text-xs ${pct === 0 ? 'text-muted-foreground' : pct > 0 ? 'text-rose-200' : 'text-emerald-200'}`}
            >
              {pct > 0 ? '+' : ''}{pct}%
            </div>
          </div>
        {/each}

        {#if allCategories().length > MAX_SLIDERS}
          <button
            class="text-xs text-muted-foreground underline-offset-2 hover:underline"
            onclick={() => (showAllSliders = !showAllSliders)}
          >
            {showAllSliders
              ? 'Show fewer'
              : `Show all ${allCategories().length} categories`}
          </button>
        {/if}
      </div>
    {/if}

    <!-- New lines -->
    {#if newLines.length > 0}
      <div class="space-y-2">
        <div class="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          Hypothetical lines
        </div>
        {#each newLines as line, i (i)}
          <div class="flex items-center justify-between rounded-md border border-border/30 px-3 py-2 text-sm">
            <div>
              <span class="font-medium text-foreground">{line.group} / {line.name}</span>
              <span class="ml-2 text-muted-foreground">
                {formatMoney(dollarsToMilliunits(line.monthly_amount))}/mo
              </span>
            </div>
            <button
              class="text-muted-foreground hover:text-rose-200"
              aria-label="Remove {line.name}"
              onclick={() => removeNewLine(i)}
            >
              <Trash2 class="h-3.5 w-3.5" />
            </button>
          </div>
        {/each}
      </div>
    {/if}

    <!-- Add hypothetical line -->
    {#if showAddLine}
      <div class="space-y-2 rounded-md border border-border/40 p-3">
        <div class="text-sm font-medium text-foreground">Add hypothetical line</div>
        <div class="grid grid-cols-3 gap-2">
          <div>
            <label for="new-line-group" class="mb-1 block text-xs text-muted-foreground">Group</label>
            <Input
              id="new-line-group"
              placeholder="e.g. Expenses"
              bind:value={newLineForm.group}
              list="group-suggestions"
            />
            <datalist id="group-suggestions">
              {#each distinctGroups() as g (g)}
                <option value={g}></option>
              {/each}
            </datalist>
          </div>
          <div>
            <label for="new-line-name" class="mb-1 block text-xs text-muted-foreground">Category</label>
            <Input id="new-line-name" placeholder="e.g. Emergency" bind:value={newLineForm.name} />
          </div>
          <div>
            <label for="new-line-amount" class="mb-1 block text-xs text-muted-foreground">$/mo</label>
            <Input
              id="new-line-amount"
              type="number"
              min="0"
              step="1"
              placeholder="0"
              bind:value={newLineForm.monthly_amount}
            />
          </div>
        </div>
        <div class="flex gap-2">
          <Button size="sm" onclick={addNewLine}>
            <Plus class="h-3.5 w-3.5" />
            Add
          </Button>
          <Button
            size="sm"
            variant="outline"
            onclick={() => {
              showAddLine = false
              newLineForm = { group: '', name: '', monthly_amount: '' }
            }}
          >
            Cancel
          </Button>
        </div>
      </div>
    {:else}
      <Button size="sm" variant="outline" onclick={() => (showAddLine = true)}>
        <Plus class="h-3.5 w-3.5" />
        Add hypothetical line
      </Button>
    {/if}

    <!-- Inline summary card -->
    {#if $previewQuery.data}
      {@const delta = annualDeltaMilliunits()}
      <div class="rounded-md border border-border/40 bg-muted/10 p-3 space-y-2" aria-label="Projection summary">
        <div class="flex items-center justify-between text-sm">
          <span class="text-muted-foreground">Annual delta vs active</span>
          <span class={`font-mono font-medium ${deltaClass(delta)}`}>
            {formatDelta(delta)}
          </span>
        </div>
        {#if top3Movers().length > 0}
          <div class="space-y-1">
            {#each top3Movers() as row (row.category_id)}
              <div class="flex items-center justify-between text-xs">
                <span class="text-muted-foreground">{row.name}</span>
                <span class={`font-mono ${deltaClass(row.vs_active_milliunits)}`}>
                  {formatDelta(row.vs_active_milliunits)}
                </span>
              </div>
            {/each}
          </div>
        {/if}
      </div>
    {:else if $previewQuery.isLoading}
      <div class="h-16 animate-pulse rounded-md bg-muted/20"></div>
    {/if}

    <!-- Action row -->
    <div class="flex gap-2">
      <Button
        size="sm"
        variant="outline"
        disabled={debouncedRequest.axes.length + debouncedRequest.new_lines.length === 0}
        onclick={() => (drawerOpen = true)}
      >
        View details
      </Button>
      <Button
        size="sm"
        disabled={$applyMutation.isPending}
        onclick={handleApply}
      >
        {$applyMutation.isPending ? 'Applying…' : 'Apply to Sandbox'}
      </Button>
    </div>
  </CardContent>
</Card>

<!-- Compare drawer in projection mode -->
<CompareDrawer
  open={drawerOpen}
  projection={debouncedRequest.axes.length + debouncedRequest.new_lines.length > 0
    ? debouncedRequest
    : null}
  onClose={() => (drawerOpen = false)}
/>

<!-- Auto-park modal -->
<DialogPrimitive.Root
  bind:open={() => parkingFor !== null,
  (next: boolean) => {
    if (!next && !parkBusy) parkingFor = null
  }}
>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Save your sandbox before applying projection?</DialogTitle>
      <DialogDescription>
        You have an open sandbox with edits. Name it to keep the work, then
        apply the projection as a new sandbox. Or discard the current sandbox.
      </DialogDescription>
    </DialogHeader>
    <div class="space-y-2">
      <label for="proj-park-label" class="text-label">Name</label>
      <Input
        id="proj-park-label"
        type="text"
        bind:value={parkLabel}
        disabled={parkBusy}
        placeholder="Untitled scenario"
      />
      {#if parkError}
        <div class="text-sm text-rose-300">{parkError}</div>
      {/if}
    </div>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={parkBusy} onclick={() => (parkingFor = null)}>
        Cancel
      </Button>
      <Button
        variant="outline"
        class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
        disabled={parkBusy}
        onclick={() => void handleParkDiscardAndApply()}
      >
        <Trash2 class="h-4 w-4" />
        Discard sandbox
      </Button>
      <Button disabled={parkBusy} onclick={() => void handleParkSaveAndApply()}>
        <Bookmark class="h-4 w-4" />
        {parkBusy ? 'Working…' : 'Save & apply'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>
