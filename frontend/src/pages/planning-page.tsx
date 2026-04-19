import { useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'
import { AlertTriangle, Plus } from 'lucide-react'

import { DataTable } from '@/components/data-table'
import {
  type EditorSelection,
  PlanCategorySheet,
} from '@/components/plan-category-sheet'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Skeleton } from '@/components/ui/skeleton'
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs'
import { BLOCK_LABELS, type BlockKey, type PlanCategory, getActivePlan, getStatus } from '@/lib/api'
import { formatMoney } from '@/lib/format'

const BLOCK_ORDER: BlockKey[] = ['monthly', 'annual', 'one_time', 'stipends', 'savings']

export function PlanningPage() {
  const planQuery = useQuery({ queryKey: ['plan', 'active'], queryFn: () => getActivePlan() })
  const statusQuery = useQuery({ queryKey: ['status'], queryFn: getStatus })
  const [activeBlock, setActiveBlock] = useState<BlockKey>('monthly')
  const [selection, setSelection] = useState<EditorSelection>(null)

  if (planQuery.isLoading) {
    return <Skeleton className="h-[640px] rounded-2xl" />
  }
  if (planQuery.isError) {
    return (
      <Card className="border-border/40 bg-card">
        <CardHeader>
          <CardTitle>Planning is unavailable</CardTitle>
        </CardHeader>
        <CardContent className="text-sm text-muted-foreground">
          {planQuery.error instanceof Error ? planQuery.error.message : 'Could not load the active plan.'}
          <p className="mt-3">
            If you have not imported a budget yet, run an import from the Operations page first.
          </p>
        </CardContent>
      </Card>
    )
  }
  const data = planQuery.data
  if (!data) return null

  const importBusy =
    statusQuery.data?.busy === true && statusQuery.data?.current_operation === 'budget_import'

  return (
    <div className="space-y-6">
      {importBusy ? (
        <Card className="border-amber-500/30 bg-amber-500/[0.06]" role="status" aria-live="polite">
          <CardHeader className="space-y-1">
            <CardTitle className="flex items-center gap-2 text-amber-100">
              <AlertTriangle className="h-4 w-4" />
              Budget import in progress
            </CardTitle>
            <p className="text-sm text-amber-100/80">
              Saved edits may be overwritten when the import completes. Wait or coordinate before saving.
            </p>
          </CardHeader>
        </Card>
      ) : null}

      <Card className="border-border/40 bg-card">
        <CardHeader className="space-y-3">
          <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
            <div>
              <CardTitle>Planning — {data.plan.name}</CardTitle>
              <p className="mt-2 text-sm text-muted-foreground">
                Active plan for {data.plan.plan_year}. Click any row to edit; use Add row to create a new
                category in the current block.
              </p>
            </div>
            <div className="text-right text-sm text-muted-foreground">
              <div>
                Plan total {formatMoney(Number(data.totals.grand_total_milliunits ?? 0))}
              </div>
              <div className="text-xs">Source: {data.plan.source}</div>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <Tabs value={activeBlock} onValueChange={(value) => setActiveBlock(value as BlockKey)}>
            <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
              <TabsList>
                {BLOCK_ORDER.map((key) => (
                  <TabsTrigger key={key} value={key}>
                    {BLOCK_LABELS[key]}
                  </TabsTrigger>
                ))}
              </TabsList>
              <Button
                size="sm"
                onClick={() =>
                  setSelection({ mode: 'create', planId: data.plan.id, block: activeBlock })
                }
              >
                <Plus className="h-4 w-4" />
                Add row
              </Button>
            </div>

            {BLOCK_ORDER.map((key) => (
              <TabsContent key={key} value={key} className="mt-4">
                <BlockPanel
                  block={key}
                  rows={data.blocks[key]}
                  total={Number(data.totals[`${key}_milliunits`] ?? 0)}
                  onRowClick={(category) =>
                    setSelection({ mode: 'edit', planId: data.plan.id, category })
                  }
                />
              </TabsContent>
            ))}
          </Tabs>
        </CardContent>
      </Card>

      <PlanCategorySheet selection={selection} onClose={() => setSelection(null)} />
    </div>
  )
}

function BlockPanel({
  block,
  rows,
  total,
  onRowClick,
}: {
  block: BlockKey
  rows: PlanCategory[]
  total: number
  onRowClick: (category: PlanCategory) => void
}) {
  const columns = useMemo<ColumnDef<PlanCategory>[]>(
    () => [
      {
        accessorKey: 'group_name',
        header: 'Group',
        cell: ({ row }) => <span className="font-medium text-foreground">{row.original.group_name}</span>,
      },
      {
        accessorKey: 'category_name',
        header: 'Category',
      },
      {
        accessorKey: 'planned_milliunits',
        header: 'Planned',
        cell: ({ row }) => (
          <span className="font-mono text-sm text-foreground">
            {formatMoney(row.original.planned_milliunits)}
          </span>
        ),
      },
      {
        accessorKey: 'annual_target_milliunits',
        header: 'Annual target',
        cell: ({ row }) => (
          <span className="font-mono text-sm text-muted-foreground">
            {row.original.annual_target_milliunits === 0 && row.original.block === 'monthly'
              ? '—'
              : formatMoney(row.original.annual_target_milliunits)}
          </span>
        ),
      },
      {
        accessorKey: 'due_month',
        header: 'Due',
        cell: ({ row }) =>
          row.original.due_month === null ? (
            <span className="text-muted-foreground">—</span>
          ) : (
            <span className="font-mono text-sm text-foreground">
              {String(row.original.due_month).padStart(2, '0')}
            </span>
          ),
      },
      {
        accessorKey: 'notes',
        header: 'Notes',
        cell: ({ row }) => (
          <span className="text-sm text-muted-foreground">
            {row.original.notes ?? '—'}
          </span>
        ),
      },
    ],
    [],
  )

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between text-sm text-muted-foreground">
        <span>
          {rows.length} {rows.length === 1 ? 'category' : 'categories'} in {BLOCK_LABELS[block]}
        </span>
        <span className="font-mono text-foreground">
          Block total {formatMoney(total)}
        </span>
      </div>
      <DataTable
        data={rows}
        columns={columns}
        onRowClick={onRowClick}
        emptyMessage={`No ${BLOCK_LABELS[block]} categories yet. Click Add row to create one.`}
      />
    </div>
  )
}
