(function(){
'use strict';

var feedbackCanvas = null;
var feedbackCtx = null;
var lastLandmarks = null;
var lastGesture = null;
var animFrameId = null;

var CONNECTION_LINES = [
	[0,1],[1,2],[2,3],[3,4],
	[0,5],[5,6],[6,7],[7,8],
	[0,9],[9,10],[10,11],[11,12],
	[0,13],[13,14],[14,15],[15,16],
	[0,17],[17,18],[18,19],[19,20],
	[5,9],[9,13],[13,17]
];

var GESTURE_LABELS = {
	index_up: '☝️ 食指向上',
	index_down: '👇 食指向下',
	fist: '✊ 握拳',
	swipe_left: '👈 左滑',
	swipe_right: '👉 右滑',
	swipe_up: '🖐️ 上滑',
	swipe_down: '🖐️ 下滑'
};

function init(canvas){
	feedbackCanvas = canvas;
	feedbackCtx = canvas.getContext('2d');
}

function updateLandmarks(landmarks){
	lastLandmarks = landmarks;
}

function updateGesture(gesture){
	lastGesture = gesture;
}

function draw(){
	if(!feedbackCtx || !feedbackCanvas) return;
	var ctx = feedbackCtx;
	var w = feedbackCanvas.width;
	var h = feedbackCanvas.height;

	ctx.clearRect(0, 0, w, h);

	if(!lastLandmarks) {
		animFrameId = requestAnimationFrame(draw);
		return;
	}

	var landmarks = lastLandmarks;

	ctx.save();
	ctx.scale(-1, 1);
	ctx.translate(-w, 0);

	// 画连接线
	ctx.strokeStyle = 'rgba(0, 212, 255, 0.5)';
	ctx.lineWidth = 2;
	for(var i=0;i<CONNECTION_LINES.length;i++){
		var pair = CONNECTION_LINES[i];
		var p1 = landmarks[pair[0]];
		var p2 = landmarks[pair[1]];
		if(p1 && p2){
			ctx.beginPath();
			ctx.moveTo(p1.x * w, p1.y * h);
			ctx.lineTo(p2.x * w, p2.y * h);
			ctx.stroke();
		}
	}

	// 画关键点
	for(var j=0;j<landmarks.length;j++){
		var p = landmarks[j];
		if(!p) continue;
		var x = p.x * w;
		var y = p.y * h;
		var z = p.z || 0;

		ctx.beginPath();
		ctx.arc(x, y, Math.max(3, 6 + z * 10), 0, Math.PI * 2);
		ctx.fillStyle = 'rgba(0, 212, 255, 0.8)';
		ctx.fill();
		ctx.strokeStyle = 'rgba(255, 255, 255, 0.3)';
		ctx.lineWidth = 1;
		ctx.stroke();
	}

	ctx.restore();

	// 手势标签
	if(lastGesture && lastGesture.type){
		var label = GESTURE_LABELS[lastGesture.type] || lastGesture.type;
		var conf = Math.round((lastGesture.confidence || 0) * 100);
		ctx.fillStyle = 'rgba(0, 230, 118, 0.9)';
		ctx.font = 'bold 14px sans-serif';
		ctx.textAlign = 'center';
		ctx.fillText(label + ' ' + conf + '%', w/2, 24);

		// 进度条
		var progress = window.GestureRuleEngine.getHoldProgress(lastGesture.type);
		if(progress > 0 && progress < 1){
			ctx.fillStyle = 'rgba(0, 230, 118, 0.2)';
			ctx.fillRect(w/2 - 60, 32, 120, 4);
			ctx.fillStyle = 'rgba(0, 230, 118, 0.8)';
			ctx.fillRect(w/2 - 60, 32, 120 * progress, 4);
		}
	}

	animFrameId = requestAnimationFrame(draw);
}

function start(){
	if(animFrameId) return;
	draw();
}

function stop(){
	if(animFrameId){
		cancelAnimationFrame(animFrameId);
		animFrameId = null;
	}
	if(feedbackCtx && feedbackCanvas){
		feedbackCtx.clearRect(0, 0, feedbackCanvas.width, feedbackCanvas.height);
	}
	lastLandmarks = null;
	lastGesture = null;
}

function resize(){
	if(feedbackCanvas && feedbackCanvas.parentElement){
		var rect = feedbackCanvas.parentElement.getBoundingClientRect();
		feedbackCanvas.width = rect.width * (window.devicePixelRatio || 1);
		feedbackCanvas.height = rect.height * (window.devicePixelRatio || 1);
		feedbackCanvas.style.width = rect.width + 'px';
		feedbackCanvas.style.height = rect.height + 'px';
	}
}

window.GestureFeedback = {
	init: init,
	updateLandmarks: updateLandmarks,
	updateGesture: updateGesture,
	start: start,
	stop: stop,
	resize: resize
};

})();
