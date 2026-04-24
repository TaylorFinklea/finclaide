import '@testing-library/jest-dom/vitest'
import { readable, writable, type Writable } from 'svelte/store'
import { vi } from 'vitest'

type PageState = {
  url: URL
  params: Record<string, string>
  route: { id: string | null }
  status: number
  error: Error | null
  data: Record<string, unknown>
  form: unknown
}

const defaultPageState: PageState = {
  url: new URL('http://localhost/'),
  params: {},
  route: { id: null },
  status: 200,
  error: null,
  data: {},
  form: null,
}

const pageStore: Writable<PageState> = writable({ ...defaultPageState })

export function setMockPage(patch: Partial<PageState>): void {
  pageStore.update((current) => ({ ...current, ...patch }))
}

export function resetMockPage(): void {
  pageStore.set({ ...defaultPageState })
}

vi.mock('$app/environment', () => ({
  browser: true,
  dev: true,
  building: false,
  version: 'test',
}))

vi.mock('$app/stores', () => ({
  page: { subscribe: pageStore.subscribe },
  navigating: readable(null),
  updated: readable(false),
}))

vi.mock('svelte-sonner', () => ({
  toast: {
    success: vi.fn(),
    error: vi.fn(),
    info: vi.fn(),
    warning: vi.fn(),
    message: vi.fn(),
    loading: vi.fn(),
    dismiss: vi.fn(),
  },
  Toaster: { $$typeof: Symbol.for('svelte.test.stub') },
}))

vi.mock('$app/navigation', () => ({
  goto: vi.fn().mockResolvedValue(undefined),
  invalidate: vi.fn().mockResolvedValue(undefined),
  invalidateAll: vi.fn().mockResolvedValue(undefined),
  beforeNavigate: vi.fn(),
  afterNavigate: vi.fn(),
  onNavigate: vi.fn(),
  preloadData: vi.fn().mockResolvedValue(undefined),
  preloadCode: vi.fn().mockResolvedValue(undefined),
}))

if (typeof Element !== 'undefined') {
  if (!Element.prototype.hasPointerCapture) {
    Element.prototype.hasPointerCapture = function () {
      return false
    }
  }
  if (!Element.prototype.setPointerCapture) {
    Element.prototype.setPointerCapture = function () {}
  }
  if (!Element.prototype.releasePointerCapture) {
    Element.prototype.releasePointerCapture = function () {}
  }
  if (!Element.prototype.scrollIntoView) {
    Element.prototype.scrollIntoView = function () {}
  }
}

const localStorageStore = new Map<string, string>()

Object.defineProperty(window, 'localStorage', {
  value: {
    getItem: (key: string) => localStorageStore.get(key) ?? null,
    setItem: (key: string, value: string) => {
      localStorageStore.set(key, value)
    },
    removeItem: (key: string) => {
      localStorageStore.delete(key)
    },
    clear: () => {
      localStorageStore.clear()
    },
  },
  configurable: true,
})
