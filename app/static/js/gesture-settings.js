(function(){
'use strict';

var STORAGE_KEY = 'gesture_settings';

var defaults = {
	enabled: true,
	frameRate: 15,
	cameraWidth: 320,
	cameraHeight: 240,
	minDetectionConfidence: 0.7,
	minTrackingConfidence: 0.5,
	showFeedback: true,
	gestures: {
		index_up: true,
		index_down: true,
		fist: true,
		swipe_left: true,
		swipe_right: true,
		swipe_up: true,
		swipe_down: true,
		open_palm: true,
		two_fingers: true
	},
	holdTimes: {
		index_up: 400,
		index_down: 400,
		fist: 600,
		open_palm: 500,
		two_fingers: 500
	},
	cooldownMs: 800
};

function load(){
	try{
		var saved = JSON.parse(localStorage.getItem(STORAGE_KEY));
		if(saved) return merge(defaults, saved);
	}catch(e){}
	return JSON.parse(JSON.stringify(defaults));
}

function merge(base, overrides){
	var result = JSON.parse(JSON.stringify(base));
	for(var k in overrides){
		if(overrides.hasOwnProperty(k)){
			if(typeof result[k] === 'object' && result[k] !== null && !Array.isArray(result[k]) && typeof overrides[k] === 'object' && !Array.isArray(overrides[k])){
				result[k] = merge(result[k], overrides[k]);
			} else {
				result[k] = overrides[k];
			}
		}
	}
	return result;
}

function save(settings){
	localStorage.setItem(STORAGE_KEY, JSON.stringify(settings));
}

var currentSettings = load();

var GestureSettings = {
	get: function(key){
		if(key){
			var parts = key.split('.');
			var val = currentSettings;
			for(var i=0;i<parts.length;i++){
				if(val === undefined || val === null) return undefined;
				val = val[parts[i]];
			}
			return val;
		}
		return currentSettings;
	},

	set: function(key, value){
		var parts = key.split('.');
		var target = currentSettings;
		for(var i=0;i<parts.length-1;i++){
			if(target[parts[i]] === undefined) target[parts[i]] = {};
			target = target[parts[i]];
		}
		target[parts[parts.length-1]] = value;
		save(currentSettings);
	},

	reset: function(){
		currentSettings = JSON.parse(JSON.stringify(defaults));
		save(currentSettings);
	},

	isGestureEnabled: function(type){
		return currentSettings.gestures && currentSettings.gestures[type] !== false;
	},

	toggleAll: function(enabled){
		currentSettings.enabled = enabled;
		save(currentSettings);
	},

	getHoldTime: function(type){
		return (currentSettings.holdTimes && currentSettings.holdTimes[type]) || 400;
	},

	getCooldown: function(){
		return currentSettings.cooldownMs || 800;
	}
};

window.GestureSettings = GestureSettings;

})();
