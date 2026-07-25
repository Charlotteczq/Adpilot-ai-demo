"""广告形式、平台能力与演示模拟参数目录。

所有参数仅用于 Demo 内的相对比较，不代表任何平台的真实基准。
"""

from __future__ import annotations

from typing import Any


CREATIVE_FORMATS: dict[str, dict[str, Any]] = {
    "search_text": {
        "name": "搜索文字广告",
        "best_for": "承接已有明确需求和关键词意图",
        "default_difficulty": "低",
        "cpm_range": (30.0, 65.0),
        "ctr_range": (0.018, 0.045),
        "cvr_range": (0.025, 0.070),
    },
    "static_image": {
        "name": "静态图片广告",
        "best_for": "外观、价格或单一卖点能够快速理解的产品",
        "default_difficulty": "低",
        "cpm_range": (25.0, 60.0),
        "ctr_range": (0.007, 0.020),
        "cvr_range": (0.012, 0.045),
    },
    "carousel": {
        "name": "轮播图广告",
        "best_for": "需要展示多个功能、步骤或使用场景的产品",
        "default_difficulty": "中",
        "cpm_range": (28.0, 64.0),
        "ctr_range": (0.009, 0.024),
        "cvr_range": (0.014, 0.050),
    },
    "short_video": {
        "name": "竖版短视频",
        "best_for": "操作演示、前后对比和过程型卖点",
        "default_difficulty": "高",
        "cpm_range": (30.0, 75.0),
        "ctr_range": (0.010, 0.032),
        "cvr_range": (0.010, 0.042),
    },
    "native_content": {
        "name": "原生图文 / UGC",
        "best_for": "依赖体验、信任、口碑或生活方式场景的产品",
        "default_difficulty": "中",
        "cpm_range": (35.0, 80.0),
        "ctr_range": (0.012, 0.035),
        "cvr_range": (0.015, 0.052),
    },
    "retargeting": {
        "name": "再营销广告",
        "best_for": "购买周期较长或需要多次触达的产品",
        "default_difficulty": "中",
        "cpm_range": (32.0, 70.0),
        "ctr_range": (0.014, 0.040),
        "cvr_range": (0.025, 0.080),
    },
}


FORMAT_ALIASES = {
    "搜索广告": "search_text",
    "搜索文字广告": "search_text",
    "响应式搜索广告": "search_text",
    "静态图片": "static_image",
    "静态图片广告": "static_image",
    "单图广告": "static_image",
    "轮播图": "carousel",
    "轮播图广告": "carousel",
    "短视频": "short_video",
    "竖版短视频": "short_video",
    "信息流短视频": "short_video",
    "原生图文": "native_content",
    "原生图文 / UGC": "native_content",
    "UGC": "native_content",
    "再营销": "retargeting",
    "再营销广告": "retargeting",
}


# 这些系数只用于让 Demo 中的平台结果产生相对差异，不是实际投放数据。
PLATFORM_DEMO_FACTORS: dict[str, dict[str, float]] = {
    "小红书": {"cpm": 1.08, "ctr": 1.10, "cvr": 0.96},
    "抖音": {"cpm": 1.12, "ctr": 1.16, "cvr": 0.90},
    "微信广告": {"cpm": 1.00, "ctr": 0.94, "cvr": 1.00},
    "百度搜索": {"cpm": 0.98, "ctr": 1.02, "cvr": 1.10},
    "百度信息流": {"cpm": 0.96, "ctr": 0.98, "cvr": 0.96},
    "Google Search": {"cpm": 1.05, "ctr": 1.04, "cvr": 1.12},
    "Google Display": {"cpm": 0.88, "ctr": 0.82, "cvr": 0.86},
    "Meta": {"cpm": 1.00, "ctr": 1.04, "cvr": 0.98},
    "TikTok": {"cpm": 1.10, "ctr": 1.14, "cvr": 0.88},
    "YouTube": {"cpm": 1.08, "ctr": 0.92, "cvr": 0.94},
}


def normalize_format_id(value: Any) -> str:
    """把模型返回的格式 ID 或中文名称归一化。"""

    raw = str(value or "").strip()
    if raw in CREATIVE_FORMATS:
        return raw
    if raw in FORMAT_ALIASES:
        return FORMAT_ALIASES[raw]
    for alias, format_id in FORMAT_ALIASES.items():
        if alias.lower() in raw.lower():
            return format_id
    return "static_image"


def format_profile(value: Any) -> dict[str, Any]:
    """返回广告形式配置，未知形式回退到静态图片。"""

    format_id = normalize_format_id(value)
    return {"id": format_id, **CREATIVE_FORMATS[format_id]}


def platform_factors(platform_name: Any) -> dict[str, float]:
    """按平台名称返回演示系数，无法识别时使用中性系数。"""

    raw = str(platform_name or "").strip().lower()
    for name, factors in PLATFORM_DEMO_FACTORS.items():
        if name.lower() in raw or raw in name.lower():
            return factors
    return {"cpm": 1.0, "ctr": 1.0, "cvr": 1.0}
