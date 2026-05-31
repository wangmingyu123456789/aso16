(function(){
'use strict';

var hands = null;
var isRunning = false;
var handDetected = false;
var frameTimer = null;

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
	},

	bindEvents: function(){
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
		this.setStatus(null, '正在启动...');

		var self = this;

		if(typeof Hands === 'undefined'){
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
				minDetectionConfidence: 0.75,
				minTrackingConfidence: 0.7
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
						handDetected = false;
						self.setStatus(null, '等待手部...');
						document.getElementById('gpToggleBtn').textContent = '⏹ 停止摄像头';
						document.getElementById('gpToggleBtn').classList.add('active');
						localStorage.setItem('gesture_auto_start', 'true');
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
	},

	sendFrame: function(){
		if(!isRunning) return;
		
		// 清除任何现有的定时器，确保只有一个活跃
		if(frameTimer){
			clearTimeout(frameTimer);
			frameTimer = null;
		}
		
		var video = document.getElementById('gpVideo');
		if(!video || video.readyState < 2 || !hands){
			console.log('[Gesture] Video not ready, readyState:', video ? video.readyState : 'no video');
			// 视频未准备好，延迟重试
			frameTimer = setTimeout(function(){ 
				GestureController.sendFrame(); 
			}, 100);
			return;
		}
		
		console.log('[Gesture] Sending frame, video size:', video.videoWidth, 'x', video.videoHeight);
		try{
			hands.send({image: video});
		}catch(e){
			console.error('[Gesture] send error:', e);
			// 发送失败，延迟后重试
			frameTimer = setTimeout(function(){ 
				GestureController.sendFrame(); 
			}, 200);
		}
	},

	onResults: function(results){
		console.log('[Gesture] onResults called, results:', results);
		
		// 清除可能存在的旧定时器
		if(frameTimer){
			clearTimeout(frameTimer);
			frameTimer = null;
		}
		
		// 如果已停止，不再处理
		if(!isRunning){
			console.log('[Gesture] Stopped, ignoring results');
			return;
		}
		
		var liveEl = document.getElementById('gpLiveGesture');
		var confEl = document.getElementById('gpLiveConfidence');

		if(!results || !results.multiHandLandmarks || results.multiHandLandmarks.length === 0){
			// 没有检测到手
			console.log('[Gesture] No hand detected');
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
			// 检测到手部
			console.log('[Gesture] Hand detected! Landmarks count:', results.multiHandLandmarks[0].length);
			var rawLandmarks = results.multiHandLandmarks[0];
			var landmarks = [];
			for(var i = 0; i < rawLandmarks.length; i++){
				landmarks.push({
					x: 1 - rawLandmarks[i].x,  // X轴镜像
					y: rawLandmarks[i].y,
					z: rawLandmarks[i].z
				});
			}

			// 只在首次检测到时更新状态
			if(!handDetected){
				handDetected = true;
				this.setStatus('active', '已检测到手部');
				console.log('[Gesture] First hand detection!');
			}

			// 更新21点可视化
			window.GestureFeedback.updateLandmarks(landmarks);

			// 手势识别
			var gesture = window.GestureRuleEngine.detectAll(landmarks);
			if(gesture){
				console.log('[Gesture] Gesture recognized:', gesture.type);
				window.GestureFeedback.updateGesture(gesture);
				this.updateLiveStatus(gesture);
				window.GestureBus.emit(gesture);
			} else {
				window.GestureFeedback.updateGesture(null);
			}
		}

		// 在onResults完成后，调度下一帧
		var frameRate = window.GestureSettings.get('frameRate') || 15;
		var delay = Math.max(33, Math.floor(1000 / frameRate));
		console.log('[Gesture] Scheduling next frame in', delay, 'ms');
		frameTimer = setTimeout(function(){ 
			GestureController.sendFrame(); 
		}, delay);
	},

	updateLiveStatus: function(gesture){
		var labels = {
			index_up: '☝️ 食指向上',
			index_down: '👇 食指向下',
			fist: '✊ 握拳',
			swipe_left: '👈 左滑',
			swipe_right: '👉 右滑',
			swipe_up: '🖐️ 上滑',
			swipe_down: '🖐️ 下滑',
			open_palm: '🖐️ 布',
			two_fingers: '✌️ 二指'
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
