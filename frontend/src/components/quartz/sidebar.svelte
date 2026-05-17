<script lang="ts">
  import { page } from '$app/stores'
  import {
    BookOpen,
    Compass,
    GitBranch,
    LayoutGrid,
    LineChart,
    ListChecks,
    Plug,
    Receipt,
    Search,
    Settings,
    Sparkles,
    Tags,
    Workflow,
  } from 'lucide-svelte'

  import { withBasePath } from '$lib/runtime'
  import type { StatusResponse } from '$lib/api'

  type NavItem = {
    to: string
    label: string
    icon: any
    badge?: string | number
  }

  type Section = {
    label: string
    items: NavItem[]
  }

  let { status, planLabel = 'v1' }: { status: StatusResponse | undefined; planLabel?: string } = $props()

  const sections: Section[] = [
    {
      label: 'Workflow',
      items: [
        { to: '/review', label: 'Review', icon: BookOpen },
        { to: '/plan', label: 'Plan', icon: Workflow },
        { to: '/operate', label: 'Operate', icon: ListChecks },
      ],
    },
    {
      label: 'Explore',
      items: [
        { to: '/explore/categories', label: 'Categories', icon: Tags },
        { to: '/explore/transactions', label: 'Transactions', icon: Receipt },
        { to: '/explore/forecast', label: 'Forecast', icon: LineChart },
        { to: '/explore/scenarios', label: 'Scenarios', icon: GitBranch },
        { to: '/explore/insights', label: 'Insights', icon: Sparkles },
      ],
    },
    {
      label: 'Admin',
      items: [
        { to: '/admin/settings', label: 'Settings', icon: Settings },
        { to: '/admin/integrations', label: 'Integrations', icon: Plug },
      ],
    },
  ]

  function isActive(href: string, pathname: string): boolean {
    return pathname === href || pathname.startsWith(`${href}/`)
  }

  function formatStaleness(hours: number | null | undefined): string {
    if (hours == null) return '—'
    if (hours < 1) return '<1h'
    if (hours < 48) return `${Math.round(hours)}h`
    return `${Math.round(hours / 24)}d`
  }

  type ConnDot = { tone: 'g' | 'a' | 'r'; label: string; value: string }

  function hoursSince(iso: string | null | undefined): number | null {
    if (!iso) return null
    const t = Date.parse(iso)
    if (Number.isNaN(t)) return null
    return (Date.now() - t) / 3_600_000
  }

  let connections = $derived.by<ConnDot[]>(() => {
    if (!status) return []
    const planHrs = status.plan_freshness?.hours_stale ?? hoursSince(status.last_budget_import_at)
    const ynabHrs = status.actuals_freshness?.hours_stale ?? hoursSince(status.last_ynab_sync_at)
    const reconHrs = hoursSince(status.last_reconcile_at)
    return [
      {
        tone: (planHrs ?? 0) > 168 ? 'a' : 'g',
        label: 'Plan import',
        value: formatStaleness(planHrs),
      },
      {
        tone: (ynabHrs ?? 0) > 24 ? 'a' : 'g',
        label: 'YNAB sync',
        value: formatStaleness(ynabHrs),
      },
      {
        tone: status.last_reconcile_status === 'failed' ? 'r' : 'g',
        label: 'Reconcile',
        value: formatStaleness(reconHrs),
      },
    ]
  })
</script>

<aside class="flex h-screen w-[240px] shrink-0 flex-col gap-4 border-r border-border bg-background p-3">
  <div class="flex items-center gap-2.5 px-2 py-1">
    <div
      class="grid h-[26px] w-[26px] place-items-center rounded-md bg-gradient-to-br from-[#4E46E5] to-[#6E64FF] text-[13px] font-semibold tracking-tight text-white"
      aria-hidden="true"
    >
      F
    </div>
    <div class="text-sm font-semibold tracking-tight">Finclaide</div>
    <div class="ml-auto rounded border border-border bg-card px-2 py-0.5 text-[11px] text-muted-foreground">
      {planLabel}
    </div>
  </div>

  <button
    type="button"
    class="flex items-center gap-2 rounded-lg border border-border bg-card px-2.5 py-1.5 text-xs text-muted-foreground transition-colors hover:border-foreground/20 hover:text-foreground"
    aria-label="Jump to anything"
  >
    <Search class="h-3.5 w-3.5" />
    <span class="flex-1 text-left">Jump to anything…</span>
    <span class="rounded border border-border bg-background px-1.5 py-0.5 text-[10px] text-muted-foreground/70">⌘K</span>
  </button>

  <nav class="space-y-3 overflow-y-auto">
    {#each sections as section (section.label)}
      <div>
        <div
          class="px-2 pb-1 text-[10px] font-medium uppercase tracking-[0.1em] text-muted-foreground/70"
        >
          {section.label}
        </div>
        <div class="space-y-0.5">
          {#each section.items as item (item.to)}
            {@const active = isActive(item.to, $page.url.pathname)}
            {@const Icon = item.icon}
            <a
              href={withBasePath(item.to)}
              data-active={active ? 'true' : undefined}
              class="flex items-center gap-2.5 rounded-md px-2 py-1.5 text-sm text-muted-foreground transition-colors data-[active]:bg-card data-[active]:font-medium data-[active]:text-foreground data-[active]:shadow-[0_1px_0_rgba(0,0,0,0.02)] hover:bg-secondary hover:text-foreground"
            >
              <Icon class="h-3.5 w-3.5" />
              <span class="flex-1">{item.label}</span>
              {#if item.badge}
                <span class="rounded border border-border bg-card px-1.5 py-0 text-[10px] text-muted-foreground">
                  {item.badge}
                </span>
              {/if}
            </a>
          {/each}
        </div>
      </div>
    {/each}
  </nav>

  <div class="mt-auto rounded-xl border border-border bg-card p-3">
    <div class="text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
      Connections
    </div>
    <div class="mt-1 space-y-1">
      {#each connections as conn (conn.label)}
        <div class="flex items-center justify-between text-xs">
          <span class="flex items-center gap-1.5">
            <span
              class="inline-block h-2 w-2 rounded-full"
              style={conn.tone === 'g'
                ? 'background:#2F8A57'
                : conn.tone === 'a'
                  ? 'background:#C68A21'
                  : 'background:#D14444'}
            ></span>
            {conn.label}
          </span>
          <span class="text-muted-foreground">{conn.value}</span>
        </div>
      {/each}
      {#if connections.length === 0}
        <div class="text-xs text-muted-foreground">Loading…</div>
      {/if}
    </div>
  </div>
</aside>
