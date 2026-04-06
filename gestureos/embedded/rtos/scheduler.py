"""RTOS Scheduler — EDF, EMS (Rate Monotonic), and Hybrid policies.

Runs the gesture engine, protocol handlers, and system control as
real-time tasks with live scheduling visualization.
"""

import threading
import time
from typing import Dict, Optional, List

from gestureos.embedded.rtos.task import RTOSTask, TaskState, SchedulingMode
from gestureos import config


class RTOSScheduler:
    def __init__(self):
        self._lock = threading.Lock()
        self._tasks: Dict[int, RTOSTask] = {}
        self._current: Optional[RTOSTask] = None
        self._mode = SchedulingMode.EDF
        self._tick: int = 0
        self._next_id = 1
        self._running = False
        self._thread: Optional[threading.Thread] = None

        self._tick_history: List[dict] = []
        self._max_history = config.WAVEFORM_VISIBLE_SAMPLES

    def add_task(self, name: str, period: int, wcet: int,
                 deadline: int = 0, is_hard: bool = True) -> int:
        with self._lock:
            tid = self._next_id
            self._next_id += 1
            if deadline <= 0:
                deadline = period
            task = RTOSTask(
                task_id=tid, name=name, period=period, wcet=wcet,
                deadline=deadline, priority=1.0 / period, is_hard=is_hard,
                release_time=self._tick, abs_deadline=self._tick + deadline,
                remaining=wcet,
            )
            self._tasks[tid] = task
        return tid

    def remove_task(self, tid: int):
        with self._lock:
            self._tasks.pop(tid, None)
            if self._current and self._current.task_id == tid:
                self._current = None

    def set_mode(self, mode: SchedulingMode):
        self._mode = mode

    @property
    def mode(self) -> SchedulingMode:
        return self._mode

    @property
    def current_tick(self) -> int:
        return self._tick

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
            self._do_tick()
            time.sleep(max(0.0005, config.RTOS_TICK_MS / 1000.0 / config.RTOS_SPEED_FACTOR))

    def _do_tick(self):
        with self._lock:
            self._tick += 1

            # Release periodic jobs
            for t in self._tasks.values():
                if t.state in (TaskState.COMPLETED, TaskState.MISSED):
                    if self._tick - t.release_time >= t.period:
                        t.release(self._tick)

            # Check deadline violations
            for t in self._tasks.values():
                if t.state in (TaskState.READY, TaskState.RUNNING):
                    if self._tick >= t.abs_deadline and t.remaining > 0:
                        t.state = TaskState.MISSED
                        t.miss_count += 1
                        if self._current and self._current.task_id == t.task_id:
                            self._current = None

            # Select next task
            selected = self._select()

            # Preempt if needed
            if (self._current and selected and
                    selected.task_id != self._current.task_id):
                if self._current.state == TaskState.RUNNING:
                    self._current.state = TaskState.READY

            # Execute
            if selected:
                if selected.state == TaskState.READY:
                    selected.state = TaskState.RUNNING
                    selected._exec_start = self._tick
                self._current = selected
                selected.remaining -= 1
                if selected.remaining <= 0:
                    selected.state = TaskState.COMPLETED
                    if selected._exec_start >= 0:
                        selected.exec_log.append((selected._exec_start, self._tick))
            else:
                self._current = None

            # Record history
            snapshot = {
                "tick": self._tick,
                "current_id": self._current.task_id if self._current else -1,
                "tasks": {
                    tid: {"state": t.state.name, "remaining": t.remaining,
                          "deadline": t.abs_deadline, "misses": t.miss_count}
                    for tid, t in self._tasks.items()
                },
            }
            self._tick_history.append(snapshot)
            if len(self._tick_history) > self._max_history:
                self._tick_history = self._tick_history[-self._max_history:]

    def _select(self) -> Optional[RTOSTask]:
        ready = [t for t in self._tasks.values()
                 if t.state in (TaskState.READY, TaskState.RUNNING)]
        if not ready:
            return None

        if self._mode == SchedulingMode.EDF:
            return min(ready, key=lambda t: t.abs_deadline)
        elif self._mode == SchedulingMode.EMS:
            return max(ready, key=lambda t: t.priority)
        else:  # HYBRID
            hard = [t for t in ready if t.is_hard]
            soft = [t for t in ready if not t.is_hard]
            if hard:
                return min(hard, key=lambda t: t.abs_deadline)
            elif soft:
                return max(soft, key=lambda t: t.priority)
            return None

    def get_utilization(self) -> tuple:
        with self._lock:
            tasks = list(self._tasks.values())
        if not tasks:
            return 0.0, 1.0, True
        u = sum(t.wcet / t.period for t in tasks)
        n = len(tasks)
        if self._mode == SchedulingMode.EDF:
            bound = 1.0
        else:
            bound = n * (2 ** (1.0 / n) - 1) if n > 0 else 1.0
        return round(u, 4), round(bound, 4), u <= bound

    def get_snapshot(self) -> dict:
        with self._lock:
            tasks = []
            for t in self._tasks.values():
                tasks.append({
                    "id": t.task_id, "name": t.name,
                    "period": t.period, "wcet": t.wcet,
                    "deadline": t.deadline, "state": t.state.name,
                    "misses": t.miss_count, "is_hard": t.is_hard,
                    "utilization": round(t.utilization, 4),
                    "remaining": t.remaining,
                })
            current = self._current.name if self._current else "IDLE"
        u, bound, feasible = self.get_utilization()
        return {
            "tick": self._tick, "mode": self._mode.name,
            "tasks": tasks, "current": current,
            "utilization": u, "bound": bound, "feasible": feasible,
        }

    def get_history(self) -> List[dict]:
        with self._lock:
            return list(self._tick_history)
