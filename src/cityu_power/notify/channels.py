"""
八个推送渠道的实现。
只用标准库 + httpx。各渠道的 `kind` 决定用 plain / html / markdown 里的哪一种正文。
"""

from __future__ import annotations

import json
import re
import smtplib
import ssl
from email.message import EmailMessage

import httpx

from ..i18n import LINKS, t
from .base import Channel, NotifyError

SendArgs = tuple[str, str, str | None, str | None]


class EmailChannel(Channel):
    """SMTP 邮件，正文用 HTML。"""
    name = "email"
    label = "邮箱"
    kind = "html"

    def available(self) -> bool:
        conf = self.conf
        return bool(
            conf.get("smtp_host") and conf.get("username") and conf.get("to_addrs")
        )

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        conf = self.conf
        host = str(conf.get("smtp_host", ""))
        port = int(conf.get("smtp_port", 465))
        username = str(conf.get("username", ""))
        password = str(conf.get("password", ""))
        from_addr = str(conf.get("from_addr") or username)
        to_addrs = conf.get("to_addrs") or []
        if isinstance(to_addrs, str):
            to_addrs = [to_addrs]

        msg = EmailMessage()
        msg["Subject"] = f"{conf.get('subject_prefix', '')}{subject}"
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        msg.set_content(plain)
        if html:
            msg.add_alternative(html, subtype="html")

        try:
            if bool(conf.get("use_ssl", True)):
                with smtplib.SMTP_SSL(host, port, timeout=30) as smtp:
                    smtp.login(username, password)
                    smtp.send_message(msg)
            else:
                with smtplib.SMTP(host, port, timeout=30) as smtp:
                    smtp.ehlo()
                    smtp.starttls(context=ssl.create_default_context())
                    smtp.login(username, password)
                    smtp.send_message(msg)
        except (smtplib.SMTPException, OSError) as exc:
            raise NotifyError(f"邮件发送失败：{exc}") from exc


class PushPlusChannel(Channel):
    """PushPlus，正文用 HTML。"""
    name = "pushplus"
    label = "PushPlus(微信)"
    kind = "html"

    def available(self) -> bool:
        return bool(self.conf.get("token"))

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        use_html = bool(html)
        payload = {
            "token": self.conf["token"],
            "title": subject,
            "content": self.clip(html if use_html else plain, 3500),
            "template": "html" if use_html else "txt",
        }
        if self.conf.get("topic"):
            payload["topic"] = self.conf["topic"]
        try:
            resp = httpx.post(
                "https://www.pushplus.plus/send", json=payload, timeout=20
            )
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NotifyError(f"PushPlus 请求失败：{exc}") from exc
        if data.get("code") != 200:
            raise NotifyError(f"PushPlus 返回异常：{data}")


class ServerChanChannel(Channel):
    """Server酱，正文用 Markdown。"""
    name = "serverchan"
    label = "Server酱"
    kind = "markdown"

    def available(self) -> bool:
        return bool(self.conf.get("sendkey"))

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        key = self.conf["sendkey"]
        body = self.pick(plain, html, markdown)
        try:
            resp = httpx.post(
                f"https://sctapi.ftqq.com/{key}.send",
                data={"title": subject, "desp": self.clip(body, 32000)},
                timeout=20,
            )
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NotifyError(f"Server酱请求失败：{exc}") from exc
        if data.get("code") not in (0, None):
            raise NotifyError(f"Server酱返回异常：{data}")


class ShowDocChannel(Channel):
    """ShowDoc 推送，正文按 Markdown 渲染。"""

    name = "showdoc"
    label = "ShowDoc(微信)"
    kind = "markdown"

    def available(self) -> bool:
        return bool(self.conf.get("url"))

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        url = str(self.conf.get("url"))
        if markdown:
            content = self.clip(markdown, 4000)
        else:
            content = self.clip(plain.replace("\n", "\n\n"), 4000)
        try:
            resp = httpx.post(
                url, params={"title": subject, "content": content}, timeout=20
            )
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NotifyError(f"ShowDoc 请求失败：{exc}") from exc
        if data.get("error_code") != 0:
            raise NotifyError(f"ShowDoc 返回异常：{data}")


def _strip_leading_title(body: str) -> str:
    """去掉正文开头的粗体标题行。

    飞书卡片有 header 标题了，正文里再来一行重复的标题就没必要。
    """
    lines = body.splitlines()
    if not lines or not lines[0].startswith("**") or not lines[0].rstrip().endswith("**"):
        return body
    lines = lines[1:]
    while lines and not lines[0].strip():
        lines = lines[1:]
    return "\n".join(lines)


class FeishuChannel(Channel):
    """飞书群机器人，正文用 Markdown，走交互卡片。"""

    name = "feishu"
    label = "飞书机器人"
    kind = "markdown"

    def available(self) -> bool:
        return bool(self.conf.get("webhook"))

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        body = _strip_leading_title(self.pick(plain, html, markdown))
        content = self.clip(body, 8000)
        # 飞书自定义机器人没有 markdown 类型，Markdown 正文走交互卡片的 lark_md
        card = {
            "msg_type": "interactive",
            "card": {
                "config": {"wide_screen_mode": True},
                "header": {
                    "title": {"tag": "plain_text", "content": subject},
                    "template": "red" if "⚠️" in body else "blue",
                },
                "elements": [
                    {"tag": "div", "text": {"tag": "lark_md", "content": content}},
                    {
                        "tag": "action",
                        "actions": [
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": "GitHub"},
                                "type": "primary",
                                "url": LINKS["github"],
                            },
                            {
                                "tag": "button",
                                "text": {"tag": "plain_text", "content": str(t("blog"))},
                                "type": "default",
                                "url": LINKS["blog"],
                            },
                        ],
                    },
                ],
            },
        }
        fallback = {
            "msg_type": "text",
            "content": {"text": f"{subject}\n\n{content}"},
        }

        try:
            resp = httpx.post(self.conf["webhook"], json=card, timeout=20)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NotifyError(f"飞书机器人请求失败：{exc}") from exc

        if data.get("code", data.get("StatusCode")) not in (0, None):
            # 卡片不被允许时退回纯文本
            try:
                resp = httpx.post(self.conf["webhook"], json=fallback, timeout=20)
                data = resp.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise NotifyError(f"飞书机器人请求失败：{exc}") from exc

        code = data.get("code", data.get("StatusCode"))
        if code not in (0, None):
            raise NotifyError(f"飞书机器人返回异常：{data}")


class WxPusherChannel(Channel):
    """WxPusher 极简推送，正文格式由 content_type 决定。"""

    name = "wxpusher"
    label = "WxPusher(SPT)"
    kind = "markdown"

    URL = "https://wxpusher.zjiecode.com/api/send/message/simple-push"

    def available(self) -> bool:
        return bool(self.conf.get("spt"))

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        content_type = int(self.conf.get("content_type", 3) or 3)

        if content_type == 3 and markdown:
            content = markdown
        elif content_type == 2 and html:
            content = _inner_body(html)
        else:
            content = plain
            content_type = 1

        payload = {
            "content": content,
            "summary": subject[:100],
            "contentType": content_type,
            "spt": self.conf["spt"],
        }

        try:
            resp = httpx.post(self.URL, json=payload, timeout=25)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NotifyError(f"WxPusher 请求失败：{exc}") from exc

        if data.get("code") != 1000:
            raise NotifyError(f"WxPusher 返回异常：{data.get('code')} {data.get('msg')}")


def _inner_body(html: str) -> str:
    """WxPusher 的 HTML 只接受 body 内部内容，把外层壳剥掉。"""
    match = re.search(r"<body[^>]*>(.*)</body>", html, re.S | re.I)
    return match.group(1) if match else html


class WecomBotChannel(Channel):
    """企业微信群机器人，正文用 Markdown。"""
    name = "wecom_bot"
    label = "企业微信群机器人"
    kind = "markdown"

    def available(self) -> bool:
        return bool(self.conf.get("webhook"))

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        body = self.pick(plain, html, markdown)
        content = self.clip(body, 3900)
        payload = {"msgtype": "markdown", "markdown": {"content": content}}
        try:
            resp = httpx.post(self.conf["webhook"], json=payload, timeout=20)
            data = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise NotifyError(f"企业微信机器人请求失败：{exc}") from exc
        if data.get("errcode") not in (0, None):
            raise NotifyError(f"企业微信机器人返回异常：{data}")


class WebhookChannel(Channel):
    """自定义接口，正文为纯文本。"""
    name = "webhook"
    label = "自定义 Webhook"
    kind = "plain"

    def available(self) -> bool:
        return bool(self.conf.get("url"))

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        body = self.conf.get("json") or {
            "subject": "${subject}",
            "text": "${report_text}",
        }
        if isinstance(body, str):
            rendered = body.replace("${subject}", subject).replace(
                "${report_text}", plain
            )
            try:
                body = json.loads(rendered)
            except json.JSONDecodeError:
                pass
        else:
            body = _render(body, subject, plain)

        method = str(self.conf.get("method", "POST")).upper()
        try:
            resp = httpx.request(method, self.conf["url"], json=body, timeout=20)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise NotifyError(f"Webhook 请求失败：{exc}") from exc

        try:
            data = resp.json()
        except ValueError:
            return
        if isinstance(data, dict):
            code = data.get("code", data.get("errcode", data.get("error_code")))
            if code not in (None, 0, "0"):
                raise NotifyError(f"Webhook 返回异常：{data}")


def _render(node, subject: str, text: str):
    if isinstance(node, str):
        return node.replace("${subject}", subject).replace("${report_text}", text)
    if isinstance(node, dict):
        return {k: _render(v, subject, text) for k, v in node.items()}
    if isinstance(node, list):
        return [_render(v, subject, text) for v in node]
    return node
