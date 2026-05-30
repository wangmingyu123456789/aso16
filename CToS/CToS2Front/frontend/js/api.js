/**
 * CToS API 客户端 v3.0
 * 管理后台专用 - 自动渲染、CRUD 操作、Toast 通知
 */
const API = {
    BASE_URL: '',
    /** WebSocket 地址
     *  开发模式下，run_dev_server.py 代理 /ws → 后端，所以用相对路径 ws://
     *  生产环境部署时，在 nginx 中统一代理 /ws 即可
     */
    WS_BASE_URL: '',  // 空字符串 = 使用页面当前 origin（开发服务器代理）
    token: null,
    currentUser: null,

    // ========== Toast 通知系统 ==========
    toastContainer: null,

    initToastContainer() {
        if (!this.toastContainer) {
            this.toastContainer = document.createElement('div');
            this.toastContainer.className = 'toast-container';
            document.body.appendChild(this.toastContainer);
        }
    },

    toast(type = 'info', title = '', message = '', duration = 4000) {
        this.initToastContainer();
        const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.innerHTML = `
            <span class="toast-icon">${icons[type] || 'ℹ️'}</span>
            <div class="toast-content">
                <div class="toast-title">${this._escapeHtml(title)}</div>
                ${message ? `<div class="toast-message">${this._escapeHtml(message)}</div>` : ''}
            </div>
            <button class="toast-close" onclick="this.closest('.toast').classList.add('removing');setTimeout(()=>this.closest('.toast').remove(),300)">×</button>`;
        this.toastContainer.appendChild(toast);
        if (duration > 0) {
            setTimeout(() => {
                toast.classList.add('removing');
                setTimeout(() => toast.remove(), 300);
            }, duration);
        }
    },

    _escapeHtml(str) {
        if (!str) return '';
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    // ========== 通用请求方法 ==========
    async request(method, path, body = null) {
        const headers = { 'Content-Type': 'application/json' };
        if (this.token) headers['Authorization'] = `Bearer ${this.token}`;
        const opts = { method, headers };
        if (body && method !== 'GET') opts.body = JSON.stringify(body);
        const response = await fetch(`${this.BASE_URL}${path}`, opts);
        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || `HTTP ${response.status}`);
        }
        return data;
    },

    // ========== 认证 ==========
    async login(username, password) {
        try {
            const data = await this.request('POST', '/api/auth/login', { username, password });
            if (data.code === 0 || data.code === 200) {
                this.token = data.data.token;
                this.currentUser = data.data.user;
                this.toast('success', '登录成功', `欢迎回来，${data.data.user.nickname || data.data.user.username}`);
                return { success: true, user: data.data.user };
            }
            this.toast('error', '登录失败', data.message || '用户名或密码错误');
            return { success: false };
        } catch (err) {
            this.toast('error', '网络错误', '无法连接到服务器，请确保后端已启动');
            return { success: false, message: err.message };
        }
    },

    async register(username, password, nickname) {
        try {
            const body = { username, password };
            if (nickname) body.nickname = nickname;
            const data = await this.request('POST', '/api/auth/register', body);
            if (data.code === 200 || data.code === 0) {
                this.toast('success', '注册成功', '请使用新账号登录');
                return { success: true };
            }
            this.toast('error', '注册失败', data.message || '请检查输入');
            return { success: false };
        } catch (err) {
            this.toast('error', '网络错误', err.message);
            return { success: false };
        }
    },

    async healthCheck() {
        try {
            const res = await fetch(`${this.BASE_URL}/api/health`);
            return await res.json();
        } catch (err) {
            return { error: err.message };
        }
    },

    async getCurrentUser() {
        if (!this.token) return null;
        try {
            const data = await this.request('GET', '/api/auth/me');
            if (data.code === 0 || data.code === 200) {
                this.currentUser = data.data;
                return data.data;
            }
            return null;
        } catch {
            return null;
        }
    },

    // ========== 数据获取与自动渲染 ==========
    /**
     * 获取数据并自动渲染到指定容器
     * @param {string} module - 模块名
     * @param {string} path - API路径
     * @param {object} options - {method, body, container, renderer, params}
     */
    async loadData(module, path, options = {}) {
        const { method = 'GET', body = null, container, renderer = 'table', params = {}, selectable = false } = options;

        // 构建带参数的URL
        let url = path;
        if (Object.keys(params).length > 0) {
            const qs = new URLSearchParams();
            Object.entries(params).forEach(([k, v]) => { if (v !== undefined && v !== null && v !== '') qs.append(k, v); });
            const qstr = qs.toString();
            if (qstr) url += (url.includes('?') ? '&' : '?') + qstr;
        }

        // 容器加载状态
        if (container) {
            container.innerHTML = '<div class="loading-spinner"><span class="mini-spinner"></span> 加载中...</div>';
        }

        try {
            const res = await this.request(method, url, body);
            const responseData = res.data !== undefined ? res.data : res;
            const items = (responseData && responseData.items && Array.isArray(responseData.items))
                ? responseData.items : responseData;

            if (container) {
                if (renderer === 'table' && Array.isArray(items)) {
                    this.renderTable(items, container, { selectable });
                } else if (renderer === 'stats' && typeof responseData === 'object' && !Array.isArray(responseData)) {
                    this.renderStats(responseData, container);
                } else if (renderer === 'list' && Array.isArray(items)) {
                    this.renderList(items, container);
                } else if (renderer === 'detail') {
                    this.renderDetail(responseData, container);
                } else if (renderer === 'cards' && Array.isArray(items)) {
                    this.renderCards(items, container);
                } else if (renderer === 'inline') {
                    this.renderInline(responseData, container);
                } else if (Array.isArray(items)) {
                    this.renderTable(items, container);
                } else {
                    this.renderDetail(responseData, container);
                }
            }
            return responseData;
        } catch (err) {
            if (container) {
                container.innerHTML = `<div class="error-state">❌ ${this._escapeHtml(err.message)}</div>`;
            }
            this.toast('error', '加载失败', err.message);
            return null;
        }
    },

    // ========== 数据渲染器 ==========

    /** 渲染数据表格（带操作列） */
    renderTable(items, container, options = {}) {
        if (!container) return;
        if (!items || items.length === 0) {
            container.innerHTML = '<div class="empty-state"><div class="empty-icon">📭</div><div class="empty-text">暂无数据</div></div>';
            return;
        }

        const { actions = true, idKey = 'id', excludeKeys = [], selectable = false } = options;
        const exclude = new Set(['avatar', '_json', ...excludeKeys]);

        // API Key 列表特殊处理：隐藏敏感字段和过宽字段
        const isApiKeys = container.id === 'admin-apikeys';
        const apiKeyExclude = new Set(['api_key', 'base_url', 'sort_order', 'model_name']);
        // api_key 隐藏、base_url URL超长、sort_order 不重要、model_name 可选冗余
        const keys = Object.keys(items[0]).filter(k =>
            !exclude.has(k) &&
            !k.endsWith('_json') &&
            !(isApiKeys && apiKeyExclude.has(k))
        );
        const displayKeys = keys.slice(0, 10);

        let html = '<div class="data-table-wrapper"><table class="data-table"><thead><tr>';
        displayKeys.forEach(k => html += `<th>${this._formatLabel(k)}</th>`);
        if (actions) html += '<th style="width:120px">操作</th>';
        html += '</tr></thead><tbody>';

        items.forEach((item, idx) => {
            const id = item[idKey];
            if (selectable) {
                html += `<tr data-source-id="${id}" onclick="if(event.target.tagName!=='BUTTON')App.selectWatchSource(${id})">`;
            } else {
                html += '<tr>';
            }
            displayKeys.forEach(k => {
                const val = this._getNestedValue(item, k);
                const rendered = this._formatCellValue(k, val, item);
                html += `<td title="${this._escapeHtml(String(rendered).replace(/<[^>]*>/g, ''))}">${rendered}</td>`;
            });
            if (actions) {
                const id = item[idKey];
                // API Key 增加"查看详情"按钮
                if (isApiKeys) {
                    html += `<td class="action-cell">
                        <button class="btn btn-xs btn-ghost" onclick="API.viewApiKeyDetail(${id})" title="查看详情">👁️</button>
                        <button class="btn btn-xs btn-ghost" onclick="API.editApiKey(${id})" title="编辑">✏️</button>
                        <button class="btn btn-xs btn-ghost" onclick="API.deleteItem('${container.id}', ${id})" title="删除">🗑️</button>
                    </td>`;
                } else if (container.id === 'watch-sources') {
                    // 瞭望源列表：增加"立刻采集"按钮
                    html += `<td class="action-cell">
                        <button class="btn btn-xs btn-success" onclick="App.triggerCollect(${id})" title="立刻采集">⚡ 采集</button>
                        <button class="btn btn-xs btn-ghost" onclick="API.editItem('${container.id}', ${id})" title="编辑">✏️</button>
                        <button class="btn btn-xs btn-ghost" onclick="API.deleteItem('${container.id}', ${id})" title="删除">🗑️</button>
                    </td>`;
        } else if (container.id === 'watch-data') {
            // 采集数据列表：增加"查看详情"按钮
            html += `<td class="action-cell">
                <button class="btn btn-xs btn-primary" onclick="API.viewWatchDataDetail(${id})" title="查看详情">👁️ 详情</button>
            </td>`;
        } else if (container.id === 'cleaning-logs') {
            // 清洗日志列表：增加"详情"和"重试"按钮
            html += `<td class="action-cell">
                <button class="btn btn-xs btn-primary" onclick="API.viewCleaningDetail(${id})" title="查看详情">👁️ 详情</button>
                <button class="btn btn-xs btn-warning" onclick="App.retryCleaning(${id})" title="重新清洗">🔄 重试</button>
            </td>`;
        } else {
                    html += `<td class="action-cell">
                        <button class="btn btn-xs btn-ghost" onclick="API.editItem('${container.id}', ${id})" title="编辑">✏️</button>
                        <button class="btn btn-xs btn-ghost" onclick="API.deleteItem('${container.id}', ${id})" title="删除">🗑️</button>
                    </td>`;
                }
            }
            html += '</tr>';
        });

        html += '</tbody></table></div>';
        // 添加总记录数
        if (items._total !== undefined) {
            html += `<div class="table-footer">共 ${items._total} 条记录</div>`;
        }
        container.innerHTML = html;

        // 存储数据供编辑使用
        container._data = items;
    },

    /** 渲染统计卡片 */
    renderStats(data, container) {
        if (!container) return;
        if (!data || Object.keys(data).length === 0) {
            container.innerHTML = '<div class="empty-state">暂无统计数据</div>';
            return;
        }

        const exclude = new Set(['_json', 'distribution', 'top_words_json', 'top_events_json']);
        const entries = Object.entries(data).filter(([k, v]) => !exclude.has(k) && v !== null && typeof v !== 'object');
        let html = '<div class="stats-grid">';
        entries.forEach(([k, v]) => {
            html += `<div class="stat-card">
                <div class="stat-value">${this._formatValue(v)}</div>
                <div class="stat-label">${this._formatLabel(k)}</div>
            </div>`;
        });
        html += '</div>';

        // 如果有 distribution 数据
        if (data.distribution && typeof data.distribution === 'object') {
            html += '<div class="stats-distribution"><h4>分布情况</h4><div class="distr-list">';
            Object.entries(data.distribution).forEach(([k, v]) => {
                const total = Object.values(data.distribution).reduce((a, b) => a + b, 0);
                const pct = total > 0 ? ((v / total) * 100).toFixed(1) : 0;
                html += `<div class="distr-item"><span class="distr-label">${k}</span>
                    <div class="distr-bar"><div class="distr-fill" style="width:${pct}%"></div></div>
                    <span class="distr-value">${v}</span></div>`;
            });
            html += '</div></div>';
        }

        container.innerHTML = html;
    },

    /** 渲染详情卡片 */
    renderDetail(data, container) {
        if (!container) return;
        if (!data) {
            container.innerHTML = '<div class="empty-state">暂无数据</div>';
            return;
        }
        let html = '<div class="detail-view">';
        Object.entries(data).forEach(([k, v]) => {
            if (k === 'id' || k.endsWith('_json') || k === 'avatar') return;
            html += `<div class="detail-row">
                <span class="detail-label">${this._formatLabel(k)}</span>
                <span class="detail-value">${this._formatCellValue(k, v, data)}</span>
            </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    },

    /** 渲染列表（卡片式） */
    renderList(items, container) {
        if (!container) return;
        if (!items || items.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无数据</div>';
            return;
        }
        let html = '<div class="list-view">';
        items.forEach(item => {
            const title = item.name || item.title || item.username || `#${item.id}`;
            const desc = item.description || item.content || '';
            html += `<div class="list-item" data-id="${item.id}">
                <div class="list-item-icon">${item.icon || '📄'}</div>
                <div class="list-item-body">
                    <div class="list-item-title">${this._escapeHtml(title)}</div>
                    ${desc ? `<div class="list-item-desc">${this._escapeHtml(desc.slice(0, 100))}</div>` : ''}
                </div>
                <div class="list-item-actions">
                    <button class="btn btn-xs btn-ghost" onclick="API.editItem('${container.id}', ${item.id})">✏️</button>
                    <button class="btn btn-xs btn-ghost" onclick="API.deleteItem('${container.id}', ${item.id})">🗑️</button>
                </div>
            </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
        container._data = items;
    },

    /** 渲染卡片集合 */
    renderCards(items, container) {
        if (!container) return;
        if (!items || items.length === 0) {
            container.innerHTML = '<div class="empty-state">暂无数据</div>';
            return;
        }
        let html = '<div class="card-grid-inline">';
        items.forEach(item => {
            html += `<div class="mini-card" data-id="${item.id}">
                <div class="mini-card-icon">${item.icon || '📄'}</div>
                <div class="mini-card-title">${this._escapeHtml(item.name || item.title || '')}</div>
                <div class="mini-card-sub">${item.description || ''}</div>
            </div>`;
        });
        html += '</div>';
        container.innerHTML = html;
    },

    /** 内联数据显示（文本） */
    renderInline(data, container) {
        if (!container) return;
        if (data === null || data === undefined) {
            container.innerHTML = '<span class="text-muted">-</span>';
            return;
        }
        if (typeof data === 'string') {
            container.textContent = data;
        } else if (typeof data === 'object') {
            container.innerHTML = `<pre>${this._escapeHtml(JSON.stringify(data, null, 2))}</pre>`;
        } else {
            container.textContent = String(data);
        }
    },

    // ========== CRUD 操作 ==========
    _getModuleByContainerId(containerId) {
        // 从容器ID推断模块名，如 "watch-sources-list" -> "watch"
        const segments = containerId.split('-');
        return segments[0];
    },

    _getApiPathByContainerId(containerId, id = null) {
        // 映射容器ID到API路径
        const mapping = {
            'watch-sources': '/api/watch/sources',
            'watch-data': '/api/watch/sources/{id}/data',
            'workers-jobs': '/api/workers/jobs',
            'workers-list': '/api/workers',
            'dispatch-logs': '/api/dispatch/logs',
            'cleaning-logs': '/api/cleaning/logs',
            'warehouse-articles': '/api/warehouse/articles',
            'warehouse-categories': '/api/warehouse/categories',
            'sentiment-analyses': '/api/sentiment/analyses',
            'admin-users': '/api/admin/users',
            'admin-apikeys': '/api/admin/api-keys',
            'admin-configs': '/api/admin/configs',
            'admin-logs': '/api/admin/logs',
            'im-friends': '/api/im/friends',
            'im-groups': '/api/im/groups',
            'im-conversations': '/api/im/conversations',
            'files-list': '/api/files',
            'files-stats': '/api/files/stats',
            'files-upload': '/api/files/upload',
        };
        // 按前缀匹配
        for (const [prefix, path] of Object.entries(mapping)) {
            if (containerId.startsWith(prefix)) {
                if (id && path.includes('{id}')) return path.replace('{id}', id);
                return path;
            }
        }
        return null;
    },

    async editItem(containerId, id) {
        const path = this._getApiPathByContainerId(containerId, id);
        if (!path) {
            this.toast('warning', '提示', '该数据不支持直接编辑');
            return;
        }
        try {
            const res = await this.request('GET', `${path}/${id}`);
            const data = res.data || res;
            this.showEditModal(containerId, id, data, path);
        } catch (err) {
            this.toast('error', '加载详情失败', err.message);
        }
    },

    async deleteItem(containerId, id) {
        if (!confirm('确定要删除这条记录吗？此操作不可撤销。')) return;
        const path = this._getApiPathByContainerId(containerId, id);
        if (!path) {
            this.toast('warning', '提示', '该数据不支持直接删除');
            return;
        }
        try {
            await this.request('DELETE', `${path}/${id}`);
            this.toast('success', '删除成功', '记录已删除');
            // 重新加载
            const container = document.getElementById(containerId);
            if (container) {
                const module = this._getModuleByContainerId(containerId);
                App.loadModuleData(module);
            }
        } catch (err) {
            this.toast('error', '删除失败', err.message);
        }
    },

    showEditModal(containerId, id, data, path) {
        // 构建编辑表单
        const exclude = new Set(['id', 'created_at', 'updated_at', 'avatar']);
        const fields = Object.entries(data).filter(([k]) => !exclude.has(k) && !k.endsWith('_at') && !k.endsWith('_json'));

        let formHtml = fields.map(([k, v]) => {
            const label = this._formatLabel(k);
            const value = typeof v === 'object' ? JSON.stringify(v) : (v || '');
            if (typeof v === 'boolean') {
                return `<label class="modal-form-group"><span class="modal-form-label">${label}</span>
                    <select class="modal-form-select" data-key="${k}">
                        <option value="1" ${v ? 'selected' : ''}>是</option>
                        <option value="0" ${!v ? 'selected' : ''}>否</option>
                    </select></label>`;
            }
            if (k === 'status' || k === 'role' || k === 'method' || k === 'purpose' || k === 'provider') {
                return `<label class="modal-form-group"><span class="modal-form-label">${label}</span>
                    <input class="modal-form-input" data-key="${k}" value="${this._escapeHtml(String(value))}" /></label>`;
            }
            if (String(value).length > 100) {
                return `<label class="modal-form-group"><span class="modal-form-label">${label}</span>
                    <textarea class="modal-form-textarea" data-key="${k}" rows="3">${this._escapeHtml(String(value))}</textarea></label>`;
            }
            return `<label class="modal-form-group"><span class="modal-form-label">${label}</span>
                <input class="modal-form-input" data-key="${k}" value="${this._escapeHtml(String(value))}" /></label>`;
        }).join('');

        const modalHtml = `
            <div class="modal-overlay" id="editModal">
                <div class="modal-dialog">
                    <div class="modal-header">
                        <h3>✏️ 编辑 #${id}</h3>
                        <button class="modal-close" onclick="API.closeEditModal()">×</button>
                    </div>
                    <div class="modal-body">
                        ${formHtml}
                    </div>
                    <div class="modal-footer">
                        <button class="btn btn-sm btn-ghost" onclick="API.closeEditModal()">取消</button>
                        <button class="btn btn-sm btn-primary" onclick="API.saveEdit('${containerId}', ${id}, '${path}')">💾 保存</button>
                    </div>
                </div>
            </div>`;

        const existing = document.getElementById('editModal');
        if (existing) existing.remove();

        document.body.insertAdjacentHTML('beforeend', modalHtml);
        setTimeout(() => document.getElementById('editModal')?.classList.add('active'), 10);
    },

    closeEditModal() {
        const modal = document.getElementById('editModal');
        if (modal) {
            modal.classList.remove('active');
            setTimeout(() => modal.remove(), 300);
        }
    },

    async saveEdit(containerId, id, path) {
        const modal = document.getElementById('editModal');
        const inputs = modal.querySelectorAll('[data-key]');
        const body = {};
        inputs.forEach(inp => {
            const key = inp.dataset.key;
            let val = inp.value;
            if (inp.tagName === 'SELECT') {
                val = inp.value === '1' || inp.value === 'true' ? 1 : (inp.value === '0' || inp.value === 'false' ? 0 : inp.value);
            }
            body[key] = val;
        });

        try {
            await this.request('PUT', `${path}/${id}`, body);
            this.toast('success', '保存成功', '数据已更新');
            this.closeEditModal();
            const container = document.getElementById(containerId);
            if (container) {
                const module = this._getModuleByContainerId(containerId);
                App.loadModuleData(module);
            }
        } catch (err) {
            this.toast('error', '保存失败', err.message);
        }
    },

    // ========== 模态框通用 ==========
    showModal(title, bodyHtml, footerHtml = '') {
        const existing = document.getElementById('appModal');
        if (existing) existing.remove();

        const html = `
            <div class="modal-overlay" id="appModal">
                <div class="modal-dialog">
                    <div class="modal-header">
                        <h3>${title}</h3>
                        <button class="modal-close" onclick="API.closeModal()">×</button>
                    </div>
                    <div class="modal-body">${bodyHtml}</div>
                    ${footerHtml ? `<div class="modal-footer">${footerHtml}</div>` : ''}
                </div>
            </div>`;
        document.body.insertAdjacentHTML('beforeend', html);
        setTimeout(() => document.getElementById('appModal')?.classList.add('active'), 10);
    },

    closeModal() {
        const modal = document.getElementById('appModal');
        if (modal) {
            modal.classList.remove('active');
            setTimeout(() => modal.remove(), 300);
        }
    },

    // ========== Helper 方法 ==========
    _formatLabel(key) {
        return key
            .replace(/_/g, ' ')
            .replace(/\b\w/g, c => c.toUpperCase())
            .replace(/Id/g, 'ID')
            .replace(/Url/g, 'URL')
            .replace(/Api/g, 'API')
            .replace(/Token/g, 'Token');
    },

    _formatValue(val) {
        if (typeof val === 'number') {
            if (val >= 10000) return (val / 10000).toFixed(1) + '万';
            if (val >= 1000) return (val / 1000).toFixed(1) + 'k';
            return val.toLocaleString();
        }
        return val;
    },

    _getNestedValue(obj, path) {
        return path.split('.').reduce((o, k) => (o && o[k] !== undefined) ? o[k] : null, obj);
    },

    _formatCellValue(key, val, item) {
        if (val === null || val === undefined) return '<span class="text-muted">-</span>';
        if (typeof val === 'boolean') return val ? '✅' : '❌';
        if (typeof val === 'object') return `<span class="text-muted">${JSON.stringify(val).slice(0, 40)}...</span>`;

        const str = String(val);

        // 状态标签
        if (key === 'status' || key.endsWith('_status')) {
            const statusMap = {
                'success': 'tag-success', 'completed': 'tag-success', 'active': 'tag-success', 'online': 'tag-success', 'published': 'tag-success',
                'failed': 'tag-danger', 'error': 'tag-danger', 'disabled': 'tag-danger', 'banned': 'tag-danger', 'offline': 'tag-danger',
                'processing': 'tag-warning', 'pending': 'tag-warning', 'draft': 'tag-warning',
            };
            const cls = statusMap[str.toLowerCase()] || 'tag-default';
            return `<span class="tag ${cls}">${str}</span>`;
        }

        // 时间格式化
        if (key.endsWith('_at') || key === 'created_at' || key === 'updated_at') {
            try {
                return new Date(val).toLocaleString('zh-CN');
            } catch { return str; }
        }

        // 启用状态
        if (key === 'enabled' || key === 'is_preset' || key === 'is_builtin' || key === 'is_blocked') {
            return val == 1 ? '✅' : '❌';
        }

        // URL
        if (key === 'url' || key.endsWith('_url')) {
            return str.length > 40 ? str.slice(0, 40) + '…' : str;
        }

        // 长文本截断
        if (str.length > 80) return str.slice(0, 80) + '…';
        return str;
    },

    // ========== API Key 详情查看与编辑 ==========

    /** 查看 API Key 详情 */
    async viewApiKeyDetail(keyId) {
        try {
            const res = await this.request('GET', `/api/admin/api-keys/${keyId}`);
            const data = res.data || res;
            if (!data) {
                this.toast('error', '加载失败', 'API密钥不存在');
                return;
            }

            const fields = [
                { label: '🔑 名称', value: data.name || '-' },
                { label: '🏢 提供方', value: data.provider || '-' },
                { label: '🔗 Base URL', value: data.base_url || '-' },
                { label: '🧠 模型', value: data.model_name || '-' },
                { label: '🎯 用途', value: data.purpose || '-' },
                { label: '📏 Max Tokens', value: data.max_tokens ?? '-' },
                { label: '🌡️ Temperature', value: data.temperature ?? '-' },
                { label: '⬆️ Top P', value: data.top_p ?? '-' },
                { label: '✅ 启用', value: data.enabled == 1 ? '是 ✅' : '否 ❌' },
                { label: '📊 排序', value: data.sort_order ?? '-' },
                { label: '📅 创建时间', value: data.created_at ? new Date(data.created_at).toLocaleString('zh-CN') : '-' },
                { label: '🔄 更新时间', value: data.updated_at ? new Date(data.updated_at).toLocaleString('zh-CN') : '-' },
            ];

            const bodyHtml = fields.map(f =>
                `<div class="detail-row" style="padding:6px 0;border-bottom:1px solid var(--border);display:flex;gap:12px">
                    <span style="min-width:120px;font-weight:500;color:var(--text-light)">${f.label}</span>
                    <span style="word-break:break-all">${this._escapeHtml(String(f.value))}</span>
                </div>`
            ).join('');

            this.showModal(`👁️ API Key 详情 #${keyId}`, bodyHtml,
                `<button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`
            );
        } catch (err) {
            this.toast('error', '加载详情失败', err.message);
        }
    },

    /** 编辑 API Key（专用表单替代通用弹窗） */
    async editApiKey(keyId) {
        try {
            const res = await this.request('GET', `/api/admin/api-keys/${keyId}`);
            const data = res.data || res;
            if (!data) {
                this.toast('error', '加载失败', 'API密钥不存在');
                return;
            }

            // 屏蔽真实的 api_key 显示，用占位符表示
            const purposeOptions = ['chat', 'dataworker', 'all'];
            const providerOptions = ['openai', 'azure', 'google', 'custom'];

            const formHtml = `
                <label class="modal-form-group"><span class="modal-form-label">名称 *</span>
                    <input class="modal-form-input" id="apikey-edit-name" value="${this._escapeHtml(data.name || '')}" /></label>
                <label class="modal-form-group"><span class="modal-form-label">提供方</span>
                    <select class="modal-form-select" id="apikey-edit-provider">
                        ${providerOptions.map(p => `<option value="${p}" ${data.provider === p ? 'selected' : ''}>${p}</option>`).join('')}
                    </select></label>
                <label class="modal-form-group"><span class="modal-form-label">Base URL</span>
                    <input class="modal-form-input" id="apikey-edit-baseurl" value="${this._escapeHtml(data.base_url || '')}" /></label>
                <label class="modal-form-group"><span class="modal-form-label">API Key（留空不修改）</span>
                    <input class="modal-form-input" id="apikey-edit-key" type="password" placeholder="输入新 Key 以替换..." /></label>
                <label class="modal-form-group"><span class="modal-form-label">模型名称</span>
                    <input class="modal-form-input" id="apikey-edit-model" value="${this._escapeHtml(data.model_name || '')}" /></label>
                <label class="modal-form-group"><span class="modal-form-label">用途</span>
                    <select class="modal-form-select" id="apikey-edit-purpose">
                        ${purposeOptions.map(p => `<option value="${p}" ${data.purpose === p ? 'selected' : ''}>${p}</option>`).join('')}
                    </select></label>
                <label class="modal-form-group"><span class="modal-form-label">Max Tokens</span>
                    <input class="modal-form-input" id="apikey-edit-maxtokens" type="number" value="${data.max_tokens ?? 4096}" /></label>
                <label class="modal-form-group"><span class="modal-form-label">Temperature</span>
                    <input class="modal-form-input" id="apikey-edit-temperature" type="number" step="0.1" min="0" max="2" value="${data.temperature ?? 0.7}" /></label>
                <label class="modal-form-group"><span class="modal-form-label">Top P</span>
                    <input class="modal-form-input" id="apikey-edit-topp" type="number" step="0.1" min="0" max="1" value="${data.top_p ?? 1.0}" /></label>
                <label class="modal-form-group"><span class="modal-form-label">排序</span>
                    <input class="modal-form-input" id="apikey-edit-sort" type="number" value="${data.sort_order ?? 0}" /></label>
                <label class="modal-form-group"><span class="modal-form-label">启用</span>
                    <select class="modal-form-select" id="apikey-edit-enabled">
                        <option value="1" ${data.enabled == 1 ? 'selected' : ''}>是</option>
                        <option value="0" ${data.enabled != 1 ? 'selected' : ''}>否</option>
                    </select></label>
            `;

            const footerHtml = `
                <button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
                <button class="btn btn-sm btn-primary" onclick="API.saveApiKeyEdit(${keyId})">💾 保存</button>
            `;

            this.showModal(`✏️ 编辑 API Key #${keyId}`, formHtml, footerHtml);
        } catch (err) {
            this.toast('error', '加载失败', err.message);
        }
    },

    /** 保存 API Key 编辑 */
    async saveApiKeyEdit(keyId) {
        const body = {};

        // 名称
        const name = document.getElementById('apikey-edit-name')?.value?.trim();
        if (name) body.name = name;

        // 基本字段
        body.provider = document.getElementById('apikey-edit-provider')?.value || 'openai';
        body.base_url = document.getElementById('apikey-edit-baseurl')?.value?.trim() || '';
        body.model_name = document.getElementById('apikey-edit-model')?.value?.trim() || '';
        body.purpose = document.getElementById('apikey-edit-purpose')?.value || 'chat';

        // 数值字段
        body.max_tokens = parseInt(document.getElementById('apikey-edit-maxtokens')?.value) || 4096;
        body.temperature = parseFloat(document.getElementById('apikey-edit-temperature')?.value) || 0.7;
        body.top_p = parseFloat(document.getElementById('apikey-edit-topp')?.value) || 1.0;
        body.sort_order = parseInt(document.getElementById('apikey-edit-sort')?.value) || 0;
        body.enabled = parseInt(document.getElementById('apikey-edit-enabled')?.value) || 0;

        // API Key（可选修改）
        const apiKey = document.getElementById('apikey-edit-key')?.value?.trim();
        if (apiKey) body.api_key = apiKey;

        if (!body.name) {
            this.toast('warning', '表单不完整', '请输入名称');
            return;
        }

        try {
            await this.request('PUT', `/api/admin/api-keys/${keyId}`, body);
            this.toast('success', '保存成功', 'API Key 已更新');
            this.closeModal();
            // 刷新列表
            const container = document.getElementById('admin-apikeys');
            if (container) App.loadModuleData('admin');
        } catch (err) {
            this.toast('error', '保存失败', err.message);
        }
    },
    // ========== 瞭望采集数据详情查看 ==========
    async viewWatchDataDetail(dataId) {
        try {
            const res = await this.request('GET', `/api/watch/data/${dataId}`);
            const data = res.data || res;
            if (!data) {
                this.toast('error', '加载失败', '采集数据不存在');
                return;
            }

            const fields = [
                { label: '📋 数据 ID', value: data.id ?? '-' },
                { label: '📡 瞭望源 ID', value: data.source_id ?? '-' },
                { label: '🔴 状态', value: data.status || '-' },
                { label: '🌐 HTTP 状态码', value: data.http_status ?? '-' },
                { label: '📅 采集时间', value: data.collected_at ? new Date(data.collected_at).toLocaleString('zh-CN') : '-' },
                { label: '❌ 错误信息', value: data.error_message || '无', isLong: !!data.error_message },
                { label: '📄 原始响应', value: data.raw_response || '无', isLong: true },
                { label: '📊 解析后的 JSON', value: data.parsed_data || '无（非JSON格式）', isLong: true },
            ];

            const bodyHtml = fields.map(f =>
                `<div class="detail-row" style="padding:8px 0;border-bottom:1px solid var(--border);display:flex;gap:12px;flex-direction:${f.isLong ? 'column' : 'row'}">
                    <span style="min-width:120px;font-weight:500;color:var(--text-light);flex-shrink:0">${f.label}</span>
                    ${f.isLong
                        ? `<pre style="margin:4px 0 0 0;background:var(--bg-input);padding:12px;border-radius:var(--radius-xs);font-size:13px;line-height:1.5;max-height:300px;overflow:auto;white-space:pre-wrap;word-break:break-all;color:var(--text)">${this._escapeHtml(String(f.value))}</pre>`
                        : `<span style="word-break:break-all;color:var(--text)">${this._escapeHtml(String(f.value))}</span>`
                    }
                </div>`
            ).join('');

            this.showModal(`👁️ 采集数据详情 #${dataId}`,
                `<div class="detail-view" style="max-height:70vh;overflow-y:auto">${bodyHtml}</div>`,
                `<button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`
            );
        } catch (err) {
            this.toast('error', '加载详情失败', err.message);
        }
    },

    // ========== 知识仓库文章编辑 ==========
    
    /** 编辑仓库文章（专用表单） */
    async editWarehouseArticle(articleId) {
        try {
            const res = await this.request('GET', `/api/warehouse/articles/${articleId}`);
            const data = res.data || res;
            if (!data) {
                this.toast('error', '加载失败', '文章不存在');
                return;
            }
            
            // 加载分类列表
            let catOptions = '<option value="">-- 无分类 --</option>';
            try {
                const catRes = await this.request('GET', '/api/warehouse/categories');
                const cats = catRes.data || [];
                cats.forEach(c => {
                    const selected = c.id === data.category_id ? 'selected' : '';
                    catOptions += `<option value="${c.id}" ${selected}>${c.icon || '📁'} ${c.name}</option>`;
                });
            } catch {}

            const formHtml = `
                <div class="modal-form-group">
                    <span class="modal-form-label">标题 *</span>
                    <input class="modal-form-input" id="wh-edit-title" value="${this._escapeHtml(data.title || '')}" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">分类</span>
                    <select class="modal-form-select" id="wh-edit-category">${catOptions}</select>
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">域名</span>
                    <input class="modal-form-input" id="wh-edit-domain" value="${this._escapeHtml(data.domain_name || '')}" />
                    <div style="font-size:11px;color:var(--text-light);margin-top:4px">💡 修改URL时域名自动提取，也可手动修改</div>
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">原文 URL</span>
                    <input class="modal-form-input" id="wh-edit-url" value="${this._escapeHtml(data.url || '')}" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">标签（逗号分隔）</span>
                    <input class="modal-form-input" id="wh-edit-tags" value="${this._escapeHtml(data.tags || '')}" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">状态</span>
                    <select class="modal-form-select" id="wh-edit-status">
                        <option value="draft" ${data.status === 'draft' ? 'selected' : ''}>📝 草稿</option>
                        <option value="published" ${data.status === 'published' ? 'selected' : ''}>✅ 已发布</option>
                    </select>
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">内容</span>
                    <textarea class="modal-form-textarea" id="wh-edit-content" rows="8">${this._escapeHtml(data.content || '')}</textarea>
                </div>`;

            this.showModal(`✏️ 编辑文章 #${articleId}`, formHtml,
                `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
                 <button class="btn btn-sm btn-primary" onclick="API.saveWarehouseArticle(${articleId})">💾 保存</button>`
            );
        } catch (err) {
            this.toast('error', '加载失败', err.message);
        }
    },

    /** 保存仓库文章编辑 */
    async saveWarehouseArticle(articleId) {
        const body = {};
        const title = document.getElementById('wh-edit-title')?.value?.trim();
        if (title) body.title = title;
        
        const categoryId = parseInt(document.getElementById('wh-edit-category')?.value);
        if (categoryId) body.category_id = categoryId;
        
        const domain = document.getElementById('wh-edit-domain')?.value?.trim();
        if (domain !== undefined) body.domain_name = domain;
        
        body.url = document.getElementById('wh-edit-url')?.value?.trim() || '';
        body.tags = document.getElementById('wh-edit-tags')?.value?.trim() || '';
        body.status = document.getElementById('wh-edit-status')?.value || 'draft';
        body.content = document.getElementById('wh-edit-content')?.value?.trim() || '';

        if (!body.title) {
            this.toast('warning', '提示', '请输入文章标题');
            return;
        }

        try {
            await this.request('PUT', `/api/warehouse/articles/${articleId}`, body);
            this.toast('success', '保存成功', '文章已更新');
            this.closeModal();
            App.loadWarehouseArticles();
        } catch (err) {
            this.toast('error', '保存失败', err.message);
        }
    },

    /** 编辑仓库分类 */
    async editWarehouseCategory(categoryId) {
        try {
            const res = await this.request('GET', '/api/warehouse/categories');
            const categories = res.data || [];
            const cat = categories.find(c => c.id === categoryId);
            if (!cat) {
                this.toast('error', '加载失败', '分类不存在');
                return;
            }

            const formHtml = `
                <div class="modal-form-group">
                    <span class="modal-form-label">分类名称 *</span>
                    <input class="modal-form-input" id="wh-catedit-name" value="${this._escapeHtml(cat.name || '')}" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">图标</span>
                    <input class="modal-form-input" id="wh-catedit-icon" value="${this._escapeHtml(cat.icon || '📁')}" />
                </div>
                <div class="modal-form-group">
                    <span class="modal-form-label">描述</span>
                    <input class="modal-form-input" id="wh-catedit-desc" value="${this._escapeHtml(cat.description || '')}" />
                </div>`;

            this.showModal(`✏️ 编辑分类 #${categoryId}`, formHtml,
                `<button class="btn btn-sm btn-ghost" onclick="API.closeModal()">取消</button>
                 <button class="btn btn-sm btn-primary" onclick="API.saveWarehouseCategory(${categoryId})">💾 保存</button>`
            );
        } catch (err) {
            this.toast('error', '加载失败', err.message);
        }
    },

    /** 保存仓库分类编辑 */
    async saveWarehouseCategory(categoryId) {
        const name = document.getElementById('wh-catedit-name')?.value?.trim();
        if (!name) { this.toast('warning', '提示', '请输入分类名称'); return; }
        try {
            await this.request('PUT', `/api/warehouse/categories/${categoryId}`, {
                name,
                icon: document.getElementById('wh-catedit-icon')?.value?.trim() || '📁',
                description: document.getElementById('wh-catedit-desc')?.value?.trim() || '',
            });
            this.toast('success', '保存成功', '分类已更新');
            this.closeModal();
            App.loadWarehouseCategories();
        } catch (err) {
            this.toast('error', '保存失败', err.message);
        }
    },

    // ========== 仓库文章详情查看 ==========
    async viewArticleDetail(articleId) {
        try {
            const res = await this.request('GET', `/api/warehouse/articles/${articleId}`);
            const data = res.data || res;
            if (!data) {
                this.toast('error', '加载失败', '文章不存在');
                return;
            }

            const fields = [
                { label: '📋 文章 ID', value: data.id ?? '-' },
                { label: '📰 标题', value: data.title || '-' },
                { label: '🌐 域名', value: data.domain_name || '-' },
                { label: '🏷️ 标签', value: data.tags || '-' },
                { label: '📎 URL', value: data.url || '-' },
                { label: '🔴 状态', value: data.status || '-' },
                { label: '📂 分类', value: data.category_name || '-' },
                { label: '📅 创建时间', value: data.created_at ? new Date(data.created_at).toLocaleString('zh-CN') : '-' },
                { label: '📄 内容', value: data.content ? data.content.slice(0, 2000) : '无', isLong: true },
            ];

            const bodyHtml = fields.map(f =>
                `<div class="detail-row" style="padding:8px 0;border-bottom:1px solid var(--border);display:flex;gap:12px;flex-direction:${f.isLong ? 'column' : 'row'}">
                    <span style="min-width:100px;font-weight:500;color:var(--text-light);flex-shrink:0">${f.label}</span>
                    ${f.isLong
                        ? `<pre style="margin:4px 0 0 0;background:var(--bg-input);padding:12px;border-radius:var(--radius-xs);font-size:13px;line-height:1.5;max-height:300px;overflow:auto;white-space:pre-wrap;word-break:break-all;color:var(--text)">${this._escapeHtml(String(f.value))}</pre>`
                        : `<span style="word-break:break-all;color:var(--text)">${this._escapeHtml(String(f.value))}</span>`
                    }
                </div>`
            ).join('');

            this.showModal(`👁️ 文章详情 #${articleId}`,
                `<div class="detail-view" style="max-height:70vh;overflow-y:auto">${bodyHtml}</div>`,
                `<button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`
            );
        } catch (err) {
            this.toast('error', '加载详情失败', err.message);
        }
    },

    // ========== 清洗日志详情查看 ==========
    async viewCleaningDetail(logId) {
        try {
            const res = await this.request('GET', `/api/cleaning/logs/${logId}`);
            const data = res.data || res;
            if (!data) {
                this.toast('error', '加载失败', '清洗日志不存在');
                return;
            }

            const fields = [
                { label: '📋 日志 ID', value: data.id ?? '-' },
                { label: '📡 瞭望数据 ID', value: data.watch_data_id ?? '-' },
                { label: '🧹 清洗方法', value: data.method || '-' },
                { label: '🔴 状态', value: data.status || '-' },
                { label: '📋 文章 ID', value: data.article_id ?? '-' },
                { label: '📰 文章标题', value: data.article_title || '-' },
                { label: '📋 执行记录 ID', value: data.execution_log_id ?? '-' },
                { label: '🔴 执行状态', value: data.execution_status || '-' },
                { label: '📅 创建时间', value: data.created_at ? new Date(data.created_at).toLocaleString('zh-CN') : '-' },
                { label: '❌ 错误信息', value: data.error_message || '无', isLong: !!data.error_message },
                { label: '📄 原始数据（前500字）', value: data.watch_data_raw || '无', isLong: true },
                { label: '📊 清洗结果', value: data.result || '无', isLong: true },
            ];

            const bodyHtml = fields.map(f =>
                `<div class="detail-row" style="padding:8px 0;border-bottom:1px solid var(--border);display:flex;gap:12px;flex-direction:${f.isLong ? 'column' : 'row'}">
                    <span style="min-width:140px;font-weight:500;color:var(--text-light);flex-shrink:0">${f.label}</span>
                    ${f.isLong
                        ? `<pre style="margin:4px 0 0 0;background:var(--bg-input);padding:12px;border-radius:var(--radius-xs);font-size:13px;line-height:1.5;max-height:300px;overflow:auto;white-space:pre-wrap;word-break:break-all;color:var(--text)">${this._escapeHtml(String(f.value))}</pre>`
                        : `<span style="word-break:break-all;color:var(--text)">${this._escapeHtml(String(f.value))}</span>`
                    }
                </div>`
            ).join('');

            this.showModal(`👁️ 清洗日志详情 #${logId}`,
                `<div class="detail-view" style="max-height:70vh;overflow-y:auto">${bodyHtml}</div>`,
                `<button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`
            );
        } catch (err) {
            this.toast('error', '加载详情失败', err.message);
        }
    },

    // ========== SSE 流式处理 ==========
    async sendChatMessage(conversationId, content, outputEl) {
        if (!conversationId || !content) {
            this.toast('warning', '表单不完整', '请填写对话ID和消息内容');
            return;
        }

        if (outputEl) {
            outputEl.className = 'sse-output';
            outputEl.innerHTML = '';
        }

        try {
            const headers = {
                'Content-Type': 'application/json',
                'Accept': 'text/event-stream'
            };
            if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

            const response = await fetch(`${this.BASE_URL}/api/chat/message`, {
                method: 'POST',
                headers,
                body: JSON.stringify({ content, conversation_id: parseInt(conversationId) })
            });

            if (!response.ok) {
                const errData = await response.json().catch(() => ({}));
                if (outputEl) outputEl.textContent = `❌ 错误: ${errData.message || response.statusText}`;
                this.toast('error', '消息发送失败', `HTTP ${response.status}`);
                return;
            }

            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';

            function processChunk(chunk) {
                buffer += chunk;
                const lines = buffer.split('\n');
                buffer = lines.pop() || '';
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        const dataStr = line.slice(6).trim();
                        if (dataStr === '[DONE]' || !dataStr) {
                            if (outputEl) {
                                const done = document.createElement('div');
                                done.className = 'sse-done';
                                done.textContent = '✓ 响应完成';
                                outputEl.appendChild(done);
                            }
                            continue;
                        }
                        try {
                            const parsed = JSON.parse(dataStr);
                            let text = '';
                            if (parsed.choices && parsed.choices[0] && parsed.choices[0].delta) {
                                text = parsed.choices[0].delta.content || '';
                            } else if (parsed.content) {
                                text = parsed.content;
                            } else if (parsed._meta) {
                                text = '\n\n--- 📋 元信息 ---\n' + JSON.stringify(parsed._meta, null, 2);
                            }
                            if (outputEl && text) {
                                const span = document.createElement('span');
                                span.className = 'token';
                                span.textContent = text;
                                outputEl.appendChild(span);
                                outputEl.scrollTop = outputEl.scrollHeight;
                            }
                        } catch {
                            if (outputEl && dataStr) outputEl.textContent += dataStr;
                        }
                    }
                }
            }

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    if (buffer) processChunk(buffer + '\n');
                    break;
                }
                processChunk(decoder.decode(value, { stream: true }));
            }
        } catch (err) {
            if (outputEl) outputEl.innerHTML += `\n\n❌ 错误: ${err.message}`;
            this.toast('error', '流式请求失败', err.message);
        }
    },

    // ========== WebSocket 客户端 ==========
    
    /** WebSocket 连接实例 */
    _ws: null,
    /** WebSocket 事件监听器 */
    _wsListeners: {},
    /** WebSocket 重连状态 */
    _wsReconnectTimer: null,
    _wsReconnecting: false,
    
    /**
     * 建立 WebSocket 连接
     * 使用页面当前 origin（开发服务器代理 /ws 到后端）
     */
    connectWS() {
        if (this._ws && (this._ws.readyState === WebSocket.OPEN || this._ws.readyState === WebSocket.CONNECTING)) {
            return; // 已有连接
        }
        if (!this.token) return;
        
        try {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            const wsUrl = `${protocol}//${window.location.host}/ws?token=${encodeURIComponent(this.token)}`;
            
            this._ws = new WebSocket(wsUrl);
            
            this._ws.onopen = () => {
                console.log('[WS] 已连接');
                this._wsReconnecting = false;
                if (this._wsReconnectTimer) {
                    clearTimeout(this._wsReconnectTimer);
                    this._wsReconnectTimer = null;
                }
            };
            
            this._ws.onmessage = (event) => {
                try {
                    const msg = JSON.parse(event.data);
                    const eventType = msg.type;
                    const eventData = msg.data || {};
                    
                    console.log(`[WS 📥 消息接收] type="${eventType}"`, 
                        eventData && eventData.content ? 
                            { type: eventType, content_preview: eventData.content.slice(0, 60), message_id: eventData.message_id, sender_id: eventData.sender_id, receiver_type: eventData.receiver_type, receiver_id: eventData.receiver_id, is_ai_reply: eventData.is_ai_reply, full_data: eventData } 
                        : eventData);
                    
                    // 触发注册的事件监听器
                    if (eventType && this._wsListeners[eventType]) {
                        const listenerCount = this._wsListeners[eventType].length;
                        console.log(`[WS 📋 事件分发] type="${eventType}", 有 ${listenerCount} 个处理器`);
                        this._wsListeners[eventType].forEach(cb => {
                            try { cb(eventData); } catch (e) { console.warn('[WS] 事件处理异常:', e); }
                        });
                    } else {
                        if (eventType) {
                            console.log(`[WS ⏭️ 未分派] type="${eventType}" 没有注册的事件处理器`);
                        }
                    }
                    
                    // 处理心跳
                    if (eventType === 'ping') {
                        console.log('[WS 💓 心跳] 收到 ping，发送 pong');
                        this._ws.send(JSON.stringify({ type: 'pong' }));
                    }
                    
                    // 处理离线消息加载完成
                    if (eventType === 'offline_messages') {
                        console.log('[WS 📦 离线消息] 已加载:', eventData);
                    }
                } catch (e) {
                    console.warn('[WS ❌ 消息解析失败]', e, '原始数据:', event.data);
                }
            };
            
            this._ws.onclose = (event) => {
                console.log('[WS] 连接关闭:', event.code, event.reason);
                this._ws = null;
                // 自动重连
                this._scheduleWSReconnect();
            };
            
            this._ws.onerror = (error) => {
                console.warn('[WS] 连接错误:', error);
            };
        } catch (e) {
            console.warn('[WS] 连接失败:', e);
            this._scheduleWSReconnect();
        }
    },
    
    /** 调度 WebSocket 自动重连 */
    _scheduleWSReconnect() {
        if (this._wsReconnecting) return;
        this._wsReconnecting = true;
        this._wsReconnectTimer = setTimeout(() => {
            this._wsReconnecting = false;
            if (!this._ws || this._ws.readyState !== WebSocket.OPEN) {
                this.connectWS();
            }
        }, 5000); // 5秒后重连
    },
    
    /**
     * 注册 WebSocket 事件监听
     * @param {string} event - 事件名 (new_message, group_message, friend_request 等)
     * @param {function} callback - 回调函数
     */
    onWS(event, callback) {
        if (!this._wsListeners[event]) {
            this._wsListeners[event] = [];
        }
        this._wsListeners[event].push(callback);
    },
    
    /**
     * 移除 WebSocket 事件监听
     * @param {string} event - 事件名
     * @param {function} callback - 要移除的回调函数
     */
    offWS(event, callback) {
        if (!this._wsListeners[event]) return;
        this._wsListeners[event] = this._wsListeners[event].filter(cb => cb !== callback);
    },
    
    /**
     * 发送 WebSocket 消息
     * @param {object} data - 要发送的数据
     */
    sendWS(data) {
        if (this._ws && this._ws.readyState === WebSocket.OPEN) {
            this._ws.send(JSON.stringify(data));
        }
    },
    
    /** 断开 WebSocket 连接 */
    disconnectWS() {
        if (this._wsReconnectTimer) {
            clearTimeout(this._wsReconnectTimer);
            this._wsReconnectTimer = null;
        }
        this._wsReconnecting = false;
        if (this._ws) {
            this._ws.onclose = null;
            this._ws.close();
            this._ws = null;
        }
        this._wsListeners = {};
    },
    
    // ========== IM 模块 API 方法 ==========

    /** 获取好友列表 */
    async getFriends(search = '') {
        const params = search ? `?search=${encodeURIComponent(search)}` : '';
        const res = await this.request('GET', `/api/im/friends${params}`);
        return res.data || [];
    },

    /** 搜索用户 */
    async searchUsers(keyword) {
        const res = await this.request('POST', '/api/im/friends/search', { keyword });
        return res.data || [];
    },

    /** 发送好友申请 */
    async sendFriendRequest(userId, message) {
        const res = await this.request('POST', '/api/im/friend-requests', {
            receiver_id: userId,
            message: message || ''
        });
        return res.data || {};
    },

    /** 获取好友申请列表 */
    async getFriendRequests(type = null) {
        const res = await this.request('GET', '/api/im/friend-requests');
        const data = res.data || { received: [], sent: [] };
        if (type === 'received') return data.received || [];
        if (type === 'sent') return data.sent || [];
        return data;
    },

    /** 处理好友申请 */
    async handleFriendRequest(requestId, action) {
        const res = await this.request('POST', '/api/im/friend-requests/handle', {
            request_id: requestId,
            action: action  // 'accept' or 'reject'
        });
        return res;
    },

    /** 修改好友备注 */
    async setFriendRemark(friendId, remark) {
        const res = await this.request('PUT', '/api/im/friends/remark', {
            friend_id: friendId,
            remark: remark
        });
        return res;
    },

    /** 删除好友 */
    async deleteFriend(friendId) {
        const res = await this.request('DELETE', `/api/im/friends/${friendId}`);
        return res;
    },

    /** 获取群组列表 */
    async getGroups() {
        const res = await this.request('GET', '/api/im/groups');
        return res.data || [];
    },

    /** 获取群组详情 */
    async getGroupDetail(groupId) {
        const res = await this.request('GET', `/api/im/groups/${groupId}`);
        return res.data || {};
    },

    /** 获取群组成员列表（供@弹出选择） */
    async getGroupMembers(groupId) {
        const res = await this.request('GET', `/api/im/groups/${groupId}/members`);
        return res.data || [];
    },

    /** 添加群组成员 */
    async addGroupMembers(groupId, userIds) {
        const res = await this.request('POST', `/api/im/groups/${groupId}/members`, {
            user_ids: userIds
        });
        return res.data || {};
    },

    /** 移除群组成员 */
    async removeGroupMember(groupId, memberId) {
        const res = await this.request('DELETE', `/api/im/groups/${groupId}/members/${memberId}`);
        return res;
    },

    /** 更新群信息 */
    async updateGroup(groupId, data) {
        const res = await this.request('PUT', `/api/im/groups/${groupId}`, data);
        return res.data || {};
    },

    /** 解散群组 */
    async dismissGroup(groupId) {
        const res = await this.request('DELETE', `/api/im/groups/${groupId}`);
        return res;
    },

    /** 管理后台-封禁/解封群组 */
    async adminBanGroup(groupId, action) {
        const res = await this.request('PUT', `/api/im/admin/groups/${groupId}/status`, { action });
        return res;
    },

    /** 管理后台-发送系统公告 */
    async adminSendAnnouncement(groupId, announcement) {
        const res = await this.request('POST', `/api/im/admin/groups/${groupId}/announcement`, { announcement });
        return res;
    },

    /** 管理后台-查看群成员列表 */
    async adminGetGroupMembers(groupId) {
        const res = await this.request('GET', `/api/im/admin/groups/${groupId}/members`);
        return res.data || {};
    },

    /** 创建群组 */
    async createGroup(name, memberIds) {
        const res = await this.request('POST', '/api/im/groups', {
            name: name,
            member_ids: memberIds || []
        });
        return res.data || {};
    },

    /** 获取会话列表 */
    async getConversations() {
        const res = await this.request('GET', '/api/im/conversations');
        return { data: res.data || [], raw: res };
    },

    /** 获取聊天消息 */
    async getMessages(receiverType, receiverId, beforeId = null, limit = 50) {
        let url = `/api/im/messages?receiver_type=${receiverType}&receiver_id=${receiverId}&limit=${limit}`;
        if (beforeId) url += `&before_id=${beforeId}`;
        const res = await this.request('GET', url);
        return { items: res.data || [], raw: res };
    },

    /** 发送 IM 消息（支持@提及） */
    async sendMessage(receiverType, receiverId, content, msgType = 'text', fileId = null, mentions = []) {
        const body = {
            receiver_id: receiverId,
            receiver_type: receiverType,
            type: msgType,
            content: content,
            file_id: fileId,
        };
        if (mentions && mentions.length > 0) {
            body.mentions = mentions;
        }
        const res = await this.request('POST', '/api/im/messages', body);
        return res.data || {};
    },

    /** 标记消息已读 */
    async markMessagesRead(receiverType, receiverId, lastReadMsgId) {
        const res = await this.request('POST', '/api/im/messages/read', {
            receiver_type: receiverType,
            receiver_id: receiverId,
            last_read_msg_id: lastReadMsgId
        });
        return res;
    },

    /** 获取聊天服务器列表 */
    async getChatServers() {
        const res = await this.request('GET', '/api/im/servers');
        return res.data || [];
    },

    /** 获取数字员工（聊天） */
    async getChatWorkers() {
        const res = await this.request('GET', '/api/im/workers/chat');
        return res.data || [];
    },

    /**
     * 上传文件（IM 模块）
     * 使用 multipart/form-data 上传
     * @param {File} file - 要上传的文件对象
     * @returns {Promise<object>} 上传结果 {id, file_name, file_size, mime_type, md5_hash, duplicate}
     */
    async uploadFile(file) {
        const formData = new FormData();
        formData.append('file', file);

        const headers = {};
        if (this.token) headers['Authorization'] = `Bearer ${this.token}`;

        // 注意：不设置 Content-Type，让浏览器自动设置 multipart/form-data; boundary=...
        const response = await fetch(`${this.BASE_URL}/api/im/files/upload`, {
            method: 'POST',
            headers,
            body: formData
        });

        const data = await response.json();
        if (!response.ok) {
            throw new Error(data.message || `HTTP ${response.status}`);
        }
        return data.data || data;
    },

    // ========== 文件详情查看 ==========

    /** 查看文件详情 */
    async viewFileDetail(fileId) {
        try {
            const res = await this.request('GET', `/api/files/${fileId}`);
            const data = res.data || res;
            if (!data) {
                this.toast('error', '加载失败', '文件不存在');
                return;
            }

            const fields = [
                { label: '📋 文件 ID', value: data.id ?? '-' },
                { label: '📄 文件名', value: data.file_name || '-' },
                { label: '📦 大小', value: data.file_size_display || '-' },
                { label: '📎 MIME 类型', value: data.mime_type || '-' },
                { label: '🔐 MD5', value: data.md5_hash || '-', short: true },
                { label: '👤 上传者 ID', value: data.uploader_id ?? '-' },
                { label: '💬 关联消息 ID', value: data.chat_message_id ?? '-' },
                { label: '📅 上传时间', value: data.created_at ? new Date(data.created_at).toLocaleString('zh-CN') : '-' },
                { label: '📁 存储路径', value: data.file_path || '-', isLong: true },
            ];

            const tokenSuffix = this.token ? `?token=${encodeURIComponent(this.token)}` : '';
            const isImage = data.mime_type && data.mime_type.startsWith('image/');
            const previewHtml = isImage
                ? `<div style="text-align:center;margin-bottom:12px;padding:8px;background:var(--bg-input);border-radius:var(--radius-xs)">
                    <img src="/api/files/${data.id}/download${tokenSuffix}" style="max-width:100%;max-height:300px;object-fit:contain;border-radius:4px" />
                    <div style="margin-top:8px"><a href="/api/files/${data.id}/download${tokenSuffix}" target="_blank" class="btn btn-sm btn-success">⬇️ 下载原图</a></div>
                   </div>`
                : '';

            const bodyHtml = previewHtml + fields.map(f =>
                `<div class="detail-row" style="padding:8px 0;border-bottom:1px solid var(--border);display:flex;gap:12px;flex-direction:${f.isLong ? 'column' : 'row'}">
                    <span style="min-width:120px;font-weight:500;color:var(--text-light);flex-shrink:0">${f.label}</span>
                    ${f.isLong
                        ? `<pre style="margin:4px 0 0 0;background:var(--bg-input);padding:8px 12px;border-radius:var(--radius-xs);font-size:13px;line-height:1.5;max-height:200px;overflow:auto;white-space:pre-wrap;word-break:break-all;color:var(--text)">${this._escapeHtml(String(f.value))}</pre>`
                        : `<span style="word-break:break-all;color:var(--text)">${this._escapeHtml(f.short ? String(f.value).slice(0, 32) + '...' : String(f.value))}</span>`
                    }
                </div>`
            ).join('');

            this.showModal(`👁️ 文件详情 #${fileId}`,
                `<div class="detail-view" style="max-height:70vh;overflow-y:auto">${bodyHtml}</div>`,
                `<button class="btn btn-sm btn-success" onclick="window.open('/api/files/${data.id}/download${tokenSuffix}','_blank')">⬇️ 下载</button>
                 <button class="btn btn-sm btn-primary" onclick="API.closeModal()">关闭</button>`
            );
        } catch (err) {
            this.toast('error', '加载详情失败', err.message);
        }
    },

    // ========== Auth ==========
    /**
     * 退出登录
     */
    async logout() {
        try {
            if (this.token) {
                await this.request('POST', '/api/auth/logout');
            }
        } catch {
            // 忽略登出请求的错误
        }
        this.token = null;
        this.currentUser = null;
        localStorage.removeItem('ctos_token');
    }
};