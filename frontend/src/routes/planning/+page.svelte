<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { Tabs as TabsPrimitive } from 'bits-ui'
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query'
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { AlertTriangle, Beaker, Bookmark, Check, Columns2, History, Plus, Trash2 } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'
  import { writable } from 'svelte/store'

  import CompareDrawer from '$components/compare-drawer.svelte'
  import DataTable, { type DataTableColumn } from '$components/data-table.svelte'
  import PlanCategorySheet, { type EditorSelection } from '$components/plan-category-sheet.svelte'
  import PlanHistorySheet from '$components/plan-history-sheet.svelte'
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
    getScenario,
    getStatus,
    listScenarios,
    saveScenario,
  } from '$lib/api'
  import { formatMoney } from '$lib/format'

  const BLOCK_ORDER: BlockKey[] = ['monthly', 'annual', 'one_time', 'stipends', 'savings']

  function blockColumns(block: BlockKey): DataTableColumn<PlanCategory>[] {
    return [
      { key: 'group_name', header: 'Group', cellClass: 'font-medium' },
      { key: 'category_name', header: 'Category' },
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

  const planQuery = createQuery({
    queryKey: ['plan', 'active'],
    queryFn: () => getActivePlan(),
    enabled: browser,
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
  let displayedQueryLoading = $derived(
    viewedScenarioId === null ? $planQuery.isLoading : $scenarioPlanQuery.isLoading,
  )
  let displayedQueryError = $derived(
    viewedScenarioId === null ? $planQuery.error : $scenarioPlanQuery.error,
  )
  let existingSandbox = $derived(
    $scenariosQuery.data?.scenarios.find((s) => s.label === null) ?? null,
  )

  let activeBlock: BlockKey = $state('monthly')
  let selection: EditorSelection = $state(null)
  let historyOpen = $state(false)
  let confirmingDiscard = $state(false)
  let confirmingCommit = $state(false)
  let confirmingSave = $state(false)
  let saveLabel: string = $state('')
  let saveError: string | null = $state(null)
  let compareOpen = $state(false)

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
  <div class="space-y-3">
    <div class="flex items-center justify-between text-sm text-muted-foreground">
      <span>
        {rows.length} {rows.length === 1 ? 'category' : 'categories'} in {BLOCK_LABELS[block]}
      </span>
      <span class="font-mono text-foreground">Block total {formatMoney(total)}</span>
    </div>
    <DataTable
      data={rows}
      {columns}
      onRowClick={(row) => (selection = { mode: 'edit', planId: rows[0]?.plan_id ?? 0, category: row })}
      emptyMessage={`No ${BLOCK_LABELS[block]} categories yet. Click Add row to create one.`}
    />
  </div>
{/snippet}

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

