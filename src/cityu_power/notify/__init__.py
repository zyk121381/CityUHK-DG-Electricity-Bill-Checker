"""推送渠道注册与工厂。

开关和参数走 .env：NOTIFY_CHANNELS 列出启用哪些渠道，各渠道的变量名见 ENV_KEYS。
config.yaml 里的 `notify.<渠道名>` 同名块会覆盖对应的环境变量。
"""

from __future__ import annotations

import os

from ..config import Config
from .base import Channel, NotifyError
from .channels import (
    EmailChannel,
    FeishuChannel,
    PushPlusChannel,
    ServerChanChannel,
    ShowDocChannel,
    WebhookChannel,
    WecomBotChannel,
    WxPusherChannel,
)

REGISTRY: dict[str, type[Channel]] = {
    c.name: c
    for c in (
        EmailChannel,
        FeishuChannel,
        PushPlusChannel,
        ServerChanChannel,
        ShowDocChannel,
        WecomBotChannel,
        WxPusherChannel,
        WebhookChannel,
    )
}

ENV_KEYS: dict[str, dict[str, str]] = {
    "email": {
        "smtp_host": "SMTP_HOST",
        "smtp_port": "SMTP_PORT",
        "username": "SMTP_USER",
        "password": "SMTP_PASSWORD",
        "to_addrs": "SMTP_TO",
        "use_ssl": "SMTP_SSL",
        "subject_prefix": "SMTP_SUBJECT_PREFIX",
    },
    "showdoc": {"url": "SHOWDOC_URL"},
    "feishu": {"webhook": "FEISHU_WEBHOOK"},
    "wxpusher": {"spt": "WXPUSHER_SPT", "content_type": "WXPUSHER_CONTENT_TYPE"},
    "pushplus": {"token": "PUSHPLUS_TOKEN", "topic": "PUSHPLUS_TOPIC"},
    "serverchan": {"sendkey": "SERVERCHAN_SENDKEY"},
    "wecom_bot": {"webhook": "WECOM_WEBHOOK"},
    "webhook": {"url": "WEBHOOK_URL"},
}

__all__ = [
    "Channel",
    "NotifyError",
    "REGISTRY",
    "build_channels",
    "channel_names",
    "send_all",
]


def _truthy(value: object, default: bool = True) -> bool:
    if value is None or value == "":
        return default
    return str(value).strip().lower() not in ("0", "false", "no", "off")


def channel_names(cfg: Config) -> list[str]:
    """启用的渠道：优先看 .env 的 NOTIFY_CHANNELS，其次 config.yaml。"""
    raw = (os.environ.get("NOTIFY_CHANNELS") or "").strip()
    if raw:
        return [name.strip() for name in raw.replace(";", ",").split(",") if name.strip()]

    wanted = cfg.get("notify.channels", []) or []
    if isinstance(wanted, str):
        wanted = [wanted]
    return [str(name).strip() for name in wanted if str(name).strip()]


def _channel_conf(cfg: Config, name: str) -> dict:
    """config.yaml 里的同名块打底，缺失的字段用环境变量补。"""
    conf = dict(cfg.get(f"notify.{name}", {}) or {})

    for key, env in ENV_KEYS.get(name, {}).items():
        value = os.environ.get(env)
        if value not in (None, "") and not conf.get(key):
            conf[key] = value

    if name == "email":
        to_addrs = conf.get("to_addrs")
        if isinstance(to_addrs, str):
            conf["to_addrs"] = [x.strip() for x in to_addrs.replace(";", ",").split(",") if x.strip()]
        if conf.get("smtp_port"):
            conf["smtp_port"] = int(conf["smtp_port"])
        conf["use_ssl"] = _truthy(conf.get("use_ssl"), True)

    if name == "wxpusher" and conf.get("content_type"):
        conf["content_type"] = int(conf["content_type"])

    return conf


def build_channels(cfg: Config) -> list[Channel]:
    channels: list[Channel] = []
    for name in channel_names(cfg):
        cls = REGISTRY.get(name)
        if cls is None:
            raise NotifyError(f"未知的推送渠道：{name}（可选 {', '.join(REGISTRY)}）")
        channel = cls(_channel_conf(cfg, name))
        if channel.available():
            channels.append(channel)
    return channels


def send_all(
    channels: list[Channel],
    subject: str,
    plain: str,
    html: str | None = None,
    markdown: str | None = None,
) -> list[tuple[str, str | None]]:
    """逐个发送，互不影响。返回 [(渠道, 错误信息或 None), ...]。"""
    results: list[tuple[str, str | None]] = []
    for channel in channels:
        try:
            channel.send(subject, plain, html, markdown)
            results.append((channel.label, None))
        except NotifyError as exc:
            results.append((channel.label, str(exc)))
        except Exception as exc:
            results.append((channel.label, f"{type(exc).__name__}: {exc}"))
    return results
