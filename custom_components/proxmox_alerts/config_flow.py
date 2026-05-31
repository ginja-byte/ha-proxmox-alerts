"""Config flow for Proxmox Alerts.

Walks the user through:
  1. Naming the instance (e.g. "Main Cluster", "Offsite Backup")
  2. Choosing source type (PVE or PBS)

A random webhook ID is generated server-side — the user doesn't need to
provide one. After setup, the webhook URL is shown in the integration's
info card via repair-style notification.
"""
from __future__ import annotations

import secrets
from typing import Any

import voluptuous as vol
from homeassistant.components import webhook as webhook_component
from homeassistant.config_entries import ConfigEntry, ConfigFlow, OptionsFlow
from homeassistant.core import callback
from homeassistant.data_entry_flow import FlowResult

from .const import (
    DEFAULT_LOG_RAW_PAYLOADS,
    DEFAULT_ROUTE_INFO_EVENTS,
    DOMAIN,
    OPT_LOG_RAW_PAYLOADS,
    OPT_ROUTE_INFO_EVENTS,
    SOURCE_TYPE_PVE,
    SOURCE_TYPES,
)


class ProxmoxAlertsConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle the initial setup."""

    VERSION = 1

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initiated by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input["name"].strip()
            source_type = user_input["source_type"]

            # Enforce a unique combination of name + source type
            unique_id = f"{source_type}:{name.lower()}"
            await self.async_set_unique_id(unique_id)
            self._abort_if_unique_id_configured()

            # Generate a fresh webhook ID — long random, URL-safe
            webhook_id = secrets.token_urlsafe(32)

            return self.async_create_entry(
                title=f"{name} ({source_type.upper()})",
                data={
                    "name": name,
                    "source_type": source_type,
                    "webhook_id": webhook_id,
                },
                options={
                    OPT_ROUTE_INFO_EVENTS: DEFAULT_ROUTE_INFO_EVENTS,
                    OPT_LOG_RAW_PAYLOADS: DEFAULT_LOG_RAW_PAYLOADS,
                },
            )

        schema = vol.Schema(
            {
                vol.Required("name", default="Main"): str,
                vol.Required("source_type", default=SOURCE_TYPE_PVE): vol.In(SOURCE_TYPES),
            }
        )
        return self.async_show_form(
            step_id="user",
            data_schema=schema,
            errors=errors,
            description_placeholders={
                "webhook_url_example": (
                    f"{self.hass.config.external_url or 'https://your-ha.example'}"
                    f"{webhook_component.async_generate_path('XXX')}"
                )
            },
        )

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> ProxmoxAlertsOptionsFlow:
        """Get the options flow for this handler."""
        return ProxmoxAlertsOptionsFlow(config_entry)


class ProxmoxAlertsOptionsFlow(OptionsFlow):
    """Handle options updates after initial setup."""

    def __init__(self, config_entry: ConfigEntry) -> None:
        """Initialize options flow."""
        self.config_entry = config_entry

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Manage the options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options
        schema = vol.Schema(
            {
                vol.Required(
                    OPT_ROUTE_INFO_EVENTS,
                    default=current.get(OPT_ROUTE_INFO_EVENTS, DEFAULT_ROUTE_INFO_EVENTS),
                ): bool,
                vol.Required(
                    OPT_LOG_RAW_PAYLOADS,
                    default=current.get(OPT_LOG_RAW_PAYLOADS, DEFAULT_LOG_RAW_PAYLOADS),
                ): bool,
            }
        )
        return self.async_show_form(step_id="init", data_schema=schema)
