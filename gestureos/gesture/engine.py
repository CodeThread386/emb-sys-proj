"""Gesture Engine — MediaPipe hand landmark detection + gesture classification."""

import os
import threading
import time
import urllib.request
from typing import Optional, List, Tuple

import cv2
import numpy as np

from gestureos import config

try:
    import mediapipe as mp
    from mediapipe.tasks.python import BaseOptions
    from mediapipe.tasks.python.vision import (
        HandLandmarker, HandLandmarkerOptions, RunningMode,
    )
    _HAS_MP = True
except ImportError:
    _HAS_MP = False


_MODEL_URL = "https://storage.googleapis.com/mediapipe-models/hand_landmarker/hand_landmarker/float16/1/hand_landmarker.task"
_MODEL_PATH = os.path.join(os.path.dirname(__file__), "hand_landmarker.task")

# Hand landmark indices
WRIST = 0
THUMB_CMC = 1; THUMB_MCP = 2; THUMB_IP = 3; THUMB_TIP = 4
INDEX_MCP = 5; INDEX_PIP = 6; INDEX_TIP = 8
MIDDLE_MCP = 9; MIDDLE_PIP = 10; MIDDLE_TIP = 12
RING_MCP = 13; RING_PIP = 14; RING_TIP = 16
PINKY_MCP = 17; PINKY_PIP = 18; PINKY_TIP = 20

# Connections for drawing
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),(0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),(9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),(0,17),
]


class HandData:
    """Processed hand landmark data for one frame."""
    __slots__ = (
        "landmarks", "finger_states", "gesture", "index_tip",
        "thumb_tip", "middle_tip", "wrist", "frame_brightness",
    )

    def __init__(self):
        self.landmarks: Optional[list] = None
        self.finger_states: List[bool] = [False] * 5
        self.gesture: str = "NONE"
        self.index_tip: Optional[Tuple[float, float]] = None
        self.thumb_tip: Optional[Tuple[float, float]] = None
        self.middle_tip: Optional[Tuple[float, float]] = None
        self.wrist: Optional[Tuple[float, float]] = None
        self.frame_brightness: float = 0.0


class GestureEngine:
    def __init__(self):
        self._running = False
        self._thread: Optional[threading.Thread] = None
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()

        self._latest_frame: Optional[np.ndarray] = None
        self._latest_hand: HandData = HandData()
        self._frame_count = 0
        self._mp_timestamp = 0

        self._landmarker = None
        self._latest_result = None

        if _HAS_MP:
            self._init_mediapipe()

    def _init_mediapipe(self):
        try:
            if not os.path.exists(_MODEL_PATH):
                print("[GestureEngine] Downloading hand landmarker model...")
                urllib.request.urlretrieve(_MODEL_URL, _MODEL_PATH)
                print("[GestureEngine] Model downloaded.")

            options = HandLandmarkerOptions(
                base_options=BaseOptions(model_asset_path=_MODEL_PATH),
                running_mode=RunningMode.LIVE_STREAM,
                num_hands=1,
                min_hand_detection_confidence=0.6,
                min_tracking_confidence=0.5,
                result_callback=self._on_result,
            )
            self._landmarker = HandLandmarker.create_from_options(options)
        except Exception as e:
            print(f"[GestureEngine] MediaPipe init failed: {e}")
            self._landmarker = None

    def _on_result(self, result, output_image, timestamp_ms):
        self._latest_result = result

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._frame_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=3.0)
        if self._cap and self._cap.isOpened():
            self._cap.release()

    def _frame_loop(self):
        self._cap = cv2.VideoCapture(0)
        if not self._cap.isOpened():
            print("[GestureEngine] No webcam found. Running headless.")
            self._run_headless()
            return

        self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)

        while self._running:
            ret, frame = self._cap.read()
            if not ret:
                time.sleep(0.01)
                continue
            self._process_frame(frame)
            time.sleep(0.001)

        self._cap.release()

    def _run_headless(self):
        while self._running:
            dummy = np.zeros((480, 640, 3), dtype=np.uint8)
            cv2.putText(dummy, "No Webcam - Headless Mode", (80, 240),
                        cv2.FONT_HERSHEY_SIMPLEX, 1.0, (0, 200, 200), 2)
            with self._lock:
                self._latest_frame = dummy
                self._latest_hand = HandData()
                self._latest_hand.frame_brightness = 30.0
            time.sleep(0.033)

    def _process_frame(self, frame: np.ndarray):
        frame = cv2.flip(frame, 1)
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        self._frame_count += 1

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        brightness = float(np.mean(gray))

        hand = HandData()
        hand.frame_brightness = brightness

        if self._landmarker is not None:
            try:
                self._mp_timestamp += 33
                mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
                self._landmarker.detect_async(mp_image, self._mp_timestamp)

                result = self._latest_result
                if result and result.hand_landmarks and len(result.hand_landmarks) > 0:
                    lms = result.hand_landmarks[0]
                    hand.landmarks = lms

                    hand.finger_states = self._get_finger_states(lms)
                    hand.gesture = self._classify_gesture(lms, hand.finger_states)

                    hand.index_tip = (lms[INDEX_TIP].x, lms[INDEX_TIP].y)
                    hand.thumb_tip = (lms[THUMB_TIP].x, lms[THUMB_TIP].y)
                    hand.middle_tip = (lms[MIDDLE_TIP].x, lms[MIDDLE_TIP].y)
                    hand.wrist = (lms[WRIST].x, lms[WRIST].y)

                    self._draw_hand(frame, lms)
            except Exception:
                pass

        color = (0, 255, 0) if hand.gesture != "NONE" else (100, 100, 100)
        cv2.putText(frame, f"Gesture: {hand.gesture}", (10, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        fingers_str = "".join("1" if f else "0" for f in hand.finger_states)
        cv2.putText(frame, f"Fingers: [{fingers_str}]", (10, 60),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (200, 200, 200), 1)

        with self._lock:
            self._latest_frame = frame
            self._latest_hand = hand

    def _draw_hand(self, frame: np.ndarray, lms):
        h, w = frame.shape[:2]
        for lm in lms:
            cx, cy = int(lm.x * w), int(lm.y * h)
            cv2.circle(frame, (cx, cy), 3, (0, 255, 0), -1)
        for s, e in HAND_CONNECTIONS:
            x1, y1 = int(lms[s].x * w), int(lms[s].y * h)
            x2, y2 = int(lms[e].x * w), int(lms[e].y * h)
            cv2.line(frame, (x1, y1), (x2, y2), (0, 200, 0), 1)

    def _get_finger_states(self, lms) -> List[bool]:
        def _dist(a, b):
            return ((lms[a].x - lms[b].x)**2 + (lms[a].y - lms[b].y)**2) ** 0.5

        thumb = _dist(THUMB_TIP, INDEX_MCP) > _dist(THUMB_IP, INDEX_MCP)
        index = lms[INDEX_TIP].y < lms[INDEX_PIP].y
        middle = lms[MIDDLE_TIP].y < lms[MIDDLE_PIP].y
        ring = lms[RING_TIP].y < lms[RING_PIP].y
        pinky = lms[PINKY_TIP].y < lms[PINKY_PIP].y
        return [thumb, index, middle, ring, pinky]

    def _classify_gesture(self, lms, fingers: List[bool]) -> str:
        thumb, index, middle, ring, pinky = fingers

        pinch_idx = ((lms[THUMB_TIP].x - lms[INDEX_TIP].x)**2 +
                     (lms[THUMB_TIP].y - lms[INDEX_TIP].y)**2) ** 0.5
        pinch_mid = ((lms[THUMB_TIP].x - lms[MIDDLE_TIP].x)**2 +
                     (lms[THUMB_TIP].y - lms[MIDDLE_TIP].y)**2) ** 0.5

        if pinch_idx < config.CLICK_PINCH_THRESHOLD:
            return "PINCH_INDEX"
        if pinch_mid < config.CLICK_PINCH_THRESHOLD:
            return "PINCH_MIDDLE"

        if not any(fingers):
            return "FIST"
        if all(fingers):
            return "OPEN_PALM"
        if index and not middle and not ring and not pinky and not thumb:
            return "INDEX_FINGER"
        if index and middle and not ring and not pinky:
            return "PEACE"
        if thumb and index and not middle and not ring and pinky:
            return "SPIDERMAN"
        if index and middle and ring and not pinky:
            return "THREE_FINGERS"
        if not thumb and index and middle and ring and pinky:
            return "FOUR_FINGERS"
        if thumb and not index and not middle and not ring and not pinky:
            if lms[THUMB_TIP].y < lms[WRIST].y:
                return "THUMBS_UP"
            else:
                return "THUMBS_DOWN"

        return "NONE"

    def get_frame(self) -> Optional[np.ndarray]:
        with self._lock:
            return self._latest_frame.copy() if self._latest_frame is not None else None

    def get_hand_data(self) -> HandData:
        with self._lock:
            return self._latest_hand
