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

/* ===== 业务映射 ===== */
if(window.GestureSettings && window.GestureSettings.get('enabled')){

gestureBus.on('index_up', function(e){
	var sp = document.querySelector('.page-nav .dot.active');
	if(sp){
		var next = sp.nextElementSibling;
		if(next && next.click) next.click();
	} else if(typeof window.scrollBy === 'function'){
		window.scrollBy(0, -window.innerHeight * 0.3);
	}
	if(window.SpeechManager && window.SpeechManager.isEnabled()){
		window.SpeechManager.speak('向上翻页');
	}
}, 10);

gestureBus.on('index_down', function(e){
	var sp = document.querySelector('.page-nav .dot.active');
	if(sp){
		var prev = sp.previousElementSibling;
		if(prev && prev.click) prev.click();
	} else if(typeof window.scrollBy === 'function'){
		window.scrollBy(0, window.innerHeight * 0.3);
	}
	if(window.SpeechManager && window.SpeechManager.isEnabled()){
		window.SpeechManager.speak('向下翻页');
	}
}, 10);

gestureBus.on('fist', function(e){
	if(window.__autoSlideInterval){
		clearInterval(window.__autoSlideInterval);
		window.__autoSlideInterval = null;
		if(window.SpeechManager && window.SpeechManager.isEnabled()){
			window.SpeechManager.speak('已暂停自动轮播');
		}
	} else {
		if(window.SpeechManager && window.SpeechManager.isEnabled()){
			window.SpeechManager.speak('已恢复自动轮播');
		}
	}
}, 10);

gestureBus.on('swipe_left', function(e){
	if(window.__navigateModule && typeof window.__navigateModule === 'function'){
		window.__navigateModule(-1);
	}
}, 10);

gestureBus.on('swipe_right', function(e){
	if(window.__navigateModule && typeof window.__navigateModule === 'function'){
		window.__navigateModule(1);
	}
}, 10);

gestureBus.on('swipe_up', function(e){
	if(typeof window.scrollBy === 'function'){
		window.scrollBy(0, -200);
	}
}, 5);

gestureBus.on('swipe_down', function(e){
	if(typeof window.scrollBy === 'function'){
		window.scrollBy(0, 200);
	}
}, 5);

}

window.GestureBus = gestureBus;

document.addEventListener('DOMContentLoaded', function(){
	if(window.__navigateModule) return;
	var navItems = [];
	var links = document.querySelectorAll('.nav-item');
	if(links.length > 0){
		for(var i=0;i<links.length;i++){
			var href = links[i].getAttribute('href');
			if(href && href !== '#' && href !== 'javascript:void(0)'){
				navItems.push({el:links[i], url:href, name:links[i].textContent.trim()});
			}
		}
	}
	if(navItems.length > 0){
		window.__navigateModule = function(direction){
			var currentIdx = -1;
			for(var i=0;i<navItems.length;i++){
				if(navItems[i].el.classList.contains('active')){
					currentIdx = i;
					break;
				}
			}
			if(currentIdx === -1){
				for(var j=0;j<navItems.length;j++){
					if(window.location.pathname.indexOf(navItems[j].url) !== -1){
						currentIdx = j;
						break;
					}
				}
			}
			var targetIdx = currentIdx + direction;
			if(targetIdx >= 0 && targetIdx < navItems.length){
				window.location.href = navItems[targetIdx].url;
			}
		};
	}
});

})();
