"""
推送文案的语言表。默认英文，改 config.yaml 的 `app.locale: zh` 切成中文。
"""

from __future__ import annotations

from typing import Any

STRINGS: dict[str, dict[str, Any]] = {
    "en": {
        # ---- 条目标签 ----
        "remaining": "Remaining",
        "room": "Room",
        "report_title": "{room} Electricity · {balance}",
        "read_at": "Checked at",
        "last_check": "Last check",
        "change": "Change",
        "daily_avg": "Daily average",
        "runs_for": "Runs for",
        "latest_bill": "Latest bill",
        "past_bills": "Past bills",
        "blog": "Blog",
        # ---- 值的补充说明 ----
        "consumed": "consumed",
        "topped_up": "topped up",
        "no_change": "no change",
        "server_history": "server history",
        "local_readings": "local readings",
        "average_of": "{start}–{end} average",
        "until": "until {date}",
        "interval": "{gap} earlier",
        "unit_seconds": "{value}s",
        "unit_minutes": "{value}min",
        "unit_hours": "{value}h",
        "unit_days": "{value}d",
        # ---- 趋势 ----
        "usage_trend": "Usage trend",
        "server_not_live": "server data, not live",
        "avg_per_day": "avg {value} kWh/day",
        "latest_month": "latest {value} kWh",
        "usage_of": "{span} usage",
        "source_suffix": "kWh · {source}",
        # ---- 标题 ----
        "subject_daily": "Daily reading",
        "subject_update": "Update",
        "subject_alert": "Alert",
        "subject_fmt": "{kind} · {bal} · {room}",
        # ---- 告警 ----
        "alert_exhausted": "Balance exhausted",
        "alert_low": "Low balance: {bal} kWh",
        "alert_runout": "About {days} days left (until {date})",
        "alert_spike": "Unusual usage yesterday: {used} kWh (recent average {avg})",
        "alert_silent": "No new reading for {days} days, check the fetch",
        "alert_unpaid": "{count} unpaid bill(s), {money} in total",
        # ---- 其它 ----
        "fail_subject": "Electricity check failed",
        "test_subject": "Test push · read at {ts}",
        "test_note": "(test push, using the last stored reading {ts}; nothing was fetched)",
        "test_empty": "Test push. If you received this, the channel works.",
        "bill_name": "{year}-{month} electricity bill",
        "server_average": "server average",
        "wrap": " ({text})",
        "html_lang": "en",
        "html_title": "CityUHK (DG)",
        "html_room": "Dorm",
        "alert_box_title": "Heads up",
        "past_label": "past",
        "mock_note": "Sample data (provider.type = mock)",
        "amount": "Amount",
        "money_sep": " ",
        "unit_day": "days",
        "err_no_steps": "provider.http.steps 为空。把抓包得到的请求填进 config.yaml 再用。",
        "err_step_no_url": "第 {idx} 个 step 缺少 url",
        "err_login_conf": "auth.mode = login，但没配 auth.login",
        "err_sso_conf": "auth.mode = sso，但没配 auth.sso.info_url",
        "err_pw_conf": "auth.mode = password，但没配 auth.password.idp",
        "err_no_sso_info": "缺少 SSO 信息接口（auth.sso.info_url / auth.password.sso.info_url）",
        "err_sso_info_fail": "获取 SSO 授权地址失败：{exc}",
        "err_no_sso_url": "SSO 信息接口没返回授权地址",
        "err_sso_req_fail": "SSO 授权请求失败：{exc}",
        "err_2fa": "统一身份认证要求二次认证（2FA），这个会话不完整",
        "err_session_invalid": "统一身份认证会话无效（没拿到 code）。检查账号密码或 IDP_COOKIE",
        "err_no_token_url": "缺少 auth.*.sso.token_url",
        "err_code_exchange": "用 code 换 token 失败：{exc}",
        "err_token_exchange": "换 token 失败：{reason}",
        "err_no_token_text": "响应里没有 token",
        "err_clientid_fail": "获取 IdP clientId 失败：{exc}",
        "err_no_clientid": "IdP 没返回 clientId",
        "err_pw_req_fail": "密码登录请求失败：{exc}",
        "err_pw_fail": "密码登录失败：{reason}",
        "err_cookie_empty": "auth.mode = sso，但 IDP_COOKIE 为空。改用 auth.mode = password 更省事",
        "err_cookie_bearer": "IDP_COOKIE 里填的是 Authorization 的 Bearer token，不是 Cookie。要的是 `Cookie: xxx=yyy; aaa=bbb` 那种带分号的整行",
        "err_cookie_format": "IDP_COOKIE 格式不对，里面没有 `名字=值`。应该是 `SESSION=xxxx; JSESSIONID=yyyy`",
        "err_pw_creds_empty": "auth.mode = password，但 EPAY_ACCOUNT / EPAY_PASSWORD 为空",
        "err_login_no_url": "auth.login 缺少 url",
        "err_login_req_fail": "登录请求失败：{exc}",
        "err_login_http": "登录 HTTP {code}",
        "err_login_fail": "登录失败：{reason}",
        "err_token_empty": "auth.mode = token，但 token 为空。浏览器 F12 复制 authorization 里的 uuid，然后运行 python run.py token",
        "err_sso_no_cookie": "auth.mode = sso，但没有 IDP_COOKIE。改用 auth.mode = password 更省事",
        "err_401": "鉴权失败（401）。token 过期且自动重登没成功，检查 auth 配置，或手动执行 python run.py login。",
        "err_step_req_fail": "[{name}] 请求失败：{exc}",
        "fail_body": "The electricity check failed.\n\nReason: {message}\nTime: {when}\n{hint}\nOther common causes: the campus network is unreachable, or the API fields changed. Run `python run.py probe` in the project directory to see the raw response.",
        "fail_hint_cookie": "\nFix: log in at idp.cityu-dg.edu.cn in a browser → F12 → Network → copy the Cookie → update IDP_COOKIE in .env → run python run.py login\n",
        "fail_hint_token": "\nFix: run python run.py token to get a new token\n",
        "label_pad": 14,
        "sep": ": ",
    },
    "zh": {
        # ---- 条目标签 ----
        "remaining": "剩余电量",
        "room": "宿舍号码",
        "report_title": "{room} 电量查询 · {balance}",
        "read_at": "查询时间",
        "last_check": "上次查询",
        "change": "电量变动",
        "daily_avg": "日均用电",
        "runs_for": "预计可用",
        "latest_bill": "最新账单",
        "past_bills": "往期账单",
        "blog": "博客",
        # ---- 值的补充说明 ----
        "consumed": "消耗",
        "topped_up": "充值",
        "no_change": "无变化",
        "server_history": "服务端历史",
        "local_readings": "本地读数",
        "average_of": "{start}–{end} 均值",
        "until": "约 {date}",
        "interval": "间隔 {gap}",
        "unit_seconds": "{value}秒",
        "unit_minutes": "{value}分钟",
        "unit_hours": "{value}小时",
        "unit_days": "{value}天",
        # ---- 趋势 ----
        "usage_trend": "用电趋势",
        "server_not_live": "服务端数据，非实时",
        "avg_per_day": "均 {value} kWh/天",
        "latest_month": "最新 {value} kWh",
        "usage_of": "{span} 用电",
        "source_suffix": "kWh · {source}",
        # ---- 标题 ----
        "subject_daily": "电量日报",
        "subject_update": "电量更新",
        "subject_alert": "电量告警",
        "subject_fmt": "{kind} · {bal} · {room}",
        # ---- 告警 ----
        "alert_exhausted": "电量已耗尽",
        "alert_low": "剩余电量偏低：{bal} kWh",
        "alert_runout": "预计 {days} 天后耗尽（约 {date}）",
        "alert_spike": "昨日用电异常：{used} kWh（近期均值 {avg}）",
        "alert_silent": "已有 {days} 天没拿到新数据，检查抓取是否失效",
        "alert_unpaid": "有 {count} 张未缴账单，合计 {money}",
        # ---- 其它 ----
        "fail_subject": "电量抓取失败",
        "test_subject": "测试推送 · 读数时间 {ts}",
        "test_note": "（测试推送，数据取自最近一次读数 {ts}，没有重新抓取）",
        "test_empty": "这是一条测试推送。收到说明渠道配置正确。",
        "bill_name": "{year}年{month}月账单电费",
        "server_average": "服务端均值",
        "wrap": "（{text}）",
        "html_lang": "zh-CN",
        "html_title": "香港城市大学（东莞）",
        "html_room": "宿舍",
        "alert_box_title": "需要注意",
        "past_label": "往期",
        "mock_note": "当前为演示数据（provider.type = mock）",
        "amount": "折合金额",
        "money_sep": "　",
        "unit_day": "天",
        "err_no_steps": "provider.http.steps is empty. Put the captured requests into config.yaml first.",
        "err_step_no_url": "step {idx} has no url",
        "err_login_conf": "auth.mode = login, but auth.login is not configured",
        "err_sso_conf": "auth.mode = sso, but auth.sso.info_url is not configured",
        "err_pw_conf": "auth.mode = password, but auth.password.idp is not configured",
        "err_no_sso_info": "Missing the SSO info endpoint (auth.sso.info_url / auth.password.sso.info_url)",
        "err_sso_info_fail": "Could not get the SSO authorize URL: {exc}",
        "err_no_sso_url": "The SSO info endpoint returned no authorize URL",
        "err_sso_req_fail": "SSO authorize request failed: {exc}",
        "err_2fa": "The IdP asked for a second factor; this session is incomplete",
        "err_session_invalid": "The IdP session is no longer valid (no code returned). Check the account, password or IDP_COOKIE",
        "err_no_token_url": "Missing auth.*.sso.token_url",
        "err_code_exchange": "Token exchange failed: {exc}",
        "err_token_exchange": "Token exchange failed: {reason}",
        "err_no_token_text": "no token in the response",
        "err_clientid_fail": "Could not get the IdP clientId: {exc}",
        "err_no_clientid": "The IdP returned no clientId",
        "err_pw_req_fail": "Password sign-in request failed: {exc}",
        "err_pw_fail": "Password sign-in failed: {reason}",
        "err_cookie_empty": "auth.mode = sso, but IDP_COOKIE is empty. auth.mode = password is easier",
        "err_cookie_bearer": "IDP_COOKIE holds an Authorization bearer token, not a cookie. It should be a whole `Cookie: xxx=yyy; aaa=bbb` line",
        "err_cookie_format": "IDP_COOKIE has the wrong format, no `name=value` in it. It should look like `SESSION=xxxx; JSESSIONID=yyyy`",
        "err_pw_creds_empty": "auth.mode = password, but EPAY_ACCOUNT / EPAY_PASSWORD are empty",
        "err_login_no_url": "auth.login has no url",
        "err_login_req_fail": "Sign-in request failed: {exc}",
        "err_login_http": "Sign-in returned HTTP {code}",
        "err_login_fail": "Sign-in failed: {reason}",
        "err_token_empty": "auth.mode = token, but the token is empty. Copy the uuid from the authorization header in the browser, then run python run.py token",
        "err_sso_no_cookie": "auth.mode = sso, but there is no IDP_COOKIE. auth.mode = password is easier",
        "err_401": "Authentication failed (401). The token expired and the automatic re-login did not work either. Check the auth settings, or run python run.py login by hand.",
        "err_step_req_fail": "[{name}] request failed: {exc}",
        "fail_body": "本次抓取宿舍电量失败。\n\n原因：{message}\n时间：{when}\n{hint}\n其他常见原因：校园网不可达 / 接口字段变了。可在项目目录执行 `python run.py probe` 看原始响应。",
        "fail_hint_cookie": "\n修复：浏览器登录 idp.cityu-dg.edu.cn → F12 → Network → 复制 Cookie → 更新 .env 的 IDP_COOKIE → 跑 python run.py login 验证\n",
        "fail_hint_token": "\n修复：python run.py token 换一个新的 token\n",
        "label_pad": 4,
        "sep": "：",
    },
}

# 项目主页，放在报告末尾
LINKS = {
    "github": "https://github.com/zyk121381",
    "blog": "https://www.040426.xyz",
}

_current = "en"


def set_locale(code: str | None) -> str:
    """设置当前语言。认不出来就回落到英文。"""
    global _current
    key = (code or "en").strip().lower()[:2]
    _current = key if key in STRINGS else "en"
    return _current


def t(key: str, **kwargs: Any) -> Any:
    """取一条文案。找不到 key 就回落到英文，再不行就返回 key 本身。"""
    table = STRINGS.get(_current, STRINGS["en"])
    value = table.get(key)
    if value is None:
        value = STRINGS["en"].get(key, key)
    if kwargs and isinstance(value, str):
        return value.format(**kwargs)
    return value
