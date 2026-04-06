"""Main Dashboard — combines webcam feed with embedded systems visualizations."""

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QSplitter, QFrame, QProgressBar, QTabWidget, QCheckBox,
)
from PyQt6.QtCore import Qt, QTimer
from PyQt6.QtGui import QFont

from gestureos.ui.webcam_widget import WebcamWidget
from gestureos.ui.register_view import RegisterView
from gestureos.ui.waveform_view import WaveformView
from gestureos.ui.adc_view import ADCView
from gestureos.ui.scheduler_view import SchedulerView
from gestureos import config


class Dashboard(QMainWindow):
    def __init__(self, app_core):
        """app_core is the AppCore instance from main.py that holds all components."""
        super().__init__()
        self._core = app_core
        self.setWindowTitle("GestureOS — Touchless Desktop Control + Embedded Systems Visualization")
        self.setMinimumSize(1400, 850)
        self.setStyleSheet("""
            QMainWindow { background-color: #0a0a23; }
            QLabel { color: #e0e0e0; }
            QFrame { border: 1px solid #222; border-radius: 4px; }
            QTabWidget::pane { border: 1px solid #333; background: #0a0a23; }
            QTabBar::tab { background: #16213e; color: #aaa; padding: 6px 14px;
                           border: 1px solid #333; border-bottom: none; border-radius: 4px 4px 0 0; }
            QTabBar::tab:selected { background: #0f3460; color: #fff; }
        """)

        self._setup_ui()
        self._start_timers()

    def _setup_ui(self):
        central = QWidget()
        self.setCentralWidget(central)
        main_layout = QVBoxLayout(central)
        main_layout.setContentsMargins(6, 6, 6, 6)
        main_layout.setSpacing(4)

        # Top section: webcam + gesture info + controls
        top = QSplitter(Qt.Orientation.Horizontal)

        # Left: webcam
        cam_frame = QFrame()
        cam_layout = QVBoxLayout(cam_frame)
        cam_layout.setContentsMargins(4, 4, 4, 4)
        self._webcam = WebcamWidget()
        self._webcam.setFixedSize(400, 300)
        cam_layout.addWidget(self._webcam)

        self._gesture_label = QLabel("Gesture: NONE")
        self._gesture_label.setFont(QFont("Monospace", 14, QFont.Weight.Bold))
        self._gesture_label.setStyleSheet("color: #00d4ff; border: none;")
        self._gesture_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cam_layout.addWidget(self._gesture_label)

        self._action_label = QLabel("Action: —")
        self._action_label.setFont(QFont("Monospace", 11))
        self._action_label.setStyleSheet("color: #2ecc71; border: none;")
        self._action_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        cam_layout.addWidget(self._action_label)

        self._control_check = QCheckBox("Desktop Control Enabled")
        self._control_check.setChecked(True)
        self._control_check.setStyleSheet("color: #e0e0e0; border: none;")
        self._control_check.toggled.connect(self._toggle_control)
        cam_layout.addWidget(self._control_check)

        top.addWidget(cam_frame)

        # Right: 8051 registers
        reg_frame = QFrame()
        reg_layout = QVBoxLayout(reg_frame)
        reg_layout.setContentsMargins(4, 4, 4, 4)
        self._register_view = RegisterView()
        reg_layout.addWidget(self._register_view)
        top.addWidget(reg_frame)

        top.setStretchFactor(0, 1)
        top.setStretchFactor(1, 2)

        # Bottom section: tabs for different visualizations
        bottom_tabs = QTabWidget()

        # Tab 1: Protocol Waveforms (Logic Analyzer)
        self._waveform_view = WaveformView()
        bottom_tabs.addTab(self._waveform_view, "Protocol Waveforms")

        # Tab 2: ADC/DAC Pipeline
        self._adc_view = ADCView()
        bottom_tabs.addTab(self._adc_view, "ADC/DAC Pipeline")

        # Tab 3: RTOS Scheduler
        sched_widget = QWidget()
        sched_layout = QVBoxLayout(sched_widget)
        sched_layout.setContentsMargins(0, 0, 0, 0)

        sched_info = QHBoxLayout()
        self._mode_label = QLabel("Mode: EDF")
        self._mode_label.setFont(QFont("Monospace", 11, QFont.Weight.Bold))
        self._mode_label.setStyleSheet("color: #00d4ff; border: none;")
        sched_info.addWidget(self._mode_label)

        self._util_bar = QProgressBar()
        self._util_bar.setRange(0, 1000)
        self._util_bar.setFixedHeight(20)
        self._util_bar.setFormat("U = 0.000")
        self._util_bar.setStyleSheet("""
            QProgressBar { border: 1px solid #333; border-radius: 3px;
                           background: #16213e; text-align: center; color: white; }
            QProgressBar::chunk { background: #2ecc71; border-radius: 2px; }
        """)
        sched_info.addWidget(self._util_bar)

        self._feasible_label = QLabel("Feasible: Yes")
        self._feasible_label.setFont(QFont("Monospace", 10))
        self._feasible_label.setStyleSheet("color: #2ecc71; border: none;")
        sched_info.addWidget(self._feasible_label)

        sched_layout.addLayout(sched_info)
        self._scheduler_view = SchedulerView()
        sched_layout.addWidget(self._scheduler_view)
        bottom_tabs.addTab(sched_widget, "RTOS Scheduler")

        # Main splitter
        v_splitter = QSplitter(Qt.Orientation.Vertical)
        v_splitter.addWidget(top)
        v_splitter.addWidget(bottom_tabs)
        v_splitter.setStretchFactor(0, 2)
        v_splitter.setStretchFactor(1, 3)

        main_layout.addWidget(v_splitter)

        # Status bar
        self._status = self.statusBar()
        self._status.setStyleSheet(
            "background: #0f3460; color: #e0e0e0; font-size: 12px; padding: 2px;")
        self._status.showMessage("GestureOS Ready")

    def _toggle_control(self, checked: bool):
        self._core.controller.set_desktop_control(checked)

    def _start_timers(self):
        self._refresh_timer = QTimer()
        self._refresh_timer.timeout.connect(self._refresh_ui)
        self._refresh_timer.start(config.UI_REFRESH_MS)

    def _refresh_ui(self):
        # Webcam
        frame = self._core.engine.get_frame()
        if frame is not None:
            self._webcam.update_frame(frame)

        # Gesture / Action labels
        gesture = self._core.controller.latest_gesture
        action = self._core.controller.latest_action
        cmd = config.GESTURE_COMMANDS.get(gesture, {})
        desc = cmd.get("desc", "—")

        self._gesture_label.setText(f"Gesture: {gesture}")
        if gesture != "NONE":
            self._gesture_label.setStyleSheet("color: #2ecc71; border: none;")
        else:
            self._gesture_label.setStyleSheet("color: #555; border: none;")

        self._action_label.setText(f"Action: {desc}")

        # 8051 Registers
        mcu_snap = self._core.mcu.get_snapshot()
        self._register_view.update_state(mcu_snap)

        # Protocol waveforms
        uart_wave = self._core.uart.get_waveform()
        i2c_sda = self._core.i2c.get_sda_waveform()
        i2c_scl = self._core.i2c.get_scl_waveform()

        can_frames = self._core.can.get_history()
        can_bits = []
        for f in can_frames[-5:]:
            for ch in f.frame_bits:
                if ch in ('0', '1'):
                    can_bits.append(int(ch))

        self._waveform_view.update_waveforms(uart_wave, i2c_sda, i2c_scl, can_bits[-300:])

        # ADC/DAC
        adc_hist = self._core.adc.get_history()
        dac_hist = self._core.dac.get_history()
        self._adc_view.update_data(
            adc_hist, dac_hist,
            self._core.adc.max_value, config.ADC_VREF,
        )

        # RTOS Scheduler
        sched_snap = self._core.scheduler.get_snapshot()
        sched_hist = self._core.scheduler.get_history()
        self._scheduler_view.update_from_snapshot(sched_snap, sched_hist)

        u = sched_snap.get("utilization", 0)
        bound = sched_snap.get("bound", 1)
        feasible = sched_snap.get("feasible", True)
        mode = sched_snap.get("mode", "EDF")

        self._mode_label.setText(f"Mode: {mode}")
        self._util_bar.setValue(int(u * 1000))
        self._util_bar.setFormat(f"U = {u:.3f} / {bound:.3f}")
        self._feasible_label.setText(f"Feasible: {'Yes' if feasible else 'NO!'}")
        self._feasible_label.setStyleSheet(
            f"color: {'#2ecc71' if feasible else '#e74c3c'}; border: none;")

        pct = u / max(bound, 0.01)
        bar_color = "#2ecc71" if pct < 0.7 else "#f1c40f" if pct < 0.9 else "#e74c3c"
        self._util_bar.setStyleSheet(f"""
            QProgressBar {{ border: 1px solid #333; border-radius: 3px;
                           background: #16213e; text-align: center; color: white; }}
            QProgressBar::chunk {{ background: {bar_color}; border-radius: 2px; }}
        """)

        # Status bar
        tick = sched_snap.get("tick", 0)
        n_tasks = len(sched_snap.get("tasks", []))
        timer_snap = self._core.timer.get_snapshot()
        t0_ovf = timer_snap["timer0"]["overflows"]

        self._status.showMessage(
            f"Gesture={gesture} | Mode={mode} | Tasks={n_tasks} | "
            f"U={u:.3f}/{bound:.3f} | {'FEASIBLE' if feasible else 'OVERLOADED'} | "
            f"Timer0 OVF={t0_ovf} | MCU cycles={mcu_snap['cycles']} | Tick={tick}"
        )
