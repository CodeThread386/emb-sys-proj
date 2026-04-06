"""RTOS Scheduler timeline visualization."""

from typing import Dict, List
from collections import defaultdict

import pyqtgraph as pg
from gestureos import config


STATE_COLORS = {
    "RUNNING": (46, 204, 113, 200),
    "READY": (241, 196, 15, 150),
    "MISSED": (231, 76, 60, 200),
    "COMPLETED": (149, 165, 166, 80),
    "BLOCKED": (155, 89, 182, 150),
}


class SchedulerView(pg.PlotWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setBackground("#0a0a23")
        self.setTitle("RTOS Scheduler Timeline", color="w", size="11pt")
        self.setLabel("bottom", "Tick")
        self.showGrid(x=True, y=False, alpha=0.15)
        self.setMouseEnabled(x=True, y=False)

        self._task_rows: Dict[int, int] = {}
        self._task_names: Dict[int, str] = {}
        self._next_row = 0
        self._max_visible = 200

    def update_from_snapshot(self, snapshot: dict, history: List[dict]):
        tasks = snapshot.get("tasks", [])
        current_tick = snapshot.get("tick", 0)

        for t in tasks:
            tid = t["id"]
            if tid not in self._task_rows:
                self._task_rows[tid] = self._next_row
                self._task_names[tid] = t["name"]
                self._next_row += 1

        self.clear()

        window_start = max(0, current_tick - self._max_visible)

        points_by_state: Dict[str, list] = defaultdict(list)

        for h in history:
            tick = h.get("tick", 0)
            if tick < window_start:
                continue
            current_id = h.get("current_id", -1)
            for tid_str, info in h.get("tasks", {}).items():
                tid = int(tid_str)
                row = self._task_rows.get(tid, 0)
                state = info["state"]
                if tid == current_id and state == "RUNNING":
                    points_by_state["RUNNING"].append((tick, row))
                elif state == "MISSED":
                    points_by_state["MISSED"].append((tick, row))
                elif state in ("READY", "RUNNING"):
                    points_by_state["READY"].append((tick, row))

        for state, pts in points_by_state.items():
            if not pts:
                continue
            color = STATE_COLORS.get(state, (100, 100, 100, 100))
            scatter = pg.ScatterPlotItem(
                x=[p[0] for p in pts], y=[p[1] for p in pts],
                pen=pg.mkPen(None), brush=pg.mkBrush(*color),
                size=6, symbol="s",
            )
            self.addItem(scatter)

        self.setXRange(window_start, current_tick + 5, padding=0)

        if self._task_names:
            ticks = [(row, name) for tid, row in self._task_rows.items()
                     for name in [self._task_names.get(tid, f"T{tid}")]]
            self.getAxis("left").setTicks([ticks])
