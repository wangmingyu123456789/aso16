(function(){
'use strict';

var hands = null;
var isRunning = false;
var handDetected = false;
var frameTimer = null;
var mediaPipeLoading = false;

var GestureController = {
	init: function(){
		this.loadSettings();
		this.restorePanelState();
		this.preloadMediaPipe();
		var self = this;
		setTimeout(function(){
			var panelCollapsed = localStorage.getItem('gesture_panel_collapsed') === 'true';
			if(localStorage.getItem('gesture_auto_start') === 'true' && !panelCollapsed){
				self.toggleCamera();
			}
		}, 300);
	},

	loadSettings: function(){
		var s = window.GestureSettings;
		if(!s) return;
		var el = function(id){ return document.getElementById(id); };
		if(el('gsEnabled')) el('gsEnabled').checked = s.get('enabled');
		if(el('gsFrameRate')) el('gsFrameRate').value = s.get('frameRate') || 15;
		if(el('gsIndexUp')) el('gsIndexUp').checked = s.get('gestures.index_up') !== false;
		if(el('gsIndexDown')) el('gsIndexDown').checked = s.get('gestures.index_down') !== false;
		if(el('gsFist')) el('gsFist').checked = s.get('gestures.fist') !== false;
		if(el('gsSwipeLeft')) el('gsSwipeLeft').checked = s.get('gestures.swipe_left') !== false;
		if(el('gsSwipeRight')) el('gsSwipeRight').checked = s.get('gestures.swipe_right') !== false;
		if(el('gsTwoFingers')) el('gsTwoFingers').checked = s.get('gestures.two_fingers') !== false;
		this.updateUIState();
	},

	toggleCollapse: function(){
		var panel = document.getElementById('gesturePanel');
		if(!panel) return;
		panel.classList.toggle('collapsed');
		var btn = panel.querySelector('.gp-btn-collapse');
		if(btn) btn.textContent = panel.classList.contains('collapsed') ? '▶' : '◀';
		var isCollapsed = panel.classList.contains('collapsed');
		localStorage.setItem('gesture_panel_collapsed', isCollapsed ? 'true' : 'false');
		if(isCollapsed && isRunning){
			this.stopCamera();
		}
	},

	toggleSettings: function(){
		var overlay = document.getElementById('gpSettingsOverlay');
		if(!overlay) return;
		overlay.classList.toggle('show');
		this.loadSettings();
	},

	toggleCamera: function(){
		if(isRunning){
			this.stopCamera();
		} else {
			this.startCamera();
		}
	},

	startCamera: function(){
		if(!window.GestureSettings.get('enabled')){
			this.setStatus('error', '手势识别已禁用');
			return;
		}
		var video = document.getElementById('gpVideo');
		if(!video) return;
		this.setStatus(null, '正在启动...');

		var self = this;

		if(typeof Hands === 'undefined'){
			if(mediaPipeLoading){
				this.setStatus(null, 'MediaPipe加载中...');
				var waitInterval = setInterval(function(){
					if(typeof Hands !== 'undefined' || !mediaPipeLoading){
						clearInterval(waitInterval);
						if(typeof Hands !== 'undefined'){
							self.startCamera();
						} else {
							self.setStatus('error', 'MediaPipe加载失败');
						}
					}
				}, 100);
				return;
			}
			this.setStatus(null, '加载MediaPipe中...');
			this.loadMediaPipe(function(success){
				if(success){
					self.startCamera();
				} else {
					self.setStatus('error', 'MediaPipe加载失败');
				}
			});
			return;
		}

		if(!hands){
			hands = new Hands({
				locateFile: function(file){
					return 'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/' + file;
				}
			});
			hands.setOptions({
				maxNumHands: 1,
				modelComplexity: 1,
				minDetectionConfidence: 0.7,
				minTrackingConfidence: 0.6
			});
			hands.onResults(function(results){ self.onResults(results); });
		}

		if(navigator.mediaDevices && navigator.mediaDevices.getUserMedia){
			navigator.mediaDevices.getUserMedia({video:{width:{ideal:320},height:{ideal:240},facingMode:'user'}})
				.then(function(stream){
					video.srcObject = stream;
					var wrap = document.getElementById('gpVideoWrap');
					if(wrap){
						var rect = wrap.getBoundingClientRect();
						var canvas = document.getElementById('gpCanvas');
						if(canvas){
							canvas.width = rect.width * (window.devicePixelRatio || 1);
							canvas.height = rect.height * (window.devicePixelRatio || 1);
							canvas.style.width = rect.width + 'px';
							canvas.style.height = rect.height + 'px';
						}
						window.GestureFeedback.init(canvas);
						window.GestureFeedback.start();
					}
					isRunning = true;
					handDetected = false;
					self.setStatus(null, '等待手部...');
					document.getElementById('gpToggleBtn').textContent = '⏹ 停止摄像头';
					document.getElementById('gpToggleBtn').classList.add('active');
					self.expand();
					localStorage.setItem('gesture_auto_start', 'true');
					video.play().then(function(){
						self.sendFrame();
					}).catch(function(){
						self.sendFrame();
					});
				})
				.catch(function(err){
					console.error('[Gesture] Camera error:', err);
					self.setStatus('error', '摄像头访问被拒绝');
					if(window.SpeechManager && window.SpeechManager.isEnabled()){
						window.SpeechManager.speak('摄像头访问被拒绝，请在浏览器设置中允许摄像头权限');
					}
				});
		} else {
			this.setStatus('error', '浏览器不支持摄像头');
		}
	},

	stopCamera: function(){
		isRunning = false;
		handDetected = false;
		if(frameTimer){
			clearTimeout(frameTimer);
			frameTimer = null;
		}
		var video = document.getElementById('gpVideo');
		if(video && video.srcObject){
			var tracks = video.srcObject.getTracks();
			for(var i=0;i<tracks.length;i++) tracks[i].stop();
			video.srcObject = null;
		}
		window.GestureFeedback.stop();
		window.GestureRuleEngine.reset();
		this.setStatus(null, '已停止');
		document.getElementById('gpToggleBtn').textContent = '📷 启动摄像头';
		document.getElementById('gpToggleBtn').classList.remove('active');
		document.getElementById('gpLiveGesture').textContent = '等待识别...';
		document.getElementById('gpLiveGesture').className = 'gp-live-gesture waiting';
		document.getElementById('gpLiveConfidence').textContent = '';
		localStorage.setItem('gesture_auto_start', 'false');
		this.collapse();
	},

	collapse: function(){
		var panel = document.getElementById('gesturePanel');
		if(!panel) return;
		panel.classList.add('collapsed');
		var btn = panel.querySelector('.gp-btn-collapse');
		if(btn) btn.textContent = '▶';
		localStorage.setItem('gesture_panel_collapsed', 'true');
	},

	expand: function(){
		var panel = document.getElementById('gesturePanel');
		if(!panel) return;
		panel.classList.remove('collapsed');
		var btn = panel.querySelector('.gp-btn-collapse');
		if(btn) btn.textContent = '◀';
		localStorage.setItem('gesture_panel_collapsed', 'false');
	},

	sendFrame: function(){
		if(!isRunning) return;
		
		if(frameTimer){
			clearTimeout(frameTimer);
			frameTimer = null;
		}
		
		var video = document.getElementById('gpVideo');
		if(!video || video.readyState < 2 || !hands){
			frameTimer = setTimeout(function(){ 
				GestureController.sendFrame(); 
			}, 50);
			return;
		}
		
		try{
			hands.send({image: video});
		}catch(e){
			frameTimer = setTimeout(function(){ 
				GestureController.sendFrame(); 
			}, 50);
		}
	},

	onResults: function(results){
		
		if(frameTimer){
			clearTimeout(frameTimer);
			frameTimer = null;
		}
		
		if(!isRunning){
			return;
		}
		
		var liveEl = document.getElementById('gpLiveGesture');
		var confEl = document.getElementById('gpLiveConfidence');

		if(!results || !results.multiHandLandmarks || results.multiHandLandmarks.length === 0){
			handDetected = false;
			this.setStatus(null, '等待手部...');
			if(liveEl){
				liveEl.textContent = '等待手势...';
				liveEl.className = 'gp-live-gesture waiting';
			}
			if(confEl) confEl.textContent = '';
			window.GestureFeedback.updateLandmarks(null);
			window.GestureFeedback.updateGesture(null);
		} else {
			var rawLandmarks = results.multiHandLandmarks[0];
			var landmarks = [];
			for(var i = 0; i < rawLandmarks.length; i++){
				landmarks.push({
					x: 1 - rawLandmarks[i].x,
					y: rawLandmarks[i].y,
					z: rawLandmarks[i].z
				});
			}

			if(!handDetected){
				handDetected = true;
				this.setStatus('active', '已检测到手部');
			}

			window.GestureFeedback.updateLandmarks(landmarks);

			var gesture = window.GestureRuleEngine.detectAll(landmarks);
			if(gesture){
				window.GestureFeedback.updateGesture(gesture);
				this.updateLiveStatus(gesture);
				window.GestureBus.emit(gesture);
			} else {
				window.GestureFeedback.updateGesture(null);
			}
		}

		var frameRate = window.GestureSettings.get('frameRate') || 15;
		var delay = Math.max(16, Math.floor(1000 / frameRate));
		frameTimer = setTimeout(function(){ 
			GestureController.sendFrame(); 
		}, delay);
	},

	updateLiveStatus: function(gesture){
		var labels = {
			index_up: '☝️ 食指向上',
			index_down: '👇 食指向下',
			fist: '✊ 握拳（回首页）',
			swipe_left: '👈 左滑（上一模块）',
			swipe_right: '👉 右滑（下一模块）',
			open_palm: '🖐️ 布（下一模块）',
			two_fingers: '✌️ 二指（瞭望采集）'
		};
		var el = document.getElementById('gpLiveGesture');
		var confEl = document.getElementById('gpLiveConfidence');
		if(el){
			el.textContent = labels[gesture.type] || gesture.type;
			el.className = 'gp-live-gesture';
		}
		if(confEl){
			confEl.textContent = '置信度: ' + Math.round((gesture.confidence || 0) * 100) + '%';
		}
	},

	setStatus: function(state, text){
		var dot = document.getElementById('gpDot');
		var textEl = document.getElementById('gpStatusText');
		if(dot){
			dot.className = 'gp-dot';
			if(state) dot.classList.add(state);
		}
		if(textEl) textEl.textContent = text || '等待启动';
	},

	loadMediaPipe: function(callback){
		var scripts = [
			'https://cdn.jsdelivr.net/npm/@mediapipe/hands@0.4/hands.js',
			'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils@0.3/camera_utils.js',
			'https://cdn.jsdelivr.net/npm/@mediapipe/drawing_utils@0.3/drawing_utils.js'
		];
		var loaded = 0;
		var self = this;
		scripts.forEach(function(src){
			var s = document.createElement('script');
			s.src = src;
			s.async = true;
			s.onload = function(){
				loaded++;
				if(loaded === scripts.length){
					if(callback) callback(true);
				}
			};
			s.onerror = function(){
				console.error('[Gesture] Failed to load:', src);
				if(callback) callback(false);
			};
			document.head.appendChild(s);
		});
	},

	preloadMediaPipe: function(){
		if(typeof Hands !== 'undefined' || mediaPipeLoading) return;
		mediaPipeLoading = true;
		this.loadMediaPipe(function(success){
			mediaPipeLoading = false;
			if(success){
				console.log('[Gesture] MediaPipe preloaded');
			}
		});
	},

	restorePanelState: function(){
		var panel = document.getElementById('gesturePanel');
		if(!panel) return;
		var wasCollapsed = localStorage.getItem('gesture_panel_collapsed') === 'true';
		if(wasCollapsed){
			panel.classList.add('collapsed');
			var btn = panel.querySelector('.gp-btn-collapse');
			if(btn) btn.textContent = '▶';
		} else {
			panel.classList.remove('collapsed');
			var btn = panel.querySelector('.gp-btn-collapse');
			if(btn) btn.textContent = '◀';
		}
	},

	showGuide: function(){
		var overlay = document.getElementById('gpGuideOverlay');
		if(overlay) overlay.classList.add('show');
	},

	hideGuide: function(){
		var overlay = document.getElementById('gpGuideOverlay');
		if(overlay) overlay.classList.remove('show');
	},

	updateUIState: function(){
		var enabled = window.GestureSettings.get('enabled');
		var btn = document.getElementById('gpToggleBtn');
		if(btn) btn.disabled = !enabled;
	}
};

window.GestureController = GestureController;

document.addEventListener('DOMContentLoaded', function(){
	if(document.getElementById('gesturePanel')){
		GestureController.init();
	}
});

})();
