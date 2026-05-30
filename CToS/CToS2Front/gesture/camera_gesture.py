#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
CToS Gesture Engine
MediaPipe Tasks API (v0.10+) + OpenCV real-time camera gesture recognition
Pushes gesture events to frontend via WebSocket

v3.0 - Built-in GestureRecognizer (no manual finger counting!)
  Recognizes via MediaPipe trained classifier:
    ClosedFist -> quick_menu
    PointingUp -> prev_menu
    Victory    -> summary
    ThumbDown  -> next_menu
    OpenPalm   -> voice_toggle
"""

import sys, os, json, time, argparse, threading, asyncio, logging

logging.basicConfig(level=logging.INFO, format="[Gesture] %(levelname)s %(message)s")
log = logging.getLogger(__name__)

# Suppress MediaPipe internal non-critical warnings
os.environ["GLOG_minloglevel"] = "2"  # 0=INFO, 1=WARNING, 2=ERROR, 3=FATAL
logging.getLogger("mediapipe").setLevel(logging.ERROR)

# Model file paths
MODELS_DIR = os.path.join(os.path.dirname(__file__), "models")
HAND_MODEL_PATH = os.path.join(MODELS_DIR, "hand_landmarker.task")
GESTURE_MODEL_PATH = os.path.join(MODELS_DIR, "gesture_recognizer.task")

# ---- Dependency imports ----
try:
    import cv2
    import numpy as np
except ImportError:
    log.error("opencv-python required: pip install opencv-python")
    sys.exit(1)

try:
    from mediapipe.tasks.python.vision import (
        GestureRecognizer as MpGestureRecognizer,
        GestureRecognizerOptions,
        GestureRecognizerResult,
        RunningMode,
        drawing_utils,
        drawing_styles,
    )
    from mediapipe.tasks.python.core.base_options import BaseOptions
    from mediapipe.tasks.python.vision import HandLandmarksConnections
    import mediapipe as mp
except ImportError:
    log.error("mediapipe required: pip install mediapipe")
    sys.exit(1)

try:
    import websockets
except ImportError:
    log.error("websockets required: pip install websockets")
    sys.exit(1)


class GestureEngine:
    """
    MediaPipe Tasks API GestureRecognizer (built-in classifier)
    Maps MediaPipe's 7 trained gestures to CToS functions:

       ClosedFist -> quick_menu
       PointingUp -> prev_menu
       Victory    -> summary
       ThumbDown  -> next_menu
       OpenPalm   -> voice_toggle
       (ThumbUp / Love / None ignored or mapped as needed)
    """

    # Gesture type enums (name/value/function matched 1:1)
    GESTURE_NONE = "none"
    GESTURE_PREV_MENU = "prev_menu"       # PointingUp -> prev menu
    GESTURE_NEXT_MENU = "next_menu"       # ThumbDown -> next menu
    GESTURE_VOICE_TOGGLE = "voice_toggle" # OpenPalm -> voice toggle
    GESTURE_SUMMARY = "summary"           # Victory -> summary
    GESTURE_QUICK_MENU = "quick_menu"     # ClosedFist -> quick menu

    # Mapping from MediaPipe gesture names to CToS gestures
    # MediaPipe GestureRecognizer v0.10+ uses underscore-separated names
    MP_GESTURE_MAP = {
        "Closed_Fist": GESTURE_QUICK_MENU,
        "Pointing_Up": GESTURE_PREV_MENU,
        "Victory":     GESTURE_SUMMARY,
        "Thumb_Down":  GESTURE_NEXT_MENU,
        "Open_Palm":   GESTURE_VOICE_TOGGLE,
    }
    # Gestures that we intentionally ignore
    IGNORED_MP_GESTURES = {"Thumb_Up", "Love", "None"}

    def __init__(self, camera_id=0, ws_port=8765, debug_camera=False):
        self.camera_id = camera_id
        self.ws_port = ws_port
        self.running = False
        self.cap = None
        self.recognizer = None
        self.debug_camera = debug_camera

        self._init_recognizer()

        # Cooldown logic
        self._cooldown = 3.0       # gesture trigger cooldown (seconds) - same gesture blocked for 3s
        self._last_gesture_time = 0

        # Stable frame counter: require N consecutive same gesture
        self._stable_frames_required = 2
        self._stable_counter = 0
        self._stable_gesture = self.GESTURE_NONE
        self._last_stable_gesture = self.GESTURE_NONE

        # Last detected MP gesture name (for debug display)
        self._last_mp_gesture = ""

        # Event callback
        self.on_gesture = None

        # WebSocket clients
        self.ws_clients = set()

        log.info(f"Gesture engine v3.0 initialized (camera#{camera_id}, WS port:{ws_port})")

    def _init_recognizer(self):
        """Initialize MediaPipe GestureRecognizer (built-in classifier)"""
        if not os.path.isfile(GESTURE_MODEL_PATH):
            print(f"[Gesture] !! Model file not found: {GESTURE_MODEL_PATH}")
            print(f"[Gesture] !! Please run: python download_models.py")
            sys.exit(1)

        try:
            options = GestureRecognizerOptions(
                base_options=BaseOptions(model_asset_path=GESTURE_MODEL_PATH),
                running_mode=RunningMode.IMAGE,
                num_hands=1,
                min_hand_detection_confidence=0.7,
                min_hand_presence_confidence=0.7,
                min_tracking_confidence=0.6,
            )
            self.recognizer = MpGestureRecognizer.create_from_options(options)
            self._frame_width = 640
            self._frame_height = 480
            log.info("GestureRecognizer initialized (Tasks API - built-in classifier)")
        except Exception as e:
            log.error(f"GestureRecognizer init failed: {e}")
            sys.exit(1)

    def _map_gesture(self, mp_gesture_name):
        """
        Map MediaPipe gesture name to CToS gesture.
        Returns (gesture_name, confidence) or (GESTURE_NONE, 0.0)
        """
        if mp_gesture_name in self.IGNORED_MP_GESTURES:
            return self.GESTURE_NONE, 0.0

        ctos_gesture = self.MP_GESTURE_MAP.get(mp_gesture_name)
        if ctos_gesture:
            return ctos_gesture, 0.9  # built-in classifier confidence is already high
        return self.GESTURE_NONE, 0.0

    async def _ws_handler(self, websocket):
        """WebSocket client connection handler"""
        self.ws_clients.add(websocket)
        log.info(f"Client connected ({len(self.ws_clients)} total)")
        try:
            async for _ in websocket:
                pass
        except:
            pass
        finally:
            self.ws_clients.discard(websocket)
            log.info(f"Client disconnected ({len(self.ws_clients)} remaining)")

    async def _broadcast_gesture(self, gesture, confidence):
        """Broadcast gesture event to all connected clients"""
        if not self.ws_clients:
            return
        event = json.dumps({
            "type": "gesture",
            "gesture": gesture,
            "confidence": round(confidence, 3),
            "timestamp": time.time(),
        })
        dead = set()
        for ws in self.ws_clients:
            try:
                await ws.send(event)
            except:
                dead.add(ws)
        self.ws_clients -= dead

    def _process_frame(self, frame):
        """
        Process a single frame with MediaPipe GestureRecognizer
        
        Strategy:
          1. Run built-in GestureRecognizer (trained classifier)
          2. Map recognized gesture to CToS function
          3. Require N consecutive same gesture (jitter elimination)
          4. Apply cooldown before triggering
        
        Returns: (processed_frame, gesture, confidence)
        """
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)

        gesture = self.GESTURE_NONE
        confidence = 0.0
        hand_detected = False
        mp_gesture_name = ""

        try:
            result: GestureRecognizerResult = self.recognizer.recognize(mp_image)
        except Exception as e:
            log.error(f"GestureRecognizer.recognize failed: {e}")
            return frame, self.GESTURE_NONE, 0.0

        if result.hand_landmarks:
            for i, hand_landmarks in enumerate(result.hand_landmarks):
                hand_detected = True

                # Draw hand skeleton (same as before)
                try:
                    drawing_utils.draw_landmarks(
                        frame,
                        hand_landmarks,
                        HandLandmarksConnections.HAND_CONNECTIONS,
                        drawing_styles.get_default_hand_landmarks_style(),
                        drawing_styles.get_default_hand_connections_style(),
                    )
                except Exception as e:
                    log.warning(f"Draw landmarks failed: {e}")

                # Get recognized gesture from built-in classifier
                if (result.gestures and len(result.gestures) > i
                        and result.gestures[i] and len(result.gestures[i]) > 0):
                    top_gesture = result.gestures[i][0]
                    mp_gesture_name = top_gesture.category_name
                    gesture, confidence = self._map_gesture(mp_gesture_name)

        # Stable frame counter + cooldown
        # v3.2: 移除多帧稳定计数器,使用"同手势3秒冷却"作为唯一防抖
        #       PointingUp/ThumbDown 等在帧间经常抖动到 None，
        #       多帧要求会使它们永远无法触发。
        #       后端 3s cooldown 已经足够防止误触发。
        current_time = time.time()
        if hand_detected and gesture != self.GESTURE_NONE and confidence > 0.4:
            # 同手势冷却检查
            if gesture != self._last_stable_gesture or \
                    current_time - self._last_gesture_time >= self._cooldown:
                self._last_gesture_time = current_time
                self._last_stable_gesture = gesture
                log.info(f"Gesture: {gesture} (MP: {mp_gesture_name}, conf: {confidence:.2f})")
                # gesture 保持有效，广播出去
            else:
                gesture = self.GESTURE_NONE
                confidence = 0.0
        else:
            gesture = self.GESTURE_NONE
            confidence = 0.0

        # Debug overlay: show MP detected gesture
        if hand_detected and mp_gesture_name:
            cv2.putText(frame, f"MP: {mp_gesture_name}",
                        (10, 110), cv2.FONT_HERSHEY_SIMPLEX, 0.5,
                        (0, 255, 255), 1)

        return frame, gesture, confidence

    async def run(self):
        """Main loop: camera capture + WebSocket server"""
        self.cap = cv2.VideoCapture(self.camera_id)
        if not self.cap.isOpened():
            log.error(f"Cannot open camera #{self.camera_id}")
            return

        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.cap.set(cv2.CAP_PROP_FPS, 30)

        self.running = True
        log.info(f"Camera started (640x480 @ 30fps)")

        # Start WebSocket server
        ws_server = await websockets.serve(
            self._ws_handler, "127.0.0.1", self.ws_port,
            ping_interval=30, ping_timeout=10,
        )
        log.info(f"WebSocket started: ws://127.0.0.1:{self.ws_port}")

        # Pre-create windows (ensures they appear even if first frame is slow)
        cv2.namedWindow("CToS Gesture Control", cv2.WINDOW_NORMAL)
        cv2.resizeWindow("CToS Gesture Control", 640, 480)
        # Process a few initial events to make window appear
        cv2.waitKey(1)

        fps_counter = 0
        fps_timer = time.time()

        if self.debug_camera:
            cv2.namedWindow("Camera Debug", cv2.WINDOW_NORMAL)
            cv2.resizeWindow("Camera Debug", 640, 480)
            cv2.waitKey(1)
            log.info("Debug camera window opened (Camera Debug)")

        try:
            while self.running:
                ret, frame = self.cap.read()
                if not ret:
                    log.warning("Camera read failed, retrying...")
                    await asyncio.sleep(0.1)
                    continue

                frame = cv2.flip(frame, 1)

                gesture = self.GESTURE_NONE
                confidence = 0.0

                if self.debug_camera:
                    debug_frame = frame.copy()

                fps_counter += 1
                processed, gesture, confidence = self._process_frame(frame)
                if gesture != self.GESTURE_NONE:
                    await self._broadcast_gesture(gesture, confidence)

                # FPS counter
                if time.time() - fps_timer >= 1.0:
                    log.debug(f"Gesture FPS: {fps_counter}")
                    if self.debug_camera:
                        cv2.putText(debug_frame, f"FPS: {fps_counter}",
                                    (10, 55), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    fps_counter = 0
                    fps_timer = time.time()

                # Show CToS gesture label
                if gesture != self.GESTURE_NONE:
                    label = {
                        self.GESTURE_PREV_MENU: "^ 1",
                        self.GESTURE_NEXT_MENU: "< 3",
                        self.GESTURE_VOICE_TOGGLE: "= 4",
                        self.GESTURE_SUMMARY: "v 2",
                        self.GESTURE_QUICK_MENU: "* 0",
                    }.get(gesture, gesture)
                    cv2.putText(processed, f"{label} ({confidence:.2f})",
                                (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                                (0, 255, 0), 2)


                cv2.imshow("CToS Gesture Control", processed)

                if self.debug_camera:
                    cv2.imshow("Camera Debug", debug_frame)
                    cv2.setWindowProperty("Camera Debug", cv2.WND_PROP_TOPMOST, 1)

                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    self.running = False
                    break

                await asyncio.sleep(0.01)

        except KeyboardInterrupt:
            pass
        finally:
            self.cleanup()
            ws_server.close()
            await ws_server.wait_closed()
            log.info("Gesture service stopped")

    def cleanup(self):
        self.running = False
        if self.recognizer:
            self.recognizer.close()
        if self.cap:
            self.cap.release()
        cv2.destroyAllWindows()

    def start(self):
        """Start gesture recognition (sync entry, runs asyncio event loop)"""
        try:
            asyncio.run(self.run())
        except KeyboardInterrupt:
            pass


def main():
    parser = argparse.ArgumentParser(description="CToS Gesture Recognition v3.0")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket port (default 8765)")
    parser.add_argument("--camera", type=int, default=0, help="Camera ID (default 0)")
    parser.add_argument("--debug", action="store_true", help="Debug mode (logging)")
    parser.add_argument("--debug-camera", action="store_true", help="Show raw camera debug window")
    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    if not os.path.isfile(GESTURE_MODEL_PATH):
        print(f"\n  !! Model file not found: {GESTURE_MODEL_PATH}")
        print(f"  Please run: python download_models.py\n")
        sys.exit(1)

    engine = GestureEngine(camera_id=args.camera, ws_port=args.ws_port, debug_camera=args.debug_camera)
    SP = "=" * 48
    print(f"\n  {SP}")
    print(f"   CToS Gesture Recognition v3.0")
    print(f"  {SP}")
    print(f"   [CAM] Camera: #{args.camera}")
    print(f"   [WS]  WebSocket: ws://127.0.0.1:{args.ws_port}")
    print(f"   [AI]  MediaPipe: GestureRecognizer (built-in classifier)")
    print(f"   [DBG] Debug cam: {'ON' if args.debug_camera else 'OFF (use --debug-camera)'}")
    print(f"   [KEY] Press q to quit")
    print(f"  {SP}")
    print(f"   Gesture mappings (MediaPipe → CToS):")
    print(f"     [* 0] ClosedFist -> quick menu")
    print(f"     [^ 1] PointingUp -> prev menu")
    print(f"     [v 2] Victory    -> summary")
    print(f"     [< 3] ThumbDown  -> next menu")
    print(f"     [= 4] OpenPalm   -> voice toggle")
    print(f"   (ThumbUp / Love / None are ignored)")
    print(f"  {SP}\n")

    engine.start()


if __name__ == "__main__":
    main()