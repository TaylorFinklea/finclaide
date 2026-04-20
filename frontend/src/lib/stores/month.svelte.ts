import { browser } from '$app/environment'

import { currentMonth } from '$lib/format'

const STORAGE_KEY = 'finclaide:selected-month'

function readInitial(): string {
  if (!browser) return currentMonth()
  try {
    return window.localStorage?.getItem(STORAGE_KEY) ?? currentMonth()
  } catch {
    return currentMonth()
  }
}

class MonthStore {
  value = $state<string>(readInitial())

  set(next: string): void {
    this.value = next
    if (!browser) return
    try {
      window.localStorage?.setItem(STORAGE_KEY, next)
    } catch {
      // localStorage is optional.
    }
  }
}

export const monthStore = new MonthStore()
