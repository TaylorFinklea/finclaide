<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { Tabs as TabsPrimitive } from 'bits-ui'
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query'
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { AlertTriangle, ArrowDownToLine, Beaker, Bookmark, Check, Columns2, History, Plus, Scale, Trash2 } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'
  import { writable } from 'svelte/store'

  import CompareDrawer from '$components/compare-drawer.svelte'
  import DataTable, { type DataTableColumn } from '$components/data-table.svelte'
  import PlanCategorySheet, { type EditorSelection } from '$components/plan-category-sheet.svelte'
  import PlanHistorySheet from '$components/plan-history-sheet.svelte'
  import RebalancePromptsCard from '$components/rebalance-prompts-card.svelte'
  import Button from '$components/ui/button.svelte'
  import Card from '$components/ui/card.svelte'
  import CardContent from '$components/ui/card-content.svelte'
  import CardHeader from '$components/ui/card-header.svelte'
  import CardTitle from '$components/ui/card-title.svelte'
  import DialogContent from '$components/ui/dialog-content.svelte'
  import DialogDescription from '$components/ui/dialog-description.svelte'
  import DialogFooter from '$components/ui/dialog-footer.svelte'
  import DialogHeader from '$components/ui/dialog-header.svelte'
  import DialogTitle from '$components/ui/dialog-title.svelte'
  import Input from '$components/ui/input.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import TabsContent from '$components/ui/tabs-content.svelte'
  import TabsList from '$components/ui/tabs-list.svelte'
  import TabsTrigger from '$components/ui/tabs-trigger.svelte'
  import {
    BLOCK_LABELS,
    type ActivePlanResponse,
    type BlockKey,
    type PlanCategory,
    commitScenario,
    createScenario,
    discardScenario,
    getActivePlan,
    getErrorMessage,
    getRebalancePrompts,
    getScenario,
    getStatus,
    listScenarios,
    saveScenario,
    updatePlanCategory,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'

  const BLOCK_ORDER: BlockKey[] = ['monthly', 'annual', 'one_time', 'stipends', 'savings']

  function blockColumns(block: BlockKey): DataTableColumn<PlanCategory>[] {
    return [
      { key: 'group_name', header: 'Group', cellClass: 'font-medium' },
      {
        key: 'category_name',
        header: 'Category',
        // Mark inflow rows so the cascade math is visible at the row level.
        // Plain text keeps DataTable simple and screen-reader-friendly.
        cell: (row) => (row.kind === 'inflow' ? `↗ ${row.category_name}` : row.category_name),
      },
      {
        key: 'planned',
        header: 'Planned',
        cell: (row) => formatMoney(row.planned_milliunits),
        cellClass: 'font-mono text-sm',
      },
      {
        key: 'annual',
        header: 'Annual target',
        cell: (row) =>
          row.annual_target_milliunits === 0 && block === 'monthly'
            ? '—'
            : formatMoney(row.annual_target_milliunits),
        cellClass: 'font-mono text-sm text-muted-foreground',
      },
      {
        key: 'due',
        header: 'Due',
        cell: (row) => (row.due_month === null ? '—' : String(row.due_month).padStart(2, '0')),
        cellClass: 'font-mono text-sm',
      },
      { key: 'notes', header: 'Notes', cell: (row) => row.notes ?? '—', cellClass: 'text-sm text-muted-foreground' },
    ]
  }

  type CascadeStep = { block: BlockKey; outflow: number; remaining_after: number }
  type Cascade = { inflow: number; steps: CascadeStep[]; leftover: number }

  function computeCascade(plan: ActivePlanResponse | undefined): Cascade | null {
    if (!plan) return null
    let inflow = 0
    const outflowByBlock: Record<BlockKey, number> = {
      monthly: 0, annual: 0, one_time: 0, stipends: 0, savings: 0,
    }
    for (const block of BLOCK_ORDER) {
      for (const cat of plan.blocks[block]) {
        if (cat.kind === 'inflow') inflow += cat.planned_milliunits
        else outflowByBlock[block] += cat.planned_milliunits
      }
    }
    const steps: CascadeStep[] = []
    let running = inflow
    for (const block of BLOCK_ORDER) {
      running -= outflowByBlock[block]
      steps.push({ block, outflow: outflowByBlock[block], remaining_after: running })
    }
    return { inflow, steps, leftover: running }
  }

  function blockCascade(cascade: Cascade | null, block: BlockKey) {
    if (!cascade) return null
    const idx = BLOCK_ORDER.indexOf(block)
    const going_in = idx === 0 ? cascade.inflow : cascade.steps[idx - 1].remaining_after
    const step = cascade.steps[idx]
    return { going_in, this_block: step.outflow, going_out: step.remaining_after }
  }

  const planQuery = createQuery({
    queryKey: ['plan', 'active'],
    queryFn: () => getActivePlan(),
    enabled: browser,
  })
  // Rebalance prompts depend on the active plan + 6-month run-rates; refetch
  // alongside the plan so changes to inflows/outflows surface immediately.
  const rebalanceQuery = createQuery({
    queryKey: ['analytics-cashflow-rebalance'],
    queryFn: () => getRebalancePrompts({ months: 12 }),
    enabled: browser,
    staleTime: 60_000,
  })
  const statusQuery = createQuery({ queryKey: ['status'], queryFn: getStatus, enabled: browser })
  const scenariosQuery = createQuery({
    queryKey: ['scenarios'],
    queryFn: listScenarios,
    enabled: browser,
  })

  let viewedScenarioId: number | null = $state(null)
  // Tracks which ?scenario=<id> param value we have already consumed. The guard
  // is intentionally tied to the string value rather than a boolean so that
  // navigating to the same URL on a fresh mount (e.g. hard-refresh) starts
  // clean while preventing re-entry after discard while the param is still in
  // the URL. Refresh-as-resume is intentional: if the operator refreshes with
  // ?scenario=<id> still in the URL and the sandbox still exists, they land
  // back in sandbox mode. The guard write is deferred until validation passes,
  // so a first render with an empty scenarios list doesn't permanently burn the
  // guard before the list loads.
  let consumedScenarioParam: string | null = $state(null)
  $effect(() => {
    const raw = $page.url.searchParams.get('scenario')
    if (raw === null) { consumedScenarioParam = null; return }
    if (consumedScenarioParam === raw) return
    const id = Number.parseInt(raw, 10)
    if (!Number.isFinite(id) || id <= 0) return
    const list = $scenariosQuery.data?.scenarios ?? []
    const match = list.find((s) => s.id === id && s.label === null)
    if (!match) return
    consumedScenarioParam = raw
    viewedScenarioId = id
  })

  type ScenarioOpts = {
    queryKey: readonly unknown[]
    queryFn: () => Promise<ActivePlanResponse>
    enabled: boolean
  }
  const scenarioOpts = writable<ScenarioOpts>({
    queryKey: ['plan', 'scenario', null],
    queryFn: () => Promise.reject(new Error('disabled')) as Promise<ActivePlanResponse>,
    enabled: false,
  })
  $effect(() => {
    if (viewedScenarioId === null) {
      scenarioOpts.set({
        queryKey: ['plan', 'scenario', null],
        queryFn: () => Promise.reject(new Error('disabled')) as Promise<ActivePlanResponse>,
        enabled: false,
      })
    } else {
      const id = viewedScenarioId
      scenarioOpts.set({
        queryKey: ['plan', 'scenario', id],
        queryFn: () => getScenario(id),
        enabled: browser,
      })
    }
  })
  const scenarioPlanQuery = createQuery(scenarioOpts)

  let inSandboxMode = $derived(viewedScenarioId !== null)
  let displayedPlan = $derived(
    viewedScenarioId === null ? $planQuery.data : $scenarioPlanQuery.data,
  )
  let cascade = $derived(computeCascade(displayedPlan))
  let displayedQueryLoading = $derived(
    viewedScenarioId === null ? $planQuery.isLoading : $scenarioPlanQuery.isLoading,
  )
  let displayedQueryError = $derived(
    viewedScenarioId === null ? $planQuery.error : $scenarioPlanQuery.error,
  )
  let existingSandbox = $derived(
    $scenariosQuery.data?.scenarios.find((s) => s.label === null) ?? null,
  )

  type Cadence = 'monthly' | 'annual'
  const CADENCE_STORAGE_KEY = 'finclaide.planning.cadence'
  function readPersistedCadence(): Cadence {
    if (typeof window === 'undefined') return 'monthly'
    const raw = window.localStorage.getItem(CADENCE_STORAGE_KEY)
    return raw === 'annual' || raw === 'monthly' ? raw : 'monthly'
  }
  let cadence: Cadence = $state(readPersistedCadence())
  let cadenceMultiplier = $derived(cadence === 'annual' ? 12 : 1)
  let cadenceLabel = $derived(cadence === 'annual' ? 'yr' : 'mo')
  $effect(() => {
    if (typeof window === 'undefined') return
    window.localStorage.setItem(CADENCE_STORAGE_KEY, cadence)
  })

  let activeBlock: BlockKey = $state('monthly')
  let selection: EditorSelection = $state(null)
  let historyOpen = $state(false)
  let confirmingDiscard = $state(false)
  let confirmingCommit = $state(false)
  let confirmingSave = $state(false)
  let saveLabel: string = $state('')
  let saveError: string | null = $state(null)
  let compareOpen = $state(false)
  let balanceOpen = $state(false)
  // Allocation amounts (dollars, as text strings to allow free editing) keyed by
  // savings category id. Reset each time the dialog opens to an even split of
  // the current leftover across all savings outflow rows.
  let balanceAllocations: Record<number, string> = $state({})

  function dollarsToMilliunits(text: string): number {
    const n = Number(text)
    if (!Number.isFinite(n)) return NaN
    return Math.round(n * 1000)
  }

  function openBalanceDialog() {
    if (!cascade || !displayedPlan) return
    const savings = displayedPlan.blocks.savings.filter((c) => c.kind === 'outflow')
    if (savings.length === 0) {
      toast.error('Add at least one outflow row in Savings before balancing.')
      return
    }
    // Split in whole cents so the displayed text adds up exactly. The last row
    // absorbs the cent remainder so 3-way splits of $311.17 land 103.72 / 103.72
    // / 103.73 instead of three displayed-as-103.72 values that sum to $311.16.
    const leftoverCents = Math.round(cascade.leftover / 10)
    const perRowCents = Math.floor(leftoverCents / savings.length)
    const seed: Record<number, string> = {}
    let assignedCents = 0
    savings.forEach((row, idx) => {
      const cents =
        idx === savings.length - 1 ? leftoverCents - assignedCents : perRowCents
      assignedCents += cents
      seed[row.id] = (cents / 100).toFixed(2)
    })
    balanceAllocations = seed
    balanceOpen = true
  }

  let balanceRows = $derived(
    displayedPlan?.blocks.savings.filter((c) => c.kind === 'outflow') ?? [],
  )
  let balanceAllocatedTotal = $derived(
    Object.values(balanceAllocations).reduce((sum, text) => {
      const n = dollarsToMilliunits(text)
      return Number.isFinite(n) ? sum + n : sum
    }, 0),
  )
  let balanceLeftover = $derived(cascade?.leftover ?? 0)
  let balanceRemainder = $derived(balanceLeftover - balanceAllocatedTotal)
  // Tolerate a 1-cent sub-cent remainder so cent-rounded splits still apply.
  let balanceValid = $derived(
    Object.values(balanceAllocations).every((t) => {
      const n = dollarsToMilliunits(t)
      return Number.isFinite(n) && n >= 0
    }) && Math.abs(balanceRemainder) <= 10,
  )

  const balanceMutation = createMutation({
    mutationFn: async ({ planId, updates }: { planId: number; updates: { id: number; planned_milliunits: number }[] }) => {
      // Sequential PATCH so a single revision summary doesn't race; the server
      // serializes writes anyway and operations are cheap.
      for (const u of updates) {
        await updatePlanCategory(u.id, {
          plan_id: planId,
          planned_milliunits: u.planned_milliunits,
        })
      }
    },
    onSuccess: async () => {
      balanceOpen = false
      await invalidatePlanState()
      toast.success('Savings rebalanced — leftover is now $0/mo.')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  function applyBalance() {
    if (!cascade || !displayedPlan || !balanceValid) return
    const updates = balanceRows.map((row) => {
      const addedMilli = dollarsToMilliunits(balanceAllocations[row.id] ?? '0') || 0
      return {
        id: row.id,
        planned_milliunits: row.planned_milliunits + addedMilli,
      }
    })
    $balanceMutation.mutate({ planId: displayedPlan.plan.id, updates })
  }

  // Inline cascade editing: click a block row in the Cash flow card to open a
  // dialog that lets you adjust every outflow row in that block at once. The
  // dialog shows a live preview of the new block total, the delta, and the
  // resulting cascade leftover so you can what-if without leaving the page.
  let blockEditOpen = $state(false)
  let blockEditTarget: BlockKey | null = $state(null)
  let blockEditValues: Record<number, string> = $state({})

  let blockEditRows: PlanCategory[] = $derived.by(() => {
    if (!blockEditTarget || !displayedPlan) return []
    return displayedPlan.blocks[blockEditTarget].filter(
      (c: PlanCategory) => c.kind === 'outflow',
    )
  })
  let blockEditOldTotal = $derived(
    blockEditRows.reduce((sum, r) => sum + r.planned_milliunits, 0),
  )
  let blockEditNewTotal = $derived(
    blockEditRows.reduce((sum, r) => {
      const v = dollarsToMilliunits(blockEditValues[r.id] ?? '0')
      return Number.isFinite(v) ? sum + v : sum
    }, 0),
  )
  let blockEditDelta = $derived(blockEditNewTotal - blockEditOldTotal)
  let blockEditNewLeftover = $derived(
    cascade ? cascade.leftover - blockEditDelta : 0,
  )
  let blockEditValid = $derived(
    blockEditRows.every((r) => {
      const v = dollarsToMilliunits(blockEditValues[r.id] ?? '0')
      return Number.isFinite(v) && v >= 0
    }),
  )

  function openBlockEdit(block: BlockKey) {
    if (!displayedPlan) return
    const rows = displayedPlan.blocks[block].filter((c) => c.kind === 'outflow')
    if (rows.length === 0) {
      toast.error('No outflow rows in this block to adjust.')
      return
    }
    const seed: Record<number, string> = {}
    rows.forEach((r) => {
      seed[r.id] = (r.planned_milliunits / 1000).toFixed(2)
    })
    blockEditTarget = block
    blockEditValues = seed
    blockEditOpen = true
  }

  const blockEditMutation = createMutation({
    mutationFn: async ({
      planId,
      updates,
    }: {
      planId: number
      updates: { id: number; planned_milliunits: number }[]
    }) => {
      for (const u of updates) {
        await updatePlanCategory(u.id, {
          plan_id: planId,
          planned_milliunits: u.planned_milliunits,
        })
      }
    },
    onSuccess: async () => {
      blockEditOpen = false
      await invalidatePlanState()
      toast.success('Block updated.')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  function applyBlockEdit() {
    if (!blockEditTarget || !displayedPlan || !blockEditValid) return
    const updates: { id: number; planned_milliunits: number }[] = []
    blockEditRows.forEach((row) => {
      const next = dollarsToMilliunits(blockEditValues[row.id] ?? '0')
      if (Number.isFinite(next) && next !== row.planned_milliunits) {
        updates.push({ id: row.id, planned_milliunits: next })
      }
    })
    if (updates.length === 0) {
      blockEditOpen = false
      return
    }
    $blockEditMutation.mutate({ planId: displayedPlan.plan.id, updates })
  }

  function defaultSaveLabel(): string {
    const now = new Date()
    const month = now.toLocaleString('en-US', { month: 'short' })
    return `Untitled scenario, ${month} ${now.getDate()}, ${now.getFullYear()}`
  }

  let importBusy = $derived(
    $statusQuery.data?.busy === true && $statusQuery.data?.current_operation === 'budget_import',
  )

  const queryClient = useQueryClient()

  async function invalidatePlanState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan'] }),
      queryClient.invalidateQueries({ queryKey: ['scenarios'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
    ])
  }

  const startSandboxMutation = createMutation({
    mutationFn: () => {
      if (existingSandbox !== null) {
        return Promise.resolve({ plan: { id: existingSandbox.id } } as ActivePlanResponse)
      }
      const activeId = $planQuery.data?.plan.id
      if (activeId === undefined) {
        return Promise.reject(new Error('Active plan not loaded'))
      }
      return createScenario({ from_plan_id: activeId })
    },
    onSuccess: async (response) => {
      viewedScenarioId = response.plan.id
      await invalidatePlanState()
      toast.success(existingSandbox ? 'Resumed sandbox' : 'Sandbox created — try edits freely.')
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const discardMutation = createMutation({
    mutationFn: (id: number) => discardScenario(id),
    onSuccess: async () => {
      viewedScenarioId = null
      confirmingDiscard = false
      await invalidatePlanState()
      toast.success('Sandbox discarded.')
    },
    onError: (error) => {
      confirmingDiscard = false
      toast.error(getErrorMessage(error))
    },
  })

  const commitMutation = createMutation({
    mutationFn: (id: number) => commitScenario(id),
    onSuccess: async (response) => {
      viewedScenarioId = null
      confirmingCommit = false
      await invalidatePlanState()
      toast.success(`Sandbox committed — active plan now reflects your changes.`)
    },
    onError: (error) => {
      confirmingCommit = false
      toast.error(getErrorMessage(error))
    },
  })

  const saveMutation = createMutation({
    mutationFn: ({ id, label }: { id: number; label: string }) => saveScenario(id, label),
    onSuccess: async (response) => {
      // Saved scenario is no longer the open Sandbox; user can fork it later.
      viewedScenarioId = null
      confirmingSave = false
      saveError = null
      await invalidatePlanState()
      toast.success(`Saved as '${response.plan.plan.label}'.`)
    },
    onError: (error) => {
      saveError = getErrorMessage(error)
    },
  })

  let scenarioBusy = $derived(
    $startSandboxMutation.isPending ||
      $discardMutation.isPending ||
      $commitMutation.isPending ||
      $saveMutation.isPending,
  )

  function whatIfButtonLabel() {
    if ($startSandboxMutation.isPending) return 'Working…'
    if (existingSandbox !== null && !inSandboxMode) return 'Continue sandbox'
    return 'Try a what-if'
  }
</script>

{#if displayedQueryLoading}
  <Skeleton class="h-[640px] rounded-2xl" />
{:else if displayedQueryError}
  <Card class="border-border/40 bg-card">
    <CardHeader><CardTitle>Planning is unavailable</CardTitle></CardHeader>
    <CardContent class="text-sm text-muted-foreground">
      {displayedQueryError instanceof Error ? displayedQueryError.message : 'Could not load the plan.'}
      <p class="mt-3">If you have not imported a budget yet, run an import from the Operations page first.</p>
    </CardContent>
  </Card>
{:else if displayedPlan}
  {@const data = displayedPlan}
  <div class="space-y-6">
    {#if importBusy}
      <Card class="border-amber-500/30 bg-amber-500/[0.06]" role="status" aria-live="polite">
        <CardHeader class="space-y-1">
          <CardTitle class="flex items-center gap-2 text-amber-100">
            <AlertTriangle class="h-4 w-4" />
            Budget import in progress
          </CardTitle>
          <p class="text-sm text-amber-100/80">
            Saved edits may be overwritten when the import completes. Wait or coordinate before saving.
          </p>
        </CardHeader>
      </Card>
    {/if}

    {#if inSandboxMode}
      <Card class="border-amber-500/40 bg-amber-500/[0.08]" role="status" aria-live="polite">
        <CardHeader class="space-y-2">
          <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div class="flex items-start gap-2">
              <Beaker class="mt-0.5 h-4 w-4 text-amber-100" />
              <div>
                <CardTitle class="text-amber-100">Sandbox mode</CardTitle>
                <p class="text-sm text-amber-100/80">
                  Edits go to a scenario, not the active plan. Commit to make it live, or discard to throw it away.
                </p>
              </div>
            </div>
            <div class="flex gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={scenarioBusy}
                onclick={() => (confirmingDiscard = true)}
              >
                <Trash2 class="h-4 w-4" />
                Discard
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={scenarioBusy}
                onclick={() => (compareOpen = true)}
              >
                <Columns2 class="h-4 w-4" />
                Compare
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={scenarioBusy}
                onclick={() => {
                  saveLabel = displayedPlan?.plan.label ?? defaultSaveLabel()
                  saveError = null
                  confirmingSave = true
                }}
              >
                <Bookmark class="h-4 w-4" />
                Save
              </Button>
              <Button
                size="sm"
                disabled={scenarioBusy || importBusy}
                onclick={() => (confirmingCommit = true)}
              >
                <Check class="h-4 w-4" />
                Commit
              </Button>
            </div>
          </div>
        </CardHeader>
      </Card>
    {/if}

    {#if cascade && cascade.inflow === 0}
      <Card class="border-cyan-500/30 bg-cyan-500/[0.06]" role="status" aria-live="polite">
        <CardHeader class="space-y-2">
          <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <div class="flex items-start gap-2">
              <ArrowDownToLine class="mt-0.5 h-4 w-4 text-cyan-100" />
              <div>
                <CardTitle class="text-cyan-100">No income detected</CardTitle>
                <p class="text-sm text-cyan-100/80">
                  Mark an existing category as income via the edit sheet, or add a new
                  income row so the cascade has a pool to subtract from.
                </p>
              </div>
            </div>
            <Button
              size="sm"
              variant="outline"
              onclick={() => (selection = {
                mode: 'create',
                planId: data.plan.id,
                block: 'monthly',
                prefill: { kind: 'inflow', group_name: 'Monthly Income' },
              })}
            >
              <Plus class="h-4 w-4" />
              Add income row
            </Button>
          </div>
        </CardHeader>
      </Card>
    {/if}

    {#if cascade}
      <Card class="border-border/40 bg-card">
        <CardHeader class="space-y-2">
          <div class="flex items-center justify-between gap-3">
            <CardTitle class="text-base">Cash flow</CardTitle>
            <div
              class="inline-flex rounded-md border border-border/40 bg-muted/15 p-0.5 text-xs"
              role="group"
              aria-label="Cadence"
            >
              <button
                type="button"
                class="rounded px-2.5 py-1 transition-colors {cadence === 'monthly'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground'}"
                aria-pressed={cadence === 'monthly'}
                onclick={() => (cadence = 'monthly')}
              >
                Monthly
              </button>
              <button
                type="button"
                class="rounded px-2.5 py-1 transition-colors {cadence === 'annual'
                  ? 'bg-muted text-foreground'
                  : 'text-muted-foreground hover:text-foreground'}"
                aria-pressed={cadence === 'annual'}
                onclick={() => (cadence = 'annual')}
              >
                Annual
              </button>
            </div>
          </div>
          <p class="text-xs text-muted-foreground">
            {cadence === 'annual' ? 'Annualized (×12).' : 'Monthly equivalent.'}
            Income flows in at the top; each block subtracts; what's left at the end is your
            savings buffer (or, if negative, a shortfall to close).
          </p>
        </CardHeader>
        <CardContent class="space-y-4">
          <div class="space-y-1.5 text-sm">
            <div class="flex items-baseline justify-between border-b border-border/30 pb-1.5">
              <span class="font-medium text-foreground">Income (inflow)</span>
              <span class="font-mono text-foreground">
                {formatMoney(cascade.inflow * cadenceMultiplier)} / {cadenceLabel}
              </span>
            </div>
            {#each cascade.steps as step (step.block)}
              <button
                type="button"
                class="-mx-2 flex w-full items-baseline justify-between rounded px-2 py-1 text-left transition-colors hover:bg-muted/30 focus:bg-muted/30 focus:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                onclick={() => openBlockEdit(step.block)}
                aria-label={`Adjust ${BLOCK_LABELS[step.block]} block outflows`}
              >
                <span class="text-muted-foreground">− {BLOCK_LABELS[step.block]}</span>
                <span class="flex items-baseline gap-3 sm:gap-6">
                  <span class="font-mono text-foreground">
                    {formatMoney(step.outflow * cadenceMultiplier)} / {cadenceLabel}
                  </span>
                  <span
                    class="font-mono text-xs {step.remaining_after < 0
                      ? 'text-rose-300'
                      : 'text-muted-foreground'}"
                  >
                    → {formatMoney(step.remaining_after * cadenceMultiplier)} left
                  </span>
                </span>
              </button>
            {/each}
          </div>
          <div class="flex flex-col items-center gap-3 pt-1">
            <span
              class="rounded-full border px-5 py-2.5 text-base font-semibold {cascade.leftover >= 0
                ? 'border-emerald-500/30 bg-emerald-500/15 text-emerald-200'
                : 'border-rose-500/30 bg-rose-500/15 text-rose-200'}"
              role="status"
              aria-live="polite"
            >
              Leftover {formatMoney(cascade.leftover * cadenceMultiplier)} / {cadenceLabel}
              {cascade.leftover >= 0 ? '✓' : '⚠'}
            </span>
            {#if cascade.leftover >= 10}
              <Button size="sm" variant="outline" onclick={openBalanceDialog} disabled={importBusy}>
                <Scale class="h-4 w-4" />
                Balance to zero (move {formatMoney(cascade.leftover * cadenceMultiplier)} to savings)
              </Button>
            {/if}
          </div>
        </CardContent>
      </Card>

      <RebalancePromptsCard
        prompts={$rebalanceQuery.data}
        planId={data.plan.id}
        isLoading={$rebalanceQuery.isLoading}
        isError={$rebalanceQuery.isError}
      />
    {/if}

    <Card class="border-border/40 bg-card">
      <CardHeader class="space-y-3">
        <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
          <div>
            <CardTitle>
              Planning — {data.plan.name}
              {#if inSandboxMode}<span class="text-amber-200"> (sandbox)</span>{/if}
            </CardTitle>
            <!-- Sandbox banner subtitle is intentionally generic. Lineage (e.g.
                 "forked from 'Smoke A'") would require persisting source_plan_id on
                 plans rows; deferred to a future slice that needs lineage anyway. -->
            <p class="mt-2 text-sm text-muted-foreground">
              {inSandboxMode
                ? 'Sandboxed edits will not affect your active plan until you commit.'
                : `Active plan for ${data.plan.plan_year}. Click any row to edit; use Add row to create a new category in the current block.`}
            </p>
          </div>
          <div class="text-right text-sm text-muted-foreground">
            <div>Plan total {formatMoney(Number(data.totals.grand_total_milliunits ?? 0))}</div>
            <div class="text-xs">Source: {data.plan.source}</div>
          </div>
        </div>
      </CardHeader>
      <CardContent class="space-y-4">
        <TabsPrimitive.Root bind:value={activeBlock}>
          <div class="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
            <TabsList>
              {#each BLOCK_ORDER as key (key)}
                <TabsTrigger value={key}>{BLOCK_LABELS[key]}</TabsTrigger>
              {/each}
            </TabsList>
            <div class="flex items-center gap-2">
              {#if !inSandboxMode}
                <Button
                  size="sm"
                  variant="outline"
                  disabled={scenarioBusy || importBusy}
                  onclick={() => $startSandboxMutation.mutate()}
                >
                  <Beaker class="h-4 w-4" />
                  {whatIfButtonLabel()}
                </Button>
              {/if}
              <Button
                size="sm"
                variant="outline"
                onclick={() => (historyOpen = true)}
                disabled={importBusy}
              >
                <History class="h-4 w-4" />
                History
              </Button>
              <Button
                size="sm"
                onclick={() => (selection = { mode: 'create', planId: data.plan.id, block: activeBlock })}
              >
                <Plus class="h-4 w-4" />
                Add row
              </Button>
            </div>
          </div>

          {#each BLOCK_ORDER as key (key)}
            <TabsContent value={key} class="mt-4">
              {@render blockPanel(key, data.blocks[key], Number(data.totals[`${key}_milliunits`] ?? 0))}
            </TabsContent>
          {/each}
        </TabsPrimitive.Root>
      </CardContent>
    </Card>

    <PlanCategorySheet {selection} onClose={() => (selection = null)} />
    <PlanHistorySheet
      open={historyOpen}
      planId={data.plan.id}
      currentBlocks={data.blocks}
      onClose={() => (historyOpen = false)}
    />
    <CompareDrawer
      open={compareOpen && inSandboxMode}
      scenarioId={inSandboxMode ? data.plan.id : null}
      onClose={() => (compareOpen = false)}
    />
  </div>
{/if}

{#snippet blockPanel(block: BlockKey, rows: PlanCategory[], total: number)}
  {@const columns = blockColumns(block)}
  {@const flow = blockCascade(cascade, block)}
  <div class="space-y-3">
    {#if flow}
      <div class="flex flex-wrap items-baseline justify-between gap-3 text-sm">
        <span class="text-muted-foreground">
          {rows.length} {rows.length === 1 ? 'category' : 'categories'}
        </span>
        <span class="flex flex-wrap items-baseline gap-x-4 gap-y-1 font-mono">
          <span class="text-muted-foreground">
            Going in <span class="text-foreground">{formatMoney(flow.going_in * cadenceMultiplier)}</span>
            / {cadenceLabel}
          </span>
          <span class="text-muted-foreground">
            ·  This block
            <span class="text-foreground">−{formatMoney(flow.this_block * cadenceMultiplier)}</span>
            / {cadenceLabel}
          </span>
          <span class="text-muted-foreground">
            ·  Going out
            <span class={flow.going_out < 0 ? 'text-rose-300' : 'text-foreground'}>
              {formatMoney(flow.going_out * cadenceMultiplier)}
            </span>
            / {cadenceLabel}
          </span>
        </span>
      </div>
    {:else}
      <div class="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {rows.length} {rows.length === 1 ? 'category' : 'categories'} in {BLOCK_LABELS[block]}
        </span>
        <span class="font-mono text-foreground">Block total {formatMoney(total)}</span>
      </div>
    {/if}
    <DataTable
      data={rows}
      {columns}
      onRowClick={(row) => (selection = { mode: 'edit', planId: rows[0]?.plan_id ?? 0, category: row })}
      emptyMessage={`No ${BLOCK_LABELS[block]} categories yet. Click Add row to create one.`}
    />
  </div>
{/snippet}

<DialogPrimitive.Root
  bind:open={() => blockEditOpen, (next) => {
    if (!next && !$blockEditMutation.isPending) blockEditOpen = false
  }}
>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>
        Adjust {blockEditTarget ? BLOCK_LABELS[blockEditTarget] : ''} outflows
      </DialogTitle>
      <DialogDescription>
        Change any row's planned amount; the cascade leftover preview updates live so you
        can what-if without leaving the page. Apply commits the changes; Cancel discards.
      </DialogDescription>
    </DialogHeader>
    <div class="max-h-96 space-y-2 overflow-y-auto pr-1">
      {#each blockEditRows as row (row.id)}
        <div class="grid grid-cols-[1fr_auto] items-baseline gap-3 text-sm">
          <span class="truncate">
            <span class="text-muted-foreground">{row.group_name} ›</span>
            <span class="font-medium">{row.category_name}</span>
            {#if row.tithe_percent !== null}
              <span class="ml-1 text-xs text-muted-foreground">
                (tithe {row.tithe_percent}% — auto)
              </span>
            {/if}
          </span>
          <Input
            type="number"
            step="0.01"
            min="0"
            class="w-28 text-right font-mono"
            disabled={row.tithe_percent !== null}
            bind:value={blockEditValues[row.id]}
          />
        </div>
      {/each}
    </div>
    <div class="space-y-1.5 border-t border-border/30 pt-3 text-sm">
      <div class="flex items-baseline justify-between">
        <span class="text-muted-foreground">Block total</span>
        <span class="font-mono">
          {formatMoney(blockEditOldTotal)} → <span
            class={blockEditDelta === 0
              ? 'text-foreground'
              : blockEditDelta < 0
                ? 'text-emerald-300'
                : 'text-rose-300'}>{formatMoney(blockEditNewTotal)}</span
          >
        </span>
      </div>
      <div class="flex items-baseline justify-between">
        <span class="text-muted-foreground">Delta</span>
        <span
          class="font-mono {blockEditDelta === 0
            ? 'text-muted-foreground'
            : blockEditDelta < 0
              ? 'text-emerald-300'
              : 'text-rose-300'}"
        >
          {blockEditDelta > 0 ? '+' : ''}{formatMoney(blockEditDelta)}
        </span>
      </div>
      <div class="flex items-baseline justify-between">
        <span class="text-muted-foreground">New cascade leftover</span>
        <span
          class="font-mono {blockEditNewLeftover >= 0 ? 'text-emerald-300' : 'text-rose-300'}"
        >
          {formatMoney(blockEditNewLeftover)} / mo
        </span>
      </div>
    </div>
    <DialogFooter class="gap-2">
      <Button
        variant="outline"
        disabled={$blockEditMutation.isPending}
        onclick={() => (blockEditOpen = false)}
      >
        Cancel
      </Button>
      <Button
        disabled={!blockEditValid || $blockEditMutation.isPending || blockEditDelta === 0}
        onclick={applyBlockEdit}
      >
        {$blockEditMutation.isPending ? 'Applying…' : 'Apply'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

<DialogPrimitive.Root bind:open={() => balanceOpen, (next) => { if (!next && !$balanceMutation.isPending) balanceOpen = false }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Balance leftover to zero</DialogTitle>
      <DialogDescription>
        Move the cascade's leftover into Savings categories. Edit each row's allocation if you want a different split — the totals must add up to the leftover.
      </DialogDescription>
    </DialogHeader>
    <div class="space-y-3">
      <div class="flex items-baseline justify-between rounded-md border border-border/40 bg-muted/15 px-3 py-2 text-sm">
        <span class="text-muted-foreground">Leftover to allocate</span>
        <span class="font-mono font-semibold text-foreground">{formatMoney(balanceLeftover)} / mo</span>
      </div>
      <div class="space-y-2">
        {#each balanceRows as row (row.id)}
          <div class="grid grid-cols-[1fr_auto_auto] items-baseline gap-3 text-sm">
            <span class="truncate">
              <span class="text-muted-foreground">{row.group_name} ›</span>
              <span class="font-medium">{row.category_name}</span>
            </span>
            <span class="font-mono text-xs text-muted-foreground">
              {formatMoney(row.planned_milliunits)} +
            </span>
            <Input
              type="number"
              step="0.01"
              min="0"
              class="w-28 text-right font-mono"
              bind:value={balanceAllocations[row.id]}
            />
          </div>
        {/each}
      </div>
      <div class="flex items-baseline justify-between border-t border-border/30 pt-2 text-sm">
        <span class="text-muted-foreground">Allocated</span>
        <span class="font-mono text-foreground">
          {formatMoney(balanceAllocatedTotal)} / mo
        </span>
      </div>
      <div class="flex items-baseline justify-between text-sm">
        <span class="text-muted-foreground">Remainder</span>
        <span
          class="font-mono {Math.abs(balanceRemainder) <= 10
            ? 'text-emerald-300'
            : 'text-rose-300'}"
        >
          {formatMoney(balanceRemainder)}
        </span>
      </div>
    </div>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$balanceMutation.isPending} onclick={() => (balanceOpen = false)}>
        Cancel
      </Button>
      <Button disabled={!balanceValid || $balanceMutation.isPending} onclick={applyBalance}>
        <Scale class="h-4 w-4" />
        {$balanceMutation.isPending ? 'Applying…' : 'Apply'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

<DialogPrimitive.Root bind:open={() => confirmingDiscard, (next) => { if (!next) confirmingDiscard = false }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Discard sandbox?</DialogTitle>
      <DialogDescription>
        Throws away all edits made in this sandbox. There is no undo. Use Save to keep these changes as a named scenario.
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$discardMutation.isPending} onclick={() => (confirmingDiscard = false)}>
        Cancel
      </Button>
      <Button
        variant="outline"
        class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
        disabled={$discardMutation.isPending}
        onclick={() => {
          if (viewedScenarioId !== null) $discardMutation.mutate(viewedScenarioId)
        }}
      >
        {$discardMutation.isPending ? 'Discarding…' : 'Discard sandbox'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

<DialogPrimitive.Root
  bind:open={() => confirmingSave, (next) => {
    if (!next && !$saveMutation.isPending) {
      confirmingSave = false
      saveError = null
    }
  }}
>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Save scenario</DialogTitle>
      <DialogDescription>
        Name this sandbox to keep its edits as a saved scenario. You can fork it back into a sandbox later from /scenarios.
      </DialogDescription>
    </DialogHeader>
    <div class="space-y-2">
      <label for="save-label" class="text-label">Name</label>
      <Input
        id="save-label"
        type="text"
        bind:value={saveLabel}
        disabled={$saveMutation.isPending}
        placeholder="Untitled scenario"
      />
      {#if saveError}
        <div class="text-sm text-rose-300">{saveError}</div>
      {/if}
    </div>
    <DialogFooter class="gap-2">
      <Button
        variant="outline"
        disabled={$saveMutation.isPending}
        onclick={() => {
          confirmingSave = false
          saveError = null
        }}
      >
        Cancel
      </Button>
      <Button
        disabled={$saveMutation.isPending}
        onclick={() => {
          const trimmed = saveLabel.trim()
          if (!trimmed) {
            saveError = 'Name cannot be empty.'
            return
          }
          if (viewedScenarioId !== null) {
            $saveMutation.mutate({ id: viewedScenarioId, label: trimmed })
          }
        }}
      >
        <Bookmark class="h-4 w-4" />
        {$saveMutation.isPending ? 'Saving…' : 'Save scenario'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

<DialogPrimitive.Root bind:open={() => confirmingCommit, (next) => { if (!next) confirmingCommit = false }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Commit sandbox to active plan?</DialogTitle>
      <DialogDescription>
        Replaces your active plan with the sandbox's contents. The previous active plan is archived and stays accessible from the database (it will appear in History once Phase 2.5c slice 2 ships per-plan history navigation). You can confirm before applying.
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$commitMutation.isPending} onclick={() => (confirmingCommit = false)}>
        Cancel
      </Button>
      <Button
        disabled={$commitMutation.isPending}
        onclick={() => {
          if (viewedScenarioId !== null) $commitMutation.mutate(viewedScenarioId)
        }}
      >
        {$commitMutation.isPending ? 'Committing…' : 'Commit to active'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

