import { lazy, Suspense, useMemo } from 'react'

import { QueryClient, QueryClientProvider, useQuery } from '@tanstack/react-query'
import { BarChart3, FolderSync, LayoutGrid, ReceiptText, TriangleAlert } from 'lucide-react'
import { BrowserRouter, NavLink, Route, Routes } from 'react-router-dom'
import { Toaster } from 'sonner'

import { AppMonthProvider, useAppMonth } from '@/app/month-context'
import { Skeleton } from '@/components/ui/skeleton'
import { getStatus } from '@/lib/api'
import { formatMonthLabel } from '@/lib/format'
import { getBasePath } from '@/lib/runtime'
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
  const basename = getBasePath() || undefined

  return (
    <QueryClientProvider client={queryClient}>
      <AppMonthProvider>
        <BrowserRouter basename={basename}>
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
      <div className="mx-auto flex min-h-screen max-w-[1680px] flex-col lg:flex-row">
        <aside className="flex w-full shrink-0 flex-col border-b border-border/50 bg-card p-5 lg:w-[260px] lg:border-b-0 lg:border-r">
          <div className="flex items-center gap-2.5 px-1">
            <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15">
              <span className="text-sm font-semibold text-primary">F</span>
            </div>
            <span className="text-sm font-semibold tracking-tight text-foreground">Finclaide</span>
          </div>

          <nav className="mt-8 space-y-1">
            {navItems.map((item) => {
              const Icon = item.icon
              return (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === '/'}
                  className={({ isActive }) =>
                    cn(
                      'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150',
                      isActive
                        ? 'border-l-2 border-primary bg-primary/8 font-medium text-foreground'
                        : 'border-l-2 border-transparent text-muted-foreground hover:bg-accent/50 hover:text-foreground',
                    )
                  }
                >
                  <Icon className="h-4 w-4" />
                  {item.label}
                </NavLink>
              )
            })}
          </nav>

          <div className="mt-auto pt-8">
            <div className="rounded-lg bg-muted/50 px-3 py-3">
              <div className="text-label">Active Plan</div>
              <div className="mt-1.5 truncate font-mono text-xs text-foreground">{planLabel}</div>
            </div>
          </div>
        </aside>

        <main className="flex-1 p-6 lg:p-8">
          <header className="mb-8 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
            <div>
              <div className="text-label">Workspace</div>
              <div className="mt-1 text-2xl font-semibold tracking-tight text-foreground">
                {formatMonthLabel(month)}
              </div>
              <div className="mt-1.5 flex items-center gap-2 text-sm text-muted-foreground">
                {statusQuery.data?.busy ? (
                  <>
                    <TriangleAlert className="h-3.5 w-3.5 text-amber-400" />
                    <span>{statusQuery.data.current_operation ?? 'Operation in progress'}</span>
                  </>
                ) : (
                  <span>Ready</span>
                )}
              </div>
            </div>

            <div className="flex items-center gap-3">
              <label className="text-label" htmlFor="workspace-month">
                Month
              </label>
              <input
                id="workspace-month"
                className="rounded-lg border border-border/60 bg-muted/40 px-3 py-1.5 font-mono text-sm text-foreground outline-none transition-colors duration-150 focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
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
