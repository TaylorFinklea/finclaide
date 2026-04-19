import { type FormEvent, useEffect, useState } from 'react'

import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Trash2 } from 'lucide-react'
import { toast } from 'sonner'

import { Button } from '@/components/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui/dialog'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetFooter,
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import {
  BLOCK_LABELS,
  type BlockKey,
  type PlanCategory,
  createPlanCategory,
  deletePlanCategory,
  getErrorMessage,
  updatePlanCategory,
} from '@/lib/api'

export type EditorSelection =
  | { mode: 'edit'; planId: number; category: PlanCategory }
  | { mode: 'create'; planId: number; block: BlockKey }
  | null

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

function dollarsToMilliunits(dollarsText: string): number {
  const dollars = Number(dollarsText)
  if (!Number.isFinite(dollars) || dollars < 0) {
    return NaN
  }
  return Math.round(dollars * 1000)
}

export function PlanCategorySheet({
  selection,
  onClose,
}: {
  selection: EditorSelection
  onClose: () => void
}) {
  const isEdit = selection?.mode === 'edit'
  const initialBlock = selection?.mode === 'create' ? selection.block : selection?.category.block ?? 'monthly'
  const [form, setForm] = useState<FormState>(() =>
    selection?.mode === 'edit' ? fromCategory(selection.category) : emptyForm(initialBlock),
  )
  const [confirmingDelete, setConfirmingDelete] = useState(false)
  const queryClient = useQueryClient()

  useEffect(() => {
    if (!selection) return
    setConfirmingDelete(false)
    setForm(
      selection.mode === 'edit'
        ? fromCategory(selection.category)
        : emptyForm(selection.block),
    )
  }, [selection])

  const invalidateAll = async () => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: ['plan'] }),
      queryClient.invalidateQueries({ queryKey: ['summary'] }),
    ])
  }

  const createMutation = useMutation({
    mutationFn: createPlanCategory,
    onSuccess: async () => {
      toast.success('Category created')
      await invalidateAll()
      onClose()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: Parameters<typeof updatePlanCategory>[1] }) =>
      updatePlanCategory(id, payload),
    onSuccess: async () => {
      toast.success('Category saved')
      await invalidateAll()
      onClose()
    },
    onError: (error) => toast.error(getErrorMessage(error)),
  })

  const deleteMutation = useMutation({
    mutationFn: ({ id, planId }: { id: number; planId: number }) => deletePlanCategory(id, planId),
    onSuccess: async () => {
      toast.success('Category deleted')
      await invalidateAll()
      setConfirmingDelete(false)
      onClose()
    },
    onError: (error) => {
      toast.error(getErrorMessage(error))
      setConfirmingDelete(false)
    },
  })

  const busy = createMutation.isPending || updateMutation.isPending || deleteMutation.isPending

  const handleSubmit = (event: FormEvent<HTMLFormElement>) => {
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
      createMutation.mutate({
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

    const payload: Parameters<typeof updatePlanCategory>[1] = {
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
    updateMutation.mutate({ id: selection.category.id, payload })
  }

  const open = selection !== null

  return (
    <>
      <Sheet open={open} onOpenChange={(next) => !next && !busy && onClose()}>
        <SheetContent className="border-border/40 bg-card text-card-foreground sm:max-w-lg">
          {selection ? (
            <form className="flex h-full flex-col" onSubmit={handleSubmit}>
              <SheetHeader>
                <SheetTitle>
                  {isEdit ? 'Edit category' : `New ${BLOCK_LABELS[selection.block]} category`}
                </SheetTitle>
                <SheetDescription>
                  {isEdit
                    ? 'Adjust the planned amount, annual target, due month, or notes. Group and category names are reconciliation-sensitive — toggle rename mode to change them.'
                    : 'Create a new planned category in this plan. Group and category names must match YNAB exactly when you reconcile.'}
                </SheetDescription>
              </SheetHeader>

              <div className="mt-6 flex-1 space-y-4 overflow-y-auto pr-1">
                {isEdit ? (
                  <label className="flex items-center gap-2 text-sm text-muted-foreground">
                    <input
                      type="checkbox"
                      checked={form.rename_enabled}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, rename_enabled: event.target.checked }))
                      }
                    />
                    Allow renaming group / category (breaks reconciliation until YNAB matches)
                  </label>
                ) : null}

                <div className="grid gap-2">
                  <label className="text-label" htmlFor="plan-category-group">Group</label>
                  <Input
                    id="plan-category-group"
                    required
                    disabled={isEdit && !form.rename_enabled}
                    value={form.group_name}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, group_name: event.target.value }))
                    }
                    placeholder="e.g. Bills"
                  />
                </div>
                <div className="grid gap-2">
                  <label className="text-label" htmlFor="plan-category-name">Category</label>
                  <Input
                    id="plan-category-name"
                    required
                    disabled={isEdit && !form.rename_enabled}
                    value={form.category_name}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, category_name: event.target.value }))
                    }
                    placeholder="e.g. Rent"
                  />
                </div>
                <div className="grid gap-2">
                  <label className="text-label" htmlFor="plan-category-block">Block</label>
                  <Select
                    value={form.block}
                    onValueChange={(value) =>
                      setForm((current) => ({ ...current, block: value as BlockKey }))
                    }
                    disabled={isEdit}
                  >
                    <SelectTrigger id="plan-category-block">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {(Object.keys(BLOCK_LABELS) as BlockKey[]).map((key) => (
                        <SelectItem key={key} value={key}>
                          {BLOCK_LABELS[key]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
                <div className="grid gap-2 md:grid-cols-2">
                  <div className="grid gap-2">
                    <label className="text-label" htmlFor="plan-category-planned">Planned ($)</label>
                    <Input
                      id="plan-category-planned"
                      required
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.planned_dollars}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, planned_dollars: event.target.value }))
                      }
                    />
                  </div>
                  <div className="grid gap-2">
                    <label className="text-label" htmlFor="plan-category-annual">Annual target ($)</label>
                    <Input
                      id="plan-category-annual"
                      type="number"
                      min="0"
                      step="0.01"
                      value={form.annual_target_dollars}
                      onChange={(event) =>
                        setForm((current) => ({ ...current, annual_target_dollars: event.target.value }))
                      }
                    />
                  </div>
                </div>
                <div className="grid gap-2">
                  <label className="text-label" htmlFor="plan-category-due">Due month (1-12, optional)</label>
                  <Input
                    id="plan-category-due"
                    type="number"
                    min="1"
                    max="12"
                    value={form.due_month}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, due_month: event.target.value }))
                    }
                  />
                </div>
                <div className="grid gap-2">
                  <label className="text-label" htmlFor="plan-category-notes">Notes</label>
                  <textarea
                    id="plan-category-notes"
                    rows={4}
                    className="rounded-md border border-input bg-transparent px-3 py-1.5 text-sm shadow-sm focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring"
                    value={form.notes}
                    onChange={(event) =>
                      setForm((current) => ({ ...current, notes: event.target.value }))
                    }
                  />
                </div>
              </div>

              <SheetFooter className="mt-6 flex flex-col-reverse gap-2 sm:flex-row sm:justify-between">
                {isEdit ? (
                  <Button
                    type="button"
                    variant="outline"
                    className="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
                    disabled={busy}
                    onClick={() => setConfirmingDelete(true)}
                  >
                    <Trash2 className="h-4 w-4" />
                    Delete
                  </Button>
                ) : <span />}
                <div className="flex gap-2">
                  <Button type="button" variant="outline" disabled={busy} onClick={onClose}>
                    Cancel
                  </Button>
                  <Button type="submit" disabled={busy}>
                    {isEdit ? 'Save' : 'Create'}
                  </Button>
                </div>
              </SheetFooter>
            </form>
          ) : null}
        </SheetContent>
      </Sheet>

      <Dialog open={confirmingDelete} onOpenChange={(next) => !next && setConfirmingDelete(false)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Delete category?</DialogTitle>
            <DialogDescription>
              This removes the row from the active plan. Reconciliation will succeed only after the
              corresponding YNAB category is also removed or stops being referenced.
            </DialogDescription>
          </DialogHeader>
          <DialogFooter className="gap-2">
            <Button variant="outline" disabled={deleteMutation.isPending} onClick={() => setConfirmingDelete(false)}>
              Cancel
            </Button>
            <Button
              variant="outline"
              className="border-rose-500/40 text-rose-100 hover:bg-rose-500/10"
              disabled={deleteMutation.isPending}
              onClick={() => {
                if (selection?.mode === 'edit') {
                  deleteMutation.mutate({ id: selection.category.id, planId: selection.planId })
                }
              }}
            >
              {deleteMutation.isPending ? 'Deleting…' : 'Delete'}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  )
}
