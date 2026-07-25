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
from strategy_catalog import format_profile, normalize_format_id, platform_factors


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

    st.markdown(
        """
        <style>
        /*
         * Soft oil-paint theme.
         * Palette: #11284D #264B6F #101A2C #F4EFDF #D5B370
         */
        :root {
            --paint-navy: #11284D;
            --paint-blue: #264B6F;
            --paint-ink: #101A2C;
            --paint-ivory: #F4EFDF;
            --paint-gold: #D5B370;
            --paint-mist: #AAB9BF;
        }

        /* 柔和的油画底色：大色块负责层次，纹理层负责画布质感 */
        .stApp {
            background-color: var(--paint-blue) !important;
            background-image:
                radial-gradient(
                    ellipse 58% 34% at 8% 7%,
                    rgba(244, 239, 223, 0.32) 0 28%,
                    rgba(244, 239, 223, 0.10) 44%,
                    transparent 68%
                ),
                radial-gradient(
                    ellipse 48% 30% at 86% 5%,
                    rgba(213, 179, 112, 0.28) 0 26%,
                    rgba(213, 179, 112, 0.08) 48%,
                    transparent 70%
                ),
                radial-gradient(
                    ellipse 64% 38% at 18% 43%,
                    rgba(17, 40, 77, 0.64) 0 30%,
                    rgba(17, 40, 77, 0.20) 54%,
                    transparent 74%
                ),
                radial-gradient(
                    ellipse 54% 34% at 80% 42%,
                    rgba(244, 239, 223, 0.22) 0 24%,
                    rgba(170, 185, 191, 0.12) 49%,
                    transparent 72%
                ),
                radial-gradient(
                    ellipse 56% 33% at 5% 78%,
                    rgba(213, 179, 112, 0.20) 0 25%,
                    transparent 68%
                ),
                radial-gradient(
                    ellipse 72% 38% at 72% 82%,
                    rgba(17, 40, 77, 0.54) 0 31%,
                    rgba(16, 26, 44, 0.18) 55%,
                    transparent 76%
                ),
                linear-gradient(
                    145deg,
                    #5E7D92 0%,
                    #3F6680 27%,
                    #264B6F 58%,
                    #385E77 100%
                ) !important;
            background-attachment: fixed !important;
        }

        /* 微颗粒：模拟颜料颗粒与画布纤维 */
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.34;
            mix-blend-mode: soft-light;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='180' viewBox='0 0 180 180'%3E%3Cfilter id='n'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.72' numOctaves='4' seed='9' stitchTiles='stitch'/%3E%3CfeColorMatrix type='saturate' values='0'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23n)' opacity='.56'/%3E%3C/svg%3E");
        }

        /* 宽而柔和的弧线笔触，不做成过碎的小波纹 */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.26;
            mix-blend-mode: screen;
            background-image:
                repeating-radial-gradient(
                    ellipse 190px 72px at 14% 21%,
                    transparent 0 14px,
                    rgba(244, 239, 223, 0.20) 15px 17px,
                    transparent 18px 31px
                ),
                repeating-radial-gradient(
                    ellipse 240px 88px at 72% 36%,
                    transparent 0 18px,
                    rgba(213, 179, 112, 0.16) 19px 21px,
                    transparent 22px 39px
                ),
                repeating-radial-gradient(
                    ellipse 210px 78px at 39% 82%,
                    transparent 0 16px,
                    rgba(244, 239, 223, 0.14) 17px 19px,
                    transparent 20px 35px
                );
        }

        [data-testid="stHeader"] {
            background: rgba(244, 239, 223, 0.82) !important;
            border-bottom: 1px solid rgba(17, 40, 77, 0.10);
            backdrop-filter: blur(14px);
        }

        .block-container {
            position: relative;
            z-index: 2;
            max-width: 1240px;
            padding-top: 2.2rem;
            padding-bottom: 5rem;
        }

        /* 侧栏保留深色，但加入暖色与纹理，降低数字界面的生硬感 */
        [data-testid="stSidebar"] {
            background:
                linear-gradient(
                    165deg,
                    rgba(16, 26, 44, 0.98),
                    rgba(17, 40, 77, 0.96) 55%,
                    rgba(38, 75, 111, 0.96)
                ) !important;
            border-right: 1px solid rgba(213, 179, 112, 0.38);
        }

        [data-testid="stSidebar"]::before {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            opacity: 0.17;
            background-image:
                repeating-radial-gradient(
                    ellipse 120px 44px at 30% 18%,
                    transparent 0 11px,
                    rgba(244, 239, 223, 0.24) 12px 13px,
                    transparent 14px 25px
                );
        }

        [data-testid="stSidebar"] h1,
        [data-testid="stSidebar"] h2,
        [data-testid="stSidebar"] h3,
        [data-testid="stSidebar"] p,
        [data-testid="stSidebar"] label {
            color: var(--paint-ivory) !important;
        }

        /* 首页主视觉：蓝色画布、奶油色柔光、少量金色颜料 */
        .ocean-hero {
            position: relative;
            isolation: isolate;
            overflow: hidden;
            min-height: 300px;
            margin-bottom: 1.5rem;
            padding: 3.4rem 3.8rem;
            border: 1px solid rgba(244, 239, 223, 0.50);
            border-radius: 34px 28px 38px 26px;
            background:
                radial-gradient(
                    ellipse 54% 78% at 100% 5%,
                    rgba(244, 239, 223, 0.40) 0 24%,
                    rgba(213, 179, 112, 0.20) 44%,
                    transparent 68%
                ),
                radial-gradient(
                    ellipse 48% 68% at 7% 100%,
                    rgba(16, 26, 44, 0.66) 0 31%,
                    transparent 68%
                ),
                linear-gradient(
                    135deg,
                    rgba(17, 40, 77, 0.96),
                    rgba(38, 75, 111, 0.92) 61%,
                    rgba(94, 125, 146, 0.90)
                ) !important;
            box-shadow:
                0 22px 55px rgba(16, 26, 44, 0.20),
                inset 0 0 70px rgba(244, 239, 223, 0.08);
        }

        .ocean-hero::before {
            content: "";
            position: absolute;
            inset: 0;
            z-index: -1;
            opacity: 0.38;
            mix-blend-mode: soft-light;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='150' height='150'%3E%3Cfilter id='p'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.045 .42' numOctaves='3' seed='21'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23p)' opacity='.68'/%3E%3C/svg%3E");
        }

        .ocean-hero::after {
            content: "";
            position: absolute;
            z-index: -1;
            width: 520px;
            height: 330px;
            right: -95px;
            bottom: -185px;
            border: 28px double rgba(213, 179, 112, 0.28);
            border-radius: 49% 51% 46% 54%;
            transform: rotate(-8deg);
            filter: blur(0.2px);
        }

        .hero-eyebrow {
            color: var(--paint-gold) !important;
            font-size: 0.78rem;
            font-weight: 700;
            letter-spacing: 0.24em;
        }

        .hero-title {
            color: var(--paint-ivory) !important;
            font-family: Georgia, "Times New Roman", serif;
            font-weight: 500;
            text-shadow: 0 2px 18px rgba(16, 26, 44, 0.26);
        }

        .hero-subtitle {
            color: rgba(244, 239, 223, 0.92) !important;
            line-height: 1.9;
        }

        /* 奶油色内容卡片，让整体更轻、更柔和 */
        [data-testid="stForm"],
        [data-testid="stExpander"],
        .stTabs [data-baseweb="tab-panel"] {
            color: var(--paint-ink) !important;
            background:
                linear-gradient(
                    145deg,
                    rgba(244, 239, 223, 0.95),
                    rgba(244, 239, 223, 0.86)
                ) !important;
            border: 1px solid rgba(213, 179, 112, 0.48) !important;
            border-radius: 24px 18px 26px 20px !important;
            box-shadow:
                0 18px 42px rgba(16, 26, 44, 0.16),
                inset 0 1px 0 rgba(255, 255, 255, 0.72) !important;
            backdrop-filter: blur(10px);
        }

        [data-testid="stForm"] h1,
        [data-testid="stForm"] h2,
        [data-testid="stForm"] h3,
        [data-testid="stForm"] p,
        [data-testid="stForm"] label,
        [data-testid="stExpander"] h1,
        [data-testid="stExpander"] h2,
        [data-testid="stExpander"] h3,
        [data-testid="stExpander"] p,
        [data-testid="stExpander"] label,
        .stTabs [data-baseweb="tab-panel"] p,
        .stTabs [data-baseweb="tab-panel"] label {
            color: var(--paint-ink) !important;
        }

        input,
        textarea,
        div[data-baseweb="select"] > div {
            color: var(--paint-ink) !important;
            background: rgba(255, 253, 246, 0.88) !important;
            border-color: rgba(38, 75, 111, 0.22) !important;
            box-shadow: inset 0 1px 7px rgba(17, 40, 77, 0.06);
        }

        input:focus,
        textarea:focus {
            border-color: var(--paint-gold) !important;
            box-shadow: 0 0 0 2px rgba(213, 179, 112, 0.24) !important;
        }

        /* 提示条使用暖白而不是冷灰 */
        .source-note {
            color: var(--paint-ink) !important;
            background:
                linear-gradient(
                    100deg,
                    rgba(244, 239, 223, 0.98),
                    rgba(244, 239, 223, 0.88)
                ) !important;
            border-left: 6px solid var(--paint-gold) !important;
            border-radius: 6px 18px 18px 6px !important;
            box-shadow: 0 10px 28px rgba(16, 26, 44, 0.12);
        }

        /* 按钮改为柔和金色，成为页面唯一强暖色焦点 */
        .stButton > button,
        [data-testid="stFormSubmitButton"] > button {
            color: var(--paint-ink) !important;
            background:
                linear-gradient(
                    120deg,
                    #E1C58E,
                    var(--paint-gold)
                ) !important;
            border: 1px solid rgba(244, 239, 223, 0.70) !important;
            box-shadow: 0 9px 24px rgba(16, 26, 44, 0.17) !important;
        }

        .stButton > button:hover,
        [data-testid="stFormSubmitButton"] > button:hover {
            color: var(--paint-ink) !important;
            filter: brightness(1.05);
            transform: translateY(-1px);
        }

        div[data-testid="stMetric"] {
            background:
                linear-gradient(
                    145deg,
                    rgba(244, 239, 223, 0.98),
                    rgba(225, 197, 142, 0.72)
                ) !important;
            border: 1px solid rgba(213, 179, 112, 0.56) !important;
            border-radius: 20px 15px 22px 16px !important;
            box-shadow: 0 13px 30px rgba(16, 26, 44, 0.14) !important;
        }

        div[data-testid="stMetric"] * {
            color: var(--paint-ink) !important;
        }

        .stTabs [data-baseweb="tab"] {
            color: rgba(244, 239, 223, 0.88) !important;
            background: rgba(17, 40, 77, 0.54) !important;
            border: 1px solid rgba(244, 239, 223, 0.22);
        }

        .stTabs [aria-selected="true"] {
            color: var(--paint-ink) !important;
            background: var(--paint-gold) !important;
        }

        hr {
            border-color: rgba(244, 239, 223, 0.38) !important;
        }

        @media (max-width: 700px) {
            .ocean-hero {
                min-height: 250px;
                padding: 2.5rem 1.6rem;
                border-radius: 25px 20px 28px 20px;
            }

            .hero-title {
                font-size: 3.3rem;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Result cards move naturally with the document while keeping
         * every generated section readable over the painted background.
         */
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) {
            position: relative;
            overflow: hidden;
            margin: 1rem 0 1.6rem;
            padding: 0.35rem;
            color: #101A2C !important;
            background:
                radial-gradient(
                    ellipse 52% 90% at 100% 0%,
                    rgba(213, 179, 112, 0.36),
                    transparent 68%
                ),
                linear-gradient(
                    135deg,
                    rgba(244, 239, 223, 0.97),
                    rgba(235, 220, 183, 0.94)
                ) !important;
            border: 1px solid rgba(213, 179, 112, 0.82) !important;
            border-left: 7px solid #D5B370 !important;
            border-radius: 26px 18px 28px 20px !important;
            box-shadow:
                0 18px 42px rgba(16, 26, 44, 0.16),
                inset 0 1px 0 rgba(255, 255, 255, 0.78) !important;
            backdrop-filter: blur(12px);
        }

        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        )::before {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            opacity: 0.10;
            background-image:
                repeating-radial-gradient(
                    ellipse 170px 58px at 20% 24%,
                    transparent 0 12px,
                    rgba(17, 40, 77, 0.28) 13px 14px,
                    transparent 15px 27px
                );
        }

        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) > div {
            position: relative;
            z-index: 1;
        }

        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) h1,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) h2,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) h3,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) h4,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) p,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) li,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) label,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) span,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) div[data-testid="stCaptionContainer"] {
            color: #101A2C !important;
        }

        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) h2 {
            color: #11284D !important;
            padding-bottom: 0.55rem;
            border-bottom: 2px solid rgba(213, 179, 112, 0.62);
        }

        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) h3 {
            color: #264B6F !important;
        }

        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) hr {
            border-color: rgba(38, 75, 111, 0.20) !important;
        }

        .result-card-marker {
            display: none;
        }

        @media (max-width: 700px) {
            div[data-testid="stVerticalBlock"]:has(
                > div[data-testid="stElementContainer"] .result-card-marker
            ) {
                border-left-width: 4px !important;
                border-radius: 20px 16px 22px 16px !important;
            }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Fine Chinese water-wave pattern.
         * The SVG displacement filter gives each stroke a fibrous,
         * hand-torn edge instead of a perfectly smooth digital curve.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.23;
            mix-blend-mode: soft-light;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='360' height='180' viewBox='0 0 360 180'%3E%3Cfilter id='rough' x='-20%25' y='-30%25' width='140%25' height='160%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.035 .22' numOctaves='2' seed='11' result='noise'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='noise' scale='1.8' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='1.15' stroke-linecap='round' stroke-linejoin='round' opacity='.76' filter='url(%23rough)'%3E%3Cpath d='M-48 72 C2 27 60 27 110 72 S212 117 270 72 S370 27 414 72'/%3E%3Cpath d='M-48 80 C2 35 60 35 110 80 S212 125 270 80 S370 35 414 80'/%3E%3Cpath d='M-48 88 C2 43 60 43 110 88 S212 133 270 88 S370 43 414 88'/%3E%3Cpath d='M-48 96 C2 51 60 51 110 96 S212 141 270 96 S370 51 414 96'/%3E%3Cpath d='M-48 104 C2 59 60 59 110 104 S212 149 270 104 S370 59 414 104'/%3E%3Cpath d='M63 72 C82 49 116 51 125 70 C133 87 117 101 101 94 C88 88 90 74 103 69 C111 66 118 71 116 78'/%3E%3Cpath d='M224 72 C245 46 279 49 289 69 C297 87 280 102 264 94 C250 87 253 72 266 68 C275 65 282 71 279 79'/%3E%3Cpath d='M-20 151 C25 113 72 113 116 151 S205 189 253 151 S337 113 382 151'/%3E%3Cpath d='M-20 159 C25 121 72 121 116 159 S205 197 253 159 S337 121 382 159'/%3E%3Cpath d='M-20 167 C25 129 72 129 116 167 S205 205 253 167 S337 129 382 167'/%3E%3C/g%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.7' opacity='.48' filter='url(%23rough)'%3E%3Cpath d='M-50 109 C0 64 59 64 110 109 S213 154 270 109 S370 64 415 109'/%3E%3Cpath d='M-20 175 C25 137 72 137 116 175 S205 213 253 175 S337 137 382 175'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 360px 180px !important;
            background-repeat: repeat !important;
        }

        /* 侧栏使用更稀疏的同款水纹 */
        [data-testid="stSidebar"]::before {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            opacity: 0.12;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='300' height='150' viewBox='0 0 300 150'%3E%3Cfilter id='r'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.04 .24' numOctaves='2' seed='17' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='1.6'/%3E%3C/filter%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='1' opacity='.72' filter='url(%23r)'%3E%3Cpath d='M-35 60 C10 20 55 20 98 60 S184 100 232 60 S318 20 342 60'/%3E%3Cpath d='M-35 68 C10 28 55 28 98 68 S184 108 232 68 S318 28 342 68'/%3E%3Cpath d='M-35 76 C10 36 55 36 98 76 S184 116 232 76 S318 36 342 76'/%3E%3Cpath d='M54 60 C73 39 103 41 110 58 C116 73 103 84 90 79 C78 74 81 61 93 58'/%3E%3Cpath d='M-15 132 C26 97 67 97 107 132 S188 167 231 132 S307 97 330 132'/%3E%3Cpath d='M-15 140 C26 105 67 105 107 140 S188 175 231 140 S307 105 330 140'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 300px 150px !important;
            background-repeat: repeat !important;
        }

        /* 去掉标题卡右下角的同心圆，改成一块毛边金色纸片 */
        .ocean-hero::after {
            content: "";
            position: absolute;
            z-index: -1;
            width: 430px;
            height: 118px;
            right: -36px;
            bottom: 24px;
            border: 0 !important;
            border-radius: 0 !important;
            background:
                linear-gradient(
                    100deg,
                    rgba(213, 179, 112, 0),
                    rgba(213, 179, 112, 0.34) 35%,
                    rgba(244, 239, 223, 0.22)
                );
            clip-path: polygon(
                0 27%, 4% 23%, 8% 28%, 13% 21%, 18% 25%,
                24% 19%, 30% 24%, 36% 18%, 43% 22%, 49% 17%,
                56% 23%, 63% 18%, 70% 24%, 77% 19%, 84% 25%,
                91% 20%, 100% 26%, 100% 78%, 94% 82%, 87% 77%,
                80% 84%, 73% 79%, 66% 85%, 58% 80%, 51% 86%,
                44% 81%, 37% 87%, 30% 80%, 23% 85%, 16% 79%,
                9% 84%, 3% 78%
            );
            transform: rotate(-5deg);
            filter: blur(0.35px);
            opacity: 0.78;
        }

        /* 浅金结果卡只保留纸纤维，不再叠加圆形纹路 */
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        )::before {
            content: "";
            position: absolute;
            inset: 0;
            pointer-events: none;
            opacity: 0.13;
            mix-blend-mode: multiply;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='170' height='170'%3E%3Cfilter id='f'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.82 .08' numOctaves='3' seed='23'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' filter='url(%23f)' opacity='.45'/%3E%3C/svg%3E") !important;
            background-size: 170px 170px !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Final canvas treatment:
         * indigo-to-mist painted ground with fine, interlaced water lines.
         */
        .stApp {
            background-color: #11284D !important;
            background-image:
                radial-gradient(
                    ellipse 58% 48% at 94% 7%,
                    rgba(244, 239, 223, 0.46) 0 18%,
                    rgba(170, 185, 191, 0.30) 40%,
                    transparent 72%
                ),
                radial-gradient(
                    ellipse 62% 44% at 73% 55%,
                    rgba(94, 125, 146, 0.40) 0 24%,
                    transparent 70%
                ),
                radial-gradient(
                    ellipse 54% 40% at 7% 84%,
                    rgba(16, 26, 44, 0.68) 0 28%,
                    transparent 72%
                ),
                linear-gradient(
                    104deg,
                    #101A2C 0%,
                    #11284D 27%,
                    #1C3B61 51%,
                    #456A82 76%,
                    #94A7AD 100%
                ) !important;
            background-attachment: fixed !important;
        }

        /* 横向油彩刷痕：细、密、轻微断续 */
        .stApp::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.31;
            mix-blend-mode: soft-light;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='520' height='260' viewBox='0 0 520 260'%3E%3Cfilter id='brush' x='-10%25' y='-20%25' width='120%25' height='140%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.006 .16' numOctaves='4' seed='31' result='grain'/%3E%3CfeColorMatrix in='grain' type='saturate' values='0' result='mono'/%3E%3CfeGaussianBlur in='mono' stdDeviation='1.1 .16'/%3E%3C/filter%3E%3Crect width='100%25' height='100%25' fill='%23F4EFDF' filter='url(%23brush)' opacity='.68'/%3E%3C/svg%3E") !important;
            background-size: 520px 260px !important;
            background-repeat: repeat !important;
        }

        /*
         * Dense Chinese-inspired water pattern.
         * Three wave fields cross at different angles. The displacement
         * filter keeps the thin lines fibrous instead of mechanically smooth.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.20;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='440' height='260' viewBox='0 0 440 260'%3E%3Cdefs%3E%3Cpath id='wave' d='M-100 36 C-52 3 -2 3 46 36 S144 69 196 36 S296 3 350 36 S450 69 510 36'/%3E%3Cfilter id='fray' x='-30%25' y='-50%25' width='160%25' height='200%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.055 .28' numOctaves='2' seed='19' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='1.35' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3C/g%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.68' stroke-linecap='round' opacity='.72' filter='url(%23fray)'%3E%3Cg%3E%3Cuse href='%23wave' y='0'/%3E%3Cuse href='%23wave' y='4'/%3E%3Cuse href='%23wave' y='8'/%3E%3Cuse href='%23wave' y='12'/%3E%3Cuse href='%23wave' y='16'/%3E%3Cuse href='%23wave' y='20'/%3E%3Cuse href='%23wave' y='68'/%3E%3Cuse href='%23wave' y='72'/%3E%3Cuse href='%23wave' y='76'/%3E%3Cuse href='%23wave' y='80'/%3E%3Cuse href='%23wave' y='84'/%3E%3Cuse href='%23wave' y='88'/%3E%3Cuse href='%23wave' y='136'/%3E%3Cuse href='%23wave' y='140'/%3E%3Cuse href='%23wave' y='144'/%3E%3Cuse href='%23wave' y='148'/%3E%3Cuse href='%23wave' y='152'/%3E%3Cuse href='%23wave' y='156'/%3E%3Cuse href='%23wave' y='204'/%3E%3Cuse href='%23wave' y='208'/%3E%3Cuse href='%23wave' y='212'/%3E%3Cuse href='%23wave' y='216'/%3E%3Cuse href='%23wave' y='220'/%3E%3Cuse href='%23wave' y='224'/%3E%3C/g%3E%3Cg transform='rotate(-17 220 130)' opacity='.52'%3E%3Cuse href='%23wave' y='26'/%3E%3Cuse href='%23wave' y='30'/%3E%3Cuse href='%23wave' y='34'/%3E%3Cuse href='%23wave' y='38'/%3E%3Cuse href='%23wave' y='42'/%3E%3Cuse href='%23wave' y='110'/%3E%3Cuse href='%23wave' y='114'/%3E%3Cuse href='%23wave' y='118'/%3E%3Cuse href='%23wave' y='122'/%3E%3Cuse href='%23wave' y='126'/%3E%3Cuse href='%23wave' y='194'/%3E%3Cuse href='%23wave' y='198'/%3E%3Cuse href='%23wave' y='202'/%3E%3Cuse href='%23wave' y='206'/%3E%3Cuse href='%23wave' y='210'/%3E%3C/g%3E%3Cg transform='rotate(16 220 130)' opacity='.40'%3E%3Cuse href='%23wave' y='52'/%3E%3Cuse href='%23wave' y='56'/%3E%3Cuse href='%23wave' y='60'/%3E%3Cuse href='%23wave' y='64'/%3E%3Cuse href='%23wave' y='68'/%3E%3Cuse href='%23wave' y='164'/%3E%3Cuse href='%23wave' y='168'/%3E%3Cuse href='%23wave' y='172'/%3E%3Cuse href='%23wave' y='176'/%3E%3Cuse href='%23wave' y='180'/%3E%3C/g%3E%3Cpath d='M42 36 C59 18 87 20 94 35 C100 48 88 58 76 53 C66 49 68 38 78 35 C85 33 90 37 88 43'/%3E%3Cpath d='M280 172 C298 151 329 153 337 170 C344 185 330 197 317 190 C306 185 309 173 320 169 C327 167 333 172 330 178'/%3E%3C/g%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.52' opacity='.42' filter='url(%23fray)' transform='rotate(-8 220 130)'%3E%3Cuse href='%23wave' y='96'/%3E%3Cuse href='%23wave' y='101'/%3E%3Cuse href='%23wave' y='106'/%3E%3Cuse href='%23wave' y='184'/%3E%3Cuse href='%23wave' y='189'/%3E%3Cuse href='%23wave' y='194'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 440px 260px !important;
            background-repeat: repeat !important;
        }

        /* 右侧雾色撕纸层，呼应参考图但不遮挡正文 */
        [data-testid="stAppViewContainer"]::after {
            content: "";
            position: fixed;
            z-index: 0;
            pointer-events: none;
            width: 58vw;
            height: 30vh;
            min-height: 220px;
            right: -4vw;
            bottom: 5vh;
            opacity: 0.17;
            background:
                linear-gradient(
                    105deg,
                    rgba(213, 179, 112, 0.16),
                    rgba(244, 239, 223, 0.72)
                );
            clip-path: polygon(
                0 38%, 5% 32%, 10% 35%, 15% 27%, 21% 31%,
                27% 23%, 33% 28%, 39% 20%, 46% 25%, 52% 17%,
                59% 22%, 66% 14%, 73% 19%, 80% 11%, 87% 16%,
                94% 8%, 100% 12%, 100% 82%, 93% 78%, 86% 84%,
                79% 79%, 72% 87%, 65% 82%, 58% 89%, 51% 83%,
                44% 91%, 37% 85%, 30% 92%, 23% 86%, 16% 94%,
                9% 88%, 3% 93%
            );
            filter: blur(0.45px);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /* Validated dense interlaced wave tile; kept last in the cascade. */
        [data-testid="stAppViewContainer"]::before {
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='440' height='260' viewBox='0 0 440 260'%3E%3Cdefs%3E%3Cpath id='w' d='M-100 36 C-52 3 -2 3 46 36 S144 69 196 36 S296 3 350 36 S450 69 510 36'/%3E%3Cfilter id='f' x='-30%25' y='-50%25' width='160%25' height='200%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.055 .28' numOctaves='2' seed='19' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='1.35' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3C/defs%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.68' stroke-linecap='round' opacity='.72' filter='url(%23f)'%3E%3Cg%3E%3Cuse href='%23w' y='0'/%3E%3Cuse href='%23w' y='4'/%3E%3Cuse href='%23w' y='8'/%3E%3Cuse href='%23w' y='12'/%3E%3Cuse href='%23w' y='16'/%3E%3Cuse href='%23w' y='20'/%3E%3Cuse href='%23w' y='64'/%3E%3Cuse href='%23w' y='68'/%3E%3Cuse href='%23w' y='72'/%3E%3Cuse href='%23w' y='76'/%3E%3Cuse href='%23w' y='80'/%3E%3Cuse href='%23w' y='84'/%3E%3Cuse href='%23w' y='128'/%3E%3Cuse href='%23w' y='132'/%3E%3Cuse href='%23w' y='136'/%3E%3Cuse href='%23w' y='140'/%3E%3Cuse href='%23w' y='144'/%3E%3Cuse href='%23w' y='148'/%3E%3Cuse href='%23w' y='192'/%3E%3Cuse href='%23w' y='196'/%3E%3Cuse href='%23w' y='200'/%3E%3Cuse href='%23w' y='204'/%3E%3Cuse href='%23w' y='208'/%3E%3Cuse href='%23w' y='212'/%3E%3C/g%3E%3Cg transform='rotate(-18 220 130)' opacity='.54'%3E%3Cuse href='%23w' y='25'/%3E%3Cuse href='%23w' y='29'/%3E%3Cuse href='%23w' y='33'/%3E%3Cuse href='%23w' y='37'/%3E%3Cuse href='%23w' y='41'/%3E%3Cuse href='%23w' y='103'/%3E%3Cuse href='%23w' y='107'/%3E%3Cuse href='%23w' y='111'/%3E%3Cuse href='%23w' y='115'/%3E%3Cuse href='%23w' y='119'/%3E%3Cuse href='%23w' y='181'/%3E%3Cuse href='%23w' y='185'/%3E%3Cuse href='%23w' y='189'/%3E%3Cuse href='%23w' y='193'/%3E%3Cuse href='%23w' y='197'/%3E%3C/g%3E%3Cg transform='rotate(17 220 130)' opacity='.42'%3E%3Cuse href='%23w' y='48'/%3E%3Cuse href='%23w' y='52'/%3E%3Cuse href='%23w' y='56'/%3E%3Cuse href='%23w' y='60'/%3E%3Cuse href='%23w' y='64'/%3E%3Cuse href='%23w' y='150'/%3E%3Cuse href='%23w' y='154'/%3E%3Cuse href='%23w' y='158'/%3E%3Cuse href='%23w' y='162'/%3E%3Cuse href='%23w' y='166'/%3E%3C/g%3E%3Cpath d='M42 36 C59 18 87 20 94 35 C100 48 88 58 76 53 C66 49 68 38 78 35 C85 33 90 37 88 43'/%3E%3Cpath d='M280 170 C298 150 329 152 337 169 C344 184 330 196 317 189 C306 184 309 172 320 168 C327 166 333 171 330 177'/%3E%3C/g%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.52' opacity='.40' filter='url(%23f)' transform='rotate(-8 220 130)'%3E%3Cuse href='%23w' y='91'/%3E%3Cuse href='%23w' y='96'/%3E%3Cuse href='%23w' y='101'/%3E%3Cuse href='%23w' y='215'/%3E%3Cuse href='%23w' y='220'/%3E%3Cuse href='%23w' y='225'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 440px 260px !important;
            background-repeat: repeat !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Seamless staggered Chinese wave field.
         * Alternating rows interlock like the traditional pattern, while
         * the mask makes the complete field softly emerge and disappear.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: -3%;
            z-index: 0;
            pointer-events: none;
            opacity: 0.22;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='128' viewBox='0 0 240 128'%3E%3Cfilter id='edge' x='-25%25' y='-30%25' width='150%25' height='160%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.08 .34' numOctaves='2' seed='37' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.9' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.62' stroke-linecap='round' opacity='.74' filter='url(%23edge)'%3E%3Cpath d='M-120 32 Q-60 0 0 32 T120 32 T240 32 T360 32'/%3E%3Cpath d='M-120 36 Q-60 4 0 36 T120 36 T240 36 T360 36'/%3E%3Cpath d='M-120 40 Q-60 8 0 40 T120 40 T240 40 T360 40'/%3E%3Cpath d='M-120 44 Q-60 12 0 44 T120 44 T240 44 T360 44'/%3E%3Cpath d='M-120 48 Q-60 16 0 48 T120 48 T240 48 T360 48'/%3E%3Cpath d='M-120 52 Q-60 20 0 52 T120 52 T240 52 T360 52'/%3E%3Cpath d='M-60 96 Q0 64 60 96 T180 96 T300 96'/%3E%3Cpath d='M-60 100 Q0 68 60 100 T180 100 T300 100'/%3E%3Cpath d='M-60 104 Q0 72 60 104 T180 104 T300 104'/%3E%3Cpath d='M-60 108 Q0 76 60 108 T180 108 T300 108'/%3E%3Cpath d='M-60 112 Q0 80 60 112 T180 112 T300 112'/%3E%3Cpath d='M-60 116 Q0 84 60 116 T180 116 T300 116'/%3E%3C/g%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.48' opacity='.38' filter='url(%23edge)'%3E%3Cpath d='M-120 56 Q-60 24 0 56 T120 56 T240 56 T360 56'/%3E%3Cpath d='M-60 120 Q0 88 60 120 T180 120 T300 120'/%3E%3Cpath d='M27 75 C39 63 56 64 62 74 C67 83 59 91 50 87 C43 84 45 76 52 74'/%3E%3Cpath d='M147 11 C159 -1 176 0 182 10 C187 19 179 27 170 23 C163 20 165 12 172 10'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 240px 128px !important;
            background-repeat: repeat !important;
            -webkit-mask-image:
                radial-gradient(
                    ellipse 96% 86% at 50% 45%,
                    #000 0%,
                    rgba(0, 0, 0, 0.96) 45%,
                    rgba(0, 0, 0, 0.62) 70%,
                    transparent 100%
                );
            mask-image:
                radial-gradient(
                    ellipse 96% 86% at 50% 45%,
                    #000 0%,
                    rgba(0, 0, 0, 0.96) 45%,
                    rgba(0, 0, 0, 0.62) 70%,
                    transparent 100%
                );
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /* Tightly interlocked rows with no empty bands between wave groups. */
        [data-testid="stAppViewContainer"]::before {
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='240' height='96' viewBox='0 0 240 96'%3E%3Cfilter id='e' x='-25%25' y='-35%25' width='150%25' height='170%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.08 .34' numOctaves='2' seed='37' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.9' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.62' stroke-linecap='round' opacity='.74' filter='url(%23e)'%3E%3Cpath d='M-120 24 Q-60 -4 0 24 T120 24 T240 24 T360 24'/%3E%3Cpath d='M-120 28 Q-60 0 0 28 T120 28 T240 28 T360 28'/%3E%3Cpath d='M-120 32 Q-60 4 0 32 T120 32 T240 32 T360 32'/%3E%3Cpath d='M-120 36 Q-60 8 0 36 T120 36 T240 36 T360 36'/%3E%3Cpath d='M-120 40 Q-60 12 0 40 T120 40 T240 40 T360 40'/%3E%3Cpath d='M-120 44 Q-60 16 0 44 T120 44 T240 44 T360 44'/%3E%3Cpath d='M-60 72 Q0 36 60 72 T180 72 T300 72'/%3E%3Cpath d='M-60 76 Q0 40 60 76 T180 76 T300 76'/%3E%3Cpath d='M-60 80 Q0 44 60 80 T180 80 T300 80'/%3E%3Cpath d='M-60 84 Q0 48 60 84 T180 84 T300 84'/%3E%3Cpath d='M-60 88 Q0 52 60 88 T180 88 T300 88'/%3E%3Cpath d='M-60 92 Q0 56 60 92 T180 92 T300 92'/%3E%3C/g%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.48' opacity='.36' filter='url(%23e)'%3E%3Cpath d='M-120 48 Q-60 20 0 48 T120 48 T240 48 T360 48'/%3E%3Cpath d='M-60 94 Q0 58 60 94 T180 94 T300 94'/%3E%3Cpath d='M27 55 C39 43 56 44 62 54 C67 63 59 71 50 67 C43 64 45 56 52 54'/%3E%3Cpath d='M147 7 C159 -5 176 -4 182 6 C187 15 179 23 170 19 C163 16 165 8 172 6'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 240px 96px !important;
            background-repeat: repeat !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Full-coverage traditional staggered wave lattice.
         * No fade mask and no empty wave bands.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.24;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='180' height='72' viewBox='0 0 180 72'%3E%3Cfilter id='r' x='-30%25' y='-40%25' width='160%25' height='180%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.11 .38' numOctaves='2' seed='41' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.72' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.58' stroke-linecap='round' opacity='.78' filter='url(%23r)'%3E%3Cpath d='M-90 18 Q-45 -8 0 18 T90 18 T180 18 T270 18'/%3E%3Cpath d='M-90 21 Q-45 -5 0 21 T90 21 T180 21 T270 21'/%3E%3Cpath d='M-90 24 Q-45 -2 0 24 T90 24 T180 24 T270 24'/%3E%3Cpath d='M-90 27 Q-45 1 0 27 T90 27 T180 27 T270 27'/%3E%3Cpath d='M-90 30 Q-45 4 0 30 T90 30 T180 30 T270 30'/%3E%3Cpath d='M-90 33 Q-45 7 0 33 T90 33 T180 33 T270 33'/%3E%3Cpath d='M-45 54 Q0 28 45 54 T135 54 T225 54'/%3E%3Cpath d='M-45 57 Q0 31 45 57 T135 57 T225 57'/%3E%3Cpath d='M-45 60 Q0 34 45 60 T135 60 T225 60'/%3E%3Cpath d='M-45 63 Q0 37 45 63 T135 63 T225 63'/%3E%3Cpath d='M-45 66 Q0 40 45 66 T135 66 T225 66'/%3E%3Cpath d='M-45 69 Q0 43 45 69 T135 69 T225 69'/%3E%3C/g%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.42' opacity='.42' filter='url(%23r)'%3E%3Cpath d='M-90 36 Q-45 10 0 36 T90 36 T180 36 T270 36'/%3E%3Cpath d='M-45 71 Q0 45 45 71 T135 71 T225 71'/%3E%3Cpath d='M20 42 Q45 25 70 42 Q45 34 20 42'/%3E%3Cpath d='M110 6 Q135 -11 160 6 Q135 -2 110 6'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 180px 72px !important;
            background-repeat: repeat !important;
            background-position: 0 0 !important;
            -webkit-mask-image: none !important;
            mask-image: none !important;
            filter:
                sepia(0.92)
                saturate(1.32)
                hue-rotate(352deg)
                brightness(0.96);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Compact seigaiha / fish-scale lattice.
         * 48 × 28 px cells, staggered by half a cell on alternating rows.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.27;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='48' height='28' viewBox='0 0 48 28'%3E%3Cfilter id='f' x='-35%25' y='-45%25' width='170%25' height='190%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.18 .52' numOctaves='2' seed='47' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.34' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.46' stroke-linecap='round' opacity='.80' filter='url(%23f)'%3E%3Cpath d='M-24 14 Q0 -10 24 14 M24 14 Q48 -10 72 14'/%3E%3Cpath d='M-24 14 Q0 -6 24 14 M24 14 Q48 -6 72 14'/%3E%3Cpath d='M-24 14 Q0 -2 24 14 M24 14 Q48 -2 72 14'/%3E%3Cpath d='M-24 14 Q0 2 24 14 M24 14 Q48 2 72 14'/%3E%3Cpath d='M-24 14 Q0 6 24 14 M24 14 Q48 6 72 14'/%3E%3Cpath d='M-24 14 Q0 10 24 14 M24 14 Q48 10 72 14'/%3E%3Cpath d='M0 28 Q24 4 48 28'/%3E%3Cpath d='M0 28 Q24 8 48 28'/%3E%3Cpath d='M0 28 Q24 12 48 28'/%3E%3Cpath d='M0 28 Q24 16 48 28'/%3E%3Cpath d='M0 28 Q24 20 48 28'/%3E%3Cpath d='M0 28 Q24 24 48 28'/%3E%3C/g%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.34' opacity='.44' filter='url(%23f)'%3E%3Cpath d='M-24 14 Q0 8 24 14 M24 14 Q48 8 72 14'/%3E%3Cpath d='M0 28 Q24 22 48 28'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 48px 28px !important;
            background-repeat: repeat !important;
            background-position: 0 0 !important;
            -webkit-mask-image: none !important;
            mask-image: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Fully interlocked fish-scale mesh.
         * Upward and downward arches share their edge nodes, so every
         * tile connects seamlessly on all four sides.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.27;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='48' height='32' viewBox='0 0 48 32'%3E%3Cfilter id='f' x='-35%25' y='-25%25' width='170%25' height='150%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.18 .48' numOctaves='2' seed='53' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.30' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.45' stroke-linecap='round' stroke-linejoin='round' opacity='.80' filter='url(%23f)'%3E%3Cpath d='M-24 0 Q0 30 24 0 M24 0 Q48 30 72 0'/%3E%3Cpath d='M-24 0 Q0 25 24 0 M24 0 Q48 25 72 0'/%3E%3Cpath d='M-24 0 Q0 20 24 0 M24 0 Q48 20 72 0'/%3E%3Cpath d='M-24 0 Q0 15 24 0 M24 0 Q48 15 72 0'/%3E%3Cpath d='M-24 0 Q0 10 24 0 M24 0 Q48 10 72 0'/%3E%3Cpath d='M-24 0 Q0 5 24 0 M24 0 Q48 5 72 0'/%3E%3Cpath d='M0 32 Q24 2 48 32'/%3E%3Cpath d='M0 32 Q24 7 48 32'/%3E%3Cpath d='M0 32 Q24 12 48 32'/%3E%3Cpath d='M0 32 Q24 17 48 32'/%3E%3Cpath d='M0 32 Q24 22 48 32'/%3E%3Cpath d='M0 32 Q24 27 48 32'/%3E%3C/g%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.32' opacity='.40' filter='url(%23f)'%3E%3Cpath d='M-24 0 Q0 18 24 0 M24 0 Q48 18 72 0'/%3E%3Cpath d='M0 32 Q24 14 48 32'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 48px 32px !important;
            background-repeat: repeat !important;
            background-position: 0 0 !important;
            -webkit-mask-image: none !important;
            mask-image: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Layered wave rows: each 32 px-high crest is overlapped by the
         * following row by 11 px (about one third), with a half-wave offset.
         * The dark filled crest masks the lower part of the row behind it.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.30;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='42' viewBox='0 0 96 42'%3E%3Cdefs%3E%3Cfilter id='f' x='-35%25' y='-25%25' width='170%25' height='150%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.17 .46' numOctaves='2' seed='59' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.30' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg id='crest'%3E%3Cpath d='M-24 32 Q0 -4 24 32 Z' fill='%23101A2C' fill-opacity='.96'/%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.46' stroke-linecap='round' stroke-linejoin='round' opacity='.82' filter='url(%23f)'%3E%3Cpath d='M-24 32 Q0 -4 24 32'/%3E%3Cpath d='M-24 32 Q0 2 24 32'/%3E%3Cpath d='M-24 32 Q0 8 24 32'/%3E%3Cpath d='M-24 32 Q0 14 24 32'/%3E%3Cpath d='M-24 32 Q0 20 24 32'/%3E%3Cpath d='M-24 32 Q0 26 24 32'/%3E%3C/g%3E%3Cpath d='M-24 32 Q0 17 24 32' fill='none' stroke='%23D5B370' stroke-width='.32' opacity='.42'/%3E%3C/g%3E%3C/defs%3E%3Cg%3E%3Cuse href='%23crest' x='24' y='-21'/%3E%3Cuse href='%23crest' x='72' y='-21'/%3E%3Cuse href='%23crest' x='0' y='0'/%3E%3Cuse href='%23crest' x='48' y='0'/%3E%3Cuse href='%23crest' x='96' y='0'/%3E%3Cuse href='%23crest' x='24' y='21'/%3E%3Cuse href='%23crest' x='72' y='21'/%3E%3Cuse href='%23crest' x='0' y='42'/%3E%3Cuse href='%23crest' x='48' y='42'/%3E%3Cuse href='%23crest' x='96' y='42'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 96px 42px !important;
            background-repeat: repeat !important;
            background-position: 0 0 !important;
            -webkit-mask-image: none !important;
            mask-image: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Exact one-third vertical overlap:
         * crest height 36 px, row step 24 px, overlap 12 px.
         * Alternate rows remain shifted 24 px so peaks meet valleys.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.30;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='48' viewBox='0 0 96 48'%3E%3Cdefs%3E%3Cfilter id='f' x='-35%25' y='-25%25' width='170%25' height='150%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.17 .46' numOctaves='2' seed='61' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.30' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg id='crest'%3E%3Cpath d='M-24 32 Q0 -4 24 32 Z' fill='%23101A2C' fill-opacity='.96'/%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.46' stroke-linecap='round' stroke-linejoin='round' opacity='.82' filter='url(%23f)'%3E%3Cpath d='M-24 32 Q0 -4 24 32'/%3E%3Cpath d='M-24 32 Q0 2 24 32'/%3E%3Cpath d='M-24 32 Q0 8 24 32'/%3E%3Cpath d='M-24 32 Q0 14 24 32'/%3E%3Cpath d='M-24 32 Q0 20 24 32'/%3E%3Cpath d='M-24 32 Q0 26 24 32'/%3E%3C/g%3E%3Cpath d='M-24 32 Q0 17 24 32' fill='none' stroke='%23D5B370' stroke-width='.32' opacity='.42'/%3E%3C/g%3E%3C/defs%3E%3Cg%3E%3Cuse href='%23crest' x='24' y='-24'/%3E%3Cuse href='%23crest' x='72' y='-24'/%3E%3Cuse href='%23crest' x='0' y='0'/%3E%3Cuse href='%23crest' x='48' y='0'/%3E%3Cuse href='%23crest' x='96' y='0'/%3E%3Cuse href='%23crest' x='24' y='24'/%3E%3Cuse href='%23crest' x='72' y='24'/%3E%3Cuse href='%23crest' x='0' y='48'/%3E%3Cuse href='%23crest' x='48' y='48'/%3E%3Cuse href='%23crest' x='96' y='48'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 96px 48px !important;
            background-repeat: repeat !important;
            background-position: 0 0 !important;
            -webkit-mask-image: none !important;
            mask-image: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Strong visible overlap:
         * 36 px crest height with a 12 px row step. The next crest reaches
         * one third of the way down from the previous crest's top.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.31;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='24' viewBox='0 0 96 24'%3E%3Cdefs%3E%3Cfilter id='f' x='-35%25' y='-25%25' width='170%25' height='150%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.17 .46' numOctaves='2' seed='67' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.28' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg id='c'%3E%3Cpath d='M-24 32 Q0 -4 24 32 Z' fill='%23101A2C' fill-opacity='.97'/%3E%3Cg fill='none' stroke='%23F4EFDF' stroke-width='.45' stroke-linecap='round' stroke-linejoin='round' opacity='.84' filter='url(%23f)'%3E%3Cpath d='M-24 32 Q0 -4 24 32'/%3E%3Cpath d='M-24 32 Q0 0 24 32'/%3E%3Cpath d='M-24 32 Q0 4 24 32'/%3E%3Cpath d='M-24 32 Q0 8 24 32'/%3E%3Cpath d='M-24 32 Q0 12 24 32'/%3E%3Cpath d='M-24 32 Q0 16 24 32'/%3E%3C/g%3E%3Cpath d='M-24 32 Q0 6 24 32' fill='none' stroke='%23D5B370' stroke-width='.31' opacity='.40'/%3E%3C/g%3E%3C/defs%3E%3Cg%3E%3Cuse href='%23c' x='0' y='-24'/%3E%3Cuse href='%23c' x='48' y='-24'/%3E%3Cuse href='%23c' x='96' y='-24'/%3E%3Cuse href='%23c' x='24' y='-12'/%3E%3Cuse href='%23c' x='72' y='-12'/%3E%3Cuse href='%23c' x='0' y='0'/%3E%3Cuse href='%23c' x='48' y='0'/%3E%3Cuse href='%23c' x='96' y='0'/%3E%3Cuse href='%23c' x='24' y='12'/%3E%3Cuse href='%23c' x='72' y='12'/%3E%3Cuse href='%23c' x='0' y='24'/%3E%3Cuse href='%23c' x='48' y='24'/%3E%3Cuse href='%23c' x='96' y='24'/%3E%3Cuse href='%23c' x='24' y='36'/%3E%3Cuse href='%23c' x='72' y='36'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 96px 24px !important;
            background-repeat: repeat !important;
            background-position: 0 0 !important;
            -webkit-mask-image: none !important;
            mask-image: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Complete each exposed fan with additional nested arcs.
         * The overlap geometry stays unchanged; only the empty lower
         * portion of the preceding crest receives continuing linework.
         */
        [data-testid="stAppViewContainer"]::before {
            content: "";
            position: fixed;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.31;
            mix-blend-mode: screen;
            filter: none !important;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='24' viewBox='0 0 96 24'%3E%3Cdefs%3E%3Cfilter id='f' x='-35%25' y='-25%25' width='170%25' height='150%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.17 .46' numOctaves='2' seed='71' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.28' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg id='c'%3E%3Cpath d='M-24 32 Q0 -4 24 32 Z' fill='%23101A2C' fill-opacity='.97'/%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.43' stroke-linecap='round' stroke-linejoin='round' opacity='.86' filter='url(%23f)'%3E%3Cpath d='M-24 32 Q0 -4 24 32'/%3E%3Cpath d='M-24 32 Q0 0 24 32'/%3E%3Cpath d='M-24 32 Q0 4 24 32'/%3E%3Cpath d='M-24 32 Q0 8 24 32'/%3E%3Cpath d='M-24 32 Q0 12 24 32'/%3E%3Cpath d='M-24 32 Q0 16 24 32'/%3E%3Cpath d='M-24 32 Q0 20 24 32'/%3E%3Cpath d='M-24 32 Q0 24 24 32'/%3E%3Cpath d='M-24 32 Q0 28 24 32'/%3E%3C/g%3E%3Cpath d='M-24 32 Q0 6 24 32' fill='none' stroke='%23E7D19B' stroke-width='.30' opacity='.52'/%3E%3C/g%3E%3C/defs%3E%3Cg%3E%3Cuse href='%23c' x='0' y='-24'/%3E%3Cuse href='%23c' x='48' y='-24'/%3E%3Cuse href='%23c' x='96' y='-24'/%3E%3Cuse href='%23c' x='24' y='-12'/%3E%3Cuse href='%23c' x='72' y='-12'/%3E%3Cuse href='%23c' x='0' y='0'/%3E%3Cuse href='%23c' x='48' y='0'/%3E%3Cuse href='%23c' x='96' y='0'/%3E%3Cuse href='%23c' x='24' y='12'/%3E%3Cuse href='%23c' x='72' y='12'/%3E%3Cuse href='%23c' x='0' y='24'/%3E%3Cuse href='%23c' x='48' y='24'/%3E%3Cuse href='%23c' x='96' y='24'/%3E%3Cuse href='%23c' x='24' y='36'/%3E%3Cuse href='%23c' x='72' y='36'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 96px 24px !important;
            background-repeat: repeat !important;
            background-position: 0 0 !important;
            -webkit-mask-image: none !important;
            mask-image: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /*
         * Low-contrast tone-on-tone pattern for light text cards.
         * The texture stays behind content and never enters input fields.
         */
        [data-testid="stForm"],
        .source-note,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) {
            position: relative;
            isolation: isolate;
            overflow: hidden;
        }

        [data-testid="stForm"]::after,
        .source-note::after,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        )::after {
            content: "";
            position: absolute;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.14;
            mix-blend-mode: multiply;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='48' viewBox='0 0 96 48'%3E%3Cg fill='none' stroke='%23CDBF9E' stroke-width='.62' stroke-linecap='round' opacity='.78'%3E%3Cpath d='M-24 24 Q0 -2 24 24 M24 24 Q48 -2 72 24 M72 24 Q96 -2 120 24'/%3E%3Cpath d='M-24 24 Q0 3 24 24 M24 24 Q48 3 72 24 M72 24 Q96 3 120 24'/%3E%3Cpath d='M-24 24 Q0 8 24 24 M24 24 Q48 8 72 24 M72 24 Q96 8 120 24'/%3E%3Cpath d='M-24 24 Q0 13 24 24 M24 24 Q48 13 72 24 M72 24 Q96 13 120 24'/%3E%3Cpath d='M-24 24 Q0 18 24 24 M24 24 Q48 18 72 24 M72 24 Q96 18 120 24'/%3E%3Cpath d='M0 48 Q24 22 48 48 M48 48 Q72 22 96 48'/%3E%3Cpath d='M0 48 Q24 27 48 48 M48 48 Q72 27 96 48'/%3E%3Cpath d='M0 48 Q24 32 48 48 M48 48 Q72 32 96 48'/%3E%3Cpath d='M0 48 Q24 37 48 48 M48 48 Q72 37 96 48'/%3E%3Cpath d='M0 48 Q24 42 48 48 M48 48 Q72 42 96 48'/%3E%3C/g%3E%3C/svg%3E");
            background-size: 96px 48px;
            background-repeat: repeat;
        }

        [data-testid="stForm"] > *,
        .source-note > *,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        ) > * {
            position: relative;
            z-index: 1;
        }

        /* Keep editable controls visually quiet and completely legible. */
        [data-testid="stForm"] input,
        [data-testid="stForm"] textarea,
        [data-testid="stForm"] div[data-baseweb="select"] > div {
            background-color: rgba(255, 253, 246, 0.94) !important;
            background-image: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        :root {
            --deep-gold: #9B6B2F;
            --deep-gold-hover: #B1813D;
        }

        /* Slightly deepen the tone-on-tone texture on light cards. */
        [data-testid="stForm"]::after,
        .source-note::after,
        div[data-testid="stVerticalBlock"]:has(
            > div[data-testid="stElementContainer"] .result-card-marker
        )::after {
            opacity: 0.20 !important;
        }

        /* Native and BaseWeb radio selected states. */
        input[type="radio"] {
            accent-color: var(--deep-gold) !important;
        }

        div[role="radiogroup"]
            label:has(input[type="radio"]:checked)
            > div:first-child {
            background-color: var(--deep-gold) !important;
            border-color: var(--deep-gold) !important;
            box-shadow: 0 0 0 1px rgba(155, 107, 47, 0.18);
        }

        div[role="radiogroup"]
            label:has(input[type="radio"]:checked)
            > div:first-child
            > div {
            border-color: var(--deep-gold) !important;
        }

        label[data-baseweb="radio"]:has(input:checked) > div:first-child {
            background-color: var(--deep-gold) !important;
            border-color: var(--deep-gold) !important;
        }

        /* Tab underline and other active tab accents. */
        .stTabs [data-baseweb="tab-highlight"],
        .stTabs [data-baseweb="tab-border"] {
            background-color: var(--deep-gold) !important;
        }

        .stTabs [aria-selected="true"] {
            color: #101A2C !important;
            border-color: var(--deep-gold) !important;
            background-color: #D5B370 !important;
        }

        /* Focus accents should follow the same palette. */
        input:focus,
        textarea:focus,
        div[data-baseweb="select"]:focus-within {
            border-color: var(--deep-gold) !important;
            box-shadow: 0 0 0 2px rgba(155, 107, 47, 0.20) !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /* Expander title bars receive the same quiet tone-on-tone texture. */
        [data-testid="stExpander"] summary {
            color: #101A2C !important;
            background-color: rgba(244, 239, 223, 0.95) !important;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='48' viewBox='0 0 96 48'%3E%3Cg fill='none' stroke='%23C2B38F' stroke-width='.58' stroke-linecap='round' opacity='.24'%3E%3Cpath d='M-24 24 Q0 -2 24 24 M24 24 Q48 -2 72 24 M72 24 Q96 -2 120 24'/%3E%3Cpath d='M-24 24 Q0 4 24 24 M24 24 Q48 4 72 24 M72 24 Q96 4 120 24'/%3E%3Cpath d='M-24 24 Q0 10 24 24 M24 24 Q48 10 72 24 M72 24 Q96 10 120 24'/%3E%3Cpath d='M-24 24 Q0 16 24 24 M24 24 Q48 16 72 24 M72 24 Q96 16 120 24'/%3E%3Cpath d='M0 48 Q24 22 48 48 M48 48 Q72 22 96 48'/%3E%3Cpath d='M0 48 Q24 28 48 48 M48 48 Q72 28 96 48'/%3E%3Cpath d='M0 48 Q24 34 48 48 M48 48 Q72 34 96 48'/%3E%3Cpath d='M0 48 Q24 40 48 48 M48 48 Q72 40 96 48'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 96px 48px !important;
            background-repeat: repeat !important;
        }

        [data-testid="stExpander"] summary:hover {
            background-color: rgba(239, 229, 202, 0.98) !important;
        }

        /* Streamlit 1.39+ radio structure: selected label -> content -> row -> circle. */
        [data-testid="stRadioOption"][data-selected="true"]
            > div
            > div:first-child
            > div:first-child {
            background-color: #9B6B2F !important;
            border-color: #9B6B2F !important;
            box-shadow: 0 0 0 1px rgba(155, 107, 47, 0.18);
        }

        [data-testid="stRadioOption"][data-selected="true"]
            > div
            > div:first-child
            > div:first-child
            > div {
            background-color: #F4EFDF !important;
        }

        /* Remove the native red selection indicator under domestic/overseas tabs. */
        [data-testid="stTab"] .react-aria-SelectionIndicator {
            display: none !important;
            background-color: transparent !important;
        }

        [data-testid="stTab"][data-selected] {
            color: #101A2C !important;
            background-color: #D5B370 !important;
            border-bottom: 0 !important;
            box-shadow: none !important;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <style>
        /* High-contrast simulation disclaimer inside light result cards. */
        .simulation-note {
            color: #11284D !important;
            font-weight: 750 !important;
            letter-spacing: 0.01em;
        }

        /* Sidebar uses the same layered gold fish-scale texture as the page. */
        [data-testid="stSidebar"]::before {
            content: "";
            position: absolute;
            inset: 0;
            z-index: 0;
            pointer-events: none;
            opacity: 0.23;
            mix-blend-mode: screen;
            background-image:
                url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' width='96' height='24' viewBox='0 0 96 24'%3E%3Cdefs%3E%3Cfilter id='f' x='-35%25' y='-25%25' width='170%25' height='150%25'%3E%3CfeTurbulence type='fractalNoise' baseFrequency='.17 .46' numOctaves='2' seed='73' result='n'/%3E%3CfeDisplacementMap in='SourceGraphic' in2='n' scale='.28' xChannelSelector='R' yChannelSelector='G'/%3E%3C/filter%3E%3Cg id='c'%3E%3Cpath d='M-24 32 Q0 -4 24 32 Z' fill='%23101A2C' fill-opacity='.97'/%3E%3Cg fill='none' stroke='%23D5B370' stroke-width='.43' stroke-linecap='round' stroke-linejoin='round' opacity='.86' filter='url(%23f)'%3E%3Cpath d='M-24 32 Q0 -4 24 32'/%3E%3Cpath d='M-24 32 Q0 0 24 32'/%3E%3Cpath d='M-24 32 Q0 4 24 32'/%3E%3Cpath d='M-24 32 Q0 8 24 32'/%3E%3Cpath d='M-24 32 Q0 12 24 32'/%3E%3Cpath d='M-24 32 Q0 16 24 32'/%3E%3Cpath d='M-24 32 Q0 20 24 32'/%3E%3Cpath d='M-24 32 Q0 24 24 32'/%3E%3Cpath d='M-24 32 Q0 28 24 32'/%3E%3C/g%3E%3Cpath d='M-24 32 Q0 6 24 32' fill='none' stroke='%23E7D19B' stroke-width='.30' opacity='.52'/%3E%3C/g%3E%3C/defs%3E%3Cg%3E%3Cuse href='%23c' x='0' y='-24'/%3E%3Cuse href='%23c' x='48' y='-24'/%3E%3Cuse href='%23c' x='96' y='-24'/%3E%3Cuse href='%23c' x='24' y='-12'/%3E%3Cuse href='%23c' x='72' y='-12'/%3E%3Cuse href='%23c' x='0' y='0'/%3E%3Cuse href='%23c' x='48' y='0'/%3E%3Cuse href='%23c' x='96' y='0'/%3E%3Cuse href='%23c' x='24' y='12'/%3E%3Cuse href='%23c' x='72' y='12'/%3E%3Cuse href='%23c' x='0' y='24'/%3E%3Cuse href='%23c' x='48' y='24'/%3E%3Cuse href='%23c' x='96' y='24'/%3E%3C/g%3E%3C/svg%3E") !important;
            background-size: 96px 24px !important;
            background-repeat: repeat !important;
            background-position: 0 0 !important;
        }

        [data-testid="stSidebar"] > div {
            position: relative;
            z-index: 1;
        }

        /* Keep the hero close to the top toolbar on current Streamlit versions. */
        [data-testid="stMainBlockContainer"],
        .block-container {
            padding-top: 3cm !important;
        }

        /* CSS-only Markdown calls must not create visible vertical gaps. */
        [data-testid="stElementContainer"]:has(style) {
            display: none !important;
        }

        .ocean-hero {
            margin-top: 0 !important;
        }

        /* The desktop hero has enough room for the complete sentence. */
        .hero-subtitle {
            width: 100%;
            max-width: none !important;
            white-space: nowrap;
        }

        @media (max-width: 1100px) {
            .hero-subtitle {
                white-space: normal;
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

    client = OpenAI(
        api_key=api_key,
        base_url=base_url.rstrip("/"),
        timeout=180,
        max_retries=3,
    )
    json_mode = os.getenv("NEW_API_JSON_MODE", "auto").strip().lower()
    use_response_format = json_mode not in {"off", "false", "0", "no"}
    common_args = {
        "model": model,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.4,
    }

    try:
        if use_response_format:
            response = client.chat.completions.create(
                **common_args,
                response_format={"type": "json_object"},
            )
        else:
            response = client.chat.completions.create(**common_args)
    except AuthenticationError as exc:
        raise RuntimeError(
            "New API 服务拒绝了当前 API Key（401）。"
            "请到服务商控制台重新创建 Key，并原样粘贴完整密钥。"
        ) from exc
    except APIConnectionError as exc:
        raise RuntimeError(
            "无法连接 New API，请检查服务地址、本机网络、防火墙或代理设置。"
        ) from exc
    except BadRequestError as first_error:
        # 部分 OpenAI 兼容服务未实现 response_format，自动重试普通文本模式。
        if not use_response_format:
            raise RuntimeError(
                "New API 拒绝了当前请求，请检查模型名称和服务商参数兼容性。"
                f"\n技术信息：{first_error}"
            ) from first_error
        try:
            response = client.chat.completions.create(**common_args)
        except AuthenticationError as exc:
            raise RuntimeError(
                "New API 服务拒绝了当前 API Key（401）。"
                "请重新创建并粘贴完整密钥。"
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


def clamp_score(value: Any, default: int = 70) -> int:
    """把模型返回的匹配分数约束到 0-100。"""

    try:
        return max(0, min(100, int(float(value))))
    except (TypeError, ValueError):
        return default


def safe_weight(value: Any) -> float:
    """兼容 0.4、40 和“40%”等模型权重写法。"""

    raw = str(value or "").strip()
    is_percent = raw.endswith("%")
    try:
        weight = float(raw.rstrip("%"))
    except ValueError:
        return 0.0
    if is_percent or weight > 1:
        weight /= 100
    return max(0.0, weight)


def normalize_creative_formats(raw: dict[str, Any]) -> list[dict[str, Any]]:
    """归一化广告形式；兼容尚未返回新字段的旧模型结果。"""

    items = raw.get("creative_format_recommendations")
    normalized: list[dict[str, Any]] = []
    if isinstance(items, list):
        for item in items:
            if not isinstance(item, dict):
                continue
            profile = format_profile(item.get("format_id") or item.get("name"))
            normalized.append(
                {
                    **item,
                    "format_id": profile["id"],
                    "name": str(item.get("name") or profile["name"]),
                    "fit_score": clamp_score(item.get("fit_score")),
                    "production_difficulty": str(
                        item.get("production_difficulty")
                        or profile["default_difficulty"]
                    ),
                }
            )

    if not normalized:
        platforms = raw.get("platform_recommendations")
        seen: set[str] = set()
        if isinstance(platforms, dict):
            for group in platforms.values():
                if not isinstance(group, list):
                    continue
                for platform in group:
                    if not isinstance(platform, dict):
                        continue
                    candidates = platform.get("ad_formats")
                    if not isinstance(candidates, list):
                        candidates = []
                    for candidate in candidates[:1]:
                        profile = format_profile(candidate)
                        if profile["id"] in seen:
                            continue
                        seen.add(profile["id"])
                        normalized.append(
                            {
                                "format_id": profile["id"],
                                "name": profile["name"],
                                "fit_score": 70,
                                "reason": profile["best_for"],
                                "funnel_role": "建议验证",
                                "production_difficulty": profile[
                                    "default_difficulty"
                                ],
                                "required_assets": [],
                                "creative_concept": {},
                            }
                        )

    if not normalized:
        profile = format_profile("static_image")
        normalized.append(
            {
                "format_id": profile["id"],
                "name": profile["name"],
                "fit_score": 65,
                "reason": "模型未返回广告形式，暂以低成本静态图片作为验证起点。",
                "funnel_role": "建议验证",
                "production_difficulty": profile["default_difficulty"],
                "required_assets": [],
                "creative_concept": {},
            }
        )
    return sorted(normalized, key=lambda item: item["fit_score"], reverse=True)


def normalize_platform_groups(
    raw_groups: Any, creative_formats: list[dict[str, Any]]
) -> dict[str, list[dict[str, Any]]]:
    """补齐平台的形式、分数和预算权重，并过滤无效条目。"""

    groups = raw_groups if isinstance(raw_groups, dict) else {}
    default_format = creative_formats[0]["format_id"]
    normalized_groups: dict[str, list[dict[str, Any]]] = {
        "domestic": [],
        "overseas": [],
    }
    for group_name in normalized_groups:
        items = groups.get(group_name)
        if not isinstance(items, list):
            continue
        for item in items:
            if not isinstance(item, dict):
                continue
            ad_formats = item.get("ad_formats")
            first_ad_format = (
                ad_formats[0] if isinstance(ad_formats, list) and ad_formats else None
            )
            profile = format_profile(
                item.get("primary_format_id")
                or item.get("primary_format_name")
                or first_ad_format
                or default_format
            )
            normalized_groups[group_name].append(
                {
                    **item,
                    "name": str(item.get("name") or "未命名平台"),
                    "fit_score": clamp_score(item.get("fit_score")),
                    "primary_format_id": profile["id"],
                    "primary_format_name": str(
                        item.get("primary_format_name") or profile["name"]
                    ),
                    "budget_weight": safe_weight(item.get("budget_weight")),
                }
            )
        normalized_groups[group_name].sort(
            key=lambda platform: platform["fit_score"], reverse=True
        )
    return normalized_groups


def normalize_result(raw: dict[str, Any]) -> dict[str, Any]:
    """为模型偶发缺失字段提供安全默认值，避免页面直接崩溃。"""

    product = raw.get("product_analysis")
    creative_formats = normalize_creative_formats(raw)
    platforms = normalize_platform_groups(
        raw.get("platform_recommendations"), creative_formats
    )
    return {
        "summary": str(raw.get("summary") or "已生成初步广告测试方案。"),
        "product_analysis": product if isinstance(product, dict) else {},
        "target_users": raw.get("target_users")
        if isinstance(raw.get("target_users"), list)
        else [],
        "creative_format_recommendations": creative_formats,
        "ad_copy": raw.get("ad_copy") if isinstance(raw.get("ad_copy"), list) else [],
        "platform_recommendations": platforms,
        "assumptions": raw.get("assumptions")
        if isinstance(raw.get("assumptions"), list)
        else [],
        "next_actions": raw.get("next_actions")
        if isinstance(raw.get("next_actions"), list)
        else [],
    }


def stable_seed(product_text: str, platform_name: str, format_id: str) -> int:
    """用产品、平台与形式生成稳定随机种子，保证演示结果可复现。"""

    digest = hashlib.sha256(
        f"{product_text}|{platform_name}|{format_id}".encode("utf-8")
    ).hexdigest()
    return int(digest[:12], 16)


def simulate_seven_days(
    *,
    product_text: str,
    platform: dict[str, Any],
    platform_budget: float,
    currency: str,
    unit_price: float,
    goal: str,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """按广告形式与平台匹配度生成七天模拟，不代表真实投放结果。"""

    platform_name = str(platform.get("name") or "未知平台")
    difficulty = str(platform.get("difficulty") or "中")
    difficulty_factor = {"低": 1.08, "中": 1.0, "高": 0.9}.get(difficulty, 1.0)
    format_id = normalize_format_id(
        platform.get("primary_format_id") or platform.get("primary_format_name")
    )
    profile = format_profile(format_id)
    factors = platform_factors(platform_name)
    fit_score = clamp_score(platform.get("fit_score"), default=70)
    fit_factor = 0.72 + fit_score * 0.003
    goal_factor = {
        "商品购买": 1.0,
        "收集线索": 1.06,
        "注册": 1.03,
        "App 安装": 0.96,
        "品牌曝光": 0.82,
    }.get(goal, 1.0)
    rng = random.Random(stable_seed(product_text, platform_name, format_id))

    raw_weights = [rng.uniform(0.85, 1.15) for _ in range(7)]
    weight_sum = sum(raw_weights)
    daily_spend = [platform_budget * weight / weight_sum for weight in raw_weights]

    rows: list[dict[str, Any]] = []
    total_revenue = 0.0
    for day, spend in enumerate(daily_spend, start=1):
        learning_factor = 0.9 + day * 0.025
        cpm = rng.uniform(*profile["cpm_range"]) * factors["cpm"]
        ctr = (
            rng.uniform(*profile["ctr_range"])
            * factors["ctr"]
            * difficulty_factor
            * fit_factor
            * learning_factor
        )
        cvr = (
            rng.uniform(*profile["cvr_range"])
            * factors["cvr"]
            * difficulty_factor
            * fit_factor
            * goal_factor
            * learning_factor
        )
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
        "format_name": profile["name"],
        "fit_score": float(fit_score),
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

    signal_cols = st.columns(4)
    signal_cols[0].metric(
        "视觉演示潜力", str(product.get("visual_demo_potential") or "待判断")
    )
    signal_cols[1].metric(
        "搜索意图潜力", str(product.get("search_intent_potential") or "待判断")
    )
    signal_cols[2].metric(
        "信任要求", str(product.get("trust_requirement") or "待判断")
    )
    signal_cols[3].metric(
        "决策周期", str(product.get("decision_cycle") or "待判断")
    )


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


def render_creative_formats(result: dict[str, Any]) -> None:
    """展示产品与广告形式的匹配结论。"""

    st.header("广告形式匹配")
    st.caption("先判断产品适合怎样表达，再选择能够承载该形式的平台。")
    formats = result.get("creative_format_recommendations")
    if not isinstance(formats, list) or not formats:
        formats = normalize_creative_formats(result)
    if not formats:
        st.info("模型暂未返回广告形式建议。")
        return

    columns = st.columns(min(3, len(formats)))
    for index, item in enumerate(formats):
        with columns[index % len(columns)]:
            name = str(item.get("name") or f"形式 {index + 1}")
            score = clamp_score(item.get("fit_score"))
            st.subheader(name)
            st.metric("产品匹配度", f"{score} / 100")
            st.progress(score / 100)
            st.write(item.get("reason") or "暂无匹配理由")
            st.markdown(
                f"**漏斗角色：** {item.get('funnel_role') or '待确认'}  \n"
                f"**制作难度：** "
                f"{item.get('production_difficulty') or '待确认'}"
            )
            st.markdown("**所需素材**")
            render_list(item.get("required_assets"))

            concept = item.get("creative_concept")
            if isinstance(concept, dict) and concept:
                st.markdown("**创意骨架**")
                st.write(f"钩子：{concept.get('hook') or '待设计'}")
                st.write(f"结构：{concept.get('structure') or '待设计'}")
                st.write(f"CTA：{concept.get('cta') or '待设计'}")


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
    goal: str,
) -> None:
    """展示单个平台建议及其七天模拟。"""

    name = str(platform.get("name") or "未命名平台")
    st.subheader(name)
    st.markdown(
        f"**投放位置：** {platform.get('placement') or '待确认'}　"
        f"**平台匹配度：** {clamp_score(platform.get('fit_score'))} / 100　"
        f"**首选广告形式：** "
        f"{platform.get('primary_format_name') or format_profile(platform.get('primary_format_id'))['name']}"
    )
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

    experiment = platform.get("experiment")
    if isinstance(experiment, dict) and experiment:
        st.markdown("**七天 A/B 实验**")
        st.write(f"验证假设：{experiment.get('hypothesis') or '待确认'}")
        experiment_cols = st.columns(3)
        experiment_cols[0].write(
            f"A：{experiment.get('variant_a') or '待设计'}"
        )
        experiment_cols[1].write(
            f"B：{experiment.get('variant_b') or '待设计'}"
        )
        experiment_cols[2].write(
            f"成功指标：{experiment.get('success_metric') or '待确认'}"
        )

    st.markdown(
        '<div class="simulation-note">以下按“产品匹配度 × 广告形式 × 平台”'
        '生成算法模拟预估，不是实际投放数据或收益承诺。</div>',
        unsafe_allow_html=True,
    )
    frame, metrics = simulate_seven_days(
        product_text=product_text,
        platform=platform,
        platform_budget=platform_budget,
        currency=currency,
        unit_price=unit_price,
        goal=goal,
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
    st.caption(
        f"模拟依据：{metrics['format_name']}；平台匹配度 "
        f"{metrics['fit_score']:.0f}/100。所有基准均为 Demo 内置相对参数。"
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
    goal: str,
) -> None:
    """按国内和海外 Tab 展示平台与模拟数据。"""

    st.header("平台推荐与七天模拟")
    st.caption(
        "国内与海外视为两套备选市场方案；每个 Tab 都按平台权重分配同一笔七天总预算。"
        "上线前需替换为真实平台数据。"
    )
    groups = result["platform_recommendations"]
    domestic = groups.get("domestic") if isinstance(groups, dict) else []
    overseas = groups.get("overseas") if isinstance(groups, dict) else []
    domestic_tab, overseas_tab = st.tabs(["国内平台", "海外平台"])
    for tab, platforms in ((domestic_tab, domestic), (overseas_tab, overseas)):
        with tab:
            if not platforms:
                st.info("暂无平台建议。")
                continue
            weights = [
                safe_weight(platform.get("budget_weight"))
                if isinstance(platform, dict)
                else 0.0
                for platform in platforms
            ]
            if sum(weights) <= 0:
                weights = [
                    float(clamp_score(platform.get("fit_score")))
                    for platform in platforms
                ]
            weight_sum = sum(weights) or float(len(platforms))
            for index, platform in enumerate(platforms):
                platform_budget = total_budget * weights[index] / weight_sum
                with st.expander(
                    f"{platform.get('name') or f'平台 {index + 1}'} · "
                    f"{platform.get('primary_format_name') or '首选形式'} · "
                    f"预算 {currency} {platform_budget:,.0f}",
                    expanded=index == 0,
                ):
                    render_platform(
                        platform=platform,
                        product_text=product_text,
                        platform_budget=platform_budget,
                        currency=currency,
                        unit_price=unit_price,
                        goal=goal,
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
    """展示分析引擎状态；API 地址、Key 与模型只允许由服务器配置。"""

    with st.sidebar:
        st.header("AI 分析")
        env_key = os.getenv("NEW_API_KEY", "")
        env_base_url = os.getenv("NEW_API_BASE_URL", "")
        env_model = os.getenv("NEW_API_MODEL", "gpt-5.6-sol")
        api_key = env_key.strip()
        base_url = env_base_url.strip()
        model = env_model.strip()

        st.caption(f"当前模型：{model or '服务器尚未配置'}")
        engine_mode = st.radio(
            "分析引擎",
            ["New API 实时生成", "固定宠物水杯案例"],
            index=0,
            help="固定案例只用于检查页面，不会分析用户输入的其他商品。",
        )

        if engine_mode == "固定宠物水杯案例":
            st.warning("固定案例会忽略产品输入，只返回预置的宠物饮水杯方案。")
        elif api_key and base_url and model:
            st.success("实时分析服务已由服务器安全配置")
        else:
            st.warning("实时分析服务尚未完成服务器配置。")
    return api_key, base_url, model, engine_mode


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

    st.markdown(
        """
        <section class="ocean-hero">
            <div class="hero-eyebrow">AI Advertising Intelligence</div>
            <h1 class="hero-title">AdPilot AI</h1>
            <div class="hero-subtitle">从产品信息到受众洞察、广告创意与七天投放模拟，在一片深海般的策略画布中完成广告方案。</div>
        </section>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="source-note">
            先输入最少产品信息。平台将补全产品、客群、广告语和渠道实验；
            所有七天指标均为模拟预估。
        </div>
        """,
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
        asset_cols = st.columns([3, 1])
        with asset_cols[0]:
            available_assets = st.multiselect(
                "当前已有素材",
                [
                    "产品白底图",
                    "产品场景图",
                    "产品演示视频",
                    "真人口播 / 出镜",
                    "用户评价 / UGC",
                    "品牌 Logo 与视觉规范",
                    "可用落地页",
                ],
                default=["产品白底图"],
                help="模型会优先推荐当前素材能够支持、或补拍成本可控的广告形式。",
            )
        with asset_cols[1]:
            production_capacity = st.selectbox(
                "素材制作能力",
                ["低：仅能改图和写文案", "中：可拍摄简单短视频", "高：可持续制作多版本素材"],
                index=1,
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
                "服务器中的 API Key 配置无效，请联系网站管理员。"
            )
        elif not fixed_demo_mode and (not api_key or not base_url or not model):
            st.error("实时分析服务尚未完成服务器配置，请联系网站管理员。")
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
                            available_assets=available_assets,
                            production_capacity=production_capacity,
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
                        "goal": goal,
                        "available_assets": available_assets,
                        "production_capacity": production_capacity,
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
        with st.container(border=True):
            st.markdown(
                '<span class="result-card-marker"></span>',
                unsafe_allow_html=True,
            )
            render_product_analysis(result)
        with st.container(border=True):
            st.markdown(
                '<span class="result-card-marker"></span>',
                unsafe_allow_html=True,
            )
            render_target_users(result)
        with st.container(border=True):
            st.markdown(
                '<span class="result-card-marker"></span>',
                unsafe_allow_html=True,
            )
            render_creative_formats(result)
        with st.container(border=True):
            st.markdown(
                '<span class="result-card-marker"></span>',
                unsafe_allow_html=True,
            )
            render_ad_copy(result)
        with st.container(border=True):
            st.markdown(
                '<span class="result-card-marker"></span>',
                unsafe_allow_html=True,
            )
            render_platform_tabs(
                result=result,
                product_text=inputs["product_text"],
                total_budget=inputs["budget"],
                currency=inputs["currency"],
                unit_price=inputs["unit_price"],
                goal=inputs.get("goal", "商品购买"),
            )
        with st.container(border=True):
            st.markdown(
                '<span class="result-card-marker"></span>',
                unsafe_allow_html=True,
            )
            render_summary(result)


if __name__ == "__main__":
    main()
