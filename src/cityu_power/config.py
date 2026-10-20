"""
配置加载。
主配置是项目根目录的 config.yaml，值里可以写 ${VAR}，
运行时从环境变量或同目录 .env 替换。读取用点号路径。
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import yaml

PLACEHOLDER = re.compile(r"\$\{([^}]+)\}")
_PATH_TOKEN = re.compile(r"[^.\[\]]+")

# 只替换这种形状的占位符：${EPAY_TOKEN}、${SMTP_PASSWORD}
# ${steps.0.json.data.token} 是 provider 层的运行时引用，留给 providers/http.py 处理
ENV_NAME = re.compile(r"^[A-Z_][A-Z0-9_]*$")

RUNTIME_PLACEHOLDERS = {"report_text", "subject"}


def load_dotenv(path: Path) -> None:
    """极简 .env 解析：KEY=VALUE，支持 # 注释与引号。不覆盖已有环境变量。"""
    if not path.exists():
        return
    for raw in path.read_text("utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def dig(data: Any, path: str, default: Any = None) -> Any:
    """按 "a.b[0].c" 或 "a.b.0.c" 取嵌套值，取不到返回 default。"""
    if not path:
        return default
    cur = data
    for token in _PATH_TOKEN.findall(path):
        try:
            if isinstance(cur, (list, tuple)):
                cur = cur[int(token)]
            elif isinstance(cur, dict):
                cur = cur[token]
            else:
                return default
        except (KeyError, IndexError, ValueError, TypeError):
            return default
    return cur


def to_float(value: Any) -> float | None:
    """把 '12.34 度' / '¥1,234.5' / 12 都转成 float。"""
    if value is None:
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    match = re.search(r"-?\d+(?:\.\d+)?", str(value).replace(",", ""))
    return float(match.group()) if match else None


class Config:
    """配置对象，用点号路径取值。"""
    def __init__(self, data: dict, path: Path, missing_env: set[str]):
        self.data = data or {}
        self.path = path
        self.missing_env = missing_env

    def get(self, dotted: str, default: Any = None) -> Any:
        value = dig(self.data, dotted, None)
        return default if value is None else value

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    @property
    def root(self) -> Path:
        return self.path.parent

    def resolve_path(self, relative: str) -> Path:
        p = Path(relative)
        return p if p.is_absolute() else (self.root / p)


def _expand(node: Any, missing: set[str]) -> Any:
    if isinstance(node, str):
        def replace(match: re.Match) -> str:
            name = match.group(1)
            if name in RUNTIME_PLACEHOLDERS or not ENV_NAME.match(name):
                return match.group(0)
            value = os.environ.get(name)
            if value is None:
                missing.add(name)
                return ""
            return value

        return PLACEHOLDER.sub(replace, node)
    if isinstance(node, dict):
        return {k: _expand(v, missing) for k, v in node.items()}
    if isinstance(node, list):
        return [_expand(v, missing) for v in node]
    return node


def load(path: str | Path = "config.yaml") -> Config:
    cfg_path = Path(path)
    if not cfg_path.exists():
        raise FileNotFoundError(
            f"找不到配置文件 {cfg_path}。先执行：python run.py init"
        )
    load_dotenv(cfg_path.parent / ".env")

    raw = yaml.safe_load(cfg_path.read_text("utf-8-sig")) or {}
    missing: set[str] = set()
    return Config(_expand(raw, missing), cfg_path, missing)
