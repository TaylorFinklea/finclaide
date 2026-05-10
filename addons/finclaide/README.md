# Finclaide Home Assistant Add-on

This add-on packages the Finclaide dashboard for Home Assistant ingress.
It can also expose the token-protected private API on port `8098` for MCP
clients over a trusted LAN/VPN such as Tailscale.

The Docker build clones the main Finclaide repository from GitHub using the defaults in `build.yaml`. Push your branch before relying on the add-on build so the Home Assistant builder can fetch the same code you tested locally.
