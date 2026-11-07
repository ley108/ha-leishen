"""雷神加速器 - 传感器。"""

from __future__ import annotations

import asyncio
import logging
import socket
import time
from datetime import timedelta
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorStateClass
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_interval
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import LeishenConfigEntry
from .api import LeishenClient
from .const import CONF_PING_TARGET, DEFAULT_PING_TARGET, DOMAIN
from .coordinator import LeishenCoordinator

_LOGGER = logging.getLogger(__name__)

# 剩余时长在不同接口版本里字段名不一致，按优先级依次尝试
# 账号信息接口返回：expiry_time_samp / user_pause_time 均为「剩余秒数」
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
            LeishenLatencySensor(coordinator, entry),
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

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        info = self.coordinator.data or {}
        return {
            "nickname": info.get("nickname"),
            "pause_status": info.get("pause_status"),
            "vip_level": info.get("vip_level"),
            "remaining_text": info.get("expiry_time"),
            "last_pause_time": info.get("last_pause_time"),
        }


class LeishenRemainSensor(_LeishenBaseSensor):
    """剩余时长（分钟）。字段名不稳定，取不到则显示 unknown。"""

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


def _parse_target(target: str) -> tuple[str, int]:
    """解析 host 或 host:port。"""
    target = (target or "").strip()
    if ":" in target and not target.count(":") > 1:
        host, _, port = target.partition(":")
        try:
            return host.strip(), int(port)
        except ValueError:
            pass
    return target, 443


def _probe_rtt(host: str, port: int, timeout: float = 3.0) -> float | None:
    """TCP 握手计时，近似 RTT（毫秒）。不依赖 ICMP 权限。"""
    start = time.monotonic()
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return round((time.monotonic() - start) * 1000, 1)
    except OSError as err:
        _LOGGER.debug("探测 %s:%s 失败: %s", host, port, err)
        return None


class LeishenLatencySensor(_LeishenBaseSensor):
    """到指定目标的网络延时（ICMP RTT）。"""

    _attr_name = "网络延时"
    _attr_icon = "mdi:speedometer"
    _attr_native_unit_of_measurement = "ms"
    _attr_state_class = SensorStateClass.MEASUREMENT

    def __init__(self, coordinator, entry) -> None:
        super().__init__(coordinator, entry)
        self._attr_object_id = f"{DOMAIN}_latency"
        self._attr_unique_id = f"{DOMAIN}_latency_{entry.entry_id}"
        self._raw_target = entry.options.get(CONF_PING_TARGET) or DEFAULT_PING_TARGET
        self._host, self._port = _parse_target(self._raw_target)

    @property
    def should_poll(self) -> bool:
        return False

    async def async_added_to_hass(self) -> None:
        await super().async_added_to_hass()
        self.async_on_remove(
            async_track_time_interval(
                self.hass, self._async_refresh_latency, timedelta(seconds=60)
            )
        )
        await self._async_refresh_latency()

    async def _async_refresh_latency(self, _now=None) -> None:
        value = await asyncio.to_thread(_probe_rtt, self._host, self._port)
        if value is None:
            _LOGGER.debug("延时探测 %s:%s 无响应", self._host, self._port)
        self._attr_native_value = value
        self.async_write_ha_state()

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        return {"target": f"{self._host}:{self._port}"}
