"""Single source of input: mood + preset selects per area."""
from __future__ import annotations

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, PRESET_NONE


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    area = hass.data[DOMAIN][entry.entry_id]
    async_add_entities([HaloMoodSelect(area), HaloPresetSelect(area)])


class _Base:
    _attr_has_entity_name = True

    def __init__(self, area) -> None:
        self._area = area

    @property
    def device_info(self) -> DeviceInfo:
        return DeviceInfo(
            identifiers={(DOMAIN, self._area.area_key)},
            name=f"HALO {self._area.area_name}",
            manufacturer="HALO",
            model="Lighting Orchestrator",
        )

    def _refresh_cb(self) -> None:
        try:
            self.async_write_ha_state()
        except Exception:  # noqa: BLE001
            pass

    async def async_added_to_hass(self) -> None:
        self._area.register_refresh(self._refresh_cb)


class HaloMoodSelect(_Base, SelectEntity):
    _attr_translation_key = "mood"

    @property
    def unique_id(self) -> str:
        return f"{self._area.area_key}_mood"

    @property
    def name(self) -> str:
        return "Mood"

    @property
    def options(self) -> list[str]:
        moods = sorted({m for (m, _p) in self._area.engine.targets})
        return moods or ["default"]

    @property
    def current_option(self) -> str | None:
        return self._area.engine.requested_mood or (self.options[0] if self.options else None)

    async def async_select_option(self, option: str) -> None:
        engine = self._area.engine
        # Keep the current preset when the new mood has it, else fall back
        # to that mood's designated default (usually "default").
        preset = engine.resolve_preset(option, engine.requested_preset)
        if (option, preset) not in engine.targets:
            preset = engine.default_preset_for(option)
        await self._area.async_request(option, preset, via="select")


class HaloPresetSelect(_Base, SelectEntity):
    _attr_translation_key = "preset"

    @property
    def unique_id(self) -> str:
        return f"{self._area.area_key}_preset"

    @property
    def name(self) -> str:
        return "Preset"

    @property
    def options(self) -> list[str]:
        mood = self._area.engine.requested_mood
        if not mood:
            moods = sorted({m for (m, _p) in self._area.engine.targets})
            mood = moods[0] if moods else "default"
        return self._area.engine.presets_for_mood(mood)

    @property
    def current_option(self) -> str | None:
        engine = self._area.engine
        mood = engine.requested_mood
        preset = engine.requested_preset
        if preset in self.options:
            return preset
        # Unset/foreign preset: show what a bare request would resolve to.
        if mood:
            return engine.resolve_preset(mood, preset)
        return self.options[0] if self.options else PRESET_NONE

    async def async_select_option(self, option: str) -> None:
        mood = self._area.engine.requested_mood
        if not mood:
            moods = sorted({m for (m, _p) in self._area.engine.targets})
            mood = moods[0]
        await self._area.async_request(mood, option, via="select")
