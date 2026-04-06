"""Timer/Counter and Watchdog Timer simulation.

Models 8051 Timer 0 and Timer 1 in Mode 1 (16-bit timer) and Mode 2 (8-bit auto-reload).
Watchdog resets the MCU if not fed within the timeout period.
"""

import threading
import time
from typing import Callable, Optional

from gestureos.embedded.mcu.core_8051 import (
    MCU8051, SFR_TCON, SFR_TMOD, SFR_TL0, SFR_TH0, SFR_TL1, SFR_TH1,
    TCON_TR0, TCON_TF0, TCON_TR1, TCON_TF1,
)
from gestureos import config


class TimerPeripheral:
    """8051 Timer 0/1 simulation with overflow interrupt generation."""

    def __init__(self, mcu: MCU8051):
        self._mcu = mcu
        self._lock = threading.Lock()
        self._overflow_count = [0, 0]
        self._on_overflow: Optional[Callable] = None

    def set_overflow_callback(self, cb: Callable):
        self._on_overflow = cb

    def tick(self):
        """Called every machine cycle. Advances timers if running."""
        tcon = self._mcu.sfr_read(SFR_TCON)
        tmod = self._mcu.sfr_read(SFR_TMOD)

        if tcon & TCON_TR0:
            self._tick_timer(0, tmod & 0x0F, tcon)

        if tcon & TCON_TR1:
            self._tick_timer(1, (tmod >> 4) & 0x0F, tcon)

    def _tick_timer(self, timer_num: int, mode: int, tcon: int):
        if timer_num == 0:
            tl_addr, th_addr = SFR_TL0, SFR_TH0
            tf_mask = TCON_TF0
        else:
            tl_addr, th_addr = SFR_TL1, SFR_TH1
            tf_mask = TCON_TF1

        tl = self._mcu.sfr_read(tl_addr)
        th = self._mcu.sfr_read(th_addr)

        timer_mode = mode & 0x03

        if timer_mode == 1:  # 16-bit timer
            val = (th << 8) | tl
            val += 1
            if val > 0xFFFF:
                val = 0
                self._mcu.sfr_write(SFR_TCON, tcon | tf_mask)
                self._overflow_count[timer_num] += 1
                if self._on_overflow:
                    self._on_overflow(timer_num)
                self._mcu.request_interrupt(
                    f"Timer{timer_num}", 0x000B if timer_num == 0 else 0x001B
                )
            self._mcu.sfr_write(tl_addr, val & 0xFF)
            self._mcu.sfr_write(th_addr, (val >> 8) & 0xFF)

        elif timer_mode == 2:  # 8-bit auto-reload
            tl += 1
            if tl > 0xFF:
                tl = th  # reload from TH
                self._mcu.sfr_write(SFR_TCON, tcon | tf_mask)
                self._overflow_count[timer_num] += 1
                if self._on_overflow:
                    self._on_overflow(timer_num)
            self._mcu.sfr_write(tl_addr, tl & 0xFF)

    def get_overflow_counts(self):
        return list(self._overflow_count)

    def get_snapshot(self) -> dict:
        tmod = self._mcu.sfr_read(SFR_TMOD)
        tcon = self._mcu.sfr_read(SFR_TCON)
        return {
            "timer0": {
                "TL": self._mcu.sfr_read(SFR_TL0),
                "TH": self._mcu.sfr_read(SFR_TH0),
                "running": bool(tcon & TCON_TR0),
                "overflow": bool(tcon & TCON_TF0),
                "mode": tmod & 0x03,
                "overflows": self._overflow_count[0],
            },
            "timer1": {
                "TL": self._mcu.sfr_read(SFR_TL1),
                "TH": self._mcu.sfr_read(SFR_TH1),
                "running": bool(tcon & TCON_TR1),
                "overflow": bool(tcon & TCON_TF1),
                "mode": (tmod >> 4) & 0x03,
                "overflows": self._overflow_count[1],
            },
        }


class WatchdogTimer:
    """Software watchdog — resets the MCU if not fed within timeout."""

    def __init__(self, mcu: MCU8051, timeout_s: float = 5.0):
        self._mcu = mcu
        self._timeout = timeout_s
        self._last_feed = time.time()
        self._enabled = False
        self._reset_count = 0
        self._on_reset: Optional[Callable] = None

    def enable(self):
        self._enabled = True
        self._last_feed = time.time()

    def disable(self):
        self._enabled = False

    def feed(self):
        self._last_feed = time.time()

    def set_reset_callback(self, cb: Callable):
        self._on_reset = cb

    def check(self):
        if not self._enabled:
            return
        if time.time() - self._last_feed > self._timeout:
            self._reset_count += 1
            self._mcu.reset()
            self._last_feed = time.time()
            if self._on_reset:
                self._on_reset(self._reset_count)

    @property
    def time_remaining(self) -> float:
        if not self._enabled:
            return float("inf")
        return max(0, self._timeout - (time.time() - self._last_feed))

    @property
    def reset_count(self) -> int:
        return self._reset_count

    @property
    def enabled(self) -> bool:
        return self._enabled
