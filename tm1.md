# 手势交互系统 - 完整实现指南

> 本文档用于在另一个未实现手势交互的项目中，完整复现手势识别功能
>
> **文档版本**: v1.0
> **创建日期**: 2026-05-29
> **适用场景**: 基于 Web 的手势识别交互系统

---

## 一、技术选型

### 1.1 核心技术栈

| 技术 | 版本 | 用途 | 说明 |
|------|------|------|------|
| **MediaPipe Hands** | 0.4.x | 手部关键点检测 | Google 开源的机器学习库，支持实时手部 21 点检测 |
| **原生 JavaScript** | ES5+ | 手势规则引擎 | 无需额外框架，纯 JS 实现手势识别算法 |
| **HTML5 Canvas** | - | 视觉反馈渲染 | 绘制手部关键点和连接线 |
| **HTML5 Video** | - | 摄像头视频流 | 实时获取摄像头画面 |
| **LocalStorage** | - | 设置持久化 | 保存用户自定义手势设置 |
| **SessionStorage** | - | 跨模块状态保持 | 摄像头状态跨页面保持 |

### 1.2 为什么选择 MediaPipe Hands

1. **无需后端**: 纯前端运行，无需服务器推理
2. **实时性能**: 支持 30fps 实时检测
3. **轻量级**: 模型文件约 10MB，支持 CDN 加载
4. **21 点手部关键点**: 提供完整的手部骨骼信息
5. **跨浏览器兼容**: 支持 Chrome、Firefox、Edge 等主流浏览器

### 1.3 文件依赖

```
# MediaPipe Hands CDN 依赖（通过 jsdelivr CDN 加载）
https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.js
https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js
https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils@0.3/drawing_utils.js
```

---

## 二、系统架构设计

### 2.1 整体架构

```
┌─────────────────────────────────────────────────────────────┐
│                        用户浏览器                            │
│  ┌──────────────────────────────────────────────────────┐   │
│  │                    手势识别面板                        │   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────────────┐    │   │
│  │  │ 摄像头   │→ │ 视频流    │→ │ MediaPipe Hands  │    │   │
│  │  │ 采集     │  │ 渲染      │  │ 手部检测          │    │   │
│  │  └─────────┘  └──────────┘  └────────┬─────────┘    │   │
│  │                                      │               │   │
│  │  ┌─────────┐  ┌──────────┐  ┌────────▼─────────┐    │   │
│  │  │ 业务操作 │← │ 事件总线  │← │ 手势规则引擎      │    │   │
│  │  │ (导航/   │  │ (分发/   │  │ (7种手势识别)     │    │   │
│  │  │  滚动/   │  │  监听)   │  │                  │    │   │
│  │  │  暂停)   │  └──────────┘  └──────────────────┘    │   │
│  │  └─────────┘                                        │   │
│  │  ┌──────────────────────────────────────────────┐   │   │
│  │  │           视觉反馈层 (Canvas 绘制)             │   │   │
│  │  └──────────────────────────────────────────────┘   │   │
│  └──────────────────────────────────────────────────────┘   │
│  ┌──────────────────────────────────────────────────────┐   │
│  │           设置管理层 (LocalStorage)                   │   │
│  └──────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 模块划分

| 模块 | 文件名 | 职责 |
|------|--------|------|
| **核心控制器** | `gesture.js` | 摄像头管理、MediaPipe 初始化、结果处理、导航控制 |
| **规则引擎** | `gesture-rule-engine.js` | 7 种手势的检测算法 |
| **事件总线** | `gesture-event-bus.js` | 手势事件分发、业务映射、中间件 |
| **视觉反馈** | `gesture-feedback.js` | 手势识别的可视化反馈 |
| **设置管理** | `gesture-settings.js` | 用户设置持久化、配置加载/保存 |
| **UI 组件** | `gesture_panel.html` | 手势面板 HTML/CSS 模板 |

### 2.3 数据流

```
摄像头采集 → 视频帧 → MediaPipe 检测 → 21 点手部关键点
    ↓
规则引擎检测 → 手势类型 + 置信度
    ↓
事件总线分发 → 业务映射回调
    ↓
执行业务操作 → 视觉反馈更新
```

---

## 三、完整功能清单

### 3.1 手势类型（7 种）

| 手势 | 图标 | 触发条件 | 业务操作 | 优先级 |
|------|------|---------|---------|--------|
| **食指向上** | ☝️ | 食指伸直，其他手指弯曲，保持 400ms | 选中下一条/下一条记录 | P0 |
| **食指向下** | 👇 | 食指向下伸直，其他手指弯曲，保持 400ms | 选中上一条/上一条记录 | P0 |
| **握拳** | ✊ | 所有指尖靠近手腕，保持 600ms | 暂停当前任务 | P0 |
| **左滑** | 👈 | 手掌中心向左移动 > 0.1（归一化），1 秒内 | 切换上一个模块 | P0 |
| **右滑** | 👉 | 手掌中心向右移动 > 0.1（归一化），1 秒内 | 切换下一个模块 | P0 |
| **上滑** | 🖐️ | 手掌中心向上移动 > 0.1（归一化），1 秒内 | 页面向下滚动 | P1 |
| **下滑** | 🖐️ | 手掌中心向下移动 > 0.1（归一化），1 秒内 | 页面向上滚动 | P1 |

### 3.2 功能特性

| 功能 | 说明 |
|------|------|
| **摄像头管理** | 启动/停止摄像头，资源正确释放，避免内存泄漏 |
| **帧率控制** | 可配置处理帧率（10/15/20/30 FPS），平衡性能与精度 |
| **视觉反馈** | Canvas 绘制手部关键点和连接线，实时显示识别状态 |
| **设置持久化** | 用户自定义设置保存到 LocalStorage，下次打开自动加载 |
| **跨模块保持** | 摄像头状态通过 SessionStorage 保持，切换页面自动恢复 |
| **新手引导** | 首次使用时弹出引导教程，逐步介绍手势用法 |
| **手势开关** | 可单独启用/禁用每种手势，灵活控制 |
| **防抖机制** | 手势触发后设置冷却时间，避免重复触发 |
| **面板折叠** | 手势面板可折叠为小圆点，不遮挡页面内容 |

---

## 四、UI 页面设计

### 4.1 手势面板布局

```
┌─────────────────────────────────┐
│ 🖐️ 手势识别              ⚙️ ▼  │  ← 标题栏（设置按钮 + 折叠按钮）
├─────────────────────────────────┤
│ ● 已检测到手部                   │  ← 状态指示（绿点/灰点/红点）
│ ┌─────────────────────────────┐ │
│ │                             │ │
│ │      摄像头视频画面          │ │  ← 视频 + Canvas 叠加
│ │    （手部关键点绘制在上面）   │ │
│ │                             │ │
│ └─────────────────────────────┘ │
│ ☝️ 食指向上 - 下一条             │  ← 当前识别到的手势
│ ┌─────────────────────────────┐ │
│ │ 实时识别状态                 │ │
│ │ ☝️ 食指向上 - 下一条          │ │  ← 实时手势状态
│ │ 置信度: 90.0%               │ │
│ └─────────────────────────────┘ │
│ [📷 启动摄像头]                 │  ← 启动/停止按钮
│ ─────────────────────────────── │
│ 支持的手势                       │
│ ☝️ 食指向上  👇 食指向下         │
│ ✊ 握拳      👈 左滑             │
│ 👉 右滑                          │
│ ─────────────────────────────── │
│ [🎓 新手引导]                   │  ← 新手引导按钮
└─────────────────────────────────┘
```

### 4.2 CSS 样式（核心样式）

```css
/* 手势面板容器 */
.gesture-panel {
    position: fixed;
    top: 80px;
    right: 20px;
    width: 240px;
    background: rgba(15, 20, 40, 0.92);
    border: 1px solid rgba(100, 120, 200, 0.25);
    border-radius: 12px;
    z-index: 1000;
    backdrop-filter: blur(12px);
    box-shadow: 0 8px 32px rgba(0, 0, 0, 0.4);
    overflow: hidden;
    transition: all 0.3s;
}

/* 折叠状态 */
.gesture-panel.collapsed {
    width: 48px;
    height: 48px;
    border-radius: 50%;
    cursor: pointer;
}
.gesture-panel.collapsed .gp-body { display: none; }

/* 状态指示点 */
.gp-dot {
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: #556;
    transition: background 0.3s;
}
.gp-dot.active {
    background: #00e676;
    box-shadow: 0 0 8px rgba(0, 230, 118, 0.5);
}
.gp-dot.error {
    background: #ff5252;
    box-shadow: 0 0 8px rgba(255, 82, 82, 0.5);
}

/* 视频容器 */
.gp-video-wrap {
    position: relative;
    width: 100%;
    aspect-ratio: 4/3;
    border-radius: 8px;
    overflow: hidden;
    background: #000;
    margin-bottom: 10px;
}
.gp-video-wrap video {
    width: 100%;
    height: 100%;
    object-fit: cover;
    transform: scaleX(-1);  /* 镜像翻转 */
}
.gp-video-wrap canvas {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    transform: scaleX(-1);  /* 镜像翻转 */
}

/* 实时手势状态 */
.gp-live-status {
    margin-top: 8px;
    padding: 8px;
    background: rgba(0, 0, 0, 0.3);
    border-radius: 6px;
    text-align: center;
    border: 1px solid rgba(100, 120, 200, 0.15);
}
.gp-live-gesture {
    font-size: 16px;
    font-weight: bold;
    color: #00e676;
    min-height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    gap: 4px;
}
.gp-live-gesture.waiting {
    color: #556;
    font-size: 12px;
}
.gp-live-confidence {
    font-size: 10px;
    color: #7788aa;
    margin-top: 2px;
}
```

---

## 五、核心实现细节

### 5.1 MediaPipe Hands 初始化

```javascript
// 创建 Hands 实例
hands = new Hands({
    locateFile: function(file) {
        return 'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/' + file;
    }
});

// 配置检测参数
hands.setOptions({
    maxNumHands: 2,              // 最多检测 2 只手
    modelComplexity: 1,          // 模型复杂度 (0=轻量, 1=标准)
    minDetectionConfidence: 0.7, // 检测置信度阈值
    minTrackingConfidence: 0.5   // 跟踪置信度阈值
});

// 绑定结果处理回调
hands.onResults(onResults);

// 启动摄像头
camera = new Camera(videoElement, {
    onFrame: function() {
        return hands.send({ image: videoElement });
    },
    width: 320,
    height: 240
});
camera.start();
```

### 5.2 手部关键点索引

MediaPipe Hands 返回 21 个手部关键点，索引如下：

```javascript
// 手腕
var WRIST = 0;

// 拇指
var THUMB_CMC = 1, THUMB_MCP = 2, THUMB_IP = 3, THUMB_TIP = 4;

// 食指
var INDEX_MCP = 5, INDEX_PIP = 6, INDEX_DIP = 7, INDEX_TIP = 8;

// 中指
var MIDDLE_MCP = 9, MIDDLE_PIP = 10, MIDDLE_DIP = 11, MIDDLE_TIP = 12;

// 无名指
var RING_MCP = 13, RING_PIP = 14, RING_DIP = 15, RING_TIP = 16;

// 小指
var PINKY_MCP = 17, PINKY_PIP = 18, PINKY_DIP = 19, PINKY_TIP = 20;
```

### 5.3 手势检测算法

#### 5.3.1 食指向上检测

```javascript
function detectIndexUp(landmarks) {
    // 1. 食指伸直（指尖距离 MCP 关节较远）
    var indexExtended = isFingerExtended(landmarks, INDEX_MCP, INDEX_TIP);
    
    // 2. 中指、无名指、小指弯曲
    var middleCurled = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_TIP);
    var ringCurled = isFingerCurled(landmarks, RING_MCP, RING_TIP);
    var pinkyCurled = isFingerCurled(landmarks, PINKY_MCP, PINKY_TIP);
    var curledCount = (middleCurled ? 1 : 0) + (ringCurled ? 1 : 0) + (pinkyCurled ? 1 : 0);
    
    // 3. 拇指弯曲
    var thumbCurled = isFingerCurled(landmarks, THUMB_MCP, THUMB_TIP);
    
    // 4. 食指指尖在 PIP 关节上方（y 坐标更小）
    var indexTip = landmarks[INDEX_TIP];
    var indexPip = landmarks[INDEX_PIP];
    var indexPointingUp = indexTip.y < indexPip.y;
    
    // 5. 所有条件满足，持续保持 400ms 后触发
    if (indexExtended && curledCount >= 2 && thumbCurled && indexPointingUp) {
        if (!holdStartTime['index_up']) {
            holdStartTime['index_up'] = Date.now();
        }
        var holdDuration = Date.now() - holdStartTime['index_up'];
        if (holdDuration >= 400 && canTrigger('index_up')) {
            holdStartTime['index_up'] = null;
            markTriggered('index_up');
            return { type: 'index_up', confidence: 0.9, targetArea: 'global' };
        }
    } else {
        holdStartTime['index_up'] = null;
    }
    return null;
}
```

#### 5.3.2 握拳检测

```javascript
function detectFist(landmarks) {
    var tips = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP];
    var allClose = true;
    var maxDist = 0;
    
    // 所有指尖靠近手腕
    for (var i = 0; i < tips.length; i++) {
        var dist = distance(landmarks[tips[i]], landmarks[WRIST]);
        maxDist = Math.max(maxDist, dist);
        if (dist > 0.25) {  // 阈值
            allClose = false;
        }
    }
    
    // 持续保持 600ms 后触发
    if (allClose) {
        if (!holdStartTime['fist']) {
            holdStartTime['fist'] = Date.now();
        }
        var holdDuration = Date.now() - holdStartTime['fist'];
        if (holdDuration >= 600 && canTrigger('fist')) {
            holdStartTime['fist'] = null;
            markTriggered('fist');
            return {
                type: 'fist',
                confidence: 1 - maxDist / 0.25,
                targetArea: 'global'
            };
        }
    } else {
        holdStartTime['fist'] = null;
    }
    return null;
}
```

#### 5.3.3 滑动检测（以右滑为例）

```javascript
function detectSwipeRight() {
    if (trajectoryBuffer.length < 5) return null;
    
    var recentFrames = trajectoryBuffer.slice(-5);
    var first = recentFrames[0];
    var last = recentFrames[recentFrames.length - 1];
    
    var deltaX = last.x - first.x;          // 水平位移
    var deltaY = Math.abs(first.y - last.y); // 垂直位移
    var deltaTime = last.time - first.time;  // 时间差
    
    // 向右移动 > 0.1，时间 < 1000ms，垂直位移较小
    if (deltaX > 0.1 && deltaTime < 1000 && deltaTime > 100 &&
        deltaY < deltaX * 0.6 && canTrigger('swipe_right')) {
        markTriggered('swipe_right');
        return {
            type: 'swipe_right',
            confidence: Math.min(1, deltaX / 0.2),
            targetArea: 'global'
        };
    }
    return null;
}
```

### 5.4 事件总线设计

```javascript
// 事件总线类
function GestureEventBus() {
    this.listeners = {};
    this.middleware = [];
    this.eventHistory = [];
}

// 注册监听器
GestureEventBus.prototype.on = function(gestureType, callback, priority) {
    if (!this.listeners[gestureType]) {
        this.listeners[gestureType] = [];
    }
    this.listeners[gestureType].push({ callback: callback, priority: priority });
    this.listeners[gestureType].sort(function(a, b) {
        return b.priority - a.priority;
    });
};

// 触发事件
GestureEventBus.prototype.emit = function(event) {
    event.timestamp = Date.now();
    event.pageUrl = window.location.pathname;
    
    // 执行中间件
    for (var i = 0; i < this.middleware.length; i++) {
        var filteredEvent = this.middleware[i](event);
        if (!filteredEvent) return;
        event = filteredEvent;
    }
    
    // 执行监听器
    var listeners = this.listeners[event.gestureType] || [];
    for (var j = 0; j < listeners.length; j++) {
        listeners[j].callback(event);
    }
};

// 业务映射注册
function registerBusinessMappings() {
    gestureBus.on('index_up', function(event) {
        if (typeof window.selectNextItem === 'function') {
            window.selectNextItem();
        }
    }, 10);

    gestureBus.on('swipe_right', function(event) {
        if (typeof window.navigateModule === 'function') {
            window.navigateModule(1);
        }
    }, 10);
    
    // ... 其他手势映射
}
```

---

## 六、构建与集成流程

### 6.1 文件结构

```
your-project/
├── app/
│   ├── static/
│   │   └── js/
│   │       ├── gesture.js              # 核心控制器
│   │       ├── gesture-rule-engine.js  # 规则引擎
│   │       ├── gesture-event-bus.js    # 事件总线
│   │       ├── gesture-feedback.js     # 视觉反馈
│   │       └── gesture-settings.js     # 设置管理
│   └── templates/
│       └── components/
│           └── gesture_panel.html      # 手势面板组件
└── ...
```

### 6.2 页面集成步骤

#### 步骤 1: 引入 MediaPipe 依赖

在页面 `<head>` 中引入 MediaPipe 库：

```html
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils@0.3/drawing_utils.js"></script>
```

#### 步骤 2: 引入手势模块脚本

在页面底部引入手势模块（注意顺序）：

```html
<script src="/static/js/gesture-settings.js?v=1"></script>
<script src="/static/js/gesture-rule-engine.js?v=1"></script>
<script src="/static/js/gesture-feedback.js?v=1"></script>
<script src="/static/js/gesture-event-bus.js?v=1"></script>
<script src="/static/js/gesture.js?v=1"></script>
```

#### 步骤 3: 引入手势面板组件

在页面 body 中引入手势面板 HTML：

```html
{% include 'components/gesture_panel.html' %}
```

或者直接复制 `gesture_panel.html` 的内容到页面中。

#### 步骤 4: 配置导航项

在 `gesture.js` 中修改 `navItems` 数组，适配你的项目路由：

```javascript
var navItems = [
    { name: '首页', url: '/home' },
    { name: '模块 A', url: '/module-a' },
    { name: '模块 B', url: '/module-b' },
    // ... 根据你的项目路由配置
];
```

### 6.3 脚本加载顺序说明

```
1. gesture-settings.js    → 初始化设置管理，加载 localStorage 配置
2. gesture-rule-engine.js → 初始化规则引擎，注册手势检测算法
3. gesture-feedback.js    → 初始化视觉反馈模块
4. gesture-event-bus.js   → 初始化事件总线，注册业务映射（DOMContentLoaded 时自动 init）
5. gesture.js             → 初始化核心控制器，绑定 DOM 元素
```

---

## 七、核心设计模式

### 7.1 模块模式（IIFE）

所有模块使用立即执行函数表达式（IIFE）封装，避免全局污染：

```javascript
(function() {
    'use strict';
    
    // 私有变量和函数
    var privateVar = 'xxx';
    function privateFunc() { }
    
    // 暴露到全局
    window.MyModule = {
        publicFunc: function() { }
    };
})();
```

### 7.2 观察者模式（事件总线）

手势事件总线使用观察者模式，实现手势检测与业务逻辑的解耦：

```
手势检测 → emit(event) → 中间件过滤 → 监听器回调 → 业务操作
```

### 7.3 策略模式（规则引擎）

每种手势检测是一个独立的策略函数：

```javascript
function detectGesture(landmarks) {
    recordTrajectory(landmarks);
    
    // 按优先级依次检测
    var result = detectIndexUp(landmarks);
    if (result) return result;
    
    result = detectIndexDown(landmarks);
    if (result) return result;
    
    result = detectFist(landmarks);
    if (result) return result;
    
    result = detectSwipeLeft();
    if (result) return result;
    
    // ... 其他手势
    return null;
}
```

### 7.4 状态机模式（摄像头管理）

摄像头状态管理使用状态机模式：

```
未启动 → 启动中 → 运行中 → 暂停 → 恢复 → 运行中
                              ↓
                           停止 → 未启动
```

---

## 八、关键实现细节

### 8.1 摄像头资源释放

切换页面时必须正确释放摄像头资源，避免内存泄漏：

```javascript
// 导航前释放摄像头
function navigateModule(direction) {
    if (cameraRunning) {
        // 1. 保存恢复标记
        sessionStorage.setItem('gesture_camera_restore', 'true');
        
        // 2. 停止摄像头
        if (camera) {
            try { camera.stop(); } catch(e) { }
            camera = null;
        }
        
        // 3. 释放视频流
        if (videoElement && videoElement.srcObject) {
            var tracks = videoElement.srcObject.getTracks();
            tracks.forEach(function(track) { track.stop(); });
            videoElement.srcObject = null;
        }
        
        cameraRunning = false;
    }
    
    // 4. 跳转页面
    setTimeout(function() {
        window.location.href = navItems[currentIndex].url;
    }, 1500);
}
```

### 8.2 跨模块摄像头恢复

新页面加载后自动恢复摄像头：

```javascript
// 页面加载时检查恢复标记
if (sessionStorage.getItem('gesture_camera_restore') === 'true') {
    sessionStorage.removeItem('gesture_camera_restore');
    
    // 渐进式重试策略
    function tryRestoreCamera(attempt) {
        if (attempt > 30) return;
        
        var handsLoaded = typeof Hands !== 'undefined';
        var toggleExists = typeof window.toggleCamera === 'function';
        
        if (handsLoaded && toggleExists && !cameraRunning) {
            window.toggleCamera();
        } else {
            var delay = attempt <= 5 ? 300 : attempt <= 10 ? 500 : attempt <= 20 ? 1000 : 2000;
            setTimeout(function() {
                tryRestoreCamera(attempt + 1);
            }, delay);
        }
    }
    
    tryRestoreCamera(1);
}
```

### 8.3 帧率控制

```javascript
var targetFrameRate = 15;  // 可配置
var lastProcessTime = 0;

function onResults(results) {
    var now = Date.now();
    var frameInterval = 1000 / targetFrameRate;
    
    // 跳过未达到帧率的帧
    if (now - lastProcessTime < frameInterval) {
        return;
    }
    lastProcessTime = now;
    
    // 处理手势检测...
}
```

### 8.4 防抖机制

```javascript
var lastGestureTime = {};
var gestureConfig = {
    index_up: { cooldown: 800 },    // 800ms 冷却时间
    swipe_right: { cooldown: 1200 } // 1200ms 冷却时间
};

function canTrigger(gestureType) {
    var now = Date.now();
    var cooldown = gestureConfig[gestureType].cooldown || 1000;
    return (now - (lastGestureTime[gestureType] || 0)) >= cooldown;
}

function markTriggered(gestureType) {
    lastGestureTime[gestureType] = Date.now();
}
```

---

## 九、设置管理

### 9.1 默认配置

```javascript
var defaultSettings = {
    enabled: true,
    sensitivity: 1.0,
    modelComplexity: 1,
    frameRate: 15,
    mirrorMode: true,
    showFeedback: true,
    tutorialCompleted: false,
    gestures: {
        index_up: { enabled: true, cooldown: 800 },
        index_down: { enabled: true, cooldown: 800 },
        fist: { enabled: true, cooldown: 1200 },
        swipe_left: { enabled: true, cooldown: 1200 },
        swipe_right: { enabled: true, cooldown: 1200 },
        swipe_up: { enabled: true, cooldown: 800 },
        swipe_down: { enabled: true, cooldown: 800 }
    }
};
```

### 9.2 配置持久化

```javascript
var STORAGE_KEY = 'gesture_settings';

function loadSettings() {
    var stored = localStorage.getItem(STORAGE_KEY);
    if (stored) {
        currentSettings = mergeSettings(defaultSettings, JSON.parse(stored));
    } else {
        currentSettings = JSON.parse(JSON.stringify(defaultSettings));
    }
    return currentSettings;
}

function saveSettings() {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(currentSettings));
}
```

---

## 十、新手引导实现

### 10.1 引导步骤

```javascript
var tutorialSteps = [
    {
        title: '欢迎使用手势交互',
        content: '通过摄像头识别您的手势，实现无接触控制',
        icon: '🖐️'
    },
    {
        title: '食指向上 ☝️',
        content: '竖起食指，保持 0.5 秒，选中下一条记录',
        icon: '☝️'
    },
    {
        title: '食指向下 👇',
        content: '食指向下竖起，保持 0.5 秒，选中上一条记录',
        icon: '👇'
    },
    {
        title: '握拳 ✊',
        content: '握拳保持 0.6 秒，暂停当前任务',
        icon: '✊'
    },
    {
        title: '左右滑动 👈👉',
        content: '手掌左右滑动，切换模块',
        icon: '👈'
    },
    {
        title: '开始使用',
        content: '点击"启动摄像头"按钮，开始手势交互',
        icon: '📷'
    }
];
```

---

## 十一、调试与测试

### 11.1 调试工具

提供手势识别模拟测试脚本 `gesture-test.js`：

```javascript
// 在浏览器控制台运行，模拟手部关键点数据
function testGesture(gestureName) {
    var landmarks = createTestLandmarks(gestureName);
    var result = window.GestureRuleEngine.detectGesture(landmarks);
    console.log('检测结果:', result);
}

// 使用示例
testGesture('index_up');   // 测试食指向上
testGesture('fist');       // 测试握拳
testGesture('swipe_right'); // 测试右滑
```

### 11.2 日志输出

各模块使用统一日志前缀：

```
[Gesture]           - 核心控制器日志
[GestureRuleEngine] - 规则引擎日志
[GestureEventBus]   - 事件总线日志
[GestureSettings]   - 设置管理日志
[GestureFeedback]   - 视觉反馈日志
```

### 11.3 常见问题排查

| 问题 | 可能原因 | 解决方案 |
|------|---------|---------|
| 摄像头无法启动 | 权限被拒绝 | 检查浏览器权限设置 |
| 手势不识别 | 置信度阈值过高 | 降低 `minDetectionConfidence` |
| 手势误触发 | 冷却时间太短 | 增加 `cooldown` 配置 |
| 页面切换后摄像头关闭 | 未正确释放资源 | 检查 `navigateModule` 实现 |
| 设置不生效 | LocalStorage 异常 | 清除浏览器缓存 |

---

## 十二、性能优化建议

### 12.1 帧率优化

| 模式 | FPS | 适用场景 |
|------|-----|---------|
| 省电模式 | 10 | 移动设备、电池供电 |
| 平衡模式 | 15 | 默认推荐 |
| 流畅模式 | 20 | 高性能设备 |
| 高性能 | 30 | 桌面端、外接电源 |

### 12.2 模型复杂度

| 复杂度 | 精度 | 速度 | 适用场景 |
|--------|------|------|---------|
| 0 (轻量) | 较低 | 快 | 低端设备 |
| 1 (标准) | 高 | 中等 | 默认推荐 |

### 12.3 内存管理

1. **及时释放摄像头资源**: 页面切换前必须停止摄像头
2. **轨迹缓冲区限制**: `trajectoryMaxLength = 20`，避免内存泄漏
3. **事件历史限制**: `maxHistoryLength = 100`，定期清理

---

## 十三、完整代码清单

### 13.1 需要创建的文件

| 文件 | 行数 | 说明 |
|------|------|------|
| `gesture.js` | ~600 | 核心控制器 |
| `gesture-rule-engine.js` | ~440 | 规则引擎 |
| `gesture-event-bus.js` | ~180 | 事件总线 |
| `gesture-feedback.js` | ~150 | 视觉反馈 |
| `gesture-settings.js` | ~200 | 设置管理 |
| `gesture_panel.html` | ~390 | UI 组件 |

### 13.2 外部依赖

```html
<!-- MediaPipe Hands -->
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js"></script>
<script src="https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils@0.3/drawing_utils.js"></script>

<!-- Font Awesome (图标) -->
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
```

---

## 十四、实现流程总结

### 14.1 开发顺序建议

```
Phase 1: 基础框架
  1. 创建 gesture_panel.html UI 组件
  2. 创建 gesture-settings.js 设置管理
  3. 创建 gesture.js 核心控制器（摄像头管理）

Phase 2: 手势识别
  4. 创建 gesture-rule-engine.js 规则引擎
  5. 实现食指向上/向下检测
  6. 实现握拳检测
  7. 实现左右滑动检测
  8. 实现上下滑动检测

Phase 3: 事件与反馈
  9. 创建 gesture-event-bus.js 事件总线
  10. 创建 gesture-feedback.js 视觉反馈
  11. 注册业务映射

Phase 4: 优化与完善
  12. 实现新手引导
  13. 实现跨模块保持
  14. 性能优化与调试
```

### 14.2 测试验证清单

- [ ] 摄像头可以正常启动和停止
- [ ] 手部关键点正常绘制
- [ ] 7 种手势均可正确识别
- [ ] 手势触发对应的业务操作
- [ ] 设置可以保存和加载
- [ ] 页面切换后摄像头自动恢复
- [ ] 面板可以折叠和展开
- [ ] 新手引导正常显示
- [ ] 性能指标符合预期（FPS、CPU 占用）

---

## 十五、附录

### 15.1 MediaPipe Hands 关键点坐标说明

- 坐标范围：0 ~ 1（归一化）
- 原点：左上角
- x 轴：从左到右
- y 轴：从上到下
- z 轴：深度（相对手腕）

### 15.2 手势配置参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `holdTime` | 保持时间（ms） | 400/600 |
| `cooldown` | 冷却时间（ms） | 800/1200 |
| `minDeltaX` | 最小水平位移 | 0.1 |
| `minDeltaY` | 最小垂直位移 | 0.1 |
| `maxTime` | 最大滑动时间（ms） | 1000 |
| `maxDeltaYRatio` | 最大垂直位移比例 | 0.6 |
| `tipWristDist` | 指尖到手腕最大距离 | 0.25 |

### 15.3 浏览器兼容性

| 浏览器 | 最低版本 | 说明 |
|--------|---------|------|
| Chrome | 80+ | 推荐，性能最佳 |
| Firefox | 90+ | 支持良好 |
| Edge | 80+ | 基于 Chromium |
| Safari | 14+ | 部分功能可能受限 |

---

> 本文档基于实际项目实现编写，可直接用于新项目的 gesture 交互功能开发。
> 如有问题，请参考调试与测试章节进行排查。
