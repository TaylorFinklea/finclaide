import { lazy, Suspense, useMemo } from 'react'

import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { BarChart3, FolderSync, LayoutGrid, ReceiptText, TriangleAlert } from 'lucide-react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'

import { AppMonthProvider, useAppMonth } from '@/app/month-context'
import { Skeleton } from '@/components/ui/skeleton'
import { getStatus } from '@/lib/api'
import { formatMonthLabel } from '@/lib/format'
import { cn } from '@/lib/utils'

const OverviewPage = lazy(async () => import('@/pages/overview-page').then((module) => ({ default: module.OverviewPage })))
const CategoriesPage = lazy(async () => import('@/pages/categories-page').then((module) => ({ default: module.CategoriesPage })))
const TransactionsPage = lazy(async () => import('@/pages/transactions-page').then((module) => ({ default: module.TransactionsPage })))
const OperationsPage = lazy(async () => import('@/pages/operations-page').then((module) => ({ default: module.OperationsPage })))

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      refetchOnWindowFocus: false,
      staleTime: 30_000,
    },
  },
})

const navItems = [
  { to: '/', label: 'Overview', icon: LayoutGrid },
  { to: '/categories', label: 'Categories', icon: BarChart3 },
  { to: '/transactions', label: 'Transactions', icon: ReceiptText },
  { to: '/operations', label: 'Operations', icon: FolderSync },
] as const

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppMonthProvider>
        <BrowserRouter>
          <AppShell />
          <Toaster richColors theme="dark" />
        </BrowserRouter>
      </AppMonthProvider>
    </QueryClientProvider>
  )
}

function AppShell() {
  const { month, setMonth } = useAppMonth()
  const statusQuery = useQuery({ queryKey: ['status'], queryFn: getStatus })
  const planLabel = useMemo(() => statusQuery.data?.plan_id ?? 'Plan not configured', [statusQuery.data])

  return (
    <div className="min-h-screen">
      <div className="mx-auto flex min-h-screen max-w-[1680px] flex-col gap-6 px-4 py-4 lg:flex-row lg:px-6">
        <aside className="w-full shrink-0 rounded-[28px] border border-border/70 bg-card/80 p-4 shadow-2xl shadow-black/20 backdrop-blur-xl lg:w-[280px]">
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/10 p-4">
            <div className="font-mono text-xs uppercase tracking-[0.24em] text-emerald-100">Finclaide</div>
            <h1 className="mt-3 text-2xl font-semibold tracking-tight text-foreground">Financial Command</h1>
            <p className="mt-2 text-sm text-muted-foreground">
              Replace passive dashboards with actionable budget visibility.
            </p>
          </div>

          <nav className="mt-6 space-y-2">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-2xl px-3 py-3 text-sm transition',
                      isActive
                        ? 'bg-primary text-primary-foreground shadow-lg shadow-emerald-500/10'
                        : 'text-muted-foreground hover:bg-accent hover:text-accent-foreground',
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              )
            })}
          </nav>

          <div className="mt-6 rounded-2xl border border-border/60 bg-background/20 p-4">
            <div className="text-xs uppercase tracking-[0.18em] text-muted-foreground">Active Plan</div>
            <div className="mt-2 break-all font-mono text-sm text-foreground">{planLabel}</div>
          </div>
        </aside>

        <main className="flex-1 rounded-[28px] border border-border/70 bg-card/75 p-4 shadow-2xl shadow-black/20 backdrop-blur-xl sm:p-6">
          <header className="mb-6 flex flex-col gap-4 border-b border-border/60 pb-6 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="text-xs uppercase tracking-[0.24em] text-muted-foreground">Workspace Month</div>
              <div className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
                {formatMonthLabel(month)}
              </div>
              <div className="mt-2 flex items-center gap-2 text-sm text-muted-foreground">
                {statusQuery.data?.busy ? (
                  <>
                    <TriangleAlert className="h-4 w-4 text-amber-300" />
                    {statusQuery.data.current_operation ?? 'Operation in progress'}
                  </>
                ) : (
                  'Ready for import, sync, and analysis'
                )}
              </div>
            </div>

            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <label className="text-xs uppercase tracking-[0.18em] text-muted-foreground" htmlFor="workspace-month">
                Month
              </label>
              <input
                id="workspace-month"
                className="rounded-xl border border-border/70 bg-background/30 px-3 py-2 font-mono text-sm text-foreground outline-none ring-0 transition focus:border-primary"
                type="month"
                value={month}
                onChange={(event) => setMonth(event.target.value)}
              />
            </div>
          </header>

          <Suspense fallback={<Skeleton className="h-[640px] rounded-2xl" />}>
            <Routes>
              <Route path="/" element={<OverviewPage />} />
              <Route path="/categories" element={<CategoriesPage />} />
              <Route path="/transactions" element={<TransactionsPage />} />
              <Route path="/operations" element={<OperationsPage />} />
            </Routes>
          </Suspense>
        </main>
      </div>
    </div>
  )
}
