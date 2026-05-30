# 舆情分析系统 - 完整实现指南

> 本文档用于在另一个未实现舆情分析的项目中，完整复现舆情分析功能
>
> **文档版本**: v1.0
> **创建日期**: 2026-05-29
> **适用场景**: 基于 Web 的智慧舆情分析系统，集成 AI 模型进行数据分析

---

## 一、技术选型

### 1.1 核心技术栈

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| **Tornado** | 6.x | 后端 Web 框架 | Python 异步 Web 框架，处理 HTTP 请求 |
| **SQLite** | 3.x | 数据存储 | 轻量级关系型数据库，存储采集数据和配置 |
| **httpx** | 0.24+ | HTTP 客户端 | 异步 HTTP 客户端，调用 AI 模型 API |
| **ECharts** | 5.5.0 | 数据可视化 | 百度开源图表库，渲染统计图表 |
| **Three.js** | r128 | 3D 渲染 | WebGL 3D 库，实现 3D 地球可视化 |
| **Layui** | 2.13.6 | UI 组件库 | 前端模块化 UI 框架 |
| **Font Awesome** | 5.15.4 | 图标库 | 提供丰富的图标资源 |

### 1.2 AI 模型集成

| 组件 | 说明 |
|------|------|
| **OpenAI 兼容 API** | 支持任何兼容 OpenAI 格式的 API 接口 |
| **模型配置管理** | 通过数据库动态配置模型地址、密钥、参数 |
| **JSON 解析** | 自动解析 AI 返回的 JSON 格式分析结果 |
| **错误处理** | 完善的异常捕获和错误提示机制 |

### 1.3 为什么选择此技术栈

1. **轻量级**: SQLite + Tornado 无需复杂部署，单机即可运行
2. **AI 集成灵活**: 支持任意 OpenAI 兼容 API，不依赖特定厂商
3. **可视化丰富**: ECharts + Three.js 提供 2D/3D 全方位数据展示
4. **响应式设计**: 现代化 UI，支持大屏展示和移动端适配
5. **扩展性强**: 模块化设计，易于添加新的分析维度

---

## 二、系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────────┐
│                          用户浏览器                              │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │                    数智大屏 & 智慧舆情页面                  │   │
│  │  ┌────────────┐  ┌────────────┐  ┌──────────────────┐   │   │
│  │  │ 数智大屏    │  │ 3D 地球    │  │ 智慧舆情分析      │   │   │
│  │  │ (ECharts)  │  │ (Three.js) │  │ (AI 分析结果)     │   │   │
│  │  └────────────┘  └────────────┘  └──────────────────┘   │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────┬─────────────────────────────────────┘
                            │ HTTP/Fetch API
┌───────────────────────────▼─────────────────────────────────────┐
│                        Tornado 后端                              │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ SentimentHandler│  │ DashboardCharts │  │ SentimentAnalyze│  │
│  │ (页面渲染)       │  │ (图表数据 API)   │  │ (AI 分析 API)   │  │
│  └─────────────────┘  └─────────────────┘  └────────────────┘  │
│  ┌─────────────────┐  ┌─────────────────┐                      │
│  │ SentimentStats  │  │ SentimentAnalyze│                      │
│  │ (统计数据 API)   │  │ (AI 分析逻辑)    │                      │
│  └─────────────────┘  └─────────────────┘                      │
└───────────────────────────┬─────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                        数据层                                    │
│  ┌─────────────────┐  ┌─────────────────┐  ┌────────────────┐  │
│  │ SQLite 数据库    │  │ ModelRepository │  │ SentimentRepo  │  │
│  │ - outlook_data  │  │ (模型配置管理)   │  │ (舆情数据仓库)  │  │
│  │ - outlook_tasks │  │                  │  │                │  │
│  │ - im_convers.   │  │                  │  │                │  │
│  │ - chat_messages │  │                  │  │                │  │
│  └─────────────────┘  └─────────────────┘  └────────────────┘  │
└─────────────────────────────────────────────────────────────────┘
                            │
┌───────────────────────────▼─────────────────────────────────────┐
│                      AI 模型服务                                 │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │  OpenAI 兼容 API (httpx 调用)                              │   │
│  │  - 热点分析  - 情感分析  - 风险评估  - 趋势预测  - 总结    │   │
│  └──────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分

| 模块 | 文件 | 职责 |
|------|------|------|
| **页面渲染** | `sentiment.html` | 数智大屏、3D 地球、智慧舆情分析页面 |
| **控制器** | `sentiment.py` | 处理 HTTP 请求，调用数据层，返回 JSON 数据 |
| **数据仓库** | `sentiment.py` (SentimentRepository) | 数据查询、统计、AI 分析逻辑 |
| **模型管理** | `model.py` (ModelRepository) | AI 模型配置管理 |
| **数据库** | `db.py` | SQLite 连接管理 |

### 2.3 数据流

```
用户点击"开始智能分析"
    ↓
前端发起 POST /api/sentiment/analyze
    ↓
SentimentAnalyzeHandler 接收请求
    ↓
SentimentRepository 获取数据摘要
    ↓
构建 Prompt 发送给 AI 模型
    ↓
AI 模型返回 JSON 分析结果
    ↓
前端渲染分析结果（热点、情感、风险、趋势、总结）
```

---

## 三、完整功能清单

### 3.1 功能模块

| 功能 | 说明 | 优先级 |
|------|------|--------|
| **数智大屏** | 展示瞭望采集数据和智能聊天数据统计 | P0 |
| **数据采集统计** | 数据总量、24h 新增、来源数量、任务数量 | P0 |
| **ECharts 可视化** | 数据来源分布饼图、采集趋势折线图、任务状态饼图 | P0 |
| **3D 地球** | Three.js 渲染可交互 3D 地球，支持拖拽、缩放、自动旋转 | P1 |
| **智慧舆情分析** | AI 自动分析舆情热点、情感倾向、风险等级、趋势预测 | P0 |
| **热点分析** | 识别当前热点话题，按热度排序，显示趋势和来源 | P0 |
| **情感倾向分析** | 整体情感倾向（正面/中性/负面），负面舆情预警 | P0 |
| **风险等级评估** | 高/中/低风险事项，包含描述和应对建议 | P0 |
| **趋势预测** | 未来发展趋势预测，建议应对措施 | P0 |
| **舆情总结** | AI 生成整体舆情总结 | P0 |
| **手势识别** | 摄像头手势控制，支持 7 种手势操作 | P1 |

### 3.2 API 接口

| 接口 | 方法 | 功能 |
|------|------|------|
| `/sentiment` | GET | 渲染智慧舆情页面 |
| `/api/sentiment/stats` | GET | 获取统计数据（瞭望 + 聊天） |
| `/api/dashboard/charts` | GET | 获取数智大屏图表数据 |
| `/api/sentiment/analyze` | POST | 触发 AI 舆情分析 |

---

## 四、UI 页面设计

### 4.1 页面布局

```
┌─────────────────────────────────────────────────────────────────┐
│  侧边栏 (300px)          │  主内容区                             │
│  ┌─────────────────────┐ │  ┌─────────────────────────────────┐ │
│  │  数据展示            │ │  │ 数智大屏 & 智慧舆情      [用户]  │ │
│  ├─────────────────────┤ │  ├─────────────────────────────────┤ │
│  │  功能模块            │ │  │ [数智大屏] [3D地球] [智慧舆情]  │ │
│  │  💬 智能问数         │ │  ├─────────────────────────────────┤ │
│  │  👥 智能聊天         │ │  │                                 │ │
│  │                      │ │  │  数智大屏 Tab:                  │ │
│  │  瞭望采集            │ │  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌───┐ │ │
│  │  🔍 瞭望采集         │ │  │  │今日 │ │累计 │ │数据 │ │任 │ │ │
│  │  📦 数据仓库         │ │  │  │采集 │ │采集 │ │源   │ │务 │ │ │
│  │  ⏱️ 定时采集         │ │  │  └─────┘ └─────┘ └─────┘ └───┘ │ │
│  │  📝 采集日志         │ │  │  ┌─────────────┐ ┌───────────┐ │ │
│  │                      │ │  │  │ 数据来源分布 │ │ 采集趋势   │ │ │
│  │  数据展示            │ │  │  │   (饼图)     │ │  (折线图)  │ │ │
│  │  📈 数智大屏&舆情    │ │  │  └─────────────┘ └───────────┘ │ │
│  └─────────────────────┘ │  │  ┌─────────────┐ ┌───────────┐ │ │
│                          │ │  │ 最近采集数据   │ │ 任务状态   │ │ │
│                          │ │  │   (列表)       │ │  (饼图)    │ │ │
│                          │ │  │  └─────────────┘ └───────────┘ │ │
│                          │ │  │                                 │ │
│                          │ │  │  3D 地球 Tab:                   │ │
│                          │ │  │  ┌───────────────────────────┐  │ │
│                          │ │  │  │                           │  │ │
│                          │ │  │  │      3D 地球渲染区域       │  │ │
│                          │ │  │  │   (拖拽旋转 · 滚轮缩放)    │  │ │
│                          │ │  │  │                           │  │ │
│                          │ │  │  └───────────────────────────┘  │ │
│                          │ │  │                                 │ │
│                          │ │  │  智慧舆情 Tab:                  │ │
│                          │ │  │  ┌─────┐ ┌─────┐ ┌─────┐ ┌───┐ │ │
│                          │ │  │ │数据 │ │24h  │ │聊天 │ │消息│ │ │
│                          │ │  │ │总量 │ │新增 │ │会话 │ │数  │ │ │
│                          │ │  │ └─────┘ └─────┘ └─────┘ └───┘  │ │
│                          │ │  │  ┌───────────────────────────┐  │ │
│                          │ │  │  │  AI 舆情分析               │  │ │
│                          │ │  │  │  [开始智能分析] 按钮        │  │ │
│                          │ │  │  └───────────────────────────┘  │ │
│                          │ │  │  ┌───────────────────────────┐  │ │
│                          │ │  │  │  舆情热点分析 (卡片网格)    │  │ │
│                          │ │  │  └───────────────────────────┘  │ │
│                          │ │  │  ┌───────────────────────────┐  │ │
│                          │ │  │  │  情感倾向分析 (进度条)      │  │ │
│                          │ │  │  └───────────────────────────┘  │ │
│                          │ │  │  ┌───────────────────────────┐  │ │
│                          │ │  │  │  风险等级评估 (列表)        │  │ │
│                          │ │  │  └───────────────────────────┘  │ │
│                          │ │  │  ┌───────────────────────────┐  │ │
│                          │ │  │  │  趋势预测 (卡片)           │  │ │
│                          │ │  │  └───────────────────────────┘  │ │
│                          │ │  │  ┌───────────────────────────┐  │ │
│                          │ │  │  │  舆情总结 (高亮框)          │  │ │
│                          │ │  │  └───────────────────────────┘  │ │
│                          │ │  └─────────────────────────────────┘ │
│                          │ └─────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────┘
```

### 4.2 核心 CSS 样式

```css
/* 全局样式 */
* { margin: 0; padding: 0; box-sizing: border-box; }
body {
    font-family: 'PingFang SC', 'Microsoft YaHei', 'Helvetica Neue', sans-serif;
    background: #0a0e1a;
    color: #e0e0e0;
    height: 100vh;
    overflow: hidden;
}

/* 侧边栏 */
.sidebar {
    width: 300px;
    background: #0d1321;
    display: flex;
    flex-direction: column;
    border-right: 1px solid rgba(255, 255, 255, 0.06);
    flex-shrink: 0;
}
.nav-item {
    display: flex;
    align-items: center;
    gap: 12px;
    padding: 12px 14px;
    border-radius: 10px;
    cursor: pointer;
    margin-bottom: 6px;
    transition: all 0.3s;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.6);
    text-decoration: none;
}
.nav-item:hover { background: rgba(255, 255, 255, 0.04); color: #fff; }
.nav-item.active { background: rgba(0, 212, 255, 0.1); color: #00d4ff; }

/* Tab 切换 */
.tab-bar {
    display: flex;
    gap: 4px;
    padding: 12px 24px;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
    background: rgba(255, 255, 255, 0.02);
}
.tab-btn {
    padding: 10px 24px;
    border-radius: 10px;
    border: none;
    background: transparent;
    color: rgba(255, 255, 255, 0.5);
    font-size: 14px;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.3s;
}
.tab-btn:hover { background: rgba(255, 255, 255, 0.04); color: #fff; }
.tab-btn.active { background: rgba(0, 212, 255, 0.1); color: #00d4ff; }

/* 统计卡片 */
.stats-grid {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 16px;
    margin-bottom: 24px;
}
.stat-card {
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(15px);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 20px;
    position: relative;
    overflow: hidden;
}
.stat-card::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 3px;
    background: linear-gradient(90deg, #00d4ff, #7b2ff7, #00d4ff);
    background-size: 200% 100%;
    animation: gradientMove 4s ease infinite;
}
.stat-card .stat-value {
    font-size: 28px;
    font-weight: 700;
    color: #fff;
    margin-bottom: 4px;
}
.stat-card .stat-label {
    font-size: 12px;
    color: rgba(255, 255, 255, 0.5);
}

/* 分析面板 */
.analysis-panel {
    background: rgba(255, 255, 255, 0.02);
    backdrop-filter: blur(15px);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 16px;
    padding: 24px;
    margin-bottom: 20px;
}
.panel-title {
    font-size: 16px;
    font-weight: 600;
    color: #fff;
    margin-bottom: 16px;
    display: flex;
    align-items: center;
    gap: 8px;
}
.panel-title::before {
    content: '';
    width: 20px;
    height: 2px;
    background: linear-gradient(90deg, #00d4ff, transparent);
}

/* 分析按钮 */
.btn-analyze {
    padding: 12px 32px;
    border-radius: 12px;
    border: none;
    background: linear-gradient(135deg, #00d4ff, #7b2ff7);
    color: #fff;
    font-size: 14px;
    font-weight: 600;
    cursor: pointer;
    transition: all 0.3s;
    display: flex;
    align-items: center;
    gap: 8px;
}
.btn-analyze:hover {
    transform: translateY(-2px);
    box-shadow: 0 8px 24px rgba(0, 212, 255, 0.3);
}
.btn-analyze:disabled {
    opacity: 0.5;
    cursor: not-allowed;
    transform: none;
}

/* 热点卡片 */
.hot-topics {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 16px;
}
.topic-card {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 12px;
    padding: 16px;
    transition: all 0.3s;
}
.topic-card:hover {
    border-color: rgba(0, 212, 255, 0.3);
    transform: translateY(-2px);
}
.topic-heat {
    padding: 4px 8px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
}
.heat-high { background: rgba(255, 77, 79, 0.2); color: #ff4d4f; }
.heat-medium { background: rgba(255, 193, 7, 0.2); color: #ffc107; }
.heat-low { background: rgba(0, 212, 255, 0.2); color: #00d4ff; }

/* 情感进度条 */
.sentiment-bar {
    display: flex;
    height: 32px;
    border-radius: 8px;
    overflow: hidden;
    margin-bottom: 16px;
}
.sentiment-positive { background: linear-gradient(90deg, #52c41a, #73d13d); }
.sentiment-neutral { background: linear-gradient(90deg, #1890ff, #40a9ff); }
.sentiment-negative { background: linear-gradient(90deg, #ff4d4f, #ff7875); }

/* 风险项 */
.risk-item {
    padding: 16px;
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 12px;
}
.risk-level {
    padding: 4px 10px;
    border-radius: 6px;
    font-size: 11px;
    font-weight: 600;
}
.risk-high { background: rgba(255, 77, 79, 0.2); color: #ff4d4f; }
.risk-medium { background: rgba(255, 193, 7, 0.2); color: #ffc107; }
.risk-low { background: rgba(0, 212, 255, 0.2); color: #00d4ff; }
.risk-suggestion {
    font-size: 12px;
    color: #00d4ff;
    padding: 8px 12px;
    background: rgba(0, 212, 255, 0.05);
    border-radius: 6px;
}

/* 趋势预测 */
.trend-prediction {
    padding: 16px;
    background: rgba(123, 47, 247, 0.05);
    border: 1px solid rgba(123, 47, 247, 0.2);
    border-radius: 12px;
    margin-bottom: 16px;
}
.trend-action {
    padding: 6px 12px;
    background: rgba(123, 47, 247, 0.1);
    border: 1px solid rgba(123, 47, 247, 0.2);
    border-radius: 6px;
    font-size: 12px;
    color: #a78bfa;
}

/* 舆情总结 */
.summary-box {
    padding: 20px;
    background: linear-gradient(135deg, rgba(0, 212, 255, 0.05), rgba(123, 47, 247, 0.05));
    border: 1px solid rgba(0, 212, 255, 0.15);
    border-radius: 12px;
    font-size: 14px;
    color: rgba(255, 255, 255, 0.8);
    line-height: 1.8;
}

/* 加载动画 */
.loading-overlay {
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(10, 14, 26, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 9999;
}
.loading-spinner {
    width: 48px;
    height: 48px;
    border: 4px solid rgba(0, 212, 255, 0.2);
    border-top-color: #00d4ff;
    border-radius: 50%;
    animation: spin 1s linear infinite;
}
@keyframes spin { to { transform: rotate(360deg); } }
@keyframes gradientMove {
    0% { background-position: 0% 50% }
    25% { background-position: 50% 100% }
    50% { background-position: 100% 50% }
    75% { background-position: 50% 0% }
    100% { background-position: 0% 50% }
}
```

### 4.3 数智大屏样式

```css
/* 数智大屏统计 */
.dashboard-stats {
    display: flex;
    gap: 12px;
    padding: 0;
    margin-bottom: 16px;
}
.dashboard-stat {
    flex: 1;
    text-align: center;
    background: rgba(24, 144, 255, 0.06);
    border: 1px solid rgba(24, 144, 255, 0.12);
    border-radius: 10px;
    padding: 14px 8px;
    transition: all 0.3s;
}
.dashboard-stat:hover {
    border-color: rgba(24, 144, 255, 0.35);
    box-shadow: 0 0 20px rgba(24, 144, 255, 0.1);
}
.dashboard-stat .num {
    font-size: 32px;
    font-weight: bold;
    color: #1890ff;
    line-height: 1.1;
}
.dashboard-stat .num.green { color: #52c41a; }
.dashboard-stat .num.orange { color: #faad14; }
.dashboard-stat .num.purple { color: #a855f7; }
.dashboard-stat .label {
    font-size: 11px;
    color: #556;
    margin-top: 6px;
    letter-spacing: 1px;
}

/* 图表容器 */
.chart-box {
    background: rgba(255, 255, 255, 0.02);
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 10px;
    padding: 10px;
    position: relative;
    overflow: hidden;
    min-height: 200px;
}
.chart-box::before {
    content: '';
    position: absolute;
    top: 0; left: 0; right: 0;
    height: 1px;
    background: linear-gradient(90deg, transparent, rgba(24, 144, 255, 0.2), transparent);
}
.charts-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
}
```

### 4.4 3D 地球容器样式

```css
.earth-container {
    width: 100%;
    height: calc(100vh - 160px);
    position: relative;
    background: radial-gradient(ellipse at center, #0a1030 0%, #060a18 50%, #020408 100%);
    border-radius: 12px;
    overflow: hidden;
}
#earthCanvas {
    width: 100%;
    height: 100%;
    display: block;
}
.earth-hint {
    position: absolute;
    bottom: 20px;
    left: 50%;
    transform: translateX(-50%);
    color: rgba(255, 255, 255, 0.3);
    font-size: 12px;
    letter-spacing: 2px;
    z-index: 10;
    pointer-events: none;
    animation: pulse-hint 2s ease-in-out infinite;
}
@keyframes pulse-hint {
    0%, 100% { opacity: 0.2 }
    50% { opacity: 0.5 }
}
```

---

## 五、核心实现细节

### 5.1 后端控制器实现

#### 5.1.1 页面渲染 Handler

```python
import tornado.web
from app.controllers.base import BaseHandler

class SentimentHandler(BaseHandler):
    """用户侧智慧舆情页面"""
    @tornado.web.authenticated
    def get(self):
        self.render("sentiment.html", title="数智大屏 & 智慧舆情", username=self.current_user)
```

#### 5.1.2 数智大屏图表数据 API

```python
class DashboardChartsHandler(BaseHandler):
    """数智大屏图表数据 API"""
    @tornado.web.authenticated
    def get(self):
        try:
            from app.models.db import get_connection
            with get_connection() as conn:
                # 数据总量
                total = conn.execute(
                    "SELECT COUNT(*) as cnt FROM outlook_data"
                ).fetchone()["cnt"]
                
                # 今日新增
                today = conn.execute(
                    "SELECT COUNT(*) as cnt FROM outlook_data WHERE date(create_at) = date('now')"
                ).fetchone()["cnt"]
                
                # 数据来源分布（Top 10）
                sources = conn.execute(
                    "SELECT source_name as name, COUNT(*) as value "
                    "FROM outlook_data GROUP BY source_name "
                    "ORDER BY value DESC LIMIT 10"
                ).fetchall()
                
                # 任务数量
                tasks = conn.execute(
                    "SELECT COUNT(*) as cnt FROM outlook_tasks"
                ).fetchone()["cnt"]
                
                # 采集趋势（最近 7 天）
                trend_data = conn.execute(
                    "SELECT date(create_at) as date, COUNT(*) as cnt "
                    "FROM outlook_data GROUP BY date ORDER BY date DESC LIMIT 7"
                ).fetchall()
                trend_data = list(reversed(trend_data))  # 正序排列
                
                # 任务状态分布
                task_status = conn.execute(
                    "SELECT status as name, COUNT(*) as value "
                    "FROM outlook_tasks GROUP BY status"
                ).fetchall()
                
                # 最近采集数据（Top 20）
                recent = conn.execute(
                    "SELECT title, publish_date FROM outlook_data "
                    "ORDER BY id DESC LIMIT 20"
                ).fetchall()
            
            self.write({
                "code": 0,
                "msg": "success",
                "data": {
                    "total": total,
                    "today": today,
                    "sources": [dict(r) for r in sources],
                    "tasks": tasks,
                    "trend": {
                        "dates": [r["date"] for r in trend_data],
                        "values": [r["cnt"] for r in trend_data]
                    },
                    "taskStatus": [dict(r) for r in task_status],
                    "recent": [dict(r) for r in recent]
                }
            })
        except Exception as e:
            self.write({
                "code": 1,
                "msg": f"获取图表数据失败: {str(e)}",
                "data": None
            })
```

#### 5.1.3 智慧舆情统计 API

```python
class SentimentStatsHandler(BaseHandler):
    """智慧舆情统计 API"""
    @tornado.web.authenticated
    def get(self):
        try:
            user_id = self.get_current_user_id()
            
            # 瞭望数据统计
            outlook_stats = SentimentRepository.get_outlook_data_stats()
            
            # 智能聊天数据统计
            conversations = IMRepository.get_user_conversations(user_id) if user_id else []
            messages = SentimentRepository.get_im_messages_summary(limit=1)
            
            self.write({
                "code": 0,
                "msg": "success",
                "data": {
                    "outlook": outlook_stats,
                    "im": {
                        "conversations": len(conversations),
                        "messages": len(messages)
                    }
                }
            })
        except Exception as e:
            self.write({
                "code": 1,
                "msg": f"获取统计数据失败: {str(e)}",
                "data": None
            })
    
    def get_current_user_id(self):
        """获取当前用户 ID"""
        from app.models.db import get_connection
        with get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM users WHERE username=?", 
                (self.current_user,)
            ).fetchone()
            return row["id"] if row else 0
```

#### 5.1.4 AI 舆情分析 API

```python
class SentimentAnalyzeHandler(BaseHandler):
    """智慧舆情分析 API"""
    @tornado.web.authenticated
    def post(self):
        try:
            # 1. 获取数据摘要
            outlook_data = SentimentRepository.get_outlook_data_summary(limit=50)
            outlook_stats = SentimentRepository.get_outlook_data_stats()
            im_conversations = SentimentRepository.get_im_conversations_summary(limit=30)
            im_messages = SentimentRepository.get_im_messages_summary(limit=100)
            
            # 2. 构建数据上下文
            data_context = {
                "outlook_data": outlook_data,
                "outlook_stats": outlook_stats,
                "im_conversations": im_conversations,
                "im_messages": im_messages,
                "im_stats": {
                    "conversations": len(im_conversations),
                    "messages": len(im_messages)
                }
            }
            
            # 3. 调用 AI 分析
            analysis = SentimentRepository.analyze_with_ai(data_context)
            
            # 4. 返回结果
            if "error" in analysis:
                self.write({
                    "code": 1,
                    "msg": analysis["error"],
                    "data": None
                })
            else:
                self.write({
                    "code": 0,
                    "msg": "分析成功",
                    "data": analysis
                })
        except Exception as e:
            self.write({
                "code": 1,
                "msg": f"分析失败: {str(e)}",
                "data": None
            })
```

### 5.2 数据仓库实现

#### 5.2.1 瞭望数据摘要

```python
class SentimentRepository:
    """智慧舆情数据仓库"""

    @staticmethod
    def get_outlook_data_summary(limit=50):
        """获取瞭望数据摘要"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT id, title, content, source_name, publish_date, create_at
                   FROM outlook_data
                   ORDER BY id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_outlook_data_stats():
        """获取瞭望数据统计"""
        with get_connection() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as cnt FROM outlook_data"
            ).fetchone()["cnt"]
            
            sources = conn.execute(
                "SELECT source_name, COUNT(*) as cnt "
                "FROM outlook_data GROUP BY source_name "
                "ORDER BY cnt DESC LIMIT 10"
            ).fetchall()
            
            recent = conn.execute(
                "SELECT COUNT(*) as cnt FROM outlook_data "
                "WHERE create_at >= datetime('now', '-24 hours')"
            ).fetchone()["cnt"]
            
            return {
                "total": total,
                "sources": [dict(r) for r in sources],
                "recent_24h": recent
            }
```

#### 5.2.2 智能聊天数据摘要

```python
    @staticmethod
    def get_im_conversations_summary(limit=30):
        """获取智能聊天会话摘要"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT c.id, c.type, c.name, c.last_message, c.last_message_at,
                          (SELECT COUNT(*) FROM chat_messages 
                           WHERE conversation_id = c.id) as msg_count
                   FROM im_conversations c
                   ORDER BY c.last_message_at DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]

    @staticmethod
    def get_im_messages_summary(limit=100):
        """获取智能聊天消息摘要"""
        with get_connection() as conn:
            rows = conn.execute(
                """SELECT cm.id, cm.conversation_id, cm.role, cm.content, cm.create_at,
                          c.type as conv_type, c.name as conv_name
                   FROM chat_messages cm
                   LEFT JOIN im_conversations c ON c.id = cm.conversation_id
                   WHERE cm.role = 'user'
                   ORDER BY cm.id DESC LIMIT ?""",
                (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
```

### 5.3 AI 分析核心实现

#### 5.3.1 获取默认模型

```python
class ModelRepository:
    @staticmethod
    def get_default_model():
        """获取默认 AI 模型"""
        with get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM models WHERE is_system_default=1 AND status=1"
            ).fetchone()
            return dict(row) if row else None
```

#### 5.3.2 AI 分析完整实现

```python
import json
import httpx
import re

class SentimentRepository:
    @staticmethod
    def analyze_with_ai(data_context: dict) -> dict:
        """使用 AI 模型分析舆情数据"""
        # 1. 获取默认模型
        model = ModelRepository.get_default_model()
        if not model:
            return {"error": "未配置默认 AI 模型"}

        # 2. 构建 Prompt
        prompt = f"""你是一个专业的舆情分析专家。请分析以下数据并提供风险评估报告。

## 数据概况

### 瞭望采集数据概览
- 数据总量: {data_context.get('outlook_stats', {}).get('total', 0)} 条
- 24 小时内新增: {data_context.get('outlook_stats', {}).get('recent_24h', 0)} 条
- 数据来源分布: {json.dumps(data_context.get('outlook_stats', {}).get('sources', []), ensure_ascii=False)}

### 瞭望数据样本（最近 {len(data_context.get('outlook_data', []))} 条）
{chr(10).join([f"- [{d.get('title', '无标题')}] 来源:{d.get('source_name', '未知')} 时间:{d.get('publish_date', '未知')}" for d in data_context.get('outlook_data', [])[:10]])}

### 智能聊天数据概览
- 会话数量: {data_context.get('im_stats', {}).get('conversations', 0)} 个
- 用户消息数量: {data_context.get('im_stats', {}).get('messages', 0)} 条

### 聊天消息样本（最近 {len(data_context.get('im_messages', []))} 条用户消息）
{chr(10).join([f"- [{m.get('conv_name', m.get('conv_type', '未知'))}] {m.get('content', '')[:100]}" for m in data_context.get('im_messages', [])[:10]])}

## 分析任务

请提供以下分析报告：

### 1. 舆情热点分析
- 当前热点话题有哪些
- 各话题的关注度排序

### 2. 情感倾向分析
- 整体情感倾向（正面/中性/负面）
- 负面舆情预警

### 3. 风险等级评估
- 高风险事项（需要立即关注）
- 中风险事项（需要持续跟踪）
- 低风险事项（常规关注）

### 4. 趋势预测
- 未来可能的发展趋势
- 建议的应对措施

请用 JSON 格式返回分析结果，格式如下：
```json
{{
  "hot_topics": [
    {{"topic": "话题名称", "heat": 85, "trend": "上升/下降/平稳", "sources": ["来源 1", "来源 2"]}}
  ],
  "sentiment": {{
    "overall": "正面/中性/负面",
    "positive_rate": 60,
    "neutral_rate": 25,
    "negative_rate": 15,
    "warnings": ["负面舆情预警 1", "负面舆情预警 2"]
  }},
  "risks": [
    {{"level": "高/中/低", "title": "风险标题", "description": "风险描述", "suggestion": "应对建议"}}
  ],
  "trends": {{
    "prediction": "趋势预测描述",
    "actions": ["建议措施 1", "建议措施 2"]
  }},
  "summary": "整体舆情总结"
}}
```"""

        try:
            # 3. 获取模型配置
            api_url = model.get("api_url", "")
            api_key = model.get("api_key", "")
            
            if not api_url:
                return {"error": "模型 API 地址未配置"}

            # 4. 构建请求
            headers = {
                "Content-Type": "application/json",
                "Authorization": f"Bearer {api_key}"
            }
            
            payload = {
                "model": model.get("code", ""),
                "messages": [
                    {"role": "system", "content": "你是一个专业的舆情分析专家，擅长数据分析和风险评估。"},
                    {"role": "user", "content": prompt}
                ],
                "temperature": 0.7,
                "max_tokens": 4000
            }

            # 5. 调用 AI API
            with httpx.Client(timeout=60.0) as client:
                resp = client.post(api_url, json=payload, headers=headers)
                resp.raise_for_status()
                result = resp.json()
                
                content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
                
                # 6. 解析 JSON（支持 markdown 代码块格式）
                json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
                if json_match:
                    content = json_match.group(1)
                
                try:
                    analysis = json.loads(content)
                    return analysis
                except json.JSONDecodeError:
                    return {"raw_analysis": content, "error": "JSON 解析失败"}
                    
        except Exception as e:
            return {"error": f"AI 分析失败：{str(e)}"}
```

### 5.4 前端实现

#### 5.4.1 Tab 切换逻辑

```javascript
function switchTab(tabName, btn) {
    // 移除所有 active 状态
    document.querySelectorAll('.tab-btn').forEach(function(b) { 
        b.classList.remove('active'); 
    });
    document.querySelectorAll('.tab-content').forEach(function(c) { 
        c.classList.remove('active'); 
    });
    
    // 设置当前 active 状态
    btn.classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');
    
    // 更新页面标题
    if (tabName === 'dashboard') {
        document.getElementById('pageTitle').textContent = '数智大屏';
        initDashboardCharts();
    } else if (tabName === 'earth') {
        document.getElementById('pageTitle').textContent = '3D 地球';
        initEarth();
    } else {
        document.getElementById('pageTitle').textContent = '智慧舆情分析';
    }
}
```

#### 5.4.2 统计数据加载

```javascript
function loadStats() {
    fetch('/api/sentiment/stats')
        .then(res => res.json())
        .then(res => {
            if (res.code === 0) {
                // 智慧舆情统计
                document.getElementById('outlookTotal').textContent = res.data.outlook.total || 0;
                document.getElementById('outlookRecent').textContent = res.data.outlook.recent_24h || 0;
                document.getElementById('imConversations').textContent = res.data.im.conversations || 0;
                document.getElementById('imMessages').textContent = res.data.im.messages || 0;
                
                // 数智大屏统计
                document.getElementById('dashTotal').textContent = res.data.outlook.total || 0;
                document.getElementById('dashToday').textContent = res.data.outlook.recent_24h || 0;
                document.getElementById('dashSources').textContent = (res.data.outlook.sources || []).length;
            }
        })
        .catch(err => console.error('加载统计失败:', err));
}
```

#### 5.4.3 AI 舆情分析请求

```javascript
function startAnalysis() {
    var btn = document.getElementById('btnAnalyze');
    btn.disabled = true;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin loading"></i> 分析中...';
    document.getElementById('loadingOverlay').style.display = 'flex';
    
    fetch('/api/sentiment/analyze', {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'X-XSRFToken': getCookie('_xsrf') || ''
        }
    })
    .then(res => res.json())
    .then(res => {
        document.getElementById('loadingOverlay').style.display = 'none';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-brain"></i> 开始智能分析';
        
        if (res.code === 0) {
            renderAnalysis(res.data);
            document.getElementById('emptyState').style.display = 'none';
            document.getElementById('analysisResult').style.display = 'block';
            layer.msg('分析完成', { icon: 1 });
        } else {
            layer.msg(res.msg || '分析失败', { icon: 2, time: 3000 });
        }
    })
    .catch(err => {
        document.getElementById('loadingOverlay').style.display = 'none';
        btn.disabled = false;
        btn.innerHTML = '<i class="fas fa-brain"></i> 开始智能分析';
        layer.msg('分析请求失败：' + err.message, { icon: 2, time: 3000 });
    });
}
```

#### 5.4.4 分析结果渲染

```javascript
function renderAnalysis(data) {
    // 1. 渲染热点分析
    var hotTopics = data.hot_topics || [];
    var hotTopicsHtml = '';
    for (var i = 0; i < hotTopics.length; i++) {
        var t = hotTopics[i];
        var heatClass = t.heat >= 80 ? 'heat-high' : (t.heat >= 50 ? 'heat-medium' : 'heat-low');
        hotTopicsHtml += '<div class="topic-card">'
            + '<div class="topic-header">'
            + '<div class="topic-name">' + t.topic + '</div>'
            + '<div class="topic-heat ' + heatClass + '">热度 ' + t.heat + '</div>'
            + '</div>'
            + '<div class="topic-trend">趋势：' + t.trend + '</div>'
            + '<div class="topic-sources">来源：' + (t.sources || []).join(', ') + '</div>'
            + '</div>';
    }
    document.getElementById('hotTopics').innerHTML = hotTopicsHtml || '<div class="empty-state"><p>暂无热点数据</p></div>';
    
    // 2. 渲染情感倾向
    var sentiment = data.sentiment || {};
    document.getElementById('sentimentPositive').style.width = (sentiment.positive_rate || 0) + '%';
    document.getElementById('sentimentNeutral').style.width = (sentiment.neutral_rate || 0) + '%';
    document.getElementById('sentimentNegative').style.width = (sentiment.negative_rate || 0) + '%';
    
    var warnings = sentiment.warnings || [];
    var warningHtml = '';
    for (var i = 0; i < warnings.length; i++) {
        warningHtml += '<div class="warning-item">' + warnings[i] + '</div>';
    }
    document.getElementById('warningList').innerHTML = warningHtml || '';
    
    // 3. 渲染风险评估
    var risks = data.risks || [];
    var riskHtml = '';
    for (var i = 0; i < risks.length; i++) {
        var r = risks[i];
        var riskClass = r.level === '高' ? 'risk-high' : (r.level === '中' ? 'risk-medium' : 'risk-low');
        riskHtml += '<div class="risk-item">'
            + '<div class="risk-header">'
            + '<div class="risk-title">' + r.title + '</div>'
            + '<div class="risk-level ' + riskClass + '">' + r.level + '风险</div>'
            + '</div>'
            + '<div class="risk-desc">' + r.description + '</div>'
            + '<div class="risk-suggestion">💡 ' + r.suggestion + '</div>'
            + '</div>';
    }
    document.getElementById('riskList').innerHTML = riskHtml || '<div class="empty-state"><p>暂无风险评估</p></div>';
    
    // 4. 渲染趋势预测
    var trends = data.trends || {};
    var trendHtml = '<p>' + (trends.prediction || '暂无趋势预测') + '</p>';
    var actions = trends.actions || [];
    if (actions.length > 0) {
        trendHtml += '<div class="trend-actions">';
        for (var i = 0; i < actions.length; i++) {
            trendHtml += '<div class="trend-action">' + actions[i] + '</div>';
        }
        trendHtml += '</div>';
    }
    document.getElementById('trendPrediction').innerHTML = trendHtml;
    
    // 5. 渲染舆情总结
    document.getElementById('summaryBox').textContent = data.summary || '暂无总结';
}
```

### 5.5 ECharts 图表实现

#### 5.5.1 数据来源分布饼图

```javascript
chartSource.setOption({
    tooltip: { trigger: 'item' },
    legend: { 
        bottom: '0%', 
        left: 'center', 
        textStyle: { color: '#8899bb', fontSize: 11 } 
    },
    series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        itemStyle: { 
            borderRadius: 8, 
            borderColor: '#0a0e1a', 
            borderWidth: 2 
        },
        label: { show: false },
        data: data.sources || []
    }]
});
```

#### 5.5.2 采集趋势折线图

```javascript
chartTrend.setOption({
    tooltip: { trigger: 'axis' },
    grid: { left: '3%', right: '4%', bottom: '3%', containLabel: true },
    xAxis: {
        type: 'category',
        boundaryGap: false,
        data: data.trend.dates || [],
        axisLine: { lineStyle: { color: '#334' } },
        axisLabel: { color: '#8899bb', fontSize: 10 }
    },
    yAxis: {
        type: 'value',
        splitLine: { lineStyle: { color: 'rgba(255,255,255,0.05)' } },
        axisLabel: { color: '#8899bb', fontSize: 10 }
    },
    series: [{
        data: data.trend.values || [],
        type: 'line',
        smooth: true,
        lineStyle: { color: '#1890ff', width: 2 },
        itemStyle: { color: '#1890ff' },
        areaStyle: {
            color: new echarts.graphic.LinearGradient(0, 0, 0, 1, [
                { offset: 0, color: 'rgba(24,144,255,0.3)' },
                { offset: 1, color: 'rgba(24,144,255,0)' }
            ])
        }
    }]
});
```

#### 5.5.3 任务状态分布饼图

```javascript
chartTaskStatus.setOption({
    tooltip: { trigger: 'item' },
    legend: { 
        bottom: '0%', 
        left: 'center', 
        textStyle: { color: '#8899bb', fontSize: 11 } 
    },
    series: [{
        type: 'pie',
        radius: ['40%', '70%'],
        itemStyle: { 
            borderRadius: 8, 
            borderColor: '#0a0e1a', 
            borderWidth: 2 
        },
        label: { show: false },
        data: data.taskStatus || []
    }]
});
```

### 5.6 Three.js 3D 地球实现

#### 5.6.1 初始化渲染器

```javascript
function initEarth() {
    if (earthInitialized) {
        // 已初始化，仅调整尺寸
        if (earthRenderer) {
            var canvas = document.getElementById('earthCanvas');
            var container = document.getElementById('earthContainer');
            if (canvas && container) {
                earthRenderer.setSize(container.clientWidth, container.clientHeight);
            }
        }
        return;
    }
    
    var canvas = document.getElementById('earthCanvas');
    var container = document.getElementById('earthContainer');
    if (!canvas || !container || typeof THREE === 'undefined') return;
    
    earthInitialized = true;
    
    // 创建渲染器
    earthRenderer = new THREE.WebGLRenderer({ 
        canvas: canvas, 
        antialias: true, 
        alpha: true 
    });
    earthRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    earthRenderer.setSize(container.clientWidth, container.clientHeight);
    earthRenderer.shadowMap.enabled = true;
    earthRenderer.shadowMap.type = THREE.PCFSoftShadowMap;
    
    // 创建场景
    earthScene = new THREE.Scene();
    
    // 创建相机
    earthCamera = new THREE.PerspectiveCamera(
        45, 
        container.clientWidth / container.clientHeight, 
        0.1, 
        1000
    );
    earthCamera.position.set(0, 0.5, 7);
    
    // 添加光源
    var hemiLight = new THREE.HemisphereLight(0x6677aa, 0x1a1a33, 0.8);
    earthScene.add(hemiLight);
    
    var ambientLight = new THREE.AmbientLight(0x333355, 0.9);
    earthScene.add(ambientLight);
    
    var sunLight = new THREE.DirectionalLight(0xfffff0, 1.5);
    sunLight.position.set(5, 3, 5);
    sunLight.castShadow = true;
    sunLight.shadow.mapSize.width = 1024;
    sunLight.shadow.mapSize.height = 1024;
    earthScene.add(sunLight);
    
    var fillLight = new THREE.DirectionalLight(0x6677aa, 0.4);
    fillLight.position.set(-3, 1, -3);
    earthScene.add(fillLight);
    
    // 创建地球组
    var earthGroup = new THREE.Group();
    earthScene.add(earthGroup);
    
    // 创建地球
    var earthGeom = new THREE.SphereGeometry(2, 64, 64);
    var textureLoader = new THREE.TextureLoader();
    
    var earthMat = new THREE.MeshPhongMaterial({
        map: textureLoader.load('https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg'),
        specularMap: textureLoader.load('https://threejs.org/examples/textures/planets/earth_specular_2048.jpg'),
        specular: new THREE.Color(0x333333),
        shininess: 5,
        normalMap: textureLoader.load('https://threejs.org/examples/textures/planets/earth_normal_2048.jpg'),
        normalScale: new THREE.Vector2(0.8, 0.8)
    });
    earthMesh = new THREE.Mesh(earthGeom, earthMat);
    earthMesh.castShadow = true;
    earthMesh.receiveShadow = true;
    earthGroup.add(earthMesh);
    
    // 创建云层
    var cloudGeom = new THREE.SphereGeometry(2.03, 64, 64);
    var cloudMat = new THREE.MeshPhongMaterial({
        map: textureLoader.load('https://threejs.org/examples/textures/planets/earth_clouds_1024.png'),
        transparent: true,
        opacity: 0.4,
        blending: THREE.AdditiveBlending,
        depthWrite: false
    });
    earthCloudMesh = new THREE.Mesh(cloudGeom, cloudMat);
    earthCloudMesh.renderOrder = 1;
    earthCloudMesh.material.depthTest = true;
    earthCloudMesh.material.depthWrite = false;
    earthGroup.add(earthCloudMesh);
    
    // 创建大气层光晕
    var glowGeom = new THREE.SphereGeometry(2.08, 64, 64);
    var glowMat = new THREE.ShaderMaterial({
        vertexShader: `
            varying vec3 vNormal;
            void main() {
                vNormal = normalize(normalMatrix * normal);
                gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
            }
        `,
        fragmentShader: `
            varying vec3 vNormal;
            void main() {
                float intensity = pow(0.65 - dot(vNormal, vec3(0.0, 0.0, 1.0)), 3.0);
                gl_FragColor = vec4(0.3, 0.6, 1.0, 1.0) * intensity * 0.35;
            }
        `,
        blending: THREE.AdditiveBlending,
        side: THREE.FrontSide,
        transparent: true,
        depthWrite: false
    });
    var glowMesh = new THREE.Mesh(glowGeom, glowMat);
    glowMesh.renderOrder = 2;
    glowMesh.material.depthTest = true;
    glowMesh.material.depthWrite = false;
    earthGroup.add(glowMesh);
    
    // 创建星空背景
    var starsGeom = new THREE.BufferGeometry();
    var starsCount = 3000;
    var starsPositions = new Float32Array(starsCount * 3);
    var starsColors = new Float32Array(starsCount * 3);
    
    for (var i = 0; i < starsCount * 3; i += 3) {
        var r = 30 + Math.random() * 70;
        var theta = Math.random() * Math.PI * 2;
        var phi = Math.acos(2 * Math.random() - 1);
        starsPositions[i] = r * Math.sin(phi) * Math.cos(theta);
        starsPositions[i+1] = r * Math.sin(phi) * Math.sin(theta);
        starsPositions[i+2] = r * Math.cos(phi);
        
        var bright = 0.5 + Math.random() * 0.5;
        var tint = Math.random();
        if (tint < 0.1) {
            starsColors[i] = 0.8; starsColors[i+1] = 0.9; starsColors[i+2] = 1.0;
        } else if (tint < 0.2) {
            starsColors[i] = 1.0; starsColors[i+1] = 0.85; starsColors[i+2] = 0.7;
        } else {
            starsColors[i] = bright; starsColors[i+1] = bright; starsColors[i+2] = bright;
        }
    }
    starsGeom.setAttribute('position', new THREE.BufferAttribute(starsPositions, 3));
    starsGeom.setAttribute('color', new THREE.BufferAttribute(starsColors, 3));
    var starsMat = new THREE.PointsMaterial({
        size: 0.15, 
        vertexColors: true, 
        blending: THREE.AdditiveBlending, 
        depthWrite: false, 
        transparent: true, 
        opacity: 0.9
    });
    var starsPoints = new THREE.Points(starsGeom, starsMat);
    earthScene.add(starsPoints);
    
    // 添加轨道控制器
    if (typeof THREE.OrbitControls !== 'undefined') {
        earthControls = new THREE.OrbitControls(earthCamera, canvas);
    }
    if (earthControls) {
        earthControls.enableDamping = true;
        earthControls.dampingFactor = 0.08;
        earthControls.minDistance = 3.5;
        earthControls.maxDistance = 15;
        earthControls.target.set(0, 0, 0);
        earthControls.autoRotate = true;
        earthControls.autoRotateSpeed = 0.3;
        earthControls.update();
        
        canvas.addEventListener('pointerdown', function() {
            earthControls.autoRotate = false;
        });
        canvas.addEventListener('pointerup', function() {
            setTimeout(function() {
                earthControls.autoRotate = true;
            }, 1500);
        });
    }
    
    // 窗口自适应
    window.addEventListener('resize', function() {
        if (!earthRenderer || !earthCamera) return;
        var c = document.getElementById('earthContainer');
        if (!c) return;
        earthCamera.aspect = c.clientWidth / c.clientHeight;
        earthCamera.updateProjectionMatrix();
        earthRenderer.setSize(c.clientWidth, c.clientHeight);
    });
    
    // 动画循环
    function animate() {
        requestAnimationFrame(animate);
        if (earthCloudMesh) earthCloudMesh.rotation.y += 0.0003;
        if (starsPoints) {
            starsPoints.rotation.y += 0.0001;
            starsPoints.rotation.x += 0.00005;
        }
        if (earthControls) earthControls.update();
        if (earthRenderer && earthScene && earthCamera) {
            earthRenderer.render(earthScene, earthCamera);
        }
    }
    animate();
}
```

---

## 六、构建与集成流程

### 6.1 文件结构

```
your-project/
├── app/
│   ├── controllers/
│   │   └── sentiment.py          # 舆情分析控制器
│   ├── models/
│   │   ├── sentiment.py          # 舆情数据仓库
│   │   ├── model.py              # AI 模型管理
│   │   ├── im.py                 # 智能聊天数据
│   │   ├── outlook.py            # 瞭望采集数据
│   │   └── db.py                 # 数据库连接
│   ├── templates/
│   │   └── sentiment.html        # 舆情分析页面
│   └── static/
│       ├── dist/
│       │   ├── echarts-5.5.0.min.js
│       │   ├── three-r128.min.js
│       │   ├── layui-v2.13.6/
│       │   └── fontawesome-free-5.15.4-web/
│       └── js/
│           └── gesture-*.js      # 手势识别模块（可选）
└── ...
```

### 6.2 数据库表结构

#### 6.2.1 瞭望数据表

```sql
CREATE TABLE outlook_data (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT,
    content TEXT,
    source_name TEXT,
    publish_date TEXT,
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 6.2.2 瞭望任务表

```sql
CREATE TABLE outlook_tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    status TEXT,
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 6.2.3 智能聊天会话表

```sql
CREATE TABLE im_conversations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    type TEXT,
    name TEXT,
    last_message TEXT,
    last_message_at DATETIME,
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

#### 6.2.4 聊天消息表

```sql
CREATE TABLE chat_messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    conversation_id INTEGER,
    role TEXT,
    content TEXT,
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (conversation_id) REFERENCES im_conversations(id)
);
```

#### 6.2.5 AI 模型配置表

```sql
CREATE TABLE models (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    code TEXT,
    api_url TEXT,
    api_key TEXT,
    status INTEGER DEFAULT 1,
    is_system_default INTEGER DEFAULT 0,
    total_requests INTEGER DEFAULT 0,
    total_tokens INTEGER DEFAULT 0,
    prompt_tokens INTEGER DEFAULT 0,
    completion_tokens INTEGER DEFAULT 0,
    last_used_at DATETIME,
    create_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 6.3 路由配置

在 Tornado 应用的路由表中添加以下路由：

```python
from app.controllers.sentiment import (
    SentimentHandler,
    DashboardChartsHandler,
    SentimentStatsHandler,
    SentimentAnalyzeHandler
)

handlers = [
    # 舆情分析页面
    (r'/sentiment', SentimentHandler),
    
    # 数智大屏图表数据 API
    (r'/api/dashboard/charts', DashboardChartsHandler),
    
    # 智慧舆情统计 API
    (r'/api/sentiment/stats', SentimentStatsHandler),
    
    # AI 舆情分析 API
    (r'/api/sentiment/analyze', SentimentAnalyzeHandler),
]
```

### 6.4 依赖安装

```bash
# Python 依赖
pip install tornado httpx

# 前端依赖（通过 CDN 加载，无需安装）
# - ECharts 5.5.0
# - Three.js r128
# - Layui 2.13.6
# - Font Awesome 5.15.4
```

---

## 七、核心设计模式

### 7.1 Repository 模式

数据访问层使用 Repository 模式，封装所有数据库操作：

```python
class SentimentRepository:
    """智慧舆情数据仓库"""
    
    @staticmethod
    def get_outlook_data_summary(limit=50):
        """获取瞭望数据摘要"""
        with get_connection() as conn:
            rows = conn.execute("SELECT ...", (limit,)).fetchall()
            return [dict(r) for r in rows]
```

### 7.2 MVC 架构

| 层 | 文件 | 职责 |
|---|---|---|
| **Model** | `sentiment.py`, `model.py` | 数据访问、业务逻辑 |
| **View** | `sentiment.html` | 页面渲染、数据展示 |
| **Controller** | `sentiment.py` (Handler) | 请求处理、响应返回 |

### 7.3 策略模式（AI Prompt）

通过动态构建 Prompt 实现不同的分析任务：

```python
prompt = f"""你是一个专业的舆情分析专家...

## 数据概况
...

## 分析任务
1. 舆情热点分析
2. 情感倾向分析
3. 风险等级评估
4. 趋势预测

请用 JSON 格式返回分析结果...
"""
```

### 7.4 观察者模式（前端事件）

前端使用事件监听实现用户交互：

```javascript
// Tab 切换
document.querySelectorAll('.tab-btn').forEach(function(btn) {
    btn.addEventListener('click', function() {
        switchTab(tabName, btn);
    });
});

// 分析按钮点击
document.getElementById('btnAnalyze').addEventListener('click', startAnalysis);
```

---

## 八、关键实现细节

### 8.1 AI 模型配置管理

#### 8.1.1 模型配置表结构

| 字段 | 类型 | 说明 |
|------|------|------|
| `id` | INTEGER | 主键 |
| `name` | TEXT | 模型名称 |
| `code` | TEXT | 模型代码 |
| `api_url` | TEXT | API 地址 |
| `api_key` | TEXT | API 密钥 |
| `status` | INTEGER | 状态（1=启用，0=禁用） |
| `is_system_default` | INTEGER | 是否默认模型 |

#### 8.1.2 获取默认模型

```python
@staticmethod
def get_default_model():
    """获取默认 AI 模型"""
    with get_connection() as conn:
        row = conn.execute(
            "SELECT * FROM models WHERE is_system_default=1 AND status=1"
        ).fetchone()
        return dict(row) if row else None
```

### 8.2 AI API 调用

#### 8.2.1 请求构建

```python
headers = {
    "Content-Type": "application/json",
    "Authorization": f"Bearer {api_key}"
}

payload = {
    "model": model.get("code", ""),
    "messages": [
        {"role": "system", "content": "你是一个专业的舆情分析专家..."},
        {"role": "user", "content": prompt}
    ],
    "temperature": 0.7,
    "max_tokens": 4000
}
```

#### 8.2.2 响应解析

```python
with httpx.Client(timeout=60.0) as client:
    resp = client.post(api_url, json=payload, headers=headers)
    resp.raise_for_status()
    result = resp.json()
    
    content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
    
    # 支持 markdown 代码块格式
    json_match = re.search(r'```json\s*(.*?)\s*```', content, re.DOTALL)
    if json_match:
        content = json_match.group(1)
    
    analysis = json.loads(content)
    return analysis
```

### 8.3 前端数据加载

#### 8.3.1 页面初始化

```javascript
// 页面加载时执行
loadStats();              // 加载统计数据
initDashboardCharts();    // 初始化图表
```

#### 8.3.2 图表懒加载

```javascript
function initDashboardCharts() {
    // 已初始化则仅调整尺寸
    if (chartSource) {
        chartSource.resize();
        chartTrend.resize();
        chartTaskStatus.resize();
        return;
    }
    
    // 首次初始化
    chartSource = echarts.init(document.getElementById('chartSource'));
    chartTrend = echarts.init(document.getElementById('chartTrend'));
    chartTaskStatus = echarts.init(document.getElementById('chartTaskStatus'));
    
    // 加载数据并渲染
    fetch('/api/dashboard/charts')
        .then(res => res.json())
        .then(res => { /* 渲染图表 */ });
}
```

### 8.4 3D 地球优化

#### 8.4.1 性能优化

```javascript
// 限制像素比
earthRenderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));

// 阴影优化
sunLight.shadow.mapSize.width = 1024;
sunLight.shadow.mapSize.height = 1024;

// 云层渲染优化
earthCloudMesh.material.depthTest = true;
earthCloudMesh.material.depthWrite = false;
```

#### 8.4.2 交互优化

```javascript
// 拖拽时停止自动旋转
canvas.addEventListener('pointerdown', function() {
    earthControls.autoRotate = false;
});

// 松开后恢复自动旋转
canvas.addEventListener('pointerup', function() {
    setTimeout(function() {
        earthControls.autoRotate = true;
    }, 1500);
});
```

---

## 九、AI 分析结果格式

### 9.1 期望的 JSON 格式

```json
{
  "hot_topics": [
    {
      "topic": "话题名称",
      "heat": 85,
      "trend": "上升/下降/平稳",
      "sources": ["来源 1", "来源 2"]
    }
  ],
  "sentiment": {
    "overall": "正面/中性/负面",
    "positive_rate": 60,
    "neutral_rate": 25,
    "negative_rate": 15,
    "warnings": ["负面舆情预警 1", "负面舆情预警 2"]
  },
  "risks": [
    {
      "level": "高/中/低",
      "title": "风险标题",
      "description": "风险描述",
      "suggestion": "应对建议"
    }
  ],
  "trends": {
    "prediction": "趋势预测描述",
    "actions": ["建议措施 1", "建议措施 2"]
  },
  "summary": "整体舆情总结"
}
```

### 9.2 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `hot_topics` | Array | 热点话题列表 |
| `hot_topics[].topic` | String | 话题名称 |
| `hot_topics[].heat` | Number | 热度值（0-100） |
| `hot_topics[].trend` | String | 趋势（上升/下降/平稳） |
| `hot_topics[].sources` | Array | 来源列表 |
| `sentiment.overall` | String | 整体情感倾向 |
| `sentiment.positive_rate` | Number | 正面情感比例（%） |
| `sentiment.neutral_rate` | Number | 中性情感比例（%） |
| `sentiment.negative_rate` | Number | 负面情感比例（%） |
| `sentiment.warnings` | Array | 负面预警列表 |
| `risks` | Array | 风险列表 |
| `risks[].level` | String | 风险等级（高/中/低） |
| `risks[].title` | String | 风险标题 |
| `risks[].description` | String | 风险描述 |
| `risks[].suggestion` | String | 应对建议 |
| `trends.prediction` | String | 趋势预测 |
| `trends.actions` | Array | 建议措施列表 |
| `summary` | String | 舆情总结 |

---

## 十、调试与测试

### 10.1 调试工具

#### 10.1.1 浏览器控制台

```javascript
// 查看统计数据加载情况
console.log('统计数据:', res.data);

// 查看 AI 分析结果
console.log('分析结果:', res.data);

// 查看图表实例
console.log('图表实例:', chartSource, chartTrend, chartTaskStatus);

// 查看 3D 地球状态
console.log('地球状态:', earthInitialized, earthRenderer, earthScene);
```

#### 10.1.2 后端日志

```python
import logging

logging.basicConfig(level=logging.DEBUG)

class SentimentAnalyzeHandler(BaseHandler):
    def post(self):
        logging.debug(f"获取数据摘要：outlook_data={len(outlook_data)}, im_messages={len(im_messages)}")
        logging.debug(f"AI 分析结果：{analysis}")
```

### 10.2 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| AI 分析失败 | 模型未配置 | 检查 `models` 表是否有默认模型 |
| AI 分析失败 | API 地址错误 | 检查 `api_url` 配置 |
| AI 分析失败 | JSON 解析失败 | 检查 Prompt 格式，确保 AI 返回 JSON |
| 图表不显示 | ECharts 未加载 | 检查 CDN 链接 |
| 3D 地球不显示 | Three.js 未加载 | 检查 CDN 链接 |
| 统计数据为空 | 数据库无数据 | 检查数据采集任务 |
| 页面加载慢 | 数据量过大 | 优化 SQL 查询，添加索引 |

### 10.3 性能优化建议

#### 10.3.1 数据库优化

```sql
-- 添加索引
CREATE INDEX idx_outlook_data_create_at ON outlook_data(create_at);
CREATE INDEX idx_outlook_data_source_name ON outlook_data(source_name);
CREATE INDEX idx_chat_messages_conversation_id ON chat_messages(conversation_id);
```

#### 10.3.2 前端优化

```javascript
// 图表懒加载
function initDashboardCharts() {
    if (chartSource) return; // 已初始化则跳过
    // ...
}

// 3D 地球懒加载
function initEarth() {
    if (earthInitialized) return; // 已初始化则跳过
    // ...
}
```

---

## 十一、扩展功能

### 11.1 实时数据更新

```javascript
// 定时刷新统计数据
setInterval(function() {
    loadStats();
}, 60000); // 每分钟刷新一次
```

### 11.2 数据导出

```python
class SentimentExportHandler(BaseHandler):
    """舆情数据导出"""
    @tornado.web.authenticated
    def get(self):
        data = SentimentRepository.get_outlook_data_summary(limit=1000)
        
        # 导出为 CSV
        import csv
        import io
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(['标题', '内容', '来源', '发布时间'])
        
        for row in data:
            writer.writerow([row['title'], row['content'], row['source_name'], row['publish_date']])
        
        self.set_header('Content-Type', 'text/csv')
        self.set_header('Content-Disposition', 'attachment; filename=sentiment_data.csv')
        self.write(output.getvalue())
```

### 11.3 定时分析

```python
from apscheduler.schedulers.background import BackgroundScheduler

scheduler = BackgroundScheduler()

def scheduled_analysis():
    """定时执行舆情分析"""
    data_context = {
        "outlook_data": SentimentRepository.get_outlook_data_summary(limit=50),
        "outlook_stats": SentimentRepository.get_outlook_data_stats(),
        # ...
    }
    analysis = SentimentRepository.analyze_with_ai(data_context)
    
    # 保存分析结果
    # ...

# 每天凌晨 2 点执行
scheduler.add_job(scheduled_analysis, 'cron', hour=2, minute=0)
scheduler.start()
```

---

## 十二、完整代码清单

### 12.1 需要创建的文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `sentiment.py` (Controller) | ~130 | 舆情分析控制器 |
| `sentiment.py` (Model) | ~180 | 舆情数据仓库 |
| `model.py` | ~150 | AI 模型管理 |
| `sentiment.html` | ~800 | 舆情分析页面 |

### 12.2 外部依赖

```html
<!-- ECharts -->
<script src="/static/dist/echarts-5.5.0.min.js"></script>

<!-- Three.js -->
<script src="/static/dist/three-r128.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>

<!-- Layui -->
<link rel="stylesheet" href="/static/dist/layui-v2.13.6/layui/css/layui.css">
<script src="/static/dist/layui-v2.13.6/layui/layui.js"></script>

<!-- Font Awesome -->
<link rel="stylesheet" href="/static/dist/fontawesome-free-5.15.4-web/css/all.min.css">
```

### 12.3 Python 依赖

```txt
tornado>=6.0
httpx>=0.24.0
apscheduler>=3.10.0  # 可选，用于定时任务
```

---

## 十三、实现流程总结

### 13.1 开发顺序建议

```
Phase 1: 基础框架
  1. 创建数据库表结构
  2. 创建 ModelRepository（模型管理）
  3. 创建 SentimentRepository（数据仓库）
  4. 创建 SentimentHandler（页面渲染）

Phase 2: 数智大屏
  5. 创建 DashboardChartsHandler（图表数据 API）
  6. 创建 ECharts 图表渲染逻辑
  7. 实现统计数据加载

Phase 3: 3D 地球
  8. 创建 Three.js 3D 地球场景
  9. 添加地球、云层、光晕、星空
  10. 实现轨道控制器

Phase 4: 智慧舆情分析
  11. 创建 SentimentAnalyzeHandler（AI 分析 API）
  12. 实现 AI Prompt 构建
  13. 实现 AI API 调用
  14. 实现 JSON 解析
  15. 创建前端结果渲染逻辑

Phase 5: 优化与完善
  16. 添加手势识别（可选）
  17. 性能优化
  18. 错误处理
  19. 测试验证
```

### 13.2 测试验证清单

- [ ] 页面可以正常访问
- [ ] 统计数据可以正常加载
- [ ] ECharts 图表可以正常显示
- [ ] 3D 地球可以正常渲染
- [ ] 3D 地球支持拖拽、缩放、旋转
- [ ] AI 分析可以正常触发
- [ ] AI 分析结果可以正常渲染
- [ ] 热点分析显示正确
- [ ] 情感倾向显示正确
- [ ] 风险评估显示正确
- [ ] 趋势预测显示正确
- [ ] 舆情总结显示正确
- [ ] 错误处理正常（模型未配置、API 调用失败等）
- [ ] 响应式布局正常

---

## 十四、附录

### 14.1 AI Prompt 模板

```
你是一个专业的舆情分析专家。请分析以下数据并提供风险评估报告。

## 数据概况

### 瞭望采集数据概览
- 数据总量：{total} 条
- 24 小时内新增：{recent_24h} 条
- 数据来源分布：{sources}

### 瞭望数据样本（最近 {limit} 条）
{data_samples}

### 智能聊天数据概览
- 会话数量：{conversations} 个
- 用户消息数量：{messages} 条

### 聊天消息样本（最近 {limit} 条用户消息）
{message_samples}

## 分析任务

请提供以下分析报告：

### 1. 舆情热点分析
- 当前热点话题有哪些
- 各话题的关注度排序

### 2. 情感倾向分析
- 整体情感倾向（正面/中性/负面）
- 负面舆情预警

### 3. 风险等级评估
- 高风险事项（需要立即关注）
- 中风险事项（需要持续跟踪）
- 低风险事项（常规关注）

### 4. 趋势预测
- 未来可能的发展趋势
- 建议的应对措施

请用 JSON 格式返回分析结果，格式如下：
```json
{
  "hot_topics": [...],
  "sentiment": {...},
  "risks": [...],
  "trends": {...},
  "summary": "..."
}
```
```

### 14.2 API 接口说明

| 接口 | 方法 | 参数 | 返回 |
|------|------|------|------|
| `/sentiment` | GET | 无 | HTML 页面 |
| `/api/sentiment/stats` | GET | 无 | 统计数据 |
| `/api/dashboard/charts` | GET | 无 | 图表数据 |
| `/api/sentiment/analyze` | POST | 无（自动获取数据） | AI 分析结果 |

### 14.3 浏览器兼容性

| 浏览器 | 最低版本 | 说明 |
|--------|---------|------|
| Chrome | 80+ | 推荐，性能最佳 |
| Firefox | 90+ | 支持良好 |
| Edge | 80+ | 基于 Chromium |
| Safari | 14+ | 部分功能可能受限 |

### 14.4 性能指标

| 指标 | 目标值 | 说明 |
|------|--------|------|
| 页面加载时间 | < 3s | 首次加载 |
| 统计数据加载 | < 1s | API 响应时间 |
| AI 分析时间 | < 30s | 取决于 AI 模型 |
| 3D 地球帧率 | > 30fps | 渲染性能 |
| ECharts 渲染 | < 500ms | 图表渲染时间 |

---

> 本文档基于实际项目实现编写，可直接用于新项目的舆情分析功能开发。
> 如有问题，请参考调试与测试章节进行排查。