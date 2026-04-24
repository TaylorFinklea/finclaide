import { render, type RenderResult } from '@testing-library/svelte'
import type { Component } from 'svelte'

import { monthStore } from '$lib/stores/month.svelte'

import Harness from './render-harness.svelte'
import { resetMockPage } from './setup'

export interface RenderPageOptions<Props extends Record<string, unknown>> {
  pageProps?: Props
  selectedMonth?: string
}

export function renderPage<Props extends Record<string, unknown> = Record<string, never>>(
  Page: Component<Props>,
  opts: RenderPageOptions<Props> = {},
): RenderResult<typeof Harness> {
  const month = opts.selectedMonth ?? '2026-03'
  window.localStorage.setItem('finclaide:selected-month', month)
  monthStore.set(month)
  resetMockPage()
  return render(Harness, {
    props: {
      Page: Page as unknown as Component<Record<string, unknown>>,
      pageProps: (opts.pageProps ?? {}) as Record<string, unknown>,
    },
  })
}
