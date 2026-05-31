"""Sensor platform for Proxmox Alerts.

Creates three sensor entities per config entry:
  - sensor.<name>_last_event       (last event title; attributes hold detail)
  - sensor.<name>_event_count      (total events received since first install)
  - sensor.<name>_last_severity    (info / warn / critical)
"""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components import webhook as webhook_component
from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceEntryType, DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.restore_state import RestoreEntity

from . import ProxmoxAlertsRuntimeData
from .const import DOMAIN, SIGNAL_NEW_EVENT

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up sensor entities for a config entry."""
    runtime: ProxmoxAlertsRuntimeData = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            _LastEventSensor(hass, entry, runtime),
            _LastSeveritySensor(hass, entry, runtime),
            _EventCountSensor(hass, entry, runtime),
        ]
    )


class _BaseSensor(SensorEntity, RestoreEntity):
    """Shared base — wires up dispatcher signals and device info."""

    _attr_has_entity_name = True
    _attr_should_poll = False

    def __init__(
        self,
        hass: HomeAssistant,
        entry: ConfigEntry,
        runtime: ProxmoxAlertsRuntimeData,
        description: SensorEntityDescription,
    ) -> None:
        self.hass = hass
        self._entry = entry
        self._runtime = runtime
        self.entity_description = description
        self._attr_unique_id = f"{entry.entry_id}_{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name=f"Proxmox Alerts: {runtime.name}",
            manufacturer="Proxmox",
            model=runtime.source_type.upper(),
            entry_type=DeviceEntryType.SERVICE,
            configuration_url=None,
        )

    async def async_added_to_hass(self) -> None:
        """Subscribe to dispatcher signals when added."""
        await super().async_added_to_hass()

        # Restore previous state from RestoreEntity
        last = await self.async_get_last_state()
        if last is not None and last.state not in (None, "unknown", "unavailable"):
            self._restore_from_state(last.state, last.attributes)

        self.async_on_remove(
            async_dispatcher_connect(
                self.hass,
                f"{SIGNAL_NEW_EVENT}_{self._entry.entry_id}",
                self._handle_update,
            )
        )

    def _restore_from_state(self, state: str, attrs: dict[str, Any]) -> None:
        """Override per-sensor to restore."""

    @callback
    def _handle_update(self) -> None:
        """Refresh state on dispatcher signal."""
        self.async_write_ha_state()


class _LastEventSensor(_BaseSensor):
    """Title of the most recent event."""

    def __init__(self, hass, entry, runtime):
        super().__init__(
            hass,
            entry,
            runtime,
            SensorEntityDescription(
                key="last_event",
                translation_key="last_event",
                icon="mdi:bell-ring-outline",
            ),
        )

    @property
    def native_value(self) -> str | None:
        if self._runtime.last_event is None:
            return None
        return self._runtime.last_event.get("title")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        ev = self._runtime.last_event or {}
        return {
            "severity": ev.get("severity"),
            "raw_severity": ev.get("raw_severity"),
            "entity": ev.get("entity"),
            "message": ev.get("message"),
            "tags": ev.get("tags"),
            "fingerprint": ev.get("fingerprint"),
            "fired_at": self._runtime.last_event_at.isoformat()
            if self._runtime.last_event_at
            else None,
            "webhook_url": webhook_component.async_generate_url(
                self.hass, self._runtime.webhook_id
            ),
        }

    def _restore_from_state(self, state, attrs):
        # Reconstruct a minimal last_event so the sensor body shows on restart
        if self._runtime.last_event is None and state:
            self._runtime.last_event = {
                "title": state,
                "severity": attrs.get("severity"),
                "raw_severity": attrs.get("raw_severity"),
                "entity": attrs.get("entity"),
                "message": attrs.get("message"),
                "tags": attrs.get("tags"),
                "fingerprint": attrs.get("fingerprint"),
            }


class _LastSeveritySensor(_BaseSensor):
    """Severity of the most recent event."""

    _attr_device_class = None

    def __init__(self, hass, entry, runtime):
        super().__init__(
            hass,
            entry,
            runtime,
            SensorEntityDescription(
                key="last_severity",
                translation_key="last_severity",
                icon="mdi:alert-circle-outline",
                options=["info", "warn", "critical"],
                device_class="enum",
            ),
        )

    @property
    def native_value(self) -> str | None:
        if self._runtime.last_event is None:
            return None
        return self._runtime.last_event.get("severity")


class _EventCountSensor(_BaseSensor):
    """Monotonically-increasing counter of events received."""

    _attr_state_class = "total_increasing"

    def __init__(self, hass, entry, runtime):
        super().__init__(
            hass,
            entry,
            runtime,
            SensorEntityDescription(
                key="event_count",
                translation_key="event_count",
                icon="mdi:counter",
            ),
        )

    @property
    def native_value(self) -> int:
        return self._runtime.event_count

    def _restore_from_state(self, state, attrs):
        try:
            self._runtime.event_count = max(self._runtime.event_count, int(state))
        except (TypeError, ValueError):
            pass
