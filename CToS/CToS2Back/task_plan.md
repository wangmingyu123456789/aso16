# 后端代码对照API文档修改计划

根据后端API接口文档对照检查意见，需要修改以下内容以使代码与API文档严格一致：

## 修改清单

### 1. Auth 模块
- [x] 添加 POST /api/auth/logout 端点（文档附录统计4个但未实现）
- [x] 移除 PUT /api/auth/me（文档未记载，仅标注TODO）

### 2. Chat 模块
- [x] 添加 DELETE /api/chat/conversation/{id}（删除对话）
- [x] 添加 PUT /api/chat/conversation/{id}（重命名对话）
- [x] 添加 POST /api/chat/message（SSE流式发送消息，对接llm_service）
- [x] 添加 POST /api/chat/message/stop（中断流式）
- [x] 保留现有 POST /api/chat/conversations/{conv_id}/messages

### 3. Watch 模块
- [x] GET /api/watch/sources 返回添加 headers, body_template 字段
- [x] POST /api/watch/sources/{id}/trigger 返回添加 raw_response 字段

### 4. Warehouse 模块
- [x] GET /api/warehouse/domains 响应改为纯字符串数组以匹配文档

### 5. Dashboard 模块 - 按文档调整所有响应字段
- [x] GET /api/dashboard/stats 改为文档字段
- [x] GET /api/dashboard/collect-trend 改为文档格式
- [x] GET /api/dashboard/token-trend 改为文档格式
- [x] GET /api/dashboard/wordcloud 改为文档字段名
- [x] GET /api/dashboard/earth 改为文档字段名
- [x] GET /api/dashboard/sentiment-stats 按文档调整

### 6. 更新对照检查意见
- [x] 更新 后端API接口文档对照检查意见.txt