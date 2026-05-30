/**
 * CToS 管理后台应用逻辑 v3.2
 * 可视区域自动加载模式 - 数据区域进入视口时自动加载，无需手动操作
 */
document.addEventListener('DOMContentLoaded', function () {
    initApp();
});

function initApp() {
    const savedToken = localStorage.getItem('ctos_token');
    const savedTheme = localStorage.getItem('ctos_theme') || 'light';

    if (savedTheme === 'dark') {
        document.documentElement.setAttribute('data-theme', 'dark');
    }

    if (savedToken) {
        API.token = savedToken;
        API.getCurrentUser().then(user => {
            if (user) {
                showMainPage(user);
            } else {
                clearAuth();
                showLoginPage();
            }
        });
    }

    // 登录/注册 Tab 切换
    document.querySelectorAll('.login-tab-btn').forEach(btn => {
        btn.addEventListener('click', function () {
            const tab = this.dataset.tab;
            document.querySelectorAll('.login-tab-btn').forEach(b => b.classList.remove('active'));
            this.classList.add('active');
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById(tab).classList.add('active');
            clearFormErrors();
        });
    });

    // 登录
    const loginBtn = document.getElementById('loginBtn');
    const loginPassword = document.getElementById('loginPassword');
    const loginUsername = document.getElementById('loginUsername');

    if (loginBtn) loginBtn.addEventListener('click', handleLogin);
    if (loginPassword) loginPassword.addEventListener('keydown', e => { if (e.key === 'Enter' && loginBtn) loginBtn.click(); });
    if (loginUsername) loginUsername.addEventListener('keydown', e => { if (e.key === 'Enter' && loginPassword) loginPassword.focus(); });

    // 注册
    document.getElementById('registerBtn')?.addEventListener('click', handleRegister);

    // 健康检查
    document.getElementById('healthBtn')?.addEventListener('click', handleHealthCheck);

    // 证书信任（HTTPS/WSS）
    document.getElementById('trustCertBtn')?.addEventListener('click', handleTrustCert);

    // 侧边栏导航
    document.querySelectorAll('.sidebar-nav li').forEach(item => {
        item.addEventListener('click', function () {
            const module = this.dataset.module;
            App.switchModule(module);
            closeSidebar();
        });
    });

    // 退出登录
    document.getElementById('logoutBtn')?.addEventListener('click', function () {
        clearAuth();
        showLoginPage();
        API.toast('info', '已退出', '您已成功退出登录');
    });

    // 主题切换
    document.getElementById('themeToggle')?.addEventListener('click', function () {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        document.documentElement.setAttribute('data-theme', newTheme);
        localStorage.setItem('ctos_theme', newTheme);
        this.textContent = newTheme === 'dark' ? '☀️' : '🌙';
        API.toast('info', newTheme === 'dark' ? '🌙 暗色主题' : '☀️ 亮色主题', '已切换');
    });

    // 密码可见切换
    document.querySelectorAll('.password-toggle').forEach(btn => {
        btn.addEventListener('click', function () {
            const input = this.closest('.password-wrapper').querySelector('input');
            if (input) {
                input.type = input.type === 'password' ? 'text' : 'password';
                this.textContent = input.type === 'password' ? '👁️' : '👁️‍🗨️';
            }
        });
    });

    // 移动端菜单
    document.getElementById('mobileMenuBtn')?.addEventListener('click', function () {
        document.querySelector('.sidebar')?.classList.toggle('open');
        document.querySelector('.sidebar-overlay')?.classList.toggle('active');
    });
    document.querySelector('.sidebar-overlay')?.addEventListener('click', closeSidebar);

    // IM 输入框 - @提及键盘导航
    const imInput = document.getElementById('im-input');
    if (imInput) {
        imInput.addEventListener('keydown', function (e) {
            const handled = App._onIMAtMenuKeydown(this, e);
            if (handled === false) {
                e.preventDefault();
                e.stopPropagation();
                return;
            }
            // 如果@菜单没打开且按了Enter，发送消息
            if (e.key === 'Enter' && !e.shiftKey && !App._im.atMenuActive) {
                e.preventDefault();
                App.sendIMMessage();
            }
        });
    }

    // @提及弹出菜单点击选择事件委托
    document.getElementById('im-at-menu-list')?.addEventListener('click', function (e) {
        const item = e.target.closest('.im-at-item');
        if (!item) return;
        const idx = parseInt(item.dataset.index);
        const filtered = App._im.atMenuFiltered || [];
        if (!isNaN(idx) && filtered[idx]) {
            App._selectAtMember(filtered[idx]);
        }
    });

    // 聊天输入框 - 自动调整高度
    const chatInput = document.getElementById('chat-input');
    if (chatInput) {
        chatInput.addEventListener('input', function () {
            this.style.height = 'auto';
            this.style.height = Math.min(this.scrollHeight, 120) + 'px';
        });
        chatInput.addEventListener('keydown', function (e) {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                App.sendChatMessage();
            }
        });
    }

    // 聊天发送按钮
    const chatSendBtn = document.getElementById('chatSendBtn');
    if (chatSendBtn) {
        chatSendBtn.addEventListener('click', function () {
            App.sendChatMessage();
        });
    }

    // 聊天停止按钮
    const chatStopBtn = document.getElementById('chatStopBtn');
    if (chatStopBtn) {
        chatStopBtn.addEventListener('click', function () {
            App.stopChatMessage();
        });
    }

    // 点击模态框外部关闭
    document.addEventListener('click', function (e) {
        if (e.target.classList.contains('modal-overlay')) {
            API.closeEditModal();
            API.closeModal();
        }
    });

    // ===== TTS 兜底保护 =====
    // 确保无论 gesture_client.js 是否加载成功，语音按钮都能工作
    if (typeof window.toggleTTS !== 'function') {
        window._ttsEnabled = false;
        window.toggleTTS = function () {
            window._ttsEnabled = !window._ttsEnabled;
            const btn = document.getElementById('ttsToggle');
            if (btn) {
                btn.innerHTML = window._ttsEnabled ? '🔊 语音' : '🔇 语音';
                btn.title = window._ttsEnabled ? '点击关闭语音播报' : '点击开启语音播报';
                if (window._ttsEnabled) {
                    btn.classList.add('active-tts');
                } else {
                    btn.classList.remove('active-tts');
                }
            }
            // 如果有真正的 TTS 引擎，委派给它
            if (window.__ttsEngine && window.__ttsEngine.toggle) {
                window.__ttsEngine.setEnabled(window._ttsEnabled);
            }
            return window._ttsEnabled;
        };
    }
}

// ========== 全局 App 对象 ==========
const App = {
    currentModule: 'dashboard',

    /** IntersectionObserver 实例，用于可视区域自动加载 */
    _lazyObserver: null,

    /** 已加载过的容器集合，防止重复加载 */
    _loadedContainers: new Set(),

    /** 切换模块并自动加载数据 */
    async switchModule(module) {
        // 离开旧模块时的清理工作
        if (this.currentModule === 'cleaning' && module !== 'cleaning') {
            this._stopCleaningPolling();
        }
        if (this.currentModule === 'im' && module !== 'im') {
            this._stopIMMessagePolling();
        }
        if (this.currentModule === 'chat' && module !== 'chat') {
            this._stopChatPolling();
        }

        this.currentModule = module;

        // 更新侧边栏
        document.querySelectorAll('.sidebar-nav li').forEach(li => li.classList.remove('active'));
        const targetLi = document.querySelector(`.sidebar-nav li[data-module="${module}"]`);
        if (targetLi) targetLi.classList.add('active');

        // 切换模块内容
        document.querySelectorAll('.module-content').forEach(el => el.classList.remove('active'));
        const targetEl = document.getElementById(`module-${module}`);
        if (targetEl) targetEl.classList.add('active');

        // 设置可视区域自动加载
        this.setupLazyAutoLoad(module);

        // 进入智能聊天模块时，立即加载数据并启动3秒轮询
        if (module === 'im') {
            this.loadIMConversations();
            this._startIMMessagePolling();
        }
    },

    /** 可视区域自动加载数据：数据容器滚动到视口时自动触发加载 */
    setupLazyAutoLoad(module) {
        // 各模块的数据区域配置
        const lazyConfigs = {
            dashboard: [
                { id: 'dashboard-stats', loader: () => API.loadData('dashboard', '/api/dashboard/stats', { container: document.getElementById('dashboard-stats'), renderer: 'stats' }) },
                { id: 'dashboard-collect-trend', loader: () => API.loadData('dashboard', '/api/dashboard/collect-trend?days=7', { container: document.getElementById('dashboard-collect-trend') }) },
                { id: 'dashboard-token-trend', loader: () => API.loadData('dashboard', '/api/dashboard/token-trend?days=7', { container: document.getElementById('dashboard-token-trend') }) },
                { id: 'dashboard-sentiment-stats', loader: () => API.loadData('dashboard', '/api/dashboard/sentiment-stats', { container: document.getElementById('dashboard-sentiment-stats'), renderer: 'stats' }) },
                { id: 'dashboard-wordcloud', loader: () => API.loadData('dashboard', '/api/dashboard/wordcloud', { container: document.getElementById('dashboard-wordcloud') }) },
            ],
            watch: [
                { id: 'watch-sources', loader: () => API.loadData('watch', '/api/watch/sources', { container: document.getElementById('watch-sources'), selectable: true }) },
            ],
            workers: [
                { id: 'workers-jobs', loader: () => API.loadData('workers', '/api/workers/jobs', { container: document.getElementById('workers-jobs') }) },
                { id: 'workers-list', loader: () => API.loadData('workers', '/api/workers', { container: document.getElementById('workers-list') }) },
            ],
            dispatch: [
                { id: 'dispatch-logs', loader: () => API.loadData('dispatch', '/api/dispatch/logs', { container: document.getElementById('dispatch-logs') }) },
            ],
            cleaning: [
                { id: 'cleaning-uncleaned', loader: () => this.loadUncleanedData() },
                { id: 'cleaning-cleaned', loader: () => this.loadCleanedArticles() },
                { id: 'cleaning-logs', loader: () => API.loadData('cleaning', '/api/cleaning/logs', { container: document.getElementById('cleaning-logs') }) },
            ],
            warehouse: [
                { id: 'warehouse-articles', loader: () => this.loadWarehouseArticles() },
                { id: 'warehouse-categories', loader: () => this.loadWarehouseCategories() },
                { id: 'warehouse-stats', loader: () => this.loadWarehouseStats() },
                { id: 'warehouse-domains', loader: () => this.loadWarehouseDomains() },
            ],
            sentiment: [
                { id: 'sentiment-analyses', loader: () => this.loadSentimentAnalyses() },
            ],
            workflow: [
                { id: 'workflow-stats', loader: () => this.loadWorkflowStats() },
                { id: 'workflow-tasks', loader: () => this.loadWorkflowTasks() },
            ],
            chat: [
                { id: 'chat-conv-list', loader: () => this.loadChatConversations() },
            ],
            im: [
                { id: 'im-conversation-list', loader: () => this.loadIMConversations() },
                { id: 'im-friends-list', loader: () => this.loadIMFriends() },
                { id: 'im-groups-list', loader: () => this.loadIMGroups() },
                { id: 'im-received-requests', loader: () => this.loadIMReceivedRequests() },
                { id: 'im-sent-requests', loader: () => this.loadIMSentRequests() },
            ],
            files: [
                { id: 'files-stats', loader: () => App.loadFilesStats() },
                { id: 'files-list', loader: () => App.loadFileList() },
            ],
            admin: [
                { id: 'admin-users', loader: () => API.loadData('admin', '/api/admin/users', { container: document.getElementById('admin-users') }) },
                { id: 'admin-apikeys', loader: () => API.loadData('admin', '/api/admin/api-keys', { container: document.getElementById('admin-apikeys') }) },
                { id: 'admin-configs', loader: () => API.loadData('admin', '/api/admin/configs', { container: document.getElementById('admin-configs') }) },
                { id: 'admin-logs', loader: () => API.loadData('admin', '/api/admin/logs', { container: document.getElementById('admin-logs') }) },
                { id: 'admin-token-daily', loader: () => API.loadData('admin', '/api/admin/token-stats/daily', { container: document.getElementById('admin-token-daily') }) },
                { id: 'admin-token-users', loader: () => API.loadData('admin', '/api/admin/token-stats/users', { container: document.getElementById('admin-token-users') }) },
                { id: 'admin-groups', loader: () => App.loadAdminGroups() },
                { id: 'admin-database-status', loader: () => App.loadDatabaseStatus() },
            ],
        };

        const configs = lazyConfigs[module];
        if (!configs) return;

        // 销毁旧的 Observer
        if (this._lazyObserver) {
            this._lazyObserver.disconnect();
        }

        // 创建 IntersectionObserver：容器进入视口时自动加载
        this._lazyObserver = new IntersectionObserver((entries) => {
            entries.forEach(entry => {
                if (entry.isIntersecting) {
                    const el = entry.target;
                    // 只在视口可见、从未加载过、不包含内容的容器上触发
                    if (!this._loadedContainers.has(el.id) &&
                        !(el.children.length > 0 && !el.querySelector('.loading-spinner'))) {
                        
                        this._loadedContainers.add(el.id);
                        // 显示加载动画
                        el.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';
                        
                        // 找到对应的 loader 并执行
                        const cfg = configs.find(c => c.id === el.id);
                        if (cfg) {
                            cfg.loader().catch(err => {
                                el.innerHTML = `<div class="error-state">❌ 加载失败: ${API._escapeHtml(err.message)}</div>`;
                            });
                        }
                    }
                }
            });
        }, {
            rootMargin: '100px', // 提前100px加载，用户滚动到附近就触发
            threshold: 0.01      // 只要有1%进入视口就触发
        });

        // 观察每个数据容器
        configs.forEach(cfg => {
            const el = document.getElementById(cfg.id);
            if (!el) return;
            // 如果容器已经有数据（_data属性存在或已有非loading-spinner的内容），跳过
            // 注意：有些容器初始HTML中有loading-spinner占位，不能因此跳过观察
            if (el._data) return;
            if (el.children.length > 0 && !el.querySelector('.loading-spinner')) return;
            // 显示轻量加载提示
            el.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';
            this._lazyObserver.observe(el);
        });
    },

    /** 加载模块数据（兼容旧调用，立即加载全部） */
    async loadModuleData(module) {
        this.loadAllModuleData(module);
    },

    /** 一次性加载模块下所有数据（供"全部加载"/"刷新"按钮使用） */
    async loadAllModuleData(module) {
        const loaders = {
            dashboard: () => this.loadDashboard(),
            watch: () => this.loadWatch(),
            workers: () => this.loadWorkers(),
            dispatch: () => this.loadDispatch(),
            cleaning: () => this.loadCleaning(),
            warehouse: () => this.loadWarehouse(),
            sentiment: () => this.loadSentiment(),
            workflow: () => this.loadWorkflow(),
            chat: () => this.loadChat(),
            im: () => this.loadIM(),
            files: () => this.loadFiles(),
            admin: () => this.loadAdmin(),
        };

        if (loaders[module]) {
            // 清除已加载标记，让所有容器重新加载
            this._loadedContainers.clear();
            document.querySelectorAll(`#module-${module} .data-container`).forEach(el => {
                el.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';
            });
            // 断开自动观察，避免冲突
            if (this._lazyObserver) this._lazyObserver.disconnect();
            await loaders[module]();
            // 重新建立自动观察（对于还没显示的模块外容器）
            this.setupLazyAutoLoad(module);
        }
    },

    // ========== 数据清洗轮询机制 ==========
    _cleaningPollTimer: null,
    _cleaningKnownStatuses: {},

    _startCleaningPolling() {
        if (this._cleaningPollTimer) return;
        this._cleaningPollTimer = setInterval(() => {
            this._checkCleaningStatus();
        }, 5000);
        this._checkCleaningStatus();
    },

    _stopCleaningPolling() {
        if (this._cleaningPollTimer) {
            clearInterval(this._cleaningPollTimer);
            this._cleaningPollTimer = null;
        }
    },

    async _checkCleaningStatus() {
        if (this.currentModule !== 'cleaning') return;
        try {
            const res = await API.request('GET', '/api/cleaning/logs?page=1&page_size=50');
            const data = res.data || {};
            const logs = data.items || [];
            if (!Array.isArray(logs) || logs.length === 0) return;
            let hasChange = false;
            const newStatuses = {};
            logs.forEach(log => {
                const id = log.id;
                const status = log.status;
                newStatuses[id] = status;
                const prevStatus = this._cleaningKnownStatuses[id];
                if (prevStatus && prevStatus !== status) {
                    if (prevStatus === 'processing' && (status === 'success' || status === 'failed')) {
                        hasChange = true;
                        if (status === 'success') {
                            API.toast('success', '🧹 清洗完成', `清洗任务 #${id} 已完成！数据已入库`);
                        } else {
                            API.toast('error', '🧹 清洗失败', `清洗任务 #${id} 执行失败，请查看详情`);
                        }
                    }
                }
            });
            this._cleaningKnownStatuses = newStatuses;
            if (hasChange) {
                this.loadUncleanedData();
                this.loadCleanedArticles();
                API.loadData('cleaning', '/api/cleaning/logs', { container: document.getElementById('cleaning-logs') });
            }
        } catch {}
    },

    // ========== Chat 轮询 ==========
    _chatPollTimer: null,

    _startChatPolling() {
        if (this._chatPollTimer) return;
        this._chatPollTimer = setInterval(() => {
            if (this.currentModule === 'chat' && this._chat.currentConvId) {
                this.loadChatConversations();
            }
        }, 10000);
    },

    _stopChatPolling() {
        if (this._chatPollTimer) {
            clearInterval(this._chatPollTimer);
            this._chatPollTimer = null;
        }
    },

    // ========== 各模块数据加载 ==========

    async loadDashboard() {
        API.loadData('dashboard', '/api/dashboard/stats', { container: document.getElementById('dashboard-stats'), renderer: 'stats' });
        API.loadData('dashboard', '/api/dashboard/collect-trend?days=7', { container: document.getElementById('dashboard-collect-trend') });
        API.loadData('dashboard', '/api/dashboard/token-trend?days=7', { container: document.getElementById('dashboard-token-trend') });
        API.loadData('dashboard', '/api/dashboard/sentiment-stats', { container: document.getElementById('dashboard-sentiment-stats'), renderer: 'stats' });
        API.loadData('dashboard', '/api/dashboard/wordcloud', { container: document.getElementById('dashboard-wordcloud') });
    },

    /** 当前选中的瞭望源 ID */
    _selectedWatchSourceId: null,

    async loadWatch() {
        API.loadData('watch', '/api/watch/sources', { container: document.getElementById('watch-sources'), selectable: true });
        const welcomeEl = document.getElementById('watch-data-welcome');
        const dataContainer = document.getElementById('watch-data');
        if (welcomeEl) welcomeEl.style.display = 'flex';
        if (dataContainer) dataContainer.style.display = 'none';
    },

    async loadWatchData() {
        const sourceId = this._selectedWatchSourceId;
        if (!sourceId) { API.toast('warning', '提示', '请选择一个瞭望源'); return; }
        const welcomeEl = document.getElementById('watch-data-welcome');
        const dataContainer = document.getElementById('watch-data');
        if (welcomeEl) welcomeEl.style.display = 'none';
        if (dataContainer) {
            dataContainer.style.display = 'block';
        }
        API.loadData('watch', `/api/watch/sources/${sourceId}/data`, { container: dataContainer });
    },

    /** 选择瞭望源，加载其采集数据 */
    selectWatchSource(sourceId) {
        this._selectedWatchSourceId = sourceId;
        document.querySelectorAll('#watch-sources .data-table tbody tr').forEach(row => {
            row.classList.remove('active');
        });
        const row = document.querySelector(`#watch-sources .data-table tbody tr[data-source-id="${sourceId}"]`);
        if (row) row.classList.add('active');
        this.loadWatchData();
    },

    /** 手动触发瞭望源采集 */
    async triggerCollect(sourceId) {
        try {
            const res = await API.request('POST', `/api/watch/sources/${sourceId}/trigger`);
            const data = res.data || {};
            if (data.status === 'success') {
                API.toast('success', '采集完成', `采集数据 #${data.id}，HTTP ${data.http_status}`);
            } else {
                API.toast('warning', '采集异常', `HTTP ${data.http_status}，${data.raw_response || ''}`);
            }
            this.loadWatch();
            if (this._selectedWatchSourceId === sourceId) {
                this.loadWatchData();
            }
        } catch (err) {
            API.toast('error', '采集失败', err.message);
        }
    },

    async loadWorkers() {
        API.loadData('workers', '/api/workers/jobs', { container: document.getElementById('workers-jobs') });
        API.loadData('workers', '/api/workers', { container: document.getElementById('workers-list') });
    },

    async loadDispatch() {
        API.loadData('dispatch', '/api/dispatch/logs', { container: document.getElementById('dispatch-logs') });
    },

    async loadCleaning() {
        this._loadCleaningSources();
        this.loadUncleanedData();
        this.loadCleanedArticles();
        API.loadData('cleaning', '/api/cleaning/logs', { container: document.getElementById('cleaning-logs') });
        this._startCleaningPolling();
    },

    /** 加载瞭望源列表到下拉菜单 */
    async _loadCleaningSources() {
        try {
            const res = await API.request('GET', '/api/watch/sources');
            const sources = res.data || [];
            const select = document.getElementById('clean-source-select');
            if (!select) return;
            select.innerHTML = '<option value="">-- 所有瞭望源 --</option>';
            sources.forEach(s => {
                select.innerHTML += `<option value="${s.id}">${s.name}</option>`;
            });
        } catch {}
    },

    /** 加载待清洗数据（瞭望数据中尚未清洗的，通过后端过滤已清洗记录） */
    async loadUncleanedData() {
        const container = document.getElementById('cleaning-uncleaned');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';

        const sourceId = document.getElementById('clean-source-select')?.value;

        try {
            // 使用新端点 /api/cleaning/uncleaned，后端自动过滤已清洗的记录
            const params = { page: 1, page_size: 50 };
            if (sourceId) params.source_id = sourceId;
            const qs = new URLSearchParams(params).toString();
            const res = await API.request('GET', `/api/cleaning/uncleaned?${qs}`);
            const data = res.data || {};
            const items = data.items || data || [];

            if (!Array.isArray(items) || items.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">暂无待清洗的采集数据</div></div>';
                return;
            }

            // 获取瞭望源名称映射
            let sourceNameMap = {};
            try {
                const srcRes = await API.request('GET', '/api/watch/sources');
                const sources = srcRes.data || [];
                sources.forEach(s => { sourceNameMap[s.id] = s.name; });
            } catch {}

            items.sort((a, b) => new Date(b.collected_at || 0) - new Date(a.collected_at || 0));

            let html = '<div class="cleaning-data-list">';
            items.forEach(d => {
                const rawPreview = (d.raw_response || d.parsed_data || '')?.slice(0, 120) || '无内容';
                const time = App._formatTime(d.collected_at);
                const sourceName = sourceNameMap[d.source_id] || '未知源';
                html += `
                    <div class="cleaning-data-card" data-id="${d.id}" onclick="App.selectUncleanedData(${d.id})" ondblclick="App.quickCleanData(${d.id})">
                        <div class="cleaning-data-card-header">
                            <span class="cleaning-data-source">📡 ${API._escapeHtml(sourceName)}</span>
                            <span class="cleaning-data-time">${time}</span>
                        </div>
                        <div class="cleaning-data-preview">${API._escapeHtml(rawPreview)}</div>
                        <div class="cleaning-data-actions">
                            <button class="btn btn-xs btn-primary" onclick="event.stopPropagation();API.viewWatchDataDetail(${d.id})" title="查看原始数据">👁️ 查看</button>
                            <button class="btn btn-xs btn-success" onclick="event.stopPropagation();App.quickCleanData(${d.id})" title="清洗此数据">🧹 清洗</button>
                        </div>
                    </div>`;
            });
            html += '</div>';
            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 选中一条待清洗数据 */
    _selectedUncleanedDataId: null,
    selectUncleanedData(dataId) {
        this._selectedUncleanedDataId = dataId;
        document.querySelectorAll('.cleaning-data-card').forEach(el => el.classList.remove('selected'));
        const card = document.querySelector(`.cleaning-data-card[data-id="${dataId}"]`);
        if (card) card.classList.add('selected');
    },

    /** 快速清洗单条数据 */
    async quickCleanData(dataId) {
        const workers = await this._fetchWorkersForDropdown();
        const workerOptions = workers.length > 0
            ? workers.map(w => `<option value="${w.id}">${w.icon || '🤖'} ${w.name}</option>`).join('')
            : '<option value="">-- 暂无可用的数字员工 --</option>';

        API.showModal(`🧹 清洗数据 #${dataId}`, `
            <div class="modal-form-group">
                <span class="modal-form-label">瞭望数据 ID</span>
                <input class="modal-form-input" id="clean-data-ids" value="${dataId}" readonly />
            </div>
            <div class="modal-form-group">
                <span class="modal-form-label">清洗方法</span>
                <select class="modal-form-select" id="clean-method" onchange="App._onCleanMethodChange()">
                    <option value="ai">🤖 AI 清洗（推荐）</option>
                    <option value="regex">🔧 正则清洗</option>
                </select>
            </div>
            <div class="modal-form-group" id="clean-worker-group">
                <span class="modal-form-label">数字员工（AI 清洗必填）</span>
                <select class="modal-form-select" id="clean-worker-select">${workerOptions}</select>
                <div style="font-size:12px;color:var(--text-light);margin-top:4px">💡 需要绑定 data_cleaner 工作 + API Key</div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.startCleaning()">▶️ 启动清洗</button>`);
    },

    /** 加载已清洗文档（从知识仓库获取） */
    async loadCleanedArticles() {
        const container = document.getElementById('cleaning-cleaned');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';

        const search = document.getElementById('clean-article-search')?.value?.trim() || '';

        try {
            const params = {};
            if (search) params.search = search;
            const qs = new URLSearchParams(params).toString();
            const url = '/api/warehouse/articles' + (qs ? '?' + qs : '');

            const res = await API.request('GET', url);
            const data = res.data;
            const articles = data?.items || data || [];

            if (!Array.isArray(articles) || articles.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">📄</div><div class="empty-text">暂无清洗后的文档</div></div>';
                return;
            }

            let html = '<div class="cleaning-data-list">';
            articles.forEach(a => {
                const time = App._formatTime(a.created_at);
                const contentPreview = (a.content || '')?.slice(0, 100) || '';
                html += `
                    <div class="cleaning-data-card cleaned">
                        <div class="cleaning-data-card-header">
                            <span class="cleaning-data-source">📄 ${API._escapeHtml(a.title || '无标题')}</span>
                            <span class="cleaning-data-tag tag tag-success">${a.status || 'published'}</span>
                        </div>
                        <div class="cleaning-data-domain">🌐 ${API._escapeHtml(a.domain_name || '未知来源')} · ${time}</div>
                        <div class="cleaning-data-preview">${API._escapeHtml(contentPreview)}</div>
                        <div class="cleaning-data-actions">
                            <button class="btn btn-xs btn-primary" onclick="API.viewArticleDetail(${a.id})" title="查看文章详情">👁️ 查看</button>
                            <button class="btn btn-xs btn-ghost" onclick="App.navigateToWarehouse(${a.id})" title="在知识仓库中查看">🏪 仓库</button>
                        </div>
                    </div>`;
            });
            html += '</div>';
            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 跳转到知识仓库 */
    navigateToWarehouse(articleId) {
        API.toast('info', '提示', `文章 #${articleId} 请在知识仓库模块查看`);
    },

    /** 切换清洗日志折叠 */
    _cleaningLogOpen: true,
    toggleCleaningLogs() {
        this._cleaningLogOpen = !this._cleaningLogOpen;
        const body = document.getElementById('cleaning-log-body');
        const toggle = document.getElementById('cleaning-log-toggle');
        if (body) body.style.display = this._cleaningLogOpen ? 'block' : 'none';
        if (toggle) toggle.textContent = this._cleaningLogOpen ? '▼' : '▶';
    },

    /** 显示清洗统计 */
    showCleaningStats() {
        API.loadData('cleaning', '/api/cleaning/stats', {
            container: null,
            renderer: 'stats'
        }).then(data => {
            if (!data) return;
            const html = `
                <div class="stats-grid" style="grid-template-columns:repeat(4,1fr)">
                    <div class="stat-card"><div class="stat-value">${data.total || 0}</div><div class="stat-label">总清洗</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--success)">${data.success || 0}</div><div class="stat-label">成功</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--danger)">${data.failed || 0}</div><div class="stat-label">失败</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--warning)">${data.processing || 0}</div><div class="stat-label">处理中</div></div>
                </div>`;
            API.showModal('📊 清洗统计', html, `<button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`);
        });
    },

    // ====== 知识仓库模块（完整实现 v2.0） ======

    /** 仓库分页状态 */
    _whPage: 1,
    _whPageSize: 15,
    _whTotal: 0,
    _whSelectedIds: new Set(),

    async loadWarehouse() {
        await this.loadWarehouseStats();
        await this.loadWarehouseArticles();
        await this.loadWarehouseCategories();
        await this.loadWarehouseDomains();
    },

    /** 加载仓库统计信息（带清洗状态） */
    async loadWarehouseStats() {
        const container = document.getElementById('warehouse-stats');
        if (!container) return;
        try {
            const res = await API.request('GET', '/api/warehouse/stats');
            const data = res.data || {};
            if (!data || !data.total_articles) {
                container.innerHTML = '<div class="stats-grid" style="grid-template-columns:repeat(4,1fr)">'
                    + Array(4).fill(0).map(() => '<div class="stat-card"><div class="stat-value">0</div><div class="stat-label">暂无数据</div></div>').join('')
                    + '</div>';
                return;
            }
            const cl = data.cleaning || {};
            container.innerHTML = `
                <div class="stats-grid" style="grid-template-columns:repeat(8,1fr)">
                    <div class="stat-card"><div class="stat-value">${data.total_articles}</div><div class="stat-label">📚 总文章</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--success)">${data.published}</div><div class="stat-label">✅ 已发布</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--warning)">${data.draft}</div><div class="stat-label">📝 草稿</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--info)">${data.today_new}</div><div class="stat-label">📅 今日新增</div></div>
                    <div class="stat-card"><div class="stat-value">${data.total_categories}</div><div class="stat-label">📁 分类</div></div>
                    <div class="stat-card"><div class="stat-value">${data.total_domains}</div><div class="stat-label">🌐 域名</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--success)">${cl.success || 0}</div><div class="stat-label">🧹 已清洗</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--danger)">${cl.failed || 0}</div><div class="stat-label">❌ 失败</div></div>
                </div>`;
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 加载文章列表（带筛选和分页） */
    async loadWarehouseArticles(page) {
        if (page !== undefined) this._whPage = page;
        const container = document.getElementById('warehouse-articles');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';

        const status = document.getElementById('wh-filter-status')?.value || '';
        const categoryId = document.getElementById('wh-filter-category')?.value || '';
        const domain = document.getElementById('wh-filter-domain')?.value || '';
        const q = document.getElementById('wh-search-input')?.value?.trim() || '';

        try {
            const params = new URLSearchParams();
            params.append('page', this._whPage);
            params.append('page_size', this._whPageSize);
            if (status) params.append('status', status);
            if (categoryId && categoryId !== 'all') params.append('category_id', categoryId);
            if (domain && domain !== 'all') params.append('domain', domain);
            if (q) params.append('q', q);

            const res = await API.request('GET', `/api/warehouse/articles?${params.toString()}`);
            const data = res.data || {};
            const items = data.items || [];
            this._whTotal = data.total || items.length;

            // 更新分页信息
            const infoEl = document.getElementById('wh-pagination-info');
            if (infoEl) {
                const totalPages = Math.ceil(this._whTotal / this._whPageSize) || 1;
                infoEl.textContent = `共 ${this._whTotal} 篇文章 · 第 ${this._whPage}/${totalPages} 页`;
            }

            if (!Array.isArray(items) || items.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">暂无文章，点击右上角"新建文章"创建</div></div>';
                this._renderWarehousePagination();
                return;
            }

            let html = '<div class="wh-article-list">';
            items.forEach(a => {
                const isSelected = this._whSelectedIds.has(a.id);
                const time = this._formatTime(a.created_at);
                const statusTag = a.status === 'published' ? 'tag-success' : 'tag-warning';
                const statusLabel = a.status === 'published' ? '✅ 已发布' : '📝 草稿';
                const contentPreview = (a.content || '').slice(0, 120);
                const domainName = a.domain_name || '未知来源';
                
                html += `
                    <div class="wh-article-card ${isSelected ? 'selected' : ''}" data-id="${a.id}">
                        <div class="wh-article-check" onclick="event.stopPropagation();App.toggleArticleSelect(${a.id})">
                            <div class="wh-checkbox ${isSelected ? 'checked' : ''}">${isSelected ? '✓' : ''}</div>
                        </div>
                        <div class="wh-article-body" onclick="API.viewArticleDetail(${a.id})">
                            <div class="wh-article-title-row">
                                <span class="wh-article-title">${API._escapeHtml(a.title || '无标题')}</span>
                                <span class="tag ${statusTag}" style="font-size:11px">${statusLabel}</span>
                            </div>
                            <div class="wh-article-meta">
                                <span>🌐 ${API._escapeHtml(domainName)}</span>
                                <span>🏷️ ${API._escapeHtml(a.tags || '-')}</span>
                                <span>🕐 ${time}</span>
                            </div>
                            ${contentPreview ? `<div class="wh-article-preview">${API._escapeHtml(contentPreview)}${(a.content || '').length > 120 ? '...' : ''}</div>` : ''}
                        </div>
                        <div class="wh-article-actions">
                            <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();API.editWarehouseArticle(${a.id})" title="编辑">✏️</button>
                            <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();API.deleteItem('warehouse-articles', ${a.id})" title="删除">🗑️</button>
                        </div>
                    </div>`;
            });
            html += '</div>';
            container.innerHTML = html;
            container._data = items;
            this._renderWarehousePagination();
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 渲染分页导航 */
    _renderWarehousePagination() {
        const navEl = document.getElementById('wh-pagination-nav');
        if (!navEl) return;
        const totalPages = Math.ceil(this._whTotal / this._whPageSize) || 1;
        if (totalPages <= 1) { navEl.innerHTML = ''; return; }
        
        let html = '';
        // 上一页
        html += `<button class="btn btn-xs ${this._whPage <= 1 ? 'btn-ghost disabled' : 'btn-primary'}" 
            onclick="App.loadWarehouseArticles(${this._whPage - 1})" ${this._whPage <= 1 ? 'disabled' : ''}>‹ 上一页</button>`;
        
        // 页码
        const start = Math.max(1, this._whPage - 2);
        const end = Math.min(totalPages, this._whPage + 2);
        if (start > 1) html += `<button class="btn btn-xs btn-ghost" onclick="App.loadWarehouseArticles(1)">1</button>${start > 2 ? '<span style="padding:0 4px">...</span>' : ''}`;
        for (let i = start; i <= end; i++) {
            html += `<button class="btn btn-xs ${i === this._whPage ? 'btn-primary' : 'btn-ghost'}" onclick="App.loadWarehouseArticles(${i})">${i}</button>`;
        }
        if (end < totalPages) html += `${end < totalPages - 1 ? '<span style="padding:0 4px">...</span>' : ''}<button class="btn btn-xs btn-ghost" onclick="App.loadWarehouseArticles(${totalPages})">${totalPages}</button>`;
        
        // 下一页
        html += `<button class="btn btn-xs ${this._whPage >= totalPages ? 'btn-ghost disabled' : 'btn-primary'}" 
            onclick="App.loadWarehouseArticles(${this._whPage + 1})" ${this._whPage >= totalPages ? 'disabled' : ''}>下一页 ›</button>`;
        
        navEl.innerHTML = html;
    },

    /** 切换文章复选 */
    toggleArticleSelect(id) {
        if (this._whSelectedIds.has(id)) {
            this._whSelectedIds.delete(id);
        } else {
            this._whSelectedIds.add(id);
        }
        this._updateBatchBar();
        // 刷新卡片选中样式
        const card = document.querySelector(`.wh-article-card[data-id="${id}"]`);
        if (card) {
            card.classList.toggle('selected');
            const checkbox = card.querySelector('.wh-checkbox');
            if (checkbox) {
                checkbox.classList.toggle('checked');
                checkbox.textContent = this._whSelectedIds.has(id) ? '✓' : '';
            }
        }
    },

    /** 更新批量操作栏 */
    _updateBatchBar() {
        const bar = document.getElementById('wh-batch-bar');
        const countEl = document.getElementById('wh-batch-count');
        if (!bar || !countEl) return;
        const count = this._whSelectedIds.size;
        if (count > 0) {
            bar.style.display = 'block';
            countEl.textContent = `已选 ${count} 篇`;
        } else {
            bar.style.display = 'none';
        }
    },

    /** 清除批量选择 */
    clearBatchSelect() {
        this._whSelectedIds.clear();
        this._updateBatchBar();
        document.querySelectorAll('.wh-article-card').forEach(c => {
            c.classList.remove('selected');
            const cb = c.querySelector('.wh-checkbox');
            if (cb) { cb.classList.remove('checked'); cb.textContent = ''; }
        });
    },

    /** 批量更新状态 */
    async batchUpdateStatus(status) {
        const ids = Array.from(this._whSelectedIds);
        if (ids.length === 0) { API.toast('warning', '提示', '请先选择文章'); return; }
        if (!confirm(`确定要将 ${ids.length} 篇文章状态更新为「${status === 'published' ? '已发布' : '草稿'}」吗？`)) return;
        try {
            await API.request('POST', '/api/warehouse/articles/batch-status', { ids, status });
            API.toast('success', '批量操作成功', `已更新 ${ids.length} 篇文章`);
            this.clearBatchSelect();
            this.loadWarehouseArticles();
        } catch (err) {
            API.toast('error', '批量操作失败', err.message);
        }
    },

    /** 批量删除 */
    async batchDeleteArticles() {
        const ids = Array.from(this._whSelectedIds);
        if (ids.length === 0) { API.toast('warning', '提示', '请先选择文章'); return; }
        if (!confirm(`确定要永久删除 ${ids.length} 篇文章吗？此操作不可撤销！`)) return;
        try {
            await API.request('POST', '/api/warehouse/articles/batch-delete', { ids });
            API.toast('success', '批量删除成功', `已删除 ${ids.length} 篇文章`);
            this.clearBatchSelect();
            this.loadWarehouseArticles();
        } catch (err) {
            API.toast('error', '批量删除失败', err.message);
        }
    },

    /** 加载分类列表 */
    async loadWarehouseCategories() {
        const container = document.getElementById('warehouse-categories');
        if (!container) return;
        try {
            const res = await API.request('GET', '/api/warehouse/categories');
            const categories = res.data || [];
            
            // 更新筛选下拉
            const filterSelect = document.getElementById('wh-filter-category');
            if (filterSelect) {
                filterSelect.innerHTML = '<option value="">全部分类</option>';
                categories.forEach(c => {
                    filterSelect.innerHTML += `<option value="${c.id}">${c.icon || '📁'} ${c.name}</option>`;
                });
            }

            if (!Array.isArray(categories) || categories.length === 0) {
                container.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-text" style="font-size:13px">暂无分类</div></div>';
                return;
            }

            let html = '';
            categories.forEach(c => {
                html += `
                    <div class="wh-category-item" style="display:flex; align-items:center; gap:8px; padding:6px 4px; border-bottom:1px solid var(--border); font-size:13px">
                        <span>${c.icon || '📁'}</span>
                        <span style="flex:1">${API._escapeHtml(c.name)}</span>
                        <span class="tag tag-default" style="font-size:11px">${c.article_count || 0}</span>
                        <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();API.editWarehouseCategory(${c.id})" title="编辑分类">✏️</button>
                        <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();API.deleteItem('warehouse-categories', ${c.id})" title="删除">🗑️</button>
                    </div>`;
            });
            container.innerHTML = html;
            container._data = categories;
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 加载域名列表 */
    async loadWarehouseDomains() {
        const container = document.getElementById('warehouse-domains');
        if (!container) return;
        try {
            const res = await API.request('GET', '/api/warehouse/domains');
            const domains = res.data || [];
            
            // 更新筛选下拉
            const filterSelect = document.getElementById('wh-filter-domain');
            if (filterSelect) {
                filterSelect.innerHTML = '<option value="">全部域名</option>';
                domains.forEach(d => {
                    if (d.domain) {
                        filterSelect.innerHTML += `<option value="${d.domain}">🌐 ${d.domain} (${d.count})</option>`;
                    }
                });
                // 兼容纯字符串数组
                if (typeof domains[0] === 'string') {
                    filterSelect.innerHTML = '<option value="">全部域名</option>';
                    domains.forEach(d => {
                        filterSelect.innerHTML += `<option value="${d}">🌐 ${d}</option>`;
                    });
                }
            }

            // 处理返回格式兼容（字符串数组 vs 对象数组）
            let domainItems = domains;
            if (Array.isArray(domains) && domains.length > 0 && typeof domains[0] === 'string') {
                domainItems = domains.map(d => ({ domain: d, count: 0 }));
            }

            if (!Array.isArray(domainItems) || domainItems.length === 0) {
                container.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-text" style="font-size:13px">暂无域名数据</div></div>';
                return;
            }

            let html = '';
            domainItems.forEach(d => {
                const count = d.count || 0;
                html += `
                    <div class="wh-domain-item" style="display:flex; align-items:center; gap:8px; padding:6px 4px; border-bottom:1px solid var(--border); font-size:13px; cursor:pointer" onclick="document.getElementById('wh-filter-domain').value='${d.domain}';App.loadWarehouseArticles()">
                        <span>🌐</span>
                        <span style="flex:1">${API._escapeHtml(d.domain)}</span>
                        <span class="tag tag-default" style="font-size:11px">${count} 篇</span>
                    </div>`;
            });
            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 显示快速搜索弹窗 */
    showQuickSearch() {
        API.showModal('🔍 快速搜索', `
            <div class="modal-form-group">
                <input class="modal-form-input" id="quick-search-input" placeholder="输入关键词搜索标题/内容/域名/标签..." style="font-size:15px; padding:10px" onkeydown="if(event.key==='Enter')App.doQuickSearch()" />
            </div>
            <div id="quick-search-results" style="margin-top:12px; max-height:400px; overflow-y:auto"></div>
        `, `<button class="btn btn-sm btn-primary" onclick="App.doQuickSearch()">🔍 搜索</button>
            <button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>`);
        setTimeout(() => document.getElementById('quick-search-input')?.focus(), 200);
    },

    /** 执行快速搜索 */
    async doQuickSearch() {
        const q = document.getElementById('quick-search-input')?.value?.trim();
        if (!q) { API.toast('warning', '提示', '请输入搜索关键词'); return; }
        const resultsEl = document.getElementById('quick-search-results');
        if (!resultsEl) return;
        resultsEl.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 搜索中...</div>';
        try {
            const res = await API.request('GET', `/api/warehouse/articles?q=${encodeURIComponent(q)}&page_size=20`);
            const data = res.data || {};
            const items = data.items || [];
            if (!Array.isArray(items) || items.length === 0) {
                resultsEl.innerHTML = '<div class="empty-state"><div class="empty-text">未找到相关文章</div></div>';
                return;
            }
            let html = `<div style="font-size:12px;color:var(--text-light);margin-bottom:8px">找到 ${data.total || items.length} 篇相关文章</div>`;
            items.forEach(a => {
                html += `
                    <div class="wh-search-result" style="padding:8px 10px; border:1px solid var(--border); border-radius:var(--radius-xs); margin-bottom:6px; cursor:pointer" onclick="API.closeModal();API.viewArticleDetail(${a.id})">
                        <div style="font-weight:500">${API._escapeHtml(a.title || '无标题')}</div>
                        <div style="font-size:12px;color:var(--text-light);margin-top:4px">
                            <span>🌐 ${API._escapeHtml(a.domain_name || '未知')}</span>
                            <span style="margin-left:12px">📅 ${this._formatTime(a.created_at)}</span>
                            <span style="margin-left:12px">${a.status === 'published' ? '✅ 已发布' : '📝 草稿'}</span>
                        </div>
                        ${a.content ? `<div style="font-size:12px;color:var(--text-light);margin-top:4px">${API._escapeHtml(a.content.slice(0, 100))}...</div>` : ''}
                    </div>`;
            });
            resultsEl.innerHTML = html;
        } catch (err) {
            resultsEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 新建文章弹窗 */
    showCreateWarehouseArticle() {
        // 先加载分类供选择
        API.request('GET', '/api/warehouse/categories').then(catRes => {
            const categories = catRes.data || [];
            const catOptions = categories.map(c => `<option value="${c.id}">${c.icon || '📁'} ${c.name}</option>`).join('');

            const formHtml = `
                <div class="modal-form-group">
                    <span class="modal-form-label">标题 *</span>
                    <input class="modal-form-input" id="wh-new-title" placeholder="文章标题" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">分类</span>
                    <select class="modal-form-select" id="wh-new-category">
                        <option value="">-- 无分类 --</option>
                        ${catOptions}
                    </select>
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">原文 URL</span>
                    <input class="modal-form-input" id="wh-new-url" placeholder="https://..." />
                    <div style="font-size:11px;color:var(--text-light);margin-top:4px">💡 输入URL后域名将自动提取</div>
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">标签（逗号分隔）</span>
                    <input class="modal-form-input" id="wh-new-tags" placeholder="科技, AI, 新闻" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">内容</span>
                    <textarea class="modal-form-textarea" id="wh-new-content" rows="6" placeholder="文章内容..."></textarea>
                </div>`;

            API.showModal('📝 新建文章', formHtml,
                `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
                 <button class="btn btn-sm btn-primary" onclick="App.doCreateWarehouseArticle()">💾 保存</button>`
            );
        }).catch(err => {
            API.toast('error', '加载分类失败', err.message);
        });
    },

    /** 执行创建文章 */
    async doCreateWarehouseArticle() {
        const title = document.getElementById('wh-new-title')?.value?.trim();
        if (!title) { API.toast('warning', '提示', '请输入文章标题'); return; }
        const body = {
            title,
            category_id: parseInt(document.getElementById('wh-new-category')?.value) || null,
            url: document.getElementById('wh-new-url')?.value?.trim() || '',
            tags: document.getElementById('wh-new-tags')?.value?.trim() || '',
            content: document.getElementById('wh-new-content')?.value?.trim() || '',
        };
        try {
            const res = await API.request('POST', '/api/warehouse/articles', body);
            API.toast('success', '创建成功', `文章 #${res.data?.id} 已创建`);
            API.closeModal();
            this.loadWarehouseArticles(1);
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    /** 新建分类弹窗 */
    showCreateWarehouseCategory() {
        API.showModal('📁 新建分类', `
            <div class="modal-form-group">
                <span class="modal-form-label">分类名称 *</span>
                <input class="modal-form-input" id="wh-cat-name" placeholder="例如: 科技新闻" />
            </div>
            <div class="modal-form-group">
                <span class="modal-form-label">图标</span>
                <input class="modal-form-input" id="wh-cat-icon" placeholder="📁" value="📁" />
            </div>
            <div class="modal-form-group">
                <span class="modal-form-label">描述</span>
                <input class="modal-form-input" id="wh-cat-desc" placeholder="分类描述（可选）" />
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.doCreateWarehouseCategory()">💾 保存</button>`);
    },

    /** 执行创建分类 */
    async doCreateWarehouseCategory() {
        const name = document.getElementById('wh-cat-name')?.value?.trim();
        if (!name) { API.toast('warning', '提示', '请输入分类名称'); return; }
        try {
            await API.request('POST', '/api/warehouse/categories', {
                name,
                icon: document.getElementById('wh-cat-icon')?.value?.trim() || '📁',
                description: document.getElementById('wh-cat-desc')?.value?.trim() || '',
            });
            API.toast('success', '创建成功', '分类已创建');
            API.closeModal();
            this.loadWarehouseCategories();
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    async loadSentiment() {
        await this.loadSentimentAnalyses();
    },

    /** 加载舆情分析列表 */
    async loadSentimentAnalyses() {
        const container = document.getElementById('sentiment-analyses');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';

        try {
            const res = await API.request('GET', '/api/sentiment/analyses');
            const data = res.data || {};
            const items = data.items || data || [];
            const analyses = Array.isArray(items) ? items : [];

            const countEl = document.getElementById('sentiment-count');
            if (countEl) countEl.textContent = analyses.length;

            if (analyses.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">📊</div><div class="empty-text">暂无分析记录，点击右上角"触发分析"开始</div></div>';
                return;
            }

            let html = '';
            analyses.forEach(a => {
                const sentiment = a.overall_sentiment || 'unknown';
                const sentimentLabel = { 'positive': '正面', 'negative': '负面', 'neutral': '中性', 'mixed': '混合' }[sentiment] || sentiment;
                const statusLabel = a.status === 'completed' ? '✅' : (a.status === 'processing' ? '⏳' : '❌');
                const time = App._formatTime(a.created_at);
                const summary = a.summary || '';

                html += `
                    <div class="sentiment-analysis-item" data-id="${a.id}" onclick="App.selectSentimentAnalysis(${a.id})">
                        <div class="sentiment-item-top">
                            <span class="sentiment-item-id">#${a.id} ${statusLabel}</span>
                            <span class="sentiment-item-sentiment ${sentiment}">${sentimentLabel}</span>
                        </div>
                        <div class="sentiment-item-meta">
                            <span>📊 ${a.articles_analyzed || 0} 条数据</span>
                            <span>${time}</span>
                        </div>
                        ${summary ? `<div class="sentiment-item-summary">${API._escapeHtml(summary)}</div>` : ''}
                    </div>
                `;
            });
            container.innerHTML = html;
            container._data = analyses;

            if (this._selectedAnalysisId) {
                const activeItem = container.querySelector(`.sentiment-analysis-item[data-id="${this._selectedAnalysisId}"]`);
                if (activeItem) activeItem.classList.add('active');
            }
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ 加载失败: ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 选中一条分析记录 */
    _selectedAnalysisId: null,

    async selectSentimentAnalysis(analysisId) {
        this._selectedAnalysisId = analysisId;

        document.querySelectorAll('.sentiment-analysis-item').forEach(el => el.classList.remove('active'));
        const activeItem = document.querySelector(`.sentiment-analysis-item[data-id="${analysisId}"]`);
        if (activeItem) activeItem.classList.add('active');

        document.getElementById('sentiment-default-hint').style.display = 'none';
        document.getElementById('sentiment-detail-content').style.display = 'block';

        const overviewEl = document.getElementById('sentiment-overview');
        const eventsEl = document.getElementById('sentiment-events');
        if (overviewEl) overviewEl.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载详情...</div>';
        if (eventsEl) eventsEl.innerHTML = '';

        try {
            const res = await API.request('GET', `/api/sentiment/analyses/${analysisId}`);
            const detail = res.data || res;
            if (!detail) return;

            if (overviewEl) {
                const sentiment = detail.overall_sentiment || 'neutral';
                const sentimentLabel = { 'positive': '正面', 'negative': '负面', 'neutral': '中性', 'mixed': '混合' }[sentiment] || sentiment;

                overviewEl.innerHTML = `
                    <div class="sentiment-overview-card">
                        <div class="sentiment-ov-value ${sentiment}">${sentimentLabel}</div>
                        <div class="sentiment-ov-label">整体情感</div>
                    </div>
                    <div class="sentiment-overview-card">
                        <div class="sentiment-ov-value">${detail.articles_analyzed || 0}</div>
                        <div class="sentiment-ov-label">分析数据</div>
                    </div>
                    <div class="sentiment-overview-card">
                        <div class="sentiment-ov-value">${(detail.events || []).length}</div>
                        <div class="sentiment-ov-label">检测事件</div>
                    </div>
                    <div class="sentiment-overview-card">
                        <div class="sentiment-ov-value">${(detail.words || []).length}</div>
                        <div class="sentiment-ov-label">关键词数</div>
                    </div>
                    <div class="sentiment-overview-card">
                        <div class="sentiment-ov-value">${(detail.locations || []).length}</div>
                        <div class="sentiment-ov-label">涉及地点</div>
                    </div>
                `;
            }

            if (eventsEl) {
                const events = detail.events || [];
                if (events.length === 0) {
                    eventsEl.innerHTML = '<div class="empty-state"><div class="empty-text">未检测到舆情事件</div></div>';
                } else {
                    let evHtml = '';
                    events.forEach(e => {
                        const sentimentType = e.sentiment_type || 'neutral';
                        const keywords = [];
                        try {
                            const parsed = typeof e.keywords_json === 'string' ? JSON.parse(e.keywords_json) : (e.keywords_json || []);
                            if (Array.isArray(parsed)) parsed.forEach(k => keywords.push(k));
                        } catch {}

                        evHtml += `
                            <div class="sentiment-event-card">
                                <div class="sentiment-event-header">
                                    <span class="sentiment-event-name">
                                        <span class="sentiment-tag ${sentimentType}">${sentimentType}</span>
                                        ${API._escapeHtml(e.event_name || '未知事件')}
                                    </span>
                                    <span class="sentiment-event-heat">🔥 ${e.heat || 0}</span>
                                </div>
                                <div class="sentiment-event-desc">${API._escapeHtml(e.description || '')}</div>
                                ${keywords.length > 0 ? `
                                    <div class="sentiment-event-keywords">
                                        ${keywords.map(k => `<span class="sentiment-event-keyword">${API._escapeHtml(k)}</span>`).join('')}
                                    </div>
                                ` : ''}
                            </div>
                        `;
                    });
                    eventsEl.innerHTML = evHtml;
                }
            }

            this._currentAnalysisDetail = detail;

        } catch (err) {
            if (overviewEl) overviewEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 触发舆情分析 */
    async triggerSentimentAnalysis() {
        const btn = event?.target;
        if (btn) { btn.disabled = true; btn.textContent = '⏳ 分析中...'; }

        try {
            const res = await API.request('POST', '/api/sentiment/analyses/trigger', { trigger_type: 'manual' });
            const data = res.data || {};
            API.toast('success', '分析完成', `舆情分析 #${data.id} 已生成`);
            await this.loadSentimentAnalyses();
            if (data.id) {
                await this.selectSentimentAnalysis(data.id);
            }
        } catch (err) {
            API.toast('error', '分析失败', err.message);
        } finally {
            if (btn) { btn.disabled = false; btn.textContent = '⚡ 触发分析'; }
        }
    },

    // ========== 词云弹窗 ==========

    openWordcloudModal() {
        const modal = document.getElementById('wordcloudModal');
        if (!modal) return;
        modal.classList.add('active');

        const body = document.getElementById('wordcloud-body');
        if (!body) return;
        body.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 生成词云...</div>';

        const detail = this._currentAnalysisDetail;
        if (!detail) {
            body.innerHTML = '<div class="empty-state">请先选择一条分析记录</div>';
            return;
        }

        const words = detail.words || [];
        if (words.length === 0) {
            body.innerHTML = '<div class="empty-state">暂无词云数据</div>';
            return;
        }

        setTimeout(() => this._drawWordcloud(body, words), 100);
    },

    _drawWordcloud(container, words) {
        container.innerHTML = '';

        const canvas = document.createElement('canvas');
        canvas.width = 700;
        canvas.height = 500;
        container.appendChild(canvas);
        container.style.background = 'var(--bg)';

        const ctx = canvas.getContext('2d');
        ctx.clearRect(0, 0, canvas.width, canvas.height);

        ctx.fillStyle = getComputedStyle(document.documentElement).getPropertyValue('--bg').trim() || '#f8fafc';
        ctx.fillRect(0, 0, canvas.width, canvas.height);

        const sorted = words.sort((a, b) => b.weight - a.weight).slice(0, 40);
        const maxWeight = sorted[0]?.weight || 1;

        const colors = ['#6366f1', '#8b5cf6', '#22c55e', '#f59e0b', '#ef4444', '#3b82f6', '#ec4899', '#14b8a6'];

        const placed = [];
        const centerX = canvas.width / 2;
        const centerY = canvas.height / 2;

        sorted.forEach((w, idx) => {
            const ratio = w.weight / maxWeight;
            const fontSize = 14 + ratio * 40;
            const word = w.word || '';
            const color = colors[idx % colors.length];

            ctx.font = `bold ${fontSize}px "Microsoft YaHei", sans-serif`;
            const metrics = ctx.measureText(word);
            const textWidth = metrics.width;
            const textHeight = fontSize;

            let wordPlaced = false;
            for (let attempt = 0; attempt < 200; attempt++) {
                const angle = Math.random() * Math.PI * 2;
                const radius = 20 + Math.random() * Math.min(centerX, centerY) * 0.8;
                const x = centerX + Math.cos(angle) * radius - textWidth / 2;
                const y = centerY + Math.sin(angle) * radius;

                let collision = false;
                for (const p of placed) {
                    if (x < p.x + p.w + 4 && x + textWidth + 4 > p.x &&
                        y < p.y + p.h + 4 && y + textHeight + 4 > p.y) {
                        collision = true;
                        break;
                    }
                }

                if (!collision) {
                    ctx.fillStyle = color;
                    ctx.fillText(word, x, y + fontSize * 0.8);
                    placed.push({ x, y, w: textWidth, h: textHeight });
                    wordPlaced = true;
                    break;
                }
            }
            if (!wordPlaced) {
                ctx.fillStyle = color;
                const fx = centerX - textWidth / 2 + (Math.random() - 0.5) * 100;
                const fy = centerY + (Math.random() - 0.5) * 100;
                ctx.fillText(word, fx, fy + fontSize * 0.8);
                placed.push({ x: fx, y: fy, w: textWidth, h: textHeight });
            }
        });
    },

    closeWordcloudModal() {
        const modal = document.getElementById('wordcloudModal');
        if (modal) modal.classList.remove('active');
    },

    // ========== 3D 地球弹窗 ==========

    openGlobeModal() {
        const modal = document.getElementById('globeModal');
        if (!modal) return;
        modal.classList.add('active');

        const body = document.getElementById('globe-body');
        if (!body) return;
        body.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 生成 3D 地球...</div>';

        const detail = this._currentAnalysisDetail;
        if (!detail) {
            body.innerHTML = '<div class="empty-state">请先选择一条分析记录</div>';
            return;
        }

        const locations = detail.locations || [];
        if (locations.length === 0) {
            body.innerHTML = '<div class="empty-state"><div class="empty-icon">🌍</div><div class="empty-text">该分析未提取到地点信息</div></div>';
            return;
        }

        setTimeout(() => this._initGlobe(body, locations), 200);
    },

    _initGlobe(container, locations) {
        container.innerHTML = '';
        const vizContainer = document.createElement('div');
        vizContainer.id = 'globe-container';
        vizContainer.style.width = '100%';
        vizContainer.style.height = '100%';
        container.appendChild(vizContainer);

        try {
            const scene = new THREE.Scene();

            const camera = new THREE.PerspectiveCamera(45, vizContainer.clientWidth / vizContainer.clientHeight, 0.1, 1000);
            camera.position.set(0, 0, 3.5);

            const renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
            renderer.setSize(vizContainer.clientWidth, vizContainer.clientHeight);
            renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
            vizContainer.appendChild(renderer.domElement);

            const controls = new THREE.OrbitControls(camera, renderer.domElement);
            controls.enableDamping = true;
            controls.dampingFactor = 0.05;
            controls.rotateSpeed = 0.8;
            controls.minDistance = 2;
            controls.maxDistance = 8;

            const textureLoader = new THREE.TextureLoader();
            const earthMapUrl = 'https://threejs.org/examples/textures/planets/earth_atmos_2048.jpg';
            
            const earthGeometry = new THREE.SphereGeometry(1.3, 64, 64);
            const earthMaterial = new THREE.MeshPhongMaterial({
                map: textureLoader.load(earthMapUrl),
                specular: new THREE.Color(0x333333),
                shininess: 5,
            });
            const earth = new THREE.Mesh(earthGeometry, earthMaterial);
            scene.add(earth);

            const glowGeometry = new THREE.SphereGeometry(1.35, 48, 48);
            const glowMaterial = new THREE.MeshPhongMaterial({
                color: 0x4488ff,
                transparent: true,
                opacity: 0.08,
                side: THREE.BackSide,
            });
            const glow = new THREE.Mesh(glowGeometry, glowMaterial);
            scene.add(glow);

            const markerMaterial = new THREE.MeshBasicMaterial({ color: 0xef4444 });
            const markerGlowMaterial = new THREE.MeshBasicMaterial({ color: 0xef4444, transparent: true, opacity: 0.3 });
            const labelCanvas = document.createElement('canvas');
            labelCanvas.width = 256;
            labelCanvas.height = 64;
            const labelCtx = labelCanvas.getContext('2d');

            locations.forEach(loc => {
                const lat = loc.latitude || 0;
                const lng = loc.longitude || 0;

                const phi = ((90 - lat) / 180) * Math.PI;
                const theta = ((lng + 180) / 360) * 2 * Math.PI;
                const r = 1.36;

                const x = -r * Math.cos(theta) * Math.sin(phi);
                const y = r * Math.cos(phi);
                const z = r * Math.sin(theta) * Math.sin(phi);

                const dot = new THREE.Mesh(new THREE.SphereGeometry(0.04, 8, 8), markerMaterial);
                dot.position.set(x, y, z);
                earth.add(dot);

                const glow = new THREE.Mesh(new THREE.SphereGeometry(0.07, 8, 8), markerGlowMaterial);
                glow.position.set(x, y, z);
                earth.add(glow);

                labelCtx.clearRect(0, 0, labelCanvas.width, labelCanvas.height);
                labelCtx.fillStyle = 'rgba(0,0,0,0.55)';
                labelCtx.roundRect ? labelCtx.roundRect(8, 8, 240, 48, 8) : labelCtx.fillRect(8, 8, 240, 48);
                labelCtx.fill();
                labelCtx.fillStyle = '#ffffff';
                labelCtx.font = 'bold 22px "Microsoft YaHei", sans-serif';
                labelCtx.textAlign = 'center';
                labelCtx.textBaseline = 'middle';
                labelCtx.fillText(loc.location_name || '未知', 128, 32);

                const labelTexture = new THREE.CanvasTexture(labelCanvas);
                const spriteMaterial = new THREE.SpriteMaterial({ map: labelTexture, transparent: true, depthTest: false });
                const sprite = new THREE.Sprite(spriteMaterial);
                sprite.position.set(x * 1.1, y * 1.1 + 0.12, z * 1.1);
                sprite.scale.set(0.4, 0.1, 1);
                earth.add(sprite);
            });

            const starsGeometry = new THREE.BufferGeometry();
            const starsCount = 2000;
            const positions = new Float32Array(starsCount * 3);
            for (let i = 0; i < starsCount * 3; i++) {
                positions[i] = (Math.random() - 0.5) * 200;
            }
            starsGeometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
            const starsMaterial = new THREE.PointsMaterial({ color: 0xffffff, size: 0.15, transparent: true });
            const stars = new THREE.Points(starsGeometry, starsMaterial);
            scene.add(stars);

            const ambientLight = new THREE.AmbientLight(0x404060);
            scene.add(ambientLight);
            const directionalLight = new THREE.DirectionalLight(0xffffff, 0.8);
            directionalLight.position.set(5, 5, 5);
            scene.add(directionalLight);
            const backLight = new THREE.DirectionalLight(0x4488ff, 0.3);
            backLight.position.set(-5, -5, -5);
            scene.add(backLight);

            function animate() {
                requestAnimationFrame(animate);
                earth.rotation.y += 0.002;
                stars.rotation.y -= 0.0002;
                controls.update();
                renderer.render(scene, camera);
            }
            animate();

            const onResize = () => {
                const w = vizContainer.clientWidth;
                const h = vizContainer.clientHeight;
                camera.aspect = w / h;
                camera.updateProjectionMatrix();
                renderer.setSize(w, h);
            };
            window.addEventListener('resize', onResize);

            this._globeCleanup = () => {
                window.removeEventListener('resize', onResize);
                renderer.dispose();
                scene.traverse(obj => {
                    if (obj.geometry) obj.geometry.dispose();
                    if (obj.material) {
                        if (obj.material.map) obj.material.map.dispose();
                        obj.material.dispose();
                    }
                });
            };

        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ 3D 加载失败: ${API._escapeHtml(err.message)}</div>`;
        }
    },

    closeGlobeModal() {
        const modal = document.getElementById('globeModal');
        if (modal) modal.classList.remove('active');
        if (this._globeCleanup) {
            this._globeCleanup();
            this._globeCleanup = null;
        }
    },

    // ========== 大屏快照弹窗 ==========

    async openDashboardModal() {
        const modal = document.getElementById('dashboardModal');
        if (!modal) return;
        modal.classList.add('active');

        const body = document.getElementById('dashboard-body');
        if (!body) return;
        body.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载大屏快照...</div>';

        try {
            const res = await API.request('GET', '/api/sentiment/dashboard');
            const dash = res.data || {};

            let topWords = [];
            let topEvents = [];
            try { topWords = JSON.parse(dash.top_words_json || '[]'); } catch {}
            try { topEvents = JSON.parse(dash.top_events_json || '[]'); } catch {}

            body.innerHTML = `
                <div class="dashboard-snapshot">
                    <div class="dashboard-snapshot-grid">
                        <div class="dashboard-snapshot-card">
                            <div class="dashboard-snapshot-value">${dash.total_articles || 0}</div>
                            <div class="dashboard-snapshot-label">分析文章</div>
                        </div>
                        <div class="dashboard-snapshot-card">
                            <div class="dashboard-snapshot-value" style="color:var(--success)">${dash.positive_count || 0}</div>
                            <div class="dashboard-snapshot-label">正面事件</div>
                        </div>
                        <div class="dashboard-snapshot-card">
                            <div class="dashboard-snapshot-value" style="color:var(--danger)">${dash.negative_count || 0}</div>
                            <div class="dashboard-snapshot-label">负面事件</div>
                        </div>
                        <div class="dashboard-snapshot-card">
                            <div class="dashboard-snapshot-value">${dash.neutral_count || 0}</div>
                            <div class="dashboard-snapshot-label">中性事件</div>
                        </div>
                        <div class="dashboard-snapshot-card">
                            <div class="dashboard-snapshot-value">${dash.total_events || 0}</div>
                            <div class="dashboard-snapshot-label">总事件数</div>
                        </div>
                        <div class="dashboard-snapshot-card">
                            <div class="dashboard-snapshot-value">${dash.avg_heat || 0}</div>
                            <div class="dashboard-snapshot-label">平均热度</div>
                        </div>
                    </div>

                    ${topWords.length > 0 ? `
                        <div class="dashboard-snapshot-section">
                            <h4>🏆 热门关键词 TOP 20</h4>
                            <div class="dashboard-rank-list">
                                ${topWords.map(w => `<span class="dashboard-rank-item">${API._escapeHtml(w.word || '')} <span class="dashboard-rank-heat">${w.weight || 0}</span></span>`).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${topEvents.length > 0 ? `
                        <div class="dashboard-snapshot-section">
                            <h4>🔥 热门事件 TOP 10</h4>
                            <div class="dashboard-rank-list">
                                ${topEvents.map(e => `<span class="dashboard-rank-item">${API._escapeHtml(e.name || '')} <span class="dashboard-rank-heat">🔥${e.heat || 0}</span></span>`).join('')}
                            </div>
                        </div>
                    ` : ''}

                    ${dash.snapshot_at ? `<div style="text-align:right;font-size:12px;color:var(--text-light);margin-top:16px">快照时间: ${App._formatTime(dash.snapshot_at)}</div>` : ''}
                </div>
            `;
        } catch (err) {
            body.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    closeDashboardModal() {
        const modal = document.getElementById('dashboardModal');
        if (modal) modal.classList.remove('active');
    },

    // ====== 聊天模块状态 ======
    _chat: {
        currentConvId: null,
        isStreaming: false,
        abortController: null,
        messages: [],
    },

    async loadChat() {
        this.loadChatConversations();
        this._startChatPolling();
    },

    /** 加载对话列表 */
    async loadChatConversations() {
        const listEl = document.getElementById('chat-conv-list');
        if (!listEl) return;
        try {
            const res = await API.request('GET', '/api/chat/conversations');
            const conversations = res.data?.items || res.data || [];
            if (!Array.isArray(conversations)) {
                listEl.innerHTML = '<div class="empty-state">暂无对话</div>';
                return;
            }
            if (conversations.length === 0) {
                listEl.innerHTML = '<div class="empty-state"><div class="empty-icon">💬</div><div class="empty-text">暂无对话，点击 ➕ 新建</div></div>';
                return;
            }
            let html = '';
            conversations.forEach(c => {
                const isActive = this._chat.currentConvId === c.id;
                const time = c.updated_at ? App._formatTime(c.updated_at, 'short') : '';
                html += `
                    <div class="chat-conv-item ${isActive ? 'active' : ''}" data-id="${c.id}" onclick="App.selectConversation(${c.id})">
                        <span class="chat-conv-item-icon">💬</span>
                        <div class="chat-conv-item-body">
                            <div class="chat-conv-item-title">${API._escapeHtml(c.title || '新对话')}</div>
                            <div class="chat-conv-item-time">${time}</div>
                        </div>
                        <div class="chat-conv-item-actions">
                            <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();App.renameConversation(${c.id})" title="重命名">✏️</button>
                            <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();App.deleteConversation(${c.id})" title="删除">🗑️</button>
                        </div>
                    </div>`;
            });
            listEl.innerHTML = html;
        } catch (err) {
            listEl.innerHTML = `<div class="error-state">❌ 加载失败: ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 选择对话 */
    async selectConversation(convId) {
        if (this._chat.isStreaming) {
            if (!confirm('当前有AI正在回复，是否中断并切换对话？')) return;
            this.stopChatMessage();
        }
        this._chat.currentConvId = convId;
        this._chat.messages = [];

        document.querySelectorAll('.chat-conv-item').forEach(el => el.classList.remove('active'));
        const activeItem = document.querySelector(`.chat-conv-item[data-id="${convId}"]`);
        if (activeItem) activeItem.classList.add('active');

        await this.loadChatMessages(convId);

        const inputEl = document.getElementById('chat-input');
        if (inputEl) { inputEl.disabled = false; inputEl.focus(); }
    },

    /** 加载对话消息 */
    async loadChatMessages(convId) {
        const msgEl = document.getElementById('chat-messages');
        if (!msgEl) return;
        msgEl.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载消息中...</div>';

        try {
            const res = await API.request('GET', `/api/chat/conversations/${convId}/messages`);
            const messages = res.data?.items || res.data || [];
            if (!Array.isArray(messages)) {
                msgEl.innerHTML = '<div class="chat-welcome"><div class="chat-welcome-icon">💬</div><h3>智能问数</h3><p>开始输入您的问题</p></div>';
                return;
            }
            if (messages.length === 0) {
                msgEl.innerHTML = '<div class="chat-welcome"><div class="chat-welcome-icon">💬</div><h3>智能问数</h3><p>开始输入您的问题</p></div>';
                this._chat.messages = [];
                return;
            }
            this._chat.messages = messages;
            msgEl.innerHTML = '';
            messages.forEach(m => this.renderMessage(m.role, m.content, m.created_at));
            this.scrollToBottom();
        } catch (err) {
            msgEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 渲染单条消息 */
    renderMessage(role, content, createdAt) {
        const msgEl = document.getElementById('chat-messages');
        if (!msgEl) return;

        const welcome = msgEl.querySelector('.chat-welcome');
        if (welcome) msgEl.innerHTML = '';

        const time = createdAt ? App._formatTime(createdAt) : new Date().toLocaleString('zh-CN');
        const avatar = role === 'user' ? '👤' : '🤖';
        const div = document.createElement('div');
        div.className = `chat-msg ${role}`;
        div.innerHTML = `
            <div class="chat-msg-avatar">${avatar}</div>
            <div>
                <div class="chat-msg-bubble">${API._escapeHtml(content)}</div>
                <div class="chat-msg-time">${time}</div>
            </div>`;
        msgEl.appendChild(div);
        this.scrollToBottom();
    },

    /** 渲染流式消息（实时追加到最后一个assistant消息） */
    renderStreamToken(token) {
        const msgEl = document.getElementById('chat-messages');
        if (!msgEl) return;
        let lastMsg = msgEl.querySelector('.chat-msg.assistant:last-child');
        if (!lastMsg) {
            const avatar = '🤖';
            const div = document.createElement('div');
            div.className = 'chat-msg assistant';
            div.innerHTML = `
                <div class="chat-msg-avatar">${avatar}</div>
                <div>
                    <div class="chat-msg-bubble"></div>
                    <div class="chat-msg-time">${new Date().toLocaleString('zh-CN')}</div>
                </div>`;
            msgEl.appendChild(div);
            lastMsg = div;
        }
        const bubble = lastMsg.querySelector('.chat-msg-bubble');
        if (bubble) {
            bubble.textContent += token;
        }
        this.scrollToBottom();
    },

    /** 隐藏打字指示器 */
    hideTyping() {
        const typing = document.getElementById('chat-typing-indicator');
        if (typing) typing.remove();
    },

    /** 滚动到底部 */
    scrollToBottom() {
        const msgEl = document.getElementById('chat-messages');
        if (msgEl) {
            setTimeout(() => { msgEl.scrollTop = msgEl.scrollHeight; }, 10);
        }
    },

    /** 发送消息到当前选中对话 */
    async sendChatMessage() {
        const convId = this._chat.currentConvId;
        const inputEl = document.getElementById('chat-input');
        const content = inputEl?.value?.trim();
        if (!convId) { API.toast('warning', '提示', '请先在右侧选择或新建一个对话'); return; }
        if (!content) { API.toast('warning', '提示', '请输入消息内容'); return; }
        if (this._chat.isStreaming) { API.toast('warning', '提示', '正在回复中，请等待或中断当前回复'); return; }

        inputEl.value = '';
        inputEl.style.height = 'auto';

        this.renderMessage('user', content);
        this._chat.messages.push({ role: 'user', content });

        const stopBtn = document.getElementById('chatStopBtn');
        if (stopBtn) stopBtn.style.display = 'flex';

        const msgEl = document.getElementById('chat-messages');
        if (msgEl && !msgEl.querySelector('.chat-welcome')) {
            const typing = document.createElement('div');
            typing.className = 'chat-typing';
            typing.id = 'chat-typing-indicator';
            typing.innerHTML = `
                <div class="chat-msg-avatar" style="background:var(--bg-input);border:1px solid var(--border);border-radius:50%;width:32px;height:32px;display:flex;align-items:center;justify-content:center;font-size:16px">🤖</div>
                <div class="chat-typing-dots"><span></span><span></span><span></span></div>`;
            msgEl.appendChild(typing);
            this.scrollToBottom();
        }

        this._chat.isStreaming = true;

        try {
            const headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            };
            if (API.token) headers['Authorization'] = `Bearer ${API.token}`;

            const response = await fetch(`${API.BASE_URL}/api/chat/message`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ content, conversation_id: convId })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                API.toast('error', '消息发送失败', errData.message || `HTTP ${response.status}`);
                this._chat.isStreaming = false;
                if (stopBtn) stopBtn.style.display = 'none';
                this.hideTyping();
                this.renderMessage('assistant', `❌ 错误: ${errData.message || response.statusText}`);
                return;
            }

            this.hideTyping();

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let fullResponse = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6).trim();
                        if (!dataStr || dataStr === '[DONE]') continue;
                        try {
                            const parsed = JSON.parse(dataStr);
                            if (parsed.type === 'token') {
                                fullResponse += parsed.content || '';
                                this.renderStreamToken(parsed.content || '');
                            } else if (parsed.type === 'meta') {
                            } else if (parsed.type === 'error') {
                                API.toast('error', 'AI回复错误', parsed.content);
                                this.renderStreamToken(`\n\n❌ ${parsed.content}`);
                            }
                        } catch {
                            if (dataStr) this.renderStreamToken(dataStr);
                        }
                    }
                }
            }

            this._chat.messages.push({ role: 'assistant', content: fullResponse });
            this._chat.isStreaming = false;
            if (stopBtn) stopBtn.style.display = 'none';

            this.loadChatConversations();

        } catch (err) {
            this._chat.isStreaming = false;
            if (stopBtn) stopBtn.style.display = 'none';
            this.hideTyping();
            if (err.name === 'AbortError') {
                this.renderStreamToken('\n\n[⏹️ 已中断]');
            } else {
                API.toast('error', '请求失败', err.message);
                this.renderStreamToken(`\n\n❌ 错误: ${err.message}`);
            }
        }
    },

    /** 中断AI回复 */
    stopChatMessage() {
        if (this._chat.isStreaming) {
            const convId = this._chat.currentConvId;
            if (convId) {
                API.request('POST', '/api/chat/message/stop', { conversation_id: convId }).catch(() => {});
            }
            this._chat.isStreaming = false;
            const stopBtn = document.getElementById('chatStopBtn');
            if (stopBtn) stopBtn.style.display = 'none';
            this.hideTyping();
        }
    },

    /** 删除对话 */
    async deleteConversation(convId) {
        if (!confirm('确定要删除这个对话及其所有消息吗？')) return;
        try {
            await API.request('DELETE', `/api/chat/conversation/${convId}`);
            API.toast('success', '删除成功', '对话已删除');
            if (this._chat.currentConvId === convId) {
                this._chat.currentConvId = null;
                this._chat.messages = [];
                const msgEl = document.getElementById('chat-messages');
                if (msgEl) {
                    msgEl.innerHTML = '<div class="chat-welcome"><div class="chat-welcome-icon">💬</div><h3>智能问数</h3><p>选择右侧对话或新建对话开始提问</p></div>';
                }
            }
            this.loadChatConversations();
        } catch (err) {
            API.toast('error', '删除失败', err.message);
        }
    },

    /** 重命名对话 */
    async renameConversation(convId, currentTitle) {
        if (currentTitle === undefined) {
            const titleEl = document.querySelector(`.chat-conv-item[data-id="${convId}"] .chat-conv-item-title`);
            currentTitle = titleEl ? titleEl.textContent : '新对话';
        }
        const newTitle = prompt('请输入新名称：', currentTitle || '新对话');
        if (!newTitle || newTitle.trim() === '') return;
        try {
            await API.request('PUT', `/api/chat/conversation/${convId}`, { title: newTitle.trim() });
            API.toast('success', '重命名成功');
            this.loadChatConversations();
            const convEl = document.querySelector(`.chat-conv-item[data-id="${convId}"] .chat-conv-item-title`);
            if (convEl) convEl.textContent = newTitle.trim();
        } catch (err) {
            API.toast('error', '重命名失败', err.message);
        }
    },

    // ========== IM 模块完整逻辑 ==========

    /** IM 聊天状态 */
    _im: {
        currentChat: null,
        conversations: [],
        friends: [],
        groups: [],
        messages: [],
        pollingTimer: null,
        currentIMTab: 'chat',
        // @提及相关状态
        atMenuActive: false,
        atMenuKeyword: '',
        atMenuMembers: [],
        atMenuFiltered: [],
        atSelectedIndex: 0,
        atCurrentGroupId: null,
    },

    async loadIM() {
        // 保存当前状态，避免刷新时丢失（保留当前标签和已选中聊天）
        const prevTab = this._im.currentIMTab || 'chat';
        const prevChat = this._im.currentChat;

        this._im.messages = [];
        this.loadIMConversations();
        this._loadIMFriendsAndGroupsInBackground();
        this.loadIMRequests();
        this._startIMMessagePolling();

        // 恢复之前的标签和聊天状态
        if (prevChat) {
            this._im.currentChat = prevChat;
            document.getElementById('im-chat-title').textContent = prevChat.name;
            const subtitle = prevChat.type === 'user' ? '好友 · 在线' : '群组';
            document.getElementById('im-chat-subtitle').textContent = subtitle;
            document.getElementById('im-chat-header-actions').style.display = 'flex';
            document.getElementById('im-input-area').style.display = 'block';
            const inputEl = document.getElementById('im-input');
            if (inputEl) inputEl.disabled = false;
            this.loadIMMessagesByChat(prevChat.type, prevChat.id, prevChat.name);
            this.switchIMTab(prevTab);
        } else {
            this.switchIMTab(prevTab);
            this._resetIMChatArea();
        }
    },

    /** 后台加载好友和群组列表（不阻塞UI） */
    async _loadIMFriendsAndGroupsInBackground() {
        try {
            await this.loadIMFriends();
        } catch {}
        try {
            await this.loadIMGroups();
        } catch {}
    },

    /** 切换 IM 左侧标签 */
    switchIMTab(tab) {
        this._im.currentIMTab = tab;
        document.querySelectorAll('.im-tab').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('.im-tab-content').forEach(el => el.classList.remove('active'));
        const tabBtn = document.querySelector(`.im-tab[data-imtab="${tab}"]`);
        if (tabBtn) tabBtn.classList.add('active');
        const tabContent = document.getElementById(`im-tab-${tab}`);
        if (tabContent) tabContent.classList.add('active');
    },

    /** 重置 IM 聊天区域 */
    _resetIMChatArea() {
        document.getElementById('im-chat-title').textContent = '选择一个会话开始聊天';
        document.getElementById('im-chat-subtitle').textContent = '';
        document.getElementById('im-chat-header-actions').style.display = 'none';
        document.getElementById('im-input-area').style.display = 'none';
        document.getElementById('im-messages').innerHTML = `
            <div class="im-welcome">
                <div class="im-welcome-icon">💬</div>
                <h3>智能聊天</h3>
                <p>从左侧选择一个好友或群组开始聊天</p>
            </div>`;
    },

    /** 加载会话列表 */
    async loadIMConversations() {
        const listEl = document.getElementById('im-conversation-list');
        if (!listEl) return;
        try {
            const result = await API.getConversations();
            // API.getConversations() 返回 { data: [...], raw: res }，需要提取 data 字段
            const convs = result.data || (Array.isArray(result) ? result : []);
            this._im.conversations = Array.isArray(convs) ? convs : [];
            if (this._im.conversations.length === 0) {
                listEl.innerHTML = '<div class="empty-state" style="padding:20px"><div class="empty-text">暂无会话</div></div>';
                return;
            }
            let html = '';
            this._im.conversations.forEach(c => {
                const isActive = this._im.currentChat && 
                    ((c.type === 'user' && this._im.currentChat.type === 'user' && this._im.currentChat.id === c.id) ||
                     (c.type === 'group' && this._im.currentChat.type === 'group' && this._im.currentChat.id === c.id));
                const lastMsg = c.last_message || {};
                const time = lastMsg.created_at ? App._formatTime(lastMsg.created_at, 'short') : '';
                const name = c.title || `用户${c.id}`;
                const avatarChar = (name || '?')[0].toUpperCase();
                const unreadBadge = c.unread_count > 0 ? `<span class="im-badge-unread">${c.unread_count > 99 ? '99+' : c.unread_count}</span>` : '';
                const receiverType = c.type || 'user';
                const receiverId = c.id;
                html += `
                    <div class="im-list-item ${isActive ? 'active' : ''}" onclick="App.selectIMChat('${receiverType}', ${receiverId}, '${API._escapeHtml(name)}')">
                        <div class="im-list-item-avatar">${avatarChar}</div>
                        <div class="im-list-item-body">
                            <div class="im-list-item-name">${API._escapeHtml(name)}</div>
                            <div class="im-list-item-preview">${API._escapeHtml((lastMsg.content || '').slice(0, 40))}</div>
                        </div>
                        <div style="display:flex;flex-direction:column;align-items:flex-end;gap:4px">
                            <div class="im-list-item-time">${time}</div>
                            ${unreadBadge}
                        </div>
                    </div>`;
            });
            listEl.innerHTML = html;
        } catch (err) {
            listEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 加载好友列表 */
    async loadIMFriends() {
        const listEl = document.getElementById('im-friends-list');
        if (!listEl) return;
        try {
            const friends = await API.getFriends();
            this._im.friends = Array.isArray(friends) ? friends : [];
            if (this._im.friends.length === 0) {
                listEl.innerHTML = '<div class="empty-state" style="padding:20px"><div class="empty-text">还没有好友，点击"添加"搜索用户</div></div>';
                return;
            }
            let html = '';
            this._im.friends.forEach(f => {
                const userId = f.id || f.user_id;
                const name = f.remark || f.nickname || f.username || `用户${userId}`;
                const avatarChar = (name || '?')[0].toUpperCase();
                html += `
                    <div class="im-list-item" onclick="App.selectIMChat('user', ${userId}, '${API._escapeHtml(name)}')">
                        <div class="im-list-item-avatar">${avatarChar}</div>
                        <div class="im-list-item-body">
                            <div class="im-list-item-name">${API._escapeHtml(name)}</div>
                            <div class="im-list-item-preview">${f.remark ? '备注: ' + API._escapeHtml(f.remark) : API._escapeHtml(f.username || '')}</div>
                        </div>
                        <div class="im-list-item-actions">
                            <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();App.showFriendRemarkForm(${f.id}, '${API._escapeHtml(name)}')" title="备注">✏️</button>
                            <button class="btn btn-xs btn-ghost" onclick="event.stopPropagation();App.deleteIMFriend(${f.id})" title="删除好友">🗑️</button>
                        </div>
                    </div>`;
            });
            listEl.innerHTML = html;
        } catch (err) {
            listEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 加载群组列表 */
    async loadIMGroups() {
        const listEl = document.getElementById('im-groups-list');
        if (!listEl) return;
        try {
            const groups = await API.getGroups();
            this._im.groups = Array.isArray(groups) ? groups : [];
            if (this._im.groups.length === 0) {
                listEl.innerHTML = '<div class="empty-state" style="padding:20px"><div class="empty-text">还没有群组，点击"建群"创建</div></div>';
                return;
            }
            let html = '';
            this._im.groups.forEach(g => {
                const name = g.name || `群${g.id}`;
                const avatarChar = (name || 'G')[0].toUpperCase();
                html += `
                    <div class="im-list-item" onclick="App.selectIMChat('group', ${g.id}, '${API._escapeHtml(name)}')">
                        <div class="im-list-item-avatar" style="background:var(--secondary)">${avatarChar}</div>
                        <div class="im-list-item-body">
                            <div class="im-list-item-name">${API._escapeHtml(name)}</div>
                            <div class="im-list-item-preview">👥 ${g.member_count || 0} 人</div>
                        </div>
                    </div>`;
            });
            listEl.innerHTML = html;
        } catch (err) {
            listEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 加载好友请求 */
    async loadIMRequests() {
        this.loadIMReceivedRequests();
        this.loadIMSentRequests();
    },

    async loadIMReceivedRequests() {
        const listEl = document.getElementById('im-received-requests');
        if (!listEl) return;
        try {
            const requests = await API.getFriendRequests('received');
            const items = Array.isArray(requests) ? requests : [];
            if (items.length === 0) {
                listEl.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-text">暂无收到的请求</div></div>';
                return;
            }
            let html = '';
            items.forEach(r => {
                const name = r.sender_username || `用户${r.sender_id}`;
                const statusMap = { 'pending': '⏳ 待处理', 'accepted': '✅ 已接受', 'rejected': '❌ 已拒绝' };
                html += `
                    <div class="im-request-item">
                        <div class="im-request-item-avatar">${(name[0] || '?').toUpperCase()}</div>
                        <div class="im-request-item-body">
                            <div class="im-request-item-name">${API._escapeHtml(name)}</div>
                            <div class="im-request-item-msg">${API._escapeHtml(r.message || '你好，加个好友')}</div>
                        </div>
                        <div class="im-request-item-actions">
                            ${r.status === 'pending' ? `
                                <button class="btn btn-xs btn-success" onclick="App.handleFriendRequest(${r.id}, 'accept')">接受</button>
                                <button class="btn btn-xs btn-danger" onclick="App.handleFriendRequest(${r.id}, 'reject')">拒绝</button>
                            ` : `<span class="text-muted">${statusMap[r.status] || r.status}</span>`}
                        </div>
                    </div>`;
            });
            listEl.innerHTML = html;
        } catch (err) {
            listEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    async loadIMSentRequests() {
        const listEl = document.getElementById('im-sent-requests');
        if (!listEl) return;
        try {
            const requests = await API.getFriendRequests('sent');
            const items = Array.isArray(requests) ? requests : [];
            if (items.length === 0) {
                listEl.innerHTML = '<div class="empty-state" style="padding:16px"><div class="empty-text">暂无已发送的请求</div></div>';
                return;
            }
            let html = '';
            items.forEach(r => {
                const name = r.receiver_username || `用户${r.receiver_id}`;
                const statusMap = { 'pending': '⏳ 等待对方接受', 'accepted': '✅ 已接受', 'rejected': '❌ 已拒绝' };
                html += `
                    <div class="im-request-item">
                        <div class="im-request-item-avatar">${(name[0] || '?').toUpperCase()}</div>
                        <div class="im-request-item-body">
                            <div class="im-request-item-name">${API._escapeHtml(name)}</div>
                            <div class="im-request-item-msg">${statusMap[r.status] || r.status}</div>
                        </div>
                    </div>`;
            });
            listEl.innerHTML = html;
        } catch (err) {
            listEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 处理好友请求 */
    async handleFriendRequest(requestId, action) {
        try {
            await API.handleFriendRequest(requestId, action);
            API.toast('success', action === 'accept' ? '已接受好友请求' : '已拒绝好友请求');
            this.loadIMRequests();
            this.loadIMFriends();
            this.loadIMConversations();
        } catch (err) {
            API.toast('error', '操作失败', err.message);
        }
    },

    /** 搜索 IM 联系人 */
    async searchIMContacts(keyword) {
        const convs = this._im.conversations || [];
        const listEl = document.getElementById('im-conversation-list');
        if (!listEl) return;
        if (!keyword) {
            this.loadIMConversations();
            return;
        }
        const filtered = convs.filter(c => {
            const name = c.title || '';
            return name.includes(keyword);
        });
        if (filtered.length === 0) {
            listEl.innerHTML = '<div class="empty-state" style="padding:20px"><div class="empty-text">未找到匹配的会话</div></div>';
            return;
        }
        let html = '';
        filtered.forEach(c => {
            const name = c.title || `用户${c.id}`;
            const avatarChar = (name || '?')[0].toUpperCase();
            const receiverType = c.type || 'user';
            const receiverId = c.id;
            html += `
                <div class="im-list-item" onclick="App.selectIMChat('${receiverType}', ${receiverId}, '${API._escapeHtml(name)}')">
                    <div class="im-list-item-avatar">${avatarChar}</div>
                    <div class="im-list-item-body">
                        <div class="im-list-item-name">${API._escapeHtml(name)}</div>
                    </div>
                </div>`;
        });
        listEl.innerHTML = html;
    },

    /** 选择聊天对象 */
    async selectIMChat(type, id, name) {
        this._im.currentChat = { type, id, name };
        this._im.messages = [];

        document.querySelectorAll('#im-conversation-list .im-list-item').forEach(el => el.classList.remove('active'));
        document.querySelectorAll('#im-friends-list .im-list-item').forEach(el => el.classList.remove('active'));

        document.getElementById('im-chat-title').textContent = name;
        const subtitle = type === 'user' ? '好友 · 在线' : '群组';
        document.getElementById('im-chat-subtitle').textContent = subtitle;
        document.getElementById('im-chat-header-actions').style.display = 'flex';
        document.getElementById('im-input-area').style.display = 'block';

        await this.loadIMMessagesByChat(type, id, name);

        try {
            let lastReadMsgId = 0;
            if (this._im.messages.length > 0) {
                lastReadMsgId = this._im.messages[this._im.messages.length - 1].id;
            }
            await API.markMessagesRead(type, id, lastReadMsgId);
        } catch {}

        const inputEl = document.getElementById('im-input');
        if (inputEl) { inputEl.disabled = false; inputEl.focus(); }

        this.switchIMTab('chat');
    },

    /** 显示群公告横幅 */
    async _showGroupAnnouncementBanner(groupId) {
        const msgEl = document.getElementById('im-messages');
        if (!msgEl) return;
        // 移除旧的横幅
        const oldBanner = msgEl.querySelector('.im-announcement-banner');
        if (oldBanner) oldBanner.remove();

        try {
            // 获取群详情拿到公告
            const group = await API.getGroupDetail(groupId);
            if (!group || !group.announcement) return;

            // 检查用户是否已读过此公告（按 groupId 存储）
            const dismissedKey = `ctos_announcement_dismissed_${API.currentUser?.id || 0}`;
            let dismissed = {};
            try { dismissed = JSON.parse(localStorage.getItem(dismissedKey) || '{}'); } catch {}
            const dismissedAnnouncements = dismissed[String(groupId)] || [];
            if (dismissedAnnouncements.includes(group.announcement)) return;

            // 在消息列表顶部插入公告横幅
            const banner = document.createElement('div');
            banner.className = 'im-announcement-banner';
            banner.innerHTML = `
                <span class="im-announcement-icon">📢</span>
                <div class="im-announcement-content">
                    <div class="im-announcement-title">群公告</div>
                    <div class="im-announcement-text">${API._escapeHtml(group.announcement)}</div>
                </div>
                <span class="im-announcement-dismiss">点击已读 ✕</span>
            `;
            // 点击横幅关闭并标记已读
            banner.addEventListener('click', () => {
                banner.classList.add('dismissed');
                dismissed[String(groupId)] = dismissed[String(groupId)] || [];
                dismissed[String(groupId)].push(group.announcement);
                localStorage.setItem(dismissedKey, JSON.stringify(dismissed));
                setTimeout(() => banner.remove(), 300);
            });
            // 插入到消息列表顶部
            msgEl.insertBefore(banner, msgEl.firstChild);
        } catch {}
    },

    /** 按聊天对象加载消息 */
    async loadIMMessagesByChat(type, id, name) {
        const msgEl = document.getElementById('im-messages');
        if (!msgEl) return;
        msgEl.innerHTML = '<div class="loading-spinner" style="padding:40px;text-align:center"><span class="mini-spinner"></span> 加载消息...</div>';

        try {
            const data = await API.getMessages(type, id, null, 100);
            const items = data.items || data || [];
            let messages = Array.isArray(items) ? items : [];
            // 【防御性过滤】私聊只显示 receiver_type="user" 的消息，群聊只显示 receiver_type="group" 的消息
            // 防止后端查询遗漏过滤条件导致群聊/私聊消息互相混淆
            if (type === 'user') {
                messages = messages.filter(m => m.receiver_type === 'user');
            } else if (type === 'group') {
                messages = messages.filter(m => m.receiver_type === 'group');
            }
            this._im.messages = messages;

            if (messages.length === 0) {
                msgEl.innerHTML = `<div class="im-welcome" style="padding:40px">
                    <div class="im-welcome-icon" style="font-size:36px">💬</div>
                    <p>开始和 ${API._escapeHtml(name)} 聊天吧</p>
                </div>`;
                return;
            }

            msgEl.innerHTML = '';
            let lastDate = '';
            let latestWeatherEffect = null;
            messages.forEach(m => {
                const msgDate = m.created_at ? App._formatTime(m.created_at, 'date') : '';
                if (msgDate && msgDate !== lastDate) {
                    msgEl.innerHTML += `<div class="im-date-divider"><span>${msgDate}</span></div>`;
                    lastDate = msgDate;
                }
                this._renderIMMessage(m, type);
                // 记录最新一条天气消息的效果，用于初始加载时展示
                if (m.weather_effect) {
                    latestWeatherEffect = m.weather_effect;
                }
            });

            // 初始加载完成后，如果有天气卡片消息，展示天气效果
            if (latestWeatherEffect) {
                setTimeout(() => this.showWeatherEffect(latestWeatherEffect), 200);
            }
            
            // 加载群公告横幅（仅群聊）
            if (type === 'group') {
                this._showGroupAnnouncementBanner(id);
            }
            
            this._scrollIMToBottom();
        } catch (err) {
            msgEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /**
     * 格式化时间：后端数据库存储为 UTC+0 时间（SQLite CURRENT_TIMESTAMP 返回 UTC），
     * 但返回的 ISO 字符串不含 Z/时区标记（如 "2026-05-28T05:29:42"），
     * JS new Date() 会将无时区标记的字符串当作本地时间解析，导致时间显示错误。
     * 
     * 修复：添加 Z 后缀 → new Date 正确识别为 UTC → toLocaleString 转换为本地时区显示
     */
    _formatTime(isoStr, format = 'full') {
        if (!isoStr) return '';
        try {
            // 如果没带 Z 后缀则添加（后端返回的 naive ISO 时间实际是 UTC）
            const d = new Date(isoStr.endsWith('Z') ? isoStr : isoStr + 'Z');
            if (isNaN(d.getTime())) return isoStr;
            if (format === 'date') return d.toLocaleDateString('zh-CN');
            if (format === 'time') return d.toLocaleString('zh-CN', { hour: '2-digit', minute: '2-digit' });
            if (format === 'short') return d.toLocaleString('zh-CN', { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' });
            return d.toLocaleString('zh-CN');
        } catch {
            return isoStr;
        }
    },

    /** 解析 IM 消息时间（复用 _formatTime，仅显示 HH:mm） */
    _parseIMTime(createdAt) {
        return this._formatTime(createdAt, 'time');
    },

    /** 渲染单条 IM 消息 */
    _renderIMMessage(msg, chatType) {
        const msgEl = document.getElementById('im-messages');
        if (!msgEl) return;

        const isSent = msg.sender_id === API.currentUser?.id;
        const isSystem = msg.type === 'system';
        const time = this._parseIMTime(msg.created_at);

        const welcome = msgEl.querySelector('.im-welcome');
        if (welcome) msgEl.innerHTML = '';

        const div = document.createElement('div');
        div.className = `im-msg ${isSystem ? 'system' : (isSent ? 'sent' : 'received')}`;

        if (isSystem) {
            div.innerHTML = `<div class="im-msg-body"><div class="im-msg-bubble">${API._escapeHtml(msg.content || '')}</div></div>`;
        } else {
            const avatarChar = (msg.sender_username || (isSent ? '我' : '?'));
            const sendName = isSent ? '' : (msg.sender_username || '');
            const tokenSuffix = API.token ? `?token=${encodeURIComponent(API.token)}` : '';

            let contentHtml = '';
            if (msg.type === 'text') {
                contentHtml = API._escapeHtml(msg.content || '');
            } else if (msg.type === 'image') {
                // 图片：用 file_id + md5_hash 构建下载URL（MD5嵌入URL保证内容变了URL就变，缓存自动失效）
                const fileId = msg.file_id;
                const md5Hash = msg.file_info?.md5_hash || '';
                const imgSrc = (fileId && md5Hash) ? `/api/im/files/${fileId}/download/${md5Hash}${tokenSuffix}` : (msg.content || '');
                contentHtml = `<div class="im-msg-image"><img src="${imgSrc}" alt="图片" onclick="window.open(this.src)" style="max-width:240px;max-height:320px;border-radius:8px;cursor:pointer"/></div>`;
                // 检测天气效果并展示（延迟等待 DOM 渲染完成）
                if (msg.weather_effect) {
                    setTimeout(() => this.showWeatherEffect(msg.weather_effect), 100);
                }
            } else if (msg.type === 'file') {
                const fileId = msg.file_id;
                const fileName = msg.file_info?.file_name || msg.content || '文件';
                contentHtml = `<div class="im-msg-file">
                    <span class="im-msg-file-icon">📎</span>
                    <div class="im-msg-file-info">
                        <span class="im-msg-file-name">${API._escapeHtml(fileName)}</span>
                        ${fileId ? `<a class="im-msg-file-download" href="/api/im/files/${fileId}/download${tokenSuffix}" target="_blank" title="下载文件" style="display:block;font-size:12px;margin-top:4px;color:var(--primary)">⬇️ 下载</a>` : ''}
                    </div>
                </div>`;
            } else if (msg.type === 'emoji') {
                contentHtml = `<span style="font-size:28px">${API._escapeHtml(msg.content || '😊')}</span>`;
            } else {
                contentHtml = API._escapeHtml(msg.content || '');
            }

            div.innerHTML = `
                <div class="im-msg-avatar">${isSent ? '我' : (avatarChar[0] || '?').toUpperCase()}</div>
                <div class="im-msg-body">
                    ${chatType === 'group' && !isSent ? `<div class="im-msg-sender">${API._escapeHtml(sendName)}</div>` : ''}
                    <div class="im-msg-bubble">${contentHtml}</div>
                    <div class="im-msg-time">${time}</div>
                </div>`;
        }
        msgEl.appendChild(div);
    },

    /** IM 消息滚动到底部 */
    _scrollIMToBottom() {
        const msgEl = document.getElementById('im-messages');
        if (msgEl) {
            setTimeout(() => { msgEl.scrollTop = msgEl.scrollHeight; }, 50);
        }
    },

    /** 提取@提及的用户ID列表 */
    _extractMentions(content) {
        const members = this._im.atMenuMembers || [];
        if (members.length === 0) return [];

        const mentionIds = [];
        const mentionRegex = /@([^\s@]+)/g;
        let match;
        while ((match = mentionRegex.exec(content)) !== null) {
            const name = match[1].trim();
            if (!name) continue;
            for (const member of members) {
                if (member.display_name === name || member.username === name) {
                    if (!mentionIds.includes(member.user_id)) {
                        mentionIds.push(member.user_id);
                    }
                    break;
                }
            }
        }
        return mentionIds;
    },

    /** 输入框@检测 */
    _onIMInputWithAt(el) {
        // 自动调整高度
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 100) + 'px';

        // @检测
        const chat = this._im.currentChat;
        if (!chat || chat.type !== 'group') {
            this._hideAtMenu();
            return;
        }

        const text = el.value;
        const cursorPos = el.selectionStart;
        const textBeforeCursor = text.substring(0, cursorPos);
        const atMatch = textBeforeCursor.match(/@([^\s@]*)$/);

        if (!atMatch) {
            this._hideAtMenu();
            return;
        }

        // 刚输入@时加载群成员
        if (!this._im.atMenuActive) {
            this._loadAtMenuMembers(chat.id);
        }

        const keyword = atMatch[1];
        this._im.atMenuActive = true;
        this._im.atMenuKeyword = keyword || '';
        this._im.atMenuFiltered = (this._im.atMenuMembers || []).filter(m => {
            return (m.display_name || '').toLowerCase().includes(this._im.atMenuKeyword.toLowerCase());
        });

        if (this._im.atMenuFiltered.length === 0) {
            this._hideAtMenu();
            return;
        }

        this._im.atSelectedIndex = 0;
        this._renderAtMenu();
        this._showAtMenu();
    },

    /** @提及菜单键盘导航 */
    _onIMAtMenuKeydown(el, e) {
        if (!this._im.atMenuActive) return true;
        
        const filtered = this._im.atMenuFiltered || [];
        if (filtered.length === 0) {
            this._hideAtMenu();
            return true;
        }

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this._im.atSelectedIndex = (this._im.atSelectedIndex + 1) % filtered.length;
            this._renderAtMenu();
            this._scrollAtMenuItemIntoView();
            return false;
        }

        if (e.key === 'ArrowUp') {
            e.preventDefault();
            this._im.atSelectedIndex = (this._im.atSelectedIndex - 1 + filtered.length) % filtered.length;
            this._renderAtMenu();
            this._scrollAtMenuItemIntoView();
            return false;
        }

        if (e.key === 'Enter' && this._im.atMenuActive) {
            e.preventDefault();
            const selected = filtered[this._im.atSelectedIndex];
            if (selected) {
                this._selectAtMember(selected);
            }
            return false;
        }

        if (e.key === 'Escape' && this._im.atMenuActive) {
            e.preventDefault();
            this._hideAtMenu();
            return false;
        }

        return true;
    },

    /** 滚动@菜单选中项到可视区域 */
    _scrollAtMenuItemIntoView() {
        const listEl = document.getElementById('im-at-menu-list');
        if (!listEl) return;
        const selected = listEl.querySelector('.im-at-item.active');
        if (selected) {
            selected.scrollIntoView({ block: 'nearest', behavior: 'smooth' });
        }
    },

    /** 加载群成员到缓存 */
    async _loadAtMenuMembers(groupId) {
        if (this._im.atCurrentGroupId === groupId && (this._im.atMenuMembers || []).length > 0) return;
        try {
            const members = await API.getGroupMembers(groupId);
            this._im.atMenuMembers = Array.isArray(members) ? members : [];
            this._im.atCurrentGroupId = groupId;
        } catch {
            this._im.atMenuMembers = [];
        }
    },

    /** 显示@菜单 */
    _showAtMenu() {
        const menu = document.getElementById('im-at-menu');
        if (menu) menu.style.display = 'block';
    },

    /** 隐藏@菜单 */
    _hideAtMenu() {
        this._im.atMenuActive = false;
        this._im.atMenuKeyword = '';
        this._im.atMenuFiltered = [];
        this._im.atSelectedIndex = 0;
        const menu = document.getElementById('im-at-menu');
        if (menu) menu.style.display = 'none';
    },

    /** 渲染@菜单列表 */
    _renderAtMenu() {
        const listEl = document.getElementById('im-at-menu-list');
        if (!listEl) return;
        let html = '';
        (this._im.atMenuFiltered || []).forEach((member, idx) => {
            const active = idx === this._im.atSelectedIndex ? 'active' : '';
            const icon = member.worker_icon || (member.is_worker ? '🤖' : '👤');
            const tag = member.is_worker ? '<span class="im-at-tag">数字员工</span>' : '';
            html += `<div class="im-at-item ${active}" data-index="${idx}">
                <span class="im-at-icon">${icon}</span>
                <span class="im-at-name">${API._escapeHtml(member.display_name)}</span>
                ${tag}
            </div>`;
        });
        listEl.innerHTML = html;
    },

    /** 选择@成员 */
    _selectAtMember(member) {
        const inputEl = document.getElementById('im-input');
        if (!inputEl) return;

        const text = inputEl.value;
        const cursorPos = inputEl.selectionStart;
        const textBeforeCursor = text.substring(0, cursorPos);
        const atMatch = textBeforeCursor.match(/@([^\s@]*)$/);
        if (!atMatch) { this._hideAtMenu(); return; }

        const atStartPos = atMatch.index;
        const restText = text.substring(cursorPos);
        const mentionText = `@${member.display_name} `;
        inputEl.value = text.substring(0, atStartPos) + mentionText + restText;
        const newPos = atStartPos + mentionText.length;
        inputEl.setSelectionRange(newPos, newPos);
        inputEl.focus();
        this._hideAtMenu();
        inputEl.style.height = 'auto';
        inputEl.style.height = Math.min(inputEl.scrollHeight, 100) + 'px';
    },

    /** 发送 IM 消息 */
    async sendIMMessage() {
        const chat = this._im.currentChat;
        if (!chat) { API.toast('warning', '提示', '请先选择一个好友或群组'); return; }

        const inputEl = document.getElementById('im-input');
        const content = inputEl?.value?.trim();
        if (!content) { API.toast('warning', '提示', '请输入消息内容'); return; }

        // 提取@提及
        const mentions = this._extractMentions(content);

        inputEl.value = '';
        inputEl.style.height = 'auto';
        this._hideAtMenu();

        // 先渲染临时消息（无闪烁）
        const tempMsg = {
            sender_id: API.currentUser?.id || 0,
            sender_username: API.currentUser?.username || '我',
            content: content,
            type: 'text',
            created_at: new Date().toISOString()
        };
        this._renderIMMessage(tempMsg, chat.type);
        this._scrollIMToBottom();

        try {
            const res = await API.sendMessage(chat.type, chat.id, content, 'text', null, mentions);
            // 用服务器返回的确认消息替换最后一条临时消息的 id 和时间
            const msgEl = document.getElementById('im-messages');
            if (msgEl) {
                const lastMsg = msgEl.querySelector('.im-msg.sent:last-child');
                if (lastMsg) {
                    const timeEl = lastMsg.querySelector('.im-msg-time');
                    if (timeEl && res.created_at) {
                        timeEl.textContent = this._parseIMTime(res.created_at);
                    }
                    lastMsg.dataset.msgId = res.id || '';
                }
            }
            // 更新内存中的消息列表
            if (res) {
                this._im.messages.push({
                    id: res.id,
                    sender_id: API.currentUser?.id,
                    sender_username: API.currentUser?.username,
                    content: content,
                    type: 'text',
                    receiver_type: chat.type,
                    receiver_id: chat.id,
                    created_at: res.created_at
                });
            }
            this.loadIMConversations();
        } catch (err) {
            API.toast('error', '发送失败', err.message);
        }
    },

    /** 输入框调整 */
    onIMInput(el) {
        el.style.height = 'auto';
        el.style.height = Math.min(el.scrollHeight, 100) + 'px';
    },

    /** 打开表情选择器 */
    openEmojiPicker() {
        const picker = document.getElementById('im-emoji-picker');
        if (!picker) return;
        const isVisible = picker.style.display !== 'none';
        picker.style.display = isVisible ? 'none' : 'block';
        if (!isVisible) {
            const grid = document.getElementById('im-emoji-grid');
            if (grid && grid.children.length === 0) {
                const emojis = ['😊','😂','🤣','❤️','😍','🥰','😘','😗','😙','😚','😋','😛','😜','🤪','😝','🤑','🤗','🤭','🤔','🤐','😏','😒','😞','😔','😟','😕','🙁','☹️','😣','😖','😫','😩','😤','😠','😡','🤬','😈','👿','💀','☠️','💩','🤡','👹','👺','👻','👽','👾','🤖','🎃','😺','😸','😹','😻','😼','😽','🙀','😿','😾','👍','👎','👊','✊','🤛','🤜','👏','🙌','👐','🤲','🤝','🙏','✌️','🤞','🤟','🤘','👌','💪','🖕','✋','🤚','🖐','👋','🤙','💅','👀','👃','👂','👄','💋','👶','👧','🧒','👦','👩','🧑','👨','👩‍🦱','👨‍🦱','👩‍🦰','👨‍🦰','👴','👵','🧓','🙋','💁','🙅','🙆','💆','💇','🚶','🏃','💃','🕺','👯','🧖','🧘','🛀','🏄','🏊','🤽','🚣','🏋️','🚴','🤸','🤼','🤹','🎱','🎮','🎯','🎲','🎰','🎳','🎭','🎨','🎬','🎤','🎧','🎼','🎵','🎶','🎹','🥁','🎷','🎺','🎸','🎻','🎲','🧩','♟️','🎯','🎳','🎪','🎨','🌈','☀️','⭐','🌙','🌤️','⛅','🌧️','⛈️','❄️','🔥','💥','✨','🎉','🎊','🎁','🎈','🎄','🎃','🎆','🎇','🎀','🎗️','🏆','🏅','🥇','🥈','🥉','⚽','⚾','🏀','🏐','🏈','🎾','🏉','🎱','🏓','🏸','🥊','🥋','⛸️','🛷','🎿','⛷️','🏂','🏋️','🤼','🤸','⛹️','🤺','🤾','🏌️','🏇','🧘','🏄','🏊','🤽','🚣','🏆','🥇','🥈','🥉','🎽','🏅','🎖️','🥇'];
                emojis.forEach(e => {
                    const span = document.createElement('span');
                    span.className = 'im-emoji-item';
                    span.textContent = e;
                    span.onclick = () => { this._insertEmoji(e); };
                    grid.appendChild(span);
                });
            }
        }
    },

    /** 插入 emoji */
    _insertEmoji(emoji) {
        const inputEl = document.getElementById('im-input');
        if (!inputEl) return;
        const start = inputEl.selectionStart;
        const end = inputEl.selectionEnd;
        const text = inputEl.value;
        inputEl.value = text.substring(0, start) + emoji + text.substring(end);
        inputEl.focus();
        inputEl.selectionStart = inputEl.selectionEnd = start + emoji.length;
        document.getElementById('im-emoji-picker').style.display = 'none';
    },

    /** 打开文件上传 */
    openFileUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.onchange = async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            try {
                API.toast('info', '上传中', '文件上传中...');
                const result = await API.uploadFile(file);
                const chat = this._im.currentChat;
                if (chat && result?.id) {
                    await API.sendMessage(chat.type, chat.id, result.file_name || file.name, 'file', result.id);
                    this.loadIMMessagesByChat(chat.type, chat.id, chat.name);
                }
                API.toast('success', '上传成功', `${file.name} 已发送`);
            } catch (err) {
                API.toast('error', '上传失败', err.message);
            }
        };
        input.click();
    },

    /** 打开图片上传 */
    openImageUpload() {
        const input = document.createElement('input');
        input.type = 'file';
        input.accept = 'image/*';
        input.onchange = async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            try {
                API.toast('info', '上传中', '图片上传中...');
                const result = await API.uploadFile(file);
                const chat = this._im.currentChat;
                if (chat && result?.id) {
                    await API.sendMessage(chat.type, chat.id, result.file_name || file.name, 'image', result.id);
                    this.loadIMMessagesByChat(chat.type, chat.id, chat.name);
                }
                API.toast('success', '上传成功', '图片已发送');
            } catch (err) {
                API.toast('error', '上传失败', err.message);
            }
        };
        input.click();
    },

    /** 添加好友弹窗 */
    showAddFriendForm() {
        API.showModal('🔍 搜索用户添加好友', `
            <div class="modal-form-group">
                <span class="modal-form-label">用户名</span>
                <input class="modal-form-input" id="friend-search-keyword" placeholder="输入要查找的用户名" oninput="App.searchForAddFriend(this.value)" />
            </div>
            <div id="friend-search-results" style="margin-top:8px">
                <div class="text-muted" style="text-align:center;padding:16px;font-size:13px">输入用户名开始搜索</div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">关闭</button>`);
    },

    /** 搜索待添加的好友 */
    async searchForAddFriend(keyword) {
        const resultEl = document.getElementById('friend-search-results');
        if (!resultEl) return;
        if (!keyword || keyword.trim().length < 1) {
            resultEl.innerHTML = '<div class="text-muted" style="text-align:center;padding:16px;font-size:13px">输入用户名开始搜索</div>';
            return;
        }
        try {
            const users = await API.searchUsers(keyword.trim());
            if (!Array.isArray(users) || users.length === 0) {
                resultEl.innerHTML = '<div class="empty-state" style="padding:12px"><div class="empty-text">未找到匹配的用户</div></div>';
                return;
            }
            let html = '';
            users.forEach(u => {
                html += `
                    <div class="cleaning-data-card" style="margin-bottom:6px">
                        <div style="display:flex;align-items:center;justify-content:space-between">
                            <div>
                                <strong>${API._escapeHtml(u.nickname || u.username)}</strong>
                                <span class="text-muted" style="font-size:12px;margin-left:8px">@${API._escapeHtml(u.username)}</span>
                            </div>
                            <button class="btn btn-xs btn-success" onclick="App.sendAddFriendRequest(${u.id}, '${API._escapeHtml(u.username || '')}')">➕ 加好友</button>
                        </div>
                    </div>`;
            });
            resultEl.innerHTML = html;
        } catch (err) {
            resultEl.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 发送好友申请 */
    async sendAddFriendRequest(userId, username) {
        const message = prompt(`给 ${username} 发送好友申请：`, '你好，加个好友');
        if (message === null) return;
        try {
            await API.sendFriendRequest(userId, message);
            API.toast('success', '已发送', `好友申请已发送给 ${username}`);
            API.closeModal();
            this.loadIMRequests();
        } catch (err) {
            API.toast('error', '发送失败', err.message);
        }
    },

    /** 创建群组弹窗 */
    showCreateGroupForm() {
        const friends = this._im.friends || [];
        const friendOptions = friends.length > 0
            ? friends.map(f => {
                const userId = f.id || f.user_id;
                const name = f.remark || f.nickname || f.username || `用户${userId}`;
                return `<label style="display:flex;align-items:center;gap:8px;padding:4px 0">
                    <input type="checkbox" class="group-member-cb" value="${userId}" />
                    <span>${API._escapeHtml(name)}</span>
                </label>`;
              }).join('')
            : '<div class="text-muted" style="padding:8px;font-size:12px">暂无好友可选</div>';

        API.showModal('👥 创建群组', `
            <div class="modal-form-group">
                <span class="modal-form-label">群组名称 *</span>
                <input class="modal-form-input" id="group-create-name" placeholder="输入群名称" />
            </div>
            <div class="modal-form-group">
                <span class="modal-form-label">选择群成员</span>
                <div style="max-height:200px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius-xs);padding:8px 12px">
                    ${friendOptions}
                </div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.createGroup()">💾 创建</button>`);
    },

    /** 创建群组 */
    async createGroup() {
        const name = document.getElementById('group-create-name')?.value?.trim();
        if (!name) { API.toast('warning', '提示', '请输入群组名称'); return; }

        const cbs = document.querySelectorAll('.group-member-cb:checked');
        const memberIds = Array.from(cbs).map(cb => parseInt(cb.value)).filter(id => !isNaN(id));

        try {
            await API.createGroup(name, memberIds);
            API.toast('success', '创建成功', `群组 "${name}" 已创建`);
            API.closeModal();
            this.loadIMGroups();
            this.loadIMConversations();
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    // ========== 天气特效展示 ==========

    _weatherEffectTimer: null,

    /** 在 IM 聊天区域展示天气特效
     * @param {string} effect - sunny/cloudy/rainy/snowy/stormy/foggy
     */
    showWeatherEffect(effect) {
        // 清除旧的定时器
        if (this._weatherEffectTimer) {
            clearTimeout(this._weatherEffectTimer);
            this._weatherEffectTimer = null;
        }

        // 移除旧的整页效果层
        const oldOverlay = document.body.querySelector('.weather-effect-overlay');
        if (oldOverlay) oldOverlay.remove();

        // 创建整页效果覆盖层
        const overlay = document.createElement('div');
        overlay.className = 'weather-effect-overlay';
        overlay.innerHTML = '';

        if (effect === 'sunny') {
            overlay.classList.add('weather-effect-sunny');
            overlay.innerHTML = '<div class="weather-ray"></div>';
        } else if (effect === 'cloudy') {
            overlay.classList.add('weather-effect-cloudy');
            overlay.innerHTML = '<div class="weather-cloud"></div><div class="weather-cloud"></div><div class="weather-cloud"></div>';
        } else if (effect === 'rainy') {
            overlay.classList.add('weather-effect-rainy');
            for (let i = 0; i < 80; i++) {
                const drop = document.createElement('div');
                drop.className = 'weather-rain-drop';
                drop.style.left = (Math.random() * 100) + '%';
                drop.style.top = (Math.random() * 100) + '%';
                drop.style.animationDelay = (Math.random() * 0.6) + 's';
                overlay.appendChild(drop);
            }
        } else if (effect === 'snowy') {
            for (let i = 0; i < 60; i++) {
                const flake = document.createElement('div');
                flake.className = 'weather-snow-flake';
                flake.style.left = (Math.random() * 100) + '%';
                flake.style.top = (Math.random() * 100) + '%';
                flake.style.animationDelay = (Math.random() * 5) + 's';
                flake.style.width = (4 + Math.random() * 6) + 'px';
                flake.style.height = flake.style.width;
                overlay.appendChild(flake);
            }
        } else if (effect === 'stormy') {
            overlay.classList.add('weather-effect-stormy');
            overlay.innerHTML = '<div class="weather-lightning"></div><div class="weather-lightning" style="top:25%;right:55%;animation-delay:1.5s"></div>';
            for (let i = 0; i < 100; i++) {
                const drop = document.createElement('div');
                drop.className = 'weather-rain-drop';
                drop.style.left = (Math.random() * 100) + '%';
                drop.style.top = (Math.random() * 100) + '%';
                drop.style.animationDelay = (Math.random() * 0.6) + 's';
                overlay.appendChild(drop);
            }
        } else if (effect === 'foggy') {
            overlay.classList.add('weather-effect-foggy');
            overlay.innerHTML = '<div class="weather-fog-layer"></div><div class="weather-fog-layer"></div><div class="weather-fog-layer"></div>';
        }

        // 挂载到 body 实现整页覆盖（极高层级 z-index:9999，pointer-events:none 不影响交互）
        document.body.appendChild(overlay);

        // 触发 active 动画（下一帧）
        requestAnimationFrame(() => {
            overlay.classList.add('active');
        });

        // 8秒后淡出消失
        this._weatherEffectTimer = setTimeout(() => {
            overlay.classList.add('fade-out');
            setTimeout(() => {
                if (overlay.parentNode) overlay.remove();
            }, 2000);
            this._weatherEffectTimer = null;
        }, 8000);
    },

    /** 删除好友 */
    async deleteIMFriend(friendId) {
        if (!confirm('确定要删除这个好友吗？')) return;
        try {
            await API.deleteFriend(friendId);
            API.toast('success', '已删除', '好友已删除');
            this.loadIMFriends();
            this.loadIMConversations();
        } catch (err) {
            API.toast('error', '删除失败', err.message);
        }
    },

    /** 修改好友备注 */
    showFriendRemarkForm(friendId, currentName) {
        const newRemark = prompt('请输入新备注：', currentName || '');
        if (newRemark === null) return;
        try {
            API.setFriendRemark(friendId, newRemark.trim());
            API.toast('success', '备注已更新');
            this.loadIMFriends();
        } catch (err) {
            API.toast('error', '更新失败', err.message);
        }
    },

    /** 聊天详情 */
    async showChatDetail() {
        const chat = this._im.currentChat;
        if (!chat) return;
        const detailEl = document.getElementById('im-chat-detail');
        const bodyEl = document.getElementById('im-chat-detail-body');
        if (!detailEl || !bodyEl) return;
        detailEl.style.display = 'flex';

        const isAdminUser = API.currentUser?.role === 'admin';

        if (chat.type === 'user') {
            bodyEl.innerHTML = `
                <div class="im-detail-section">
                    <div class="im-detail-section-title">👤 好友信息</div>
                    <div style="text-align:center;padding:16px">
                        <div style="width:48px;height:48px;border-radius:50%;background:var(--primary-light);color:white;display:flex;align-items:center;justify-content:center;font-size:24px;margin:0 auto 8px">${(chat.name[0] || '?').toUpperCase()}</div>
                        <div style="font-size:16px;font-weight:600">${API._escapeHtml(chat.name)}</div>
                        <div class="text-muted" style="font-size:12px;margin-top:4px">ID: ${chat.id}</div>
                    </div>
                </div>
                <div class="im-detail-section">
                    <button class="btn btn-sm btn-danger btn-block" onclick="App.deleteIMFriendByChat()">🗑️ 删除好友</button>
                </div>`;
        } else {
            bodyEl.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';
            try {
                const group = await API.getGroupDetail(chat.id);
                const members = group.members || [];
                const currentUserId = API.currentUser?.id;
                const isOwner = group.owner_id === currentUserId;
                const isGroupBanned = group.status === 'banned';
                
                let memberHtml = members.map(m => {
                    const mName = m.nickname || m.username || `用户${m.user_id}`;
                    const isSelf = m.user_id === currentUserId;
                    const canRemove = (isOwner || isAdminUser) && !isSelf && m.role !== 'owner';
                    return `<div class="im-detail-member">
                        <div class="im-detail-member-avatar">${(mName[0] || '?').toUpperCase()}</div>
                        <span class="im-detail-member-name">${API._escapeHtml(mName)}${m.role === 'owner' ? ' 👑' : (m.is_worker ? ' 🤖' : '')}</span>
                        ${canRemove ? `<button class="btn btn-xs btn-ghost im-detail-member-remove" onclick="App.removeGroupMemberBtn(${chat.id}, ${m.user_id}, '${API._escapeHtml(mName)}')" title="移除">✕</button>` : ''}
                    </div>`;
                }).join('');

                const statusTag = isGroupBanned 
                    ? '<span class="tag tag-danger" style="margin-left:8px">已封禁</span>' 
                    : '<span class="tag tag-success" style="margin-left:8px">正常</span>';

                bodyEl.innerHTML = `
                    <div class="im-detail-section">
                        <div class="im-detail-section-title">👥 群组信息 ${statusTag}</div>
                        <div style="text-align:center;padding:12px">
                            <div style="font-size:18px;font-weight:600">${API._escapeHtml(group.name || chat.name)}</div>
                            <div class="text-muted" style="font-size:12px;margin-top:4px">${members.length} 人 · ID: ${chat.id}</div>
                            ${group.announcement ? `<div style="margin-top:8px;padding:8px;background:var(--bg-input);border-radius:var(--radius-xs);font-size:12px;color:var(--text-light);text-align:left">📢 ${API._escapeHtml(group.announcement)}</div>` : ''}
                        </div>
                    </div>
                    <div style="display:flex;gap:10px">
                        <div style="flex:1;min-width:0">
                            <div class="im-detail-section-title" style="margin-bottom:6px">👥 群成员</div>
                            <div style="max-height:300px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius-xs);padding:4px">
                                ${memberHtml || '<div class="text-muted" style="padding:8px;text-align:center">暂无成员</div>'}
                            </div>
                        </div>
                        <div style="width:70px;flex-shrink:0;display:flex;flex-direction:column;gap:6px;padding-top:22px">
                            ${isOwner ? `
                                <button class="btn btn-xs btn-primary" onclick="App.showGroupManageModal(${chat.id})" title="群管理">⚙️</button>
                                <button class="btn btn-xs btn-danger" onclick="App.dismissGroupConfirm(${chat.id}, '${API._escapeHtml(group.name || chat.name)}')" title="解散群组">🗑️</button>
                            ` : ''}
                            ${isAdminUser ? `
                                <div class="im-detail-section-title" style="font-size:11px;margin-bottom:2px;text-align:center">管控</div>
                                <button class="btn btn-xs ${isGroupBanned ? 'btn-success' : 'btn-warning'}" onclick="App.adminToggleGroupBan(${chat.id}, ${isGroupBanned})" title="${isGroupBanned ? '解封群组' : '封禁群组'}">
                                    ${isGroupBanned ? '🔓 解封' : '🔒 封禁'}
                                </button>
                                <button class="btn btn-xs btn-primary" onclick="App.adminShowAnnouncementForm(${chat.id}, '${API._escapeHtml(group.name || chat.name)}')" title="发系统公告">📢 公告</button>
                            ` : ''}
                        </div>
                    </div>`;
            } catch (err) {
                bodyEl.innerHTML = `<div class="error-state">❌ ${err.message}</div>`;
            }
        }
    },

    /** 通过聊天详情删除好友 */
    async deleteIMFriendByChat() {
        if (!confirm('确定要删除这个好友吗？')) return;
        const chat = this._im.currentChat;
        if (!chat) return;
        const friend = (this._im.friends || []).find(f => f.user_id === chat.id);
        if (!friend) { API.toast('error', '操作失败', '未找到好友记录'); return; }
        try {
            await API.deleteFriend(friend.id);
            API.toast('success', '已删除');
            this.closeChatDetail();
            this._resetIMChatArea();
            this._im.currentChat = null;
            this.loadIMFriends();
            this.loadIMConversations();
        } catch (err) {
            API.toast('error', '删除失败', err.message);
        }
    },

    closeChatDetail() {
        const detailEl = document.getElementById('im-chat-detail');
        if (detailEl) detailEl.style.display = 'none';
    },

    /** IM 消息轮询 - 每3秒刷新一次（纯HTTP轮询，无需WebSocket） */
    _startIMMessagePolling() {
        if (this._im.pollingTimer) clearInterval(this._im.pollingTimer);
        this._im.pollingTimer = setInterval(() => {
            this._pollIMMessages();
        }, 3000);
    },

    _stopIMMessagePolling() {
        if (this._im.pollingTimer) {
            clearInterval(this._im.pollingTimer);
            this._im.pollingTimer = null;
        }
    },

    async _pollIMMessages() {
        const chat = this._im.currentChat;
        try {
            // 无论是否有选中聊天，每次轮询都刷新左侧对话列表
            this.loadIMConversations();

            // 如果有选中的聊天对象，再增量轮询新消息
            if (chat) {
                const data = await API.getMessages(chat.type, chat.id, null, 50);
                const items = data.items || data || [];
                let messages = Array.isArray(items) ? items : [];
                // 【防御性过滤】轮询也要按类型过滤消息
                if (chat.type === 'user') {
                    messages = messages.filter(m => m.receiver_type === 'user');
                } else if (chat.type === 'group') {
                    messages = messages.filter(m => m.receiver_type === 'group');
                }
                if (messages.length === 0) return;

                // 用最新消息的ID判断是否有新消息
                const latestIncomingId = messages[messages.length - 1].id;
                const latestCachedId = this._im.messages.length > 0
                    ? this._im.messages[this._im.messages.length - 1].id
                    : 0;

                // 只有新来的消息ID与缓存的最新ID不同时，才认为有新消息
                if (latestIncomingId !== latestCachedId) {
                    // 找出确实不在已有消息中的新消息
                    const existingIds = new Set(this._im.messages.map(m => m.id));
                    const newMsgs = messages.filter(m => !existingIds.has(m.id));
                    if (newMsgs.length > 0) {
                        this._im.messages = this._im.messages.concat(newMsgs);
                        const msgEl = document.getElementById('im-messages');
                        if (msgEl) {
                            newMsgs.forEach(m => {
                                this._renderIMMessage(m, chat.type);
                                // 检测天气效果并展示
                                if (m.weather_effect) {
                                    this.showWeatherEffect(m.weather_effect);
                                }
                            });
                            this._scrollIMToBottom();
                        }
                    }
                }
            }
        } catch {}
    },

    async loadAdmin() {
        API.loadData('admin', '/api/admin/users', { container: document.getElementById('admin-users') });
        API.loadData('admin', '/api/admin/api-keys', { container: document.getElementById('admin-apikeys') });
        API.loadData('admin', '/api/admin/configs', { container: document.getElementById('admin-configs') });
        API.loadData('admin', '/api/admin/logs', { container: document.getElementById('admin-logs') });
        API.loadData('admin', '/api/admin/token-stats/daily', { container: document.getElementById('admin-token-daily') });
        API.loadData('admin', '/api/admin/token-stats/users', { container: document.getElementById('admin-token-users') });
        this.loadAdminGroups();
        this.loadDatabaseStatus();
    },

    // ========== 管理员群组管理 ==========

    /** 管理员加载所有群组列表 */
    async loadAdminGroups() {
        const container = document.getElementById('admin-groups');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载群组列表...</div>';
        try {
            const res = await API.request('GET', '/api/im/admin/groups?page=1&page_size=100');
            const data = res.data || {};
            const groups = data.items || data || [];
            if (!Array.isArray(groups) || groups.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">👥</div><div class="empty-text">暂无群组</div></div>';
                return;
            }
            let html = '<div class="data-table-wrapper"><table class="data-table"><thead><tr><th>ID</th><th>群名称</th><th>群主ID</th><th>成员数</th><th>状态</th><th>创建时间</th><th>操作</th></tr></thead><tbody>';
            groups.forEach(g => {
                const statusClass = g.status === 'banned' ? 'tag tag-danger' : 'tag tag-success';
                const statusText = g.status === 'banned' ? '⚠️ 已封禁' : '✅ 正常';
                const time = App._formatTime(g.created_at, 'short');
                html += `<tr>
                    <td>${g.id}</td>
                    <td><strong>${API._escapeHtml(g.name)}</strong></td>
                    <td>${g.owner_id}</td>
                    <td>${g.member_count}</td>
                    <td><span class="${statusClass}">${statusText}</span></td>
                    <td>${time}</td>
                    <td>
                        <button class="btn btn-xs btn-primary" onclick="App.adminViewGroupDetail(${g.id})" title="查看详情">👁️ 详情</button>
                        <button class="btn btn-xs btn-ghost" onclick="App.adminShowAnnouncement(${g.id}, '${API._escapeHtml(g.name)}')" title="发系统公告">📢 公告</button>
                        ${g.status === 'banned' 
                            ? `<button class="btn btn-xs btn-success" onclick="App.adminUnbanGroupConfirm(${g.id}, '${API._escapeHtml(g.name)}')" title="解封">🔓 解封</button>`
                            : `<button class="btn btn-xs btn-warning" onclick="App.adminBanGroupConfirm(${g.id}, '${API._escapeHtml(g.name)}')" title="封禁">🔒 封禁</button>`
                        }
                        <button class="btn btn-xs btn-danger" onclick="App.adminDissolveGroupConfirm(${g.id}, '${API._escapeHtml(g.name)}')" title="解散">🗑️ 解散</button>
                    </td>
                </tr>`;
            });
            html += '</tbody></table></div>';
            container.innerHTML = html;
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ 加载失败: ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 管理员查看群组详情 */
    async adminViewGroupDetail(groupId) {
        try {
            const res = await API.request('GET', `/api/im/admin/groups/${groupId}/detail`);
            const group = res.data || {};
            const membersRes = await API.request('GET', `/api/im/admin/groups/${groupId}/members`);
            const membersData = membersRes.data || {};
            const members = membersData.members || [];

            let memberHtml = members.map(m => {
                const mName = m.nickname || m.username || `用户${m.user_id}`;
                const roleTag = m.role === 'owner' ? ' 👑' : (m.role === 'admin' ? ' 🔧' : '');
                const joined = App._formatTime(m.joined_at, 'short');
                return `<tr><td>${m.user_id}</td><td>${API._escapeHtml(mName)}</td><td>${m.role}${roleTag}</td><td>${joined}</td></tr>`;
            }).join('');

            const statusText = group.status === 'banned' ? '⚠️ 已封禁' : '✅ 正常';
            const time = App._formatTime(group.created_at, 'full');

            API.showModal(`👥 群组详情 - ${API._escapeHtml(group.name)}`, `
                <div style="margin-bottom:12px">
                    <div class="stats-grid" style="grid-template-columns:repeat(4,1fr);margin-bottom:12px">
                        <div class="stat-card"><div class="stat-value">${group.id}</div><div class="stat-label">群ID</div></div>
                        <div class="stat-card"><div class="stat-value">${group.owner_name}</div><div class="stat-label">群主</div></div>
                        <div class="stat-card"><div class="stat-value">${group.member_count}</div><div class="stat-label">成员数</div></div>
                        <div class="stat-card"><div class="stat-value">${statusText}</div><div class="stat-label">状态</div></div>
                    </div>
                    <div style="font-size:12px;color:var(--text-light);margin-bottom:8px">创建时间: ${time}</div>
                    ${group.announcement ? `<div style="padding:8px;background:var(--bg-input);border-radius:var(--radius-xs);margin-bottom:8px"><strong>📢 公告:</strong> ${API._escapeHtml(group.announcement)}</div>` : ''}
                </div>
                <div class="section-title">👥 成员列表 (${members.length}人)</div>
                <div style="max-height:300px;overflow-y:auto">
                    <table class="data-table" style="font-size:12px">
                        <thead><tr><th>ID</th><th>名称</th><th>角色</th><th>加入时间</th></tr></thead>
                        <tbody>${memberHtml || '<tr><td colspan="4" style="text-align:center">暂无成员</td></tr>'}</tbody>
                    </table>
                </div>
            `, `<button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`);
        } catch (err) {
            API.toast('error', '加载失败', err.message);
        }
    },

    /** 管理员封禁群组 */
    async adminBanGroupConfirm(groupId, groupName) {
        if (!confirm(`确定要封禁群组"${groupName}"吗？封禁后群成员将无法发送消息！`)) return;
        try {
            await API.adminBanGroup(groupId, 'ban');
            API.toast('success', '已封禁', `群组"${groupName}"已封禁`);
            this.loadAdminGroups();
        } catch (err) {
            API.toast('error', '封禁失败', err.message);
        }
    },

    /** 管理员解封群组 */
    async adminUnbanGroupConfirm(groupId, groupName) {
        if (!confirm(`确定要解封群组"${groupName}"吗？`)) return;
        try {
            await API.adminBanGroup(groupId, 'unban');
            API.toast('success', '已解封', `群组"${groupName}"已解封`);
            this.loadAdminGroups();
        } catch (err) {
            API.toast('error', '解封失败', err.message);
        }
    },

    /** 管理员解散群组 */
    async adminDissolveGroupConfirm(groupId, groupName) {
        if (!confirm(`⚠️ 确定要解散群组"${groupName}"吗？此操作不可撤销！将删除所有消息和成员记录。`)) return;
        if (!confirm(`再次确认：解散群组"${groupName}"后不可恢复，确定继续？`)) return;
        try {
            await API.request('POST', `/api/im/admin/groups/${groupId}/dissolve`);
            API.toast('success', '已解散', `群组"${groupName}"已解散`);
            this.loadAdminGroups();
        } catch (err) {
            API.toast('error', '解散失败', err.message);
        }
    },

    /** 管理员发送系统群公告 */
    adminShowAnnouncement(groupId, groupName) {
        API.showModal(`📢 发送系统公告 - ${API._escapeHtml(groupName)}`, `
            <div class="modal-form-group">
                <span class="modal-form-label">公告内容 *</span>
                <textarea class="modal-form-textarea" id="admin-sys-announcement" rows="4" placeholder="输入系统公告内容，所有群成员将收到通知..."></textarea>
                <div style="font-size:12px;color:var(--text-light);margin-top:4px">💡 公告将以系统消息形式发送到群聊中</div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.adminSendSysAnnouncement(${groupId})">📢 发送</button>`);
    },

    /** 确认发送系统公告 */
    async adminSendSysAnnouncement(groupId) {
        const content = document.getElementById('admin-sys-announcement')?.value?.trim();
        if (!content) { API.toast('warning', '提示', '请输入公告内容'); return; }
        try {
            await API.request('POST', `/api/im/admin/groups/${groupId}/announcement`, { announcement: content });
            API.toast('success', '公告已发送', '系统公告已发送给所有群成员');
            API.closeModal();
        } catch (err) {
            API.toast('error', '发送失败', err.message);
        }
    },

    // ========== 文件管理模块 ==========

    /** 文件分页状态 */
    _filesPage: 1,
    _filesPageSize: 20,
    _filesTotal: 0,

    async loadFiles() {
        await this.loadFilesStats();
        await this.loadFileList();
    },

    /** 加载文件统计信息 */
    async loadFilesStats() {
        const container = document.getElementById('files-stats');
        if (!container) return;
        try {
            const res = await API.request('GET', '/api/files/stats');
            const data = res.data || {};
            container.innerHTML = `
                <div class="stats-grid" style="grid-template-columns:repeat(6, 1fr)">
                    <div class="stat-card">
                        <div class="stat-value">${data.total_files || 0}</div>
                        <div class="stat-label">📁 总文件数</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${App._formatFileSize(data.total_size || 0)}</div>
                        <div class="stat-label">📦 总大小</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${data.today_uploads || 0}</div>
                        <div class="stat-label">📅 今日上传</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${data.total_uploaders || 0}</div>
                        <div class="stat-label">👤 上传者数</div>
                    </div>
                </div>`;
            // 显示类型分布（如果有）
            if (data.type_distribution && data.type_distribution.length > 0) {
                const distHtml = data.type_distribution.map(t => {
                    const mimeLabel = t.mime_type.split('/')[1] || t.mime_type;
                    return `<span class="tag tag-default" style="font-size:11px">${API._escapeHtml(mimeLabel)}: ${t.count}</span>`;
                }).join(' ');
                container.innerHTML += `<div style="margin-top:8px;display:flex;gap:6px;flex-wrap:wrap">${distHtml}</div>`;
            }
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 加载文件列表 */
    async loadFileList(page) {
        if (page !== undefined) this._filesPage = page;
        const container = document.getElementById('files-list');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';

        const searchVal = document.getElementById('files-search-input')?.value?.trim() || '';
        const typeFilter = document.getElementById('files-type-filter')?.value || '';
        const uploaderFilter = document.getElementById('files-uploader-filter')?.value || '';

        // 类型筛选转 mime_type 前缀
        let mimeType = '';
        const typeMap = {
            'image': 'image',
            'text': 'text',
            'application/pdf': 'application/pdf',
            'video': 'video',
            'audio': 'audio',
        };
        if (typeFilter && typeMap[typeFilter]) {
            mimeType = typeMap[typeFilter];
        }

        try {
            const params = new URLSearchParams();
            params.append('page', this._filesPage);
            params.append('page_size', this._filesPageSize);
            if (searchVal) params.append('file_name', searchVal);
            if (mimeType) params.append('mime_type', mimeType);
            if (uploaderFilter) params.append('uploader_id', uploaderFilter);

            const res = await API.request('GET', `/api/files?${params.toString()}`);
            const data = res.data || {};
            const items = data.items || [];
            this._filesTotal = data.total || items.length;

            // 更新分页信息
            const infoEl = document.getElementById('files-pagination-info');
            if (infoEl) {
                const totalPages = Math.ceil(this._filesTotal / this._filesPageSize) || 1;
                infoEl.textContent = `共 ${this._filesTotal} 个文件 · 第 ${this._filesPage}/${totalPages} 页`;
            }

            if (!Array.isArray(items) || items.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">📁</div><div class="empty-text">暂无文件，点击右上角"上传文件"上传</div></div>';
                this._renderFilesPagination();
                return;
            }

            let html = '<div class="data-table-wrapper"><table class="data-table"><thead><tr>' +
                '<th>文件名</th><th>大小</th><th>MIME类型</th><th>上传者</th><th>上传时间</th><th style="width:140px">操作</th>' +
                '</tr></thead><tbody>';

            items.forEach(f => {
                const time = App._formatTime(f.created_at);
                const fileIcon = App._getFileIcon(f.mime_type, f.file_name);
                const sizeDisplay = f.file_size_display || App._formatFileSize(f.file_size);

                // 图片直接预览，其他显示图标
                const isImage = f.mime_type && f.mime_type.startsWith('image/');
                const previewHtml = isImage
                    ? `<img src="/api/files/${f.id}/download?token=${encodeURIComponent(API.token)}" style="width:32px;height:32px;object-fit:cover;border-radius:4px;vertical-align:middle" />`
                    : `<span style="font-size:20px">${fileIcon}</span>`;

                html += `<tr>
                    <td>
                        <div style="display:flex;align-items:center;gap:8px">
                            ${previewHtml}
                            <span title="${API._escapeHtml(f.file_name)}" style="max-width:200px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;display:inline-block">${API._escapeHtml(f.file_name)}</span>
                        </div>
                    </td>
                    <td>${sizeDisplay}</td>
                    <td><span class="tag tag-default" style="font-size:11px">${API._escapeHtml(f.mime_type || '-')}</span></td>
                    <td>${f.uploader_id || '-'}</td>
                    <td>${time}</td>
                    <td class="action-cell">
                        <button class="btn btn-xs btn-primary" onclick="API.viewFileDetail(${f.id})" title="查看详情">👁️</button>
                        <button class="btn btn-xs btn-success" onclick="window.open('/api/files/${f.id}/download?token=${encodeURIComponent(API.token)}','_blank')" title="下载">⬇️</button>
                        <button class="btn btn-xs btn-ghost" onclick="API.deleteItem('files-list', ${f.id})" title="删除">🗑️</button>
                    </td>
                </tr>`;
            });

            html += '</tbody></table></div>';
            container.innerHTML = html;
            container._data = items;
            this._renderFilesPagination();
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 渲染文件分页 */
    _renderFilesPagination() {
        const navEl = document.getElementById('files-pagination-nav');
        if (!navEl) return;
        const totalPages = Math.ceil(this._filesTotal / this._filesPageSize) || 1;
        if (totalPages <= 1) { navEl.innerHTML = ''; return; }

        let html = '';
        html += `<button class="btn btn-xs ${this._filesPage <= 1 ? 'btn-ghost disabled' : 'btn-primary'}" 
            onclick="App.loadFileList(${this._filesPage - 1})" ${this._filesPage <= 1 ? 'disabled' : ''}>‹ 上一页</button>`;

        const start = Math.max(1, this._filesPage - 2);
        const end = Math.min(totalPages, this._filesPage + 2);
        if (start > 1) html += `<button class="btn btn-xs btn-ghost" onclick="App.loadFileList(1)">1</button>${start > 2 ? '<span style="padding:0 4px">...</span>' : ''}`;
        for (let i = start; i <= end; i++) {
            html += `<button class="btn btn-xs ${i === this._filesPage ? 'btn-primary' : 'btn-ghost'}" onclick="App.loadFileList(${i})">${i}</button>`;
        }
        if (end < totalPages) html += `${end < totalPages - 1 ? '<span style="padding:0 4px">...</span>' : ''}<button class="btn btn-xs btn-ghost" onclick="App.loadFileList(${totalPages})">${totalPages}</button>`;

        html += `<button class="btn btn-xs ${this._filesPage >= totalPages ? 'btn-ghost disabled' : 'btn-primary'}" 
            onclick="App.loadFileList(${this._filesPage + 1})" ${this._filesPage >= totalPages ? 'disabled' : ''}>下一页 ›</button>`;

        navEl.innerHTML = html;
    },

    /** 上传文件弹窗 */
    showFileUploadForm() {
        API.showModal('📤 上传文件', `
            <div class="modal-form-group">
                <span class="modal-form-label">选择文件 *</span>
                <input type="file" id="file-upload-input" class="form-input" style="padding:8px" />
                <div id="file-upload-info" style="font-size:12px;color:var(--text-light);margin-top:6px">支持所有文件类型，单文件最大 10MB</div>
            </div>
            <div class="modal-form-group">
                <span class="modal-form-label">关联消息 ID（可选）</span>
                <input class="modal-form-input" id="file-upload-msg-id" type="number" placeholder="聊天消息ID，可选" />
            </div>
            <div id="file-upload-preview" style="display:none;margin-top:8px;padding:12px;background:var(--bg-input);border-radius:var(--radius-xs);text-align:center">
                <div id="file-upload-preview-icon" style="font-size:32px">📄</div>
                <div id="file-upload-preview-name" style="font-weight:500;margin-top:4px"></div>
                <div id="file-upload-preview-size" style="font-size:12px;color:var(--text-light)"></div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.doFileUpload()">📤 开始上传</button>`);

        // 文件选择预览
        document.getElementById('file-upload-input')?.addEventListener('change', function() {
            const file = this.files?.[0];
            const preview = document.getElementById('file-upload-preview');
            if (!file) { preview.style.display = 'none'; return; }
            preview.style.display = 'block';
            document.getElementById('file-upload-preview-icon').textContent = App._getFileIcon(file.type, file.name);
            document.getElementById('file-upload-preview-name').textContent = file.name;
            document.getElementById('file-upload-preview-size').textContent = App._formatFileSize(file.size);
        });
    },

    /** 执行文件上传 */
    async doFileUpload() {
        const input = document.getElementById('file-upload-input');
        const file = input?.files?.[0];
        if (!file) { API.toast('warning', '提示', '请选择要上传的文件'); return; }

        const chatMessageId = parseInt(document.getElementById('file-upload-msg-id')?.value) || null;

        const formData = new FormData();
        formData.append('file', file);
        if (chatMessageId) formData.append('chat_message_id', chatMessageId.toString());

        const headers = {};
        if (API.token) headers['Authorization'] = `Bearer ${API.token}`;

        try {
            API.toast('info', '上传中', `${file.name} 上传中...`);
            const response = await fetch('/api/files/upload', {
                method: 'POST',
                headers,
                body: formData,
            });
            const data = await response.json();
            if (!response.ok) throw new Error(data.message || `HTTP ${response.status}`);

            const result = data.data || {};
            const isDuplicate = result.md5_hash ? true : false;
            const sizeStr = App._formatFileSize(result.file_size || file.size);
            API.toast('success', '上传成功', `${result.file_name} (${sizeStr})${isDuplicate ? ' 📎 MD5重复已去重' : ''}`);
            API.closeModal();
            this._filesPage = 1;
            this.loadFileList();
            this.loadFilesStats();
        } catch (err) {
            API.toast('error', '上传失败', err.message);
        }
    },

    /** 获取文件类型图标 */
    _getFileIcon(mimeType, fileName) {
        if (!mimeType && !fileName) return '📄';
        if (mimeType) {
            if (mimeType.startsWith('image/')) return '🖼️';
            if (mimeType.startsWith('video/')) return '🎬';
            if (mimeType.startsWith('audio/')) return '🎵';
            if (mimeType.startsWith('text/')) return '📄';
            if (mimeType.startsWith('application/pdf')) return '📕';
            if (mimeType.includes('zip') || mimeType.includes('rar') || mimeType.includes('7z')) return '🗜️';
            if (mimeType.includes('json') || mimeType.includes('xml')) return '📋';
            if (mimeType.includes('word') || mimeType.includes('document')) return '📝';
            if (mimeType.includes('excel') || mimeType.includes('spreadsheet') || mimeType.includes('sheet')) return '📊';
            if (mimeType.includes('powerpoint') || mimeType.includes('presentation')) return '📽️';
        }
        if (fileName) {
            const ext = fileName.split('.').pop()?.toLowerCase();
            const extMap = {
                'jpg': '🖼️', 'jpeg': '🖼️', 'png': '🖼️', 'gif': '🖼️', 'svg': '🖼️', 'webp': '🖼️',
                'mp4': '🎬', 'avi': '🎬', 'mov': '🎬', 'wmv': '🎬', 'flv': '🎬',
                'mp3': '🎵', 'wav': '🎵', 'flac': '🎵', 'aac': '🎵',
                'pdf': '📕', 'doc': '📝', 'docx': '📝',
                'xls': '📊', 'xlsx': '📊', 'csv': '📊',
                'ppt': '📽️', 'pptx': '📽️',
                'zip': '🗜️', 'rar': '🗜️', '7z': '🗜️', 'tar': '🗜️', 'gz': '🗜️',
                'json': '📋', 'xml': '📋', 'yaml': '📋', 'yml': '📋',
                'py': '🐍', 'js': '🟨', 'ts': '🟦', 'html': '🌐', 'css': '🎨', 'sql': '🗄️',
            };
            return extMap[ext] || '📄';
        }
        return '📄';
    },

    /** 格式化文件大小 */
    _formatFileSize(bytes) {
        if (!bytes || bytes === 0) return '0 B';
        const units = ['B', 'KB', 'MB', 'GB', 'TB'];
        let i = 0;
        let size = bytes;
        while (size >= 1024 && i < units.length - 1) {
            size /= 1024;
            i++;
        }
        return size.toFixed(i > 0 ? 1 : 0) + ' ' + units[i];
    },

    // ========== 自动工作流模块 ==========

    /** 工作流分页状态 */
    _wfPage: 1,
    _wfPageSize: 15,
    _wfTotal: 0,

    async loadWorkflow() {
        await this.loadWorkflowStats();
        await this.loadWorkflowTasks();
    },

    /** 加载工作流统计信息 */
    async loadWorkflowStats() {
        const container = document.getElementById('workflow-stats');
        if (!container) return;
        try {
            const res = await API.request('GET', '/api/workflow/stats');
            const data = res.data || {};
            container.innerHTML = `
                <div class="stats-grid" style="grid-template-columns:repeat(4,1fr)">
                    <div class="stat-card"><div class="stat-value">${data.total || 0}</div><div class="stat-label">📋 总任务</div></div>
                    <div class="stat-card"><div class="stat-value" style="color:var(--warning)">${data.running || 0}</div><div class="stat-label">⚡ 运行中</div></div>
                </div>`;
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 加载工作流任务列表 */
    async loadWorkflowTasks(page) {
        if (page !== undefined) this._wfPage = page;
        const container = document.getElementById('workflow-tasks');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';

        try {
            const res = await API.request('GET', `/api/workflow/tasks?page=${this._wfPage}&page_size=${this._wfPageSize}`);
            const data = res.data || {};
            const items = data.items || [];
            this._wfTotal = data.total || items.length;

            const infoEl = document.getElementById('workflow-pagination-info');
            if (infoEl) {
                const totalPages = Math.ceil(this._wfTotal / this._wfPageSize) || 1;
                infoEl.textContent = `共 ${this._wfTotal} 个任务 · 第 ${this._wfPage}/${totalPages} 页`;
            }

            if (!Array.isArray(items) || items.length === 0) {
                container.innerHTML = '<div class="empty-state"><div class="empty-icon">⚡</div><div class="empty-text">暂无任务，点击"新建任务"创建一个自动工作流</div></div>';
                this._renderWorkflowPagination();
                return;
            }

            let html = '<div class="data-table-wrapper"><table class="data-table"><thead><tr>' +
                '<th>ID</th><th>任务名称</th><th>状态</th><th>进度</th><th>创建时间</th><th style="width:180px">操作</th>' +
                '</tr></thead><tbody>';

            items.forEach(t => {
                const statusMap = {
                    'pending': '<span class="tag tag-default">⏳ 等待中</span>',
                    'running': '<span class="tag tag-warning">⚡ 运行中</span>',
                    'completed': '<span class="tag tag-success">✅ 已完成</span>',
                    'failed': '<span class="tag tag-danger">❌ 失败</span>',
                    'cancelled': '<span class="tag tag-default">⏹️ 已取消</span>',
                };
                const statusHtml = statusMap[t.status] || `<span class="tag tag-default">${t.status}</span>`;
                const time = this._formatTime(t.created_at);
                const progress = `${t.current_step}/${t.total_steps}`;
                const isRunning = t.status === 'running';
                const isPending = t.status === 'pending';

                html += `<tr>
                    <td>#${t.id}</td>
                    <td><strong>${API._escapeHtml(t.name)}</strong></td>
                    <td>${statusHtml}</td>
                    <td>${progress}</td>
                    <td>${time}</td>
                    <td class="action-cell">
                        <button class="btn btn-xs btn-primary" onclick="App.showWorkflowTaskDetail(${t.id})" title="查看详情">👁️</button>
                        ${isPending ? `<button class="btn btn-xs btn-success" onclick="App.startWorkflowTask(${t.id})">▶️ 启动</button>` : ''}
                        ${isRunning ? `<button class="btn btn-xs btn-warning" onclick="App.cancelWorkflowTask(${t.id})">⏹️ 取消</button>` : ''}
                        <button class="btn btn-xs btn-ghost" onclick="App.deleteWorkflowTask(${t.id})" title="删除">🗑️</button>
                    </td>
                </tr>`;
            });

            html += '</tbody></table></div>';
            container.innerHTML = html;
            container._data = items;
            this._renderWorkflowPagination();
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 渲染工作流分页 */
    _renderWorkflowPagination() {
        const navEl = document.getElementById('workflow-pagination-nav');
        if (!navEl) return;
        const totalPages = Math.ceil(this._wfTotal / this._wfPageSize) || 1;
        if (totalPages <= 1) { navEl.innerHTML = ''; return; }

        let html = '';
        html += `<button class="btn btn-xs ${this._wfPage <= 1 ? 'btn-ghost disabled' : 'btn-primary'}" 
            onclick="App.loadWorkflowTasks(${this._wfPage - 1})" ${this._wfPage <= 1 ? 'disabled' : ''}>‹ 上一页</button>`;
        const start = Math.max(1, this._wfPage - 2);
        const end = Math.min(totalPages, this._wfPage + 2);
        if (start > 1) html += `<button class="btn btn-xs btn-ghost" onclick="App.loadWorkflowTasks(1)">1</button>${start > 2 ? '<span style="padding:0 4px">...</span>' : ''}`;
        for (let i = start; i <= end; i++) {
            html += `<button class="btn btn-xs ${i === this._wfPage ? 'btn-primary' : 'btn-ghost'}" onclick="App.loadWorkflowTasks(${i})">${i}</button>`;
        }
        if (end < totalPages) html += `${end < totalPages - 1 ? '<span style="padding:0 4px">...</span>' : ''}<button class="btn btn-xs btn-ghost" onclick="App.loadWorkflowTasks(${totalPages})">${totalPages}</button>`;
        html += `<button class="btn btn-xs ${this._wfPage >= totalPages ? 'btn-ghost disabled' : 'btn-primary'}" 
            onclick="App.loadWorkflowTasks(${this._wfPage + 1})" ${this._wfPage >= totalPages ? 'disabled' : ''}>下一页 ›</button>`;
        navEl.innerHTML = html;
    },

    /** 新建工作流任务弹窗 */
    showCreateWorkflowTask() {
        // 加载可选的数据源
        API.request('GET', '/api/workflow/sources').then(res => {
            const sources = res.data || [];
            let sourceHtml;
            if (sources.length === 0) {
                sourceHtml = '<div class="text-muted" style="padding:12px;text-align:center">暂无瞭望源，请先在"智能瞭望"模块创建数据源</div>';
            } else {
                sourceHtml = sources.map(s => `
                    <label style="display:flex;align-items:center;gap:8px;padding:6px 4px;border-bottom:1px solid var(--border)">
                        <input type="checkbox" class="wf-source-cb" value="${s.id}" />
                        <span>📡 ${API._escapeHtml(s.name)}</span>
                        <span style="font-size:11px;color:var(--text-light);margin-left:auto">${s.enabled ? '✅' : '❌'}</span>
                    </label>
                `).join('');
            }

            API.showModal('⚡ 新建自动工作流任务', `
                <div class="modal-form-group">
                    <span class="modal-form-label">任务名称 *</span>
                    <input class="modal-form-input" id="wf-task-name" placeholder="例如: 每日舆情分析" value="${new Date().toLocaleDateString('zh-CN')} 自动采集" />
                    <div style="font-size:12px;color:var(--text-light);margin-top:4px">💡 任务将自动执行3个步骤：📡采集数据源 → 🧹清洗入库 → 📊舆情分析</div>
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">选择数据源 *</span>
                    <div style="max-height:250px;overflow-y:auto;border:1px solid var(--border);border-radius:var(--radius-xs);padding:4px 8px">
                        ${sourceHtml}
                    </div>
                </div>
            `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
                <button class="btn btn-sm btn-primary" onclick="App.doCreateWorkflowTask()">💾 创建</button>`);
        }).catch(err => {
            API.toast('error', '加载数据源失败', err.message);
        });
    },

    /** 执行创建工作流任务 */
    async doCreateWorkflowTask() {
        const name = document.getElementById('wf-task-name')?.value?.trim();
        if (!name) { API.toast('warning', '提示', '请输入任务名称'); return; }

        const cbs = document.querySelectorAll('.wf-source-cb:checked');
        const sourceIds = Array.from(cbs).map(cb => parseInt(cb.value)).filter(id => !isNaN(id));
        if (sourceIds.length === 0) { API.toast('warning', '提示', '请至少选择一个数据源'); return; }

        try {
            const res = await API.request('POST', '/api/workflow/tasks', { name, source_ids: sourceIds });
            API.toast('success', '创建成功', `任务 #${res.data?.id} 已创建`);
            API.closeModal();
            this._wfPage = 1;
            this.loadWorkflow();
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    /** 启动工作流任务 */
    async startWorkflowTask(taskId) {
        if (!confirm(`确定要启动任务 #${taskId} 吗？`)) return;
        try {
            await API.request('POST', `/api/workflow/tasks/${taskId}/start`);
            API.toast('success', '任务已启动', `任务 #${taskId} 已在后台执行`);
            this.loadWorkflowTasks();
        } catch (err) {
            API.toast('error', '启动失败', err.message);
        }
    },

    /** 取消工作流任务 */
    async cancelWorkflowTask(taskId) {
        if (!confirm(`确定要取消任务 #${taskId} 吗？`)) return;
        try {
            await API.request('POST', `/api/workflow/tasks/${taskId}/cancel`);
            API.toast('success', '已取消', `任务 #${taskId} 已取消`);
            this.loadWorkflowTasks();
        } catch (err) {
            API.toast('error', '取消失败', err.message);
        }
    },

    /** 删除工作流任务 */
    async deleteWorkflowTask(taskId) {
        if (!confirm(`确定要删除任务 #${taskId} 吗？此操作不可撤销！`)) return;
        try {
            await API.request('DELETE', `/api/workflow/tasks/${taskId}`);
            API.toast('success', '已删除', `任务 #${taskId} 已删除`);
            this.loadWorkflowTasks();
        } catch (err) {
            API.toast('error', '删除失败', err.message);
        }
    },

    /** 查看工作流任务详情 */
    async showWorkflowTaskDetail(taskId) {
        try {
            const res = await API.request('GET', `/api/workflow/tasks/${taskId}`);
            const task = res.data || {};

            const statusMap = {
                'pending': '⏳ 等待中',
                'running': '⚡ 运行中',
                'completed': '✅ 已完成',
                'failed': '❌ 失败',
                'cancelled': '⏹️ 已取消',
            };
            const statusHtml = statusMap[task.status] || task.status;
            const progressHtml = task.total_steps > 0
                ? `<div style="margin:8px 0">
                     <div style="display:flex;justify-content:space-between;font-size:12px;margin-bottom:4px">
                       <span>进度: ${task.current_step}/${task.total_steps}</span>
                       <span>${Math.round(task.current_step / task.total_steps * 100)}%</span>
                     </div>
                     <div style="background:var(--bg-input);border-radius:8px;height:8px;overflow:hidden">
                       <div style="background:var(--primary);height:100%;width:${Math.round(task.current_step / task.total_steps * 100)}%;border-radius:8px;transition:width 0.3s"></div>
                     </div>
                   </div>`
                : '';

            let logsHtml = '';
            if (task.logs && task.logs.length > 0) {
                logsHtml = '<div style="margin-top:16px"><div class="section-title" style="margin-bottom:8px">📋 步骤日志</div>';
                task.logs.forEach(log => {
                    const logStatusMap = {
                        'pending': '⏳',
                        'running': '⚡',
                        'completed': '✅',
                        'failed': '❌',
                        'skipped': '⏭️',
                    };
                    const logIcon = logStatusMap[log.status] || '❓';
                    const logTime = log.completed_at ? this._formatTime(log.completed_at) : (log.started_at ? this._formatTime(log.started_at) : '');
                    logsHtml += `
                        <div style="padding:8px 12px;margin-bottom:6px;background:var(--bg);border-radius:var(--radius-xs);border:1px solid var(--border)">
                            <div style="display:flex;justify-content:space-between;align-items:center">
                                <span><strong>步骤 ${log.step_index + 1}:</strong> ${log.step_label || log.step_name}</span>
                                <span>${logIcon} <span style="font-size:12px;color:var(--text-light)">${logTime}</span></span>
                            </div>
                            ${log.target_name ? `<div style="font-size:12px;color:var(--text-light);margin-top:4px">🎯 ${API._escapeHtml(log.target_name)}</div>` : ''}
                            ${log.error_message ? `<div style="font-size:12px;color:var(--danger);margin-top:2px">❌ ${API._escapeHtml(log.error_message)}</div>` : ''}
                        </div>`;
                });
                logsHtml += '</div>';
            }

            const startTime = task.started_at ? this._formatTime(task.started_at) : '—';
            const endTime = task.completed_at ? this._formatTime(task.completed_at) : '—';

            API.showModal(`⚡ 任务详情 #${task.id}`, `
                <div class="stats-grid" style="grid-template-columns:repeat(3,1fr);margin-bottom:12px">
                    <div class="stat-card"><div class="stat-value" style="font-size:14px">${statusHtml}</div><div class="stat-label">状态</div></div>
                    <div class="stat-card"><div class="stat-value" style="font-size:14px">${startTime}</div><div class="stat-label">开始时间</div></div>
                    <div class="stat-card"><div class="stat-value" style="font-size:14px">${endTime}</div><div class="stat-label">完成时间</div></div>
                </div>
                <div style="background:var(--bg-card);border:1px solid var(--border);border-radius:var(--radius-sm);padding:12px;margin-bottom:12px">
                    <div style="font-weight:600;margin-bottom:8px">📌 ${API._escapeHtml(task.name)}</div>
                    ${progressHtml}
                    ${task.error_message ? `<div style="color:var(--danger);font-size:13px;margin-top:8px">❌ ${API._escapeHtml(task.error_message)}</div>` : ''}
                </div>
                ${logsHtml}
            `, `<button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`);
        } catch (err) {
            API.toast('error', '加载详情失败', err.message);
        }
    },

    // ========== 表单弹窗 ==========

    /** 新建瞭望源 */
    showWatchSourceForm() {
        API.showModal('📡 新建瞭望源', `
            <label class="modal-form-group"><span class="modal-form-label">名称 *</span>
                <input class="modal-form-input" id="ws-name" placeholder="如：新浪财经" /></label>
            <label class="modal-form-group"><span class="modal-form-label">URL *</span>
                <input class="modal-form-input" id="ws-url" placeholder="https://example.com" /></label>
            <label class="modal-form-group"><span class="modal-form-label">请求方法</span>
                <select class="modal-form-select" id="ws-method"><option value="GET">GET</option><option value="POST">POST</option></select></label>
            <label class="modal-form-group"><span class="modal-form-label">间隔（秒）</span>
                <input class="modal-form-input" id="ws-interval" value="3600" /></label>
            <label class="modal-form-group"><span class="modal-form-label">请求头（JSON）</span>
                <textarea class="modal-form-textarea" id="ws-headers" rows="2">{}</textarea></label>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.createWatchSource()">💾 创建</button>`);
    },

    async createWatchSource() {
        const body = {
            name: document.getElementById('ws-name')?.value,
            url: document.getElementById('ws-url')?.value,
            method: document.getElementById('ws-method')?.value || 'GET',
            interval_seconds: parseInt(document.getElementById('ws-interval')?.value) || 3600,
            headers: document.getElementById('ws-headers')?.value || '{}'
        };
        if (!body.name || !body.url) { API.toast('warning', '表单不完整', '请填写名称和URL'); return; }
        try {
            await API.request('POST', '/api/watch/sources', body);
            API.toast('success', '创建成功', '瞭望源已创建');
            API.closeModal();
            this.loadWatch();
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    /** 新建员工（异步加载 Jobs + API Keys 下拉列表） */
    async showWorkerForm() {
        let jobs = [];
        let apiKeys = [];
        try {
            const jobsRes = await API.request('GET', '/api/workers/jobs');
            jobs = jobsRes.data || [];
        } catch (e) { /* ignore */ }
        try {
            const keysRes = await API.request('GET', '/api/admin/api-keys');
            apiKeys = keysRes.data || [];
        } catch (e) { /* ignore */ }

        const jobOptions = jobs.length > 0
            ? jobs.map(j => `<option value="${j.id}">${j.icon || '🤖'} ${j.name} (${j.code})</option>`).join('')
            : '<option value="">-- 暂无工作，请先创建工作 --</option>';

        const keyOptions = apiKeys.length > 0
            ? apiKeys.map(k => `<option value="${k.id}">${k.name} (${k.model_name || '未知模型'})</option>`).join('')
            : '<option value="">-- 暂无 API Key，请先配置 --</option>';

        API.showModal('🤖 新建员工', `
            <label class="modal-form-group"><span class="modal-form-label">名称 *</span>
                <input class="modal-form-input" id="worker-name" placeholder="员工名称" /></label>
            <label class="modal-form-group"><span class="modal-form-label">所属工作 *</span>
                <select class="modal-form-select" id="worker-job-id">${jobOptions}</select></label>
            <label class="modal-form-group"><span class="modal-form-label">绑定 API Key *</span>
                <select class="modal-form-select" id="worker-apikey-id">${keyOptions}</select></label>
            <label class="modal-form-group"><span class="modal-form-label">图标</span>
                <input class="modal-form-input" id="worker-icon" value="🤖" /></label>
            <label class="modal-form-group"><span class="modal-form-label">描述</span>
                <textarea class="modal-form-textarea" id="worker-desc" rows="2" placeholder="员工简介"></textarea></label>
            <label class="modal-form-group"><span class="modal-form-label">人格提示词（System Prompt）</span>
                <textarea class="modal-form-textarea" id="worker-prompt" rows="4" placeholder="定义员工的性格、语气和行为方式，如：你是某领域的专家，回答专业且耐心..."></textarea>
                <div style="font-size:12px;color:var(--text-light);margin-top:4px">💡 留空则使用工作的默认提示词</div></label>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.createWorker()">💾 创建</button>`);
    },

    async createWorker() {
        const body = {
            name: document.getElementById('worker-name')?.value,
            job_id: parseInt(document.getElementById('worker-job-id')?.value),
            api_key_id: parseInt(document.getElementById('worker-apikey-id')?.value) || null,
            icon: document.getElementById('worker-icon')?.value || '🤖',
            description: document.getElementById('worker-desc')?.value || '',
            system_prompt: document.getElementById('worker-prompt')?.value || ''
        };
        if (!body.name || !body.job_id) { API.toast('warning', '表单不完整', '请填写名称并选择工作'); return; }
        try {
            await API.request('POST', '/api/workers', body);
            API.toast('success', '创建成功', '员工已创建');
            API.closeModal();
            this.loadWorkers();
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    /** 派遣员工 */
    showDispatchForm() {
        API.showModal('🚀 派遣员工', `
            <label class="modal-form-group"><span class="modal-form-label">员工 ID *</span>
                <input class="modal-form-input" id="dispatch-worker-id" type="number" placeholder="Worker ID" /></label>
            <label class="modal-form-group"><span class="modal-form-label">查询内容 *</span>
                <textarea class="modal-form-textarea" id="dispatch-query" rows="3" placeholder="输入查询或任务描述"></textarea></label>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.dispatchWorker()">🚀 派遣</button>`);
    },

    async dispatchWorker() {
        const body = {
            worker_id: parseInt(document.getElementById('dispatch-worker-id')?.value),
            query: document.getElementById('dispatch-query')?.value
        };
        if (!body.worker_id || !body.query) { API.toast('warning', '表单不完整', '请填写员工ID和查询内容'); return; }
        try {
            const res = await API.request('POST', '/api/dispatch/execute', body);
            API.toast('success', '派遣成功', `执行记录 ID: ${res.data?.execution_log_id || res.execution_log_id}`);
            API.closeModal();
            this.loadDispatch();
        } catch (err) {
            API.toast('error', '派遣失败', err.message);
        }
    },

    /** 获取员工列表（用于下拉菜单） */
    async _fetchWorkersForDropdown() {
        try {
            const res = await API.request('GET', '/api/workers');
            const workers = res.data || [];
            return workers.filter(w => w.enabled == 1);
        } catch {
            return [];
        }
    },

    /** 启动清洗 */
    async showCleaningForm() {
        const workers = await this._fetchWorkersForDropdown();

        const workerOptions = workers.length > 0
            ? workers.map(w => `<option value="${w.id}">${w.icon || '🤖'} ${w.name} (ID:${w.id})</option>`).join('')
            : '<option value="">-- 暂无可用的数字员工，请先在"数字员工"模块创建 --</option>';

        API.showModal('🧹 启动数据清洗', `
            <label class="modal-form-group"><span class="modal-form-label">瞭望数据 ID（逗号分隔）*</span>
                <input class="modal-form-input" id="clean-data-ids" placeholder="如：1,2,3" /></label>
            <label class="modal-form-group"><span class="modal-form-label">清洗方法</span>
                <select class="modal-form-select" id="clean-method" onchange="App._onCleanMethodChange()">
                    <option value="ai">🤖 AI 清洗（推荐）</option>
                    <option value="regex">🔧 正则清洗</option>
                </select></label>
            <label class="modal-form-group" id="clean-worker-group">
                <span class="modal-form-label">数字员工（AI 清洗必填）</span>
                <select class="modal-form-select" id="clean-worker-select">${workerOptions}</select>
                <div style="font-size:12px;color:var(--text-light);margin-top:4px">💡 数字员工需绑定 data_cleaner 工作并绑定 API Key</div>
            </label>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.startCleaning()">▶️ 启动</button>`);
    },

    /** 清洗方法切换时显示/隐藏员工选择 */
    _onCleanMethodChange() {
        const method = document.getElementById('clean-method')?.value;
        const workerGroup = document.getElementById('clean-worker-group');
        if (workerGroup) {
            workerGroup.style.display = method === 'ai' ? 'block' : 'none';
        }
    },

    async startCleaning() {
        const dataIdsStr = document.getElementById('clean-data-ids')?.value;
        const method = document.getElementById('clean-method')?.value || 'ai';
        let workerId = null;

        if (!dataIdsStr) { API.toast('warning', '表单不完整', '请填写瞭望数据ID'); return; }

        if (method === 'ai') {
            const workerSelect = document.getElementById('clean-worker-select');
            workerId = workerSelect ? parseInt(workerSelect.value) : null;
            if (!workerId) {
                API.toast('warning', '表单不完整', 'AI 清洗必须选择一个数字员工');
                return;
            }
        }

        const watchDataIds = dataIdsStr.split(',').map(s => parseInt(s.trim())).filter(n => !isNaN(n));
        const body = { watch_data_ids: watchDataIds, method };
        if (workerId) body.worker_id = workerId;

        try {
            await API.request('POST', '/api/cleaning/start', body);
            API.toast('success', '清洗已启动', '数据清洗任务已提交');
            API.closeModal();
            this.loadCleaning();
        } catch (err) {
            API.toast('error', '启动失败', err.message);
        }
    },

    /** 重试清洗 */
    async retryCleaning(logId) {
        if (!confirm(`确定要重新清洗日志 #${logId} 吗？`)) return;
        try {
            const res = await API.request('POST', `/api/cleaning/logs/${logId}/retry`);
            API.toast('success', '重试已提交', res.message || '清洗任务已在后台重新执行');
            this.loadCleaning();
        } catch (err) {
            API.toast('error', '重试失败', err.message);
        }
    },

    /** 新建文章 */
    showArticleForm() {
        API.showModal('📄 新建文章', `
            <label class="modal-form-group"><span class="modal-form-label">标题 *</span>
                <input class="modal-form-input" id="article-title" placeholder="文章标题" /></label>
            <label class="modal-form-group"><span class="modal-form-label">内容 *</span>
                <textarea class="modal-form-textarea" id="article-content" rows="4" placeholder="文章内容"></textarea></label>
            <label class="modal-form-group"><span class="modal-form-label">分类 ID</span>
                <input class="modal-form-input" id="article-category" type="number" placeholder="可选" /></label>
            <label class="modal-form-group"><span class="modal-form-label">标签</span>
                <input class="modal-form-input" id="article-tags" placeholder="逗号分隔" /></label>
            <label class="modal-form-group"><span class="modal-form-label">URL</span>
                <input class="modal-form-input" id="article-url" placeholder="来源链接" /></label>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.createArticle()">💾 创建</button>`);
    },

    async createArticle() {
        const body = {
            title: document.getElementById('article-title')?.value,
            content: document.getElementById('article-content')?.value,
            category_id: parseInt(document.getElementById('article-category')?.value) || null,
            tags: document.getElementById('article-tags')?.value || '',
            url: document.getElementById('article-url')?.value || ''
        };
        if (!body.title || !body.content) { API.toast('warning', '表单不完整', '请填写标题和内容'); return; }
        try {
            await API.request('POST', '/api/warehouse/articles', body);
            API.toast('success', '创建成功', '文章已创建');
            API.closeModal();
            this.loadWarehouse();
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    /** 新建对话 */
    showCreateConversationForm() {
        API.showModal('💬 新建对话', `
            <label class="modal-form-group"><span class="modal-form-label">标题</span>
                <input class="modal-form-input" id="conv-title" value="新对话" /></label>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.createConversation()">💾 创建</button>`);
    },

    async createConversation() {
        const title = document.getElementById('conv-title')?.value || '新对话';
        try {
            const res = await API.request('POST', '/api/chat/conversations', { title });
            API.toast('success', '创建成功', '对话已创建');
            API.closeModal();
            await this.loadChatConversations();
            const newId = res.data?.id;
            if (newId) {
                setTimeout(() => this.selectConversation(newId), 100);
            }
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    /** 新建用户（Admin） */
    showCreateUserForm() {
        API.showModal('👤 新建用户', `
            <label class="modal-form-group"><span class="modal-form-label">用户名 *</span>
                <input class="modal-form-input" id="admin-user-username" placeholder="用户名" /></label>
            <label class="modal-form-group"><span class="modal-form-label">密码 *（至少6位）</span>
                <input class="modal-form-input" id="admin-user-password" type="password" placeholder="密码" /></label>
            <label class="modal-form-group"><span class="modal-form-label">昵称</span>
                <input class="modal-form-input" id="admin-user-nickname" placeholder="可选" /></label>
            <label class="modal-form-group"><span class="modal-form-label">角色</span>
                <select class="modal-form-select" id="admin-user-role"><option value="user">👤 普通用户</option><option value="admin">🔐 管理员</option></select></label>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.createUser()">💾 创建</button>`);
    },

    async createUser() {
        const body = {
            username: document.getElementById('admin-user-username')?.value,
            password: document.getElementById('admin-user-password')?.value,
            nickname: document.getElementById('admin-user-nickname')?.value || '',
            role: document.getElementById('admin-user-role')?.value || 'user'
        };
        if (!body.username || !body.password) { API.toast('warning', '表单不完整', '请填写用户名和密码'); return; }
        if (body.password.length < 6) { API.toast('warning', '密码太短', '密码至少6位'); return; }
        try {
            await API.request('POST', '/api/admin/users', body);
            API.toast('success', '创建成功', '用户已创建');
            API.closeModal();
            this.loadAdmin();
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    // ========== 群主管理功能 ==========

    /** 群管理弹窗 */
    async showGroupManageModal(groupId) {
        const group = await API.getGroupDetail(groupId).catch(() => ({}));
        const groupName = group.name || '群聊';

        // 加载可用用户（非群成员的好友）和可用的数字员工
        let availableFriends = [];
        let availableWorkers = [];
        let currentMembers = [];

        try {
            const detail = await API.getGroupDetail(groupId);
            currentMembers = detail.members || [];
            const memberIds = currentMembers.map(m => m.user_id);
            const friends = await API.getFriends();
            // 过滤出还不是群成员的好友
            availableFriends = (Array.isArray(friends) ? friends : []).filter(f => {
                const userId = f.id || f.user_id;
                return !memberIds.includes(userId);
            });
        } catch {}

        try {
            const workers = await API.getChatWorkers();
            const memberIds = currentMembers.map(m => m.user_id);
            availableWorkers = (Array.isArray(workers) ? workers : []).filter(w => {
                return !memberIds.includes(w.user_id);
            });
        } catch {}

        const friendsHtml = availableFriends.length > 0
            ? availableFriends.map(f => {
                const userId = f.id || f.user_id;
                const name = f.remark || f.nickname || f.username || `用户${userId}`;
                return `<label class="im-mgmt-member-item">
                    <input type="checkbox" class="mgmt-member-cb" value="${userId}" />
                    <span class="im-mgmt-member-avatar">${(name[0] || '?').toUpperCase()}</span>
                    <span class="im-mgmt-member-name">${API._escapeHtml(name)}</span>
                </label>`;
              }).join('')
            : '<div class="text-muted" style="padding:12px;text-align:center">暂无可用好友</div>';

        const workersHtml = availableWorkers.length > 0
            ? availableWorkers.map(w => {
                return `<label class="im-mgmt-member-item">
                    <input type="checkbox" class="mgmt-worker-cb" value="${w.user_id}" />
                    <span class="im-mgmt-member-avatar" style="background:var(--secondary)">${w.icon || '🤖'}</span>
                    <span class="im-mgmt-member-name">${API._escapeHtml(w.name)} <span class="im-at-tag">数字员工</span></span>
                </label>`;
              }).join('')
            : '<div class="text-muted" style="padding:12px;text-align:center">暂无可用数字员工</div>';

        API.showModal(`⚙️ 群管理 - ${API._escapeHtml(groupName)}`, `
            <div class="im-mgmt-tabs">
                <button class="im-mgmt-tab active" data-mgmt-tab="add-members" onclick="App._switchMgmtTab('add-members')">👤 拉人进群</button>
                <button class="im-mgmt-tab" data-mgmt-tab="add-workers" onclick="App._switchMgmtTab('add-workers')">🤖 添加数字员工</button>
            </div>
            <div id="mgmt-tab-add-members" class="im-mgmt-tab-content active">
                <div class="im-mgmt-search">
                    <input type="text" class="im-mgmt-search-input" id="mgmt-member-search" placeholder="搜索好友..." oninput="App._filterMgmtMembers(this.value)" />
                </div>
                <div class="im-mgmt-member-list" id="mgmt-member-list">
                    ${friendsHtml}
                </div>
            </div>
            <div id="mgmt-tab-add-workers" class="im-mgmt-tab-content">
                <div class="im-mgmt-member-list" id="mgmt-worker-list">
                    ${workersHtml}
                </div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App._addSelectedToGroup(${groupId})">💾 确认添加</button>`);
    },

    /** 切换群管理 Tab */
    _switchMgmtTab(tab) {
        document.querySelectorAll('.im-mgmt-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.im-mgmt-tab-content').forEach(t => t.classList.remove('active'));
        const tabBtn = document.querySelector(`.im-mgmt-tab[data-mgmt-tab="${tab}"]`);
        if (tabBtn) tabBtn.classList.add('active');
        const tabContent = document.getElementById(`mgmt-tab-${tab}`);
        if (tabContent) tabContent.classList.add('active');
    },

    /** 搜索过滤群管理中的好友列表 */
    _filterMgmtMembers(keyword) {
        const list = document.getElementById('mgmt-member-list');
        if (!list) return;
        const items = list.querySelectorAll('.im-mgmt-member-item');
        items.forEach(item => {
            const name = item.querySelector('.im-mgmt-member-name')?.textContent || '';
            item.style.display = !keyword || name.toLowerCase().includes(keyword.toLowerCase()) ? 'flex' : 'none';
        });
    },

    /** 确认添加选中的成员（好友+数字员工）到群组 */
    async _addSelectedToGroup(groupId) {
        const memberCbs = document.querySelectorAll('.mgmt-member-cb:checked');
        const workerCbs = document.querySelectorAll('.mgmt-worker-cb:checked');
        const userIds = [];

        memberCbs.forEach(cb => userIds.push(parseInt(cb.value)));
        workerCbs.forEach(cb => userIds.push(parseInt(cb.value)));

        if (userIds.length === 0) {
            API.toast('warning', '提示', '请选择要添加的成员');
            return;
        }

        try {
            await API.addGroupMembers(groupId, userIds);
            API.toast('success', '添加成功', `已添加 ${userIds.length} 位成员到群组`);
            API.closeModal();
            // 刷新聊天详情
            this.showChatDetail();
            // 刷新群成员缓存
            this._im.atCurrentGroupId = null;
            this._im.atMenuMembers = [];
            this.loadIMGroups();
            this.loadIMConversations();
        } catch (err) {
            API.toast('error', '添加失败', err.message);
        }
    },

    /** 确认解散群组 */
    async dismissGroupConfirm(groupId, groupName) {
        if (!confirm(`确定要解散群组"${groupName}"吗？此操作不可撤销！`)) return;
        try {
            await API.dismissGroup(groupId);
            API.toast('success', '已解散', `群组"${groupName}"已解散`);
            this.closeChatDetail();
            this._resetIMChatArea();
            this._im.currentChat = null;
            this.loadIMGroups();
            this.loadIMConversations();
        } catch (err) {
            API.toast('error', '解散失败', err.message);
        }
    },

    /** 移除群成员（在聊天详情面板中） */
    async removeGroupMemberBtn(groupId, memberId, memberName) {
        if (!confirm(`确定要将 ${memberName} 移出群组吗？`)) return;
        try {
            await API.removeGroupMember(groupId, memberId);
            API.toast('success', '已移除', `${memberName} 已被移出群组`);
            this.showChatDetail();
            this._im.atCurrentGroupId = null;
            this._im.atMenuMembers = [];
            this.loadIMGroups();
        } catch (err) {
            API.toast('error', '移除失败', err.message);
        }
    },

    // ========== 管理员群管控功能 ==========

    /** 管理员封禁/解封群组 */
    async adminToggleGroupBan(groupId, isBanned) {
        const action = isBanned ? 'unban' : 'ban';
        const actionText = isBanned ? '解封' : '封禁';
        if (!confirm(`确定要${actionText}此群组吗？${isBanned ? '' : '封禁后群成员将无法发送消息！'}`)) return;
        try {
            await API.adminBanGroup(groupId, action);
            API.toast('success', `${actionText}成功`, `群组已${actionText}`);
            this.showChatDetail();
            this.loadIMGroups();
            this.loadIMConversations();
        } catch (err) {
            API.toast('error', `${actionText}失败`, err.message);
        }
    },

    /** 管理员发送系统公告弹窗 */
    adminShowAnnouncementForm(groupId, groupName) {
        API.showModal(`📢 发送系统公告 - ${API._escapeHtml(groupName)}`, `
            <div class="modal-form-group">
                <span class="modal-form-label">公告内容 *</span>
                <textarea class="modal-form-textarea" id="admin-announcement-content" rows="4" placeholder="输入系统公告内容，所有群成员将收到通知..."></textarea>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.adminSendAnnouncementConfirm(${groupId})">📢 发送公告</button>`);
    },

    /** 确认发送系统公告 */
    async adminSendAnnouncementConfirm(groupId) {
        const content = document.getElementById('admin-announcement-content')?.value?.trim();
        if (!content) { API.toast('warning', '提示', '请输入公告内容'); return; }
        try {
            await API.adminSendAnnouncement(groupId, content);
            API.toast('success', '公告已发送', '系统公告已发送给所有群成员');
            API.closeModal();
            this.showChatDetail();
        } catch (err) {
            API.toast('error', '发送失败', err.message);
        }
    },

    /** 新建 API Key（Admin） */
    showCreateApiKeyForm() {
        API.showModal('🔑 新建 API Key', `
            <label class="modal-form-group"><span class="modal-form-label">名称 *</span>
                <input class="modal-form-input" id="apikey-name" placeholder="如：默认 OpenAI" /></label>
            <label class="modal-form-group"><span class="modal-form-label">API Key *</span>
                <input class="modal-form-input" id="apikey-key" placeholder="sk-..." /></label>
            <label class="modal-form-group"><span class="modal-form-label">提供方</span>
                <select class="modal-form-select" id="apikey-provider"><option value="openai">OpenAI</option><option value="azure">Azure</option><option value="google">Google</option><option value="custom">自定义</option></select></label>
            <label class="modal-form-group"><span class="modal-form-label">Base URL</span>
                <input class="modal-form-input" id="apikey-base-url" placeholder="https://api.openai.com/v1" /></label>
            <label class="modal-form-group"><span class="modal-form-label">模型名称</span>
                <input class="modal-form-input" id="apikey-model" value="gpt-4o-mini" /></label>
            <label class="modal-form-group"><span class="modal-form-label">用途</span>
                <select class="modal-form-select" id="apikey-purpose">
                    <option value="chat">💬 聊天</option>
                    <option value="dataworker">🤖 数据工作</option>
                    <option value="all">全部</option>
                </select></label>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.createApiKey()">💾 创建</button>`);
    },

    async createApiKey() {
        const body = {
            name: document.getElementById('apikey-name')?.value,
            api_key: document.getElementById('apikey-key')?.value,
            provider: document.getElementById('apikey-provider')?.value || 'openai',
            base_url: document.getElementById('apikey-base-url')?.value || '',
            model_name: document.getElementById('apikey-model')?.value || 'gpt-4o-mini',
            purpose: document.getElementById('apikey-purpose')?.value || 'chat'
        };
        if (!body.name || !body.api_key) { API.toast('warning', '表单不完整', '请填写名称和API Key'); return; }
        try {
            await API.request('POST', '/api/admin/api-keys', body);
            API.toast('success', '创建成功', 'API Key 已创建');
            API.closeModal();
            this.loadAdmin();
        } catch (err) {
            API.toast('error', '创建失败', err.message);
        }
    },

    // ========== 数据库管理（多数据库支持与切换） ==========

    /** 加载数据库状态 */
    async loadDatabaseStatus() {
        const container = document.getElementById('admin-database-status');
        if (!container) return;
        container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载数据库状态...</div>';

        try {
            const res = await API.request('GET', '/api/admin/database/status');
            const status = res.data || {};

            const activeDb = status.active_database || 'sqlite';
            const dbTypeLabel = activeDb === 'mysql' ? '🐬 MySQL' : '🗃️ SQLite';
            const engineStatusText = status.engine_status === 'connected' ? '✅ 已连接' : '❌ 未连接';

            let configHtml = '';
            if (activeDb === 'mysql') {
                configHtml = `
                    <div class="stat-card" style="min-width:120px">
                        <div class="stat-value" style="font-size:14px">${status.mysql_config?.host || 'localhost'}</div>
                        <div class="stat-label">主机</div>
                    </div>
                    <div class="stat-card" style="min-width:120px">
                        <div class="stat-value" style="font-size:14px">${status.mysql_config?.port || 3306}</div>
                        <div class="stat-label">端口</div>
                    </div>
                    <div class="stat-card" style="min-width:120px">
                        <div class="stat-value" style="font-size:14px">${status.mysql_config?.database || 'ctos'}</div>
                        <div class="stat-label">数据库</div>
                    </div>
                    <div class="stat-card" style="min-width:120px">
                        <div class="stat-value" style="font-size:14px">${status.mysql_config?.user || 'root'}</div>
                        <div class="stat-label">用户</div>
                    </div>`;
            } else {
                configHtml = `
                    <div class="stat-card" style="min-width:200px">
                        <div class="stat-value" style="font-size:13px">${status.sqlite_config?.path || './data/ctos.db'}</div>
                        <div class="stat-label">数据库文件路径</div>
                    </div>`;
            }

            container.innerHTML = `
                <div class="stats-grid" style="grid-template-columns:repeat(auto-fit, minmax(120px, 1fr));margin-bottom:16px">
                    <div class="stat-card">
                        <div class="stat-value">${dbTypeLabel}</div>
                        <div class="stat-label">当前数据库</div>
                    </div>
                    <div class="stat-card">
                        <div class="stat-value">${engineStatusText}</div>
                        <div class="stat-label">连接状态</div>
                    </div>
                    ${configHtml}
                </div>
                <div style="display:flex;gap:10px;flex-wrap:wrap;margin-top:12px">
                    <button class="btn btn-sm btn-primary" onclick="App.showMySQLConfigForm()">⚙️ MySQL 配置</button>
                    <button class="btn btn-sm btn-primary" onclick="App.showSwitchDatabaseForm()">🔄 切换数据库</button>
                    <button class="btn btn-sm btn-success" onclick="App.showMigrateDatabaseForm()">📦 数据迁移</button>
                    <button class="btn btn-sm btn-ghost" onclick="App.loadDatabaseStatus()">🔄 刷新</button>
                </div>
                <div id="migration-progress-area" style="margin-top:12px"></div>`;
        } catch (err) {
            container.innerHTML = `<div class="error-state">❌ 加载数据库状态失败: ${API._escapeHtml(err.message)}</div>`;
        }
    },

    /** 显示切换数据库弹窗 */
    showSwitchDatabaseForm() {
        API.showModal('🔄 切换数据库', `
            <div style="margin-bottom:12px">
                <p style="margin-bottom:8px">选择要切换到的数据库：</p>
                <div style="display:flex;gap:12px">
                    <button class="btn btn-outline" onclick="App.confirmSwitchDatabase('sqlite')" style="flex:1;padding:12px;text-align:center">
                        <div style="font-size:28px;margin-bottom:4px">🗃️</div>
                        <div>SQLite</div>
                        <div style="font-size:11px;color:var(--text-light)">轻量本地数据库</div>
                    </button>
                    <button class="btn btn-outline" onclick="App.confirmSwitchDatabase('mysql')" style="flex:1;padding:12px;text-align:center">
                        <div style="font-size:28px;margin-bottom:4px">🐬</div>
                        <div>MySQL</div>
                        <div style="font-size:11px;color:var(--text-light)">生产级关系数据库</div>
                    </button>
                </div>
                <div style="margin-top:12px;padding:8px;background:var(--warning-bg, #fff3cd);border-radius:var(--radius-xs);font-size:12px;color:var(--warning-text, #856404)">
                    ⚠️ 切换数据库不会迁移数据，仅更改连接。<br>
                    如需迁移数据，请使用"数据迁移"功能。
                </div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>`);
    },

    /** 确认切换数据库 */
    async confirmSwitchDatabase(dbType) {
        try {
            const res = await API.request('POST', '/api/admin/database/switch', { db_type: dbType });
            API.toast('success', '切换成功', res.message || `已切换到 ${dbType}`);
            API.closeModal();
            this.loadDatabaseStatus();
        } catch (err) {
            API.toast('error', '切换失败', err.message);
        }
    },

    /** 显示MySQL配置弹窗（含密码配置） */
    showMySQLConfigForm() {
        API.showModal('⚙️ MySQL 配置', `
            <div style="margin-bottom:12px">
                <p style="margin-bottom:12px;font-size:13px;color:var(--text-light)">修改MySQL数据库连接参数，保存后可尝试切换到MySQL数据库</p>
                <div class="modal-form-group">
                    <span class="modal-form-label">主机地址</span>
                    <input class="modal-form-input" id="mysql-cfg-host" value="localhost" placeholder="如: localhost 或 192.168.1.100" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">端口</span>
                    <input class="modal-form-input" id="mysql-cfg-port" value="3306" type="number" placeholder="3306" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">用户名</span>
                    <input class="modal-form-input" id="mysql-cfg-user" value="root" placeholder="数据库用户名" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">密码</span>
                    <div class="password-wrapper">
                        <input class="modal-form-input" id="mysql-cfg-password" type="password" placeholder="数据库密码" />
                        <button type="button" class="password-toggle" tabindex="-1" onclick="this.previousElementSibling.type = this.previousElementSibling.type === 'password' ? 'text' : 'password'; this.textContent = this.previousElementSibling.type === 'password' ? '👁️' : '👁️‍🗨️';">👁️</button>
                    </div>
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">数据库名</span>
                    <input class="modal-form-input" id="mysql-cfg-database" value="ctos" placeholder="数据库名称" />
                </div>
                <div style="padding:8px;background:var(--info-bg, #d1ecf1);border-radius:var(--radius-xs);font-size:12px;color:var(--info-text, #0c5460);margin-top:8px">
                    💡 配置仅保存到内存中，重启后端后失效。<br>
                    如需持久化请修改 .env 文件中的 MYSQL_* 参数。
                </div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
            <button class="btn btn-sm btn-primary" onclick="App.saveMySQLConfig()">💾 保存配置</button>
            <button class="btn btn-sm btn-success" onclick="App.saveMySQLConfigAndSwitch()">💾 保存并切换到MySQL</button>`);
    },

    /** 保存MySQL配置 */
    async saveMySQLConfig() {
        const body = {};
        const host = document.getElementById('mysql-cfg-host')?.value?.trim();
        const port = parseInt(document.getElementById('mysql-cfg-port')?.value);
        const user = document.getElementById('mysql-cfg-user')?.value?.trim();
        const password = document.getElementById('mysql-cfg-password')?.value;
        const database = document.getElementById('mysql-cfg-database')?.value?.trim();

        if (host) body.host = host;
        if (port) body.port = port;
        if (user) body.user = user;
        if (password) body.password = password;
        if (database) body.database = database;

        try {
            await API.request('PUT', '/api/admin/database/mysql-config', body);
            API.toast('success', '配置已保存', 'MySQL配置已更新，可尝试切换数据库');
            API.closeModal();
            this.loadDatabaseStatus();
        } catch (err) {
            API.toast('error', '保存失败', err.message);
        }
    },

    /** 保存MySQL配置并立即切换到MySQL */
    async saveMySQLConfigAndSwitch() {
        const body = {};
        const host = document.getElementById('mysql-cfg-host')?.value?.trim();
        const port = parseInt(document.getElementById('mysql-cfg-port')?.value);
        const user = document.getElementById('mysql-cfg-user')?.value?.trim();
        const password = document.getElementById('mysql-cfg-password')?.value;
        const database = document.getElementById('mysql-cfg-database')?.value?.trim();

        if (host) body.host = host;
        if (port) body.port = port;
        if (user) body.user = user;
        if (password) body.password = password;
        if (database) body.database = database;

        try {
            // 1. 保存配置
            await API.request('PUT', '/api/admin/database/mysql-config', body);
            // 2. 切换
            const res = await API.request('POST', '/api/admin/database/switch', { db_type: 'mysql' });
            API.toast('success', '切换成功', res.message || '已切换到MySQL数据库');
            API.closeModal();
            this.loadDatabaseStatus();
        } catch (err) {
            API.toast('error', '切换失败', err.message);
        }
    },

    /** 显示数据迁移弹窗 */
    showMigrateDatabaseForm() {
        API.showModal('📦 数据迁移', `
            <div style="margin-bottom:12px">
                <p style="margin-bottom:8px">将当前数据库的数据迁移到目标数据库：</p>
                <div style="display:flex;gap:12px;margin-bottom:16px">
                    <button class="btn btn-outline" onclick="App.confirmMigrateDatabase('sqlite')" style="flex:1;padding:12px;text-align:center">
                        <div style="font-size:28px;margin-bottom:4px">🗃️</div>
                        <div>迁移到 SQLite</div>
                        <div style="font-size:11px;color:var(--text-light)">🔥 数据将从MySQL复制到SQLite</div>
                    </button>
                    <button class="btn btn-outline" onclick="App.confirmMigrateDatabase('mysql')" style="flex:1;padding:12px;text-align:center">
                        <div style="font-size:28px;margin-bottom:4px">🐬</div>
                        <div>迁移到 MySQL</div>
                        <div style="font-size:11px;color:var(--text-light)">🔥 数据将从SQLite复制到MySQL</div>
                    </button>
                </div>
                <div style="padding:8px;background:var(--warning-bg, #fff3cd);border-radius:var(--radius-xs);font-size:12px;color:var(--warning-text, #856404)">
                    ⚠️ 迁移过程会读取所有表数据并写入目标数据库，<br>
                    完成后自动切换到目标数据库。
                </div>
            </div>
        `, `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>`);
    },

    /** 确认执行数据迁移 */
    async confirmMigrateDatabase(targetDb) {
        API.closeModal();
        const area = document.getElementById('migration-progress-area');
        if (area) {
            area.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 正在执行数据迁移，请稍候...</div>';
        }

        try {
            const res = await API.request('POST', '/api/admin/database/migrate', { target_db: targetDb });
            const result = res.data || {};

            if (area) {
                if (result.status === 'completed') {
                    const verification = result.verification || {};
                    const mismatches = verification.mismatches || [];
                    const matchText = verification.passed
                        ? '<span style="color:var(--success)">✅ 全部通过</span>'
                        : `<span style="color:var(--danger)">⚠️ ${mismatches.length} 张表不匹配</span>`;

                    area.innerHTML = `
                        <div style="padding:12px;background:var(--success-bg, #d4edda);border-radius:var(--radius-xs);margin-top:12px">
                            <div style="font-weight:600;color:var(--success-text, #155724);margin-bottom:8px">✅ 迁移完成</div>
                            <table class="data-table" style="font-size:12px;margin:0">
                                <tbody>
                                    <tr><td>源数据库</td><td><strong>${result.source || ''}</strong></td></tr>
                                    <tr><td>目标数据库</td><td><strong>${result.target || ''}</strong></td></tr>
                                    <tr><td>迁移表数</td><td><strong>${result.tables_migrated || 0}</strong></td></tr>
                                    <tr><td>迁移数据量</td><td><strong>${result.total_rows || 0}</strong> 条</td></tr>
                                    <tr><td>数据校验</td><td>${matchText}</td></tr>
                                </tbody>
                            </table>
                            ${mismatches.length > 0 ? `
                                <div style="margin-top:8px;font-size:12px">
                                    <strong>不匹配的表：</strong>
                                    ${mismatches.map(m => `<div>${m.table}: 源 ${m.source} → 目标 ${m.target}</div>`).join('')}
                                </div>
                            ` : ''}
                        </div>`;
                } else {
                    area.innerHTML = `
                        <div style="padding:12px;background:var(--danger-bg, #f8d7da);border-radius:var(--radius-xs);margin-top:12px">
                            <div style="font-weight:600;color:var(--danger-text, #721c24)">❌ 迁移失败</div>
                            <div style="font-size:13px;margin-top:4px">${API._escapeHtml(result.error || '未知错误')}</div>
                        </div>`;
                }
            }

            this.loadDatabaseStatus();
            if (result.status === 'completed') {
                API.toast('success', '迁移完成', `已迁移 ${result.total_rows || 0} 条数据到 ${result.target}`);
            } else if (result.status === 'failed') {
                API.toast('error', '迁移失败', result.error);
            }
        } catch (err) {
            if (area) {
                area.innerHTML = `
                    <div style="padding:12px;background:var(--danger-bg, #f8d7da);border-radius:var(--radius-xs);margin-top:12px">
                        <div style="font-weight:600;color:var(--danger-text, #721c24)">❌ 迁移失败</div>
                        <div style="font-size:13px;margin-top:4px">${API._escapeHtml(err.message)}</div>
                    </div>`;
            }
            API.toast('error', '迁移失败', err.message);
        }
    },
};

// ========== 辅助函数 ==========

function clearAuth() {
    localStorage.removeItem('ctos_token');
    API.token = null;
    API.currentUser = null;
    // 断开 WebSocket 连接
    API.disconnectWS();
    // 清除模块容器"已加载"状态，确保下次登录时重新加载数据（切换用户时数据不刷新的关键修复）
    App._loadedContainers.clear();
    // 重置聊天状态，避免残留旧用户的对话数据
    App._chat.currentConvId = null;
    App._chat.messages = [];
    App._chat.isStreaming = false;
}

function closeSidebar() {
    document.querySelector('.sidebar')?.classList.remove('open');
    document.querySelector('.sidebar-overlay')?.classList.remove('active');
}

function clearFormErrors() {
    document.querySelectorAll('.form-error').forEach(e => e.classList.remove('visible'));
    document.querySelectorAll('.form-input.error').forEach(e => e.classList.remove('error'));
}

// ========== 登录处理 ==========
async function handleLogin() {
    const username = document.getElementById('loginUsername').value.trim();
    const password = document.getElementById('loginPassword').value;

    let valid = true;
    if (!username) {
        document.getElementById('loginUsername').classList.add('error');
        const err = document.querySelector('#loginTab .form-error');
        if (err) { err.textContent = '请输入用户名'; err.classList.add('visible'); }
        valid = false;
    }
    if (!password) {
        document.getElementById('loginPassword').closest('.form-group').querySelector('.form-error').classList.add('visible');
        document.getElementById('loginPassword').classList.add('error');
        valid = false;
    }
    if (!valid) return;

    const btn = document.getElementById('loginBtn');
    btn.disabled = true;
    btn.textContent = '⏳ 登录中...';

    const result = await API.login(username, password);
    if (result.success) {
        localStorage.setItem('ctos_token', API.token);
        showMainPage(result.user);
    }

    btn.disabled = false;
    btn.textContent = '登录';
}

// ========== 注册处理 ==========
async function handleRegister() {
    const username = document.getElementById('regUsername').value.trim();
    const password = document.getElementById('regPassword').value;
    const nickname = document.getElementById('regNickname').value.trim();

    let valid = true;
    if (!username) { valid = false; document.getElementById('regUsername').classList.add('error'); }
    if (!password || password.length < 6) {
        valid = false;
        document.getElementById('regPassword').classList.add('error');
        const err = document.querySelector('#registerTab .form-error');
        if (err) { err.textContent = '密码至少6位'; err.classList.add('visible'); }
    }
    if (!valid) return;

    const btn = document.getElementById('registerBtn');
    btn.disabled = true;
    btn.textContent = '⏳ 注册中...';

    const result = await API.register(username, password, nickname);
    if (result.success) {
        document.querySelector('[data-tab="loginTab"]').click();
        document.getElementById('loginUsername').value = username;
        document.getElementById('loginPassword').value = '';
        clearFormErrors();
    }

    btn.disabled = false;
    btn.textContent = '注册';
}

// ========== 健康检查 ==========
async function handleHealthCheck() {
    const statusEl = document.getElementById('healthStatus');
    statusEl.innerHTML = '⏳ 检查中...';

    const result = await API.healthCheck();
    if (result.status === 'ok') {
        statusEl.innerHTML = `<span style="color:#22c55e">●</span> 服务正常 (${result.app} v${result.version || '1.0.0'})`;
    } else {
        statusEl.innerHTML = `<span style="color:#ef4444">●</span> 服务异常: ${result.error || JSON.stringify(result)}`;
    }
}

// ========== 证书信任（HTTPS/WSS 自签名证书） ==========
async function handleTrustCert() {
    const certStatusEl = document.getElementById('certStatus');
    const btn = document.getElementById('trustCertBtn');
    if (!certStatusEl || !btn) return;

    btn.disabled = true;
    btn.textContent = '⏳ 正在连接...';
    certStatusEl.textContent = '正在尝试连接 HTTPS 后端...';

    try {
        // 先尝试 fetch HTTPS 后端，触发浏览器自签名证书信任提示
        const backendUrl = API.WS_BASE_URL || 'https://127.0.0.1:8000';
        const httpsBase = backendUrl.replace(/^ws(s)?:\/\//, 'https$1://');
        
        // 发送一个简单的 GET 请求到 /api/health
        const response = await fetch(`${httpsBase}/api/health`, {
            method: 'GET',
            mode: 'cors',
            cache: 'no-cache',
        });

        if (response.ok) {
            const data = await response.json();
            certStatusEl.innerHTML = `✅ 证书已信任！后端响应: ${data.app || '正常'}`;
            btn.textContent = '✅ 已连接';
            btn.style.borderColor = '#22c55e';
            API.toast('success', '🔒 证书已信任', 'HTTPS/WSS 后端连接成功！');
        } else {
            certStatusEl.textContent = `⚠️ 后端响应异常: HTTP ${response.status}`;
            btn.textContent = '🔄 重试';
            btn.disabled = false;
        }
    } catch (err) {
        // 自签名证书错误通常是用户的第一次访问，需要手动信任
        // 引导用户访问后端地址
        certStatusEl.innerHTML = `
            ⚠️ 需要手动信任证书。<br>
            请用浏览器打开 <a href="https://127.0.0.1:8000/api/health" target="_blank" style="color:var(--primary)">https://127.0.0.1:8000/api/health</a>，<br>
            点击"高级"→"继续前往"，然后再返回本页点击"信任证书"。
        `;
        btn.textContent = '🔒 再次尝试';
        btn.disabled = false;
        
        // 尝试用 iframe 方式加载（某些浏览器会自动弹窗要求确认）
        try {
            const iframe = document.createElement('iframe');
            iframe.style.display = 'none';
            iframe.src = 'https://127.0.0.1:8000/api/health';
            document.body.appendChild(iframe);
            setTimeout(() => iframe.remove(), 3000);
        } catch (e) {
            // 忽略 iframe 错误
        }
    }
}

// ========== 页面切换 ==========
function showMainPage(user) {
    document.getElementById('loginPage').classList.remove('active');
    document.getElementById('mainPage').classList.add('active');

    const userInfoEl = document.getElementById('userInfo');
    if (user && userInfoEl) {
        const initial = (user.nickname || user.username || 'U')[0].toUpperCase();
        userInfoEl.innerHTML = `
            <span class="user-avatar">${initial}</span>
            <span>${user.nickname || user.username}</span>
            <span style="color:var(--text-light);font-weight:400;font-size:11px">${user.role || 'user'}</span>
        `;

        if (user.role !== 'admin') {
            document.querySelectorAll('.admin-only').forEach(el => el.style.display = 'none');
        }
    }

    const themeToggle = document.getElementById('themeToggle');
    if (themeToggle) {
        const theme = document.documentElement.getAttribute('data-theme') || 'light';
        themeToggle.textContent = theme === 'dark' ? '☀️' : '🌙';
    }

    // 初始化手势识别客户端（无障碍功能）
    const gc = window.__gestureClient;
    if (gc) {
        gc.connect();
        // 更新语音播报按钮状态
        const ttsBtn = document.getElementById('ttsToggle');
        if (ttsBtn) {
            ttsBtn.textContent = gc.tts.enabled ? '🔊 语音' : '🔇 语音';
        }
    }

    App.switchModule('dashboard');
}

function showLoginPage() {
    document.getElementById('mainPage').classList.remove('active');
    document.getElementById('loginPage').classList.add('active');
    clearFormErrors();

    // 退出登录时断开手势客户端
    const gc = window.__gestureClient;
    if (gc) {
        gc.disconnect();
    }
}
