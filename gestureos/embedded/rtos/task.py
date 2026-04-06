"""RTOS Task model."""

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import List, Tuple


class TaskState(Enum):
    READY = auto()
    RUNNING = auto()
    BLOCKED = auto()
    COMPLETED = auto()
    MISSED = auto()


class SchedulingMode(Enum):
    EDF = auto()
    EMS = auto()
    HYBRID = auto()


@dataclass
class RTOSTask:
    task_id: int
    name: str
    period: int          # ms
    wcet: int            # worst-case execution time (ms)
    deadline: int        # relative deadline (ms)
    priority: float      # static priority (for EMS: 1/period)
    is_hard: bool = True # hard vs soft real-time

    release_time: int = 0
    abs_deadline: int = 0
    remaining: int = 0
    state: TaskState = TaskState.READY
    miss_count: int = 0

    exec_log: List[Tuple[int, int]] = field(default_factory=list)
    _exec_start: int = -1

    def release(self, tick: int):
        self.release_time = tick
        self.abs_deadline = tick + self.deadline
        self.remaining = self.wcet
        self.state = TaskState.READY
        self._exec_start = -1

    @property
    def utilization(self) -> float:
        return self.wcet / self.period
