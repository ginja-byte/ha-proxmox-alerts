"""The Proxmox Alerts integration.

Receives webhook notifications from Proxmox VE and Proxmox Backup Server,
classifies them by severity, fires events on the HA bus, and exposes state
via sensor entities.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_send

from .const import DOMAIN, SIGNAL_NEW_EVENT
from .webhook import async_register_webhook, async_unregister_webhook

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SENSOR]


@dataclass
class ProxmoxAlertsRuntimeData:
    """Per-config-entry runtime state.

    Stored on the config entry so platforms can read it. Holds the latest
    event details and a count, kept in memory only — sensors with the
    RestoreEntity mixin persist their last state across restarts.
    """

    name: str
    source_type: str
    webhook_id: str
    event_count: int = 0
    last_event: dict[str, Any] | None = None
    last_event_at: datetime | None = None
    listeners: list = field(default_factory=list)


async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up Proxmox Alerts from a config entry."""
    hass.data.setdefault(DOMAIN, {})

    runtime = ProxmoxAlertsRuntimeData(
        name=entry.data["name"],
        source_type=entry.data["source_type"],
        webhook_id=entry.data["webhook_id"],
    )
    hass.data[DOMAIN][entry.entry_id] = runtime

    # Register the webhook handler
    async_register_webhook(hass, entry)

    # React to options updates without requiring a reload
    entry.async_on_unload(entry.add_update_listener(_async_options_updated))

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        async_unregister_webhook(hass, entry)
        hass.data[DOMAIN].pop(entry.entry_id, None)
    return unload_ok


async def _async_options_updated(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update — just refresh entities, no reload needed."""
    runtime: ProxmoxAlertsRuntimeData | None = hass.data.get(DOMAIN, {}).get(entry.entry_id)
    if runtime is not None:
        async_dispatcher_send(hass, f"{SIGNAL_NEW_EVENT}_{entry.entry_id}")


@callback
def record_event(
    hass: HomeAssistant,
    entry: ConfigEntry,
    normalised: dict[str, Any],
) -> None:
    """Update runtime state with a new event and notify entities.

    Called from webhook.py after a payload has been parsed and accepted.
    """
    runtime: ProxmoxAlertsRuntimeData = hass.data[DOMAIN][entry.entry_id]
    runtime.event_count += 1
    runtime.last_event = normalised
    runtime.last_event_at = datetime.now()
    async_dispatcher_send(hass, f"{SIGNAL_NEW_EVENT}_{entry.entry_id}")
