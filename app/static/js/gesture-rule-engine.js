(function(){
'use strict';

/* ===== 关键点索引常量 ===== */
var WRIST = 0;
var THUMB_CMC = 1, THUMB_MCP = 2, THUMB_IP = 3, THUMB_TIP = 4;
var INDEX_MCP = 5, INDEX_PIP = 6, INDEX_DIP = 7, INDEX_TIP = 8;
var MIDDLE_MCP = 9, MIDDLE_PIP = 10, MIDDLE_DIP = 11, MIDDLE_TIP = 12;
var RING_MCP = 13, RING_PIP = 14, RING_DIP = 15, RING_TIP = 16;
var PINKY_MCP = 17, PINKY_PIP = 18, PINKY_DIP = 19, PINKY_TIP = 20;

/* ===== 状态变量 ===== */
var trajectoryBuffer = [];
var holdStartTime = {};
var lastTriggerTime = {};
var prevPalmCenter = null;
var lastGestureTriggerTime = 0;
var gestureHistory = [];
var HISTORY_SIZE = 5;
var CONSENSUS_THRESHOLD = 2;

/* ===== 关键点平滑缓冲区 ===== */
var keypointHistory = [];
var SMOOTHING_FRAMES = 2;

/* ===== 手势稳定状态机 ===== */
var currentStableGesture = null;
var stableGestureCount = 0;
var GESTURE_STABLE_FRAMES = 2;

/* ===== 工具函数 ===== */
function distance(a, b){
	return Math.sqrt((a.x - b.x) * (a.x - b.x) + (a.y - b.y) * (a.y - b.y));
}

function getFingerAngle(landmarks, mcp, pip, tip){
	var mcpJ = landmarks[mcp];
	var pipJ = landmarks[pip];
	var tipJ = landmarks[tip];
	
	var v1 = {x: pipJ.x - mcpJ.x, y: pipJ.y - mcpJ.y};
	var v2 = {x: tipJ.x - pipJ.x, y: tipJ.y - pipJ.y};
	
	var dot = v1.x * v2.x + v1.y * v2.y;
	var mag1 = Math.sqrt(v1.x * v1.x + v1.y * v1.y);
	var mag2 = Math.sqrt(v2.x * v2.x + v2.y * v2.y);
	
	if(mag1 === 0 || mag2 === 0) return 0;
	
	var cos = dot / (mag1 * mag2);
	cos = Math.max(-1, Math.min(1, cos));
	return Math.acos(cos) * (180 / Math.PI);
}

/* ===== 关键点平滑处理 ===== */
function smoothKeypoints(landmarks){
	keypointHistory.push(landmarks);
	if(keypointHistory.length > SMOOTHING_FRAMES){
		keypointHistory.shift();
	}
	
	if(keypointHistory.length < SMOOTHING_FRAMES) return landmarks;
	
	var smoothed = [];
	for(var i = 0; i < 21; i++){
		var sumX = 0, sumY = 0, sumZ = 0;
		for(var j = 0; j < keypointHistory.length; j++){
			sumX += keypointHistory[j][i].x;
			sumY += keypointHistory[j][i].y;
			sumZ += keypointHistory[j][i].z;
		}
		smoothed.push({
			x: sumX / keypointHistory.length,
			y: sumY / keypointHistory.length,
			z: sumZ / keypointHistory.length
		});
	}
	return smoothed;
}

/* ===== 关键点有效性检查 ===== */
function validateKeypoints(landmarks){
	if(!landmarks || landmarks.length !== 21) return false;
	
	for(var i = 0; i < 21; i++){
		if(isNaN(landmarks[i].x) || isNaN(landmarks[i].y) || isNaN(landmarks[i].z)){
			return false;
		}
		if(landmarks[i].x < -0.5 || landmarks[i].x > 1.5 ||
		   landmarks[i].y < -0.5 || landmarks[i].y > 1.5){
			return false;
		}
	}
	return true;
}

/* ===== 手指状态判断（优化版） ===== */
function isFingerExtended(landmarks, mcp, pip, dip, tip){
	var angle = getFingerAngle(landmarks, mcp, pip, tip);
	
	var mcpJ = landmarks[mcp];
	var pipJ = landmarks[pip];
	var tipJ = landmarks[tip];
	
	var fingerLen = distance(mcpJ, tipJ);
	var pipToTip = distance(pipJ, tipJ);
	
	var angleThreshold = 160;
	var distanceRatio = pipToTip / fingerLen;
	
	var pipAngle = getFingerAngle(landmarks, mcp, pip, dip);
	
	return angle > angleThreshold && distanceRatio > 0.65 && pipAngle > 140;
}

function isFingerCurled(landmarks, mcp, pip, dip, tip){
	var angle = getFingerAngle(landmarks, mcp, pip, tip);
	
	var mcpJ = landmarks[mcp];
	var pipJ = landmarks[pip];
	var tipJ = landmarks[tip];
	
	var fingerLen = distance(mcpJ, tipJ);
	var pipToTip = distance(pipJ, tipJ);
	
	var angleThreshold = 80;
	var distanceRatio = pipToTip / fingerLen;
	
	return angle < angleThreshold && distanceRatio < 0.45;
}

function isThumbExtended(landmarks){
	var cmc = landmarks[THUMB_CMC];
	var ip = landmarks[THUMB_IP];
	var tip = landmarks[THUMB_TIP];

	var thumbLen = distance(cmc, tip);
	var ipToTip = distance(ip, tip);

	return ipToTip > thumbLen * 0.55;
}

function isThumbCurled(landmarks){
	var cmc = landmarks[THUMB_CMC];
	var ip = landmarks[THUMB_IP];
	var tip = landmarks[THUMB_TIP];

	var thumbLen = distance(cmc, tip);
	var ipToTip = distance(ip, tip);

	return ipToTip < thumbLen * 0.5;
}

function getPalmCenter(landmarks){
	return {
		x: (landmarks[0].x + landmarks[5].x + landmarks[9].x + landmarks[13].x + landmarks[17].x) / 5,
		y: (landmarks[0].y + landmarks[5].y + landmarks[9].y + landmarks[13].y + landmarks[17].y) / 5,
		z: (landmarks[0].z + landmarks[5].z + landmarks[9].z + landmarks[13].z + landmarks[17].z) / 5
	};
}

/* ===== 触发控制 ===== */
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

/* ===== 手势历史平滑处理 ===== */
function addToHistory(gestureType){
	gestureHistory.push(gestureType || 'none');
	if(gestureHistory.length > HISTORY_SIZE){
		gestureHistory.shift();
	}
	
	if(gestureType && gestureType !== 'none'){
		if(gestureType === currentStableGesture){
			stableGestureCount++;
		} else {
			currentStableGesture = gestureType;
			stableGestureCount = 1;
		}
	} else {
		stableGestureCount = 0;
		currentStableGesture = null;
	}
}

function getConsensusGesture(){
	if(currentStableGesture && stableGestureCount >= GESTURE_STABLE_FRAMES){
		return {type: currentStableGesture, confidence: 0.95};
	}
	
	if(gestureHistory.length < HISTORY_SIZE) return null;
	
	var counts = {};
	for(var i = 0; i < gestureHistory.length; i++){
		var g = gestureHistory[i];
		if(g && g !== 'none'){
			counts[g] = (counts[g] || 0) + 1;
		}
	}
	
	var maxCount = 0;
	var maxGesture = null;
	for(var type in counts){
		if(counts[type] > maxCount){
			maxCount = counts[type];
			maxGesture = type;
		}
	}
	
	if(maxCount >= CONSENSUS_THRESHOLD){
		return {type: maxGesture, confidence: maxCount / HISTORY_SIZE};
	}
	return null;
}

/* ===== 布（五指伸直） ===== */
function detectOpenPalm(landmarks){
	if(!window.GestureSettings.isGestureEnabled('open_palm')) return null;

	var indexExt = isFingerExtended(landmarks, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP);
	var midExt = isFingerExtended(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP);
	var ringExt = isFingerExtended(landmarks, RING_MCP, RING_PIP, RING_DIP, RING_TIP);
	var pinkyExt = isFingerExtended(landmarks, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP);
	var thumbExt = isThumbExtended(landmarks);

	var extendedCount = (indexExt ? 1 : 0) + (midExt ? 1 : 0) + (ringExt ? 1 : 0) + (pinkyExt ? 1 : 0) + (thumbExt ? 1 : 0);

	// 优化：至少4指伸直（允许1指不完全伸直）
	if(extendedCount >= 4){
		// 增加：手指间距检测（布手势应该是五指张开的）
		var indexTip = landmarks[INDEX_TIP];
		var midTip = landmarks[MIDDLE_TIP];
		var ringTip = landmarks[RING_TIP];
		var pinkyTip = landmarks[PINKY_TIP];
		
		// 计算相邻手指间距
		var indexMidGap = distance(indexTip, midTip);
		var midRingGap = distance(midTip, ringTip);
		var ringPinkyGap = distance(ringTip, pinkyTip);
		
		// 布手势特征：手指间距应该较大（张开状态）
		var avgGap = (indexMidGap + midRingGap + ringPinkyGap) / 3;
		
		// 排除二指手势：如果无名指和小指弯曲，则不是布
		var ringCur = isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_DIP, RING_TIP);
		var pinkyCur = isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP);
		
		// 如果无名指或小指弯曲，不是布手势
		if(ringCur || pinkyCur){
			holdStartTime['open_palm'] = null;
			return null;
		}
		
		// 增加手指间距阈值（确保是张开状态）
		if(avgGap > 0.03){
			if(!holdStartTime['open_palm']) holdStartTime['open_palm'] = Date.now();
			var held = Date.now() - holdStartTime['open_palm'];
			if(held >= window.GestureSettings.getHoldTime('open_palm') && canTrigger('open_palm')){
				holdStartTime['open_palm'] = null;
				markTriggered('open_palm');
				return {type: 'open_palm', confidence: extendedCount / 5, targetArea: 'global'};
			}
		} else {
			holdStartTime['open_palm'] = null;
		}
	} else {
		holdStartTime['open_palm'] = null;
	}
	return null;
}

/* ===== 二指（食指+中指伸直） ===== */
function detectTwoFingers(landmarks){
	if(!window.GestureSettings.isGestureEnabled('two_fingers')) return null;

	// 二指检测（和平手势）：食指和中指伸展，无名指和小指弯曲，拇指自然弯曲或放松
	// 使用较宽松的角度阈值（不是完全伸直也能识别）
	var indexAngle = getFingerAngle(landmarks, INDEX_MCP, INDEX_PIP, INDEX_TIP);
	var midAngle = getFingerAngle(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_TIP);
	var indexStraight = indexAngle > 145;
	var midStraight = midAngle > 145;

	var ringCur = isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_DIP, RING_TIP);
	var pinkyCur = isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP);
	var thumbExt = isThumbExtended(landmarks);

	if(indexStraight && midStraight && ringCur && pinkyCur && !thumbExt){
		var iTip = landmarks[INDEX_TIP];
		var mTip = landmarks[MIDDLE_TIP];
		var fingerGap = distance(iTip, mTip);

		// 二指特征：两指之间有适当间距（并拢但不重叠）
		if(fingerGap > 0.025 && fingerGap < 0.2){
			if(!holdStartTime['two_fingers']) holdStartTime['two_fingers'] = Date.now();
			var held = Date.now() - holdStartTime['two_fingers'];
			if(held >= window.GestureSettings.getHoldTime('two_fingers') && canTrigger('two_fingers')){
				holdStartTime['two_fingers'] = null;
				markTriggered('two_fingers');
				return {type: 'two_fingers', confidence: 0.85, targetArea: 'global'};
			}
		} else {
			holdStartTime['two_fingers'] = null;
		}
	} else {
		holdStartTime['two_fingers'] = null;
	}
	return null;
}

/* ===== 食指向上 ===== */
function detectIndexUp(landmarks){
	if(!window.GestureSettings.isGestureEnabled('index_up')) return null;

	var indexExt = isFingerExtended(landmarks, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP);
	var midCur = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP);
	var ringCur = isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_DIP, RING_TIP);
	var pinkyCur = isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP);

	var curledCount = (midCur ? 1 : 0) + (ringCur ? 1 : 0) + (pinkyCur ? 1 : 0);

	var indexTip = landmarks[INDEX_TIP];
	var indexPip = landmarks[INDEX_PIP];
	var pointingUp = indexTip.y < indexPip.y;

	if(indexExt && curledCount >= 3 && pointingUp){
		if(!holdStartTime['index_up']) holdStartTime['index_up'] = Date.now();
		var held = Date.now() - holdStartTime['index_up'];
		if(held >= window.GestureSettings.getHoldTime('index_up') && canTrigger('index_up')){
			holdStartTime['index_up'] = null;
			markTriggered('index_up');
			return {type: 'index_up', confidence: 0.9, targetArea: 'global'};
		}
	} else {
		holdStartTime['index_up'] = null;
	}
	return null;
}

/* ===== 食指向下 ===== */
function detectIndexDown(landmarks){
	if(!window.GestureSettings.isGestureEnabled('index_down')) return null;

	var indexExt = isFingerExtended(landmarks, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP);
	var midCur = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP);
	var ringCur = isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_DIP, RING_TIP);
	var pinkyCur = isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP);

	var curledCount = (midCur ? 1 : 0) + (ringCur ? 1 : 0) + (pinkyCur ? 1 : 0);

	var indexTip = landmarks[INDEX_TIP];
	var indexPip = landmarks[INDEX_PIP];
	var pointingDown = indexTip.y > indexPip.y;

	if(indexExt && curledCount >= 3 && pointingDown){
		if(!holdStartTime['index_down']) holdStartTime['index_down'] = Date.now();
		var held = Date.now() - holdStartTime['index_down'];
		if(held >= window.GestureSettings.getHoldTime('index_down') && canTrigger('index_down')){
			holdStartTime['index_down'] = null;
			markTriggered('index_down');
			return {type: 'index_down', confidence: 0.9, targetArea: 'global'};
		}
	} else {
		holdStartTime['index_down'] = null;
	}
	return null;
}

/* ===== 握拳 ===== */
function detectFist(landmarks){
	if(!window.GestureSettings.isGestureEnabled('fist')) return null;

	var indexCur = isFingerCurled(landmarks, INDEX_MCP, INDEX_PIP, INDEX_DIP, INDEX_TIP);
	var midCur = isFingerCurled(landmarks, MIDDLE_MCP, MIDDLE_PIP, MIDDLE_DIP, MIDDLE_TIP);
	var ringCur = isFingerCurled(landmarks, RING_MCP, RING_PIP, RING_DIP, RING_TIP);
	var pinkyCur = isFingerCurled(landmarks, PINKY_MCP, PINKY_PIP, PINKY_DIP, PINKY_TIP);
	var thumbCur = isThumbCurled(landmarks);

	var curledCount = (indexCur ? 1 : 0) + (midCur ? 1 : 0) + (ringCur ? 1 : 0) + (pinkyCur ? 1 : 0);

	// 优化：4指都弯曲 + 拇指弯曲（严格条件）
	if(curledCount >= 4 && thumbCur){
		// 增加：指尖到掌心距离检测（握拳时指尖应该靠近掌心）
		var wrist = landmarks[WRIST];
		var indexTip = landmarks[INDEX_TIP];
		var midTip = landmarks[MIDDLE_TIP];
		var ringTip = landmarks[RING_TIP];
		var pinkyTip = landmarks[PINKY_TIP];
		
		// 计算指尖到手腕的平均距离（握拳时应该较小）
		var avgDistToWrist = (
			distance(indexTip, wrist) +
			distance(midTip, wrist) +
			distance(ringTip, wrist) +
			distance(pinkyTip, wrist)
		) / 4;
		
		// 握拳特征：指尖到手腕距离 < 0.25（收紧状态）
		if(avgDistToWrist < 0.25){
			if(!holdStartTime['fist']) holdStartTime['fist'] = Date.now();
			var held = Date.now() - holdStartTime['fist'];
			if(held >= window.GestureSettings.getHoldTime('fist') && canTrigger('fist')){
				holdStartTime['fist'] = null;
				markTriggered('fist');
				return {type: 'fist', confidence: 0.95, targetArea: 'global'};
			}
		} else {
			holdStartTime['fist'] = null;
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
	if(deltaX < -0.04 && deltaTime < 1500 && deltaTime > 50 && deltaY < Math.abs(deltaX) * 0.8 && canTrigger('swipe_left')){
		markTriggered('swipe_left');
		trajectoryBuffer = [];
		prevPalmCenter = null;
		return {type: 'swipe_left', confidence: Math.min(1, Math.abs(deltaX) / 0.12), targetArea: 'global'};
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
	if(deltaX > 0.04 && deltaTime < 1500 && deltaTime > 50 && deltaY < deltaX * 0.8 && canTrigger('swipe_right')){
		markTriggered('swipe_right');
		trajectoryBuffer = [];
		prevPalmCenter = null;
		return {type: 'swipe_right', confidence: Math.min(1, deltaX / 0.12), targetArea: 'global'};
	}
	return null;
}


function detectSwipes(){
	if(trajectoryBuffer.length < 3) return null;
	return detectSwipeLeft() || detectSwipeRight();
}

function resetTrajectory(){
	trajectoryBuffer = [];
	prevPalmCenter = null;
}

/* ===== 主检测函数 ===== */
var GestureRuleEngine = {
	detectAll: function(rawLandmarks){
		if(!validateKeypoints(rawLandmarks)){
			addToHistory(null);
			return null;
		}
		
		var landmarks = smoothKeypoints(rawLandmarks);
		
		updateTrajectory(landmarks);

		// 1. 优先检测滑动手势（动态手势）
		var gesture = detectSwipeLeft() || detectSwipeRight();
		if(gesture){
			addToHistory(gesture.type);
			return gesture;
		}

		// 2. 检测握拳（4指弯曲，优先级最高）
		gesture = detectFist(landmarks);
		if(gesture){
			addToHistory('fist');
			return gesture;
		}
		
		// 3. 检测二指（食指+中指伸直，无名指+小指+拇指弯曲）
		gesture = detectTwoFingers(landmarks);
		if(gesture){
			addToHistory('two_fingers');
			return gesture;
		}
		
		// 4. 检测布（4-5指伸直，无名指和小指不能弯曲）
		gesture = detectOpenPalm(landmarks);
		if(gesture){
			addToHistory('open_palm');
			return gesture;
		}
		
		// 5. 检测食指向上（食指伸直，其他3指弯曲）
		gesture = detectIndexUp(landmarks);
		if(gesture){
			addToHistory('index_up');
			return gesture;
		}
		
		// 6. 检测食指向下（食指伸直，其他3指弯曲）
		gesture = detectIndexDown(landmarks);
		if(gesture){
			addToHistory('index_down');
			return gesture;
		}
		
		addToHistory(null);

		// 7. 共识机制（平滑处理）
		var consensus = getConsensusGesture();
		if(consensus){
			return {
				type: consensus.type,
				confidence: consensus.confidence,
				targetArea: 'global'
			};
		}

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
		gestureHistory = [];
		keypointHistory = [];
		currentStableGesture = null;
		stableGestureCount = 0;
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
