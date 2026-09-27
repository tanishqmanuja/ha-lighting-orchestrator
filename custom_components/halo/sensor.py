"""Read-only truth: active mood / preset / status (active|transitioning|custom)."""
from __future__ import annotations

from homeassistant.components.sensor import SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    area = hass.data[DOMAIN][entry.entry_id]
    async_add_entities(
        [HaloActiveMoodSensor(area), HaloActivePresetSensor(area), HaloStatusSensor(area)]
    )


class _Base(SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, area) -> None:
        self._area = area

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._area.area_key)},
            name=f"HALO {self._area.area_name}",
        )

    async def async_added_to_hass(self) -> None:
        self._area.register_refresh(
            lambda: self.async_write_ha_state() if self.hass else None
        )


class HaloActiveMoodSensor(_Base):
    @property
    def unique_id(self) -> str:
        return f"{self._area.area_key}_active_mood"

    @property
    def name(self) -> str:
        return "Active mood"

    @property
    def native_value(self) -> str:
        return self._area.engine.active_mood

    @property
    def extra_state_attributes(self):
        e = self._area.engine
        return {
            "requested_mood": e.requested_mood,
            "requested_preset": e.requested_preset,
            "status": e.status,
        }


class HaloActivePresetSensor(_Base):
    @property
    def unique_id(self) -> str:
        return f"{self._area.area_key}_active_preset"

    @property
    def name(self) -> str:
        return "Active preset"

    @property
    def native_value(self) -> str:
        return self._area.engine.active_preset


class HaloStatusSensor(_Base):
    @property
    def unique_id(self) -> str:
        return f"{self._area.area_key}_status"

    @property
    def name(self) -> str:
        return "Status"

    @property
    def native_value(self) -> str:
        return self._area.engine.status

    @property
    def extra_state_attributes(self):
        e = self._area.engine
        mapping: dict[str, dict[str, str]] = {}
        for (mood, preset), target in sorted(e.targets.items()):
            mapping.setdefault(mood, {})[preset] = target.get("action", "")
        return {
            "active_mood": e.active_mood,
            "active_preset": e.active_preset,
            "requested_mood": e.requested_mood,
            "requested_preset": e.requested_preset,
            "mismatched_entities": e.mismatched,
            # What each preset actually triggers (scene.* / script.*).
            # The panel renders this; native HA cannot.
            "mapping": mapping,
            # Designated default preset per mood (bare mood requests
            # resolve here). The panel marks it on the preset buttons.
            "default_presets": dict(e.defaults),
            # Friendly area name (config entry); the panel shows it as the
            # card title with the area key as subtitle.
            "area_name": self._area.area_name,
        }
