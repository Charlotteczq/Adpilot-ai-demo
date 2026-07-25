# AdPilot AI Streamlit Demo

AdPilot AI 是一个一天内可落地的广告策略 Demo。用户提供产品描述或公开网页链接后，应用通过 OpenAI 兼容 SDK 调用 New API，生成结构化广告方案，并展示不同平台的七天模拟投放结果。

## 当前 MVP

- 三种信息来源模式：纯文字、单链接抓取、联网增强。
- 链接抓取使用 `requests + beautifulsoup4`，失败时自动降级为手动描述。
- 通过 `.env` 读取 `NEW_API_KEY`、`NEW_API_BASE_URL` 和可选的 `NEW_API_MODEL`。
- 结构化展示产品分析、目标用户、广告语和下一步建议。
- 国内和海外平台分 Tab 展示。
- 每个平台包含广告形式、素材要求、制作难度、预算建议和计费方式。
- 每个平台都有七天模拟指标、折线图和明细表。
- 内置“固定宠物水杯案例”，可在无 API Key 时检查完整界面。

> 页面中的曝光、点击、转化、CPA、收入和 ROAS 都是模拟预估，不代表真实投放结果或收益承诺。

## 项目文件

```text
.
├── app.py              # Streamlit 页面、抓取、API 调用和七天模拟
├── prompt.py           # 系统提示词、JSON 协议和固定演示数据
├── requirements.txt    # Python 依赖
├── .env.example        # 环境变量模板
└── .gitignore
```

## 本地运行

推荐使用 Python 3.10 或更高版本。

### Windows PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
streamlit run app.py
```

### macOS / Linux

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
streamlit run app.py
```

浏览器通常会自动打开：

```text
http://localhost:8501
```

## New API 配置

编辑 `.env`：

```dotenv
NEW_API_KEY=你的真实Key
NEW_API_BASE_URL=https://你的服务地址/v1
NEW_API_MODEL=服务商提供的模型ID
```

注意：

- `NEW_API_BASE_URL` 通常需要包含 `/v1`，以 New API 控制台说明为准。
- `NEW_API_MODEL` 必须填写 New API 中真实可用的模型 ID。
- 应用会优先请求 JSON Mode；若兼容服务不支持 `response_format`，会自动用普通模式重试。
- `.env` 已被 `.gitignore` 忽略，不要把真实 Key 提交到 GitHub。

## 使用方式

1. 在侧边栏填写 API 配置，并保持“New API 实时生成”。
2. 选择信息来源模式。
3. 输入产品介绍、广告目标、市场、预算和可选售价。
4. 点击“生成广告方案”。
5. 查看产品分析、目标用户、广告语、平台建议和七天模拟。

“固定宠物水杯案例”只用于检查页面布局，会忽略其他商品输入。它不会默认开启。

### 信息来源模式

| 模式 | 行为 |
| --- | --- |
| 纯文字 | 只分析用户填写的产品描述 |
| 链接抓取 | 抓取一个公开产品页面，失败时自动降级 |
| 联网增强 | 抓取最多三个用户提供的公开参考页面并综合分析 |

当前 MVP 不包含通用搜索引擎，也不声称模型拥有实时联网能力。“联网增强”是对用户提供的公开链接进行抓取。

## 七天模拟说明

模拟引擎使用产品描述和平台名称生成固定随机种子，因此同一输入的结果可以重复演示。预算会平均拆分到模型推荐的全部国内和海外平台，再根据平台制作难度生成示意性的 CPM、CTR 和 CVR。

这些数值只用于演示产品交互。接入真实广告账户后，应使用真实平台数据替代模拟基准。

## 一天内的后续完善顺序

1. **先验证真实 API**：确认 New API 的 Base URL、模型 ID 和 JSON 输出兼容性。
2. **再优化平台创意**：为 Google Search、Meta Feed、TikTok/Reels 和内容网页增加差异化广告预览。
3. **最后接真实数据**：增加搜索服务、行业基准和广告平台报表上传。

建议当天不要加入登录、数据库、支付或真实广告发布，优先保证从输入到七天模拟的完整演示稳定。
