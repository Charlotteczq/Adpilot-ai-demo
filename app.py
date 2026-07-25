"""AdPilot AI：一天可落地的 Streamlit 广告策略 Demo。"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
from dataclasses import dataclass
from typing import Any
from urllib.parse import urlparse

import pandas as pd
import requests
import streamlit as st
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from openai import APIConnectionError, AuthenticationError, BadRequestError, OpenAI

from prompt import SYSTEM_PROMPT, build_user_prompt, demo_result_copy


load_dotenv()

APP_TITLE = "AdPilot AI"
REQUEST_TIMEOUT_SECONDS = 10
MAX_SCRAPED_CHARS = 8_000


@dataclass
class FetchResult:
    """网页抓取结果。"""

    text: str
    warning: str = ""


def configure_page() -> None:
    """设置页面与深海油画视觉样式。"""

    st.set_page_config(
        page_title=f"{APP_TITLE} · 广告策略 Demo",
        page_icon="🌊",
        layout="wide",
    )

    st.markdown(
        """
        <style>
        :root {
            --navy: #031447;
            --deep-blue: #093876;
            --ocean-blue: #135B93;
            --light-blue: #3682A8;
            --stone: #C3C4B4;
            --ivory: #F3F0E6;
            --ink: #06183B;
        }

        /* 整个页面的深海油画背景 */
        .stApp {
            background-color: var(--navy);
            background-image:
                radial-gradient(
                    ellipse at 8% 12%,
                    rgba(54, 130, 168, 0.78) 0 9%,
                    transparent 26%
                ),
                radial-gradient(
                    ellipse at 32% 5%,
                    rgba(19, 91, 147, 0.82) 0 12%,
                    transparent 31%
                ),
                radial-gradient(
                    ellipse at 69% 8%,
                    rgba(9, 56, 118, 0.90) 0 15%,
                    transparent 34%
                ),
                radial-gradient(
                    ellipse at 94% 19%,
                    rgba(54, 130, 168, 0.68) 0 10%,
                    transparent 28%
                ),
                radial-gradient(
                    ellipse at 17% 38%,
                    rgba(9, 56, 118, 0.92) 0 15%,
                    transparent 36%
                ),
                radial-gradient(
                    ellipse at 48% 34%,
                    rgba(54, 130, 168, 0.48) 0 12%,
                    transparent 31%
                ),
                radial-gradient(
                    ellipse at 83% 43%,
                    rgba(19, 91, 147, 0.78) 0 14%,
                    transparent 34%
                ),
                radial-gradient(
                    ellipse at 3% 69%,
                    rgba(19, 91, 147, 0.72) 0 13%,
                    transparent 33%
                ),
                radial-gradient(
                    ellipse at 35% 68%,
                    rgba(54, 130, 168, 0.50) 0 12%,
                    transparent 32%
                ),
                radial-gradient(
                    ellipse at 67% 73%,
                    rgba(9, 56, 118, 0.88) 0 16%,
                    transparent 37%
                ),
                radial-gradient(
                    ellipse at 96% 79%,
                    rgba(54, 130, 168, 0.56) 0 13%,
                    transparent 31%
                ),
                radial-gradient(
                    ellipse at 20% 100%,
                    rgba(9, 56, 118, 0.96) 0 20%,
                    transparent 42%
                ),
                linear-gradient(
                    155deg,
                    #031447 0%,
                    #093876 44%,
                    #031447 100%
                );
            background-attachment: fixed;
        }

        /* 细密弧形纹理，用来模拟画布和笔触 */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            pointer-events: none;
            opacity: 0.18;
            background-image:
                repeating-radial-gradient(
                    ellipse at 20% 30%,
                    transparent 0 7px,
                    rgba(243, 240, 230, 0.23) 8px,
                    transparent 9px 15px
                ),
                repeating-radial-gradient(
                    ellipse at 75% 65%,
                    transparent 0 10px,
                    rgba(195, 196, 180, 0.15) 11px,
                    transparent 12px 20px
                );
            mix-blend-mode: soft-light;
            z-index: 0;
        }

        /* 主内容保持在纹理上方 */
        .block-container {
            position: relative;
            z-index: 1;
            max-width: 1240px;
            padding-top: 1.8rem;
            padding-bottom: 4rem;
        }

        /* 基础文字 */
        h1, h2, h3 {
            color: var(--ivory) !important;
            letter-spacing: 0.01em;
        }

        p, label, .stCaption {
            color: rgba(243, 240, 230, 0.92);
        }

        [data-testid="stCaptionContainer"] {
            color: rgba(243, 240, 230, 0.72);
        }

        /* 左侧设置栏 */
        [data-testid="stSidebar"] {
            background:
                linear-gradient(
                    180deg,
                    rgba(3, 20, 71, 0.98),
                    rgba(9, 56, 118, 0.96)
                );
            border-right: 1px solid rgba(195, 196, 180, 0.28);
        }

        [data-testid="stSidebar"] * {
            color: var(--ivory);
        }

        /* 表单、结果折叠栏和标签内容 */
        [data-testid="stForm"],
        [data-testid="stExpander"],
        .stTabs [data-baseweb="tab-panel"] {
            background: rgba(3, 20, 71, 0.72);
            border: 1px solid rgba(195, 196, 180, 0.32);
            border-radius: 18px;
            padding: 1.15rem;
            box-shadow:
                0 16px 36px rgba(1, 10, 38, 0.25),
                inset 0 1px 0 rgba(243, 240, 230, 0.08);
            backdrop-filter: blur(8px);
        }

        /* 输入框 */
        input, textarea {
            color: var(--ink) !important;
            background-color: rgba(243, 240, 230, 0.96) !important;
        }

        div[data-baseweb="select"] > div {
            color: var(--ink) !important;
            background-color: rgba(243, 240, 230, 0.96) !important;
            border-color: rgba(54, 130, 168, 0.65) !important;
        }

        /* 指标卡片 */
        div[data-testid="stMetric"] {
            min-height: 112px;
            padding: 14px 16px;
            background:
                linear-gradient(
                    145deg,
                    rgba(243, 240, 230, 0.96),
                    rgba(195, 196, 180, 0.92)
                );
            border: 1px solid rgba(243, 240, 230, 0.55);
            border-radius: 16px;
            box-shadow: 0 12px 25px rgba(1, 10, 38, 0.22);
        }

        div[data-testid="stMetric"] * {
            color: var(--ink) !important;
        }

        /* 主按钮 */
        .stButton > button,
        [data-testid="stFormSubmitButton"] > button {
            border: 1px solid rgba(243, 240, 230, 0.50);
            border-radius: 999px;
            color: var(--ivory);
            background:
                linear-gradient(
                    115deg,
                    var(--ocean-blue),
                    var(--light-blue)
                );
            box-shadow: 0 8px 22px rgba(1, 10, 38, 0.28);
            transition:
                transform 160ms ease,
                box-shadow 160ms ease,
                filter 160ms ease;
        }

        .stButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            color: #ffffff;
            border-color: var(--ivory);
            filter: brightness(1.10);
            transform: translateY(-2px);
            box-shadow: 0 12px 28px rgba(1, 10, 38, 0.34);
        }

        /* 标签页 */
        .stTabs [data-baseweb="tab-list"] {
            gap: 0.7rem;
        }

        .stTabs [data-baseweb="tab"] {
            color: rgba(243, 240, 230, 0.72);
            background: rgba(3, 20, 71, 0.52);
            border-radius: 999px;
            padding-left: 1.4rem;
            padding-right: 1.4rem;
        }

        .stTabs [aria-selected="true"] {
            color: var(--ivory) !important;
            background: var(--ocean-blue) !important;
        }

        /* 分隔线 */
        hr {
            border-color: rgba(195, 196, 180, 0.28) !important;
        }

        /* 首页标题卡 */
        .ocean-hero {
            position: relative;
            overflow: hidden;
            min-height: 280px;
            margin-bottom: 1.4rem;
            padding: 3.2rem 3.5rem;
            border: 1px solid rgba(243, 240, 230, 0.28);
            border-radius: 30px;
            background:
                radial-gradient(
                    ellipse at 82% 18%,
                    rgba(54, 130, 168, 0.85),
                    transparent 35%
                ),
                radial-gradient(
                    ellipse at 15% 100%,
                    rgba(9, 56, 118, 0.96),
                    transparent 48%
                ),
                linear-gradient(
                    135deg,
                    rgba(3, 20, 71, 0.96),
                    rgba(19, 91, 147, 0.90)
                );
            box-shadow: 0 24px 55px rgba(1, 10, 38, 0.34);
        }

        .ocean-hero::after {
            content: "";
            position: absolute;
            width: 430px;
            height: 430px;
            right: -110px;
            bottom: -270px;
            border: 42px double rgba(195, 196, 180, 0.12);
            border-radius: 48% 52% 45% 55%;
            transform: rotate(-12deg);
        }

        .hero-eyebrow {
            position: relative;
            z-index: 1;
            margin-bottom: 1rem;
            color: rgba(195, 196, 180, 0.88);
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.22em;
            text-transform: uppercase;
        }

        .hero-title {
            position: relative;
            z-index: 1;
            margin: 0;
            color: var(--ivory);
            font-family: Georgia, "Times New Roman", serif;
            font-size: clamp(3rem, 7vw, 6.4rem);
            font-weight: 500;
            line-height: 0.95;
            letter-spacing: -0.045em;
        }

        .hero-subtitle {
            position: relative;
            z-index: 1;
            max-width: 680px;
            margin-top: 1.4rem;
            color: rgba(243, 240, 230, 0.86);
            font-size: 1.05rem;
            line-height: 1.8;
        }

        /* 原有说明文字 */
        .source-note {
            border-left: 4px solid var(--light-blue);
            border-radius: 0 12px 12px 0;
            background: rgba(243, 240, 230, 0.90);
            color: var(--ink);
            padding: 12px 16px;
            margin: 4px 0 20px;
        }

        .simulation-note {
            color: #D9E6E8;
            font-size: 0.88rem;
            font-weight: 600;
        }

        /* 小屏幕 */
        @media (max-width: 700px) {
            .block-container {
                padding-top: 1rem;
            }

            .ocean-hero {
                min-height: 230px;
                padding: 2.4rem 1.5rem;
                border-radius: 22px;
            }

            .hero-title {
                font-size: 3.4rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def normalize_url(url: str) -> str:
    """补齐协议并拒绝明显非法地址。"""

    url = url.strip()
    if not url:
        return ""
    if not url.startswith(("http://", "https://")):
        url = f"https://{url}"
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError("链接格式不正确，请输入完整网页地址。")
    return url


@st.cache_data(ttl=900, show_spinner=False)
def fetch_page_text(url: str) -> FetchResult:
    """抓取公开网页正文；失败时返回可展示的降级说明。"""

    try:
        normalized = normalize_url(url)
        response = requests.get(
            normalized,
            timeout=REQUEST_TIMEOUT_SECONDS,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/124 Safari/537.36"
                )
            },
        )
        response.raise_for_status()
        soup = BeautifulSoup(response.text, "html.parser")
        for tag in soup(["script", "style", "noscript", "svg", "nav", "footer"]):
            tag.decompose()

        title = soup.title.get_text(" ", strip=True) if soup.title else ""
        body = " ".join(soup.stripped_strings)
        body = re.sub(r"\s+", " ", body)
        text = f"页面标题：{title}\n页面正文：{body}"[:MAX_SCRAPED_CHARS]
        if len(text) < 80:
            return FetchResult(
                text="",
                warning="网页可访问，但未提取到足够正文，将自动使用手动描述继续分析。",
            )
        return FetchResult(text=text)
    except (requests.RequestException, ValueError) as exc:
        return FetchResult(
            text="",
            warning=f"网页抓取失败（{exc}），已自动降级为手动描述模式。",
        )


def collect_source_context(source_mode: str, url_text: str) -> FetchResult:
    """根据来源模式抓取一个或多个网页。"""

    if source_mode == "纯文字" or not url_text.strip():
        return FetchResult(text="")

    urls = [line.strip() for line in url_text.splitlines() if line.strip()]
    if source_mode == "链接抓取":
        urls = urls[:1]
    else:
        urls = urls[:3]

    chunks: list[str] = []
    warnings: list[str] = []
    for url in urls:
        result = fetch_page_text(url)
        if result.text:
            chunks.append(f"来源链接：{url}\n{result.text}")
        if result.warning:
            warnings.append(result.warning)

    return FetchResult(
        text="\n\n".join(chunks)[:MAX_SCRAPED_CHARS],
        warning=" ".join(warnings),
    )


def extract_json_object(content: str) -> dict[str, Any]:
    """兼容纯 JSON 和被代码块包裹的 JSON。"""

    cleaned = content.strip()
    cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s*```$", "", cleaned)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        start = cleaned.find("{")
        end = cleaned.rfind("}")
        if start == -1 or end <= start:
            raise ValueError("模型没有返回可解析的 JSON。")
        parsed = json.loads(cleaned[start : end + 1])
    if not isinstance(parsed, dict):
        raise ValueError("模型返回的顶层结构不是 JSON 对象。")
    return parsed


def call_new_api(
    *,
    api_key: str,
    base_url: str,
    model: str,
    user_prompt: str,
) -> dict[str, Any]:
    """通过 OpenAI 兼容 SDK 调用 New API，并兼容不支持 response_format 的服务。"""

    client = OpenAI(api_key=api_key, base_url=base_url.rstrip("/"))
    common_args = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }

    try:
        response = client.chat.completions.create(
            **common_args,
            response_format={"type": "json_object"},
        )
    except AuthenticationError as exc:
        raise RuntimeError(
            "DeepSeek 拒绝了当前 API Key（401）。请不要使用 CC Switch 中的掩码值；"
            "请到 DeepSeek 开放平台重新创建 Key，并原样粘贴完整密钥。"
        ) from exc
    except APIConnectionError as exc:
        raise RuntimeError(
            "无法连接 DeepSeek API，请检查本机网络、防火墙或代理设置。"
        ) from exc
    except BadRequestError as first_error:
        # 部分 OpenAI 兼容服务未实现 response_format，自动重试普通文本模式。
        try:
            response = client.chat.completions.create(**common_args)
        except AuthenticationError as exc:
            raise RuntimeError(
                "DeepSeek 拒绝了当前 API Key（401）。请重新创建并粘贴完整密钥。"
            ) from exc
        except Exception as second_error:
            raise RuntimeError(
                "New API 调用失败。请检查 Key、Base URL、模型名称或服务余额。"
                f"\n首次请求：{first_error}\n兼容重试：{second_error}"
            ) from second_error
    except Exception as exc:
        raise RuntimeError(
            "New API 调用失败。请检查模型名称、账户余额或服务状态。"
            f"\n技术信息：{exc}"
        ) from exc

    content = response.choices[0].message.content
    if not content:
        raise ValueError("模型返回内容为空，请稍后重试。")
    return extract_json_object(content)


def normalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    """为模型偶发缺失字段提供安全默认值，避免页面直接崩溃。"""

    product = raw.get("product_analysis")
    platforms = raw.get("platform_recommendations")
    return {
        "summary": str(raw.get("summary") or "已生成初步广告测试方案。"),
        "product_analysis": product if isinstance(product, dict) else {},
        "target_users": raw.get("target_users")
        if isinstance(raw.get("target_users"), list)
        else [],
        "ad_copy": raw.get("ad_copy") if isinstance(raw.get("ad_copy"), list) else [],
        "platform_recommendations": platforms
        if isinstance(platforms, dict)
        else {"domestic": [], "overseas": []},
        "assumptions": raw.get("assumptions")
        if isinstance(raw.get("assumptions"), list)
        else [],
        "next_actions": raw.get("next_actions")
        if isinstance(raw.get("next_actions"), list)
        else [],
    }


def stable_seed(product_text: str, platform_name: str) -> int:
    """用产品与平台生成稳定随机种子，保证现场演示结果可复现。"""

    digest = hashlib.sha256(f"{product_text}|{platform_name}".encode("utf-8")).hexdigest()
    return int(digest[:12], 16)


def simulate_seven_days(
    *,
    product_text: str,
    platform: dict[str, Any],
    platform_budget: float,
    currency: str,
    unit_price: float,
) -> tuple[pd.DataFrame, dict[str, float]]:
    """生成用于产品演示的七天预测，不代表真实投放结果。"""

    platform_name = str(platform.get("name") or "未知平台")
    difficulty = str(platform.get("difficulty") or "中")
    difficulty_factor = {"低": 1.08, "中": 1.0, "高": 0.9}.get(difficulty, 1.0)
    rng = random.Random(stable_seed(product_text, platform_name))

    raw_weights = [rng.uniform(0.85, 1.15) for _ in range(7)]
    weight_sum = sum(raw_weights)
    daily_spend = [platform_budget * weight / weight_sum for weight in raw_weights]

    rows: list[dict[str, Any]] = []
    total_revenue = 0.0
    for day, spend in enumerate(daily_spend, start=1):
        learning_factor = 0.9 + day * 0.025
        cpm = rng.uniform(28, 72) / difficulty_factor
        ctr = rng.uniform(0.008, 0.026) * difficulty_factor * learning_factor
        cvr = rng.uniform(0.012, 0.055) * difficulty_factor * learning_factor
        impressions = max(1, int(spend / cpm * 1000))
        clicks = max(1, int(impressions * ctr))
        conversions = round(clicks * cvr, 1)
        revenue = conversions * unit_price if unit_price > 0 else 0.0
        total_revenue += revenue
        rows.append(
            {
                "日期": f"第 {day} 天",
                f"花费（{currency}）": round(spend, 2),
                "曝光": impressions,
                "点击": clicks,
                "CTR": f"{clicks / impressions:.2%}",
                "转化": conversions,
                f"预估收入（{currency}）": round(revenue, 2)
                if unit_price > 0
                else "未提供售价",
            }
        )

    frame = pd.DataFrame(rows)
    total_spend = float(sum(daily_spend))
    total_impressions = float(frame["曝光"].sum())
    total_clicks = float(frame["点击"].sum())
    total_conversions = float(frame["转化"].sum())
    metrics = {
        "spend": total_spend,
        "impressions": total_impressions,
        "clicks": total_clicks,
        "conversions": total_conversions,
        "cpa": total_spend / total_conversions if total_conversions else 0.0,
        "roas": total_revenue / total_spend if total_spend and unit_price > 0 else 0.0,
    }
    return frame, metrics


def render_list(items: Any, empty_text: str = "暂无") -> None:
    """统一渲染简单列表。"""

    if not isinstance(items, list) or not items:
        st.caption(empty_text)
        return
    for item in items:
        st.markdown(f"- {item}")


def render_product_analysis(result: dict[str, Any]) -> None:
    """展示产品分析。"""

    st.header("产品分析")
    product = result["product_analysis"]
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("产品定位")
        st.write(product.get("positioning") or "暂无")
    with col2:
        st.subheader("核心价值")
        st.write(product.get("core_value") or "暂无")

    col3, col4 = st.columns(2)
    with col3:
        st.subheader("核心卖点")
        render_list(product.get("selling_points"))
    with col4:
        st.subheader("风险与待验证假设")
        render_list(product.get("risks"))


def render_target_users(result: dict[str, Any]) -> None:
    """展示目标用户画像。"""

    st.header("目标用户")
    users = result["target_users"]
    if not users:
        st.info("模型暂未返回目标用户画像。")
        return
    columns = st.columns(min(3, len(users)))
    for index, user in enumerate(users):
        with columns[index % len(columns)]:
            st.subheader(str(user.get("segment") or f"客群 {index + 1}"))
            st.caption(str(user.get("features") or ""))
            st.markdown("**主要痛点**")
            render_list(user.get("pain_points"))
            st.markdown("**沟通重点**")
            st.write(user.get("message") or "暂无")


def render_ad_copy(result: dict[str, Any]) -> None:
    """展示广告语。"""

    st.header("广告语")
    copies = result["ad_copy"]
    if not copies:
        st.info("模型暂未返回广告文案。")
        return
    for index, item in enumerate(copies, start=1):
        with st.expander(
            f"{index}. {item.get('angle') or '创意方向'} · "
            f"{item.get('headline') or '未命名标题'}",
            expanded=index == 1,
        ):
            st.markdown(f"**标题：** {item.get('headline') or '暂无'}")
            st.markdown(f"**正文：** {item.get('body') or '暂无'}")
            st.markdown(f"**CTA：** {item.get('cta') or '暂无'}")


def render_platform(
    *,
    platform: dict[str, Any],
    product_text: str,
    platform_budget: float,
    currency: str,
    unit_price: float,
) -> None:
    """展示单个平台建议及其七天模拟。"""

    name = str(platform.get("name") or "未命名平台")
    st.subheader(name)
    st.write(platform.get("reason") or "暂无推荐理由")

    detail_cols = st.columns(4)
    with detail_cols[0]:
        st.markdown("**广告形式**")
        render_list(platform.get("ad_formats"))
    with detail_cols[1]:
        st.markdown("**素材要求**")
        render_list(platform.get("asset_requirements"))
    with detail_cols[2]:
        st.markdown("**制作难度**")
        st.write(platform.get("difficulty") or "中")
        st.markdown("**计费方式**")
        st.write(" / ".join(platform.get("billing_methods") or ["待确认"]))
    with detail_cols[3]:
        st.markdown("**预算建议**")
        st.write(platform.get("budget_advice") or "建议先做小预算测试")

    st.markdown(
        '<div class="simulation-note">以下为算法模拟预估，不是实际投放数据或收益承诺。</div>',
        unsafe_allow_html=True,
    )
    frame, metrics = simulate_seven_days(
        product_text=product_text,
        platform=platform,
        platform_budget=platform_budget,
        currency=currency,
        unit_price=unit_price,
    )
    metric_cols = st.columns(5)
    metric_cols[0].metric("七天预算", f"{currency} {metrics['spend']:,.0f}")
    metric_cols[1].metric("预估曝光", f"{metrics['impressions']:,.0f}")
    metric_cols[2].metric("预估点击", f"{metrics['clicks']:,.0f}")
    metric_cols[3].metric("预估转化", f"{metrics['conversions']:,.1f}")
    metric_cols[4].metric(
        "预估 CPA",
        f"{currency} {metrics['cpa']:,.2f}" if metrics["cpa"] else "暂无",
    )

    chart_frame = frame.set_index("日期")[["点击", "转化"]]
    st.line_chart(chart_frame, height=260)
    st.dataframe(frame, width="stretch", hide_index=True)
    if unit_price > 0:
        st.caption(f"基于用户输入售价计算的模拟 ROAS：{metrics['roas']:.2f}")


def render_platform_tabs(
    *,
    result: dict[str, Any],
    product_text: str,
    total_budget: float,
    currency: str,
    unit_price: float,
) -> None:
    """按国内和海外 Tab 展示平台与模拟数据。"""

    st.header("平台推荐与七天模拟")
    st.caption("每个平台使用相同总预算拆分规则，便于 Demo 中比较；上线前需替换为真实平台数据。")
    groups = result["platform_recommendations"]
    domestic = groups.get("domestic") if isinstance(groups, dict) else []
    overseas = groups.get("overseas") if isinstance(groups, dict) else []
    all_count = max(1, len(domestic or []) + len(overseas or []))
    platform_budget = total_budget / all_count

    domestic_tab, overseas_tab = st.tabs(["国内平台", "海外平台"])
    for tab, platforms in ((domestic_tab, domestic), (overseas_tab, overseas)):
        with tab:
            if not platforms:
                st.info("暂无平台建议。")
                continue
            for index, platform in enumerate(platforms):
                with st.expander(
                    f"{platform.get('name') or f'平台 {index + 1}'} · "
                    f"七天模拟预估",
                    expanded=index == 0,
                ):
                    render_platform(
                        platform=platform,
                        product_text=product_text,
                        platform_budget=platform_budget,
                        currency=currency,
                        unit_price=unit_price,
                    )


def render_summary(result: dict[str, Any]) -> None:
    """展示摘要、假设与下一步。"""

    st.header("方案摘要")
    st.success(result["summary"])
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("关键假设")
        render_list(result["assumptions"])
    with col2:
        st.subheader("下一步")
        render_list(result["next_actions"])


def render_sidebar() -> tuple[str, str, str, str]:
    """展示 API 设置，并返回当前配置。"""

    with st.sidebar:
        st.header("New API 设置")
        env_key = os.getenv("NEW_API_KEY", "")
        env_base_url = os.getenv("NEW_API_BASE_URL", "")
        env_model = os.getenv("NEW_API_MODEL", "gpt-4o-mini")

        override_key = st.text_input(
            "临时 API Key（可选）",
            value="",
            type="password",
            placeholder="服务器已配置时无需填写",
            help="仅用于本次浏览器会话；服务器中的 Key 不会发送到页面。",
        )
        api_key = override_key.strip() or env_key.strip()
        base_url = st.text_input(
            "NEW_API_BASE_URL",
            value=env_base_url,
            placeholder="https://your-provider.example/v1",
        )
        model = st.text_input("模型名称", value=env_model)
        engine_mode = st.radio(
            "分析引擎",
            ["New API 实时生成", "固定宠物水杯案例"],
            index=0,
            help="固定案例只用于检查页面，不会分析用户输入的其他商品。",
        )

        if engine_mode == "固定宠物水杯案例":
            st.warning("固定案例会忽略产品输入，只返回预置的宠物饮水杯方案。")
        elif api_key and base_url and model:
            if override_key.strip():
                st.success("正在使用本次会话的临时 API Key")
            else:
                st.success("API Key 已由服务器安全配置")
        else:
            st.warning("请填写 Key、Base URL 和模型名称后再生成。")
    return api_key.strip(), base_url.strip(), model.strip(), engine_mode


def main() -> None:
    """Streamlit 应用入口。"""

    configure_page()
    api_key, base_url, model, engine_mode = render_sidebar()
    fixed_demo_mode = engine_mode == "固定宠物水杯案例"

    # 切换分析引擎时清除旧结果，避免真实结果与固定案例互相混淆。
    previous_engine = st.session_state.get("_analysis_engine")
    if previous_engine and previous_engine != engine_mode:
        st.session_state.pop("analysis_result", None)
        st.session_state.pop("analysis_inputs", None)
    st.session_state["_analysis_engine"] = engine_mode

    st.title(APP_TITLE)
    st.caption("AI 广告策略与七天投放模拟 Demo")
    st.markdown(
        '<div class="source-note">先输入最少产品信息。平台将补全产品、客群、'
        "广告语和渠道实验；所有七天指标均为模拟预估。</div>",
        unsafe_allow_html=True,
    )
    if fixed_demo_mode:
        st.warning(
            "当前选择的是“固定宠物水杯案例”，下方产品信息不会用于生成方案。"
            "测试其他商品时，请切换到“New API 实时生成”。"
        )

    # 来源模式放在表单外，切换时页面会立即重绘并显示对应的链接输入框。
    source_mode = st.radio(
        "信息来源模式",
        ["纯文字", "链接抓取", "联网增强"],
        horizontal=True,
        help="联网增强可同时抓取最多 3 个公开参考页面，再交给模型综合分析。",
    )

    with st.form("analysis_form"):
        product_label = (
            "产品信息"
            if source_mode == "纯文字"
            else "产品补充信息（可选）"
        )
        product_text = st.text_area(
            product_label,
            height=150,
            placeholder=(
                "例如：售价、核心卖点、目标客户或你希望重点强调的信息。"
                if source_mode != "纯文字"
                else "例如：便携式宠物饮水杯，售价 29.99 美元，防漏、单手操作，"
                "希望卖给经常遛狗或携宠旅行的人。"
            ),
        )

        url_text = ""
        if source_mode == "链接抓取":
            url_text = st.text_input(
                "产品链接",
                placeholder="https://example.com/product",
            )
        elif source_mode == "联网增强":
            url_text = st.text_area(
                "参考链接（每行一个，最多 3 个）",
                height=90,
                placeholder="产品页、竞品页或公开行业资料链接",
            )

        field_cols = st.columns(4)
        with field_cols[0]:
            goal = st.selectbox(
                "广告目标",
                ["商品购买", "收集线索", "注册", "App 安装", "品牌曝光"],
            )
        with field_cols[1]:
            market = st.text_input("目标市场", value="国内与海外对比")
        with field_cols[2]:
            currency = st.selectbox("预算币种", ["¥", "$", "€"])
        with field_cols[3]:
            budget = st.number_input(
                "七天总预算",
                min_value=100.0,
                value=1000.0,
                step=100.0,
            )

        unit_price = st.number_input(
            "产品售价（可选，用于模拟收入与 ROAS）",
            min_value=0.0,
            value=0.0,
            step=10.0,
        )
        submitted = st.form_submit_button(
            "生成广告方案",
            type="primary",
            width="stretch",
        )

    if submitted:
        if source_mode == "纯文字" and not product_text.strip():
            st.error("请至少输入一句产品描述。")
        elif source_mode == "链接抓取" and not url_text.strip():
            st.error("请选择“链接抓取”后，在“产品链接”框中填写完整网址。")
        elif (
            source_mode == "联网增强"
            and not product_text.strip()
            and not url_text.strip()
        ):
            st.error("请至少填写产品补充信息或一个公开参考链接。")
        elif not fixed_demo_mode and "*" in api_key:
            st.error(
                "当前 API Key 包含星号，看起来是被隐藏后的掩码值。"
                "请到 DeepSeek 开放平台新建 Key，并粘贴创建时显示的完整密钥。"
            )
        elif not fixed_demo_mode and (not api_key or not base_url or not model):
            st.error("请在侧边栏补充 NEW_API_KEY、NEW_API_BASE_URL 和模型名称。")
        else:
            with st.status("正在生成广告方案…", expanded=True) as status:
                st.write("1/3 正在整理产品资料")
                fetch_result = collect_source_context(source_mode, url_text)
                if fetch_result.warning:
                    st.warning(fetch_result.warning)
                st.write("2/3 正在分析客群、广告语与平台形式")
                try:
                    if fixed_demo_mode:
                        raw_result = demo_result_copy()
                    else:
                        user_prompt = build_user_prompt(
                            source_mode=source_mode,
                            product_text=product_text,
                            source_context=fetch_result.text,
                            goal=goal,
                            market=market,
                            budget=budget,
                            currency=currency,
                        )
                        raw_result = call_new_api(
                            api_key=api_key,
                            base_url=base_url,
                            model=model,
                            user_prompt=user_prompt,
                        )
                    st.write("3/3 正在生成七天模拟预估")
                    st.session_state["analysis_result"] = normalize_result(raw_result)
                    st.session_state["analysis_inputs"] = {
                        "product_text": product_text,
                        "budget": budget,
                        "currency": currency,
                        "unit_price": unit_price,
                        "result_source": engine_mode,
                    }
                    status.update(label="广告方案已生成", state="complete")
                except (RuntimeError, ValueError, json.JSONDecodeError) as exc:
                    status.update(label="生成失败", state="error")
                    st.error(str(exc))
                except Exception as exc:
                    status.update(label="生成失败", state="error")
                    st.error(
                        "生成过程中出现意外错误，请检查网络与 API 配置后重试。"
                        f"\n\n技术信息：{exc}"
                    )

    result = st.session_state.get("analysis_result")
    inputs = st.session_state.get("analysis_inputs")
    if result and inputs:
        st.divider()
        st.caption(f"本次方案来源：{inputs.get('result_source', '未知')}")
        render_product_analysis(result)
        st.divider()
        render_target_users(result)
        st.divider()
        render_ad_copy(result)
        st.divider()
        render_platform_tabs(
            result=result,
            product_text=inputs["product_text"],
            total_budget=inputs["budget"],
            currency=inputs["currency"],
            unit_price=inputs["unit_price"],
        )
        st.divider()
        render_summary(result)


if __name__ == "__main__":
    main()
