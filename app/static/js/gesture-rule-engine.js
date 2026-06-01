(function(){
'use strict';

var WRIST = 0;
var THUMB_CMC = 1, THUMB_MCP = 2, THUMB_IP = 3, THUMB_TIP = 4;
var INDEX_MCP = 5, INDEX_PIP = 6, INDEX_DIP = 7, INDEX_TIP = 8;
var MIDDLE_MCP = 9, MIDDLE_PIP = 10, MIDDLE_DIP = 11, MIDDLE_TIP = 12;
var RING_MCP = 13, RING_PIP = 14, RING_DIP = 15, RING_TIP = 16;
var PINKY_MCP = 17, PINKY_PIP = 18, PINKY_DIP = 19, PINKY_TIP = 20;

var holdStartTime = {};
var lastTriggerTime = {};
var lastGestureTriggerTime = 0;

/* ===== 滑动检测相关变量 ===== */
var trajectoryBuffer = [];
var prevPalmCenter = null;

function distance(a, b){
	return Math.sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y));
}

function validateKeypoints(landmarks){
	if(!landmarks || landmarks.length !== 21) return false;
	for(var i = 0; i < 21; i++){
		if(isNaN(landmarks[i].x) || isNaN(landmarks[i].y)) return false;
	}
	return true;
}

function getPalmSize(landmarks){
	return distance(landmarks[WRIST], landmarks[MIDDLE_MCP]);
}

function getPalmCenter(landmarks){
	return {
		x: (landmarks[WRIST].x + landmarks[INDEX_MCP].x + landmarks[PINKY_MCP].x) / 3,
		y: (landmarks[WRIST].y + landmarks[INDEX_MCP].y + landmarks[PINKY_MCP].y) / 3
	};
}

function canTrigger(type){
	if(!window.GestureSettings.isGestureEnabled(type)) return false;
	var now = Date.now();
	var cd = window.GestureSettings.getCooldown();
	if(lastTriggerTime[type] && now - lastTriggerTime[type] < cd) return false;
	return true;
}

function markTriggered(type){
	lastTriggerTime[type] = Date.now();
	lastGestureTriggerTime = Date.now();
}

/* ===== 判断手指是否伸直 ===== */
/* 核心逻辑：指尖到MCP的距离 > PIP到MCP的距离 * 1.8 说明伸直 */
function isFingerExtended(landmarks, mcp, pip, dip, tip){
	var mcpToTip = distance(landmarks[mcp], landmarks[tip]);
	var mcpToPip = distance(landmarks[mcp], landmarks[pip]);
	if(mcpToPip === 0) return false;
	return mcpToTip > mcpToPip * 1.8;
}

/* ===== 判断手指是否弯曲 ===== */
/* 核心逻辑：指尖到MCP的距离 < MCP到PIP距离 * 1.3 说明弯曲 */
function isFingerCurled(landmarks, mcp, pip, tip){
	var mcpToTip = distance(landmarks[mcp], landmarks[tip]);
	var mcpToPip = distance(landmarks[mcp], landmarks[pip]);
	if(mcpToPip === 0) return true;
	return mcpToTip < mcpToPip * 1.3;
}

/* ===== 食指向上 ===== */
/* 核心逻辑：
   1. 食指伸直（指尖远离MCP）
   2. 食指指尖在MCP上方（Y轴差值大于手掌大小的35%）- 提高阈值
   3. 中指、无名指、小指弯曲
*/
function detectIndexUp(landmarks){
	if(!window.GestureSettings.isGestureEnabled('index_up')) return null;

	var indexMcp = landmarks[INDEX_MCP];
	var indexTip = landmarks[INDEX_TIP];

	var palmSize = getPalmSize(landmarks);

	// 条件1：食指伸直
	var indexExtended = isFingerExtended(landmarks, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP);
	
	// 条件2：食指指尖在MCP上方（Y轴差值大于手掌大小的35%）- 提高阈值
	var yDiff = indexMcp.y - indexTip.y;
	var yThreshold = palmSize * 0.35;

	// 条件3：中指、无名指、小指弯曲
	var middleCurled = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP);
	var ringCurled = isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_TIP);
	var pinkyCurled = isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_TIP);

	if(!indexExtended){
		holdStartTime['index_up'] = null;
		return null;
	}

	if(yDiff < yThreshold){
		holdStartTime['index_up'] = null;
		return null;
	}

	if(!middleCurled || !ringCurled || !pinkyCurled){
		holdStartTime['index_up'] = null;
		return null;
	}

	if(!holdStartTime['index_up']) holdStartTime['index_up'] = Date.now();
	var held = Date.now() - holdStartTime['index_up'];
	if(held >= window.GestureSettings.getHoldTime('index_up') && canTrigger('index_up')){
		holdStartTime['index_up'] = null;
		markTriggered('index_up');
		return {type: 'index_up', confidence: 0.9, targetArea: 'global'};
	}
	return null;
}

/* ===== 食指向下 ===== */
/* 核心逻辑：
   1. 食指伸直
   2. 食指指尖在MCP下方（Y轴差值大于手掌大小的35%）- 提高阈值
   3. 中指、无名指、小指弯曲
*/
function detectIndexDown(landmarks){
	if(!window.GestureSettings.isGestureEnabled('index_down')) return null;

	var indexMcp = landmarks[INDEX_MCP];
	var indexTip = landmarks[INDEX_TIP];
	var palmSize = getPalmSize(landmarks);

	// 条件1：食指伸直
	var indexExtended = isFingerExtended(landmarks, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP);

	// 条件2：食指指尖在MCP下方（Y轴差值大于手掌大小的35%）- 提高阈值
	var yDiff = indexTip.y - indexMcp.y;
	var yThreshold = palmSize * 0.35;

	// 条件3：中指、无名指、小指弯曲
	var middleCurled = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP);
	var ringCurled = isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_TIP);
	var pinkyCurled = isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_TIP);

	if(!indexExtended){
		holdStartTime['index_down'] = null;
		return null;
	}

	if(yDiff < yThreshold){
		holdStartTime['index_down'] = null;
		return null;
	}

	if(!middleCurled || !ringCurled || !pinkyCurled){
		holdStartTime['index_down'] = null;
		return null;
	}

	if(!holdStartTime['index_down']) holdStartTime['index_down'] = Date.now();
	var held = Date.now() - holdStartTime['index_down'];
	if(held >= window.GestureSettings.getHoldTime('index_down') && canTrigger('index_down')){
		holdStartTime['index_down'] = null;
		markTriggered('index_down');
		return {type: 'index_down', confidence: 0.9, targetArea: 'global'};
	}
	return null;
}

/* ===== 握拳 ===== */
/* 核心逻辑：
1. 食指、中指、无名指、小指都弯曲
   2. 所有指尖都接近掌心（指尖到掌心距离 < 手掌大小 * 0.5）
*/
function detectFist(landmarks){
	if(!window.GestureSettings.isGestureEnabled('fist')) return null;

	var palmCenter = getPalmCenter(landmarks);
	var palmSize = getPalmSize(landmarks);

	// 条件1：四个手指都弯曲
	var indexCurled = isFingerCurled(landmarks, INDEX_MCP, INDEX_PIP, INDEX_TIP);
	var middleCurled = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP);
	var ringCurled = isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_TIP);
	var pinkyCurled = isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_TIP);

	// 条件2：指尖接近掌心
	var indexTipToPalm = distance(landmarks[INDEX_TIP], palmCenter);
	var middleTipToPalm = distance(landmarks[MIDDLE_TIP], palmCenter);
	var ringTipToPalm = distance(landmarks[RING_TIP], palmCenter);
	var pinkyTipToPalm = distance(landmarks[PINKY_TIP], palmCenter);

	var tipThreshold = palmSize * 0.5;

	var indexClose = indexTipToPalm < tipThreshold;
	var middleClose = middleTipToPalm < tipThreshold;
	var ringClose = ringTipToPalm < tipThreshold;
	var pinkyClose = pinkyTipToPalm < tipThreshold;

	console.log('[DEBUG detectFist]', {
		indexCurled: indexCurled,
		middleCurled: middleCurled,
		ringCurled: ringCurled,
		pinkyCurled: pinkyCurled,
		indexClose: indexClose,
		middleClose: middleClose,
		ringClose: ringClose,
		pinkyClose: pinkyClose
	});

	if(!indexCurled || !middleCurled || !ringCurled || !pinkyCurled){
		holdStartTime['fist'] = null;
		return null;
	}

	if(!indexClose || !middleClose || !ringClose || !pinkyClose){
		holdStartTime['fist'] = null;
		return null;
	}

	if(!holdStartTime['fist']) holdStartTime['fist'] = Date.now();
	var held = Date.now() - holdStartTime['fist'];
	if(held >= window.GestureSettings.getHoldTime('fist') && canTrigger('fist')){
		holdStartTime['fist'] = null;
		markTriggered('fist');
		return {type: 'fist', confidence: 0.9, targetArea: 'global'};
	}
	return null;
}

/* ===== 二指 ===== */
function detectTwoFingers(landmarks){
	if(!window.GestureSettings.isGestureEnabled('two_fingers')) return null;

	if(!isFingerExtended(landmarks, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP)){
		holdStartTime['two_fingers'] = null;
		return null;
	}
	if(!isFingerExtended(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP)){
		holdStartTime['two_fingers'] = null;
		return null;
	}
	if(!isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_TIP)){
		holdStartTime['two_fingers'] = null;
		return null;
	}
	if(!isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_TIP)){
		holdStartTime['two_fingers'] = null;
		return null;
	}

	var fingerGap = distance(landmarks[INDEX_TIP], landmarks[MIDDLE_TIP]);
	if(fingerGap < 0.02 || fingerGap > 0.2){
		holdStartTime['two_fingers'] = null;
		return null;
	}

	if(!holdStartTime['two_fingers']) holdStartTime['two_fingers'] = Date.now();
	var held = Date.now() - holdStartTime['two_fingers'];
	if(held >= window.GestureSettings.getHoldTime('two_fingers') && canTrigger('two_fingers')){
		holdStartTime['two_fingers'] = null;
		markTriggered('two_fingers');
		return {type: 'two_fingers', confidence: 0.85, targetArea: 'global'};
	}
	return null;
}

/* ===== 滑动检测 ===== */
function updateTrajectory(landmarks){
	var center = getPalmCenter(landmarks);
	if(prevPalmCenter){
		var dx = center.x - prevPalmCenter.x;
		var dy = center.y - prevPalmCenter.y;
		trajectoryBuffer.push({x: center.x, y: center.y, dx: dx, dy: dy, time: Date.now()});
		if(trajectoryBuffer.length > 30) trajectoryBuffer.shift();
	}
	prevPalmCenter = center;
}

function detectSwipeLeft(){
	if(!window.GestureSettings.isGestureEnabled('swipe_left') || trajectoryBuffer.length < 3) return null;
	var recent = trajectoryBuffer.slice(-8);
	var first = recent[0];
	var last = recent[recent.length - 1];
	var deltaX = last.x - first.x;
	var deltaY = Math.abs(last.y - first.y);
	var deltaTime = last.time - first.time;
	if(deltaX < -0.04 && deltaTime < 1500 && deltaTime > 50 && deltaY < Math.abs(deltaX) * 0.6 && canTrigger('swipe_left')){
		markTriggered('swipe_left');
		trajectoryBuffer = [];
		prevPalmCenter = null;
		return {type: 'swipe_left', confidence: Math.min(1, Math.abs(deltaX) / 0.08), targetArea: 'global'};
	}
	return null;
}

function detectSwipeRight(){
	if(!window.GestureSettings.isGestureEnabled('swipe_right') || trajectoryBuffer.length < 3) return null;
	var recent = trajectoryBuffer.slice(-8);
	var first = recent[0];
	var last = recent[recent.length - 1];
	var deltaX = last.x - first.x;
	var deltaY = Math.abs(last.y - first.y);
	var deltaTime = last.time - first.time;
	if(deltaX > 0.04 && deltaTime < 1500 && deltaTime > 50 && deltaY < deltaX * 0.6 && canTrigger('swipe_right')){
		markTriggered('swipe_right');
		trajectoryBuffer = [];
		prevPalmCenter = null;
		return {type: 'swipe_right', confidence: Math.min(1, deltaX / 0.08), targetArea: 'global'};
	}
	return null;
}

function detectSwipes(){
	if(trajectoryBuffer.length < 5) return null;
	return detectSwipeLeft() || detectSwipeRight();
}

var GestureRuleEngine = {
	detectAll: function(landmarks){
		if(!validateKeypoints(landmarks)) return null;

		// 更新轨迹缓冲区（用于滑动检测）
		updateTrajectory(landmarks);

		// 优先检测静态手势
		var gesture = detectFist(landmarks);
		if(gesture) return gesture;

		gesture = detectTwoFingers(landmarks);
		if(gesture) return gesture;

		gesture = detectIndexUp(landmarks);
		if(gesture) return gesture;

		gesture = detectIndexDown(landmarks);
		if(gesture) return gesture;

		// 最后检测滑动手势
		gesture = detectSwipes();
		if(gesture) return gesture;

		return null;
	},

	getLastGesture: function(){
		var types = Object.keys(lastTriggerTime);
		if(types.length === 0) return null;
		var latest = types[0];
		var latestTime = lastTriggerTime[latest] || 0;
		for(var i = 1; i < types.length; i++){
			if((lastTriggerTime[types[i]] || 0) > latestTime){
				latest = types[i];
				latestTime = lastTriggerTime[types[i]];
			}
		}
		return {type: latest, time: latestTime};
	},

	getLastGestureTime: function(){
		return lastGestureTriggerTime;
	},

	reset: function(){
		holdStartTime = {};
		lastTriggerTime = {};
		trajectoryBuffer = [];
		prevPalmCenter = null;
		lastGestureTriggerTime = 0;
	},

	getHoldProgress: function(type){
		if(!holdStartTime[type]) return 0;
		var held = Date.now() - holdStartTime[type];
		var needed = window.GestureSettings.getHoldTime(type) || 400;
		return Math.min(1, held / needed);
	}
};

window.GestureRuleEngine = GestureRuleEngine;

})();
