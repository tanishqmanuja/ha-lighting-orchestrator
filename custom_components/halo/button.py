"""Resync button: re-apply requested mood to clear manual 'custom' drift."""
from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    area = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HaloResyncButton(area)])


class HaloResyncButton(ButtonEntity):
    _attr_has_entity_name = True

    def __init__(self, area) -> None:
        self._area = area

    @property
    def unique_id(self) -> str:
        return f"{self._area.area_key}_resync"

    @property
    def name(self) -> str:
        return "Resync"

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._area.area_key)},
            name=f"HALO {self._area.area_name}",
        )

    async def async_press(self) -> None:
        await self._area.async_resync()
