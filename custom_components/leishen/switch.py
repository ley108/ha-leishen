"""雷神加速器 - 加速开关。"""

from __future__ import annotations

import logging

from homeassistant.components.switch import SwitchEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LeishenConfigEntry
from .api import LeishenClient, LeishenError
from .const import DOMAIN
from .coordinator import LeishenCoordinator

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeishenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    runtime = entry.runtime_data
    async_add_entities(
        [LeishenAccelerateSwitch(runtime.coordinator, runtime.client, entry)]
    )


class LeishenAccelerateSwitch(CoordinatorEntity[LeishenCoordinator], SwitchEntity):
    """开 = 计时中（recover），关 = 已暂停（pause）。"""

    _attr_has_entity_name = True
    _attr_name = "加速"
    _attr_icon = "mdi:rocket-launch"

    def __init__(
        self,
        coordinator: LeishenCoordinator,
        client: LeishenClient,
        entry: LeishenConfigEntry,
    ) -> None:
        super().__init__(coordinator)
        self._client = client
        self._attr_object_id = f"{DOMAIN}_accelerate"
        self._attr_unique_id = f"{DOMAIN}_accelerate_{entry.entry_id}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="雷神加速器",
            manufacturer="雷神（leigod）",
            model="云账号",
        )

    @property
    def is_on(self) -> bool:
        return not LeishenClient.is_paused(self.coordinator.data or {})

    @property
    def extra_state_attributes(self) -> dict:
        info = self.coordinator.data or {}
        return {
            "pause_status": info.get("pause_status"),
            "pause_status_id": info.get("pause_status_id"),
            "nickname": info.get("nickname"),
        }

    async def async_turn_on(self, **kwargs) -> None:
        """恢复加速计时。"""
        try:
            await self._client.async_recover()
        except LeishenError as err:
            _LOGGER.error("恢复加速失败: %s", err)
            raise
        await self.coordinator.async_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """暂停加速计时。"""
        try:
            await self._client.async_pause()
        except LeishenError as err:
            _LOGGER.error("暂停加速失败: %s", err)
            raise
        await self.coordinator.async_refresh()
