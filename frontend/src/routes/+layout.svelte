<script lang="ts">
  import '../app.css'

  import { browser } from '$app/environment'
  import { page } from '$app/stores'
  import { QueryClient, QueryClientProvider, createQuery } from '@tanstack/svelte-query'

  import Sidebar from '$components/quartz/sidebar.svelte'
  import AIRail from '$components/quartz/ai-rail.svelte'
  import Toaster from '$components/ui/toaster.svelte'
  import { getStatus } from '$lib/api'

  let { children } = $props()

  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        refetchOnWindowFocus: false,
        staleTime: 30_000,
      },
    },
  })

  const statusQuery = createQuery(
    {
      queryKey: ['status'],
      queryFn: getStatus,
      enabled: browser,
    },
    queryClient,
  )

  let planLabel = $derived.by(() => {
    const planId = $statusQuery.data?.plan_id
    if (!planId) return 'no plan'
    // The mock shows "v34" — use the import id when present, falling back to plan id.
    const importId = $statusQuery.data?.last_budget_import_id
    return importId ? `v${importId}` : planId
  })

  let aiAvailable = $state(false)
  $effect(() => {
    if (!browser) return
    // The AI rail backend returns 503 ai_unavailable when ANTHROPIC_API_KEY
    // is absent. A cheap POST with an empty messages list returns 400 if the
    // rail is wired, 503 if not — both let us flip the rail's visual state.
    fetch('/ui-api/ai/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json', 'X-Finclaide-UI': '1' },
      body: JSON.stringify({ messages: [{ role: 'user', content: 'ping' }] }),
    })
      .then((response) => {
        aiAvailable = response.status !== 503
        // Drain the body so the connection closes promptly.
        return response.body?.cancel?.()
      })
      .catch(() => {
        aiAvailable = false
      })
  })

  let contextLabel = $derived.by(() => {
    const pathname = $page.url.pathname
    if (pathname.startsWith('/plan')) return 'Plan mode · sandbox'
    if (pathname.startsWith('/operate')) return 'Operate mode'
    if (pathname.startsWith('/explore')) return 'Explore mode'
    return 'Review mode'
  })
</script>

<QueryClientProvider client={queryClient}>
  <div
    class="grid h-screen w-screen overflow-hidden"
    style="grid-template-columns: 240px minmax(0, 1fr) 360px"
  >
    <Sidebar status={$statusQuery.data} {planLabel} />

    <main class="overflow-y-auto bg-background">
      {@render children()}
    </main>

    <AIRail {contextLabel} available={aiAvailable} />
  </div>
  <Toaster />
</QueryClientProvider>
