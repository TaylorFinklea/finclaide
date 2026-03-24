# Finclaide

Finclaide is a private finance dashboard for one YNAB budget plus a spreadsheet-based annual plan. In Home Assistant, it runs behind ingress and stores its SQLite database in the add-on data volume.

## Features

- Home Assistant ingress sidebar panel
- Google Sheets and Google Drive-hosted `.xlsx` budget import
- YNAB sync and strict reconcile workflow
- Scheduled refresh every N minutes
- Private API can stay disabled by default

## Setup

1. Open the add-on configuration.
2. Paste `ynab_access_token` and `ynab_plan_id`.
3. Choose `budget_source`.

### Google Sheets / Drive-hosted workbook

1. Set `budget_source` to `google_sheets`.
2. Put your Google service account JSON into the add-on config directory as `/addon_configs/<slug>/google-service-account.json`.
3. Set `google_service_account_file` to that filename.
4. Set `google_file_id` to the spreadsheet or Drive file ID.
5. Share the sheet/file with the service account email as a viewer.

### Local workbook file

1. Put `Budget.xlsx` into the add-on config directory.
2. Set `budget_source` to `local_file`.
3. Set `local_workbook_file` if the filename is not `Budget.xlsx`.

### Remote workbook URL

1. Set `budget_source` to `remote_url`.
2. Set `remote_workbook_url` to a direct `.xlsx` export URL.

## Notes

- The add-on stores its database in `/data/finclaide.db`.
- The Google/remote workbook cache is stored in `/data/Budget.google.xlsx`.
- The dashboard uses Home Assistant ingress. You normally do not need to expose a separate port.
- If `enable_private_api` is `false`, `/api/*` is blocked at the ingress proxy.
