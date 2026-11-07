"""雷神加速器 - 配置流程（短信验证码登录 / Token 登录）。"""

from __future__ import annotations

import logging
import re
from typing import Any

import voluptuous as vol

from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .api import (
    LeishenAuthError,
    LeishenClient,
    LeishenError,
    LeishenSmsError,
)
from .const import (
    CONF_MOBILE,
    CONF_PING_TARGET,
    CONF_SMSCODE,
    CONF_TOKEN,
    DEFAULT_PING_TARGET,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

MOBILE_RE = re.compile(r"^\d{6,15}$")
CODE_RE = re.compile(r"^\d{4,8}$")

PHONE_SCHEMA = vol.Schema(
    {
        vol.Required(CONF_MOBILE): str,
        vol.Optional("country_code", default="86"): str,
    }
)

SMSCODE_SCHEMA = vol.Schema({vol.Required(CONF_SMSCODE): str})

TOKEN_SCHEMA = vol.Schema({vol.Required(CONF_TOKEN): str})


class LeishenConfigFlow(ConfigFlow, domain=DOMAIN):
    """配置流程。"""

    VERSION = 1

    def __init__(self) -> None:
        self._mobile: str = ""
        self._country: str = "86"
        self._smscode_key: str = ""
        self._is_reauth: bool = False

    # ── 入口：选择登录方式 ──────────────────────────────────────
    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="user",
            menu_options=["sms_phone", "token"],
            description_placeholders={"url": "https://www.leigod.com/"},
        )

    # ── 短信登录：第一步 手机号 ────────────────────────────────
    async def async_step_sms_phone(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            mobile = str(user_input[CONF_MOBILE]).strip()
            country = str(user_input.get("country_code", "86")).strip() or "86"

            if not MOBILE_RE.match(mobile):
                errors["base"] = "invalid_mobile"
            else:
                session = async_get_clientsession(self.hass)
                client = LeishenClient(session)
                try:
                    key = await client.async_send_sms(mobile, country)
                except LeishenSmsError as err:
                    _LOGGER.warning("发送短信验证码失败: %s", err)
                    errors["base"] = "sms_send_failed"
                except LeishenError as err:
                    _LOGGER.warning("发送短信验证码异常: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    self._mobile = mobile
                    self._country = country
                    self._smscode_key = key
                    return await self.async_step_sms_code()

        return self.async_show_form(
            step_id="sms_phone",
            data_schema=PHONE_SCHEMA,
            errors=errors,
        )

    # ── 短信登录：第二步 验证码 ────────────────────────────────
    async def async_step_sms_code(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            smscode = str(user_input[CONF_SMSCODE]).strip()
            if not CODE_RE.match(smscode):
                errors["base"] = "invalid_code"
            else:
                session = async_get_clientsession(self.hass)
                client = LeishenClient(session)
                try:
                    token = await client.async_login_by_sms(
                        self._mobile, smscode, self._smscode_key, self._country
                    )
                    client.update_token(token)
                    info = await client.async_get_info()
                except LeishenSmsError as err:
                    _LOGGER.warning("短信验证码登录失败: %s", err)
                    errors["base"] = "invalid_code"
                except LeishenAuthError as err:
                    _LOGGER.warning("登录后拉取账号信息鉴权失败: %s", err)
                    errors["base"] = "invalid_auth"
                except LeishenError as err:
                    _LOGGER.warning("短信验证码登录异常: %s", err)
                    errors["base"] = "cannot_connect"
                else:
                    return await self._finish(token, info)

        return self.async_show_form(
            step_id="sms_code",
            data_schema=SMSCODE_SCHEMA,
            errors=errors,
            description_placeholders={"mobile": self._mobile},
        )

    # ── Token 登录（备用）──────────────────────────────────────
    async def async_step_token(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}

        if user_input is not None:
            token = str(user_input[CONF_TOKEN]).strip()
            session = async_get_clientsession(self.hass)
            client = LeishenClient(session, token)
            try:
                info = await client.async_get_info()
            except LeishenAuthError:
                errors["base"] = "invalid_auth"
            except LeishenError:
                errors["base"] = "cannot_connect"
            else:
                return await self._finish(token, info)

        return self.async_show_form(
            step_id="token",
            data_schema=TOKEN_SCHEMA,
            errors=errors,
            description_placeholders={"url": "https://www.leigod.com/"},
        )

    # ── 收尾：创建或更新 entry ─────────────────────────────────
    async def _finish(self, token: str, info: dict[str, Any]) -> ConfigFlowResult:
        nickname = info.get("nickname") or "雷神加速器"

        if self._is_reauth:
            entry: ConfigEntry | None = self.hass.config_entries.async_get_entry(
                self.context["entry_id"]
            )
            if entry is not None:
                self.hass.config_entries.async_update_entry(
                    entry, data={**entry.data, CONF_TOKEN: token}
                )
            return self.async_abort(reason="reauth_successful")

        uid = str(
            info.get("user_id")
            or info.get("account_id")
            or info.get("mobile")
            or self._mobile
        )
        if uid:
            await self.async_set_unique_id(uid)
            self._abort_if_unique_id_configured()
        return self.async_create_entry(
            title=f"雷神加速器（{nickname}）",
            data={CONF_TOKEN: token, CONF_MOBILE: self._mobile},
        )

    # ── 重新认证 ───────────────────────────────────────────────
    async def async_step_reauth(
        self, entry_data: dict[str, Any]
    ) -> ConfigFlowResult:
        self._is_reauth = True
        return await self.async_step_reauth_menu()

    async def async_step_reauth_menu(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        return self.async_show_menu(
            step_id="reauth_menu",
            menu_options=["sms_phone", "token"],
        )

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> OptionsFlow:
        return LeishenOptionsFlow()


class LeishenOptionsFlow(OptionsFlow):
    """选项：配置延时探测目标。"""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        current = self.config_entry.options.get(
            CONF_PING_TARGET, DEFAULT_PING_TARGET
        )
        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {vol.Optional(CONF_PING_TARGET, default=current): str}
            ),
        )
