import { z } from 'zod'

import { withBasePath } from '@/lib/runtime'

const NullableString = z.string().nullable()
const NullableNumber = z.number().nullable()

const LatestRunSchema = z.object({
  status: z.string(),
  started_at: NullableString.optional(),
  finished_at: NullableString.optional(),
  details: z.record(z.string(), z.any()),
})

const FreshnessSchema = z.object({
  status: z.string(),
  last_updated_at: NullableString,
  hours_stale: NullableNumber,
})

const PlanProvenanceSchema = z.object({
  source_type: z.string(),
  workbook_path: z.string(),
  workbook_url: NullableString.optional(),
  sheet_name: z.string(),
  import_id: z.number().nullable(),
  imported_at: NullableString,
  last_result: NullableString,
})

const ActualsProvenanceSchema = z.object({
  source_type: z.string(),
  plan_id: NullableString,
  last_synced_at: NullableString,
  server_knowledge: NullableNumber,
  last_result: NullableString,
})

const ScheduledRefreshSchema = z.object({
  enabled: z.boolean(),
  interval_minutes: z.number().nullable(),
  next_run_at: NullableString,
  last_started_at: NullableString,
  last_finished_at: NullableString,
  last_status: NullableString,
  last_error: NullableString,
})

export const RunEntrySchema = z.object({
  id: z.number(),
  source: z.string(),
  status: z.string(),
  started_at: NullableString,
  finished_at: NullableString,
  details: z.record(z.string(), z.any()),
})

const RunsSchema = z.object({
  runs: z.array(RunEntrySchema),
})

const ReviewItemSchema = z.object({
  kind: z.string(),
  signal_class: z.string(),
  severity: z.string(),
  title: z.string(),
  why_it_matters: z.string(),
  recommended_action: NullableString,
  group_name: NullableString,
  category_name: NullableString,
  evidence: z.record(z.string(), z.any()),
})

const WeeklyReviewSchema = z.object({
  month: z.string(),
  generated_at: z.string(),
  overall_status: z.string(),
  headline: z.string(),
  blockers: z.array(ReviewItemSchema),
  changes: z.array(ReviewItemSchema),
  overages: z.array(ReviewItemSchema),
  anomalies: z.array(ReviewItemSchema),
  recommendations: z.array(ReviewItemSchema),
  supporting_metrics: z.record(z.string(), z.any()),
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
  plan_freshness: FreshnessSchema,
  actuals_freshness: FreshnessSchema,
  plan_provenance: PlanProvenanceSchema,
  actuals_provenance: ActualsProvenanceSchema,
  scheduled_refresh: ScheduledRefreshSchema,
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

export const OverageWatchCategorySchema = z.object({
  group_name: z.string(),
  category_name: z.string(),
  block: z.string(),
  watch_level: z.string(),
  watch_kind: z.string(),
  planned_milliunits: z.number(),
  suggested_monthly_milliunits: z.number(),
  average_spend_milliunits: z.number(),
  active_average_spend_milliunits: z.number(),
  max_spend_milliunits: z.number(),
  peak_month: z.string(),
  active_months: z.number(),
  analysis_month_count: z.number(),
  over_months: z.number(),
  shortfall_milliunits: z.number(),
  current_balance_milliunits: z.number(),
})

export const OverageWatchSchema = z.object({
  analysis_start_month: NullableString,
  analysis_end_month: NullableString,
  analysis_month_count: z.number(),
  categories: z.array(OverageWatchCategorySchema),
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
  overage_watch: OverageWatchSchema,
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
export type OverageWatch = z.infer<typeof OverageWatchSchema>
export type OverageWatchCategory = z.infer<typeof OverageWatchCategorySchema>
export type TransactionRow = z.infer<typeof TransactionSchema>
export type TransactionsPageResponse = z.infer<typeof TransactionsPageSchema>
export type RunEntry = z.infer<typeof RunEntrySchema>
export type ReviewItem = z.infer<typeof ReviewItemSchema>
export type WeeklyReviewResponse = z.infer<typeof WeeklyReviewSchema>

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
  return requestJson(withBasePath('/ui-api/status'), StatusSchema)
}

export async function getSummary(month: string) {
  const search = new URLSearchParams({ month })
  return requestJson(withBasePath(`/ui-api/summary?${search.toString()}`), SummarySchema)
}

export async function getWeeklyReview(month: string) {
  const search = new URLSearchParams({ month })
  return requestJson(withBasePath(`/ui-api/review/weekly?${search.toString()}`), WeeklyReviewSchema)
}

export async function getRuns(limit = 20, source?: string) {
  const search = new URLSearchParams({ limit: String(limit) })
  if (source) {
    search.set('source', source)
  }
  return requestJson(withBasePath(`/ui-api/runs?${search.toString()}`), RunsSchema)
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
  return requestJson(withBasePath(`/ui-api/transactions?${search.toString()}`), TransactionsPageSchema)
}

const MutationResultSchema = z.record(z.string(), z.any())

async function postUiOperation<T extends Record<string, unknown>>(
  path: string,
  body?: T,
): Promise<Record<string, unknown>> {
  return requestJson(withBasePath(path), MutationResultSchema, {
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
    if (
      error.body &&
      typeof error.body === 'object' &&
      'error_detail' in error.body &&
      typeof error.body.error_detail === 'object' &&
      error.body.error_detail !== null &&
      'message' in error.body.error_detail &&
      typeof error.body.error_detail.message === 'string'
    ) {
      return error.body.error_detail.message
    }
    return error.message
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'Unexpected error'
}
