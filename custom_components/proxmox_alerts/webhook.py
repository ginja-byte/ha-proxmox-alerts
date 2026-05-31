"""Webhook registration and handling for Proxmox Alerts.

The HA `webhook` component exposes incoming POST requests at:
    /api/webhook/<webhook_id>

We register a handler keyed on the per-entry webhook_id; the handler parses
the JSON body Proxmox sends, normalises severity, fires a HA event, and
updates entity state via dispatcher.
"""
from __future__ import annotations

import logging
import re
from typing import Any

from aiohttp import web
from homeassistant.components import webhook as webhook_component
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback

from .const import (
    DOMAIN,
    EVENT_PROXMOX_ALERT,
    OPT_LOG_RAW_PAYLOADS,
    OPT_ROUTE_INFO_EVENTS,
    SEVERITY_MAP,
)

_LOGGER = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def _slug(text: str) -> str:
    """Lowercase, replace non-alphanumeric with dashes, trim."""
    return _SLUG_RE.sub("-", text.lower()).strip("-") or "unknown"


def _normalise(payload: dict[str, Any], source_type: str) -> dict[str, Any]:
    """Convert a raw Proxmox webhook payload to our normalised event shape."""
    hostname = str(payload.get("hostname") or "unknown")
    raw_sev = str(payload.get("severity") or "info").lower()
    severity = SEVERITY_MAP.get(raw_sev, "info")
    title = str(payload.get("title") or "Proxmox event")
    message = str(payload.get("message") or "(no message)")
    fingerprint = f"{source_type}:{hostname}:{_slug(title)}"

    return {
        "source": "proxmox_alerts",
        "source_type": source_type,
        "severity": severity,
        "raw_severity": raw_sev,
        "title": title,
        "message": message,
        "entity": hostname,
        "tags": ["proxmox", source_type],
        "fingerprint": fingerprint,
        "raw": payload,
    }


@callback
def async_register_webhook(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Register the webhook for this config entry."""
    webhook_id = entry.data["webhook_id"]
    source_type = entry.data["source_type"]
    instance_name = entry.data["name"]

    async def handler(
        hass: HomeAssistant, webhook_id: str, request: web.Request
    ) -> web.Response:
        """Process an inbound Proxmox webhook."""
        # Late import to avoid circular dep
        from . import record_event

        try:
            payload = await request.json()
        except Exception as exc:  # noqa: BLE001 — any parse error is a 400
            _LOGGER.warning("Invalid JSON from Proxmox webhook %s: %s", webhook_id, exc)
            return web.Response(status=400, text="invalid json")

        if not isinstance(payload, dict):
            _LOGGER.warning("Proxmox webhook %s payload is not an object", webhook_id)
            return web.Response(status=400, text="payload must be a JSON object")

        if entry.options.get(OPT_LOG_RAW_PAYLOADS, False):
            _LOGGER.info("[%s] Raw payload: %s", instance_name, payload)

        normalised = _normalise(payload, source_type)

        # Drop info events if the user disabled routing them
        if normalised["severity"] == "info" and not entry.options.get(
            OPT_ROUTE_INFO_EVENTS, True
        ):
            return web.Response(status=204)

        # Fire HA event — users automate against this
        hass.bus.async_fire(
            EVENT_PROXMOX_ALERT,
            {
                "config_entry_id": entry.entry_id,
                "instance": instance_name,
                **normalised,
            },
        )

        # Update entity state
        record_event(hass, entry, normalised)

        return web.Response(status=200, text="ok")

    webhook_component.async_register(
        hass,
        DOMAIN,
        f"Proxmox Alerts ({instance_name})",
        webhook_id,
        handler,
        local_only=False,
        allowed_methods=["POST"],
    )
    _LOGGER.debug(
        "Registered Proxmox Alerts webhook %s for instance %s",
        webhook_id,
        instance_name,
    )


@callback
def async_unregister_webhook(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Unregister the webhook on unload."""
    webhook_component.async_unregister(hass, entry.data["webhook_id"])
