import { createContext, useContext, useEffect, useMemo, useState, type ReactNode } from 'react'

import { currentMonth } from '@/lib/format'

type MonthContextValue = {
  month: string
  setMonth: (month: string) => void
}

const MonthContext = createContext<MonthContextValue | null>(null)

const STORAGE_KEY = 'finclaide:selected-month'

export function AppMonthProvider({ children }: { children: ReactNode }) {
  const [month, setMonth] = useState(() => {
    try {
      return window.localStorage?.getItem(STORAGE_KEY) ?? currentMonth()
    } catch {
      return currentMonth()
    }
  })

  useEffect(() => {
    try {
      window.localStorage?.setItem(STORAGE_KEY, month)
    } catch {
      // Local storage is optional for the dashboard shell.
    }
  }, [month])

  const value = useMemo(
    () => ({
      month,
      setMonth,
    }),
    [month],
  )

  return <MonthContext.Provider value={value}>{children}</MonthContext.Provider>
}

export function useAppMonth() {
  const value = useContext(MonthContext)
  if (!value) {
    throw new Error('useAppMonth must be used within AppMonthProvider')
  }
  return value
}
