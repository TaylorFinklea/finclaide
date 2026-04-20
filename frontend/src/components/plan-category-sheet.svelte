<script lang="ts" module>
  import type { BlockKey, PlanCategory } from '$lib/api'

  export type EditorSelection =
    | { mode: 'edit'; planId: number; category: PlanCategory }
    | { mode: 'create'; planId: number; block: BlockKey }
    | null
</script>

<script lang="ts">
  import { createMutation, useQueryClient } from '@tanstack/svelte-query'
  import { Dialog as DialogPrimitive } from 'bits-ui'
  import { Trash2 } from 'lucide-svelte'
  import { toast } from 'svelte-sonner'

  import DialogContent from '$components/ui/dialog-content.svelte'
  import DialogDescription from '$components/ui/dialog-description.svelte'
  import DialogFooter from '$components/ui/dialog-footer.svelte'
  import DialogHeader from '$components/ui/dialog-header.svelte'
  import DialogTitle from '$components/ui/dialog-title.svelte'
  import Button from '$components/ui/button.svelte'
  import Input from '$components/ui/input.svelte'
  import SheetContent from '$components/ui/sheet-content.svelte'
  import {
    BLOCK_LABELS,
    createPlanCategory,
    deletePlanCategory,
    getErrorMessage,
    updatePlanCategory,
    type UpdatePlanCategoryInput,
  } from '$lib/api'

  type Props = {
    selection: EditorSelection
    onClose: () => void
  }
  let { selection, onClose }: Props = $props()

  type FormState = {
    group_name: string
    category_name: string
    block: BlockKey
    planned_dollars: string
    annual_target_dollars: string
    due_month: string
    notes: string
    rename_enabled: boolean
  }

  function emptyForm(block: BlockKey): FormState {
    return {
      group_name: '',
      category_name: '',
      block,
      planned_dollars: '0.00',
      annual_target_dollars: '0.00',
      due_month: '',
      notes: '',
      rename_enabled: false,
    }
  }

  function fromCategory(category: PlanCategory): FormState {
    return {
      group_name: category.group_name,
      category_name: category.category_name,
      block: category.block,
      planned_dollars: (category.planned_milliunits / 1000).toFixed(2),
      annual_target_dollars: (category.annual_target_milliunits / 1000).toFixed(2),
      due_month: category.due_month === null ? '' : String(category.due_month),
      notes: category.notes ?? '',
      rename_enabled: false,
    }
  }

  function dollarsToMilliunits(text: string): number {
    const dollars = Number(text)
    if (!Number.isFinite(dollars) || dollars < 0) return NaN
    return Math.round(dollars * 1000)
  }

  let isEdit = $derived(selection?.mode === 'edit')
  let initialBlock = $derived(
    selection?.mode === 'create' ? selection.block : (selection?.mode === 'edit' ? selection.category.block : 'monthly'),
  )
  let form: FormState = $state(emptyForm('monthly'))
  let confirmingDelete = $state(false)
  let open = $derived(selection !== null)

  $effect(() => {
    if (!selection) return
    confirmingDelete = false
    form = selection.mode === 'edit' ? fromCategory(selection.category) : emptyForm(selection.block)
  })

  const queryClient = useQueryClient()

  async function invalidateAll() {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
    ])
  }

  const createMutationStore = createMutation({
    mutationFn: createPlanCategory,
    onSuccess: async () => {
      toast.success('Category created')
      await invalidateAll()
      onClose()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const updateMutationStore = createMutation({
    mutationFn: ({ id, payload }: { id: number; payload: UpdatePlanCategoryInput }) =>
      updatePlanCategory(id, payload),
    onSuccess: async () => {
      toast.success('Category saved')
      await invalidateAll()
      onClose()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const deleteMutationStore = createMutation({
    mutationFn: ({ id, planId }: { id: number; planId: number }) => deletePlanCategory(id, planId),
    onSuccess: async () => {
      toast.success('Category deleted')
      await invalidateAll()
      confirmingDelete = false
      onClose()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error))
      confirmingDelete = false
    },
  })

  let busy = $derived(
    $createMutationStore.isPending || $updateMutationStore.isPending || $deleteMutationStore.isPending,
  )

  function handleSubmit(event: Event) {
    event.preventDefault()
    if (!selection) return
    const planned = dollarsToMilliunits(form.planned_dollars)
    const annual = dollarsToMilliunits(form.annual_target_dollars)
    if (Number.isNaN(planned) || Number.isNaN(annual)) {
      toast.error('Amounts must be non-negative numbers.')
      return
    }
    const due = form.due_month.trim() === '' ? null : Number(form.due_month)
    if (due !== null && (!Number.isInteger(due) || due < 1 || due > 12)) {
      toast.error('Due month must be an integer 1-12.')
      return
    }
    const notes = form.notes.trim() === '' ? null : form.notes

    if (selection.mode === 'create') {
      $createMutationStore.mutate({
        plan_id: selection.planId,
        group_name: form.group_name.trim(),
        category_name: form.category_name.trim(),
        block: form.block,
        planned_milliunits: planned,
        annual_target_milliunits: annual,
        due_month: due,
        notes,
      })
      return
    }

    const payload: UpdatePlanCategoryInput = {
      plan_id: selection.planId,
      planned_milliunits: planned,
      annual_target_milliunits: annual,
      due_month: due,
      notes,
    }
    if (form.rename_enabled) {
      payload.rename = {
        group_name: form.group_name.trim(),
        category_name: form.category_name.trim(),
      }
    }
    $updateMutationStore.mutate({ id: selection.category.id, payload })
  }
</script>

<DialogPrimitive.Root bind:open={() => open, (next) => { if (!next && !busy) onClose() }}>
  <SheetContent class="border-border/40 bg-card text-card-foreground sm:max-w-lg" side="right">
    {#if selection}
      <form class="flex h-full flex-col" onsubmit={handleSubmit}>
        <DialogHeader>
          <DialogTitle>
            {isEdit ? 'Edit category' : `New ${BLOCK_LABELS[initialBlock]} category`}
          </DialogTitle>
          <DialogDescription>
            {isEdit
              ? 'Adjust the planned amount, annual target, due month, or notes. Group and category names are reconciliation-sensitive — toggle rename mode to change them.'
              : 'Create a new planned category in this plan. Group and category names must match YNAB exactly when you reconcile.'}
          </DialogDescription>
        </DialogHeader>

        <div class="mt-6 flex-1 space-y-4 overflow-y-auto pr-1">
          {#if isEdit}
            <label class="flex items-center gap-2 text-sm text-muted-foreground">
              <input type="checkbox" bind:checked={form.rename_enabled} />
              Allow renaming group / category (breaks reconciliation until YNAB matches)
            </label>
          {/if}

          <div class="grid gap-2">
            <label class="text-label" for="plan-category-group">Group</label>
            <Input
              id="plan-category-group"
              required
              disabled={isEdit && !form.rename_enabled}
              bind:value={form.group_name}
              placeholder="e.g. Bills"
            />
          </div>
          <div class="grid gap-2">
            <label class="text-label" for="plan-category-name">Category</label>
            <Input
              id="plan-category-name"
              required
              disabled={isEdit && !form.rename_enabled}
              bind:value={form.category_name}
              placeholder="e.g. Rent"
            />
          </div>
          <div class="grid gap-2">
            <label class="text-label" for="plan-category-block">Block</label>
            <select
              id="plan-category-block"
              class="flex h-9 w-full items-center justify-between rounded-md border border-input bg-transparent px-3 py-1 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
              bind:value={form.block}
              disabled={isEdit}
            >
              {#each Object.entries(BLOCK_LABELS) as [key, label] (key)}
                <option value={key}>{label}</option>
              {/each}
            </select>
          </div>
          <div class="grid gap-2 md:grid-cols-2">
            <div class="grid gap-2">
              <label class="text-label" for="plan-category-planned">Planned ($)</label>
              <Input
                id="plan-category-planned"
                required
                type="number"
                min="0"
                step="0.01"
                bind:value={form.planned_dollars}
              />
            </div>
            <div class="grid gap-2">
              <label class="text-label" for="plan-category-annual">Annual target ($)</label>
              <Input
                id="plan-category-annual"
                type="number"
                min="0"
                step="0.01"
                bind:value={form.annual_target_dollars}
              />
            </div>
          </div>
          <div class="grid gap-2">
            <label class="text-label" for="plan-category-due">Due month (1-12, optional)</label>
            <Input
              id="plan-category-due"
              type="number"
              min="1"
              max="12"
              bind:value={form.due_month}
            />
          </div>
          <div class="grid gap-2">
            <label class="text-label" for="plan-category-notes">Notes</label>
            <textarea
              id="plan-category-notes"
              rows="4"
              class="rounded-md border border-input bg-transparent px-3 py-1.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
              bind:value={form.notes}
            ></textarea>
          </div>
        </div>

        <DialogFooter class="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
          {#if isEdit}
            <Button
              type="button"
              variant="outline"
              class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
              disabled={busy}
              onclick={() => (confirmingDelete = true)}
            >
              <Trash2 class="h-4 w-4" />
              Delete
            </Button>
          {:else}
            <span></span>
          {/if}
          <div class="flex gap-2">
            <Button type="button" variant="outline" disabled={busy} onclick={onClose}>
              Cancel
            </Button>
            <Button type="submit" disabled={busy}>
              {isEdit ? 'Save' : 'Create'}
            </Button>
          </div>
        </DialogFooter>
      </form>
    {/if}
  </SheetContent>
</DialogPrimitive.Root>

<DialogPrimitive.Root bind:open={() => confirmingDelete, (next) => { if (!next) confirmingDelete = false }}>
  <DialogContent>
    <DialogHeader>
      <DialogTitle>Delete category?</DialogTitle>
      <DialogDescription>
        This removes the row from the active plan. Reconciliation will succeed only after the
        corresponding YNAB category is also removed or stops being referenced.
      </DialogDescription>
    </DialogHeader>
    <DialogFooter class="gap-2">
      <Button variant="outline" disabled={$deleteMutationStore.isPending} onclick={() => (confirmingDelete = false)}>
        Cancel
      </Button>
      <Button
        variant="outline"
        class="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
        disabled={$deleteMutationStore.isPending}
        onclick={() => {
          if (selection?.mode === 'edit') {
            $deleteMutationStore.mutate({ id: selection.category.id, planId: selection.planId })
          }
        }}
      >
        {$deleteMutationStore.isPending ? 'Deleting…' : 'Delete'}
      </Button>
    </DialogFooter>
  </DialogContent>
</DialogPrimitive.Root>
