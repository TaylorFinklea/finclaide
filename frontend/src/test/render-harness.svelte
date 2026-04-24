<script lang="ts">
  import { QueryClient, QueryClientProvider } from '@tanstack/svelte-query'
  import type { Component } from 'svelte'

  interface Props {
    Page: Component<Record<string, unknown>>
    pageProps?: Record<string, unknown>
  }

  let { Page, pageProps = {} }: Props = $props()

  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false },
      mutations: { retry: false },
    },
  })
</script>

<QueryClientProvider {client}>
  <Page {...pageProps} />
</QueryClientProvider>
