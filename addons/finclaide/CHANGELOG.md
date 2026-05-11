# Changelog

## 0.1.5

- Accept Home Assistant ingress UI writes even when the add-on sees an internal proxy host

## 0.1.4

- Allow legitimate Home Assistant ingress UI writes when HTTPS terminates before the add-on

## 0.1.3

- Clarify where to find the required Google Sheet/Drive file ID
- Make the startup error for missing `google_file_id` actionable

## 0.1.2

- Allow `remote_workbook_url` to stay blank unless remote URL mode is selected
- Document the exact Home Assistant service account JSON setup flow

## 0.1.1

- Add optional port 8098 private API for MCP clients over LAN/VPN/Tailscale
- Expand MCP reconciliation remediation tools
- Ignore generated root-level screenshots

## 0.1.0

- Initial Home Assistant add-on scaffold
- Ingress-ready dashboard packaging
- Add-on options for YNAB, Google Sheets, scheduling, and private API access
