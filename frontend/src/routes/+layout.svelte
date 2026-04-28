<script lang="ts">
  import '../app.css'

  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { QueryClient, QueryClientProvider, createQuery } from '@tanstack/svelte-query'
  import {
    AlertCircle,
    BarChart3,
    FolderSync,
    LayoutGrid,
    Pencil,
    ReceiptText,
    TriangleAlert,
  } from 'lucide-svelte'

  import FreshnessChip from '$components/freshness-chip.svelte'
  import Toaster from '$components/ui/toaster.svelte'
  import { getStatus, type StatusResponse } from '$lib/api'
  import { formatMonthLabel, formatRunAt } from '$lib/format'
  import { withBasePath } from '$lib/runtime'
  import { monthStore } from '$lib/stores/month.svelte'
  import { initThemeOnHydrate } from '$lib/theme/theme-service'
  import { cn } from '$lib/utils'

  let { children } = $props()

  $effect(() => {
    if (browser) initThemeOnHydrate()
  })

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
    { to: '/planning', label: 'Planning', icon: Pencil },
    { to: '/operations', label: 'Operations', icon: FolderSync },
  ] as const

  const statusQuery = createQuery(
    {
      queryKey: ['status'],
      queryFn: getStatus,
      enabled: browser,
    },
    queryClient,
  )

  let planLabel = $derived(($statusQuery.data?.plan_id) ?? 'Plan not configured')

  function isActive(href: string, pathname: string): boolean {
    if (href === '/') return pathname === '/' || pathname === ''
    return pathname === href || pathname.startsWith(`${href}/`)
  }

  function scheduledBanner(status: StatusResponse | undefined) {
    if (!status?.scheduled_refresh.enabled) return null
    const lastStatus = status.scheduled_refresh.last_status
    if (lastStatus !== 'failed' && lastStatus !== 'skipped') return null
    return {
      tone:
        lastStatus === 'failed'
          ? 'border-rose-500/30 bg-rose-500/[0.08] text-rose-100'
          : 'border-amber-500/30 bg-amber-500/[0.08] text-amber-100',
      headline:
        lastStatus === 'failed'
          ? `Scheduled refresh failed ${formatRunAt(status.scheduled_refresh.last_finished_at)}`
          : `Scheduled refresh skipped ${formatRunAt(status.scheduled_refresh.last_finished_at)}`,
      detail:
        status.scheduled_refresh.last_error ??
        (lastStatus === 'skipped'
          ? 'A manual operation was running when the scheduled refresh fired. Next attempt will retry.'
          : 'Open Operations to retry or read the run detail for the full payload.'),
    }
  }
</script>

<QueryClientProvider client={queryClient}>
  <div class="min-h-screen">
    <div class="mx-auto flex min-h-screen max-w-[1680px] flex-col lg:flex-row">
      <aside class="flex w-full shrink-0 flex-col border-b border-border/50 bg-card p-5 lg:w-[260px] lg:border-b-0 lg:border-r">
        <div class="flex items-center gap-2.5 px-1">
          <div class="flex h-8 w-8 items-center justify-center rounded-lg bg-primary/15">
            <span class="text-sm font-semibold text-primary">F</span>
          </div>
          <span class="text-sm font-semibold tracking-tight text-foreground">Finclaide</span>
        </div>

        <nav class="mt-8 space-y-1">
          {#each navItems as item (item.to)}
            {@const active = isActive(item.to, $page.url.pathname)}
            {@const Icon = item.icon}
            <a
              href={withBasePath(item.to)}
              class={cn(
                'flex items-center gap-3 rounded-lg px-3 py-2 text-sm transition-colors duration-150',
                active
                  ? 'border-l-2 border-primary bg-primary/8 font-medium text-foreground'
                  : 'border-l-2 border-transparent text-muted-foreground hover:bg-accent/50 hover:text-foreground',
              )}
            >
              <Icon class="h-4 w-4" />
              {item.label}
            </a>
          {/each}
        </nav>

        <div class="mt-auto pt-8">
          <div class="rounded-lg bg-muted/50 px-3 py-3">
            <div class="text-label">Active Plan</div>
            <div class="mt-1.5 truncate font-mono text-xs text-foreground">{planLabel}</div>
          </div>
        </div>
      </aside>

      <main class="flex-1 p-6 lg:p-8">
        <header class="mb-8 flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div>
            <div class="text-label">Workspace</div>
            <div class="mt-1 text-2xl font-semibold tracking-tight text-foreground">
              {formatMonthLabel(monthStore.value)}
            </div>
            <div class="mt-1.5 flex items-center gap-2 text-sm text-muted-foreground">
              {#if $statusQuery.data?.busy}
                <TriangleAlert class="h-3.5 w-3.5 text-amber-400" />
                <span>{$statusQuery.data.current_operation ?? 'Operation in progress'}</span>
              {:else}
                <span>Ready</span>
              {/if}
            </div>
          </div>

          <div class="flex flex-col items-end gap-3">
            {#if $statusQuery.data}
              <div class="flex flex-wrap items-center justify-end gap-x-4 gap-y-2">
                <FreshnessChip label="Plan" freshness={$statusQuery.data.plan_freshness} />
                <FreshnessChip label="YNAB" freshness={$statusQuery.data.actuals_freshness} />
              </div>
            {/if}
            <div class="flex items-center gap-3">
              <label class="text-label" for="workspace-month">Month</label>
              <input
                id="workspace-month"
                class="rounded-lg border border-border/60 bg-muted/40 px-3 py-1.5 font-mono text-sm text-foreground outline-none transition-colors duration-150 focus:border-primary/60 focus:ring-1 focus:ring-primary/30"
                type="month"
                value={monthStore.value}
                onchange={(event) => monthStore.set((event.currentTarget as HTMLInputElement).value)}
              />
            </div>
          </div>
        </header>

        {#if $statusQuery.data}
          {@const banner = scheduledBanner($statusQuery.data)}
          {#if banner}
            <div
              class={cn('mb-6 flex flex-col gap-3 rounded-xl p-4 ring-1 ring-inset md:flex-row md:items-center md:justify-between', banner.tone)}
              role="status"
              aria-live="polite"
            >
              <div class="flex items-start gap-3">
                <AlertCircle class="mt-0.5 h-4 w-4" />
                <div>
                  <div class="text-sm font-medium">{banner.headline}</div>
                  <div class="mt-1 text-xs opacity-80">{banner.detail}</div>
                </div>
              </div>
              <a
                href={withBasePath('/operations')}
                class="self-start rounded-md border border-current/30 px-3 py-1.5 text-xs font-medium hover:bg-current/10 md:self-center"
              >
                Open Operations
              </a>
            </div>
          {/if}
        {/if}

        {@render children()}
      </main>
    </div>
  </div>
  <Toaster />
</QueryClientProvider>
