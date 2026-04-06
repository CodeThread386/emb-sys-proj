"""UART Simulator — full frame-level serial protocol model.

Serializes gesture commands into UART frames with start bit, data bits,
parity, and stop bit. Generates waveform data for visualization.
"""

import threading
import time
from typing import List, Optional
from dataclasses import dataclass, field

from gestureos.embedded.mcu.core_8051 import (
    MCU8051, SFR_SCON, SFR_SBUF, SCON_TI, SCON_RI,
)
from gestureos import config


@dataclass
class UARTFrame:
    """One complete UART frame with bit-level detail."""
    timestamp: float
    data_byte: int
    bits: List[int] = field(default_factory=list)
    # bits layout: [start, d0, d1, ..., d7, parity?, stop]
    character: str = ""
    direction: str = "TX"  # TX or RX


class UARTSimulator:
    def __init__(self, mcu: MCU8051):
        self._mcu = mcu
        self._lock = threading.Lock()
        self._baud = config.UART_BAUD_RATE
        self._data_bits = config.UART_DATA_BITS
        self._parity = config.UART_PARITY
        self._stop_bits = config.UART_STOP_BITS

        self._tx_history: List[UARTFrame] = []
        self._rx_history: List[UARTFrame] = []
        self._waveform: List[int] = []  # bit-level waveform (0/1 values)
        self._max_frames = 50

        self._bit_period_us = 1_000_000 / self._baud

    def transmit_byte(self, data: int) -> UARTFrame:
        """Serialize one byte into a UART frame and generate the waveform."""
        data &= 0xFF
        bits = [0]  # start bit (low)

        for i in range(self._data_bits):
            bits.append((data >> i) & 1)

        if self._parity == "EVEN":
            bits.append(sum(bits[1:]) % 2)
        elif self._parity == "ODD":
            bits.append(1 - (sum(bits[1:]) % 2))

        for _ in range(self._stop_bits):
            bits.append(1)  # stop bit (high)

        char = chr(data) if 32 <= data < 127 else f"0x{data:02X}"

        frame = UARTFrame(
            timestamp=time.time(),
            data_byte=data,
            bits=bits,
            character=char,
            direction="TX",
        )

        with self._lock:
            self._tx_history.append(frame)
            if len(self._tx_history) > self._max_frames:
                self._tx_history = self._tx_history[-self._max_frames:]

            self._waveform.extend(bits)
            idle_bits = [1] * 2
            self._waveform.extend(idle_bits)
            max_waveform = config.WAVEFORM_VISIBLE_SAMPLES
            if len(self._waveform) > max_waveform:
                self._waveform = self._waveform[-max_waveform:]

        self._mcu.sfr_write(SFR_SBUF, data)
        scon = self._mcu.sfr_read(SFR_SCON)
        self._mcu.sfr_write(SFR_SCON, scon | SCON_TI)

        return frame

    def transmit_string(self, text: str) -> List[UARTFrame]:
        """Transmit a string as a sequence of UART frames."""
        frames = []
        for ch in text:
            frames.append(self.transmit_byte(ord(ch)))
        return frames

    def receive_byte(self, data: int) -> UARTFrame:
        """Simulate receiving a byte (for RX waveform display)."""
        data &= 0xFF
        bits = [0]
        for i in range(self._data_bits):
            bits.append((data >> i) & 1)
        if self._parity != "NONE":
            bits.append(0)
        bits.append(1)

        char = chr(data) if 32 <= data < 127 else f"0x{data:02X}"
        frame = UARTFrame(
            timestamp=time.time(),
            data_byte=data,
            bits=bits,
            character=char,
            direction="RX",
        )

        with self._lock:
            self._rx_history.append(frame)
            if len(self._rx_history) > self._max_frames:
                self._rx_history = self._rx_history[-self._max_frames:]

        scon = self._mcu.sfr_read(SFR_SCON)
        self._mcu.sfr_write(SFR_SCON, scon | SCON_RI)
        self._mcu.sfr_write(SFR_SBUF, data)

        return frame

    def get_waveform(self) -> List[int]:
        with self._lock:
            return list(self._waveform)

    def get_tx_history(self) -> List[UARTFrame]:
        with self._lock:
            return list(self._tx_history)

    def get_config_str(self) -> str:
        return f"{self._baud}-{self._data_bits}{self._parity[0]}{self._stop_bits}"

    @property
    def bit_period_us(self) -> float:
        return self._bit_period_us

    @property
    def baud_rate(self) -> int:
        return self._baud
