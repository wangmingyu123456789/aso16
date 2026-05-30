/**
 * CToS 手势识别前端客户端 v2.0
 * 通过 WebSocket 连接 Python 手势引擎，接收手势事件并映射到系统操作
 * 集成语音播报（TTS）提供无障碍反馈
 *
 * v2.0 — 适配新的纯静态手势引擎（手指计数 0/1/2/3/5）
 */
(function () {
    'use strict';

    // ==================== TTS 语音引擎 ====================
    class TTSEngine {
        constructor() {
            this.enabled = false; // 默认关闭，由用户主动开启
            this.synth = window.speechSynthesis;
            this._speaking = false;
            this._queue = [];
            this._processing = false;
        }

        /** 播报文本 */
        speak(text, priority = 'normal') {
            if (!this.enabled || !this.synth) return;
            this._queue.push({ text, priority });
            this._processQueue();
        }

        /** 立即播报（中断当前播报） */
        speakImmediate(text) {
            if (!this.enabled || !this.synth) return;
            this._queue = [];
            if (this._speaking) {
                this.synth.cancel();
                this._speaking = false;
            }
            this._queue.push({ text, priority: 'high' });
            this._processQueue();
        }

        _processQueue() {
            if (this._processing || this._queue.length === 0) return;
            this._processing = true;

            const item = this._queue.shift();
            this._speaking = true;

            try {
                const utterance = new SpeechSynthesisUtterance(item.text);
                utterance.lang = 'zh-CN';
                utterance.rate = 1.0;
                utterance.pitch = 1.0;
                utterance.volume = 1.0;

                utterance.onend = () => {
                    this._speaking = false;
                    this._processing = false;
                    this._processQueue();
                };
                utterance.onerror = () => {
                    this._speaking = false;
                    this._processing = false;
                    this._processQueue();
                };

                this.synth.speak(utterance);
            } catch (e) {
                this._speaking = false;
                this._processing = false;
            }
        }

        /** 切换开关 */
        toggle() {
            this.enabled = !this.enabled;
            if (!this.enabled) {
                this.synth.cancel();
                this._queue = [];
                this._speaking = false;
                this._processing = false;
            }
            return this.enabled;
        }

        /** 设置状态 */
        setEnabled(state) {
            this.enabled = state;
            if (!this.enabled) {
                this.synth.cancel();
                this._queue = [];
                this._speaking = false;
                this._processing = false;
            }
        }
    }

    // ==================== 手势客户端 ====================
    class GestureClient {
        constructor() {
            this.ws = null;
            this.wsUrl = 'ws://127.0.0.1:8765';
            this.reconnectTimer = null;
            this.reconnectInterval = 5000;
            this.connected = false;
            this.tts = new TTSEngine();

            // 手势冷却（按手势类型分别跟踪，互不影响）
            this._lastGestureTimes = {};
            this._gestureCooldown = 800;

            // 模块导航列表
            this._modules = [
                'dashboard', 'watch', 'workers', 'dispatch',
                'cleaning', 'warehouse', 'sentiment', 'chat', 'im', 'admin'
            ];
            this._moduleNames = {
                dashboard: '数字大屏', watch: '智能瞭望', workers: '数字员工',
                dispatch: '派遣执行', cleaning: '数据清洗', warehouse: '知识仓库',
                sentiment: '智慧舆情', chat: '智能问数', im: '智能聊天', admin: '系统管理'
            };
            this._lastSwipeTime = 0;
            this._swipeCooldown = 1500;

            this._autoWorkflowRunning = false;
        }

        /** 连接手势服务 */
        connect() {
            if (this.ws && (this.ws.readyState === WebSocket.OPEN || this.ws.readyState === WebSocket.CONNECTING)) {
                return;
            }

            try {
                this.ws = new WebSocket(this.wsUrl);
            } catch (e) {
                console.warn('[Gesture] WebSocket 创建失败:', e.message);
                this._scheduleReconnect();
                return;
            }

            this.ws.onopen = () => {
                this.connected = true;
                console.log('[Gesture] ✅ 已连接到手势识别服务');
                if (this.tts.enabled) {
                    this.tts.speak('手势识别已连接');
                }
                if (this.onconnect) this.onconnect();
            };

            this.ws.onclose = () => {
                this.connected = false;
                console.log('[Gesture] 手势服务已断开');
                this._scheduleReconnect();
                if (this.ondisconnect) this.ondisconnect();
            };

            this.ws.onerror = () => {
                console.warn('[Gesture] WebSocket 错误');
            };

            this.ws.onmessage = (event) => {
                try {
                    const data = JSON.parse(event.data);
                    if (data.type === 'gesture' && data.gesture) {
                        this._handleGesture(data.gesture, data.confidence || 0);
                    }
                } catch (e) {
                    console.warn('[Gesture] 解析消息失败:', e.message);
                }
            };
        }

        /** 断开连接 */
        disconnect() {
            this._clearReconnect();
            if (this.ws) {
                this.ws.close();
                this.ws = null;
            }
            this.connected = false;
        }

        _scheduleReconnect() {
            if (this.reconnectTimer) return;
            this.reconnectTimer = setTimeout(() => {
                this.reconnectTimer = null;
                if (!this.connected) {
                    console.log('[Gesture] 尝试重新连接...');
                    this.connect();
                }
            }, this.reconnectInterval);
        }

        _clearReconnect() {
            if (this.reconnectTimer) {
                clearTimeout(this.reconnectTimer);
                this.reconnectTimer = null;
            }
        }

        /** 处理手势事件（v3.0 适配 MediaPipe GestureRecognizer 内置分类器） */
        _handleGesture(gesture, confidence) {
            const now = Date.now();

            // 每种手势单独冷却，互不影响
            const lastTime = this._lastGestureTimes[gesture] || 0;
            if (now - lastTime < this._gestureCooldown) {
                console.log(`[Gesture] ${gesture} 冷却中，跳过 (距上次 ${(now - lastTime).toFixed(0)}ms)`);
                return;
            }
            this._lastGestureTimes[gesture] = now;

            console.log(`[Gesture] ✅ 触发: ${gesture} (${(confidence * 100).toFixed(0)}%)`);

            // 映射 v3.0 MediaPipe GestureRecognizer 新手势名称到功能
            switch (gesture) {
                case 'prev_menu':    // PointingUp -> 上一个模块
                    this._handleSwipeLeft();
                    break;
                case 'next_menu':    // ThumbDown -> 下一个模块
                    this._handleSwipeRight();
                    break;
                case 'voice_toggle': // OpenPalm -> 切换语音播报
                    this._handleFiveOpen();
                    break;
                case 'summary':      // Victory -> 页面摘要播报
                    this._handlePeace();
                    break;
                case 'quick_menu':   // ClosedFist -> 快捷菜单
                    this._handleFist();
                    break;
                default:
                    break;
            }
        }

        _getCurrentModuleIndex() {
            const current = App?.currentModule || 'dashboard';
            return this._modules.indexOf(current);
        }

        _switchToModule(index) {
            if (index < 0) index = this._modules.length - 1;
            if (index >= this._modules.length) index = 0;
            const module = this._modules[index];
            const name = this._moduleNames[module] || module;

            if (App && App.switchModule) {
                App.switchModule(module);
            }

            if (this.tts.enabled) {
                this.tts.speakImmediate(`已切换到${name}`);
            }

            if (API && API.toast) {
                API.toast('info', `-> ${name}`, `手势切换到 ${name} 模块`);
            }
        }

        // ========== 手势映射 ==========

        _handleSwipeLeft() {
            const now = Date.now();
            if (now - this._lastSwipeTime < this._swipeCooldown) return;
            this._lastSwipeTime = now;

            const idx = this._getCurrentModuleIndex();
            this._switchToModule(idx - 1);
        }

        _handleSwipeRight() {
            const now = Date.now();
            if (now - this._lastSwipeTime < this._swipeCooldown) return;
            this._lastSwipeTime = now;

            const idx = this._getCurrentModuleIndex();
            this._switchToModule(idx + 1);
        }

        /** 五指张开(5根) -> 切换语音播报 */
        _handleFiveOpen() {
            const enabled = this.tts.toggle();
            this._updateTTSButton(enabled);
            if (enabled) {
                if (API && API.toast) API.toast('success', '语音播报已开启', '手势操作将播报反馈');
                this.tts.speakImmediate('语音播报已开启');
            } else {
                if (API && API.toast) API.toast('info', '语音播报已关闭', '手势操作仍可使用');
            }
        }

        /** V字(2根) -> 播报当前页面摘要 */
        _handlePeace() {
            const module = App?.currentModule || 'dashboard';
            const summary = this._generateSummary(module);

            if (this.tts.enabled) {
                this.tts.speakImmediate(summary);
            }

            if (API && API.toast) {
                API.toast('info', '页面摘要', summary);
            }
        }

        /** 握拳(0根) -> 快捷菜单 */
        _handleFist() {
            this._handlePinch();
        }

    /** 同步更新TTS按钮UI */
        _updateTTSButton(enabled) {
            const btn = document.getElementById('ttsToggle');
            if (btn) {
                btn.innerHTML = enabled ? '🔊 语音' : '🔇 语音';
                btn.title = enabled ? '点击关闭语音播报' : '点击开启语音播报';
                if (enabled) {
                    btn.classList.add('active-tts');
                } else {
                    btn.classList.remove('active-tts');
                }
            }
        }

        /** 快捷菜单（握拳触发） */
        _handlePinch() {
            const module = App?.currentModule || 'dashboard';
            const actions = {
                dashboard: [
                    { label: '刷新大屏', action: () => App?.loadAllModuleData?.('dashboard') },
                    { label: '舆情分析', action: () => App?.triggerSentimentAnalysis?.() },
                ],
                watch: [
                    { label: '刷新瞭望', action: () => App?.loadAllModuleData?.('watch') },
                    { label: '新建瞭望源', action: () => App?.showWatchSourceForm?.() },
                ],
                cleaning: [
                    { label: '启动清洗', action: () => App?.showCleaningForm?.() },
                    { label: '清洗统计', action: () => App?.showCleaningStats?.() },
                ],
                sentiment: [
                    { label: '触发分析', action: () => App?.triggerSentimentAnalysis?.() },
                    { label: '词云', action: () => App?.openWordcloudModal?.() },
                    { label: '3D地球', action: () => App?.openGlobeModal?.() },
                ],
                chat: [
                    { label: '新建对话', action: () => App?.showCreateConversationForm?.() },
                    { label: '刷新', action: () => App?.loadChatConversations?.() },
                ],
                im: [
                    { label: '添加好友', action: () => App?.showAddFriendForm?.() },
                    { label: '创建群组', action: () => App?.showCreateGroupForm?.() },
                ],
                admin: [
                    { label: '新建用户', action: () => App?.showCreateUserForm?.() },
                    { label: '新建API Key', action: () => App?.showCreateApiKeyForm?.() },
                ],
                workers: [
                    { label: '新建员工', action: () => App?.showWorkerForm?.() },
                    { label: '刷新', action: () => App?.loadAllModuleData?.('workers') },
                ],
                dispatch: [
                    { label: '派遣员工', action: () => App?.showDispatchForm?.() },
                    { label: '刷新', action: () => App?.loadAllModuleData?.('dispatch') },
                ],
                warehouse: [
                    { label: '新建文章', action: () => App?.showArticleForm?.() },
                    { label: '刷新', action: () => App?.loadAllModuleData?.('warehouse') },
                ],
            };

            const moduleActions = actions[module] || [
                { label: '刷新', action: () => App?.loadAllModuleData?.(module) },
            ];

            const menuHtml = moduleActions.map((a, i) =>
                `<button class="btn btn-sm btn-ghost" style="display:block;width:100%;text-align:left;margin:2px 0" onclick="GestureClient.instance._executeQuickAction(${i})" data-action-index="${i}">
                    ${a.label}
                </button>`
            ).join('');

            const moduleName = this._moduleNames[module] || module;
            if (API && API.showModal) {
                API.showModal(`快捷操作 - ${moduleName}`, menuHtml, `<button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`);
            }

            this._quickActions = moduleActions;

            if (this.tts.enabled) {
                this.tts.speak(`已打开${moduleName}快捷菜单，共${moduleActions.length}个操作`);
            }
        }

        _executeQuickAction(index) {
            const action = this._quickActions?.[index];
            if (action) {
                if (API && API.closeModal) API.closeModal();
                action.action();
                if (this.tts.enabled) {
                    this.tts.speak(`执行${action.label}`);
                }
            }
        }

        /** 生成页面摘要 */
        _generateSummary(module) {
            const name = this._moduleNames[module] || module;
            let summary = `当前在${name}`;

            switch (module) {
                case 'dashboard': {
                    const statsEl = document.getElementById('dashboard-stats');
                    const match = statsEl?.textContent?.trim().match(/(\d+)/g);
                    if (match) summary += `，检测到 ${match.length} 个数据指标`;
                    break;
                }
                case 'im': {
                    const convCount = document.querySelectorAll('#im-conversation-list .im-list-item').length;
                    const friendsCount = document.querySelectorAll('#im-friends-list .im-list-item').length;
                    summary += `，${convCount}个会话，${friendsCount}个好友`;
                    break;
                }
                case 'cleaning': {
                    const count = document.querySelectorAll('#cleaning-uncleaned .cleaning-data-card').length;
                    summary += `，${count}条待清洗数据`;
                    break;
                }
                case 'sentiment': {
                    const count = document.querySelectorAll('#sentiment-analyses .sentiment-analysis-item').length;
                    summary += `，${count}条分析记录`;
                    break;
                }
                case 'warehouse': {
                    const count = document.querySelectorAll('#warehouse-articles tbody tr').length;
                    summary += `，${count}篇文章`;
                    break;
                }
                default:
                    summary += '，可使用1根/3根手指切换模块';
                    break;
            }
            return summary;
        }
    }

    // ==================== 暴露给全局 ====================

    const instance = new GestureClient();
    GestureClient.instance = instance;

    window.GestureClient = GestureClient;
    window.__gestureClient = instance;
    window.__ttsEngine = instance.tts;

    /** 切换TTS + 同步更新按钮UI */
    window.toggleTTS = function () {
        const enabled = instance.tts.toggle();
        const btn = document.getElementById('ttsToggle');
        if (btn) {
            btn.innerHTML = enabled ? '🔊 语音' : '🔇 语音';
            btn.title = enabled ? '点击关闭语音播报' : '点击开启语音播报';
            if (enabled) {
                btn.classList.add('active-tts');
                // 点击开启后播报一声，验证声音正常 + 满足浏览器用户手势要求
                instance.tts.speakImmediate('语音播报已开启');
            } else {
                btn.classList.remove('active-tts');
            }
        }
        return enabled;
    };

    console.log('[Gesture] 手势客户端 v2.0 已加载');
    console.log('[Gesture] 手势服务地址:', instance.wsUrl);
    console.log('[Gesture] 使用 toggleTTS() 或在页头点击"语音"按钮');
    console.log('[Gesture] 支持手势: 0根=菜单 1根=上一个 2根=播报 3根=下一个 5根=语音');

})();