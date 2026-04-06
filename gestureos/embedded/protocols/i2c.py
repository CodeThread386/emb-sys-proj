"""I2C Protocol Simulator — bit-level frame encoding with proper protocol semantics.

Models the actual I2C wire protocol: START, address+R/W, ACK/NACK, data, STOP.
Generates SDA/SCL waveform data for the logic analyzer view.
"""

import threading
import time
from typing import List, Tuple
from dataclasses import dataclass, field

from gestureos import config


@dataclass
class I2CFrame:
    timestamp: float
    slave_addr: int          # 7-bit address
    rw: str                  # "W" or "R"
    data: List[int]          # payload bytes
    acked: bool = True
    sda_waveform: List[int] = field(default_factory=list)
    scl_waveform: List[int] = field(default_factory=list)
    description: str = ""


class I2CSimulator:
    def __init__(self):
        self._lock = threading.Lock()
        self._history: List[I2CFrame] = []
        self._sda_wave: List[int] = []
        self._scl_wave: List[int] = []
        self._max_frames = 30
        self._max_wave = config.WAVEFORM_VISIBLE_SAMPLES

    def transfer(self, slave_addr: int, rw: str, data: List[int],
                 description: str = "") -> I2CFrame:
        """Generate a complete I2C transaction with bit-level waveforms.

        Protocol: START → ADDR+RW → ACK → DATA0 → ACK → ... → STOP
        """
        sda = []
        scl = []

        # Idle: SDA=1, SCL=1
        sda.extend([1, 1])
        scl.extend([1, 1])

        # START condition: SDA falls while SCL is high
        sda.extend([1, 0])
        scl.extend([1, 1])

        # Address byte: 7-bit addr + R/W bit
        addr_byte = (slave_addr << 1) | (1 if rw == "R" else 0)
        self._add_byte_to_waveform(addr_byte, sda, scl)

        # ACK from slave
        sda.append(0)  # ACK = low
        scl.extend([0, 1, 0])
        sda.extend([0, 0])

        # Data bytes with ACK
        for byte in data:
            self._add_byte_to_waveform(byte, sda, scl)
            sda.append(0)  # ACK
            scl.extend([0, 1, 0])
            sda.extend([0, 0])

        # STOP condition: SDA rises while SCL is high
        sda.extend([0, 0, 1])
        scl.extend([0, 1, 1])

        # Idle
        sda.extend([1, 1])
        scl.extend([1, 1])

        frame = I2CFrame(
            timestamp=time.time(),
            slave_addr=slave_addr,
            rw=rw,
            data=data,
            acked=True,
            sda_waveform=sda,
            scl_waveform=scl,
            description=description,
        )

        with self._lock:
            self._history.append(frame)
            if len(self._history) > self._max_frames:
                self._history = self._history[-self._max_frames:]

            self._sda_wave.extend(sda)
            self._scl_wave.extend(scl)
            if len(self._sda_wave) > self._max_wave:
                self._sda_wave = self._sda_wave[-self._max_wave:]
                self._scl_wave = self._scl_wave[-self._max_wave:]

        return frame

    def _add_byte_to_waveform(self, byte: int, sda: list, scl: list):
        """Clock out 8 bits MSB-first onto SDA with SCL pulses."""
        for bit_pos in range(7, -1, -1):
            bit = (byte >> bit_pos) & 1
            scl.append(0)     # SCL low (setup)
            sda.append(bit)   # SDA data
            scl.append(1)     # SCL high (sample)
            sda.append(bit)
            scl.append(0)     # SCL low
            sda.append(bit)

    def get_history(self) -> List[I2CFrame]:
        with self._lock:
            return list(self._history)

    def get_sda_waveform(self) -> List[int]:
        with self._lock:
            return list(self._sda_wave)

    def get_scl_waveform(self) -> List[int]:
        with self._lock:
            return list(self._scl_wave)

    @staticmethod
    def decode_frame_str(frame: I2CFrame) -> str:
        addr_str = f"0x{frame.slave_addr:02X}"
        data_str = " ".join(f"0x{b:02X}" for b in frame.data)
        return f"[{frame.rw}] Addr={addr_str} Data=[{data_str}] {'ACK' if frame.acked else 'NACK'}"
