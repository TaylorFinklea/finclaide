import type { ReactElement } from 'react'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { render } from '@testing-library/react'
import { BrowserRouter } from 'react-router-dom'

import { AppMonthProvider } from '@/app/month-context'

export function renderWithProviders(ui: ReactElement) {
  const queryClient = new QueryClient({
    defaultOptions: {
      queries: {
        retry: false,
      },
      mutations: {
        retry: false,
      },
    },
  })
  window.localStorage.setItem('finclaide:selected-month', '2026-03')

  return render(
    <QueryClientProvider client={queryClient}>
      <AppMonthProvider>
        <BrowserRouter>{ui}</BrowserRouter>
      </AppMonthProvider>
    </QueryClientProvider>,
  )
}
