import { useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'

import { useAppMonth } from '@/app/month-context'
import { DataTable } from '@/components/data-table'
import { StatusChip } from '@/components/status-chip'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { Input } from '@/components/ui/input'
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select'
import { Skeleton } from '@/components/ui/skeleton'
import { getSummary, type SummaryCategory } from '@/lib/api'
import { formatMoney } from '@/lib/format'

type CategoryRow = SummaryCategory & {
  group_name: string
}

const columns: ColumnDef<CategoryRow>[] = [
  {
    accessorKey: 'group_name',
    header: 'Group',
  },
  {
    accessorKey: 'category_name',
    header: 'Category',
  },
  {
    accessorKey: 'planned_milliunits',
    header: 'Planned',
    cell: ({ row }) => <span className="font-mono">{formatMoney(row.original.planned_milliunits)}</span>,
  },
  {
    accessorKey: 'actual_milliunits',
    header: 'Actual',
    cell: ({ row }) => <span className="font-mono">{formatMoney(row.original.actual_milliunits)}</span>,
  },
  {
    accessorKey: 'variance_milliunits',
    header: 'Variance',
    cell: ({ row }) => (
      <span className={row.original.variance_milliunits > 0 ? 'font-mono text-rose-200' : 'font-mono text-emerald-200'}>
        {formatMoney(row.original.variance_milliunits)}
      </span>
    ),
  },
  {
    accessorKey: 'current_balance_milliunits',
    header: 'Balance',
    cell: ({ row }) => <span className="font-mono">{formatMoney(row.original.current_balance_milliunits)}</span>,
  },
  {
    accessorKey: 'due_month',
    header: 'Due',
    cell: ({ row }) => row.original.due_month ?? '—',
  },
  {
    accessorKey: 'status',
    header: 'Status',
    cell: ({ row }) => <StatusChip status={row.original.status} />,
  },
]

export function CategoriesPage() {
  const { month } = useAppMonth()
  const [groupFilter, setGroupFilter] = useState('all')
  const [statusFilter, setStatusFilter] = useState('all')
  const [search, setSearch] = useState('')
  const [annualOnly, setAnnualOnly] = useState('all')
  const summaryQuery = useQuery({ queryKey: ['summary', month], queryFn: () => getSummary(month) })

  const rows = useMemo(
    () =>
      summaryQuery.data?.groups.flatMap((group) =>
        group.categories.map((category) => ({
          ...category,
          group_name: group.group_name,
        })),
      ) ?? [],
    [summaryQuery.data],
  )

  const filteredRows = useMemo(() => {
    return rows.filter((row) => {
      if (groupFilter !== 'all' && row.group_name !== groupFilter) {
        return false
      }
      if (statusFilter !== 'all' && row.status !== statusFilter) {
        return false
      }
      if (annualOnly === 'annual' && row.due_month === null) {
        return false
      }
      if (annualOnly === 'monthly' && row.due_month !== null) {
        return false
      }
      if (search) {
        const haystack = `${row.group_name} ${row.category_name}`.toLowerCase()
        if (!haystack.includes(search.toLowerCase())) {
          return false
        }
      }
      return true
    })
  }, [annualOnly, groupFilter, rows, search, statusFilter])

  if (summaryQuery.isLoading) {
    return <Skeleton className="h-[640px] rounded-xl" />
  }

  const groups = [...new Set(rows.map((row) => row.group_name))].sort()
  const statuses = [...new Set(rows.map((row) => row.status))].sort()

  return (
    <div className="space-y-6">
      <Card className="border-border/40 bg-card">
        <CardHeader className="space-y-4">
          <div>
            <CardTitle>Category Analysis</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              Filter categories by group, funding status, or annual cadence.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search group or category" />
            <Select value={groupFilter} onValueChange={setGroupFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All groups" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All groups</SelectItem>
                {groups.map((group) => (
                  <SelectItem key={group} value={group}>
                    {group}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={statusFilter} onValueChange={setStatusFilter}>
              <SelectTrigger>
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All statuses</SelectItem>
                {statuses.map((status) => (
                  <SelectItem key={status} value={status}>
                    {status.replace('_', ' ')}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={annualOnly} onValueChange={setAnnualOnly}>
              <SelectTrigger>
                <SelectValue placeholder="All cadence" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All cadence</SelectItem>
                <SelectItem value="annual">Annual only</SelectItem>
                <SelectItem value="monthly">Monthly only</SelectItem>
              </SelectContent>
            </Select>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-lg bg-muted/30 p-4">
              <div className="text-label-upper">Visible Categories</div>
              <div className="mt-2 font-mono text-2xl font-semibold">{filteredRows.length}</div>
            </div>
            <div className="rounded-lg bg-muted/30 p-4">
              <div className="text-label-upper">Visible Planned</div>
              <div className="mt-2 font-mono text-2xl font-semibold">
                {formatMoney(filteredRows.reduce((sum, row) => sum + row.planned_milliunits, 0))}
              </div>
            </div>
            <div className="rounded-lg bg-muted/30 p-4">
              <div className="text-label-upper">Visible Actual</div>
              <div className="mt-2 font-mono text-2xl font-semibold">
                {formatMoney(filteredRows.reduce((sum, row) => sum + row.actual_milliunits, 0))}
              </div>
            </div>
          </div>
          <DataTable data={filteredRows} columns={columns} emptyMessage="No categories match the current filters." />
        </CardContent>
      </Card>
    </div>
  )
}
