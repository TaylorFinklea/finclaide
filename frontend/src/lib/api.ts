import { z } from 'zod'

const NullableString = z.string().nullable()

const LatestRunSchema = z.object({
  status: z.string(),
  started_at: NullableString.optional(),
  finished_at: NullableString.optional(),
  details: z.record(z.string(), z.any()),
})

export const StatusSchema = z.object({
  plan_id: NullableString,
  budget_sheet: z.string(),
  busy: z.boolean(),
  current_operation: NullableString,
  last_budget_import_at: NullableString,
  last_budget_import_id: z.number().nullable(),
  last_ynab_sync_at: NullableString,
  last_server_knowledge: z.number().nullable(),
  last_reconcile_at: NullableString,
  last_reconcile_status: NullableString,
  latest_runs: z.record(z.string(), LatestRunSchema).optional(),
})

export const SummaryCategorySchema = z.object({
  category_name: z.string(),
  planned_milliunits: z.number(),
  actual_milliunits: z.number(),
  variance_milliunits: z.number(),
  current_balance_milliunits: z.number(),
  due_month: z.number().nullable(),
  status: z.string(),
})

export const SummaryGroupSchema = z.object({
  group_name: z.string(),
  categories: z.array(SummaryCategorySchema),
  planned_milliunits: z.number(),
  actual_milliunits: z.number(),
  variance_milliunits: z.number(),
})

export const TransactionSchema = z.object({
  id: z.string(),
  date: z.string(),
  payee_name: NullableString,
  memo: NullableString,
  amount_milliunits: z.number(),
  group_name: NullableString,
  category_name: NullableString,
})

export const SummarySchema = z.object({
  as_of: z.string(),
  plan_year: z.number().nullable(),
  month: z.string(),
  groups: z.array(SummaryGroupSchema),
  recent_transactions: z.array(TransactionSchema),
  mismatches: z.array(
    z.object({
      group_name: z.string(),
      category_name: z.string(),
      reason: z.string(),
    }),
  ),
  sync_status: StatusSchema,
})

export const TransactionsPageSchema = z.object({
  transactions: z.array(TransactionSchema),
  total_count: z.number(),
  limit: z.number(),
  offset: z.number(),
})

export type StatusResponse = z.infer<typeof StatusSchema>
export type SummaryResponse = z.infer<typeof SummarySchema>
export type SummaryGroup = z.infer<typeof SummaryGroupSchema>
export type SummaryCategory = z.infer<typeof SummaryCategorySchema>
export type TransactionRow = z.infer<typeof TransactionSchema>
export type TransactionsPageResponse = z.infer<typeof TransactionsPageSchema>

export class ApiError extends Error {
  status: number
  body: unknown

  constructor(message: string, status: number, body: unknown) {
    super(message)
    this.name = 'ApiError'
    this.status = status
    this.body = body
  }
}

async function requestJson<T>(
  path: string,
  schema: z.ZodType<T>,
  init?: RequestInit,
): Promise<T> {
  const response = await fetch(path, {
    headers: {
      Accept: 'application/json',
      ...(init?.headers ?? {}),
    },
    ...init,
  })
  const body = await response.json().catch(() => null)
  if (!response.ok) {
    const message =
      typeof body === 'object' &&
      body !== null &&
      'error' in body &&
      typeof body.error === 'string'
        ? body.error
        : `Request failed with status ${response.status}`
    throw new ApiError(message, response.status, body)
  }
  return schema.parse(body)
}

export async function getStatus() {
  return requestJson('/ui-api/status', StatusSchema)
}

export async function getSummary(month: string) {
  const search = new URLSearchParams({ month })
  return requestJson(`/ui-api/summary?${search.toString()}`, SummarySchema)
}

export type TransactionsParams = {
  since?: string
  until?: string
  group?: string
  category?: string
  q?: string
  limit: number
  offset: number
}

export async function getTransactions(params: TransactionsParams) {
  const search = new URLSearchParams()
  Object.entries(params).forEach(([key, value]) => {
    if (value !== undefined && value !== '') {
      search.set(key, String(value))
    }
  })
  return requestJson(`/ui-api/transactions?${search.toString()}`, TransactionsPageSchema)
}

const MutationResultSchema = z.record(z.string(), z.any())

async function postUiOperation<T extends Record<string, unknown>>(
  path: string,
  body?: T,
): Promise<Record<string, unknown>> {
  return requestJson(path, MutationResultSchema, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-Finclaide-UI': '1',
    },
    body: JSON.stringify(body ?? {}),
  })
}

export function importBudget() {
  return postUiOperation('/ui-api/operations/import-budget')
}

export function syncYnab() {
  return postUiOperation('/ui-api/operations/sync-ynab')
}

export function reconcile() {
  return postUiOperation('/ui-api/operations/reconcile')
}

export function refreshAll(month: string) {
  return postUiOperation('/ui-api/operations/refresh-all', { month })
}

export function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Unexpected error'
}
