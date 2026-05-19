/**
 * UI chrome state: which side panels are collapsed.
 *
 * Both flags persist to localStorage so the operator's layout choice
 * survives reload. SSR-safe — reads/writes are gated on `window`.
 */

const SIDEBAR_KEY = 'finclaide.chrome.sidebar-collapsed'
const RAIL_KEY = 'finclaide.chrome.ai-rail-collapsed'

function readBool(key: string): boolean {
  if (typeof window === 'undefined') return false
  try {
    return window.localStorage.getItem(key) === '1'
  } catch {
    return false
  }
}

function writeBool(key: string, value: boolean): void {
  if (typeof window === 'undefined') return
  try {
    window.localStorage.setItem(key, value ? '1' : '0')
  } catch {
    // Storage blocked — runtime state still reflects the choice for the
    // current session; we just can't remember next time.
  }
}

class ChromeStore {
  #sidebarCollapsed = $state(false)
  #aiRailCollapsed = $state(false)
  #hydrated = false

  hydrate(): void {
    if (this.#hydrated) return
    this.#sidebarCollapsed = readBool(SIDEBAR_KEY)
    this.#aiRailCollapsed = readBool(RAIL_KEY)
    this.#hydrated = true
  }

  get sidebarCollapsed(): boolean {
    return this.#sidebarCollapsed
  }

  get aiRailCollapsed(): boolean {
    return this.#aiRailCollapsed
  }

  setSidebarCollapsed(next: boolean): void {
    this.#sidebarCollapsed = next
    writeBool(SIDEBAR_KEY, next)
  }

  setAIRailCollapsed(next: boolean): void {
    this.#aiRailCollapsed = next
    writeBool(RAIL_KEY, next)
  }

  toggleSidebar(): void {
    this.setSidebarCollapsed(!this.#sidebarCollapsed)
  }

  toggleAIRail(): void {
    this.setAIRailCollapsed(!this.#aiRailCollapsed)
  }
}

export const chromeStore = new ChromeStore()
