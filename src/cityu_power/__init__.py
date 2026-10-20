"""香港城市大学（东莞）宿舍电量查询器。

包结构：
    config      配置加载（YAML + .env + 环境变量占位符）
    models      数据模型
    storage     SQLite 存储
    analyzer    用量分析与告警判定
    providers   数据来源（mock / 配置化 HTTP）
    notify      推送渠道
    report      报告渲染（纯文本 / Markdown / HTML）
    i18n        报告文案，中英两套
    cli         命令行入口
"""

__version__ = "0.1.0"
