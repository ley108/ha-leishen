"""雷神加速器集成常量。"""

DOMAIN = "leishen"

CONF_TOKEN = "account_token"

API_BASE = "https://webapi.leigod.com"
EP_INFO = "/api/user/info"
EP_PAUSE = "/api/user/pause"
EP_RECOVER = "/api/user/recover"
EP_TIME_LOG = "/api/user/time/log"

# 短信验证码登录
EP_SMS_SEND = "/tools/smscode"
EP_LOGIN_CODE = "/api/auth/login/code"

CONF_MOBILE = "mobile_num"
CONF_COUNTRY_CODE = "country_code"
CONF_SMSCODE = "smscode"

# 延时探测目标（ICMP），可在集成"选项"里修改
CONF_PING_TARGET = "ping_target"
DEFAULT_PING_TARGET = "www.baidu.com:443"

DEFAULT_SCAN_INTERVAL = 300  # 秒

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json, text/plain, */*",
    "Referer": "https://www.leigod.com/",
}

# 雷神接口返回码
CODE_OK = 0
CODE_TOKEN_INVALID = 400006      # 账号未登录 / token 失效
CODE_SESSION_EXPIRED = 400007     # 登录态过期
CODE_ALREADY_PAUSED = 400803      # 已处于暂停状态，无需重复操作

# token 失效时需要在 UI 重新认证
AUTH_ERROR_CODES = {CODE_TOKEN_INVALID, CODE_SESSION_EXPIRED}
BENIGN_CODES = {CODE_ALREADY_PAUSED}
