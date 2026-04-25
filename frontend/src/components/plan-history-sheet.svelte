<script lang="ts">
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query'
  import { History, RotateCcw } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'
  import { writable } from 'svelte/store'

  import Button from '$components/ui/button.svelte'
  import DialogContent from '$components/ui/dialog-content.svelte'
  import DialogDescription from '$components/ui/dialog-description.svelte'
  import DialogFooter from '$components/ui/dialog-footer.svelte'
  import DialogHeader from '$components/ui/dialog-header.svelte'
  import DialogTitle from '$components/ui/dialog-title.svelte'
  import Skeleton from '$components/ui/skeleton.svelte'
  import SheetContent from '$components/ui/sheet-content.svelte'
  import {
    getErrorMessage,
    getPlanRevision,
    listPlanRevisions,
    restorePlanRevision,
    type ActivePlanResponse,
    type PlanCategory,
    type PlanRevisionDetail,
    type PlanRevisionSource,
  } from '$lib/api'
  import { formatMoney, formatRunAt } from '$lib/format'

  type Props = {
    open: boolean
    planId: number | null
    currentBlocks: ActivePlanResponse['blocks']
    onClose: () => void
  }
  let { open, planId, currentBlocks, onClose }: Props = $props()

  let selectedRevisionId: number | null = $state(null)
  let confirmingRestore = $state(false)

  const queryClient = useQueryClient()

  type ListOpts = {
    queryKey: readonly unknown[]
    queryFn: () => Promise<Awaited<ReturnType<typeof listPlanRevisions>>>
    enabled: boolean
  }
  type DetailOpts = {
    queryKey: readonly unknown[]
    queryFn: () => Promise<PlanRevisionDetail | null>
    enabled: boolean
  }

  const listOpts = writable<ListOpts>({
    queryKey: ['plan', 'revisions', null],
    queryFn: () => Promise.resolve({ revisions: [] }),
    enabled: false,
  })
  $effect(() => {
    listOpts.set({
      queryKey: ['plan', 'revisions', planId],
      queryFn: () =>
        planId ? listPlanRevisions(planId) : Promise.resolve({ revisions: [] }),
      enabled: open && planId !== null,
    })
  })
  const listQuery = createQuery(listOpts)

  const detailOpts = writable<DetailOpts>({
    queryKey: ['plan', 'revision', null],
    queryFn: () => Promise.resolve(null),
    enabled: false,
  })
  $effect(() => {
    const current = selectedRevisionId
    detailOpts.set({
      queryKey: ['plan', 'revision', current],
      queryFn: () => (current ? getPlanRevision(current) : Promise.resolve(null)),
      enabled: current !== null,
    })
  })
  const detailQuery = createQuery(detailOpts)

  const restoreMutation = createMutation({
    mutationFn: (revisionId: number) => restorePlanRevision(revisionId),
    onSuccess: async () => {
      toast.success('Plan restored')
      await Promise.all([
        queryClient.invalidateQueries({ queryKey: ['plan'] }),
        queryClient.invalidateQueries({ queryKey: ['summary'] }),
      ])
      confirmingRestore = false
      selectedRevisionId = null
      onClose()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error))
      confirmingRestore = false
    },
  })

  $effect(() => {
    if (!open) {
      selectedRevisionId = null
      confirmingRestore = false
    }
  })

  const SOURCE_BADGE: Record<PlanRevisionSource, { label: string; class: string }> = {
    ui_create: { label: 'create', class: 'bg-emerald-500/[0.12] text-emerald-100' },
    ui_update: { label: 'edit', class: 'bg-sky-500/[0.12] text-sky-100' },
    ui_delete: { label: 'delete', class: 'bg-rose-500/[0.12] text-rose-100' },
    ui_rename: { label: 'rename', class: 'bg-violet-500/[0.12] text-violet-100' },
    importer: { label: 'import', class: 'bg-amber-500/[0.18] text-amber-100' },
    migration: { label: 'migration', class: 'bg-slate-500/[0.18] text-slate-100' },
    restore: { label: 'restore', class: 'bg-slate-500/[0.18] text-slate-100' },
  }

  type DiffRow = {
    label: string
    block: string
    plannedDelta: number | null
    annualDelta: number | null
    snapshotPlanned: number | null
    snapshotAnnual: number | null
    livePlanned: number | null
    liveAnnual: number | null
  }

  function buildLiveIndex(): Map<string, PlanCategory> {
    const map = new Map<string, PlanCategory>()
    for (const block of Object.values(currentBlocks)) {
      for (const row of block) {
        map.set(`${row.group_name}::${row.category_name}`, row)
      }
    }
    return map
  }

  function buildDiff(snapshot: PlanCategory[]): DiffRow[] {
    const live = buildLiveIndex()
    const diffs: DiffRow[] = []
    const seen = new Set<string>()

    for (const row of snapshot) {
      const key = `${row.group_name}::${row.category_name}`
      seen.add(key)
      const liveRow = live.get(key)
      const livePlanned = liveRow?.planned_milliunits ?? null
      const liveAnnual = liveRow?.annual_target_milliunits ?? null
      const plannedDelta = liveRow ? row.planned_milliunits - liveRow.planned_milliunits : null
      const annualDelta = liveRow
        ? row.annual_target_milliunits - liveRow.annual_target_milliunits
        : null
      const planChanged = liveRow ? plannedDelta !== 0 || annualDelta !== 0 : true
      if (!planChanged) continue
      diffs.push({
        label: `${row.group_name} / ${row.category_name}`,
        block: row.block,
        plannedDelta,
        annualDelta,
        snapshotPlanned: row.planned_milliunits,
        snapshotAnnual: row.annual_target_milliunits,
        livePlanned,
        liveAnnual,
      })
    }

    for (const [key, liveRow] of live) {
      if (seen.has(key)) continue
      diffs.push({
        label: `${liveRow.group_name} / ${liveRow.category_name}`,
        block: liveRow.block,
        plannedDelta: -liveRow.planned_milliunits,
        annualDelta: -liveRow.annual_target_milliunits,
        snapshotPlanned: null,
        snapshotAnnual: null,
        livePlanned: liveRow.planned_milliunits,
        liveAnnual: liveRow.annual_target_milliunits,
      })
    }

    return diffs
  }

  function formatDelta(value: number | null): string {
    if (value === null || value === 0) return '—'
    const formatted = formatMoney(Math.abs(value))
    return value > 0 ? `+${formatted}` : `−${formatted}`
  }
</script>

<DialogPrimitive.Root bind:open={() => open, (next) => { if (!next) onClose() }}>
  <SheetContent class="border-border/40 bg-card text-card-foreground sm:max-w-2xl" side="right">
    <DialogHeader>
      <DialogTitle class="flex items-center gap-2">
        <History class="h-4 w-4" />
        Plan history
      </DialogTitle>
      <DialogDescription>
        Every save creates a snapshot. Pick one to see what changed and restore if needed.
      </DialogDescription>
    </DialogHeader>

    <div class="mt-6 grid h-[calc(100%-7rem)] gap-4 lg:grid-cols-[280px_1fr]">
      <div class="overflow-y-auto rounded-md border bg-muted/15 p-1" aria-label="Plan revisions">
        {#if $listQuery.isLoading}
          <Skeleton class="h-[400px] rounded" />
        {:else if $listQuery.isError}
          <div class="p-3 text-sm text-rose-200">
            Could not load revisions: {getErrorMessage($listQuery.error)}
          </div>
        {:else if !$listQuery.data || $listQuery.data.revisions.length === 0}
          <div class="p-3 text-sm text-muted-foreground">No revisions yet — edit the plan to start the history.</div>
        {:else}
          {#each $listQuery.data.revisions as rev (rev.id)}
            {@const badge = SOURCE_BADGE[rev.source]}
            <button
              type="button"
              class={`flex w-full flex-col gap-1 rounded p-2.5 text-left text-sm transition-colors hover:bg-muted/40 ${selectedRevisionId === rev.id ? 'bg-muted/50 ring-1 ring-primary/40' : ''}`}
              onclick={() => (selectedRevisionId = rev.id)}
            >
              <div class="flex items-center justify-between gap-2">
                <span class={`rounded px-1.5 py-0.5 text-[10px] font-medium uppercase tracking-wide ${badge.class}`}>
                  {badge.label}
                </span>
                <span class="text-[11px] text-muted-foreground">{formatRunAt(rev.created_at)}</span>
              </div>
              <div class="text-foreground">{rev.summary ?? `Revision ${rev.id}`}</div>
              <div class="text-[11px] text-muted-foreground">
                {rev.change_count} {rev.change_count === 1 ? 'category' : 'categories'}
              </div>
            </button>
          {/each}
        {/if}
      </div>

      <div class="overflow-y-auto rounded-md border bg-muted/15 p-3">
        {#if selectedRevisionId === null}
          <div class="text-sm text-muted-foreground">Select a revision to preview the diff.</div>
        {:else if $detailQuery.isLoading || !$detailQuery.data}
          <Skeleton class="h-[300px] rounded" />
        {:else}
          {@const detail = $detailQuery.data}
          {@const diffs = buildDiff(detail.snapshot)}
          <div class="flex items-start justify-between gap-3">
            <div>
              <div class="text-sm text-muted-foreground">{detail.summary ?? 'Revision detail'}</div>
              <div class="mt-1 text-xs text-muted-foreground">{formatRunAt(detail.created_at)}</div>
            </div>
            <Button size="sm" disabled={$restoreMutation.isPending} onclick={() => (confirmingRestore = true)}>
              <RotateCcw class="h-3.5 w-3.5" />
              Restore
            </Button>
          </div>

          <div class="mt-4 space-y-2">
            {#if diffs.length === 0}
              <div class="text-sm text-muted-foreground">
                This revision matches the current plan. Nothing to restore.
              </div>
            {:else}
              <div class="text-[11px] uppercase tracking-wide text-muted-foreground">
                {diffs.length} {diffs.length === 1 ? 'category differs' : 'categories differ'} from the current plan
              </div>
              <div class="grid gap-1.5">
                {#each diffs as row (row.label)}
                  <div class="grid grid-cols-[1fr_auto_auto] items-center gap-3 rounded bg-muted/30 px-3 py-2 text-sm">
                    <div>
                      <div class="font-medium text-foreground">{row.label}</div>
                      <div class="text-[11px] text-muted-foreground">{row.block}</div>
                    </div>
                    <div class="font-mono text-xs text-muted-foreground">
                      planned {row.snapshotPlanned !== null ? formatMoney(row.snapshotPlanned) : '—'}
                      → {row.livePlanned !== null ? formatMoney(row.livePlanned) : '(removed)'}
                    </div>
                    <div class={`font-mono text-xs ${row.plannedDelta && row.plannedDelta < 0 ? 'text-emerald-200' : row.plannedDelta && row.plannedDelta > 0 ? 'text-rose-200' : 'text-muted-foreground'}`}>
                      Δ {formatDelta(row.plannedDelta)}
                    </div>
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/if}
      </div>
    </div>
  </SheetContent>
</DialogPrimitive.Root>

<DialogPrimitive.Root
  bind:open={() => confirmingRestore, (next) => { if (!next && !$restoreMutation.isPending) confirmingRestore = false }}
>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Restore this revision?</DialogTitle>
      <DialogDescription>
        The current state will be saved as a new revision before the restore, so you can undo this action by restoring it back.
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$restoreMutation.isPending} onclick={() => (confirmingRestore = false)}>
        Cancel
      </Button>
      <Button
        disabled={$restoreMutation.isPending}
        onclick={() => {
          if (selectedRevisionId !== null) {
            $restoreMutation.mutate(selectedRevisionId)
          }
        }}
      >
        {$restoreMutation.isPending ? 'Restoring…' : 'Restore'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>
