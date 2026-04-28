<script lang="ts">
  import { browser } from '$app/environment'
  import { goto } from '$app/navigation'
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { createMutation, createQuery, useQueryClient } from '@tanstack/svelte-query'
  import { Bookmark, Check, FlaskConical, Layers, Trash2 } from 'lucide-svelte'
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
  import Skeleton from '$components/ui/skeleton.svelte'
  import {
    commitScenario,
    discardScenario,
    forkScenario,
    getErrorMessage,
    listScenarios,
    saveScenario,
    type ScenarioSummary,
  } from '$lib/api'
  import { formatRunAt } from '$lib/format'
  import { withBasePath } from '$lib/runtime'

  const queryClient = useQueryClient()

  const scenariosQuery = createQuery({
    queryKey: ['scenarios'],
    queryFn: listScenarios,
    enabled: browser,
  })

  let savedScenarios = $derived(
    $scenariosQuery.data?.scenarios.filter((s) => s.label !== null) ?? [],
  )
  let existingSandbox = $derived(
    $scenariosQuery.data?.scenarios.find((s) => s.label === null) ?? null,
  )

  // --- mutations ---------------------------------------------------------

  async function invalidate() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan'] }),
      queryClient.invalidateQueries({ queryKey: ['scenarios'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
    ])
  }

  const forkMutation = createMutation({
    mutationFn: (saved_id: number) => forkScenario(saved_id),
    onSuccess: async () => {
      await invalidate()
      goto(withBasePath('/planning'))
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const commitMutationLocal = createMutation({
    mutationFn: (id: number) => commitScenario(id),
    onSuccess: async () => {
      confirmingCommitFor = null
      await invalidate()
      toast.success('Scenario is now your active plan.')
    },
    onError: (error) => {
      confirmingCommitFor = null
      toast.error(getErrorMessage(error))
    },
  })

  const deleteMutation = createMutation({
    mutationFn: (id: number) => discardScenario(id),
    onSuccess: async () => {
      confirmingDeleteFor = null
      await invalidate()
      toast.success('Scenario deleted.')
    },
    onError: (error) => {
      confirmingDeleteFor = null
      toast.error(getErrorMessage(error))
    },
  })

  // --- modal state -------------------------------------------------------

  type Target = { id: number; label: string }

  let confirmingCommitFor: Target | null = $state(null)
  let confirmingDeleteFor: Target | null = $state(null)
  let compareTargetId: number | null = $state(null)

  // Auto-park modal: opens when the user clicks Open on a saved row while
  // a Sandbox already exists. parkLabel defaults to today's untitled name.
  let parkingFor: Target | null = $state(null)
  let parkLabel: string = $state('')
  let parkError: string | null = $state(null)
  let parkBusy: boolean = $state(false)

  function defaultParkLabel(): string {
    const now = new Date()
    const month = now.toLocaleString('en-US', { month: 'short' })
    const day = now.getDate()
    const year = now.getFullYear()
    return `Untitled scenario, ${month} ${day}, ${year}`
  }

  function startOpen(target: Target) {
    if (existingSandbox === null) {
      $forkMutation.mutate(target.id)
      return
    }
    parkingFor = target
    parkLabel = defaultParkLabel()
    parkError = null
    parkBusy = false
  }

  async function handleSaveAndOpen() {
    if (!parkingFor || !existingSandbox) return
    const target = parkingFor
    const label = parkLabel.trim()
    if (!label) {
      parkError = 'Name cannot be empty.'
      return
    }
    parkBusy = true
    parkError = null
    try {
      await saveScenario(existingSandbox.id, label)
    } catch (error) {
      parkBusy = false
      parkError = getErrorMessage(error)
      return
    }
    // Sandbox is now Saved — the partial-unique-sandbox slot is free.
    try {
      await forkScenario(target.id)
      parkingFor = null
      parkBusy = false
      await invalidate()
      goto(withBasePath('/planning'))
    } catch (error) {
      parkBusy = false
      parkingFor = null
      await invalidate()
      toast.error(
        `Saved as '${label}' but couldn't open '${target.label}' — try again. (${getErrorMessage(error)})`,
      )
    }
  }

  async function handleDiscardAndOpen() {
    if (!parkingFor || !existingSandbox) return
    parkBusy = true
    parkError = null
    try {
      await discardScenario(existingSandbox.id)
    } catch (error) {
      parkBusy = false
      parkError = getErrorMessage(error)
      return
    }
    try {
      await forkScenario(parkingFor.id)
      parkingFor = null
      parkBusy = false
      await invalidate()
      goto(withBasePath('/planning'))
    } catch (error) {
      parkBusy = false
      parkingFor = null
      await invalidate()
      toast.error(getErrorMessage(error))
    }
  }

  function rowKey(s: ScenarioSummary): string {
    return `${s.id}`
  }
</script>

<Card class="border-border/40 bg-card">
  <CardHeader>
    <CardTitle class="flex items-center gap-2">
      <Layers class="h-4 w-4" />
      Saved scenarios
    </CardTitle>
    <p class="text-sm text-muted-foreground">
      Named alternatives you can compare, open as a fresh sandbox, or commit
      as your active plan. The active plan and any unnamed sandbox live on
      <a class="underline" href={withBasePath('/planning')}>Planning</a>.
    </p>
  </CardHeader>
  <CardContent>
    {#if $scenariosQuery.isLoading}
      <Skeleton class="h-[200px] rounded" />
    {:else if $scenariosQuery.isError}
      <div class="text-sm text-rose-200">
        Could not load scenarios: {getErrorMessage($scenariosQuery.error)}
      </div>
    {:else if savedScenarios.length === 0}
      <div class="rounded-md border border-dashed border-border/40 p-6 text-center text-sm text-muted-foreground">
        No saved scenarios yet. Open a sandbox on
        <a class="underline" href={withBasePath('/planning')}>Planning</a>
        and use Save to keep your work.
      </div>
    {:else}
      <ul class="divide-y divide-border/30">
        {#each savedScenarios as s (rowKey(s))}
          <li class="flex flex-col gap-3 py-3 md:flex-row md:items-center md:justify-between">
            <div>
              <div class="flex items-center gap-2 text-foreground">
                <FlaskConical class="h-3.5 w-3.5 text-muted-foreground" />
                <span class="font-medium">{s.label}</span>
                <span class="text-xs text-muted-foreground">
                  · {s.plan_year} · {s.category_count} categories
                </span>
              </div>
              <div class="mt-0.5 text-xs text-muted-foreground">
                Updated {formatRunAt(s.updated_at)}
              </div>
            </div>
            <div class="flex flex-wrap gap-2">
              <Button
                size="sm"
                variant="outline"
                disabled={$forkMutation.isPending}
                onclick={() => startOpen({ id: s.id, label: s.label ?? '' })}
              >
                Open
              </Button>
              <Button
                size="sm"
                variant="outline"
                onclick={() => (compareTargetId = s.id)}
              >
                Compare
              </Button>
              <Button
                size="sm"
                variant="outline"
                onclick={() => (confirmingCommitFor = { id: s.id, label: s.label ?? '' })}
              >
                <Check class="h-4 w-4" />
                Make active
              </Button>
              <Button
                size="sm"
                variant="outline"
                class="border-rose-500/30 text-rose-100 hover:bg-rose-500/10"
                onclick={() => (confirmingDeleteFor = { id: s.id, label: s.label ?? '' })}
              >
                <Trash2 class="h-4 w-4" />
                Delete
              </Button>
            </div>
          </li>
        {/each}
      </ul>
    {/if}
  </CardContent>
</Card>

<!-- Auto-park modal: opens when Open is clicked while a Sandbox exists. -->
<DialogPrimitive.Root
  bind:open={() => parkingFor !== null,
  (next: boolean) => {
    if (!next && !parkBusy) parkingFor = null
  }}
>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>
        {#if parkingFor}
          Save your sandbox before opening "{parkingFor.label}"?
        {:else}
          Save your sandbox?
        {/if}
      </DialogTitle>
      <DialogDescription>
        You have an open sandbox with edits. Name it to keep the work, then
        open this scenario as a new sandbox. Or discard the current sandbox
        if you don't need it.
      </DialogDescription>
    </DialogHeader>
    <div class="space-y-2">
      <label for="park-label" class="text-label">Name</label>
      <Input
        id="park-label"
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
      <Button
        variant="outline"
        disabled={parkBusy}
        onclick={() => (parkingFor = null)}
      >
        Cancel
      </Button>
      <Button
        variant="outline"
        class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
        disabled={parkBusy}
        onclick={() => void handleDiscardAndOpen()}
      >
        <Trash2 class="h-4 w-4" />
        Discard sandbox
      </Button>
      <Button disabled={parkBusy} onclick={() => void handleSaveAndOpen()}>
        <Bookmark class="h-4 w-4" />
        {parkBusy ? 'Working…' : 'Save & open'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

<!-- Make active confirm -->
<DialogPrimitive.Root
  bind:open={() => confirmingCommitFor !== null,
  (next: boolean) => {
    if (!next && !$commitMutationLocal.isPending) confirmingCommitFor = null
  }}
>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>
        {#if confirmingCommitFor}
          Make "{confirmingCommitFor.label}" your active plan?
        {:else}
          Make scenario active?
        {/if}
      </DialogTitle>
      <DialogDescription>
        Replaces your active plan with this scenario. The previous active
        plan is archived and remains accessible from History (where you can
        restore it).
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button
        variant="outline"
        disabled={$commitMutationLocal.isPending}
        onclick={() => (confirmingCommitFor = null)}
      >
        Cancel
      </Button>
      <Button
        disabled={$commitMutationLocal.isPending}
        onclick={() => {
          if (confirmingCommitFor !== null) {
            $commitMutationLocal.mutate(confirmingCommitFor.id)
          }
        }}
      >
        {$commitMutationLocal.isPending ? 'Activating…' : 'Make active'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>

<CompareDrawer
  open={compareTargetId !== null}
  scenarioId={compareTargetId}
  onClose={() => (compareTargetId = null)}
/>

<!-- Delete confirm -->
<DialogPrimitive.Root
  bind:open={() => confirmingDeleteFor !== null,
  (next: boolean) => {
    if (!next && !$deleteMutation.isPending) confirmingDeleteFor = null
  }}
>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>
        {#if confirmingDeleteFor}
          Delete "{confirmingDeleteFor.label}"?
        {:else}
          Delete scenario?
        {/if}
      </DialogTitle>
      <DialogDescription>
        This permanently deletes the saved scenario. There is no undo.
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button
        variant="outline"
        disabled={$deleteMutation.isPending}
        onclick={() => (confirmingDeleteFor = null)}
      >
        Cancel
      </Button>
      <Button
        variant="outline"
        class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
        disabled={$deleteMutation.isPending}
        onclick={() => {
          if (confirmingDeleteFor !== null) {
            $deleteMutation.mutate(confirmingDeleteFor.id)
          }
        }}
      >
        {$deleteMutation.isPending ? 'Deleting…' : 'Delete scenario'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>
