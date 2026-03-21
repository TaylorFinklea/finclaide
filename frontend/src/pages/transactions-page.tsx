import { useMemo, useState } from 'react'

import { useQuery } from '@tanstack/react-query'
import type { ColumnDef } from '@tanstack/react-table'

import { useAppMonth } from '@/app/month-context'
import { DataTable } from '@/components/data-table'
import { Button } from '@/components/ui/button'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
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
  SheetHeader,
  SheetTitle,
} from '@/components/ui/sheet'
import { Skeleton } from '@/components/ui/skeleton'
import { getSummary, getTransactions, type TransactionRow } from '@/lib/api'
import { formatDay, formatMoney } from '@/lib/format'
import { cn } from '@/lib/utils'

const PAGE_SIZE = 25

export function TransactionsPage() {
  const { month } = useAppMonth()
  const [group, setGroup] = useState('all')
  const [category, setCategory] = useState('all')
  const [search, setSearch] = useState('')
  const [since, setSince] = useState(`${month}-01`)
  const [until, setUntil] = useState('')
  const [offset, setOffset] = useState(0)
  const [selectedTransaction, setSelectedTransaction] = useState<TransactionRow | null>(null)

  const summaryQuery = useQuery({ queryKey: ['summary', month], queryFn: () => getSummary(month) })
  const transactionsQuery = useQuery({
    queryKey: ['transactions', month, group, category, search, since, until, offset],
    queryFn: () =>
      getTransactions({
        since,
        until,
        group: group === 'all' ? undefined : group,
        category: category === 'all' ? undefined : category,
        q: search || undefined,
        limit: PAGE_SIZE,
        offset,
      }),
  })

  const categoryOptions = useMemo(() => {
    const categories = summaryQuery.data?.groups.flatMap((groupItem) =>
      groupItem.categories.map((item) => ({
        group_name: groupItem.group_name,
        category_name: item.category_name,
      })),
    ) ?? []
    if (group === 'all') {
      return categories
    }
    return categories.filter((item) => item.group_name === group)
  }, [group, summaryQuery.data])

  const groups = summaryQuery.data?.groups.map((groupItem) => groupItem.group_name) ?? []

  const columns: ColumnDef<TransactionRow>[] = [
    {
      accessorKey: 'date',
      header: 'Date',
      cell: ({ row }) => <span className="font-mono text-sm text-muted-foreground">{formatDay(row.original.date)}</span>,
    },
    {
      accessorKey: 'payee_name',
      header: 'Payee',
      cell: ({ row }) => (
        <div>
          <div className="font-medium text-foreground">{row.original.payee_name ?? 'No payee'}</div>
          {row.original.memo ? <div className="mt-1 text-xs text-muted-foreground">{row.original.memo}</div> : null}
        </div>
      ),
    },
    {
      accessorKey: 'group_name',
      header: 'Group',
    },
    {
      accessorKey: 'category_name',
      header: 'Category',
    },
    {
      accessorKey: 'amount_milliunits',
      header: 'Amount',
      cell: ({ row }) => (
        <span className={row.original.amount_milliunits < 0 ? 'font-mono text-rose-200' : 'font-mono text-emerald-200'}>
          {formatMoney(row.original.amount_milliunits)}
        </span>
      ),
    },
  ]

  if (summaryQuery.isLoading || transactionsQuery.isLoading) {
    return <Skeleton className="h-[640px] rounded-xl" />
  }

  const page = transactionsQuery.data
  if (!page) {
    return null
  }

  return (
    <div className="space-y-6">
      <Card className="border-border/40 bg-card">
        <CardHeader className="space-y-4">
          <div>
            <CardTitle>Transactions</CardTitle>
            <p className="mt-2 text-sm text-muted-foreground">
              Search payees and memos, then drill into individual rows.
            </p>
          </div>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-5">
            <Input value={search} onChange={(event) => setSearch(event.target.value)} placeholder="Search payee or memo" />
            <Select
              value={group}
              onValueChange={(value) => {
                setGroup(value)
                setCategory('all')
                setOffset(0)
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="All groups" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All groups</SelectItem>
                {groups.map((groupItem) => (
                  <SelectItem key={groupItem} value={groupItem}>
                    {groupItem}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={category}
              onValueChange={(value) => {
                setCategory(value)
                setOffset(0)
              }}
            >
              <SelectTrigger>
                <SelectValue placeholder="All categories" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">All categories</SelectItem>
                {categoryOptions.map((option) => (
                  <SelectItem key={`${option.group_name}-${option.category_name}`} value={option.category_name}>
                    {option.category_name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Input type="date" value={since} onChange={(event) => setSince(event.target.value)} />
            <Input type="date" value={until} onChange={(event) => setUntil(event.target.value)} />
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between text-sm text-muted-foreground">
            <span>
              Showing {page.transactions.length} of {page.total_count} transactions
            </span>
            <div className="flex gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={offset === 0}
                onClick={() => setOffset((current) => Math.max(current - PAGE_SIZE, 0))}
              >
                Previous
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={offset + PAGE_SIZE >= page.total_count}
                onClick={() => setOffset((current) => current + PAGE_SIZE)}
              >
                Next
              </Button>
            </div>
          </div>
          <DataTable
            data={page.transactions}
            columns={columns}
            emptyMessage="No transactions match the current filters."
            onRowClick={setSelectedTransaction}
          />
        </CardContent>
      </Card>

      <Sheet open={selectedTransaction !== null} onOpenChange={(open) => !open && setSelectedTransaction(null)}>
        <SheetContent className="border-border/40 bg-card text-card-foreground sm:max-w-lg">
          {selectedTransaction ? (
            <>
              <SheetHeader>
                <SheetTitle>{selectedTransaction.payee_name ?? 'No payee name'}</SheetTitle>
                <SheetDescription>
                  {selectedTransaction.group_name ?? 'No group'} / {selectedTransaction.category_name ?? 'No category'}
                </SheetDescription>
              </SheetHeader>
              <div className="mt-8 space-y-4">
                <DetailRow label="Date" value={formatDay(selectedTransaction.date)} />
                <DetailRow label="Amount" value={formatMoney(selectedTransaction.amount_milliunits)} />
                <DetailRow label="Memo" value={selectedTransaction.memo ?? '—'} />
                <DetailRow label="Transaction ID" value={selectedTransaction.id} mono />
              </div>
            </>
          ) : null}
        </SheetContent>
      </Sheet>
    </div>
  )
}

function DetailRow({
  label,
  value,
  mono = false,
}: {
  label: string
  value: string
  mono?: boolean
}) {
  return (
    <div className="rounded-lg bg-muted/30 p-4">
      <div className="text-label">{label}</div>
      <div className={cn('mt-1.5 text-sm text-foreground', mono && 'break-all font-mono')}>
        {value}
      </div>
    </div>
  )
}
