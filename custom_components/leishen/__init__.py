"""雷神加速器集成入口。"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import LeishenClient
from .const import CONF_TOKEN, DOMAIN
from .coordinator import LeishenCoordinator

_LOGGER = logging.getLogger(__name__)

PLATFORMS = ["switch", "sensor"]


@dataclass
class LeishenRuntimeData:
    """运行时数据。"""

    client: LeishenClient
    coordinator: LeishenCoordinator


type LeishenConfigEntry = ConfigEntry[LeishenRuntimeData]


async def async_setup_entry(hass: HomeAssistant, entry: LeishenConfigEntry) -> bool:
    """建立 config entry。"""
    session = async_get_clientsession(hass)
    client = LeishenClient(session, entry.data[CONF_TOKEN])

    coordinator = LeishenCoordinator(hass, client)
    coordinator.config_entry = entry
    await coordinator.async_config_entry_first_refresh()

    entry.runtime_data = LeishenRuntimeData(client=client, coordinator=coordinator)

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))
    return True


async def async_unload_entry(hass: HomeAssistant, entry: LeishenConfigEntry) -> bool:
    """卸载 config entry。"""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass: HomeAssistant, entry: LeishenConfigEntry) -> None:
    """重新加载。"""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_update_listener(
    hass: HomeAssistant, entry: LeishenConfigEntry
) -> None:
    """配置更新后重新加载。"""
    await hass.config_entries.async_reload(entry.entry_id)
