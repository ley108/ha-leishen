"""雷神加速器 - 传感器。"""

from __future__ import annotations

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LeishenConfigEntry
from .api import LeishenClient
from .const import DOMAIN
from .coordinator import LeishenCoordinator

# 账号信息接口里代表「剩余秒数」的字段，按优先级依次尝试
REMAIN_KEYS = ("expiry_time_samp", "user_pause_time")


async def async_setup_entry(
    hass: HomeAssistant,
    entry: LeishenConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    coordinator = entry.runtime_data.coordinator
    async_add_entities(
        [
            LeishenStatusSensor(coordinator, entry),
            LeishenRemainSensor(coordinator, entry),
        ]
    )


class _LeishenBaseSensor(CoordinatorEntity[LeishenCoordinator], SensorEntity):
    _attr_has_entity_name = True

    def __init__(self, coordinator: LeishenCoordinator, entry: LeishenConfigEntry) -> None:
        super().__init__(coordinator)
        self._entry = entry
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, entry.entry_id)},
            name="雷神加速器",
            manufacturer="雷神（leigod）",
            model="云账号",
        )


class LeishenStatusSensor(_LeishenBaseSensor):
    """账号当前状态：计时中 / 已暂停。"""

    _attr_name = "状态"
    _attr_icon = "mdi:account-clock"

    def __init__(self, coordinator: LeishenCoordinator, entry: LeishenConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_object_id = f"{DOMAIN}_status"
        self._attr_unique_id = f"{DOMAIN}_status_{entry.entry_id}"

    @property
    def native_value(self) -> str | None:
        info = self.coordinator.data or {}
        if LeishenClient.is_paused(info):
            return "已暂停"
        return "计时中"


class LeishenRemainSensor(_LeishenBaseSensor):
    """剩余可用时长（小时）。"""

    _attr_name = "剩余时长"
    _attr_icon = "mdi:timer-sand"
    _attr_native_unit_of_measurement = "h"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator: LeishenCoordinator, entry: LeishenConfigEntry) -> None:
        super().__init__(coordinator, entry)
        self._attr_object_id = f"{DOMAIN}_remaining"
        self._attr_unique_id = f"{DOMAIN}_remain_{entry.entry_id}"

    @property
    def native_value(self) -> float | None:
        info = self.coordinator.data or {}
        for key in REMAIN_KEYS:
            if key in info and info[key] is not None:
                try:
                    value = float(info[key])
                except (TypeError, ValueError):
                    continue
                # 接口给的是秒，换算成小时
                return round(value / 3600, 1)
        return None
