# Phase 2.5d — Publish Plan (xlsx + Sheets write-back)

## Context

Phase 2.5 (Native Planning Surface) shipped through Slices 2.5a, 2.5b
(versioning + rollback), and 2.5c (what-if scenarios; Slices 1–4 +
3.5 bug fixes, all on `main` as of 2026-04-30). The operator can now
edit the plan, branch sandboxes, save scenarios, project changes,
and commit — all without opening Google Sheets. SQLite is the
canonical plan store; the workbook is read-only at import time.

The last unmet exit criterion in Phase 2.5 is:

> **Sheet exports remain readable by non-app users (household
> members, accountant) and round-trip back into the importer if
> needed.**

This phase delivers two surfaces that close that gap:

- **xlsx download** — generates a fresh `.xlsx` from the active plan
  matching the importer's exact column layout. Lets the operator
  hand a snapshot to an accountant, keep an offline copy, or
  re-import to roll back. No Google deps; works for users who
  don't use Google Sheets at all.
- **Google Sheets publish** — writes the active plan as a *new
  tab* in the configured workbook (file id from
  `FINCLAIDE_GOOGLE_SHEETS_FILE_ID`). Tab name encodes the publish
  date: `2026 Budget — published 2026-04-30 14:32`. The canonical
  `2026 Budget` tab the importer reads is never touched, so the
  round-trip stays clean.

User decisions locked via AskUserQuestion (2026-04-30):

- **Both surfaces**, not xlsx-only.
- **New tab in same workbook**, not overwrite or new file.
- **Manual trigger only** — no auto-publish on commit, no
  scheduled publish.

## Slicing — 2 commits, one PR

- **Slice 5a** (xlsx) — `PlanExporter` service, `/api/budget/export`
  + `/ui-api/budget/export` endpoints, Operations page
  "Export .xlsx" button + browser download. ~250 LOC + ~10 pytest
  cases. Standalone — closes the accountant-handoff use case.
- **Slice 5b** (Sheets write-back) — `google-api-python-client` +
  `google-auth-httplib2` deps, expand service-account scope to
  include `drive.file`, `SheetsPublisher` service that uploads
  the workbook bytes as a new tab via the Sheets `batchUpdate`
  API, `/api/budget/publish` + `/ui-api/budget/publish`
  endpoints, Operations page "Publish to Sheets" button.
  ~250 LOC + ~6 pytest cases (Drive client mocked).

Each slice is independently shippable. Slice 5b builds on 5a's
exporter — they share the openpyxl workbook construction.

## Locked design decisions

- **Mirror the importer's column layout exactly.** The exporter
  must produce a workbook the existing `BudgetImporter.import_budget`
  re-reads losslessly. Coordinates per
  `src/finclaide/budget_sheet.py:57-60`:

  | Block | Name col | Amount cols | Header detection |
  |---|---|---|---|
  | Monthly | A | B | empty B = group |
  | Annual / One-time | D | E (annual), F (due/monthly), G (monthly fallback) | E+F+G all empty = group |
  | Stipends | I | J | empty J = group |
  | Savings | L | M | empty M = group |

  Row 2 onward is data. Totals at row 53 (legacy fallback in
  importer at lines 369–397) — keep that convention. Sheet name
  matches `config.budget_sheet_name` (default `"2026 Budget"`).

- **Preserve `formula_text` if present, otherwise write static
  values.** Each `plan_categories` row may carry a `formula_text`
  field captured by the importer (e.g. `"=B2+B3"`). On export,
  if `formula_text` is set, write it as a formula; otherwise
  write the planned dollar value with currency format.

- **Output file naming** — exporter returns the workbook bytes plus
  a suggested filename: `2026 Budget — exported {YYYY-MM-DD HHMM}.xlsx`.
  Browser download honors the suggestion via
  `Content-Disposition: attachment; filename=...`.

- **Sheets target = new tab in same workbook.** Tab name template:
  `2026 Budget — published {YYYY-MM-DD HHMM}` (truncated to 100
  chars per Google's tab name limit). Append `(2)`, `(3)`, etc. on
  same-minute collisions.

- **Service account scope.** Existing `drive.readonly` is
  insufficient for write. Replace with `drive.file`
  (`https://www.googleapis.com/auth/drive.file` — write to files
  the service account already has access to). Setup note: the user
  must re-share the workbook with the service account email and
  grant Editor permissions; this is a one-time operator action,
  documented in the spec's setup section.

- **Run history** — both exports record runs in the existing
  `runs` table via `database.record_run()`:
  - xlsx: `source='budget_export'`,
    `details={"file_size_bytes": N, "row_count": N}`. The xlsx
    bytes themselves are NOT persisted in the DB; the operator
    must download immediately.
  - Sheets: `source='budget_publish'`,
    `details={"sheets_file_id": "...", "tab_id": N,
    "tab_name": "...", "tab_url": "https://docs.google.com/..."}`.

- **Operation lock** — `operation_lock.guard("budget_export")` and
  `operation_lock.guard("budget_publish")`. Prevents concurrent
  exports and serializes against import/sync/reconcile so the user
  can't publish a half-imported plan.

- **Two-step xlsx download UX** — POST to kick off, GET to
  download. Two endpoints:
  - `POST /api/budget/export` → `{run_id, file_size_bytes}` after
    rendering the workbook into a temp file under
    `database.dir / exports/`.
  - `GET /api/budget/export/<run_id>/download` → streams the
    bytes back. Same-origin guard for `/ui-api/...` mirror.

  Alternative considered: single POST that returns the bytes
  inline. Rejected because it confuses the run-history pattern —
  every other operation records a run first then surfaces results.

- **Sheets publish is one-step.** `POST /api/budget/publish` →
  blocks until Drive write completes → returns
  `{run_id, tab_name, tab_url}`. Drive API call typically <2s for
  a 5-block workbook.

- **Frontend = Operations page only in v1.** Two new buttons in
  the action grid: `Export .xlsx` and `Publish to Sheets`. Grid
  goes from 2×2 to 3×2. No /planning header export button in v1
  (deferred). Run history surfaces both new sources just like
  import/sync/reconcile.

- **MCP tools deferred to follow-up.** Slice 5a + 5b cover UI +
  REST. Adding `export_plan_to_xlsx` + `publish_plan_to_sheets`
  to `mcp_server.py` is a tiny follow-up that doesn't need to
  block the slice.

## Schema delta

**None.** Both surfaces read existing `plan_categories` and write
to `runs` via the existing `record_run()` helper.

---

## Slice 5a — xlsx download

### Service layer (NEW: `src/finclaide/plan_exporter.py`)

```python
class PlanExporter:
    """Renders the active plan as an .xlsx matching the importer's layout."""

    def __init__(self, plan_service: PlanService):
        self._plan_service = plan_service

    def export_active_plan(
        self, *, sheet_name: str | None = None,
    ) -> tuple[bytes, str]:
        """Returns (xlsx_bytes, suggested_filename).

        Layout matches budget_sheet.py:57-60 exactly so the importer
        round-trips. Group headers carry only the group name in the
        name column; category rows have name + amount(s). Totals
        row at row 53 with SUM formula spanning the block range."""
```

Implementation:
- Fetch active plan via `plan_service.get_active_plan()` (returns
  `{plan, blocks: {monthly, annual, one_time, stipends, savings},
  totals}`).
- Use `openpyxl.Workbook()`. Single sheet, name = `sheet_name or
  config.budget_sheet_name`.
- Walk each block in column-block order:
  - Monthly → A:B from row 2
  - Yearly (annual + one_time, sorted with annual first per
    importer's grouping) → D:G from row 2
  - Stipends → I:J from row 2
  - Savings → L:M from row 2
- For each block:
  - Group rows in `(group_name, category_name)` order.
  - When `group_name` changes, emit a **group header row**: name
    only; amount cells empty.
  - Emit category rows: name + planned amount (and for yearly,
    annual_target + due_month).
  - Track row index per block.
  - At row 53 (per importer's legacy fallback at
    `budget_sheet.py:369-397`), write a totals SUM formula:
    e.g. `=SUM(B2:B52)` for Monthly, etc.
- Write currency format `$#,##0.00` on amount cells.
- If `formula_text` is set on a category row, write that formula
  string (e.g. `=B2+B3`); otherwise write the dollar value.
- Convert milliunits → dollars: `value_milliunits / 1000`.
- Save workbook to `BytesIO`, return `(buffer.getvalue(),
  suggested_filename)`.

Suggested filename: `f"{plan.name} — exported {now:%Y-%m-%d %H%M}.xlsx"`.

### API layer (`src/finclaide/api.py`)

Add two endpoints near the existing `import_budget` (line 50):

```python
@api.post("/budget/export")
@require_bearer_token
def export_budget():
    container = _container()
    with container.operation_lock.guard("budget_export"):
        result = run_budget_export(container)
    return jsonify(result), 201
```

```python
@api.get("/budget/export/<int:run_id>/download")
@require_bearer_token
def download_budget_export(run_id: int):
    path = _container().export_storage.path_for(run_id)
    if not path.exists():
        return jsonify({"error": "Export not found"}), 404
    return send_file(
        path, as_attachment=True,
        download_name=path.name,
        mimetype=(
            "application/vnd.openxmlformats-officedocument."
            "spreadsheetml.sheet"
        ),
    )
```

### Operations layer (`src/finclaide/operations.py`)

```python
def run_budget_export(container) -> dict[str, Any]:
    """Renders the xlsx, persists to a temp file, records a run."""
```

Behavior:
- Call `container.plan_exporter.export_active_plan()` → bytes +
  filename.
- Persist bytes to
  `container.export_storage.write(run_id_placeholder, bytes,
  filename)` — see storage helper below.
- Record run: `database.record_run(source='budget_export',
  status='success', details={"file_size_bytes": len(bytes),
  "row_count": ..., "filename": ...},
  started_at=..., finished_at=...)`.
- Return `{run_id, file_size_bytes, filename, download_url:
  f"/api/budget/export/{run_id}/download"}`.

### Storage helper (NEW: `src/finclaide/export_storage.py`)

```python
class ExportStorage:
    """Stores rendered xlsx files keyed by run_id under
    {database.dir}/exports/{run_id}.xlsx. Pruned on write
    when count > 20 (keep the 20 most recent)."""

    def __init__(self, base_dir: Path): ...
    def path_for(self, run_id: int) -> Path: ...
    def write(self, run_id: int, content: bytes, filename: str) -> Path: ...
    def prune(self, keep: int = 20) -> None: ...
```

Wired into `ServiceContainer` (`src/finclaide/services.py`) alongside
the other services. Files are not persisted across container restarts
in v1 — that's fine; if the operator wants a permanent copy, they
download it to their machine.

### UI API mirror (`src/finclaide/ui_api.py`)

Same two routes under `/ui-api/budget/...` with `require_ui_write_request`
(POST) and `require_same_origin` (GET).

### Frontend (`frontend/src/lib/api.ts`)

```ts
export const BudgetExportResponseSchema = z.object({
  run_id: z.number(),
  file_size_bytes: z.number(),
  filename: z.string(),
  download_url: z.string(),
})

export async function exportBudget() {
  return requestJson(
    withBasePath('/ui-api/budget/export'),
    BudgetExportResponseSchema,
    {
      method: 'POST',
      headers: { 'X-Finclaide-UI': '1' },
    },
  )
}
```

### Frontend — Operations page (`frontend/src/routes/operations/+page.svelte`)

Add a fifth button "Export .xlsx" to the action grid. On click:

```ts
const exportMutation = createMutation({
  mutationFn: () => exportBudget(),
  onSuccess: (resp) => {
    invalidate(['runs', 'status'])
    // Trigger download via a hidden anchor
    const link = document.createElement('a')
    link.href = withBasePath(resp.download_url)
    link.download = resp.filename
    document.body.appendChild(link)
    link.click()
    link.remove()
    toast.success(`Exported ${resp.filename}`)
  },
  onError: (e) => toast.error(`Export failed: ${getErrorMessage(e)}`),
})
```

Grid layout: stays balanced (3 cols × 2 rows after Slice 5b adds
the Publish button).

Run history list already renders any source from the runs table; the
new `budget_export` source appears with the same pattern as
`budget_import`. Add a copy mapping for the source label
(`runs.source === 'budget_export'` → `"Export .xlsx"`).

### Tests — Slice 5a

**pytest** — new `tests/test_plan_exporter.py`:

- `test_exporter_returns_xlsx_bytes_with_correct_layout` — render,
  assert column letters + row offsets match importer expectations.
- `test_exporter_round_trips_through_importer` — render xlsx, save
  to tmp file, re-import via `BudgetImporter`, assert plan
  categories match by `(group_name, category_name)`.
- `test_exporter_preserves_formula_text` — seed a category with
  `formula_text='=B2+B3'`, export, assert that cell holds the
  formula string.
- `test_exporter_groups_have_empty_amount_cells` — group rows
  emitted correctly.
- `test_exporter_handles_empty_block` — e.g. no savings →
  block columns L:M empty (no exception).
- `test_exporter_filename_includes_plan_name_and_date` —
  format check.

**pytest** — extend `tests/test_api.py`:

- `test_export_endpoint_returns_201_with_run_id`
- `test_export_endpoint_records_run`
- `test_export_download_endpoint_streams_bytes` — checks
  Content-Disposition + content-type.
- `test_export_download_404_for_unknown_run_id`

**vitest** — extend `frontend/src/routes/operations/page.test.ts`:

- `Export .xlsx button calls exportBudget and triggers a download` —
  mock anchor click, assert mutation invoked.
- `Export error shows toast.`

### Slice 5a pass gate

- `make test` green; `npm run check` 0/0; `npx vitest run` green.
- Manual smoke: docker-compose stack, click `Export .xlsx`,
  download lands on disk, open in Excel/Numbers, layout matches
  the importer's `2026 Budget` source. Re-import the downloaded
  file via `POST /api/budget/import` (after copying to the
  `BUDGET_XLSX_HOST_PATH` location) — plan rows come back identical.
- Commit: `Add Phase 2.5d Slice 5a: xlsx export + download`.

---

## Slice 5b — Google Sheets publish

### Dependencies (`pyproject.toml`)

Add to `dependencies`:

```toml
"google-api-python-client>=2.130,<3.0",
"google-auth-httplib2>=0.2,<1.0",
```

(`google-auth` already at 2.40+; `google-auth-oauthlib` not needed
for service-account flow.)

`make install` reruns `pip install -e .[dev]` to pick them up.

### Auth scope expansion (`src/finclaide/budget_source.py`)

The existing `GoogleServiceAccountTokenProvider` (line 177) uses
`https://www.googleapis.com/auth/drive.readonly`. Add a new constant:

```python
DRIVE_FILE_SCOPE = "https://www.googleapis.com/auth/drive.file"
```

Provide a parallel provider (or extend the existing one to take
a list of scopes). `SheetsPublisher` instantiates with both
`drive.readonly` (for read-after-write verification) and
`drive.file` (for write).

**Operator setup note** (added to `docs/mcp.md` and the spec
"Setup" section below): the user must re-share the source workbook
with the service account email as **Editor** (not just Viewer) for
write to succeed. One-time action.

### Service layer (NEW: `src/finclaide/sheets_publisher.py`)

```python
class SheetsPublisher:
    """Publishes the active plan as a new tab in the configured
    Google Sheets workbook."""

    def __init__(
        self,
        plan_exporter: PlanExporter,
        config: AppConfig,
        token_provider: GoogleServiceAccountTokenProvider,
    ):
        self._exporter = plan_exporter
        self._config = config
        self._token = token_provider

    def publish(self) -> dict[str, Any]:
        """Renders the workbook, uploads as new tab to
        config.google_sheets_file_id. Returns
        {tab_name, tab_id, tab_url, file_size_bytes}."""
```

Behavior:
- Generate workbook bytes via `self._exporter.export_active_plan()`.
- Open with `openpyxl` (just the source tab in the rendered xlsx).
- Compute target tab name:
  `f"{config.budget_sheet_name} — published {now:%Y-%m-%d %H%M}"`.
- Use Sheets API `spreadsheets.batchUpdate` with two requests:
  1. `addSheet` with the target tab name (collision retry: append
     `(2)`, `(3)` if duplicate).
  2. `updateCells` writing the per-cell values + formulas extracted
     from the openpyxl workbook into the new tab. Encode currency
     format via `userEnteredFormat.numberFormat`.
- Return tab metadata + computed URL:
  `f"https://docs.google.com/spreadsheets/d/{file_id}/edit#gid={tab_id}"`.

Use `googleapiclient.discovery.build('sheets', 'v4',
credentials=...)`. The token-refresh dance is already handled by
the existing token provider.

### API layer (`src/finclaide/api.py`, `ui_api.py`)

```python
@api.post("/budget/publish")
@require_bearer_token
def publish_budget():
    container = _container()
    with container.operation_lock.guard("budget_publish"):
        result = run_budget_publish(container)
    return jsonify(result), 201
```

UI mirror at `/ui-api/budget/publish`.

### Operations layer

```python
def run_budget_publish(container) -> dict[str, Any]:
    if container.config.budget_source != "google_sheets":
        raise ConfigError(
            "Publish requires FINCLAIDE_BUDGET_SOURCE=google_sheets "
            "and FINCLAIDE_GOOGLE_SHEETS_FILE_ID configured."
        )
    result = container.sheets_publisher.publish()
    container.database.record_run(
        source='budget_publish', status='success',
        details=result, ...
    )
    return result
```

Errors: 400 if `budget_source` is local/remote (not Sheets); 502
if Drive API fails (record run with status='failure', details
includes error string).

### Frontend (`frontend/src/lib/api.ts`)

```ts
export const BudgetPublishResponseSchema = z.object({
  run_id: z.number(),
  tab_name: z.string(),
  tab_id: z.number(),
  tab_url: z.string(),
  file_size_bytes: z.number(),
})

export async function publishBudget() { ... }
```

### Frontend — Operations page

Add sixth button "Publish to Sheets" to the action grid. Disabled
when `config.budget_source !== 'google_sheets'` (status payload
already exposes plan source type via `_plan_source_type` at
`services.py:781`). On click:

```ts
const publishMutation = createMutation({
  mutationFn: () => publishBudget(),
  onSuccess: (resp) => {
    invalidate(['runs', 'status'])
    toast.success(`Published as "${resp.tab_name}"`, {
      action: { label: 'Open', onClick: () => window.open(resp.tab_url, '_blank') },
    })
  },
})
```

Run history mapping: `runs.source === 'budget_publish'` →
`"Publish to Sheets"`.

### Tests — Slice 5b

**pytest** — new `tests/test_sheets_publisher.py`:

- `test_publisher_creates_new_tab_with_dated_name` — mock
  `googleapiclient.discovery.build`, assert `addSheet` request
  payload.
- `test_publisher_writes_cells_in_importer_layout` — assert
  `updateCells` request carries the right cell coordinates.
- `test_publisher_handles_tab_name_collision` — first add returns
  409, second add succeeds with `(2)` suffix.
- `test_publisher_returns_tab_url` — URL format check.
- `test_publisher_raises_when_budget_source_not_google_sheets`.

**pytest** — extend `tests/test_api.py`:

- `test_publish_endpoint_returns_201_on_success`
- `test_publish_endpoint_400_when_budget_source_not_google_sheets`
- `test_publish_endpoint_502_when_drive_api_fails` (mock
  `googleapiclient.errors.HttpError`).

**vitest** — extend `frontend/src/routes/operations/page.test.ts`:

- `Publish to Sheets button is disabled when budget_source is local.`
- `Publish success shows toast with tab URL.`

### Slice 5b pass gate

- `make test` green; `npm run check` 0/0; `npx vitest run` green.
- Manual smoke: against real Google Sheet (operator re-shares
  workbook as Editor first), click Publish, verify new tab
  appears with correct layout and formulas. Re-import the
  canonical `2026 Budget` tab — still works. Click "Open" on the
  toast — Sheet loads at the new tab.
- Commit: `Add Phase 2.5d Slice 5b: Google Sheets publish`.

---

## End-to-end smoke (after both commits)

1. From Operations, click `Export .xlsx` — file downloads, open
   in Excel/Numbers, all 5 blocks present + formulas, totals
   match the active plan.
2. Drop the downloaded file into `BUDGET_XLSX_HOST_PATH`,
   trigger `Import Budget`, plan re-imports identically.
3. From Operations, click `Publish to Sheets` — toast appears
   with tab name and Open link, target Sheet has new tab named
   `2026 Budget — published {date}`, original `2026 Budget` tab
   unchanged.
4. Re-trigger Publish — second tab appears with `(2)` suffix on
   the same minute, or fresh date stamp later.
5. Run history shows two new sources: "Export .xlsx" and
   "Publish to Sheets".

## Setup notes (operator-facing)

Add to `docs/setup.md` (or `README.md`'s config section):

> **Sheets publish requires write access.** The Drive service
> account that imports your budget must also be granted **Editor**
> on the source workbook. In Google Sheets: Share → add the
> service account email → set role to Editor. Without this, the
> Publish to Sheets button returns a 403.

## Critical files

Backend:
- `src/finclaide/plan_exporter.py` (NEW) — `PlanExporter`.
- `src/finclaide/sheets_publisher.py` (NEW) — `SheetsPublisher`.
- `src/finclaide/export_storage.py` (NEW) — `ExportStorage`.
- `src/finclaide/operations.py` — `run_budget_export`,
  `run_budget_publish`.
- `src/finclaide/api.py` — `/budget/export`, `/budget/export/<id>/download`,
  `/budget/publish` endpoints.
- `src/finclaide/ui_api.py` — UI mirrors.
- `src/finclaide/services.py` — wire `PlanExporter`,
  `ExportStorage`, `SheetsPublisher` into `ServiceContainer`.
- `src/finclaide/budget_source.py` — add `drive.file` scope.
- `pyproject.toml` — `google-api-python-client`,
  `google-auth-httplib2`.

Frontend:
- `frontend/src/lib/api.ts` — `exportBudget`, `publishBudget`,
  Zod schemas.
- `frontend/src/routes/operations/+page.svelte` — two new
  buttons + run-history source mapping.

Tests:
- `tests/test_plan_exporter.py` (NEW) — 6 cases.
- `tests/test_sheets_publisher.py` (NEW) — 5 cases.
- `tests/test_api.py` — +7 cases.
- `frontend/src/routes/operations/page.test.ts` — +4 cases.

## Out of scope

- **Auto-publish on commit / scheduled publish.** Manual only
  per user decision.
- **Format/style preservation in Sheets.** Numbers and formulas
  only. Bold headers, conditional formatting, etc. not carried
  over.
- **Per-block selective export.** Always all 5 blocks.
- **Custom destination Sheet ID.** Uses configured
  `FINCLAIDE_GOOGLE_SHEETS_FILE_ID`. No UI to publish to a
  different Sheet.
- **Diff visualization between published tabs.** History tab is
  just a list; the operator can compare in Sheets.
- **MCP tools for export/publish.** Tiny follow-up; doesn't
  block this slice.
- **Export retention beyond 20 files.** `ExportStorage.prune`
  keeps the 20 most recent xlsx files; older runs lose their
  download bytes (run history rows persist).
- **/planning header export button.** v1 puts the trigger only
  on Operations to match how every other ops action works.

## Verification commands

```bash
# Backend
make test                                    # +18 cases (pytest 190 → 208)
. .venv/bin/activate && pytest tests/test_plan_exporter.py -v
. .venv/bin/activate && pytest tests/test_sheets_publisher.py -v

# Frontend
cd frontend && npm run check                 # 0/0 expected
cd frontend && npx vitest run                # +4 cases (367 → 371)
```

End-to-end smoke against `docker compose up --build -d` per the
slice pass gates above.
