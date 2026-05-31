(function(){
'use strict';

function GestureEventBus(){
	this.listeners = {};
	this.middleware = [];
	this.history = [];
}

GestureEventBus.prototype.on = function(gestureType, callback, priority){
	if(!this.listeners[gestureType]) this.listeners[gestureType] = [];
	this.listeners[gestureType].push({callback:callback, priority:priority||0});
	this.listeners[gestureType].sort(function(a,b){ return b.priority - a.priority; });
};

GestureEventBus.prototype.emit = function(event){
	if(!event || !event.type) return;
	event.timestamp = Date.now();
	for(var i=0;i<this.middleware.length;i++){
		var filtered = this.middleware[i](event);
		if(!filtered) return;
		event = filtered;
	}
	var list = this.listeners[event.type] || [];
	for(var j=0;j<list.length;j++){
		try{ list[j].callback(event); }catch(e){ console.error('[GestureBus]', e); }
	}
	this.history.push(event);
	if(this.history.length > 100) this.history.shift();
};

GestureEventBus.prototype.use = function(fn){
	this.middleware.push(fn);
};

GestureEventBus.prototype.getHistory = function(){
	return this.history;
};

var gestureBus = new GestureEventBus();

/* ===== 页面加载导航冷却 ===== */
var __pageLoadTime = Date.now();
var __navCooldown = 3000; // 3秒内阻止手势触发的页面跳转，防止刷新时误检测跳回首页

function canNavigate(){
	if(Date.now() - __pageLoadTime < __navCooldown){
		return false;
	}
	return true;
}

/* ===== 辅助函数 ===== */
function getCurrentPage(){
	var path = window.location.pathname;
	if(path.indexOf('/user/dashboard') !== -1) return 'dashboard';
	if(path.indexOf('/user/sentiment') !== -1) return 'sentiment';
	if(path.indexOf('/user/outlook/collect') !== -1) return 'outlook_collect';
	if(path.indexOf('/user/outlook/data') !== -1) return 'outlook_data';
	if(path.indexOf('/user/outlook/schedule') !== -1) return 'outlook_schedule';
	if(path.indexOf('/user/outlook/log') !== -1) return 'outlook_log';
	if(path.indexOf('/qa') !== -1) return 'qa';
	if(path.indexOf('/im') !== -1) return 'im';
	return 'home';
}

function speak(text){
	if(window.SpeechManager && window.SpeechManager.isEnabled()){
		window.SpeechManager.speak(text);
	}
}

/* ===== 通用导航序列（覆盖所有页面，包括独立页面） ===== */
var UNIVERSAL_NAV = [
	{url: '/home', label: '首页'},
	{url: '/qa', label: '智能问数'},
	{url: '/im', label: '智能聊天'},
	{url: '/user/dashboard', label: '数智大屏'},
	{url: '/user/sentiment', label: '智慧舆情'},
	{url: '/user/outlook/collect', label: '瞭望采集'},
	{url: '/user/outlook/data', label: '数据仓库'},
	{url: '/user/outlook/schedule', label: '定时采集'},
	{url: '/user/outlook/log', label: '采集日志'}
];

function navigateModule(direction){
	if(!canNavigate()) return;

	// 先尝试用通用导航序列（适用于所有页面，包括独立页面/q/a、/im等）
	var currentPath = window.location.pathname;
	var foundIdx = -1;
	for(var i = 0; i < UNIVERSAL_NAV.length; i++){
		if(currentPath.indexOf(UNIVERSAL_NAV[i].url) !== -1){
			foundIdx = i;
			break;
		}
	}

	// 如果在通用序列中找到了，直接使用通用序列导航
 	if(foundIdx !== -1){
 		var targetIdx = foundIdx + direction;
 		if(targetIdx < 0){
 			speak('已经是第一个模块');
 			return;
 		}
 		if(targetIdx >= UNIVERSAL_NAV.length){
 			speak('已经是最后一个模块');
 			return;
 		}
 		window.location.href = UNIVERSAL_NAV[targetIdx].url;
 		return;
 	}

	// 回退方案：使用侧边栏导航（带layout的页面）
	var navItems = document.querySelectorAll('.sidebar .nav-item');
	if(navItems.length === 0) return;
	
	var navArray = [];
	for(var i = 0; i < navItems.length; i++){
		var href = navItems[i].getAttribute('href');
		if(href && href !== '#' && href !== 'javascript:void(0)'){
			navArray.push({el: navItems[i], url: href});
		}
	}
	
	var currentIdx = -1;
	for(var j = 0; j < navArray.length; j++){
		if(currentPath.indexOf(navArray[j].url) !== -1){
			currentIdx = j;
			break;
		}
	}
	
	if(currentIdx === -1) return;
	
	var targetIdx = currentIdx + direction;
	
	if(targetIdx < 0){
		console.log('[GestureBus] At first module, cannot go left');
		speak('已经是第一个模块');
		return;
	}
	if(targetIdx >= navArray.length){
		console.log('[GestureBus] At last module, cannot go right');
		speak('已经是最后一个模块');
		return;
	}
	
	console.log('[GestureBus] Navigating module from', currentIdx, 'to', targetIdx);
	window.location.href = navArray[targetIdx].url;
}

function navigateDashboardPage(direction){
	var dots = document.querySelectorAll('.page-nav .dot');
	if(dots.length === 0) return;
	
	var currentIdx = -1;
	for(var i = 0; i < dots.length; i++){
		if(dots[i].classList.contains('active')){
			currentIdx = i;
			break;
		}
	}
	
	if(currentIdx === -1) return;
	
	var targetIdx = currentIdx + direction;
	
	if(targetIdx < 0){
		console.log('[GestureBus] At first dashboard page');
		speak('已经是第一页');
		return;
	}
	if(targetIdx >= dots.length){
		console.log('[GestureBus] At last dashboard page');
		speak('已经是最后一页');
		return;
	}
	
	console.log('[GestureBus] Navigating dashboard page from', currentIdx, 'to', targetIdx);
	dots[targetIdx].click();
}

function switchSentimentTab(direction){
	var tabs = document.querySelectorAll('.tab-bar .tab-btn');
	var contents = document.querySelectorAll('.tab-content');
	if(tabs.length === 0 || contents.length === 0) return;
	
	var currentIdx = -1;
	for(var i = 0; i < tabs.length; i++){
		if(tabs[i].classList.contains('active')){
			currentIdx = i;
			break;
		}
	}
	
	if(currentIdx === -1) return;
	
	var targetIdx = currentIdx + direction;
	
	if(targetIdx < 0){
		console.log('[GestureBus] At first sentiment tab');
		speak('已经是左Tab');
		return;
	}
	if(targetIdx >= tabs.length){
		console.log('[GestureBus] At last sentiment tab');
		speak('已经是右Tab');
		return;
	}
	
	console.log('[GestureBus] Switching sentiment tab from', currentIdx, 'to', targetIdx);
	
	for(var j = 0; j < tabs.length; j++){
		tabs[j].classList.remove('active');
		contents[j].classList.remove('active');
	}
	
	tabs[targetIdx].classList.add('active');
	contents[targetIdx].classList.add('active');
	
	if(typeof window.switchTab === 'function'){
		window.switchTab(targetIdx === 0 ? 'dashboard' : 'sentiment', tabs[targetIdx]);
	}
}

/* ===== 手势映射注册 ===== */
function registerGestureMappings(){

	gestureBus.on('index_up', function(e){
		var page = getCurrentPage();
		
		if(page === 'dashboard'){
			navigateDashboardPage(-1);
		} else if(page === 'sentiment'){
			switchSentimentTab(-1);
		} else {
			window.scrollBy(0, -window.innerHeight * 0.3);
			speak('向上滚动');
		}
	}, 10);

	gestureBus.on('index_down', function(e){
		var page = getCurrentPage();
		
		if(page === 'dashboard'){
			navigateDashboardPage(1);
		} else if(page === 'sentiment'){
			switchSentimentTab(1);
		} else {
			window.scrollBy(0, window.innerHeight * 0.3);
			speak('向下滚动');
		}
	}, 10);

	gestureBus.on('fist', function(e){
		if(!canNavigate()) return;
		window.location.href = '/home';
		speak('回到首页');
	}, 10);

	gestureBus.on('swipe_left', function(e){
		navigateModule(-1);
	}, 10);

	gestureBus.on('swipe_right', function(e){
		navigateModule(1);
	}, 10);

	gestureBus.on('open_palm', function(e){
		if(!canNavigate()) return;
		navigateModule(1);
		speak('下一个模块');
	}, 10);

	gestureBus.on('two_fingers', function(e){
		if(!canNavigate()) return;
		window.location.href = '/user/outlook/collect';
		speak('瞭望采集');
	}, 10);
}

if(document.readyState === 'loading'){
	document.addEventListener('DOMContentLoaded', registerGestureMappings);
} else {
	registerGestureMappings();
}

window.GestureBus = gestureBus;

/* ===== 数智大屏自动轮播 ===== */
window.startAutoSlide = function(){
	if(window.__autoSlideInterval) return;
	
	var currentPage = getCurrentPage();
	if(currentPage !== 'dashboard'){
		console.log('[GestureBus] Auto-slide only works on dashboard page');
		return;
	}
	
	var dots = document.querySelectorAll('.page-nav .dot');
	if(dots.length === 0) return;
	
	// 检查用户是否关闭了自动轮播
	var autoSlideEnabled = localStorage.getItem('dashboard_auto_slide') !== 'false';
	if(!autoSlideEnabled){
		console.log('[GestureBus] Auto-slide disabled by user setting');
		window.__autoSlidePaused = true;
	} else {
		window.__autoSlidePaused = false;
	}
	
	console.log('[GestureBus] Starting auto-slide on dashboard');

	window.__autoSlideInterval = setInterval(function(){
		if(window.__autoSlidePaused) return;
		
		var currentIdx = -1;
		for(var i = 0; i < dots.length; i++){
			if(dots[i].classList.contains('active')){
				currentIdx = i;
				break;
			}
		}
		
		if(currentIdx === -1) return;
		
		var nextIdx = (currentIdx + 1) % dots.length;
		console.log('[GestureBus] Auto-slide from page', currentIdx, 'to', nextIdx);
		dots[nextIdx].click();
	}, 5000);
};

if(getCurrentPage() === 'dashboard'){
	document.addEventListener('DOMContentLoaded', function(){
		setTimeout(function(){
			window.startAutoSlide();
		}, 2000);
	});
}

})();
