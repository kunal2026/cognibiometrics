import time
import threading
import math
import os
from collections import deque
from dataclasses import dataclass, field
from typing import Deque, Dict, Any

from pynput import keyboard
import psutil

import config


def get_active_app_name() -> str:
    """Get active app name (Windows-focused)."""
    if os.name != "nt":
        return "unknown"
    try:
        import ctypes
        user32 = ctypes.windll.user32
        hwnd = user32.GetForegroundWindow()
        if not hwnd:
            return "unknown"
        pid = ctypes.c_ulong()
        user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
        process_id = pid.value
        return psutil.Process(process_id).name()
    except Exception:
        return "unknown"


@dataclass
class FeatureSnapshot:
    timestamp: float
    keys_per_min: float
    backspace_ratio: float
    app_switches_per_min: float
    trust_score: float
    state: str
    burnout_risk: float = 0.0


@dataclass
class SharedState:
    lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    current_state: str = "initializing"
    trust_score: float = 50.0
    burnout_risk: float = 0.0
    last_features: Dict[str, float] = field(default_factory=dict)
    baseline: Dict[str, float] = field(default_factory=dict)
    history: Deque[FeatureSnapshot] = field(default_factory=lambda: deque(maxlen=config.BURNOUT_HISTORY_POINTS))

    def update(self, **kwargs: Any) -> None:
        with self.lock:
            for k, v in kwargs.items():
                setattr(self, k, v)

    def add_history(self, snapshot: FeatureSnapshot) -> None:
        with self.lock:
            self.history.append(snapshot)

    def get_snapshot(self) -> Dict[str, Any]:
        with self.lock:
            return {
                "current_state": self.current_state,
                "trust_score": self.trust_score,
                "burnout_risk": self.burnout_risk,
                "last_features": dict(self.last_features),
                "baseline": dict(self.baseline),
                "history": [
                    {
                        "timestamp": s.timestamp,
                        "keys_per_min": s.keys_per_min,
                        "backspace_ratio": s.backspace_ratio,
                        "app_switches_per_min": s.app_switches_per_min,
                        "trust_score": s.trust_score,
                        "state": s.state,
                        "burnout_risk": s.burnout_risk,
                    }
                    for s in self.history
                ],
            }


global_state = SharedState()


class DataBuffer:
    def __init__(self, window_seconds: int):
        self.window_seconds = window_seconds
        self.keystroke_times: Deque[float] = deque()
        self.backspace_times: Deque[float] = deque()
        self.app_switch_times: Deque[float] = deque()

    def _prune(self, dq: Deque[float]) -> None:
        cutoff = time.time() - self.window_seconds
        while dq and dq[0] < cutoff:
            dq.popleft()

    def add_keypress(self, timestamp: float, is_backspace: bool = False) -> None:
        self.keystroke_times.append(timestamp)
        if is_backspace:
            self.backspace_times.append(timestamp)
        self._prune(self.keystroke_times)
        self._prune(self.backspace_times)

    def add_app_switch(self, timestamp: float) -> None:
        self.app_switch_times.append(timestamp)
        self._prune(self.app_switch_times)

    def get_features(self) -> Dict[str, float]:
        now = time.time()
        self._prune(self.keystroke_times)
        self._prune(self.backspace_times)
        self._prune(self.app_switch_times)

        if self.keystroke_times:
            span = max(1e-3, now - self.keystroke_times[0])
            keys_per_min = len(self.keystroke_times) / span * 60.0
        else:
            keys_per_min = 0.0

        total_keys = len(self.keystroke_times)
        backspaces = len(self.backspace_times)
        backspace_ratio = backspaces / total_keys if total_keys > 0 else 0.0

        if self.app_switch_times:
            span_sw = max(1e-3, now - self.app_switch_times[0])
            app_switches_per_min = len(self.app_switch_times) / span_sw * 60.0
        else:
            app_switches_per_min = 0.0

        return {
            "keys_per_min": keys_per_min,
            "backspace_ratio": backspace_ratio,
            "app_switches_per_min": app_switches_per_min,
        }


class CognitiveAgent:
    def __init__(self, shared_state: SharedState):
        self.state = shared_state
        self.buffer = DataBuffer(config.WINDOW_SECONDS)
        self.stop_event = threading.Event()
        self.listener = None

        self.baseline_start_time = time.time()
        self.baseline_ready = False
        self.baseline_values: Dict[str, float] = {}

        self.last_state = "initializing"

    def _on_press(self, key):
        # we use release timing only
        pass

    def _on_release(self, key):
        t = time.time()
        is_backspace = False
        try:
            if key == keyboard.Key.backspace:
                is_backspace = True
        except Exception:
            pass
        self.buffer.add_keypress(t, is_backspace=is_backspace)
        if self.stop_event.is_set():
            return False

    def start_keyboard_listener(self) -> None:
        self.listener = keyboard.Listener(on_press=self._on_press, on_release=self._on_release)
        self.listener.start()

    def monitor_active_app(self) -> None:
        last_app = None
        while not self.stop_event.is_set():
            current_app = get_active_app_name()
            if current_app != last_app:
                self.buffer.add_app_switch(time.time())
                last_app = current_app
            time.sleep(1.0)

    def _update_baseline(self, features: Dict[str, float]) -> None:
        elapsed = time.time() - self.baseline_start_time
        if elapsed < config.BASELINE_SECONDS:
            if not self.baseline_values:
                self.baseline_values = dict(features)
            else:
                alpha = 0.1
                for k, v in features.items():
                    old = self.baseline_values.get(k, v)
                    self.baseline_values[k] = (1 - alpha) * old + alpha * v
        else:
            self.baseline_ready = True
        self.state.update(baseline=self.baseline_values)

    def _compute_trust_score(self, features: Dict[str, float]) -> float:
        if not self.baseline_ready or not self.baseline_values:
            return 50.0
        dist_sq = 0.0
        for k, v in features.items():
            base = self.baseline_values.get(k, v)
            dist_sq += (v - base) ** 2
        dist = math.sqrt(dist_sq)
        trust = max(0.0, 100.0 * (1.0 - dist / config.TRUST_MAX_DISTANCE))
        return trust

    def _classify_state(self, features: Dict[str, float], trust_score: float) -> str:
        kpm = features["keys_per_min"]
        br = features["backspace_ratio"]
        asm = features["app_switches_per_min"]

        if kpm > 200 and br > 0.15 and asm > 10:
            state = "anxious_scatter"
        elif kpm > 150 and br < 0.05 and asm < 5:
            state = "deep_focus"
        elif kpm < 50 and asm < 3:
            state = "fatigued"
        else:
            state = "normal"
        return state

    def _update_burnout_risk(self, snapshot: FeatureSnapshot) -> float:
        hist = self.state.history
        self.state.add_history(snapshot)
        if not hist:
            snapshot.burnout_risk = 0.0
            return 0.0

        avg_backspace = sum(s.backspace_ratio for s in hist) / len(hist)
        avg_switches = sum(s.app_switches_per_min for s in hist) / len(hist)
        fatigue_like = sum(1 for s in hist if s.state in ("fatigued", "anxious_scatter")) / len(hist)

        c1 = min(1.0, avg_backspace * 5.0)
        c2 = min(1.0, avg_switches / 20.0)
        c3 = fatigue_like

        raw_risk = (c1 + c2 + c3) / 3.0
        burnout_risk = raw_risk * 100.0
        snapshot.burnout_risk = burnout_risk
        return burnout_risk

    def analysis_loop(self) -> None:
        while not self.stop_event.is_set():
            features = self.buffer.get_features()
            self._update_baseline(features)
            trust = self._compute_trust_score(features)
            state = self._classify_state(features, trust)

            snapshot = FeatureSnapshot(
                timestamp=time.time(),
                keys_per_min=features["keys_per_min"],
                backspace_ratio=features["backspace_ratio"],
                app_switches_per_min=features["app_switches_per_min"],
                trust_score=trust,
                state=state,
            )

            burnout_risk = self._update_burnout_risk(snapshot)

            self.state.update(
                current_state=state,
                trust_score=trust,
                burnout_risk=burnout_risk,
                last_features=features,
            )

            if config.DEBUG_LOG:
                print(
                    f"[STATE] {state} | trust={trust:.1f} | burnout={burnout_risk:.1f} | "
                    f"features={features}"
                )
            time.sleep(config.ANALYSIS_INTERVAL)

    def start(self) -> None:
        if config.DEBUG_LOG:
            print("Starting Cognitive Agent (web backend)...")
        self.start_keyboard_listener()
        threading.Thread(target=self.monitor_active_app, daemon=True).start()
        threading.Thread(target=self.analysis_loop, daemon=True).start()

    def stop(self) -> None:
        self.stop_event.set()
        if self.listener:
            self.listener.stop()
        if config.DEBUG_LOG:
            print("Cognitive Agent stopped.")
