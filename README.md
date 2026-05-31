# Proxmox Alerts for Home Assistant

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-41BDF5.svg)](https://hacs.xyz/)
[![Validate](https://github.com/ginja-byte/ha-proxmox-alerts/actions/workflows/validate.yml/badge.svg)](https://github.com/ginja-byte/ha-proxmox-alerts/actions/workflows/validate.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

Receive webhook notifications from **Proxmox VE** and **Proxmox Backup Server** in Home Assistant. Each Proxmox instance is added as its own integration entry with a dedicated webhook URL, exposing sensor entities for the last event, last severity, and total event count.

## Features

- 🪝 **Webhook receiver** — one webhook per instance, generated automatically
- 🏷️ **Multi-instance** — add multiple PVE clusters and PBS servers independently
- 📊 **Sensor entities** — `last_event`, `last_severity`, `event_count` per instance
- 🔔 **HA events** — fires `proxmox_alerts_event` on the HA bus for automations
- 🎚️ **Configurable** — toggle info-event routing and raw payload logging via the options flow
- 🧪 **Tested** — hassfest + HACS validation on every push

## Requirements

- Home Assistant 2024.6 or newer
- Proxmox VE 8.2+ or Proxmox Backup Server 3.2+ (older versions work but use simpler payload templating)
- Home Assistant reachable from Proxmox over HTTPS (Nabu Casa Cloudhook, reverse proxy, or local network)

## Installation

### HACS (recommended)

1. Open HACS → **Integrations** → menu (⋮) → **Custom repositories**.
2. Add `https://github.com/ginja-byte/ha-proxmox-alerts` with category **Integration**.
3. Install **Proxmox Alerts** from the list, then restart Home Assistant.

### Manual

1. Copy `custom_components/proxmox_alerts/` into your `<config>/custom_components/` directory.
2. Restart Home Assistant.

## Setup

### 1. Add the integration in Home Assistant

1. **Settings → Devices & Services → Add Integration → "Proxmox Alerts"**.
2. Give it a name (e.g. `Main Cluster`) and pick the source type (`pve` or `pbs`).
3. Submit — a webhook URL is generated and shown on the new device's page.

### 2. Configure the webhook in Proxmox

#### Proxmox VE 8.2+

1. **Datacenter → Notifications → Add → Webhook**.
2. Set:
   - **URL:** the webhook URL from step 1 (looks like `https://your-ha/api/webhook/<random>`)
   - **Method:** POST
   - **Header:** `Content-Type: application/json`
   - **Body:**
     ```
     {
       "source": "pve",
       "hostname": "{{ hostname }}",
       "severity": "{{ severity }}",
       "title": "{{ title }}",
       "message": "{{ escape message }}",
       "fields": {{ fields | json }},
       "timestamp": {{ timestamp }}
     }
     ```
3. **Datacenter → Notifications → Notification Matchers → Add** — route events to your new webhook target.

#### Proxmox Backup Server

Same flow under **Configuration → Other → Notifications**. Use `"source": "pbs"` in the body.

### 3. (Optional) Tune via the options flow

Go to the integration card → **Configure** to toggle:
- **Forward info-severity events** — when off, drops info events at the webhook handler.
- **Log raw payloads** — for debugging unfamiliar payload shapes.

## Entities created

Per instance:

| Entity | Description |
|---|---|
| `sensor.<name>_last_event` | Title of the most recent event. Attributes hold severity, message, entity, tags, fingerprint, fired_at, webhook URL. |
| `sensor.<name>_last_severity` | Enum: `info`, `warn`, `critical`. |
| `sensor.<name>_event_count` | Total events received (monotonically increasing). |

## Automating off events

Every accepted webhook fires a `proxmox_alerts_event` event on the HA event bus. Sample automation:

```yaml
automation:
  - alias: "Discord: critical Proxmox alerts"
    trigger:
      - platform: event
        event_type: proxmox_alerts_event
        event_data:
          severity: critical
    action:
      - service: notify.discord_critical
        data:
          title: "{{ trigger.event.data.instance }}: {{ trigger.event.data.title }}"
          message: "{{ trigger.event.data.message }}"
```

Event data shape:

```json
{
  "config_entry_id": "abc123...",
  "instance": "Main Cluster",
  "source": "proxmox_alerts",
  "source_type": "pve",
  "severity": "critical",
  "raw_severity": "error",
  "title": "Backup failed on pve-01",
  "message": "Job vzdump-lxc-101 exited with status ERROR",
  "entity": "pve-01",
  "tags": ["proxmox", "pve"],
  "fingerprint": "pve:pve-01:backup-failed-on-pve-01",
  "raw": { /* original Proxmox payload */ }
}
```

## Severity mapping

| Proxmox value | Normalised |
|---|---|
| `info`, `notice` | `info` |
| `warning`, `warn` | `warn` |
| `error`, `critical`, `unknown` | `critical` |

## Testing without Proxmox

Use **Developer Tools → Actions** with:

```yaml
action: webhook.async_handle
data:
  webhook_id: "<paste the webhook ID portion from the URL>"
  data:
    source: pve
    hostname: test-host
    severity: warning
    title: "Test alert"
    message: "This is a test"
```

Or with `curl`:

```bash
curl -X POST -H "Content-Type: application/json" \
  -d '{"source":"pve","hostname":"test","severity":"warning","title":"Test","message":"hello"}' \
  https://your-ha/api/webhook/<your-webhook-id>
```

## Troubleshooting

- **Webhook returns 404** — the integration isn't loaded or the webhook ID is wrong. Check **Settings → Devices & Services → Proxmox Alerts → Logs**.
- **Webhook returns 400** — payload isn't valid JSON or isn't a JSON object. Enable **Log raw payloads** in the options flow and check logs.
- **No events fired** — confirm info-event routing is on if you're sending info-severity test events.

## License

MIT — see [LICENSE](LICENSE).
