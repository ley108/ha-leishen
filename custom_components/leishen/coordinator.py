"""雷神加速器 - 数据协调器。"""

from __future__ import annotations

import logging
from datetime import timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import LeishenAuthError, LeishenClient, LeishenError
from .const import DEFAULT_SCAN_INTERVAL, DOMAIN

_LOGGER = logging.getLogger(__name__)


class LeishenCoordinator(DataUpdateCoordinator[dict[str, Any]]):
    """轮询 /api/user/info。"""

    config_entry: ConfigEntry

    def __init__(self, hass: HomeAssistant, client: LeishenClient) -> None:
        super().__init__(
            hass,
            _LOGGER,
            name=DOMAIN,
            update_interval=timedelta(seconds=DEFAULT_SCAN_INTERVAL),
        )
        self.client = client

    async def _async_update_data(self) -> dict[str, Any]:
        try:
            return await self.client.async_get_info()
        except LeishenAuthError as err:
            # 让 config entry 进入需要重新认证的状态
            self.config_entry.async_start_reauth(self.hass)
            raise UpdateFailed(f"登录态失效: {err}") from err
        except LeishenError as err:
            raise UpdateFailed(str(err)) from err
