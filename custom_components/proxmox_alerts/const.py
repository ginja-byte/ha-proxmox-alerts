"""Constants for the Proxmox Alerts integration."""
from __future__ import annotations

from typing import Final

DOMAIN: Final = "proxmox_alerts"

# Config entry data keys
CONF_NAME: Final = "name"
CONF_SOURCE_TYPE: Final = "source_type"
CONF_WEBHOOK_ID: Final = "webhook_id"

# Options keys (mutable via Options Flow)
OPT_ROUTE_INFO_EVENTS: Final = "route_info_events"
OPT_LOG_RAW_PAYLOADS: Final = "log_raw_payloads"

DEFAULT_ROUTE_INFO_EVENTS: Final = True
DEFAULT_LOG_RAW_PAYLOADS: Final = False

# Source types — Proxmox VE or Proxmox Backup Server
SOURCE_TYPE_PVE: Final = "pve"
SOURCE_TYPE_PBS: Final = "pbs"
SOURCE_TYPES: Final = [SOURCE_TYPE_PVE, SOURCE_TYPE_PBS]

# Severity mapping: Proxmox severity string -> normalised level
SEVERITY_MAP: Final = {
    "info": "info",
    "notice": "info",
    "warning": "warn",
    "warn": "warn",
    "error": "critical",
    "critical": "critical",
    "unknown": "critical",
}

NORMALISED_SEVERITIES: Final = ["info", "warn", "critical"]

# Event fired on the HA bus when a webhook is received and accepted
EVENT_PROXMOX_ALERT: Final = f"{DOMAIN}_event"

# Signal dispatched within HA to update entities on new events
SIGNAL_NEW_EVENT: Final = f"{DOMAIN}_new_event"
