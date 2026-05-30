# CToS2 外部 API 接口文档

> **服务地址**: `http://{host}:9877`
> **鉴权方式**: 无鉴权（开放接口）
> **数据格式**: JSON (所有请求/响应均使用 `Content-Type: application/json`)
> **统一响应格式**:
> ```json
> {
>   "code": 0,          // 0 表示成功，非0表示错误
>   "message": "ok",    // 提示信息
>   "data": { ... }     // 业务数据
> }
> ```

---

## 目录

1. [健康检查](#1-健康检查)
2. [天气代理服务](#2-天气代理服务)
3. [天气卡片图片下载](#3-天气卡片图片下载)
4. [系统文件下载](#4-系统文件下载)

---

## 1. 健康检查

检查外部服务是否正常运行。

### 请求

```
GET /health
```

### 响应示例

```json
{
  "status": "ok",
  "service": "external",
  "version": "1.0.0"
}
```

### 字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `status` | string | 服务状态，`"ok"` 表示正常 |
| `service` | string | 服务标识，固定为 `"external"` |
| `version` | string | 当前 API 版本号 |

---

## 2. 天气代理服务

接收外部请求 → 调用内部天气工具获取实时天气 → 生成天气卡片图片 → 将图片URL和文本消息**分两次**回调到远程服务器。

### 请求

```
POST /weather
```

### 请求体

```json
{
  "city": "北京",
  "conversation_id": "conv_xxxxx",
  "callback_url": "https://remote-server.com/callback"
}
```

### 请求参数字段

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `city` | string | 是 | 城市名称，支持中文（如"北京"、"东京"）和英文（如"Beijing"、"Tokyo"） |
| `conversation_id` | string | 是 | 会话标识，回调时会原样传回，用于关联消息 |
| `callback_url` | string | 是 | 远程服务器的回调地址，服务端会向此地址发送两条消息 |

### 回调协议

服务端会按顺序向 `callback_url` 发送 **2 次 POST 请求**：

#### 第 1 次回调：图片消息

```json
{
  "conversation_id": "conv_xxxxx",
  "type": "image",
  "image_url": "http://host:9877/files/weather_card/weather_Beijing_abc12345.png",
  "text": "🌤 北京 天气卡片"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `conversation_id` | string | 原请求的会话标识 |
| `type` | string | 消息类型，固定为 `"image"` |
| `image_url` | string | 天气卡片图片的可下载地址（通过外部服务提供） |
| `text` | string | 图片简短描述 |

> **注意**: 如果 Pillow 未安装或生成图片失败，**不会发送此回调**，仅发送文本消息。

#### 第 2 次回调：文本消息

```json
{
  "conversation_id": "conv_xxxxx",
  "type": "text",
  "text": "☀️ 北京 今日天气：晴\n🌡️ 当前温度：25°C（体感 26°C）\n💧 湿度：60%\n💨 风速：15 km/h 南风\n\n📅 未来天气：\n  05-31 ☀️ 晴 18°~28°\n  06-01 ☀️ 晴 20°~30°\n  06-02 ⛅ 多云 19°~27°"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| `conversation_id` | string | 原请求的会话标识 |
| `type` | string | 消息类型，固定为 `"text"` |
| `text` | string | 格式化天气信息文本，包含当前天气和未来3天预报 |

### 成功响应

**HTTP 200**

```json
{
  "code": 0,
  "message": "ok",
  "data": {
    "city": "北京",
    "weather": {
      "temp_c": "25",
      "description": "☀️ 晴",
      "humidity": "60",
      "wind": "南风 15 km/h"
    },
    "image_url": "/files/weather_card/weather_Beijing_abc12345.png",
    "text": "☀️ 北京 今日天气：晴\n🌡️ 当前温度：25°C（体感 26°C）\n💧 湿度：60%\n💨 风速：15 km/h 南风\n\n📅 未来天气：\n  05-31 ☀️ 晴 18°~28°\n  06-01 ☀️ 晴 20°~30°\n  06-02 ⛅ 多云 19°~27°",
    "forward_to": "https://remote-server.com/callback",
    "forward_status": "success"
  }
}
```

### 错误响应

**天气查询失败 — HTTP 502**

```json
{
  "code": -1,
  "message": "天气查询失败: 未找到该城市的天气数据",
  "data": null
}
```

**缺少 httpx 库 — HTTP 500**

```json
{
  "code": -1,
  "message": "缺少 httpx 库",
  "data": null
}
```

### 响应字段说明

| 字段 | 类型 | 说明 |
|------|------|------|
| `data.city` | string | 查询的城市名称 |
| `data.weather.temp_c` | string | 当前温度（摄氏度） |
| `data.weather.description` | string | 天气描述（含 emoji） |
| `data.weather.humidity` | string | 湿度百分比 |
| `data.weather.wind` | string | 风向和风速 |
| `data.image_url` | string\|null | 天气卡片图片的相对路径，生成失败时为 `null` |
| `data.text` | string | 格式化天气文本（同回调中的文本） |
| `data.forward_to` | string | 回调的目标地址 |
| `data.forward_status` | string | 回调状态: `"success"`(全部成功) / `"partial_failure"`(部分失败) |

---

## 3. 天气卡片图片下载

下载天气代理服务生成的天气卡片图片（PNG格式）。

### 请求

```
GET /files/weather_card/{filename}
```

### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `filename` | string | 文件名，格式为 `weather_{城市}_{随机}.png` |

### 响应

- **HTTP 200**: 返回 PNG 图片，`Content-Type: image/png`
- **HTTP 400**: 文件类型无效（仅允许 `.png` 文件）
- **HTTP 404**: 文件不存在

### 示例

```bash
curl -O http://localhost:9877/files/weather_card/weather_Beijing_abc12345.png
```

---

## 4. 系统文件下载

通过文件ID下载系统中已上传的任意文件（无鉴权）。

### 请求

```
GET /files/{file_id}/download
```

### 路径参数

| 参数 | 类型 | 说明 |
|------|------|------|
| `file_id` | integer | 系统中的文件记录ID（来自文件管理模块） |

### 响应

- **HTTP 200**: 文件内容（根据MIME类型决定内联预览或附件下载）
  - 图片、文本、PDF 类型 → `Content-Disposition: inline`（浏览器直接预览）
  - 其他类型 → `Content-Disposition: attachment`（触发下载）
- **HTTP 404**: 文件不存在或文件存储已丢失

### 响应头说明

| 响应头 | 说明 |
|--------|------|
| `Content-Type` | 文件的 MIME 类型（如 `image/png`、`application/pdf` 等） |
| `Content-Disposition` | 控制浏览器的展示方式（`inline` 预览 / `attachment` 下载），支持中文文件名 |

### 示例

```bash
# 下载文件 ID 为 42 的文件
curl -O http://localhost:9877/files/42/download

# 直接预览图片（浏览器打开即可显示）
open http://localhost:9877/files/42/download
```

---

## 附录

### A. 启动方式

```bash
# 方式1：通过统一入口启动（同时启动主服务和外部服务）
python run.py

# 方式2：单独启动外部服务
cd CToS2Back && python external.py
```

### B. 配置项（.env 文件）

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `EXTERNAL_PORT` | `9877` | 外部服务监听端口 |
| `EXTERNAL_BASE_URL` | `http://localhost:9877` | 外部服务的外部可访问地址（回调图片URL以此为前缀） |
| `APP_PORT` | `8000` | 主服务端口（不影响外部服务） |

### C. 完整调用示例（curl）

```bash
# 1. 健康检查
curl http://localhost:9877/health

# 2. 查询北京天气（回调到本地测试服务器）
curl -X POST http://localhost:9877/weather \
  -H "Content-Type: application/json" \
  -d '{
    "city": "北京",
    "conversation_id": "conv_001",
    "callback_url": "https://your-server.com/callback"
  }'

# 3. 下载天气卡片图片
curl -O http://localhost:9877/files/weather_card/weather_Beijing_abc12345.png

# 4. 下载系统文件（ID=1）
curl -O http://localhost:9877/files/1/download
```

### D. 注意事项

1. **天气代理会发送 2 次回调**：先发图片消息，再发文本消息。远程服务器需按 `type` 字段区分处理。
2. **图片非必达**：若 Pillow 未安装或生成失败，图片回调会被跳过，仅发送文本回调。
3. **文件安全**：天气卡片下载做了 `.png` 后缀校验和路径穿越防护；系统文件下载需文件 ID 有效。
4. **无鉴权**：所有外部接口均无鉴权，建议在生产环境中通过防火墙/反向代理限制访问来源。