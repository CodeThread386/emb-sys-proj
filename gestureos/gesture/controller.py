"""Desktop Controller — maps gestures to system commands."""

import subprocess
import time
import threading
from typing import Optional, Callable

from gestureos.gesture.engine import GestureEngine, HandData
from gestureos import config

try:
    from pynput.keyboard import Key, Controller as KBController
    _kb = KBController()
    _HAS_PYNPUT = True
except Exception:
    _kb = None
    _HAS_PYNPUT = False

try:
    import pyautogui
    pyautogui.FAILSAFE = True
    pyautogui.PAUSE = 0.0
    _HAS_PYAUTOGUI = True
except ImportError:
    _HAS_PYAUTOGUI = False


def _run_cmd(args: list):
    """Run a system command, wait for completion."""
    try:
        subprocess.run(args, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                       timeout=2)
    except Exception:
        pass


def _kde_shortcut(component: str, shortcut: str):
    """Invoke a KDE global shortcut via D-Bus."""
    _run_cmd([
        "dbus-send", "--dest=org.kde.kglobalaccel",
        f"/component/{component}",
        "org.kde.kglobalaccel.Component.invokeShortcut",
        f"string:{shortcut}",
    ])


def _press_key(key):
    """Press and release a key via pynput."""
    if _kb:
        _kb.press(key)
        _kb.release(key)


class DesktopController:
    def __init__(self, engine: GestureEngine):
        self._engine = engine
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._current_gesture: str = "NONE"
        self._gesture_hold: int = 0
        self._action_fired: bool = False

        self._mouse_active = False
        self._prev_x: Optional[float] = None
        self._prev_y: Optional[float] = None
        self._smooth_dx: float = 0.0
        self._smooth_dy: float = 0.0

        self._on_gesture_callback: Optional[Callable] = None
        self._on_action_callback: Optional[Callable] = None

        self._desktop_control_enabled = True
        self._latest_gesture = "NONE"
        self._latest_action = ""
        self._last_cycle_time: float = 0.0
        self._alt_held: bool = False


        if _HAS_PYAUTOGUI:
            self._screen_w, self._screen_h = pyautogui.size()
        else:
            self._screen_w, self._screen_h = 1920, 1080

    def set_desktop_control(self, enabled: bool):
        self._desktop_control_enabled = enabled

    def on_gesture(self, callback: Callable):
        self._on_gesture_callback = callback

    def on_action(self, callback: Callable):
        self._on_action_callback = callback

    def start(self):
        self._running = True
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._running = False
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self):
        while self._running:
            hand = self._engine.get_hand_data()
            self._process(hand)
            time.sleep(0.02)

    def _process(self, hand: HandData):
        gesture = hand.gesture
        prev_gesture = self._current_gesture
        self._latest_gesture = gesture

        if self._on_gesture_callback:
            self._on_gesture_callback(gesture, hand)

        if gesture == self._current_gesture:
            self._gesture_hold += 1
        else:
            self._current_gesture = gesture
            self._gesture_hold = 0
            self._action_fired = False

        if gesture == "INDEX_FINGER" and hand.index_tip:
            self._handle_mouse_move(hand)
            return
        else:
            self._mouse_active = False
            self._prev_x = None
            self._prev_y = None
            self._smooth_dx = 0.0
            self._smooth_dy = 0.0

        if gesture == "THREE_FINGERS" and self._gesture_hold >= config.GESTURE_HOLD_FRAMES:
            now = time.time()
            if now - self._last_cycle_time >= 1.0:
                self._last_cycle_time = now
                self._handle_alt_tab_cycle()
            return

        if gesture != "THREE_FINGERS" and self._alt_held:
            self._handle_alt_tab_release()

        if (self._gesture_hold >= config.GESTURE_HOLD_FRAMES
                and gesture != "NONE" and not self._action_fired):
            self._action_fired = True
            self._execute_action(gesture, hand)

    def _handle_mouse_move(self, hand: HandData):
        if not _HAS_PYAUTOGUI or not self._desktop_control_enabled:
            return

        ix, iy = hand.index_tip

        if self._prev_x is None:
            self._prev_x = ix
            self._prev_y = iy
            return

        dx = ix - self._prev_x
        dy = iy - self._prev_y

        self._prev_x = ix
        self._prev_y = iy

        if abs(dx) < config.MOUSE_DEAD_ZONE and abs(dy) < config.MOUSE_DEAD_ZONE:
            return

        s = config.SMOOTHING_FACTOR
        self._smooth_dx = self._smooth_dx * (1 - s) + dx * s
        self._smooth_dy = self._smooth_dy * (1 - s) + dy * s

        move_x = int(self._smooth_dx * config.MOUSE_SENSITIVITY)
        move_y = int(self._smooth_dy * config.MOUSE_SENSITIVITY)

        if move_x == 0 and move_y == 0:
            return

        try:
            pyautogui.moveRel(move_x, move_y, _pause=False)
        except Exception:
            pass

        self._latest_action = "mouse_move"

    def _handle_alt_tab_cycle(self):
        """Hold Alt and press Tab to cycle to next window."""
        if not _HAS_PYNPUT or not self._desktop_control_enabled:
            return
        if not self._alt_held:
            _kb.press(Key.alt_l)
            self._alt_held = True
            print("[ACTION] Alt+Tab STARTED — cycling windows")
        _kb.press(Key.tab)
        _kb.release(Key.tab)
        print("[ACTION] Tab → next window")
        self._latest_action = "alt_tab"
        if self._on_action_callback:
            self._on_action_callback("alt_tab", "THREE_FINGERS")

    def _handle_alt_tab_release(self):
        """Release Alt to confirm the selected window."""
        if not _HAS_PYNPUT or not self._alt_held:
            return
        _kb.release(Key.alt_l)
        self._alt_held = False
        print("[ACTION] Alt RELEASED — window selected")

    def _execute_action(self, gesture: str, hand: HandData):
        cmd_info = config.GESTURE_COMMANDS.get(gesture)
        if not cmd_info:
            return

        action = cmd_info["action"]
        self._latest_action = action

        if self._on_action_callback:
            self._on_action_callback(action, gesture)

        if not self._desktop_control_enabled:
            return

        print(f"[ACTION] gesture={gesture} action={action}")

        try:
            if action == "meta_d":
                _kde_shortcut("kwin", "Show Desktop")
            elif action == "space":
                if _HAS_PYNPUT:
                    _press_key(Key.space)
                elif _HAS_PYAUTOGUI:
                    pyautogui.press("space")
            elif action == "toggle_mute":
                _run_cmd(["wpctl", "set-mute", "@DEFAULT_AUDIO_SINK@", "toggle"])
            elif action == "volume_up":
                _run_cmd(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@",
                          f"{config.VOLUME_STEP}%+"])
            elif action == "volume_down":
                _run_cmd(["wpctl", "set-volume", "@DEFAULT_AUDIO_SINK@",
                          f"{config.VOLUME_STEP}%-"])
            elif action == "right_click" and _HAS_PYAUTOGUI:
                pyautogui.rightClick()
            elif action == "left_click" and _HAS_PYAUTOGUI:
                pyautogui.click()
            print(f"[ACTION] OK: {action}")
        except Exception as e:
            print(f"[ACTION] FAILED: {action} -> {e}")

    @property
    def latest_gesture(self) -> str:
        return self._latest_gesture

    @property
    def latest_action(self) -> str:
        return self._latest_action
