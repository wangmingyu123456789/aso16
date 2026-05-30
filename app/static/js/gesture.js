(function(){
'use strict';

var hands = null;
var camera = null;
var isRunning = false;
var lastGestureType = null;
var settingsLoaded = false;

var GestureController = {
	init: function(){
		this.loadSettings();
		this.bindEvents();
		setTimeout(function(){
			if(localStorage.getItem('gesture_auto_start') === 'true'){
				GestureController.toggleCamera();
			}
		}, 1000);
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
		if(el('gsSwipeUp')) el('gsSwipeUp').checked = s.get('gestures.swipe_up') !== false;
		if(el('gsSwipeDown')) el('gsSwipeDown').checked = s.get('gestures.swipe_down') !== false;
		this.updateUIState();
		settingsLoaded = true;
	},

	bindEvents: function(){
		var panel = document.getElementById('gesturePanel');
		if(!panel) return;
		if(panel.classList.contains('collapsed')){
			panel.addEventListener('click', function(e){
				if(panel.classList.contains('collapsed') && !e.target.closest('.gp-header-actions')){
					GestureController.toggleCollapse();
				}
			});
		}
	},

	toggleCollapse: function(){
		var panel = document.getElementById('gesturePanel');
		if(!panel) return;
		panel.classList.toggle('collapsed');
		var btn = panel.querySelector('.gp-btn-collapse');
		if(btn) btn.textContent = panel.classList.contains('collapsed') ? '▶' : '◀';
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
		this.setStatus('active', '正在启动...');

		var self = this;

		if(typeof Hands === 'undefined'){
			this.setStatus('error', '加载MediaPipe中...');
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
				minDetectionConfidence: window.GestureSettings.get('minDetectionConfidence') || 0.7,
				minTrackingConfidence: window.GestureSettings.get('minTrackingConfidence') || 0.5
			});
			hands.onResults(function(results){ self.onResults(results); });
		}

		if(navigator.mediaDevices && navigator.mediaDevices.getUserMedia){
			navigator.mediaDevices.getUserMedia({video:{width:{ideal:320},height:{ideal:240},facingMode:'user'}})
				.then(function(stream){
					video.srcObject = stream;
					video.play().then(function(){
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
						self.setStatus('active', '已检测到手部');
						document.getElementById('gpToggleBtn').textContent = '⏹ 停止摄像头';
						document.getElementById('gpToggleBtn').classList.add('active');
						localStorage.setItem('gesture_auto_start', 'true');
						self.processFrame();
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
	},

	processFrame: function(){
		if(!isRunning) return;
		var video = document.getElementById('gpVideo');
		if(video && video.readyState >= 2 && hands){
			try{
				hands.send({image: video});
			}catch(e){
				console.error('[Gesture] send error:', e);
			}
		}
		var frameRate = window.GestureSettings.get('frameRate') || 15;
		var delay = Math.max(33, Math.floor(1000 / frameRate));
		setTimeout(function(){ GestureController.processFrame(); }, delay);
	},

	onResults: function(results){
		if(!results || !results.multiHandLandmarks || results.multiHandLandmarks.length === 0){
			this.setStatus(null, '未检测到手部');
			document.getElementById('gpLiveGesture').textContent = '等待手势...';
			document.getElementById('gpLiveGesture').className = 'gp-live-gesture waiting';
			return;
		}

		var landmarks = results.multiHandLandmarks[0];
		this.setStatus('active', '已检测到手部');

		window.GestureFeedback.updateLandmarks(landmarks);

		var gesture = window.GestureRuleEngine.detectAll(landmarks);
		if(gesture){
			lastGestureType = gesture.type;
			window.GestureFeedback.updateGesture(gesture);
			this.updateLiveStatus(gesture);
			window.GestureBus.emit(gesture);
		} else {
			window.GestureFeedback.updateGesture(null);
			if(!lastGestureType || Date.now() - (window.GestureRuleEngine.getLastGesture() ? 0 : Date.now()) > 500){
				document.getElementById('gpLiveGesture').textContent = '等待手势...';
				document.getElementById('gpLiveGesture').className = 'gp-live-gesture waiting';
				document.getElementById('gpLiveConfidence').textContent = '';
			}
		}
	},

	updateLiveStatus: function(gesture){
		var labels = {
			index_up: '☝️ 食指向上',
			index_down: '👇 食指向下',
			fist: '✊ 握拳',
			swipe_left: '👈 左滑',
			swipe_right: '👉 右滑',
			swipe_up: '🖐️ 上滑',
			swipe_down: '🖐️ 下滑'
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

	toggleSpeech: function(){
		if(!window.SpeechManager) return;
		var enabled = !window.SpeechManager.isEnabled();
		window.SpeechManager.setEnabled(enabled);
		var btn = document.getElementById('gpSpeechBtn');
		if(btn){
			btn.textContent = enabled ? '🔊 语音播报' : '🔇 已静音';
			btn.classList.toggle('muted', !enabled);
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
