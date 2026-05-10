<script lang="ts">
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { createMutation, useQueryClient } from '@tanstack/svelte-query'
  import { CloudUpload, LoaderCircle, Plus, ScanSearch, Trash2, Wand2 } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'

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
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    createPlanCategory,
    deletePlanCategory,
    getErrorMessage,
    applyPlanToYnab,
    updatePlanCategory,
    type ActivePlanResponse,
    type PlanCategory,
    type ReconcilePreviewEntry,
    type ReconcilePreviewResponse,
  } from '$lib/api'

  type Props = {
    preview: ReconcilePreviewResponse | undefined
    plan?: ActivePlanResponse | undefined
    isLoading: boolean
    isError: boolean
    error: unknown
    onRefresh?: () => void
    onRetryReconcile?: () => void
    retrying?: boolean
  }

  let {
    preview,
    plan,
    isLoading,
    isError,
    error,
    onRefresh,
    onRetryReconcile,
    retrying,
  }: Props = $props()

  const queryClient = useQueryClient()
  let confirmingDelete: { id: number; group: string; name: string; planned: number } | null = $state(null)

  // ------- helpers ---------------------------------------------------------

  function planId(): number | null {
    return plan?.plan?.id ?? null
  }

  /** Look up a category by (group, name) in the active plan. */
  function findPlanCategory(group: string, name: string): PlanCategory | null {
    if (!plan) return null
    for (const block of [
      plan.blocks.monthly,
      plan.blocks.annual,
      plan.blocks.one_time,
      plan.blocks.stipends,
      plan.blocks.savings,
    ]) {
      const hit = block.find((c) => c.group_name === group && c.category_name === name)
      if (hit) return hit
    }
    return null
  }

  /** Infer the block for a new YNAB category by checking what block
   * existing categories in the same group use. Defaults to "monthly". */
  function inferBlock(groupName: string): 'monthly' | 'annual' | 'one_time' | 'stipends' | 'savings' {
    if (!plan) return 'monthly'
    const candidates: PlanCategory[] = []
    for (const [blockName, rows] of Object.entries(plan.blocks)) {
      void blockName
      for (const c of rows) {
        if (c.group_name === groupName) candidates.push(c)
      }
    }
    if (candidates.length === 0) return 'monthly'
    return candidates[0].block as 'monthly' | 'annual' | 'one_time' | 'stipends' | 'savings'
  }

  async function invalidateAll() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['reconcile-preview'] }),
      queryClient.invalidateQueries({ queryKey: ['plan'] }),
      queryClient.invalidateQueries({ queryKey: ['plan-active'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
      queryClient.invalidateQueries({ queryKey: ['status'] }),
    ])
  }

  // ------- mutations -------------------------------------------------------

  const renameMutation = createMutation({
    mutationFn: async (args: { plan_category_id: number; to_group: string; to_name: string }) => {
      const id = planId()
      if (id === null) throw new Error('No active plan loaded.')
      return updatePlanCategory(args.plan_category_id, {
        plan_id: id,
        rename: { group_name: args.to_group, category_name: args.to_name },
      })
    },
    onSuccess: async (_data, vars) => {
      toast.success(`Renamed plan category to "${vars.to_name}".`)
      await invalidateAll()
    },
    onError: (e) => toast.error(`Rename failed: ${getErrorMessage(e)}`),
  })

  const addMutation = createMutation({
    mutationFn: async (args: { group: string; name: string }) => {
      const id = planId()
      if (id === null) throw new Error('No active plan loaded.')
      return createPlanCategory({
        plan_id: id,
        group_name: args.group,
        category_name: args.name,
        block: inferBlock(args.group),
        planned_milliunits: 0,
        annual_target_milliunits: 0,
        due_month: null,
        notes: null,
      })
    },
    onSuccess: async (_data, vars) => {
      toast.success(`Added "${vars.group} / ${vars.name}" to plan.`)
      await invalidateAll()
    },
    onError: (e) => toast.error(`Add failed: ${getErrorMessage(e)}`),
  })

  const deleteMutation = createMutation({
    mutationFn: async (args: { plan_category_id: number }) => {
      const id = planId()
      if (id === null) throw new Error('No active plan loaded.')
      await deletePlanCategory(args.plan_category_id, id)
    },
    onSuccess: async () => {
      toast.success('Removed category from plan.')
      confirmingDelete = null
      await invalidateAll()
    },
    onError: (e) => toast.error(`Delete failed: ${getErrorMessage(e)}`),
  })

  const applyPlanToYnabMutation = createMutation({
    mutationFn: applyPlanToYnab,
    onSuccess: async (data) => {
      if (data.reconcile_error) {
        toast.success(`Updated YNAB. ${data.reconcile_error.message}`)
      } else {
        toast.success('Updated YNAB and reconcile now passes.')
      }
      await invalidateAll()
    },
    onError: (e) => toast.error(`YNAB update failed: ${getErrorMessage(e)}`),
  })

  let busy = $derived(
    $renameMutation.isPending ||
      $addMutation.isPending ||
      $deleteMutation.isPending ||
      $applyPlanToYnabMutation.isPending,
  )

  // ------- coalesce reciprocal pairs --------------------------------------

  // Build the set of plan_category_ids covered by an extra_in_ynab
  // suggestion. The matching missing_in_ynab row is hidden so the
  // operator only has to make one decision per pair.
  let coveredPlanIds = $derived((): Set<number> => {
    const out = new Set<number>()
    if (!preview) return out
    for (const row of preview.extra_in_ynab) {
      const pid = row.suggested_match?.plan_category_id ?? null
      if (pid !== null) out.add(pid)
    }
    return out
  })

  let visibleMissing = $derived((): ReconcilePreviewEntry[] => {
    if (!preview) return []
    return preview.missing_in_ynab.filter((row) => {
      const planRow = findPlanCategory(row.group_name, row.category_name)
      if (!planRow) return true
      return !coveredPlanIds().has(planRow.id)
    })
  })

  // ------- action handlers -------------------------------------------------

  function handleRename(row: ReconcilePreviewEntry) {
    const sm = row.suggested_match
    if (!sm || sm.plan_category_id === null) return
    $renameMutation.mutate({
      plan_category_id: sm.plan_category_id,
      to_group: row.group_name,
      to_name: row.category_name,
    })
  }

  function handleAdd(row: ReconcilePreviewEntry) {
    $addMutation.mutate({ group: row.group_name, name: row.category_name })
  }

  function handleUsePlanForRename(row: ReconcilePreviewEntry) {
    const sm = row.suggested_match
    if (!sm) return
    $applyPlanToYnabMutation.mutate({
      operation: 'rename_category',
      source: { group_name: row.group_name, category_name: row.category_name },
      target: { group_name: sm.group_name, category_name: sm.category_name },
    })
  }

  function handleCreateInYnab(row: ReconcilePreviewEntry) {
    $applyPlanToYnabMutation.mutate({
      operation: 'create_category',
      target: { group_name: row.group_name, category_name: row.category_name },
    })
  }

  function handleDelete(row: ReconcilePreviewEntry) {
    const planRow = findPlanCategory(row.group_name, row.category_name)
    if (!planRow) {
      toast.error('Could not locate plan category to delete.')
      return
    }
    if (planRow.planned_milliunits > 0) {
      confirmingDelete = {
        id: planRow.id,
        group: row.group_name,
        name: row.category_name,
        planned: planRow.planned_milliunits,
      }
      return
    }
    $deleteMutation.mutate({ plan_category_id: planRow.id })
  }
</script>

<Card class="border-amber-500/30 bg-amber-500/[0.05]">
  <CardHeader class="space-y-3">
    <div class="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
      <div>
        <CardTitle class="flex items-center gap-2 text-amber-100">
          <ScanSearch class="h-4 w-4" />
          Reconcile preview
        </CardTitle>
        <p class="mt-2 text-sm text-amber-100/80">
          Diff of the in-app plan against current YNAB categories. Apply suggested
          renames, add YNAB categories to the plan, or remove plan rows YNAB no
          longer has.
        </p>
      </div>
      <div class="flex gap-2">
        {#if onRefresh}
          <Button variant="outline" class="border-amber-200/30 text-amber-50 hover:bg-amber-500/10" onclick={onRefresh}>
            Refresh preview
          </Button>
        {/if}
        {#if onRetryReconcile}
          <Button
            variant="outline"
            class="border-amber-200/30 text-amber-50 hover:bg-amber-500/10"
            disabled={retrying || busy}
            onclick={onRetryReconcile}
          >
            {retrying ? 'Re-running…' : 'Re-run reconcile'}
          </Button>
        {/if}
      </div>
    </div>
  </CardHeader>
  <CardContent class="space-y-4">
    {#if isLoading}
      <Skeleton class="h-32 rounded-lg" />
    {:else if isError}
      <div class="rounded-lg bg-rose-500/[0.08] p-4 text-sm text-rose-100 ring-1 ring-inset ring-rose-500/20">
        Could not load reconcile preview: {getErrorMessage(error)}
      </div>
    {:else if preview}
      <div class="grid gap-3 md:grid-cols-3">
        <div class="rounded-lg p-4 ring-1 ring-inset border-emerald-400/30 bg-emerald-500/[0.06] text-emerald-100">
          <div class="text-label-upper">Exact matches</div>
          <div class="mt-2 font-mono text-2xl font-semibold">{preview.counts.exact}</div>
        </div>
        <div class="rounded-lg p-4 ring-1 ring-inset border-rose-400/30 bg-rose-500/[0.08] text-rose-100">
          <div class="text-label-upper">Missing in YNAB</div>
          <div class="mt-2 font-mono text-2xl font-semibold">{preview.counts.missing_in_ynab}</div>
        </div>
        <div class="rounded-lg p-4 ring-1 ring-inset border-cyan-400/30 bg-cyan-500/[0.06] text-cyan-100">
          <div class="text-label-upper">Extra in YNAB</div>
          <div class="mt-2 font-mono text-2xl font-semibold">{preview.counts.extra_in_ynab}</div>
        </div>
      </div>

      <!-- Extra in YNAB: rename or add -->
      <div class="rounded-lg bg-amber-500/[0.04] p-4">
        <div class="flex items-baseline justify-between gap-3">
          <div class="text-sm font-medium text-amber-50">Extra in YNAB</div>
          <div class="text-label">{preview.extra_in_ynab.length}</div>
        </div>
        <p class="mt-1 text-sm text-amber-100/70">
          Present in YNAB but not in your plan. Often a renamed category or a YNAB-side addition.
        </p>
        {#if preview.extra_in_ynab.length === 0}
          <div class="mt-3 rounded-lg p-3 text-sm bg-emerald-500/[0.06] text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
            No extra YNAB categories outside the plan.
          </div>
        {:else}
          <ul class="mt-3 space-y-1.5">
            {#each preview.extra_in_ynab as row (row.group_name + '/' + row.category_name)}
              <li class="rounded-md bg-muted/30 px-3 py-2 text-sm">
                <div class="flex flex-col gap-2 md:flex-row md:items-center md:justify-between">
                  <div class="min-w-0">
                    <div class="text-foreground">{row.group_name} / {row.category_name}</div>
                    {#if row.suggested_match && row.suggested_match.plan_category_id !== null}
                      <div class="mt-0.5 text-[11px] text-muted-foreground">
                        ↳ matches plan: {row.suggested_match.group_name} /
                        {row.suggested_match.category_name}
                        ({Math.round(row.suggested_match.confidence * 100)}% confidence)
                      </div>
                    {/if}
                  </div>
                  <div class="flex shrink-0 gap-2">
                    {#if row.suggested_match && row.suggested_match.plan_category_id !== null}
                      <Button
                        variant="outline"
                        class="border-amber-200/30 text-amber-50 hover:bg-amber-500/10"
                        disabled={busy || !plan}
                        onclick={() => handleRename(row)}
                      >
                        {#if $renameMutation.isPending}<LoaderCircle class="h-3.5 w-3.5 animate-spin" />{:else}<Wand2 class="h-3.5 w-3.5" />{/if}
                        Use YNAB
                      </Button>
                      <Button
                        variant="outline"
                        class="border-cyan-300/30 text-cyan-50 hover:bg-cyan-500/10"
                        disabled={busy || !plan}
                        onclick={() => handleUsePlanForRename(row)}
                      >
                        {#if $applyPlanToYnabMutation.isPending}<LoaderCircle class="h-3.5 w-3.5 animate-spin" />{:else}<CloudUpload class="h-3.5 w-3.5" />{/if}
                        Use plan
                      </Button>
                    {/if}
                    <Button
                      variant="outline"
                      class="border-amber-200/30 text-amber-50 hover:bg-amber-500/10"
                      disabled={busy || !plan}
                      onclick={() => handleAdd(row)}
                    >
                      {#if $addMutation.isPending}<LoaderCircle class="h-3.5 w-3.5 animate-spin" />{:else}<Plus class="h-3.5 w-3.5" />{/if}
                      Add to plan
                    </Button>
                  </div>
                </div>
              </li>
            {/each}
          </ul>
        {/if}
      </div>

      <!-- Missing in YNAB: delete (with reciprocal-pair coalescing) -->
      <div class="rounded-lg bg-amber-500/[0.04] p-4">
        <div class="flex items-baseline justify-between gap-3">
          <div class="text-sm font-medium text-amber-50">Missing in YNAB</div>
          <div class="text-label">{visibleMissing().length}</div>
        </div>
        <p class="mt-1 text-sm text-amber-100/70">
          In your plan but not in YNAB. Items already covered by a suggested rename
          above are hidden. Remaining rows are likely deletions.
        </p>
        {#if visibleMissing().length === 0}
          <div class="mt-3 rounded-lg p-3 text-sm bg-emerald-500/[0.06] text-emerald-100 ring-1 ring-inset ring-emerald-500/15">
            No remaining plan rows missing from YNAB.
          </div>
        {:else}
          <ul class="mt-3 space-y-1.5">
            {#each visibleMissing() as row (row.group_name + '/' + row.category_name)}
              <li class="flex items-center justify-between gap-3 rounded-md bg-muted/30 px-3 py-2 text-sm">
                <span class="text-foreground">{row.group_name} / {row.category_name}</span>
                <Button
                  variant="outline"
                  class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
                  disabled={busy || !plan}
                  onclick={() => handleDelete(row)}
                >
                  {#if $deleteMutation.isPending}<LoaderCircle class="h-3.5 w-3.5 animate-spin" />{:else}<Trash2 class="h-3.5 w-3.5" />{/if}
                  Delete from plan
                </Button>
                <Button
                  variant="outline"
                  class="border-cyan-300/30 text-cyan-50 hover:bg-cyan-500/10"
                  disabled={busy || !plan}
                  onclick={() => handleCreateInYnab(row)}
                >
                  {#if $applyPlanToYnabMutation.isPending}<LoaderCircle class="h-3.5 w-3.5 animate-spin" />{:else}<CloudUpload class="h-3.5 w-3.5" />{/if}
                  Create in YNAB
                </Button>
              </li>
            {/each}
          </ul>
        {/if}
      </div>
    {/if}
  </CardContent>
</Card>

<DialogPrimitive.Root bind:open={() => confirmingDelete !== null, (next) => { if (!next) confirmingDelete = null }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Delete plan category?</DialogTitle>
      <DialogDescription>
        {#if confirmingDelete}
          {confirmingDelete.group} / {confirmingDelete.name} has a planned amount of ${(confirmingDelete.planned / 1000).toFixed(2)}/mo. Removing it will lose that planning. There is no undo.
        {/if}
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$deleteMutation.isPending} onclick={() => (confirmingDelete = null)}>
        Cancel
      </Button>
      <Button
        variant="outline"
        class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
        disabled={$deleteMutation.isPending}
        onclick={() => {
          if (confirmingDelete) $deleteMutation.mutate({ plan_category_id: confirmingDelete.id })
        }}
      >
        {$deleteMutation.isPending ? 'Deleting…' : 'Delete category'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>
