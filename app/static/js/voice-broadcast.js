(function(){
'use strict';

var enabled = localStorage.getItem('voice_broadcast_enabled') !== 'false';
var volume = parseFloat(localStorage.getItem('voice_broadcast_volume') || '0.7');
var rate = parseFloat(localStorage.getItem('voice_broadcast_rate') || '1.0');
var pitch = parseFloat(localStorage.getItem('voice_broadcast_pitch') || '1.0');
var toastTimer = null;
var currentUtterance = null;

var toastContainer = null;
function ensureContainer(){
	if(toastContainer) return;
	toastContainer = document.createElement('div');
	toastContainer.id = 'voiceToastContainer';
	toastContainer.style.cssText = 'position:fixed;bottom:24px;right:24px;z-index:99999;display:flex;flex-direction:column;gap:8px;pointer-events:none;';
	document.body.appendChild(toastContainer);
}

function showToast(text, duration){
	if(!enabled) return;
	ensureContainer();
	var el = document.createElement('div');
	el.style.cssText = 'display:flex;align-items:center;gap:8px;padding:10px 16px;background:rgba(15,20,40,0.88);border:1px solid rgba(0,212,255,0.2);border-radius:10px;color:#e0e0f0;font-size:13px;backdrop-filter:blur(12px);box-shadow:0 4px 20px rgba(0,0,0,0.3);pointer-events:auto;animation:voiceToastIn 0.3s ease;max-width:360px;';
	el.innerHTML = '<span style="flex-shrink:0;font-size:16px;animation:voiceWave 1s ease-in-out infinite">🔊</span><span style="flex:1;line-height:1.4">'+text+'</span><span style="flex-shrink:0;font-size:11px;color:rgba(255,255,255,0.3);cursor:pointer;padding:2px 6px;border-radius:4px;transition:all 0.2s;" onclick="this.parentElement.remove()" onmouseover="this.style.background=\'rgba(255,255,255,0.1)\'" onmouseout="this.style.background=\'transparent\'">✕</span>';
	toastContainer.appendChild(el);
	if(duration !== 0){
		setTimeout(function(){ if(el.parentNode) el.remove(); }, duration || 5000);
	}
}

var styleInjected = false;
function injectStyles(){
	if(styleInjected) return;
	styleInjected = true;
	var s = document.createElement('style');
	s.textContent = '@keyframes voiceToastIn{from{opacity:0;transform:translateX(40px) scale(0.9)}to{opacity:1;transform:translateX(0) scale(1)}}@keyframes voiceWave{0%,100%{opacity:1}50%{opacity:0.4}}';
	document.head.appendChild(s);
}
injectStyles();

var SpeechManager = {
	speak: function(text, callback){
		if(!enabled || !window.speechSynthesis) {
			if(callback) callback();
			return;
		}
		window.speechSynthesis.cancel();
		var utterance = new SpeechSynthesisUtterance(text);
		utterance.lang = 'zh-CN';
		utterance.rate = rate;
		utterance.pitch = pitch;
		utterance.volume = volume;
		currentUtterance = utterance;
		utterance.onend = function(){
			currentUtterance = null;
			if(callback) callback();
		};
		utterance.onerror = function(){
			currentUtterance = null;
			if(callback) callback();
		};
		showToast(text);
		window.speechSynthesis.speak(utterance);
	},

	stop: function(){
		if(window.speechSynthesis){
			window.speechSynthesis.cancel();
		}
		currentUtterance = null;
	},

	speakAndToast: function(text, duration){
		this.speak(text);
		showToast(text, duration || 5000);
	},

	setEnabled: function(val){
		enabled = val;
		localStorage.setItem('voice_broadcast_enabled', val);
		if(!val) this.stop();
	},

	isEnabled: function(){ return enabled; },

	setVolume: function(val){
		volume = Math.max(0, Math.min(1, val));
		localStorage.setItem('voice_broadcast_volume', volume);
	},

	getVolume: function(){ return volume; },

	setRate: function(val){
		rate = Math.max(0.1, Math.min(2.0, val));
		localStorage.setItem('voice_broadcast_rate', rate);
	},

	getRate: function(){ return rate; },

	setPitch: function(val){
		pitch = Math.max(0.1, Math.min(2.0, val));
		localStorage.setItem('voice_broadcast_pitch', pitch);
	},

	getPitch: function(){ return pitch; },

	getVoices: function(){
		return window.speechSynthesis ? window.speechSynthesis.getVoices() : [];
	}
};

window.SpeechManager = SpeechManager;

})();
