"""配置驱动的 HTTP 数据源。

请求链写在 config.yaml 的 provider.http.steps 里，字段位置写在 extract 里，
换接口或改字段名不用动 Python。鉴权方式在 auth.mode 里选。
"""

from __future__ import annotations

import json
import os
import re
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import httpx

from ..config import dig, to_float
from ..i18n import t
from ..models import Reading
from .base import Provider, ProviderError

_PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")


def _subst(node: Any, ctx: dict) -> Any:
    if isinstance(node, str):
        whole = _PLACEHOLDER.fullmatch(node.strip())
        if whole:
            # 整个字符串就是一个占位符时，保留原始类型（数字/对象）
            value = dig(ctx, whole.group(1))
            return value if value is not None else ""
        return _PLACEHOLDER.sub(
            lambda m: "" if dig(ctx, m.group(1)) is None else str(dig(ctx, m.group(1))),
            node,
        )
    if isinstance(node, dict):
        return {k: _subst(v, ctx) for k, v in node.items()}
    if isinstance(node, list):
        return [_subst(v, ctx) for v in node]
    return node


def _decode(resp: httpx.Response) -> str:
    """优先按响应头 charset，其次 utf-8，最后回退 gbk（老系统常见）。"""
    raw = resp.content
    for enc in (resp.charset_encoding, "utf-8", "gb18030"):
        if not enc:
            continue
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def _try_json(text: str) -> Any:
    text = text.strip()
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # 兼容 JSONP：callback({...})
    match = re.match(r"^[\w$.]+\s*\((.*)\)\s*;?$", text, re.S)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
    return None


class HttpProvider:
    """按 config.yaml 里描述的请求链抓数据。"""
    name = "http"

    def __init__(self, conf: dict[str, Any]):
        self.conf = conf or {}
        self.timeout = float(self.conf.get("timeout", 20))
        self.verify_ssl = bool(self.conf.get("verify_ssl", True))
        self.base_headers: dict[str, str] = dict(self.conf.get("headers") or {})
        self.cookies: dict[str, str] = dict(self.conf.get("cookies") or {})
        self.steps: list[dict] = list(self.conf.get("steps") or [])
        self.extract: dict[str, Any] = dict(self.conf.get("extract") or {})

        auth = self.conf.get("auth") or {}
        self.auth_mode = str(auth.get("mode", "none")).lower()
        self.static_token = auth.get("token") or ""
        self.token_file = Path(auth["token_file"]) if auth.get("token_file") else None
        self.login_conf: dict = auth.get("login") or {}
        self.sso_conf: dict = auth.get("sso") or {}
        self.password_conf: dict = auth.get("password") or {}
        self._token = ""
        self.token_info: dict[str, Any] = {}

        if not self.steps:
            raise ProviderError(
                str(t("err_no_steps"))
            )
        for idx, step in enumerate(self.steps):
            if not step.get("url"):
                raise ProviderError(str(t("err_step_no_url", idx=idx)))
        if self.auth_mode == "login" and not self.login_conf:
            raise ProviderError(str(t("err_login_conf")))
        if self.auth_mode == "sso" and not self.sso_conf.get("info_url"):
            raise ProviderError(str(t("err_sso_conf")))
        if self.auth_mode == "password" and not (self.password_conf.get("idp") or {}):
            raise ProviderError(str(t("err_pw_conf")))

    @staticmethod
    def _parse_cookie(raw: str) -> dict[str, str]:
        jar: dict[str, str] = {}
        for part in (raw or "").split(";"):
            if "=" not in part:
                continue
            key, _, value = part.partition("=")
            key, value = key.strip(), value.strip()
            if key:
                jar[key] = value
        return jar

    def _sso_exchange(self, cookies: dict[str, str], ctx: dict) -> str:
        """拿着已认证的会话 cookie 走一遍授权，换 onebill token。"""
        conf = self.sso_conf or (self.password_conf.get("sso") or {})
        info_url = str(conf.get("info_url") or "")
        if not info_url:
            raise ProviderError(str(t("err_no_sso_info")))

        try:
            with httpx.Client(timeout=self.timeout, verify=self.verify_ssl) as probe:
                info = probe.get(info_url)
                info.raise_for_status()
                sso_url = dig(_try_json(_decode(info)), str(conf.get("info_field", "data.ssoUrl")))
        except httpx.HTTPError as exc:
            raise ProviderError(str(t("err_sso_info_fail", exc=exc))) from exc
        if not sso_url:
            raise ProviderError(str(t("err_no_sso_url")))

        code, last_url = "", ""
        with httpx.Client(
            timeout=self.timeout,
            verify=self.verify_ssl,
            follow_redirects=False,
            cookies=cookies,
        ) as browserish:
            url = str(sso_url)
            for _ in range(6):
                try:
                    resp = browserish.get(url)
                except httpx.HTTPError as exc:
                    raise ProviderError(str(t("err_sso_req_fail", exc=exc))) from exc
                location = resp.headers.get("location")
                if not location:
                    break
                url = str(httpx.URL(url).join(location))
                last_url = url
                params = httpx.URL(url).params
                if "code" in params:
                    code = params["code"]
                    break

        if not code:
            if "second/auth" in last_url:
                raise ProviderError(str(t("err_2fa")))
            raise ProviderError(
                str(t("err_session_invalid"))
            )

        token_url = str(conf.get("token_url") or "")
        if not token_url:
            raise ProviderError(str(t("err_no_token_url")))
        try:
            with httpx.Client(timeout=self.timeout, verify=self.verify_ssl) as poster:
                resp = poster.post(token_url, json={"code": code})
                body = _try_json(_decode(resp))
        except httpx.HTTPError as exc:
            raise ProviderError(str(t("err_code_exchange", exc=exc))) from exc

        token = dig(body, str(conf.get("token_path", "data.token")))
        if not token:
            reason = dig(body, "msg") or dig(body, "message") or ""
            raise ProviderError(str(t("err_token_exchange", reason=reason or t("err_no_token_text"))), detail=body)

        self._token = str(token)
        self._write_cache(self._token)
        ctx["token"] = self._token
        return self._token

    def _sso_login(self, client: httpx.Client, ctx: dict) -> str:
        """用 IDP_COOKIE 换 token。cookie 必须是"完全认证"的会话。"""
        cookie = str(self.sso_conf.get("cookie") or "").strip()

        if not cookie:
            raise ProviderError(
                str(t("err_cookie_empty"))
            )
        if cookie.lower().startswith("bearer ") or cookie.startswith("eyJ"):
            raise ProviderError(
                str(t("err_cookie_bearer"))
            )
        if "=" not in cookie:
            raise ProviderError(
                str(t("err_cookie_format"))
            )
        return self._sso_exchange(self._parse_cookie(cookie), ctx)

    def _password_login(self, client: httpx.Client, ctx: dict) -> str:
        """学号密码 → IdP access_token → SSO code → onebill token。"""
        conf = self.password_conf
        idp = conf.get("idp") or {}
        account = str(conf.get("account") or "")
        secret = str(conf.get("secret") or "")
        if not account or not secret:
            raise ProviderError(
                str(t("err_pw_creds_empty"))
            )

        headers = {
            "accept": "application/json, text/plain, */*",
            "content-type": "application/json",
            "origin": str(idp.get("origin") or "https://idp.cityu-dg.edu.cn"),
            "referer": str(idp.get("origin") or "https://idp.cityu-dg.edu.cn")
            + "/frontend/login/",
        }

        try:
            info = client.get(str(idp["login_data"]), headers=headers)
            login_data = _try_json(_decode(info)) or {}
            client_id = dig(login_data, "data.clientId") or ""
        except httpx.HTTPError as exc:
            raise ProviderError(str(t("err_clientid_fail", exc=exc))) from exc
        if not client_id:
            raise ProviderError(str(t("err_no_clientid")), detail=login_data)

        sm2_code = ""
        try:
            init = client.get(str(idp["init_code"]), headers=headers)
            sm2_code = dig(_try_json(_decode(init)), "data.code") or ""
        except httpx.HTTPError:
            pass

        payload = {
            "client_id": client_id,
            "grant_type": "password",
            "scope": "read",
            "username": account,
            "password": secret,
            "_enterprise_id": "",
            "sm2_code": sm2_code,
            "auto_login": False,
        }
        try:
            resp = client.post(str(idp["token"]), json=payload, headers=headers)
            body = _try_json(_decode(resp)) or {}
        except httpx.HTTPError as exc:
            raise ProviderError(str(t("err_pw_req_fail", exc=exc))) from exc

        access = dig(body, "data.access_token") or dig(body, "data.accessToken")
        if not access:
            reason = dig(body, "message") or dig(body, "error_description") or ""
            raise ProviderError(str(t("err_pw_fail", reason=reason or body)), detail=body)
        ctx["idp_access_token"] = access

        return self._sso_exchange(dict(client.cookies), ctx)

    def _read_cache(self) -> str:
        if not self.token_file or not self.token_file.exists():
            return ""
        try:
            data = json.loads(self.token_file.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return ""
        return str(data.get("token") or "")

    def _write_cache(self, token: str) -> None:
        if not self.token_file:
            return
        self.token_file.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "token": token,
            "obtained_at": datetime.now().isoformat(timespec="seconds"),
        }
        self.token_file.write_text(json.dumps(payload, ensure_ascii=False), "utf-8")
        try:
            self.token_file.chmod(0o600)
        except OSError:
            pass

    def _login(self, client: httpx.Client, ctx: dict) -> str:
        req = _subst(self.login_conf, ctx)
        url = str(req.get("url") or "")
        if not url:
            raise ProviderError(str(t("err_login_no_url")))

        kwargs: dict[str, Any] = {"headers": {**self.base_headers, **(req.get("headers") or {})}}
        if req.get("params"):
            kwargs["params"] = req["params"]
        if req.get("json"):
            kwargs["json"] = req["json"]
        elif req.get("form") or req.get("data"):
            kwargs["data"] = req.get("form") or req.get("data")

        try:
            resp = client.request(str(req.get("method", "POST")).upper(), url, **kwargs)
        except httpx.HTTPError as exc:
            raise ProviderError(str(t("err_login_req_fail", exc=exc))) from exc

        text = _decode(resp)
        body = _try_json(text)
        if not resp.is_success:
            raise ProviderError(str(t("err_login_http", code=resp.status_code)), detail=text[:800])

        token = dig(body, req.get("token_path", "data.token"))
        if not token:
            reason = (
                dig(body, "msg")
                or dig(body, "message")
                or dig(body, "error")
                or text[:200]
            )
            raise ProviderError(str(t("err_login_fail", reason=reason)), detail=text[:800])
        token = str(token)
        self._token = token
        self._write_cache(token)
        ctx["token"] = token
        return token

    def _ensure_token(self, client: httpx.Client, ctx: dict) -> None:
        if self.auth_mode == "none":
            return
        if self.auth_mode == "token":
            # 优先用本地缓存的（run.py token 写进去的），其次才是 .env 里的
            token = self._read_cache() or self.static_token
            if not token:
                raise ProviderError(
                    str(t("err_token_empty"))
                )
            self._token = token
            ctx["token"] = token
            return
        cached = self._read_cache()
        if cached:
            self._token = cached
            ctx["token"] = cached
            return
        if self.auth_mode == "password":
            self._password_login(client, ctx)
            return
        if self.auth_mode == "sso":
            if self.sso_conf.get("cookie"):
                self._sso_login(client, ctx)
            elif self.static_token:
                self._token = self.static_token
                ctx["token"] = self.static_token
            else:
                raise ProviderError(
                    str(t("err_sso_no_cookie"))
                )
            return
        self._login(client, ctx)

    @staticmethod
    def _is_auth_error(entry: dict) -> bool:
        if entry["status"] in (401, 403):
            return True
        body = entry.get("json")
        return isinstance(body, dict) and str(body.get("code")) == "401"

    def _run(self) -> tuple[list[dict], dict]:
        ctx: dict[str, Any] = {
            "steps": [],
            "env": dict(os.environ),
            "now": {
                "iso": datetime.now().isoformat(timespec="seconds"),
                "date": datetime.now().strftime("%Y-%m-%d"),
                "ts": int(datetime.now().timestamp() * 1000),
            },
        }

        with httpx.Client(
            timeout=self.timeout,
            verify=self.verify_ssl,
            follow_redirects=True,
            cookies=self.cookies,
        ) as client:
            self._ensure_token(client, ctx)
            self.token_info = {
                "mode": self.auth_mode,
                "ok": bool(ctx.get("token")),
            }

            entries: list[dict] = []
            for attempt in range(2):
                entries, auth_failed = self._run_steps(client, ctx)
                if auth_failed:
                    if attempt == 0 and self.auth_mode in ("login", "sso", "password"):
                        if self.auth_mode == "sso":
                            self._sso_login(client, ctx)
                        elif self.auth_mode == "password":
                            self._password_login(client, ctx)
                        else:
                            self._login(client, ctx)
                        ctx["steps"] = []
                        continue
                    raise ProviderError(
                        str(t("err_401")),
                        detail=entries[-1] if entries else None,
                    )
                return entries, ctx
            return entries, ctx

    def _run_steps(self, client: httpx.Client, ctx: dict) -> tuple[list[dict], bool]:
        """执行所有 step。返回 (entries, 是否鉴权失败)。

        标了 optional: true 的步骤失败只记录、不中断；其余步骤出错直接抛。
        """
        entries: list[dict] = []
        auth_failed = False

        for index, step in enumerate(self.steps):
            name = step.get("name") or f"step{index}"
            optional = bool(step.get("optional"))
            req = _subst(step, ctx)

            headers = {**self.base_headers, **(req.get("headers") or {})}
            if ctx.get("token") and not any(k.lower() == "authorization" for k in headers):
                headers["Authorization"] = f"Bearer {ctx['token']}"

            method = str(req.get("method", "GET")).upper()
            url = str(req["url"])

            kwargs: dict[str, Any] = {"headers": headers}
            if req.get("params"):
                kwargs["params"] = req["params"]
            if req.get("json"):
                kwargs["json"] = req["json"]
            elif req.get("form") or req.get("data"):
                kwargs["data"] = req.get("form") or req.get("data")

            try:
                resp = client.request(method, url, **kwargs)
            except httpx.HTTPError as exc:
                if optional:
                    entry = {
                        "name": name,
                        "status": 0,
                        "url": url,
                        "text": "",
                        "json": None,
                        "error": str(exc),
                    }
                    ctx["steps"].append(entry)
                    entries.append(entry)
                    continue
                raise ProviderError(str(t("err_step_req_fail", name=name, exc=exc))) from exc

            text = _decode(resp)
            entry = {
                "name": name,
                "status": resp.status_code,
                "url": str(resp.request.url),
                "request_body": kwargs.get("json") or kwargs.get("data"),
                "text": text[:20000],
                "json": _try_json(text),
            }
            if step.get("save_cookies"):
                entry["cookies"] = dict(client.cookies)

            ctx["steps"].append(entry)
            entries.append(entry)

            if self._is_auth_error(entry):
                if optional:
                    entry["error"] = "auth"
                    continue
                auth_failed = True
                break

            if not resp.is_success:
                if optional:
                    entry["error"] = f"HTTP {resp.status_code}"
                    continue
                raise ProviderError(f"[{name}] HTTP {resp.status_code}", detail=entry)

        return entries, auth_failed

    def _pick(self, spec: Any, entries: list[dict]) -> Any:
        if spec is None or not entries:
            return None
        if isinstance(spec, str):
            return dig(entries[-1].get("json"), spec)
        if isinstance(spec, dict):
            index = int(spec.get("step", -1))
            try:
                entry = entries[index]
            except IndexError:
                return None
            if "regex" in spec:
                text = entry.get("text") or ""
                match = re.search(spec["regex"], text, re.S)
                if not match:
                    return None
                try:
                    return match.group(int(spec.get("group", 1)))
                except IndexError:
                    return match.group(0)
            path = spec.get("path")
            base = entry.get("json") if spec.get("source") != "text" else entry.get("text")
            return dig(base, path) if path else None
        return spec

    def fetch(self, previous: Reading | None = None) -> Reading:
        entries, _ctx = self._run()

        spec = self.extract.get("balance_kwh")
        try:
            last = entries[int(spec.get("step", -1))] if isinstance(spec, dict) else entries[-1]
        except (IndexError, TypeError, ValueError):
            last = entries[-1] if entries else {"json": None, "text": ""}

        kwh = to_float(self._pick(spec, entries))
        if kwh is None:
            msg = dig(last.get("json"), "msg") or dig(last.get("json"), "message")
            hint = f"（接口返回：{msg}）" if msg else ""
            raise ProviderError(
                f"没能从响应里解析出 balance_kwh{hint}。检查 provider.http.extract 配置，"
                "或用 `python run.py probe` 看原始响应。",
                detail=last,
            )

        room = self._pick(self.extract.get("room"), entries)
        updated = self._pick(self.extract.get("updated_at"), entries)

        extra: dict[str, Any] = {}
        for key, spec in (self.extract.get("extra") or {}).items():
            value = self._pick(spec, entries)
            if value not in (None, ""):
                extra[key] = value

        return Reading(
            ts=datetime.now().astimezone(),
            room=str(room or self.conf.get("room", "") or ""),
            balance_kwh=kwh,
            balance_cny=to_float(self._pick(self.extract.get("balance_cny"), entries)),
            source=self.name,
            meta={
                "reported_at": str(updated) if updated else None,
                "extra": extra,
                "steps": [
                    {"name": e["name"], "status": e["status"]} for e in entries
                ],
            },
        )

    def probe(self) -> list[dict]:
        entries, _ctx = self._run()
        return [{k: v for k, v in e.items() if k != "cookies"} for e in entries]

    def validate_token(self, token: str) -> tuple[bool, str]:
        """拿第一个 step 试一下这个 token 还能不能用。"""
        step = self.steps[0]
        ctx: dict[str, Any] = {"steps": [], "env": dict(os.environ), "token": token}
        req = _subst(step, ctx)

        headers = {**self.base_headers, **(req.get("headers") or {})}
        headers["Authorization"] = f"Bearer {token}"

        kwargs: dict[str, Any] = {"headers": headers}
        if req.get("params"):
            kwargs["params"] = req["params"]
        if req.get("json"):
            kwargs["json"] = req["json"]
        elif req.get("form") or req.get("data"):
            kwargs["data"] = req.get("form") or req.get("data")

        try:
            with httpx.Client(
                timeout=self.timeout, verify=self.verify_ssl, follow_redirects=True
            ) as client:
                resp = client.request(
                    str(req.get("method", "GET")).upper(), str(req["url"]), **kwargs
                )
        except httpx.HTTPError as exc:
            return False, f"请求失败：{exc}"

        text = _decode(resp)
        entry = {
            "name": step.get("name", "step0"),
            "status": resp.status_code,
            "json": _try_json(text),
        }
        if self._is_auth_error(entry):
            return False, "token 无效或已过期"
        if not resp.is_success:
            return False, f"HTTP {resp.status_code}"
        return True, "ok"

    def save_token(self, token: str) -> None:
        self._token = token
        self._write_cache(token)

    def current_token(self) -> str:
        """当前会用的 token：缓存优先，其次配置里的。"""
        return self._read_cache() or self.static_token

    def token_meta(self) -> dict:
        """看缓存里存的 token 是什么时候拿到的。"""
        if not self.token_file or not self.token_file.exists():
            return {}
        try:
            return json.loads(self.token_file.read_text("utf-8"))
        except (json.JSONDecodeError, OSError):
            return {}

    def relogin(self) -> dict:
        with httpx.Client(timeout=self.timeout, verify=self.verify_ssl) as client:
            ctx: dict[str, Any] = {"env": dict(os.environ), "steps": []}
            if self.auth_mode == "password":
                token = self._password_login(client, ctx)
            elif self.auth_mode == "sso":
                token = self._sso_login(client, ctx)
            else:
                token = self._login(client, ctx)
        return {
            "ok": True,
            "length": len(token),
            "obtained_at": datetime.now().isoformat(timespec="seconds"),
            "file": str(self.token_file) if self.token_file else None,
        }
