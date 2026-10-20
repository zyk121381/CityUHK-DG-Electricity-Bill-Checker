"""推送渠道基类。"""

from __future__ import annotations


class NotifyError(RuntimeError):
    """推送失败。"""

    pass


class Channel:
    """推送渠道基类。"""
    name = "base"
    label = "基础"
    # 正文偏好：plain / markdown / html
    kind = "plain"

    def __init__(self, conf: dict | None = None):
        self.conf = conf or {}

    def available(self) -> bool:
        """配置是否齐全。缺配置就静默跳过，不报错。"""
        return True

    def pick(self, plain: str, html: str | None, markdown: str | None) -> str:
        if self.kind == "html" and html:
            return html
        if self.kind == "markdown" and markdown:
            return markdown
        return plain

    def send(
        self,
        subject: str,
        plain: str,
        html: str | None = None,
        markdown: str | None = None,
    ) -> None:
        raise NotImplementedError

    @staticmethod
    def clip(text: str, limit: int) -> str:
        if len(text) <= limit:
            return text
        return text[: limit - 12] + "\n…（已截断）"
