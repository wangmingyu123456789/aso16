(function(){
'use strict';

var WRIST = 0;
var THUMB_CMC = 1, THUMB_MCP = 2, THUMB_IP = 3, THUMB_TIP = 4;
var INDEX_MCP = 5, INDEX_PIP = 6, INDEX_DIP = 7, INDEX_TIP = 8;
var MIDDLE_MCP = 9, MIDDLE_PIP = 10, MIDDLE_DIP = 11, MIDDLE_TIP = 12;
var RING_MCP = 13, RING_PIP = 14, RING_DIP = 15, RING_TIP = 16;
var PINKY_MCP = 17, PINKY_PIP = 18, PINKY_DIP = 19, PINKY_TIP = 20;

var trajectoryBuffer = [];
var holdStartTime = {};
var lastTriggerTime = {};
var prevPalmCenter = null;

function distance(a,b){
	return Math.sqrt((a.x-b.x)*(a.x-b.x)+(a.y-b.y)*(a.y-b.y)+(a.z-b.z)*(a.z-b.z));
}

function isFingerExtended(landmarks, mcp, tip){
	var mcpJ = landmarks[mcp];
	var tipJ = landmarks[tip];
	var pipJ = mcp + 1 < 21 ? landmarks[mcp+1] : null;
	if(pipJ){
		return distance(tipJ, pipJ) > 0.08;
	}
	return distance(tipJ, mcpJ) > 0.12;
}

function isFingerCurled(landmarks, mcp, tip){
	return !isFingerExtended(landmarks, mcp, tip);
}

function getPalmCenter(landmarks){
	return {
		x: (landmarks[0].x + landmarks[5].x + landmarks[9].x + landmarks[13].x + landmarks[17].x) / 5,
		y: (landmarks[0].y + landmarks[5].y + landmarks[9].y + landmarks[13].y + landmarks[17].y) / 5,
		z: (landmarks[0].z + landmarks[5].z + landmarks[9].z + landmarks[13].z + landmarks[17].z) / 5
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
}

/* ===== 食指向上 ===== */
function detectIndexUp(landmarks){
	if(!window.GestureSettings.isGestureEnabled('index_up')) return null;
	var indexExt = isFingerExtended(landmarks, INDEX_MCP, INDEX_TIP);
	var midCur = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_TIP);
	var ringCur = isFingerCurled(landmarks, RING_MCP, RING_TIP);
	var pinkyCur = isFingerCurled(landmarks, PINKY_MCP, PINKY_TIP);
	var thumbCur = isFingerCurled(landmarks, THUMB_MCP, THUMB_TIP);
	var curled = (midCur?1:0) + (ringCur?1:0) + (pinkyCur?1:0);
	var indexTip = landmarks[INDEX_TIP];
	var indexPip = landmarks[INDEX_PIP];
	var pointingUp = indexTip.y < indexPip.y;

	if(indexExt && curled >= 2 && thumbCur && pointingUp){
		if(!holdStartTime['index_up']) holdStartTime['index_up'] = Date.now();
		var held = Date.now() - holdStartTime['index_up'];
		if(held >= window.GestureSettings.getHoldTime('index_up') && canTrigger('index_up')){
			holdStartTime['index_up'] = null;
			markTriggered('index_up');
			return {type:'index_up', confidence:0.85, targetArea:'global'};
		}
	} else {
		holdStartTime['index_up'] = null;
	}
	return null;
}

/* ===== 食指向下 ===== */
function detectIndexDown(landmarks){
	if(!window.GestureSettings.isGestureEnabled('index_down')) return null;
	var indexExt = isFingerExtended(landmarks, INDEX_MCP, INDEX_TIP);
	var midCur = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_TIP);
	var ringCur = isFingerCurled(landmarks, RING_MCP, RING_TIP);
	var pinkyCur = isFingerCurled(landmarks, PINKY_MCP, PINKY_TIP);
	var thumbCur = isFingerCurled(landmarks, THUMB_MCP, THUMB_TIP);
	var curled = (midCur?1:0) + (ringCur?1:0) + (pinkyCur?1:0);
	var indexTip = landmarks[INDEX_TIP];
	var indexPip = landmarks[INDEX_PIP];
	var pointingDown = indexTip.y > indexPip.y;

	if(indexExt && curled >= 2 && thumbCur && pointingDown){
		if(!holdStartTime['index_down']) holdStartTime['index_down'] = Date.now();
		var held = Date.now() - holdStartTime['index_down'];
		if(held >= window.GestureSettings.getHoldTime('index_down') && canTrigger('index_down')){
			holdStartTime['index_down'] = null;
			markTriggered('index_down');
			return {type:'index_down', confidence:0.85, targetArea:'global'};
		}
	} else {
		holdStartTime['index_down'] = null;
	}
	return null;
}

/* ===== 握拳 ===== */
function detectFist(landmarks){
	if(!window.GestureSettings.isGestureEnabled('fist')) return null;
	var tips = [INDEX_TIP, MIDDLE_TIP, RING_TIP, PINKY_TIP];
	var allClose = true;
	var wrist = landmarks[WRIST];
	var maxDist = 0;
	for(var i=0;i<tips.length;i++){
		var d = distance(landmarks[tips[i]], wrist);
		maxDist = Math.max(maxDist, d);
		if(d > 0.22) allClose = false;
	}
	if(allClose){
		if(!holdStartTime['fist']) holdStartTime['fist'] = Date.now();
		var held = Date.now() - holdStartTime['fist'];
		if(held >= window.GestureSettings.getHoldTime('fist') && canTrigger('fist')){
			holdStartTime['fist'] = null;
			markTriggered('fist');
			return {type:'fist', confidence:Math.max(0.5, 1 - maxDist/0.22), targetArea:'global'};
		}
	} else {
		holdStartTime['fist'] = null;
	}
	return null;
}

/* ===== 滑动检测 ===== */
function updateTrajectory(landmarks){
	var center = getPalmCenter(landmarks);
	if(prevPalmCenter){
		var dx = center.x - prevPalmCenter.x;
		var dy = center.y - prevPalmCenter.y;
		trajectoryBuffer.push({x:center.x, y:center.y, dx:dx, dy:dy, time:Date.now()});
		if(trajectoryBuffer.length > 30) trajectoryBuffer.shift();
	}
	prevPalmCenter = center;
}

function detectSwipeLeft(){
	if(!window.GestureSettings.isGestureEnabled('swipe_left') || trajectoryBuffer.length < 5) return null;
	var recent = trajectoryBuffer.slice(-8);
	var first = recent[0];
	var last = recent[recent.length-1];
	var deltaX = last.x - first.x;
	var deltaY = Math.abs(last.y - first.y);
	var deltaTime = last.time - first.time;
	if(deltaX < -0.08 && deltaTime < 1200 && deltaTime > 100 && deltaY < Math.abs(deltaX)*0.6 && canTrigger('swipe_left')){
		markTriggered('swipe_left');
		trajectoryBuffer = [];
		prevPalmCenter = null;
		return {type:'swipe_left', confidence:Math.min(1, Math.abs(deltaX)/0.15), targetArea:'global'};
	}
	return null;
}

function detectSwipeRight(){
	if(!window.GestureSettings.isGestureEnabled('swipe_right') || trajectoryBuffer.length < 5) return null;
	var recent = trajectoryBuffer.slice(-8);
	var first = recent[0];
	var last = recent[recent.length-1];
	var deltaX = last.x - first.x;
	var deltaY = Math.abs(last.y - first.y);
	var deltaTime = last.time - first.time;
	if(deltaX > 0.08 && deltaTime < 1200 && deltaTime > 100 && deltaY < deltaX*0.6 && canTrigger('swipe_right')){
		markTriggered('swipe_right');
		trajectoryBuffer = [];
		prevPalmCenter = null;
		return {type:'swipe_right', confidence:Math.min(1, deltaX/0.15), targetArea:'global'};
	}
	return null;
}

function detectSwipeUp(){
	if(!window.GestureSettings.isGestureEnabled('swipe_up') || trajectoryBuffer.length < 5) return null;
	var recent = trajectoryBuffer.slice(-8);
	var first = recent[0];
	var last = recent[recent.length-1];
	var deltaY = last.y - first.y;
	var deltaX = Math.abs(last.x - first.x);
	var deltaTime = last.time - first.time;
	if(deltaY < -0.08 && deltaTime < 1200 && deltaTime > 100 && deltaX < Math.abs(deltaY)*0.6 && canTrigger('swipe_up')){
		markTriggered('swipe_up');
		trajectoryBuffer = [];
		prevPalmCenter = null;
		return {type:'swipe_up', confidence:Math.min(1, Math.abs(deltaY)/0.15), targetArea:'global'};
	}
	return null;
}

function detectSwipeDown(){
	if(!window.GestureSettings.isGestureEnabled('swipe_down') || trajectoryBuffer.length < 5) return null;
	var recent = trajectoryBuffer.slice(-8);
	var first = recent[0];
	var last = recent[recent.length-1];
	var deltaY = last.y - first.y;
	var deltaX = Math.abs(last.x - first.x);
	var deltaTime = last.time - first.time;
	if(deltaY > 0.08 && deltaTime < 1200 && deltaTime > 100 && deltaX < deltaY*0.6 && canTrigger('swipe_down')){
		markTriggered('swipe_down');
		trajectoryBuffer = [];
		prevPalmCenter = null;
		return {type:'swipe_down', confidence:Math.min(1, deltaY/0.15), targetArea:'global'};
	}
	return null;
}

function detectSwipes(){
	if(trajectoryBuffer.length < 5) return null;
	return detectSwipeLeft() || detectSwipeRight() || detectSwipeUp() || detectSwipeDown();
}

function resetTrajectory(){
	trajectoryBuffer = [];
	prevPalmCenter = null;
}

var GestureRuleEngine = {
	detectAll: function(landmarks){
		updateTrajectory(landmarks);
		var gesture = null;
		gesture = detectSwipeLeft() || detectSwipeRight() || detectSwipeUp() || detectSwipeDown();
		if(gesture) return gesture;
		gesture = detectFist(landmarks);
		if(gesture) return gesture;
		gesture = detectIndexUp(landmarks);
		if(gesture) return gesture;
		gesture = detectIndexDown(landmarks);
		if(gesture) return gesture;
		return null;
	},

	getLastGesture: function(){
		var types = Object.keys(lastTriggerTime);
		if(types.length === 0) return null;
		var latest = types[0];
		var latestTime = lastTriggerTime[latest] || 0;
		for(var i=1;i<types.length;i++){
			if((lastTriggerTime[types[i]] || 0) > latestTime){
				latest = types[i];
				latestTime = lastTriggerTime[types[i]];
			}
		}
		return {type:latest, time:latestTime};
	},

	reset: function(){
		holdStartTime = {};
		lastTriggerTime = {};
		trajectoryBuffer = [];
		prevPalmCenter = null;
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
