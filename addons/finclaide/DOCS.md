# Finclaide

Finclaide is a private finance dashboard for one YNAB budget plus a spreadsheet-based annual plan. In Home Assistant, it runs behind ingress and stores its SQLite database in the add-on data volume.

## Features

- Home Assistant ingress sidebar panel
- Google Sheets and Google Drive-hosted `.xlsx` budget import
- YNAB sync and strict reconcile workflow
- Scheduled refresh every N minutes
- Private API can stay disabled by default; when enabled, it is available on
  port `8098` for bearer-token MCP clients over LAN/VPN/Tailscale

## Setup

1. Open the add-on configuration.
2. Paste `ynab_access_token` and `ynab_plan_id`.
3. Choose `budget_source`.

### Google Sheets / Drive-hosted workbook

1. Set `budget_source` to `google_sheets`.
2. Set `google_file_id` to the spreadsheet or Drive file ID.
3. Set `google_service_account_file` to `google-service-account.json`.
4. Share the sheet/file with the service account email as a viewer.
5. Put the service account JSON file into the add-on config directory.

For a Google Sheet URL like:

```text
https://docs.google.com/spreadsheets/d/1AbCdEfGhIjKlMnOpQrStUvWxYz/edit
```

the `google_file_id` is:

```text
1AbCdEfGhIjKlMnOpQrStUvWxYz
```

If `google_file_id` is blank, the add-on cannot start in `google_sheets`
mode. Either fill it in or switch `budget_source` to `local_file` or
`remote_url`.

Home Assistant may not create the add-on config directory automatically.
From the Terminal & SSH add-on, find the real add-on slug:

```bash
ha addons list | grep -i finclaide
```

Create the matching config directory if it is missing:

```bash
mkdir -p /addon_configs/<actual-finclaide-slug>
```

Then create the JSON file and paste the full Google service account JSON:

```bash
vi /addon_configs/<actual-finclaide-slug>/google-service-account.json
```

The file must contain the raw JSON object, not the path to the file and not a
Home Assistant secret reference. The add-on mounts this directory at `/config`,
so `google_service_account_file: google-service-account.json` resolves to:

```text
/config/google-service-account.json
```

inside the add-on.

### Local workbook file

1. Put `Budget.xlsx` into the same add-on config directory described above.
2. Set `budget_source` to `local_file`.
3. Set `local_workbook_file` if the filename is not `Budget.xlsx`.

### Remote workbook URL

1. Set `budget_source` to `remote_url`.
2. Set `remote_workbook_url` to a direct `.xlsx` export URL.

## Notes

- The add-on stores its database in `/data/finclaide.db`.
- The Google/remote workbook cache is stored in `/data/Budget.google.xlsx`.
- The dashboard uses Home Assistant ingress. You normally do not need to expose a separate port.
- If `enable_private_api` is `false`, `/api/*` is blocked at both the ingress proxy and the private API port.
- To use MCP from another machine, enable `enable_private_api`, set a strong `api_token`, expose port `8098` in the add-on network settings, and point MCP at `http://<home-assistant-tailscale-name>:8098/api`.
