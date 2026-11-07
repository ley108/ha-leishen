"""雷神加速器 Web API 客户端。"""

from __future__ import annotations

import logging
from typing import Any

import aiohttp

from .const import (
    API_BASE,
    AUTH_ERROR_CODES,
    CODE_OK,
    EP_INFO,
    EP_LOGIN_CODE,
    EP_PAUSE,
    EP_RECOVER,
    EP_SMS_SEND,
    EP_TIME_LOG,
    HEADERS,
)

_LOGGER = logging.getLogger(__name__)

TIMEOUT = aiohttp.ClientTimeout(total=20)


class LeishenError(Exception):
    """基础异常。"""


class LeishenAuthError(LeishenError):
    """token 无效或已过期。"""


class LeishenApiError(LeishenError):
    """接口返回业务错误。"""


class LeishenSmsError(LeishenApiError):
    """短信验证码相关错误。"""


def _extract_token(data: Any) -> str | None:
    """从登录返回里挖出 account_token，兼容几种嵌套。"""
    if not isinstance(data, dict):
        return None
    if isinstance(data.get("login_info"), dict):
        token = data["login_info"].get("account_token")
        if token:
            return str(token)
    for key in ("account_token", "token", "access_token"):
        if data.get(key):
            return str(data[key])
    return None


class LeishenClient:
    """雷神接口封装。"""

    def __init__(self, session: aiohttp.ClientSession, token: str = "") -> None:
        self._session = session
        self._token = token

    @property
    def token(self) -> str:
        return self._token

    def update_token(self, token: str) -> None:
        self._token = token

    # ── 底层请求 ────────────────────────────────────────────────
    async def _post_raw(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        """不带鉴权头的原始 POST，返回完整 body。"""
        url = f"{API_BASE}{path}"
        try:
            async with self._session.post(
                url, json=payload, headers=HEADERS, timeout=TIMEOUT
            ) as resp:
                if resp.status == 404:
                    raise LeishenApiError(f"接口不存在: {path}")
                if resp.status == 403:
                    raise LeishenApiError("请求过于频繁，稍后再试")
                body = await resp.json(content_type=None)
        except aiohttp.ClientError as err:
            raise LeishenError(f"网络请求失败: {err}") from err
        except ValueError as err:
            raise LeishenError("接口返回内容无法解析") from err
        return body if isinstance(body, dict) else {}

    async def _request(
        self,
        path: str,
        extra: dict[str, Any] | None = None,
        allow_codes: frozenset[int] | set[int] = frozenset(),
    ) -> dict[str, Any]:
        """带 account_token 的业务请求，直接返回 data。"""
        payload: dict[str, Any] = {
            "account_token": self._token,
            "lang": "zh_CN",
            "os_type": 4,
            "region_code": 1,
            "src_channel": "guanwang",
        }
        if extra:
            payload.update(extra)

        body = await self._post_raw(path, payload)
        code = body.get("code", -1)
        if code in AUTH_ERROR_CODES:
            raise LeishenAuthError(body.get("msg") or "登录态失效，请重新登录")
        if code != CODE_OK and code not in allow_codes:
            raise LeishenApiError(f"{body.get('msg', '未知错误')}（code {code}）")
        return body.get("data") or {}

    # ── 短信登录 ────────────────────────────────────────────────
    async def async_send_sms(self, mobile_num: str, country_code: str = "86") -> str:
        """发送短信验证码，返回 smscode_key。"""
        body = await self._post_raw(
            EP_SMS_SEND,
            {
                "phone": mobile_num,
                "country_code": str(country_code),
                "lang": "zh_CN",
                "region_code": 1,
                "src_channel": "guanwang",
            },
        )
        code = body.get("code", -1)
        if code != CODE_OK:
            raise LeishenSmsError(f"{body.get('msg', '短信发送失败')}（code {code}）")

        data = body.get("data")
        key = None
        if isinstance(data, dict):
            for k in ("smscode_key", "sms_code_key", "smscodeKey", "key"):
                if data.get(k):
                    key = str(data[k])
                    break
        elif isinstance(data, str):
            key = data
        if not key:
            _LOGGER.error("短信接口未返回 smscode_key，原始返回: %s", body)
            raise LeishenSmsError("短信接口未返回验证码标识")
        return key

    async def async_login_by_sms(
        self, mobile_num: str, smscode: str, smscode_key: str, country_code: str = "86"
    ) -> str:
        """用短信验证码登录，返回 account_token。"""
        body = await self._post_raw(
            EP_LOGIN_CODE,
            {
                "mobile_num": mobile_num,
                "country_code": str(country_code),
                "smscode": str(smscode),
                "smscode_key": smscode_key,
                "lang": "zh_CN",
                "region_code": 1,
                "src_channel": "guanwang",
                "user_type": "0",
            },
        )
        code = body.get("code", -1)
        if code != CODE_OK:
            raise LeishenSmsError(f"{body.get('msg', '登录失败')}（code {code}）")
        token = _extract_token(body.get("data"))
        if not token:
            _LOGGER.error("登录接口未返回 account_token，原始返回: %s", body)
            raise LeishenSmsError("登录成功但未拿到 token")
        return token

    # ── 业务接口 ────────────────────────────────────────────────
    async def async_get_info(self) -> dict[str, Any]:
        return await self._request(EP_INFO)

    async def async_pause(self) -> dict[str, Any]:
        # 400803 = 本来就已经暂停，视为幂等成功
        return await self._request(EP_PAUSE, allow_codes={400803})

    async def async_recover(self) -> dict[str, Any]:
        return await self._request(EP_RECOVER, allow_codes={400803})

    async def async_time_log(self) -> dict[str, Any]:
        return await self._request(EP_TIME_LOG, {"page": 1, "size": 5})

    @staticmethod
    def is_paused(info: dict[str, Any]) -> bool:
        """pause_status_id: 1 = 已暂停, 0 = 计时中。"""
        try:
            return int(info.get("pause_status_id", 0)) == 1
        except (TypeError, ValueError):
            return False
