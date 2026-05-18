<script lang="ts">
  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query'
  import { Beaker } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'
  import { writable } from 'svelte/store'

  import PlanCategoriesTable from '$components/quartz/plan-categories-table.svelte'
  import PlanDiffCard from '$components/quartz/plan-diff-card.svelte'
  import PlanHistoryCard, { type PlanHistoryEntry } from '$components/quartz/plan-history-card.svelte'
  import PlanProjectedImpactCard from '$components/quartz/plan-projected-impact-card.svelte'
  import ScreenHeader from '$components/quartz/screen-header.svelte'
  import Tabs from '$components/quartz/tabs.svelte'
  import PlanCategorySheet, { type EditorSelection } from '$components/plan-category-sheet.svelte'
  import PlanHistorySheet from '$components/plan-history-sheet.svelte'
  import Button from '$components/ui/button.svelte'
  import DialogContent from '$components/ui/dialog-content.svelte'
  import DialogDescription from '$components/ui/dialog-description.svelte'
  import DialogFooter from '$components/ui/dialog-footer.svelte'
  import DialogHeader from '$components/ui/dialog-header.svelte'
  import DialogTitle from '$components/ui/dialog-title.svelte'
  import Input from '$components/ui/input.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    type ActivePlanResponse,
    type CompareResponse,
    type PlanCategory,
    commitScenario,
    compareScenario,
    createScenario,
    discardScenario,
    getActivePlan,
    getErrorMessage,
    getScenario,
    getStatus,
    getSummary,
    getYearEndProjection,
    listPlanRevisions,
    listScenarios,
    saveScenario,
  } from '$lib/api'

  // ----- data -----
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

  // Honour ?scenario=<id> on mount/refresh so a sandbox URL resumes after a
  // hard refresh, but never silently re-enter sandbox after the user
  // discards. The guard tracks the consumed param value.
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

  // Right-rail data. The diff card needs compareScenario for the active
  // sandbox; impact + history are useful in both modes.
  type ScenarioCompareOpts = {
    queryKey: readonly unknown[]
    queryFn: () => Promise<CompareResponse>
    enabled: boolean
  }
  const compareOpts = writable<ScenarioCompareOpts>({
    queryKey: ['plan', 'compare', null],
    queryFn: () => Promise.reject(new Error('disabled')) as Promise<CompareResponse>,
    enabled: false,
  })
  $effect(() => {
    if (viewedScenarioId === null) {
      compareOpts.set({
        queryKey: ['plan', 'compare', null],
        queryFn: () => Promise.reject(new Error('disabled')) as Promise<CompareResponse>,
        enabled: false,
      })
    } else {
      const id = viewedScenarioId
      compareOpts.set({
        queryKey: ['plan', 'compare', id],
        queryFn: () => compareScenario(id),
        enabled: browser,
      })
    }
  })
  const compareQuery = createQuery(compareOpts)

  const currentMonth = (() => {
    const d = new Date()
    return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
  })()
  const summaryQuery = createQuery({
    queryKey: ['summary', 'plan-editor', currentMonth],
    queryFn: () => getSummary(currentMonth),
    enabled: browser,
  })
  const projectionQuery = createQuery({
    queryKey: ['projection', 'plan-editor'],
    queryFn: () => getYearEndProjection(),
    enabled: browser,
  })

  let activePlanIdForRevisions = $derived($planQuery.data?.plan.id ?? null)
  type RevisionsOpts = {
    queryKey: readonly unknown[]
    queryFn: () => Promise<{ revisions: Array<any> }>
    enabled: boolean
  }
  const revisionsOpts = writable<RevisionsOpts>({
    queryKey: ['plan', 'revisions', null],
    queryFn: () => Promise.reject(new Error('disabled')),
    enabled: false,
  })
  $effect(() => {
    const id = activePlanIdForRevisions
    if (id === null) {
      revisionsOpts.set({
        queryKey: ['plan', 'revisions', null],
        queryFn: () => Promise.reject(new Error('disabled')),
        enabled: false,
      })
    } else {
      revisionsOpts.set({
        queryKey: ['plan', 'revisions', id],
        queryFn: () => listPlanRevisions(id, 10),
        enabled: browser,
      })
    }
  })
  const revisionsQuery = createQuery(revisionsOpts)

  // ----- tab filter -----
  type TabValue = 'all' | 'edited' | 'monthly' | 'sinking' | 'stipends'
  let tabValue: TabValue = $state('all')
  let editedCount = $derived(
    ($compareQuery.data?.rows ?? []).filter((r) => r.vs_active_milliunits !== 0).length,
  )
  let tabs = $derived([
    { value: 'all' as const, label: 'All categories' },
    { value: 'edited' as const, label: `Edited (${editedCount})` },
    { value: 'monthly' as const, label: 'Monthly' },
    { value: 'sinking' as const, label: 'Sinking' },
    { value: 'stipends' as const, label: 'Stipends' },
  ])

  // ----- labels -----
  function versionLabel(planId: number | undefined, draft = false): string {
    if (planId === undefined) return '—'
    return draft ? `v${planId}-draft` : `v${planId}`
  }
  let livePlanLabel = $derived(versionLabel($planQuery.data?.plan.id))
  let draftPlanLabel = $derived(versionLabel(viewedScenarioId ?? undefined, true))

  // ----- selection / dialogs -----
  let selection: EditorSelection = $state(null)
  let historyOpen = $state(false)
  let confirmingDiscard = $state(false)
  let confirmingCommit = $state(false)
  let confirmingSave = $state(false)
  let saveLabel = $state('')
  let saveError: string | null = $state(null)

  function defaultSaveLabel(): string {
    const now = new Date()
    return `Sandbox ${now.toISOString().slice(0, 10)}`
  }

  // ----- mutations -----
  const queryClient = useQueryClient()
  async function invalidatePlanState() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan'] }),
      queryClient.invalidateQueries({ queryKey: ['scenarios'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
      queryClient.invalidateQueries({ queryKey: ['projection'] }),
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
    onSuccess: async () => {
      viewedScenarioId = null
      confirmingCommit = false
      await invalidatePlanState()
      toast.success('Sandbox committed — active plan now reflects your changes.')
    },
    onError: (error) => {
      confirmingCommit = false
      toast.error(getErrorMessage(error))
    },
  })

  const saveMutation = createMutation({
    mutationFn: ({ id, label }: { id: number; label: string }) => saveScenario(id, label),
    onSuccess: async (response) => {
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

  function onEditCategory(cat: PlanCategory): void {
    selection = { mode: 'edit', planId: cat.plan_id, category: cat }
  }

  function startSandbox(): void {
    if (!inSandboxMode) {
      $startSandboxMutation.mutate()
    }
  }

  // ----- history entries -----
  let revisionEntries = $derived.by<PlanHistoryEntry[]>(() => {
    const out: PlanHistoryEntry[] = []
    if (viewedScenarioId !== null) {
      out.push({
        label: draftPlanLabel,
        note: `${editedCount} staged edit${editedCount === 1 ? '' : 's'}`,
        who: 'You · sandbox',
        when: 'now',
        active: true,
      })
    }
    const revisions = $revisionsQuery.data?.revisions ?? []
    for (const rev of revisions) {
      out.push({
        label: `r${rev.id}`,
        note: rev.summary ?? `${rev.change_count} change${rev.change_count === 1 ? '' : 's'}`,
        who: rev.source.replace(/_/g, ' '),
        when: relativeTime(rev.created_at),
      })
      if (out.length >= 6) break
    }
    return out
  })

  function relativeTime(iso: string): string {
    const diff = Date.now() - Date.parse(iso)
    const minutes = Math.round(diff / 60_000)
    if (minutes < 60) return `${minutes}m`
    const hours = Math.round(minutes / 60)
    if (hours < 48) return `${hours}h`
    return `${Math.round(hours / 24)}d`
  }

  // ----- projected impact figures -----
  let projectedBefore = $derived<number | undefined>(
    ($projectionQuery.data?.totals?.projected_annual_milliunits as number | undefined) ?? undefined,
  )
  let plannedAnnual = $derived<number | undefined>(
    ($projectionQuery.data?.totals?.planned_annual_milliunits as number | undefined) ?? undefined,
  )
  // Before+After delta is the net monthly change from the diff card * months
  // remaining in the plan year. A rough but useful approximation.
  let projectedAfter = $derived.by<number | undefined>(() => {
    if (projectedBefore === undefined) return undefined
    const net = $compareQuery.data?.totals.vs_active_milliunits ?? 0
    const now = new Date()
    const monthsRemaining = 12 - now.getMonth()
    return projectedBefore + net * monthsRemaining
  })
</script>

<svelte:head>
  <title>Plan · Finclaide</title>
</svelte:head>

<section class="flex flex-col gap-5 px-7 py-6">
  <ScreenHeader
    pill={inSandboxMode ? 'Plan · Sandbox' : 'Plan · Live'}
    title="Editor"
    subtitle={inSandboxMode
      ? `Plan ${livePlanLabel} → draft ${draftPlanLabel}`
      : `Plan ${livePlanLabel}`}
    tone="plan"
  >
    {#snippet actions()}
      {#if inSandboxMode}
        <button
          type="button"
          class="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-secondary"
          onclick={() => (confirmingDiscard = true)}
          disabled={scenarioBusy}
        >
          Discard draft
        </button>
        <button
          type="button"
          class="rounded-lg border border-border bg-card px-3 py-1.5 text-xs font-medium hover:bg-secondary"
          onclick={() => {
            saveLabel = defaultSaveLabel()
            saveError = null
            confirmingSave = true
          }}
          disabled={scenarioBusy}
        >
          Save scenario
        </button>
        <button
          type="button"
          class="rounded-lg bg-[#4E46E5] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90"
          onclick={() => (confirmingCommit = true)}
          disabled={scenarioBusy}
        >
          Commit
        </button>
      {:else}
        <button
          type="button"
          class="rounded-lg bg-[#4E46E5] px-3 py-1.5 text-xs font-medium text-white hover:opacity-90 disabled:opacity-50"
          onclick={startSandbox}
          disabled={$startSandboxMutation.isPending || $planQuery.data === undefined}
        >
          {existingSandbox ? 'Continue sandbox' : 'Start sandbox'}
        </button>
      {/if}
    {/snippet}
  </ScreenHeader>

  <Tabs {tabs} bind:value={tabValue} />

  {#if displayedQueryLoading}
    <Skeleton class="h-[640px] rounded-2xl" />
  {:else if displayedQueryError}
    <div class="rounded-xl border border-border bg-card p-6">
      <h2 class="text-base font-semibold">Planning is unavailable</h2>
      <p class="mt-2 text-sm text-muted-foreground">
        {displayedQueryError instanceof Error ? displayedQueryError.message : 'Could not load the plan.'}
      </p>
      <p class="mt-3 text-xs text-muted-foreground">
        If you have not imported a budget yet, run an import from the Operate page first.
      </p>
    </div>
  {:else if displayedPlan}
    <div class="grid gap-4" style="grid-template-columns: 1.4fr 1fr">
      <div class="flex flex-col gap-4">
        <PlanCategoriesTable
          plan={displayedPlan}
          summary={$summaryQuery.data}
          compare={$compareQuery.data}
          filter={tabValue}
          {onEditCategory}
        />
      </div>

      <div class="flex flex-col gap-4">
        <PlanDiffCard
          compare={$compareQuery.data}
          fromLabel={livePlanLabel}
          toLabel={draftPlanLabel}
        />
        <PlanProjectedImpactCard
          beforeMilliunits={projectedBefore}
          afterMilliunits={projectedAfter}
          planMilliunits={plannedAnnual}
          confidenceNote={projectedBefore !== undefined && plannedAnnual !== undefined
            ? `Year-end projection from current run rate; refreshed when actuals or the plan change.`
            : undefined}
        />
        <PlanHistoryCard entries={revisionEntries} onOpen={() => (historyOpen = true)} />
      </div>
    </div>
  {/if}
</section>

<PlanCategorySheet
  {selection}
  onClose={() => {
    selection = null
    invalidatePlanState()
  }}
/>

{#if displayedPlan}
  <PlanHistorySheet
    open={historyOpen}
    planId={displayedPlan.plan.id}
    currentBlocks={displayedPlan.blocks}
    onClose={() => (historyOpen = false)}
  />
{/if}

<DialogPrimitive.Root bind:open={() => confirmingDiscard, (next) => { if (!next) confirmingDiscard = false }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Discard sandbox?</DialogTitle>
      <DialogDescription>
        Throws away all edits made since the sandbox was created. The active plan is unchanged.
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$discardMutation.isPending} onclick={() => (confirmingDiscard = false)}>
        Cancel
      </Button>
      <Button
        variant="outline"
        class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
        disabled={$discardMutation.isPending || viewedScenarioId === null}
        onclick={() => viewedScenarioId !== null && $discardMutation.mutate(viewedScenarioId)}
      >
        {$discardMutation.isPending ? 'Discarding…' : 'Discard sandbox'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

<DialogPrimitive.Root bind:open={() => confirmingSave, (next) => { if (!next) confirmingSave = false }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Save scenario</DialogTitle>
      <DialogDescription>
        Saves the sandbox as a named scenario you can revisit, compare, or commit later.
      </DialogDescription>
    </DialogHeader>
    <div class="space-y-3">
      <label class="text-sm font-medium" for="scenario-label">Label</label>
      <Input id="scenario-label" bind:value={saveLabel} />
      {#if saveError}
        <p class="text-sm text-rose-200">{saveError}</p>
      {/if}
    </div>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$saveMutation.isPending} onclick={() => (confirmingSave = false)}>
        Cancel
      </Button>
      <Button
        disabled={$saveMutation.isPending || saveLabel.trim().length === 0 || viewedScenarioId === null}
        onclick={() => {
          if (viewedScenarioId === null) return
          $saveMutation.mutate({ id: viewedScenarioId, label: saveLabel.trim() })
        }}
      >
        {$saveMutation.isPending ? 'Saving…' : 'Save'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

<DialogPrimitive.Root bind:open={() => confirmingCommit, (next) => { if (!next) confirmingCommit = false }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Commit sandbox?</DialogTitle>
      <DialogDescription>
        Replaces the active plan with the sandbox's category values. Old plan rows are archived.
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$commitMutation.isPending} onclick={() => (confirmingCommit = false)}>
        Cancel
      </Button>
      <Button
        disabled={$commitMutation.isPending || viewedScenarioId === null}
        onclick={() => viewedScenarioId !== null && $commitMutation.mutate(viewedScenarioId)}
      >
        {$commitMutation.isPending ? 'Committing…' : 'Commit'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

