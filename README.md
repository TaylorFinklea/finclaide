# Finclaide

Docker-first financial planning and reporting for a single YNAB plan plus a Google Sheets budget export.

## Runtime

1. Copy `.env.example` to `.env` and fill in the YNAB and API tokens.
2. Confirm `BUDGET_XLSX_HOST_PATH` points at the exported workbook on the host.
3. Run `make build`.
4. Run `make up`.

The Dash UI is available at `http://localhost:8050/` and the private JSON API is available under `http://localhost:8050/api/*`.

## Tests

Run the full test suite in Docker:

```bash
make test
```
